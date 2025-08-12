import os
import threading
import logging
from flask_mail import Message
from datetime import datetime
from routes.Auth.token import employee_jwt_required
from routes.Auth.token import verify_employee_token
from routes.Auth.utils import get_db_connection
from user_agents import parse
from flask import g, jsonify, render_template, request
import psycopg2
from routes.Employee import employee_bp

def get_readable_device_name(user_agent_obj):
    brand = getattr(user_agent_obj.device, "brand", None)
    model = getattr(user_agent_obj.device, "model", None)
    family = user_agent_obj.device.family
    os_family = user_agent_obj.os.family.lower()

    # For desktops (Windows, Mac, Linux), always return 'Desktop'
    if user_agent_obj.is_pc or os_family in ["windows", "mac os x", "linux"]:
        return "Desktop"

    # For mobile/tablet, try brand+model first
    if brand and model and brand.lower() != "other" and model.lower() != "other":
        return f"{brand} {model}".strip()
    elif model and model.lower() != "other":
        return model
    elif family and family.lower() not in ["other", "generic smartphone"]:
        return family
    elif user_agent_obj.is_mobile:
        return "Mobile"
    elif user_agent_obj.is_tablet:
        return "Tablet"
    return "Unknown"

def detect_device_info():
    user_agent = request.headers.get('User-Agent')
    ip_address = request.remote_addr or 'Unknown'

    if not user_agent:
        return {}

    user_agent_obj = parse(user_agent)
    device_name = get_readable_device_name(user_agent_obj)

    device_os = user_agent_obj.os.family + " " + user_agent_obj.os.version_string
    browser_name = user_agent_obj.browser.family
    browser_version = user_agent_obj.browser.version_string

    logging.info(f"User-Agent: {user_agent}")
    logging.info(f"Parsed device: {device_name}, os: {user_agent_obj.os.family}, browser: {user_agent_obj.browser.family}")

    return {
        'device_name': device_name,
        'device_os': device_os,
        'browser_name': browser_name,
        'browser_version': browser_version,
        'ip_address': ip_address,
        'raw_user_agent': user_agent
    }

def save_or_update_device(mail, employee_id=None, admin_id=None):
    device_info = detect_device_info()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if employee_id:
            cursor.execute("""
                SELECT device_id FROM devices 
                WHERE employee_id = %s AND device_name = %s AND device_os = %s AND browser_name = %s AND ip_address = %s
            """, (employee_id, device_info['device_name'], device_info['device_os'], device_info['browser_name'], device_info['ip_address']))
        else:
            cursor.execute("""
                SELECT device_id FROM devices 
                WHERE admin_id = %s AND device_name = %s AND device_os = %s AND browser_name = %s AND ip_address = %s
            """, (admin_id, device_info['device_name'], device_info['device_os'], device_info['browser_name'], device_info['ip_address']))

        existing_device = cursor.fetchone()

        if existing_device:
            # Update last seen time
            cursor.execute("""
                UPDATE devices 
                SET last_seen = NOW(), is_current = TRUE 
                WHERE device_id = %s
            """, (existing_device[0],))
        else:
            # New device detected! Insert it
            cursor.execute("""
                INSERT INTO devices (employee_id, admin_id, device_name, device_os, browser_name, browser_version, ip_address, is_current, last_seen)
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, NOW())
            """, (
                employee_id,
                admin_id,
                device_info.get('device_name', 'Unknown'),
                device_info.get('device_os', 'Unknown'),
                device_info.get('browser_name', 'Unknown'),
                device_info.get('browser_version', 'Unknown'),
                device_info.get('ip_address', 'Unknown')
            ))

            # 🎯 Send New Device Email (in background thread)
            threading.Thread(
                target=send_new_device_alert_email,
                kwargs={
                    "mail": mail,
                    "employee_id": employee_id,
                    "admin_id": admin_id,
                    "device_info": device_info
                }
            ).start()


        conn.commit()
    except Exception as e:
        logging.error(f"❌ Error in save_device: {e}", exc_info=True)
    finally:
        cursor.close()
        conn.close()

def send_new_device_alert_email(mail, employee_id=None, admin_id=None, device_info=None):
    sender_email = os.getenv("EMAIL_USER")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if employee_id:
            cursor.execute("SELECT email FROM employees WHERE employee_id = %s", (employee_id,))
        else:
            cursor.execute("SELECT email FROM admins WHERE admin_id = %s", (admin_id,))

        row = cursor.fetchone()

        if not row:
            logging.error("❌ Email not found for user trying to receive device alert")
            return

        user_email = row[0]

        # Create the email
        msg = Message(
            subject="⚠️ New Device Login Detected",
            sender=sender_email,
            recipients=[user_email]
        )

        msg.body = f"""\
Hello,

A new device has just logged into your account:

Device: {device_info.get('device_name')}  
Operating System: {device_info.get('device_os')}  
Browser: {device_info.get('browser_name')} {device_info.get('browser_version')}  
IP Address: {device_info.get('ip_address')}  
Time: {datetime.utcnow()} UTC

If this was you, you can safely ignore this email.
If you did NOT log in, please secure your account immediately.

Stay safe,
Your Security Team
"""

        mail.send(msg)
        logging.info(f"✅ New device alert email sent to {user_email}")

    except Exception as e:
        logging.error(f"❌ Failed to send device alert email: {e}", exc_info=True)
    finally:
        cursor.close()
        conn.close()

def log_device_session(request, employee_id=None, admin_id=None, jti=None, issued_at=None):
    user_agent_obj = parse(request.headers.get('User-Agent', ''))
    ip_address = request.remote_addr or request.environ.get('HTTP_X_FORWARDED_FOR')

    device_name = get_readable_device_name(user_agent_obj)  # << Use helper!

    device_data = {
        'employee_id': employee_id,
        'admin_id': admin_id,
        'device_name': device_name,
        'device_os': user_agent_obj.os.family,
        'browser_name': user_agent_obj.browser.family,
        'browser_version': user_agent_obj.browser.version_string,
        'ip_address': ip_address,
        'is_current': True,
        'last_seen': datetime.utcnow(),
        'jti': jti,
        'issued_at': issued_at
    }

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO devices (employee_id, admin_id, device_name, device_os, browser_name, browser_version, ip_address, is_current, last_seen, jti, issued_at)
        VALUES (%(employee_id)s, %(admin_id)s, %(device_name)s, %(device_os)s, %(browser_name)s, %(browser_version)s, %(ip_address)s, %(is_current)s, %(last_seen)s, %(jti)s, %(issued_at)s)
    """, device_data)
    conn.commit()
    cursor.close()
    conn.close()
    
@employee_bp.route('/employee/devices')
def employee_devices():
    employee_id,role = verify_employee_token()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT device_name, device_os, browser_name, browser_version, ip_address, last_seen, is_current
        FROM devices
        WHERE employee_id = %s
        ORDER BY last_seen DESC
    """, (employee_id,))
    devices = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('Employee/ManageDevices.html', devices=devices)

@employee_bp.route('/recent-devices', methods=['GET'])
@employee_jwt_required()
def recent_devices():
    employee_id = g.employee_id  # Now pulled from JWT
    if not employee_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT device_name, device_os, browser_name, ip_address, issued_at
            FROM devices
            WHERE employee_id = %s
            ORDER BY issued_at DESC
            LIMIT 10
        """, (employee_id,))
        devices = cursor.fetchall()

        device_list = [{
            'device_name': d[0],
            'device_os': d[1],
            'browser_name': d[2],
            'ip_address': d[3],
            'issued_at': d[4].strftime('%Y-%m-%d %H:%M:%S') if d[4] else None
        } for d in devices]
        
        return jsonify({'success': True, 'devices': device_list})
    
    except Exception as e:
        logging.error(f"❌ Error fetching devices: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Error fetching devices'}), 500
    finally:
        cursor.close()
        conn.close()
