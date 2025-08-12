import logging
from flask import flash, g, jsonify, redirect, render_template, request, url_for

from routes.Auth.token import employee_jwt_required
from . import employee_bp
from routes.Auth.token import verify_employee_token
from routes.Auth.utils import get_db_connection
from extensions import csrf
from routes.Auth.audit import log_employee_audit,log_employee_incident

# === USER LOOKUP HELPERS ===

def fetch_user_by_email(email):
    """Return list of (user_id, role) for the given email from all tables including super_admins."""
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
    """Return email for the given user_id and role, with super_admin support."""
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

# ========== INBOX ==========
@employee_bp.route("/employee/messages/inbox", methods=["GET"])
@employee_jwt_required()
def get_employee_inbox():
    from flask import jsonify
    user_id = g.employee_id

    if not user_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized inbox access attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT message_id, sender_id, sender_role, body, timestamp, is_read
            FROM messages
            WHERE receiver_id = %s 
            ORDER BY timestamp DESC
        """, (user_id, ))
        rows = cur.fetchall()
        
        messages = []
        unread_count = 0
        sender_roles = {}
        
        for row in rows:
            is_read = row[5]
            sender_role = row[2] or 'Unknown'
            
            if not is_read:
                unread_count += 1
            
            sender_roles[sender_role] = sender_roles.get(sender_role, 0) + 1
            
            messages.append({
                "message_id": row[0],
                "sender_id": row[1],
                "sender_role": sender_role,
                "content": row[3],
                "timestamp": row[4],
                "is_read": is_read
            })

        # Log successful audit trail
        role_summary = ', '.join([f"{count} from {role}" for role, count in sender_roles.items()]) if sender_roles else "none"
        log_employee_audit(
            employee_id=user_id,
            action="view_inbox",
            details=f"Retrieved {len(messages)} messages ({unread_count} unread): {role_summary}"
        )

    except Exception as e:
        logging.error(f"Failed to fetch inbox: {e}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=user_id,
            description=f"System error while fetching inbox: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Database query failed'}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify(messages)

# ========== MARK AS READ ==========
@employee_bp.route('/employee/messages/read/<int:message_id>', methods=['POST'])
@employee_jwt_required()
def employee_mark_as_read(message_id):
    from flask import jsonify
    user_id = g.employee_id

    if not user_id:
        log_employee_incident(
            employee_id=None,
            description=f"Unauthorized message mark-as-read attempt for message {message_id} - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # First get message details for logging
        cur.execute("""
            SELECT sender_id, sender_role, body, is_read
            FROM messages
            WHERE message_id = %s AND receiver_id = %s
        """, (message_id, user_id))
        
        message_info = cur.fetchone()
        
        if not message_info:
            log_employee_incident(
                employee_id=user_id,
                description=f"Employee attempted to mark non-existent or unauthorized message {message_id} as read",
                severity="Medium"
            )
            cur.close()
            conn.close()
            return jsonify({"error": "Message not found or not authorized"}), 404

        sender_id, sender_role, message_body, was_read = message_info
        
        if was_read:
            # Log audit for already read message
            log_employee_audit(
                employee_id=user_id,
                action="mark_message_read",
                details=f"Attempted to mark already-read message {message_id} from {sender_role} {sender_id} as read"
            )
            cur.close()
            conn.close()
            return jsonify({"message": "Message already marked as read"})

        cur.execute("""
            UPDATE messages SET is_read = TRUE
            WHERE message_id = %s AND receiver_id = %s 
        """, (message_id, user_id, ))
        conn.commit()
        
        if cur.rowcount == 0:
            log_employee_incident(
                employee_id=user_id,
                description=f"Unexpected error: Message {message_id} mark-as-read failed after validation checks passed",
                severity="High"
            )
            cur.close()
            conn.close()
            return jsonify({"error": "Message not found or not authorized"}), 404

        # Log successful audit trail
        content_preview = message_body[:50] + "..." if len(message_body) > 50 else message_body
        log_employee_audit(
            employee_id=user_id,
            action="mark_message_read",
            details=f"Successfully marked message {message_id} from {sender_role} {sender_id} as read: '{content_preview}'"
        )

        cur.close()
        conn.close()
        return jsonify({"message": "Marked as read"})
        
    except Exception as e:
        logging.error(f"Failed to mark message as read: {e}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=user_id,
            description=f"System error while marking message {message_id} as read: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": "Failed to mark message as read", "details": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# ========== DELETE MESSAGE ==========
@csrf.exempt
@employee_bp.route('/employee/messages/delete/<int:message_id>', methods=['DELETE'])
@employee_jwt_required()
def employee_delete_message(message_id):
    from flask import jsonify
    user_id = g.employee_id

    if not user_id:
        log_employee_incident(
            employee_id=None,
            description=f"Unauthorized message deletion attempt for message {message_id} - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # First get message details for logging before deletion
        cur.execute("""
            SELECT sender_id, sender_role, body, is_read, timestamp
            FROM messages
            WHERE message_id = %s AND receiver_id = %s
        """, (message_id, user_id))
        
        message_info = cur.fetchone()
        
        if not message_info:
            log_employee_incident(
                employee_id=user_id,
                description=f"Employee attempted to delete non-existent or unauthorized message {message_id}",
                severity="Medium"
            )
            cur.close()
            conn.close()
            return jsonify({"error": "Message not found or not authorized to delete"}), 404

        sender_id, sender_role, message_body, is_read, timestamp = message_info

        # Only allow the receiver to delete their own messages
        cur.execute("""
            DELETE FROM messages
            WHERE message_id = %s AND receiver_id = %s 
        """, (message_id, user_id,))
        
        if cur.rowcount == 0:
            log_employee_incident(
                employee_id=user_id,
                description=f"Unexpected error: Message {message_id} deletion failed after validation checks passed",
                severity="High"
            )
            cur.close()
            conn.close()
            return jsonify({"error": "Message not found or not authorized to delete"}), 404
        
        conn.commit()

        # Log successful audit trail
        content_preview = message_body[:50] + "..." if len(message_body) > 50 else message_body
        read_status = "read" if is_read else "unread"
        log_employee_audit(
            employee_id=user_id,
            action="delete_message",
            details=f"Successfully deleted {read_status} message {message_id} from {sender_role} {sender_id} (sent: {timestamp}): '{content_preview}'"
        )

        cur.close()
        conn.close()
        return jsonify({"message": "Message deleted successfully."}), 200
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Failed to delete message: {e}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=user_id,
            description=f"System error while deleting message {message_id}: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": "Failed to delete message", "details": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# ========== UNREAD COUNT ==========
@employee_bp.route('/employee/messages/unread-count', methods=["GET"])
@employee_jwt_required()
def employee_unread_count():
    from flask import jsonify
    user_id = g.employee_id

    if not user_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized unread message count access attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT message_id, sender_id, sender_role, body, timestamp
            FROM messages
            WHERE receiver_id = %s AND is_read = FALSE
            ORDER BY timestamp DESC
            LIMIT 5
        """, (user_id,))
        rows = cur.fetchall()
        
        messages = []
        sender_roles = {}
        
        for row in rows:
            sender_role = row[2] or 'Unknown'
            sender_roles[sender_role] = sender_roles.get(sender_role, 0) + 1
            
            messages.append({
                'message_id': row[0],
                'sender_id': row[1],
                'sender_role': sender_role,
                'content': row[3],
                'timestamp': row[4].isoformat() if row[4] else None
            })
        
        total = len(messages)

        # Log successful audit trail
        if total > 0:
            role_summary = ', '.join([f"{count} from {role}" for role, count in sender_roles.items()])
            log_employee_audit(
                employee_id=user_id,
                action="check_unread_count",
                details=f"Retrieved {total} unread messages (showing top 5): {role_summary}"
            )
        else:
            log_employee_audit(
                employee_id=user_id,
                action="check_unread_count",
                details="Checked unread messages: no unread messages found"
            )

    except Exception as e:
        logging.error(f"Failed to fetch unread messages: {e}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=user_id,
            description=f"System error while fetching unread message count: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Database query failed'}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({
        'unread_count': total,
        'messages': messages
    })

# ========== SEND MESSAGE ==========
@csrf.exempt
@employee_bp.route('/employee/messages/send', methods=['POST'])
@employee_jwt_required()
def employee_send_message():
    print("[DEBUG] Entered employee_send_message route")
    try:
        data = request.get_json()
        print(f"[DEBUG] Received data: {data}")

        sender_id = g.employee_id
        sender_role = g.employee_role
        print(f"[DEBUG] sender_id: {sender_id}, sender_role: {sender_role}")
        
        if not sender_id:
            print("[DEBUG] Invalid or missing sender_id")
            log_employee_incident(
                employee_id=None,
                description="Unauthorized message sending attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        if not data or not data.get('receiver_email') or not data.get('body'):
            log_employee_incident(
                employee_id=sender_id,
                description=f"Message sending attempted with missing data - receiver_email: {bool(data.get('receiver_email') if data else False)}, body: {bool(data.get('body') if data else False)}",
                severity="Low"
            )
            return jsonify({'error': 'Missing required fields: receiver_email and body'}), 400

        recipient_email = data['receiver_email']
        message_body = data['body']
        subject = data.get('subject', 'No Subject')
        
        recipients = fetch_user_by_email(recipient_email)
        print(f"[DEBUG] Recipients fetched: {recipients}")
        
        if not recipients:
            print("[DEBUG] No user found for that email")
            log_employee_incident(
                employee_id=sender_id,
                description=f"Employee attempted to send message to non-existent email: '{recipient_email}'",
                severity="Low"
            )
            return jsonify({"error": "No user found for that email"}), 404

        conn = get_db_connection()
        cur = conn.cursor()
        
        message_count = 0
        recipient_details = []
        
        for recv_id, recv_role in recipients:
            query = """
                INSERT INTO messages (sender_id, sender_role, receiver_id, receiver_role, subject, body)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING message_id
            """
            values = (
                sender_id, sender_role,
                recv_id, recv_role,
                subject, message_body
            )
            print(f"[DEBUG] Inserting message: {values}")
            cur.execute(query, values)
            message_id = cur.fetchone()[0] if cur.rowcount > 0 else None
            message_count += 1
            recipient_details.append(f"{recv_role} {recv_id}")
        
        conn.commit()
        print("[DEBUG] Message(s) committed to DB.")

        # Log successful audit trail
        body_preview = message_body[:100] + "..." if len(message_body) > 100 else message_body
        recipients_summary = ', '.join(recipient_details)
        log_employee_audit(
            employee_id=sender_id,
            action="send_message",
            details=f"Successfully sent {message_count} message(s) to {recipient_email} ({recipients_summary}) with subject '{subject}': '{body_preview}'"
        )

        cur.close()
        conn.close()
        return jsonify({"message": "Message sent successfully"}), 201
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        logging.error(f"Error sending message: {e}")
        import traceback; traceback.print_exc()
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during message sending: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

# ========== ALERTS READ ==========
@employee_bp.route('/api/alerts/read', methods=['POST'])
@employee_jwt_required()
def mark_alert_as_read():
    try:
        employee_id = g.employee_id
        
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized alert mark-as-read attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json
        alert_id = data.get('alert_id')

        if not alert_id:
            log_employee_incident(
                employee_id=employee_id,
                description="Alert mark-as-read attempted without alert_id",
                severity="Low"
            )
            return jsonify({'error': 'Missing alert_id'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # First check if alert exists and get details for logging
        cursor.execute("""
            SELECT alert_id, title, message, alert_type, read_by
            FROM alerts
            WHERE alert_id = %s
        """, (alert_id,))
        
        alert_info = cursor.fetchone()
        
        if not alert_info:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to mark non-existent alert {alert_id} as read",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Alert not found'}), 404

        alert_id_db, title, message, alert_type, read_by = alert_info
        
        # Check if already read by this employee
        if read_by and employee_id in read_by:
            log_employee_audit(
                employee_id=employee_id,
                action="mark_alert_read",
                details=f"Attempted to mark already-read alert {alert_id} as read: '{title}' ({alert_type})"
            )
            cursor.close()
            conn.close()
            return jsonify({"success": True, "message": "Alert already marked as read!"}), 200

        cursor.execute("""
            UPDATE alerts
            SET read_by = array_append(read_by, %s), status = 'read'
            WHERE alert_id = %s
        """, (employee_id, alert_id))

        if cursor.rowcount == 0:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Unexpected error: Alert {alert_id} mark-as-read failed after validation checks passed",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Failed to mark alert as read'}), 500

        conn.commit()

        # Log successful audit trail
        message_preview = message[:50] + "..." if message and len(message) > 50 else message or "No message"
        log_employee_audit(
            employee_id=employee_id,
            action="mark_alert_read",
            details=f"Successfully marked alert {alert_id} as read: '{title}' ({alert_type}) - '{message_preview}'"
        )

        cursor.close()
        conn.close()
        return jsonify({"success": True, "message": "Alert marked as read!"}), 200

    except Exception as e:
        if "conn" in locals():
            conn.rollback()
        logging.error(f"Error marking alert as read: {e}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while marking alert as read: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": str(e)}), 500

    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()