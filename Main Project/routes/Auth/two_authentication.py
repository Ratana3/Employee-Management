import os
import random
import logging
from functools import wraps
from datetime import datetime, timedelta

from flask import flash, g, jsonify, redirect, render_template, request
from flask_mail import Message
from flask.cli import load_dotenv

import psycopg2
from routes.Auth.token import employee_jwt_required, get_employee_token, token_required_with_roles
from user_agents import parse

from routes.Auth.token import get_admin_from_token, verify_employee_token
from routes.Auth.utils import get_db_connection
from routes.Login import login_bp

# ============================ Shared utilities for both admin and employees ============================ (Start)

# Generate a 6-digit 2FA code
def generate_2fa_code():
    code = str(random.randint(100000, 999999))
    logging.debug(f"Generated 2FA code: {code}")
    return code

# ============================ Shared utilities for both admin and employees ============================ (End)

# ==================== Two authentication for employees ==================== (Start)
# Functions for 2FA for employees (Start)
@login_bp.route('/employee/verify-2fa', methods=['GET', 'POST'])
@employee_jwt_required()
def verify_employee_2fa():
    # Use g, as set by the decorator
    employee_id = getattr(g, "employee_id", None)
    employee_role = getattr(g, "employee_role", None)

    if not employee_id:
        logging.debug("Redirecting to login: No employee found in g.")
        return redirect('/')

    # Always redirect to dashboard after 2FA verification
    dashboard_url = '/user'  # Update this to your actual dashboard URL

    if request.method == 'POST':
        code = request.form['code']
        logging.debug(f"Employee ID: {employee_id} submitted 2FA code: {code}")

        if verify_employee_2fa_code(employee_id, code):
            # 2FA success: respond with JSON for AJAX, including token if available
            token = request.form.get('token') or request.cookies.get('employeeToken')
            logging.info(f"Employee ID: {employee_id} successfully verified 2FA.")
            response_data = {
                "status": "success",
                "success": True,
                "message": "2FA verification successful! Redirecting...",
                "redirect": dashboard_url,
                "token": token,
            }
            return jsonify(response_data)
        else:
            logging.warning(f"Employee ID: {employee_id} entered an invalid 2FA code.")
            return jsonify({
                "status": "error",
                "success": False,
                "error": "Invalid 2FA code. Please try again."
            }), 400

    return render_template('Employee/TwoFactorAuthentication.html')

# sending two-authentication code to employee's email
def send_employee_2fa_email(employee_id):
    from app import mail
    import logging

    """Sends a 2FA verification email to the employee."""

    logging.debug(f"[2FA EMAIL] Called with employee_id={employee_id} (type: {type(employee_id)})")

    if not employee_id:
        logging.error("❌ No employee ID provided")
        return False

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch employee email
        logging.debug(f"[2FA EMAIL] Executing: SELECT email FROM employees WHERE employee_id = %s", employee_id)
        cursor.execute("SELECT email FROM employees WHERE employee_id = %s", (employee_id,))
        user = cursor.fetchone()
        logging.debug(f"[2FA EMAIL] Query result for employee_id={employee_id}: {user}")

        if not user:
            logging.error(f"❌ No email found for employee ID: {employee_id}")
            return False

        email = user[0]
        logging.debug(f"[2FA EMAIL] Email found: {email}")
        code = generate_2fa_code()
        logging.debug(f"[2FA EMAIL] Generated 2FA code: {code}")

        # Store 2FA attempt in database
        timestamp = datetime.utcnow()
        logging.debug(f"[2FA EMAIL] Inserting 2FA record for employee_id={employee_id} at {timestamp}")
        cursor.execute("""
            INSERT INTO two_factor_verifications (employee_id, verification_code, is_verified, verification_timestamp)
            VALUES (%s, %s, false, %s)
        """, (employee_id, code, timestamp))
        conn.commit()
        logging.debug(f"[2FA EMAIL] 2FA record inserted.")

        sender_email = os.getenv("EMAIL_USER")
        if not sender_email:
            logging.error("❌ EMAIL_USER not set in .env")
            return False

        logging.debug(f"[2FA EMAIL] Preparing to send email: sender={sender_email}, recipient={email}")
        msg = Message(
            subject="Your 2FA Verification Code",
            sender=sender_email,
            recipients=[email]
        )
        msg.body = f"Your 2FA verification code is: {code}. This code expires in 60 seconds."

        mail.send(msg)
        logging.info(f"✅ 2FA email sent successfully to {email}")
        return True

    except Exception as db_error:
        logging.error(f"❌ Database error: {db_error}")
        import traceback
        logging.error(traceback.format_exc())
        return False
    finally:
        cursor.close()
        conn.close()
        logging.debug(f"[2FA EMAIL] Database connection closed.")

# Verify the 2FA code (For employee)
def verify_employee_2fa_code(employee_id, input_code):
    logging.debug(f"Verifying 2FA for Employee ID: {employee_id} | Input Code: {input_code}")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check failed attempts
    cursor.execute("""
        SELECT COUNT(*) FROM two_factor_verifications
        WHERE employee_id = %s AND is_verified = FALSE
        AND verification_timestamp >= NOW() - INTERVAL '5 minutes'
    """, (employee_id,))
    failed_attempts = cursor.fetchone()[0]

    if failed_attempts >= 5:
        logging.warning(f"Too many failed 2FA attempts for Employee ID: {employee_id}")
        return False

    # Get latest unverified code
    cursor.execute("""
        SELECT verification_code FROM two_factor_verifications
        WHERE employee_id = %s AND is_verified = FALSE
        ORDER BY verification_timestamp DESC
        LIMIT 1
    """, (employee_id,))
    row = cursor.fetchone()
    if not row:
        logging.warning(f"No valid 2FA code found for Employee ID: {employee_id}")
        return False

    stored_code = row[0]
    if input_code == stored_code:
        logging.debug(f"Correct 2FA code for Employee ID: {employee_id}. Marking as verified.")
        cursor.execute("""
            UPDATE two_factor_verifications
            SET is_verified = TRUE
            WHERE employee_id = %s AND verification_code = %s
        """, (employee_id, stored_code))
        conn.commit()
        return True

    logging.warning(f"Incorrect 2FA code for Employee ID: {employee_id}.")
    return False

# function to check for two-authentication (For employee)
def require_employee_2fa(f):
    from functools import wraps
    from datetime import datetime, timedelta

    @wraps(f)
    def decorated_function(*args, **kwargs):
        employee_id = getattr(g, 'employee_id', None)
        current_route = request.path

        logging.debug(f"Accessing route: {current_route} | Employee ID: {employee_id}")

        if not employee_id:
            logging.debug("No employee_id present in request context. Unauthorized.")
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

        conn = get_db_connection()
        cursor = conn.cursor()

        # 1) Fetch both is_verified and timestamp
        cursor.execute("""
            SELECT is_verified, verification_timestamp
              FROM two_factor_verifications
             WHERE employee_id = %s
             ORDER BY verification_timestamp DESC
             LIMIT 1
        """, (employee_id,))
        last_verification = cursor.fetchone()
        now = datetime.utcnow()
        twofa_window = timedelta(minutes=10)   # e.g. 10‑minute validity

        # 2) Decide if we need a fresh 2FA
        need_2fa = True
        if last_verification:
            is_verified, verified_time = last_verification
            if is_verified and (now - verified_time) <= twofa_window:
                need_2fa = False

        if need_2fa:
            logging.debug("Employee needs fresh 2FA or window expired. Not sending code automatically, just requiring 2FA.")
            # Do NOT send the 2FA code here!
            dashboard_url = '/user'  # Update this to your actual dashboard URL

            return jsonify({
                'status': 'error',
                'error': '2FA_REQUIRED',
                'redirect': f'/employee/verify-2fa?next={dashboard_url}'
            }), 403

        logging.debug("Employee 2FA still valid. Access granted.")
        return f(*args, **kwargs)
    return decorated_function

# Resend 2FA code
@login_bp.route('/employee/resend-2fa-code', methods=['POST'])
@employee_jwt_required()
def resend_employee_2fa_code():
    employee_id = g.employee_id  # pulled from the decorator

    logging.debug(f"[2FA] Resending 2FA for employee_id: {employee_id}")

    # 1) Generate a fresh 2FA code
    new_code = generate_2fa_code()

    # 2) Store the code in the database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO two_factor_verifications
            (employee_id, verification_code, is_verified, verification_timestamp)
        VALUES (%s, %s, %s, %s)
    """, (employee_id, new_code, False, datetime.utcnow()))
    conn.commit()
    cursor.close()
    conn.close()

    # 3) Send the email
    send_employee_2fa_email(employee_id)

    # 4) Return success as JSON (always, for AJAX)
    return jsonify({
        "success": True,
        "message": "Verification code sent! Check your email."
    })

# ==================== Two authentication for employees ==================== (End)



# ==================== Two authentication for admins  ==================== (Start)
# route for rendering two authentication page
@login_bp.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    if request.method == 'POST':
        # Detect fetch / AJAX request
        is_ajax = (
            request.is_json or
            request.headers.get("X-Requested-With") == "XMLHttpRequest" or
            request.headers.get("Content-Type", "").startswith("application/x-www-form-urlencoded")
        )

        # Get token from Authorization header or form field
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ")[1].strip()
        elif 'token' in request.form:
            token = request.form['token']

        if not token:
            logging.debug("No token for 2FA verification. Redirecting to login.")
            if is_ajax:
                return jsonify({"status": "error", "message": "Missing token."}), 401
            return redirect('/admin_login')

        admin_id, role, error = get_admin_from_token(token)
        if not admin_id:
            logging.debug("Invalid admin token.")
            if is_ajax:
                return jsonify({"status": "error", "message": "Invalid or expired token."}), 401
            return redirect('/admin_login')

        code = request.form['code']
        logging.debug(f"Admin ID: {admin_id} submitted 2FA code: {code}")

        if verify_2fa_code(admin_id, role, code):
            logging.info(f"Admin ID: {admin_id} successfully verified 2FA.")

            if is_ajax:
                return jsonify({
                    "status": "success",
                    "message": "Verification successful! Redirecting...",
                    "redirect": request.args.get("next", "/dashboard"),
                    "token": token
                })

            response = redirect(request.args.get('next', '/dashboard'))
            response.set_cookie('authenticated', 'true', max_age=3600)
            return response
        else:
            logging.warning(f"Admin ID: {admin_id} entered an invalid 2FA code.")
            if is_ajax:
                return jsonify({
                    "status": "error",
                    "message": "Invalid 2FA code. Please try again."
                }), 400

            flash("Invalid 2FA code. Please try again.", "danger")
            return redirect('/verify-2fa')

    # GET: show the 2FA form page
    return render_template('Admin/TwoFactorAuthentication.html')

# Verify the 2FA code (For admin)
def verify_2fa_code(admin_id, role, input_code):
    logging.debug(f"Verifying 2FA for Admin ID: {admin_id} | Input Code: {input_code}")
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check failed attempts in the last 5 minutes
    cursor.execute("""
        SELECT COUNT(*) FROM two_factor_verifications 
        WHERE admin_id = %s AND is_verified = FALSE 
        AND verification_timestamp >= NOW() - INTERVAL '5 minutes'
    """, (admin_id,))
    failed_attempts = cursor.fetchone()[0]

    if failed_attempts >= 5:
        logging.warning(f"Too many failed 2FA attempts for Admin ID: {admin_id}")
        return False  

    # Get the latest unverified code
    cursor.execute("""
        SELECT verification_code FROM two_factor_verifications 
        WHERE admin_id = %s AND is_verified = FALSE
        ORDER BY verification_timestamp DESC 
        LIMIT 1
    """, (admin_id,))
    
    row = cursor.fetchone()
    if not row:
        logging.warning(f"No valid unverified 2FA code found for Admin ID: {admin_id}")
        return False  

    stored_code = row[0]
    if input_code == stored_code:
        logging.debug(f"Correct 2FA code entered for Admin ID: {admin_id}. Marking as verified.")
        cursor.execute("""
            UPDATE two_factor_verifications 
            SET is_verified = TRUE 
            WHERE admin_id = %s AND verification_code = %s
        """, (admin_id, stored_code))
        conn.commit()
        return True
    
    logging.warning(f"Incorrect 2FA code entered for Admin ID: {admin_id}.")
    return False  

# for generating a new 2FA code for resending 2FA code
def generate_and_send_2fa_code(admin_id, role):
    """
    Generate a new 2FA code, store it for this admin, and send it via email.
    """
    import os
    from flask_mail import Message
    from app import mail

    # Connect to DB
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get admin email
        cursor.execute("SELECT email FROM admins WHERE admin_id = %s", (admin_id,))
        row = cursor.fetchone()
        if not row:
            logging.error(f"❌ No email found for admin ID: {admin_id}")
            return False

        email = row[0]
        code = generate_2fa_code()  # You already have this function

        # Store 2FA attempt in database
        timestamp = datetime.utcnow()
        cursor.execute("""
            INSERT INTO two_factor_verifications (admin_id, verification_code, is_verified, verification_timestamp)
            VALUES (%s, %s, FALSE, %s)
        """, (admin_id, code, timestamp))
        conn.commit()

        sender_email = os.getenv("EMAIL_USER")
        if not sender_email:
            logging.error("❌ EMAIL_USER not set in .env")
            return False

        msg = Message(
            subject="Your 2FA Verification Code",
            sender=sender_email,
            recipients=[email]
        )
        msg.body = f"Your 2FA verification code is: {code}. This code expires in 60 seconds."

        mail.send(msg)
        logging.info(f"✅ 2FA email resent successfully to {email}")
        return True
    except Exception as e:
        logging.error(f"❌ Error in generate_and_send_2fa_code: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

# Send verification code via email (For admin)
load_dotenv()
def send_2fa_email():
    from app import mail
    """Sends a 2FA verification email to the admin."""
    admin_id, role, error = get_admin_from_token()
    if not admin_id:
        logging.error("❌ No admin ID found in token")
        return False  

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch admin email
        cursor.execute("SELECT email FROM admins WHERE admin_id = %s", (admin_id,))
        user = cursor.fetchone()

        if not user:
            logging.error(f"❌ No email found for admin ID: {admin_id}")
            return False  

        email = user[0]  # Extract email
        code = generate_2fa_code()  # Generate 2FA code

        # Store 2FA attempt in database
        timestamp = datetime.utcnow()
        cursor.execute("""
            INSERT INTO two_factor_verifications (admin_id, verification_code, is_verified, verification_timestamp)
            VALUES (%s, %s, FALSE, %s)
        """, (admin_id, code, timestamp))
        conn.commit()

        # **Fix Email Sender Issue**
        sender_email = os.getenv("EMAIL_USER")
        if not sender_email:
            logging.error("❌ EMAIL_USER is not set in the .env file")
            return False  

        # Prepare email message
        msg = Message(
            subject="Your 2FA Verification Code",
            sender=sender_email,  # Use the sender email from .env
            recipients=[email]
        )
        msg.body = f"Your 2FA verification code is: {code}. This code expires in 60 seconds."

        # Send email
        try:
            mail.send(msg)
            logging.info(f"✅ 2FA email sent successfully to {email}")
            return True
        except Exception as e:
            logging.error(f"❌ Failed to send email to {email}: {e}")
            return False
    except Exception as db_error:
        logging.error(f"❌ Database error: {db_error}")
        return False
    finally:
        cursor.close()
        conn.close()

# Resend 2FA code
@login_bp.route('/resend-2fa-code', methods=['POST'])
def resend_2fa_code():
    # Accept token from either Authorization header or POST form body
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split("Bearer ")[1].strip()
    elif 'token' in request.form:
        token = request.form['token']

    if not token:
        logging.debug("Missing or invalid Authorization header and no token in form.")
        flash("Session expired or invalid. Please log in again.", "danger")
        return redirect('/admin_login')

    # Now try to decode the token
    admin_id, role, error = get_admin_from_token(token)
    if not admin_id:
        logging.error("❌ No admin ID found in token")
        flash("Session expired or invalid. Please log in again.", "danger")
        return redirect('/admin_login')

    logging.debug(f"Admin ID: {admin_id} requested a new 2FA code.")
    # Generate and send new 2FA code (your implementation here)
    # Example:
    new_code = generate_and_send_2fa_code(admin_id, role)
    logging.info(f"✅ New 2FA code sent to admin ID: {admin_id}")

    flash("A new 2FA code has been sent to your email.", "success")
    # Optionally return JSON for AJAX, or redirect for classic POST
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "message": "2FA code resent."})
    else:
        return redirect('/verify-2fa')
   
# Two-authentication before accessing routes or pages for admin
def require_2fa_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_id, role, error = get_admin_from_token()

        if error == "unauthorized":
            logging.debug("Unauthorized access attempt. Missing or invalid token.")
            if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": "UNAUTHORIZED", "redirect": "/admin_login"}), 401
            return redirect('/admin_login')
        elif error == "expired":
            logging.debug("Token expired.")
            if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": "EXPIRED", "redirect": "/admin_login"}), 401
            return redirect('/admin_login')

        current_route = request.path
        logging.debug(f"Accessing route: {current_route} | Admin ID: {admin_id} | Role: {role}")

        if role == 'super_admin':
            logging.debug("Super Admin bypassing 2FA.")
            return f(*args, **kwargs)

        if role == 'admin' and current_route in ADMIN_BYPASS_ROUTES:
            logging.debug("Admin accessing a bypass route. No 2FA required.")
            return f(*args, **kwargs)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check last 2FA verification status
        cursor.execute("""
             SELECT is_verified, verification_timestamp
            FROM two_factor_verifications
            WHERE admin_id = %s
            ORDER BY verification_timestamp DESC
            LIMIT 1
        """, (admin_id,))
        last_verification = cursor.fetchone()
        now = datetime.utcnow()
        twofa_window = timedelta(minutes=10) # Change 10 to 5 or 15 as desired

        if not last_verification or not last_verification[0]:
            logging.debug("Admin has not verified 2FA. Redirecting to verification page.")
            send_2fa_email()  # Ensure the 2FA code is sent immediately
            # --- AJAX/Fetch aware 2FA redirect ---
            if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": "2FA_REQUIRED", "redirect": "/verify-2fa"}), 403
            return redirect('/verify-2fa')
        else:
            is_verified, verified_time = last_verification
            if not is_verified or (now - verified_time) > twofa_window:
                send_2fa_email()
                # --- AJAX/Fetch aware 2FA redirect ---
                if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"error": "2FA_REQUIRED", "redirect": "/verify-2fa"}), 403
                return redirect('/verify-2fa')
        
        logging.debug("Admin has already verified 2FA. Granting access.")
        return f(*args, **kwargs)

    return decorated_function

# function for checking 2FA bypass , if i have routes below like "/verification" in here , it will skip that route 
# and don't check for two authentication but if the routes that are not in this function below it will check for 2FA
# Summarize : put the routes that don't need 2FA in the function below so that it doesn't require 2FA to access
ADMIN_BYPASS_ROUTES = {
    "/dashboard",
}
# ==================== Two authentication for admins  ==================== (End)




 







