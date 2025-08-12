import os
import random
import logging
import sys
import traceback
import bcrypt
from datetime import datetime, timedelta
from flask import request, jsonify, render_template, session
from flask_mail import Message
from routes.Auth.utils import get_db_connection
from . import login_bp
from extensions import csrf

# ---- BASIC PAGE ROUTES (already present) ----

@login_bp.route("/forgot_password")
def forgot_password():
    return render_template("Login/forgot_password.html")

@login_bp.route("/contact_admin")
def contact_admin():
    return render_template("Login/contact_admin.html")

@login_bp.route("/enter_code")
def enter_code():
    return render_template("Login/enter_code.html")

@login_bp.route("/reset_password")
def reset_password():
    return render_template("Login/reset_password.html")

# ---- API ROUTES FOR FORGOT PASSWORD FLOW ----

def send_contact_admin_email(first_name, last_name, sender_email_address, message_body):
    from app import mail
    import os
    import logging
    from flask_mail import Message

    admin_email = os.getenv("ADMIN_CONTACT_EMAIL")
    if not admin_email:
        logging.error("❌ ADMIN_CONTACT_EMAIL is not set in the .env file")
        return False

    sender_email = os.getenv("EMAIL_USER")
    if not sender_email:
        logging.error("❌ EMAIL_USER is not set in the .env file")
        return False

    subject = "Password Reset Assistance Requested"
    body = f"""A user has requested password reset assistance.

Name: {first_name} {last_name}
Email: {sender_email_address}

Message:
{message_body}
"""

    msg = Message(
        subject=subject,
        sender=sender_email,
        recipients=[admin_email]
    )
    msg.body = body

    try:
        mail.send(msg)
        logging.info(f"✅ Contact admin email sent successfully to {admin_email}")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to send contact email to {admin_email}: {e}")
        return False

def generate_reset_code():
    return str(random.randint(100000, 999999))

def send_reset_code_email(email, code):
    from app import mail
    sender_email = os.getenv("EMAIL_USER")
    if not sender_email:
        logging.error("EMAIL_USER not set in .env")
        return False

    msg = Message(
        subject="Your Password Reset Code",
        sender=sender_email,
        recipients=[email]
    )
    msg.body = f"Your password reset code is: {code}. This code expires in 10 minutes."
    try:
        mail.send(msg)
        logging.info(f"✅ Password reset code sent to {email}")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to send password reset code to {email}: {e}")
        return False

# 1. Request password reset code (POST: send code to email)
@csrf.exempt
@login_bp.route("/api/forgot_password/request_code", methods=["POST"])
def api_forgot_password_request_code():
    data = request.get_json()
    email = data.get("email")
    user_type = data.get("user_type", "employee")  # default to employee

    if not email:
        return jsonify({"error": "Email is required."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Lookup user
        if user_type == "employee":
            cur.execute("SELECT employee_id FROM employees WHERE email = %s", (email,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "No employee account found with this email."}), 404
            user_id = row[0]
            id_field = "employee_id"
        elif user_type == "admin":
            cur.execute("SELECT admin_id FROM admins WHERE email = %s", (email,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "No admin account found with this email."}), 404
            user_id = row[0]
            id_field = "admin_id"
        else:
            return jsonify({"error": "Invalid user type."}), 400

        # Generate & save reset code
        code = generate_reset_code()
        timestamp = datetime.utcnow()
        cur.execute(f"""
            INSERT INTO two_factor_verifications ({id_field}, verification_code, is_verified, verification_timestamp, purpose)
            VALUES (%s, %s, FALSE, %s, 'reset')
        """, (user_id, code, timestamp))
        conn.commit()

        # Send code via email
        send_reset_code_email(email, code)
        # Optionally, store email/user_type in session for next steps (stateless: let frontend keep)
        return jsonify({"success": True, "message": "Reset code sent to email."})
    finally:
        cur.close()
        conn.close()

# 2. Verify code (POST: verify code for email)
@csrf.exempt
@login_bp.route("/api/forgot_password/verify_code", methods=["POST"])
def api_forgot_password_verify_code():
    data = request.get_json()
    email = data.get("email")
    code = data.get("code")
    user_type = data.get("user_type", "employee")

    if not email or not code:
        return jsonify({"error": "Email and code are required."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if user_type == "employee":
            cur.execute("SELECT employee_id FROM employees WHERE email = %s", (email,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "No employee found."}), 404
            user_id = row[0]
            id_field = "employee_id"
        elif user_type == "admin":
            cur.execute("SELECT admin_id FROM admins WHERE email = %s", (email,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "No admin found."}), 404
            user_id = row[0]
            id_field = "admin_id"
        else:
            return jsonify({"error": "Invalid user type."}), 400

        # Check code (valid for last 10 min, not used)
        cur.execute(f"""
            SELECT verification_code, verification_timestamp FROM two_factor_verifications
            WHERE {id_field} = %s AND purpose = 'reset' AND is_verified = FALSE
            ORDER BY verification_timestamp DESC LIMIT 1
        """, (user_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "No reset code found. Please request a new one."}), 400
        stored_code, sent_time = row
        if code != stored_code:
            return jsonify({"error": "Invalid code."}), 400
        if sent_time < datetime.utcnow() - timedelta(minutes=10):
            return jsonify({"error": "Code expired. Please request a new one."}), 400

        # Mark as verified
        cur.execute(f"""
            UPDATE two_factor_verifications SET is_verified = TRUE
            WHERE {id_field} = %s AND verification_code = %s AND purpose = 'reset'
        """, (user_id, code))
        conn.commit()
        return jsonify({"success": True, "message": "Code verified."})
    finally:
        cur.close()
        conn.close()

# 3. Reset password (POST: after code is verified)

@csrf.exempt
@login_bp.route("/api/forgot_password/reset_password", methods=["POST"])
def api_forgot_password_reset_password():
    def debug_log(msg):
        print(f"[DEBUG][reset_password]: {msg}", file=sys.stderr)

    try:
        data = request.get_json()
        debug_log(f"Received data: {data}")
        email = data.get("email")
        new_password = data.get("new_password")
        user_type = data.get("user_type", "employee")

        if not email or not new_password:
            debug_log("Email or new_password missing.")
            return jsonify({"error": "Email and new password are required."}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            debug_log(f"Processing user_type: {user_type}")
            hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

            if user_type == "employee":
                cur.execute("SELECT employee_id FROM employees WHERE email = %s", (email,))
                row = cur.fetchone()
                debug_log(f"Employee row: {row}")
                if not row:
                    debug_log("No employee found.")
                    return jsonify({"error": "No employee found."}), 404
                user_id = row[0]
                debug_log(f"Updating employee_id {user_id} with new hashed password.")
                cur.execute("UPDATE employees SET password = %s WHERE employee_id = %s", (hashed, user_id))

            elif user_type == "admin":
                # Check admins table first
                cur.execute("SELECT admin_id FROM admins WHERE email = %s", (email,))
                admin_row = cur.fetchone()
                debug_log(f"Admin row: {admin_row}")

                # Check employees table too
                cur.execute("SELECT employee_id FROM employees WHERE email = %s", (email,))
                employee_row = cur.fetchone()
                debug_log(f"Employee row: {employee_row}")

                found_any = False

                if admin_row:
                    admin_id = admin_row[0]
                    debug_log(f"Updating admin_id {admin_id} with new hashed password.")
                    cur.execute("UPDATE admins SET password = %s WHERE admin_id = %s", (hashed, admin_id))
                    found_any = True

                if employee_row:
                    employee_id = employee_row[0]
                    debug_log(f"Updating employee_id {employee_id} (admin option) with new hashed password.")
                    cur.execute("UPDATE employees SET password = %s WHERE employee_id = %s", (hashed, employee_id))
                    found_any = True

                if not found_any:
                    debug_log("No admin or employee found for given email.")
                    return jsonify({"error": "No admin or employee found with that email."}), 404

            else:
                debug_log(f"Invalid user type: {user_type}")
                return jsonify({"error": "Invalid user type."}), 400

            conn.commit()
            debug_log("Password update committed successfully.")
            return jsonify({"success": True, "message": "Password updated."})
        except Exception as exc:
            debug_log(f"Exception during DB operation: {traceback.format_exc()}")
            return jsonify({"error": "Internal server error."}), 500
        finally:
            cur.close()
            conn.close()
            debug_log("DB connection closed.")
    except Exception as exc:
        debug_log(f"Exception in request processing: {traceback.format_exc()}")
        return jsonify({"error": "Invalid request."}), 400
    
@csrf.exempt
@login_bp.route("/api/contact_admin", methods=["POST"])
def api_contact_admin():
    from app import mail
    """
    Endpoint for users to contact admin for password reset/help.
    Stores request in contact_requests and notifies admin by email.
    """
    data = request.get_json()
    first_name = data.get("first_name")
    last_name = data.get("last_name")
    email = data.get("email")
    message = data.get("message")

    if not first_name or not last_name or not email or not message:
        return jsonify({"error": "All fields are required."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Insert contact request into the DB
        cur.execute("""
            INSERT INTO contact_requests (first_name, last_name, email, message, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (first_name, last_name, email, message, 'pending'))
        request_id = cur.fetchone()[0]
        conn.commit()

        # Email notification to admin
        admin_email = os.getenv("ADMIN_CONTACT_EMAIL")
        sender_email = os.getenv("EMAIL_USER")
        if not admin_email or not sender_email:
            logging.error("❌ ADMIN_CONTACT_EMAIL or EMAIL_USER not set in .env")
            # Still return success so user isn't exposed to backend config
            return jsonify({"success": True, "message": "Your message has been submitted."})

        subject = "New Password Reset Request"
        body = f"""A user has requested password reset assistance.

Name: {first_name} {last_name}
Email: {email}

Message:
{message}

(Request ID: {request_id})
"""
        msg = Message(
            subject=subject,
            sender=sender_email,
            recipients=[admin_email],
            body=body
        )
        try:
            mail.send(msg)
            logging.info(f"✅ Contact admin email sent to {admin_email}")
        except Exception as e:
            logging.error(f"❌ Failed to send admin notification email: {e}")

        return jsonify({"success": True, "message": "Your message has been submitted."})
    except Exception as e:
        logging.error(f"❌ Error in contact admin endpoint: {e}")
        return jsonify({"error": "An error occurred. Please try again later."}), 500
    finally:
        cur.close()
        conn.close()

@csrf.exempt
@login_bp.route("/api/verify_user_name_email", methods=["POST"])
def verify_user_name_email():
    """
    Checks if the provided first_name, last_name, and email match a user in any user table.
    Returns {"match": true} or {"match": false}
    """
    data = request.get_json()
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    email = data.get("email", "").strip().lower()

    # Defensive: must have all fields
    if not first_name or not last_name or not email:
        return jsonify({"match": False, "error": "Missing fields."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Search in admins, super_admins, and employees for a matching user
        # (modify table/column names if needed)
        query = """
            SELECT 1 FROM admins WHERE LOWER(email) = %s AND LOWER(first_name) = %s AND LOWER(last_name) = %s
            UNION
            SELECT 1 FROM super_admins WHERE LOWER(email) = %s AND LOWER(first_name) = %s AND LOWER(last_name) = %s
            UNION
            SELECT 1 FROM employees WHERE LOWER(email) = %s AND LOWER(first_name) = %s AND LOWER(last_name) = %s
            LIMIT 1
        """
        params = [email, first_name.lower(), last_name.lower()] * 3
        cur.execute(query, params)
        match_found = bool(cur.fetchone())
        return jsonify({"match": match_found})
    except Exception as e:
        return jsonify({"match": False, "error": str(e)}), 500
    finally:
        cur.close()
        conn.close()