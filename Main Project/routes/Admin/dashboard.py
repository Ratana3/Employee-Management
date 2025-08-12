from datetime import datetime, timedelta
import logging
import os
import bcrypt
from flask import Blueprint, Response, render_template, jsonify, request, send_file, url_for
import psycopg2
from routes.Auth.audit import log_audit, log_incident
from routes.Auth.token import get_admin_from_token, token_required_with_roles, token_required_with_roles_and_2fa
from routes.Auth.two_authentication import require_2fa_admin
from routes.Auth.utils import get_db_connection
from . import admin_bp
from extensions import csrf

# Dashboard (Start)

# Route for replying to message that user requests admin to change their password through email
@csrf.exempt
@admin_bp.route("/api/admin/reply_to_contact_request", methods=["POST"])
@token_required_with_roles(required_actions=["reply_contact_request"])
def reply_to_contact_request(admin_id, role, role_id):
    from flask_mail import Message
    from app import mail
    """
    Allows an admin or super_admin to reply to a user's contact request.
    Requires: request_id (int), message (str)
    """
    logging.debug(f"Admin {admin_id} ({role}) is attempting to reply to a contact request.")
    data = request.get_json()
    logging.debug(f"Received data for reply: {data}")

    request_id = data.get("request_id")
    message = data.get("message")
    subject = data.get("subject", "Reply from Admin")

    if not request_id or not message:
        logging.warning("Missing required fields in reply_to_contact_request.")
        log_incident(
            admin_id, role,
            f"Attempted to reply to contact request with missing fields: request_id={request_id}, message={message}",
            severity="Low"
        )
        return jsonify({"error": "Missing required fields."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Fetch user's email
        logging.debug(f"Fetching email for contact request ID: {request_id}")
        cur.execute("SELECT email FROM contact_requests WHERE id = %s", (request_id,))
        row = cur.fetchone()
        if not row:
            logging.warning(f"Contact request {request_id} not found.")
            log_incident(
                admin_id, role,
                f"Attempted to reply to non-existent contact request: {request_id}",
                severity="Low"
            )
            return jsonify({"error": "Contact request not found."}), 404
        user_email = row[0]
        logging.debug(f"Contact request {request_id} found, user email: {user_email}")

        # Store reply in DB, including admin_type (role)
        logging.debug(f"Inserting reply into contact_replies: admin_id={admin_id}, admin_type={role}, request_id={request_id}")
        cur.execute(
            "INSERT INTO contact_replies (contact_request_id, admin_id, admin_type, reply_message) VALUES (%s, %s, %s, %s)",
            (request_id, admin_id, role, message)
        )
        conn.commit()
        logging.info(f"Reply by admin {admin_id} ({role}) stored in DB for contact request {request_id}.")

        # Audit log: reply sent
        log_audit(
            admin_id, role,
            "reply_to_contact_request",
            f"Replied to contact request {request_id} (user email: {user_email})"
        )

        # Send reply email to user
        sender_email = os.getenv("EMAIL_USER")
        if not sender_email:
            logging.error("EMAIL_USER is not set in environment variables!")
        logging.debug(f"Sending reply email from {sender_email} to {user_email}")

        msg = Message(
            subject=subject,
            sender=sender_email,
            recipients=[user_email],
            body=message
        )
        try:
            mail.send(msg)
            logging.info(f"Reply email sent to {user_email} for contact request {request_id}")
        except Exception as mail_error:
            logging.error(f"Failed to send reply email: {mail_error}")
            log_incident(
                admin_id, role,
                f"Failed to send reply email for contact request {request_id}: {mail_error}",
                severity="Medium"
            )

        # Optionally, update contact_requests.status to 'replied'
        logging.debug(f"Updating contact_requests status to 'replied' for ID {request_id}")
        cur.execute("UPDATE contact_requests SET status = 'replied' WHERE id = %s", (request_id,))
        conn.commit()

        return jsonify({"success": True, "message": "Reply sent!"})
    except Exception as e:
        logging.exception(f"Exception in reply_to_contact_request: {e}")
        log_incident(
            admin_id, role,
            f"Exception in reply_to_contact_request for {request_id}: {e}",
            severity="High"
        )
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
        logging.debug("Database connection closed for reply_to_contact_request.")

# Route to Fetch Contact Requests
@csrf.exempt
@admin_bp.route("/api/admin/contact_requests", methods=["GET"])
@token_required_with_roles(required_actions=["get_contact_requests"])
def get_contact_requests(admin_id, role, role_id):
    """
    Returns all user contact requests
    """
    logging.debug(f"Admin {admin_id} ({role}) is fetching all contact requests.")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        logging.debug("Executing SELECT query for contact_requests.")
        cur.execute("""
            SELECT id, first_name, last_name, email, message, status, created_at
            FROM contact_requests
            ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
        logging.debug(f"Fetched {len(rows)} contact requests from the database.")
        requests = [
            {
                "id": row[0],
                "first_name": row[1],
                "last_name": row[2],
                "email": row[3],
                "message": row[4],
                "status": row[5],
                "created_at": row[6].isoformat() if row[6] else None
            }
            for row in rows
        ]
        log_audit(
            admin_id, role,
            "get_contact_requests",
            f"Fetched {len(rows)} contact requests"
        )
        return jsonify({"requests": requests})
    except Exception as e:
        logging.exception(f"Database query failed in get_contact_requests: {e}")
        log_incident(
            admin_id, role,
            f"Database query failed in get_contact_requests: {e}",
            severity="High"
        )
        return jsonify({'error': 'Database query failed'}), 500
    finally:
        cur.close()
        conn.close()
        logging.debug("Database connection closed for get_contact_requests.")

@csrf.exempt
@admin_bp.route("/api/admin/contact_requests/<int:request_id>", methods=["DELETE"])
@token_required_with_roles(required_actions=["delete_contact_request"])
def delete_contact_request(admin_id, role, role_id, request_id):
    """
    Deletes a user contact request by ID
    """
    logging.debug(f"Admin {admin_id} ({role}) is attempting to delete contact request {request_id}.")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Check if the request exists
        cur.execute("SELECT COUNT(*) FROM contact_requests WHERE id = %s", (request_id,))
        count = cur.fetchone()[0]
        if count == 0:
            logging.warning(f"Contact request {request_id} does not exist.")
            # Optionally, do NOT log this as an incident, just return 404
            return jsonify({'error': 'Contact request not found'}), 404

        # Delete the request
        cur.execute("DELETE FROM contact_requests WHERE id = %s", (request_id,))
        conn.commit()
        logging.info(f"Contact request {request_id} deleted by Admin {admin_id}.")

        log_audit(
            admin_id, role,
            "delete_contact_request",
            f"Deleted contact request {request_id}"
        )
        return jsonify({'message': 'Contact request deleted successfully.'}), 200
    except Exception as e:
        logging.exception(f"Failed to delete contact request {request_id}: {e}")
        log_incident(
            admin_id, role,
            f"Failed to delete contact request {request_id}: {e}",
            severity="High"
        )
        return jsonify({'error': 'Failed to delete contact request.'}), 500
    finally:
        cur.close()
        conn.close()
        logging.debug(f"Database connection closed for delete_contact_request {request_id}.")
        
#route to fetch the roles
@admin_bp.route("/roles", methods=["GET"])
def get_roles():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT role_id, role_name FROM roles")
        rows = cur.fetchall()
        roles = [{"role_id": row[0], "role_name": row[1]} for row in rows]
        # No admin_id/role available here, so cannot log audit for a specific user.
        # If you want to require admin for this route, add token_required_with_roles.
        return jsonify(roles)
    except Exception as e:
        # If you want to log incidents here, you must have admin_id/role from a decorator.
        pass
    finally:
        cur.close()
        conn.close()

# Route for fetching users who have a specific role, avoiding duplicate emails
@admin_bp.route("/users/by_role/<int:role_id_url>", methods=["GET"])
@token_required_with_roles(required_actions=["get_users_by_role"])
def get_users_by_role(admin_id, role, role_id, role_id_url):
    """
    Returns all users (admins, super admins, employees) that have the given role_id_url,
    but does not display the same email twice.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT admin_id AS user_id , email, 'Admin' AS role_type
            FROM admins WHERE role_id = %s
            UNION
            SELECT super_admin_id AS user_id, email, 'Super Admin' AS role_type
            FROM super_admins WHERE role_id = %s
            UNION
            SELECT employee_id AS user_id, email, 'Employee' AS role_type
            FROM employees WHERE role_id = %s
        """, (role_id_url, role_id_url, role_id_url))
        
        rows = cur.fetchall()
        users = []
        seen_emails = set()
        for row in rows:
            email = row[1]
            if email not in seen_emails:
                users.append({
                    "user_id": row[0],
                    "email": email,
                    "role_type": row[2]
                })
                seen_emails.add(email)
        # Audit log for viewing users by role
        log_audit(admin_id, role, "view_users_by_role", f"Fetched users with role_id {role_id_url}")
        if not users:
            log_incident(admin_id, role, f"No users found with role_id {role_id_url}", severity="Low")
        return jsonify(users)
    except Exception as e:
        log_incident(admin_id, role, f"Error fetching users by role: {str(e)}", severity="Medium")
        return jsonify({'error': 'Database query failed'}), 500
    finally:
        cur.close()
        conn.close()

def fetch_user_by_email(email):
    """Return list of (user_id, role) for the given email from all tables, including super_admins."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT admin_id, 'admin' FROM admins WHERE email = %s", (email,))
        admin_rows = cur.fetchall()
        cur.execute("SELECT employee_id, 'employee' FROM employees WHERE email = %s", (email,))
        emp_rows = cur.fetchall()
        cur.execute("SELECT super_admin_id, 'super_admin' FROM super_admins WHERE email = %s", (email,))
        super_rows = cur.fetchall()
        return admin_rows + emp_rows + super_rows
    finally:
        cur.close()
        conn.close()

def fetch_user_email_by_id_role(user_id, role):
    """Return email for the given user_id and role (supports admin, employee, super_admin)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if role == "admin":
            cur.execute("SELECT email FROM admins WHERE admin_id = %s", (user_id,))
        elif role == "employee":
            cur.execute("SELECT email FROM employees WHERE employee_id = %s", (user_id,))
        elif role == "super_admin":
            cur.execute("SELECT email FROM super_admins WHERE super_admin_id = %s", (user_id,))
        else:
            return None
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()
        conn.close()

# ========== UNREAD COUNT ==========

@admin_bp.route('/messages/unread-count', methods=["GET"])
@token_required_with_roles(required_actions=["get_unread_messages"])
def get_unread_messages(admin_id, role, role_id):
    logging.debug(f"[DASHBOARD DEBUG] {request.method} {request.path} | function: get_unread_messages")
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logging.debug("Missing or invalid Authorization header.")
        log_incident(admin_id, role, "Missing or invalid Authorization header on unread-count", severity="Low")
        return jsonify({"error": "Missing or invalid Authorization header"}), 401
    token = auth_header.split("Bearer ")[1].strip()

    try:
        user_id, user_role, error = get_admin_from_token(token)
        if error == "expired":
            log_incident(admin_id, role, "Token expired on unread-count", severity="Medium")
            return jsonify({'error': 'Token expired'}), 401
        elif error:
            log_incident(admin_id, role, "Unauthorized token on unread-count", severity="Medium")
            return jsonify({'error': 'Unauthorized'}), 401
        # get email for current user
        email = fetch_user_email_by_id_role(user_id, user_role)
    except Exception as e:
        logging.debug(f"Token decoding failed: {str(e)}")
        log_incident(admin_id, role, f"Token decoding failed: {str(e)}", severity="Medium")
        return jsonify({"error": "Invalid or expired token", "details": str(e)}), 401

    # find all user_ids/roles that match this email (admin, employee, super_admin)
    id_roles = fetch_user_by_email(email)
    if not id_roles:
        return jsonify({'unread_count': 0, 'messages': [], 'requests': []})

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Fetch unread messages for all roles
        messages = []
        for uid, urole in id_roles:
            cur.execute("""
                SELECT message_id, sender_id, sender_role, body, timestamp
                FROM messages
                WHERE receiver_id = %s AND is_read = FALSE
                ORDER BY timestamp DESC
                LIMIT 5
            """, (uid, ))
            rows = cur.fetchall()
            messages.extend([
                {
                    'type': 'message',
                    'message_id': row[0],
                    'sender_id': row[1],
                    'sender_role': row[2],
                    'content': row[3],
                    'timestamp': row[4].isoformat()
                }
                for row in rows
            ])
        # Contact requests (pending only)
        cur.execute("""
            SELECT id, first_name, last_name, email, message, created_at
            FROM contact_requests
            WHERE status = 'pending'
            ORDER BY created_at DESC
            LIMIT 5
        """)
        req_rows = cur.fetchall()
        requests = [
            {
                'type': 'contact_request',
                'request_id': req_row[0],
                'first_name': req_row[1],
                'last_name': req_row[2],
                'email': req_row[3],
                'content': req_row[4],
                'timestamp': req_row[5].isoformat()
            }
            for req_row in req_rows
        ]
        total = len(messages) + len(requests)
        log_audit(admin_id, role, "get_unread_messages", f"Fetched unread messages and contact requests for {user_id} (all roles)")
    except Exception as e:
        logging.error(f"Failed to fetch unread messages/contact requests: {e}")
        log_incident(admin_id, role, f"Failed to fetch unread messages: {str(e)}", severity="Medium")
        return jsonify({'error': 'Database query failed'}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({
        'unread_count': total,
        'messages': messages,
        'requests': requests
    })

# ========== MARK AS READ ==========

@admin_bp.route('/messages/read/<int:message_id>', methods=['POST'])
@token_required_with_roles(required_actions=["mark_message_as_read"])
def mark_message_as_read(admin_id, role, role_id, message_id):
    logging.debug(f"[DASHBOARD DEBUG] {request.method} {request.path} | function: mark_message_as_read")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Mark as read regardless of receiver_role, as long as message_id matches
        cur.execute("UPDATE messages SET is_read = TRUE WHERE message_id = %s", (message_id,))
        conn.commit()
        log_audit(admin_id, role, "mark_message_as_read", f"Marked message {message_id} as read")
        return jsonify({"message": "Marked as read"})
    except Exception as e:
        log_incident(admin_id, role, f"Failed to mark message {message_id} as read: {str(e)}", severity="Medium")
        return jsonify({'error': 'Database query failed'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

# ========== INBOX ==========

@admin_bp.route("/messages/inbox", methods=["GET"])
@token_required_with_roles(required_actions=["get_message_inbox"])
def get_message_inbox(admin_id, role, role_id):
    logging.debug(f"[DASHBOARD DEBUG] {request.method} {request.path} | function: get_message_inbox")
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logging.debug("Missing or invalid Authorization header.")
        log_incident(admin_id, role, "Missing or invalid Authorization header on inbox", severity="Low")
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split("Bearer ")[1].strip()
    try:
        user_id, user_role, error = get_admin_from_token(token)
        email = fetch_user_email_by_id_role(user_id, user_role)
    except Exception as e:
        logging.debug(f"Token decoding failed: {str(e)}")
        log_incident(admin_id, role, f"Token decoding failed: {str(e)}", severity="Medium")
        return jsonify({"error": "Invalid or expired token", "details": str(e)}), 401

    id_roles = fetch_user_by_email(email)
    if not id_roles:
        return jsonify([])

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        messages = []
        for uid, urole in id_roles:
            cur.execute("""
                SELECT message_id, sender_id, sender_role, body, timestamp, is_read
                FROM messages
                WHERE receiver_id = %s 
                ORDER BY timestamp DESC
            """, (uid,))
            rows = cur.fetchall()
            messages += [
                {
                    "message_id": row[0],
                    "sender_id": row[1],
                    "sender_role": row[2],
                    "content": row[3],
                    "timestamp": row[4],
                    "is_read": row[5]
                } for row in rows
            ]
        log_audit(admin_id, role, "get_message_inbox", f"Fetched inbox for user {admin_id} (all roles)")
        return jsonify(messages)
    except Exception as e:
        log_incident(admin_id, role, f"Failed to fetch inbox: {str(e)}", severity="Medium")
        return jsonify({'error': 'Database query failed'}), 500
    finally:
        cur.close()
        conn.close()
        logging.debug("Database connection closed.")

# ========== SEND MESSAGE ==========

@csrf.exempt
@admin_bp.route('/messages/send', methods=['POST'])
@token_required_with_roles(required_actions=["send_message"])
def send_message(admin_id, role, role_id):
    logging.debug(f"[DASHBOARD DEBUG] {request.method} {request.path} | function: send_message")
    data = request.get_json()
    print("Received message send request with data:", data)  # Debug

    recipient_email = data['receiver_email']  # Ensure the sender supplies receiver_email in payload!
    recipients = fetch_user_by_email(recipient_email)
    if not recipients:
        return jsonify({"error": "No user found for that email"}), 404

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        for recv_id, recv_role in recipients:
            query = """
                INSERT INTO messages (sender_id, sender_role, receiver_id, receiver_role, subject, body)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            values = (
                data['sender_id'], data['sender_role'],
                recv_id, recv_role,
                data.get('subject'), data['body']
            )
            cur.execute(query, values)
        conn.commit()
        # AUDIT: log successful message send
        log_audit(
            admin_id,
            role,
            "send_message",
            f"Sent message to {recipient_email} (roles: {','.join([r[1] for r in recipients])})"
        )
        print("Message inserted successfully.")
        return jsonify({"message": "Message sent successfully"}), 201
    except Exception as e:
        conn.rollback()
        log_incident(
            admin_id=admin_id,
            role=role,
            description=f"Failed to send message: {str(e)}",
            severity="Medium"
        )
        print("Error occurred while sending message:", str(e))  # Debug the error
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
        print("Database connection closed.")

# Route for deleting a message
@admin_bp.route('/messages/delete/<int:message_id>', methods=['DELETE'])
@token_required_with_roles(required_actions=["delete_message"])
def delete_message(admin_id, role, role_id, message_id):
    logging.debug(f"[DASHBOARD DEBUG] {request.method} {request.path} | function: delete_message")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Optionally: check ownership (receiver_id/admin_id), skip if not required
        cur.execute(
            "DELETE FROM messages WHERE message_id = %s", (message_id,)
        )
        if cur.rowcount == 0:
            log_incident(
                admin_id, role,
                f"Attempted to delete non-existent or unauthorized message {message_id}",
                severity="Low"
            )
            return jsonify({"error": "Message not found or not authorized to delete"}), 404
        conn.commit()
        log_audit(
            admin_id, role, "delete_message",
            f"Deleted message {message_id}"
        )
        return jsonify({"message": "Message deleted successfully."}), 200
    except Exception as e:
        conn.rollback()
        log_incident(
            admin_id, role,
            f"Failed to delete message {message_id}: {str(e)}",
            severity="Medium"
        )
        return jsonify({"error": "Failed to delete message"}), 500
    finally:
        cur.close()
        conn.close()

@admin_bp.route('/dashboard', methods=['GET'])
def dashboard_page():
    return render_template('Admin/dashboard.html')

#route for fetching dashboard datas such as for displaying in charts
@admin_bp.route('/dashboard_data', methods=['GET'])
@token_required_with_roles(required_actions=["dashboard"])
def dashboard(admin_id, role, role_id):
    logging.debug(f"[DASHBOARD DEBUG] {request.method} {request.path} | function: dashboard")
    logging.debug("\n=== ADMIN DASHBOARD REQUEST ===")
    logging.debug(f"Authenticated as {role} ID {admin_id}")

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if role == 'super_admin':
                cursor.execute("SELECT first_name, last_name, email FROM super_admins WHERE super_admin_id = %s", (admin_id,))
            else:
                cursor.execute("SELECT first_name, last_name, email FROM admins WHERE admin_id = %s", (admin_id,))

            admin_row = cursor.fetchone()
            if not admin_row:
                # INCIDENT: admin/super_admin not found in DB
                log_incident(
                    admin_id=admin_id, 
                    role=role, 
                    description=f"{role.replace('_', ' ').capitalize()} ID {admin_id} not found when accessing dashboard.", 
                    severity="Medium"
                )
                return jsonify({'error': f'{role.replace("_", " ").capitalize()} not found'}), 404

            first_name, last_name, email = admin_row
            profile_image_url = url_for('admin_bp.admin_profile_picture', route_admin_id=admin_id, route_role=role)

            cursor.execute("SELECT COUNT(*) FROM employees;")
            total_employees = cursor.fetchone()[0]

            today = datetime.now().date()
            cursor.execute("""
                SELECT COUNT(DISTINCT employee_id)
                FROM attendance_logs
                WHERE date = %s AND clock_in_time IS NOT NULL;
            """, (today,))
            clockin_users = cursor.fetchone()[0]

            cursor.execute("""
                SELECT date, COUNT(DISTINCT employee_id)
                FROM attendance_logs
                WHERE date >= %s
                GROUP BY date
                ORDER BY date ASC;
            """, (today - timedelta(days=6),))
            trend_rows = cursor.fetchall()
            attendance_data = {
                "dates": [row[0].strftime('%Y-%m-%d') for row in trend_rows],
                "counts": [row[1] for row in trend_rows]
            }

            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN department IS NULL OR TRIM(department) = '' OR LOWER(TRIM(department)) = 'none'
                        THEN 'Unassigned'
                        ELSE TRIM(department)
                    END AS department,
                    COUNT(*)
                FROM employees
                GROUP BY department;
            """)
            dept_rows = cursor.fetchall()
            department_data = {
                "labels": [row[0] for row in dept_rows],
                "counts": [row[1] for row in dept_rows]
            }

        response_data = {
            "total_employees": total_employees,
            "clockin_users": clockin_users,
            "attendance_data": attendance_data,
            "department_data": department_data,
            "admin_id": admin_id,
            "admin_role": role,
            "admin_profile": {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "profile_image": profile_image_url
            }
        }

        # AUDIT: successful dashboard data fetch
        log_audit(admin_id, role, "view_dashboard", "Viewed dashboard data")

        return jsonify(response_data)
    
    except Exception as e:
        # Optional: log as incident if you feel dashboard fetch errors should be tracked
        log_incident(
            admin_id=admin_id,
            role=role,
            description=f"Exception during dashboard fetch: {str(e)}",
            severity="High"
        )
        logging.error(f"Exception in /dashboard_data: {e}")
        return jsonify({'error': 'Internal server error'}), 500
    
@admin_bp.route('/check_jti', methods=['GET'])
def check_jti():
    return jsonify({'msg': 'ok'}), 200


# Dashboard (End)
