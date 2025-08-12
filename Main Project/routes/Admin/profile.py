from datetime import datetime, timedelta
import logging
import os
import bcrypt
from flask import Blueprint, Response, render_template, jsonify, request, send_file, url_for
import psycopg2
from routes.Auth.audit import log_audit, log_incident
from routes.Auth.token import token_required_with_roles
from routes.Auth.utils import get_db_connection
from . import admin_bp
from extensions import csrf
from PIL import Image
import io

@admin_bp.route('/profile_details', methods=['GET'])
def profile_details():
    return render_template('Admin/Profile_Page.html')

#route for fetching profile details for logged in admin
@admin_bp.route('/api/profile_details', methods=['GET'])
@token_required_with_roles(required_actions=["get_profile_details"])
def get_profile_details(admin_id, role, role_id):
    logging.debug(f"[DASHBOARD DEBUG] {request.method} {request.path} | Entered get_profile_details with admin_id={admin_id}, role={role}, role_id={role_id}")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if role == 'super_admin':
                logging.debug(f"[DASHBOARD DEBUG] Querying super_admins for admin_id={admin_id}")
                cur.execute(
                    "SELECT first_name, last_name, email, phone_number,date_of_birth FROM super_admins WHERE super_admin_id = %s",
                    (admin_id,)
                )
                row = cur.fetchone()
                if not row:
                    logging.warning(f"[DASHBOARD DEBUG] Super admin not found: admin_id={admin_id}")
                    return jsonify({"error": "Super admin not found"}), 404

                first_name, last_name, email, phone,date_of_birth = row
                name = f"{first_name} {last_name}"
                logging.debug(f"[DASHBOARD DEBUG] Fetched super_admin: {row}")

            else:
                logging.debug(f"[DASHBOARD DEBUG] Querying admins for admin_id={admin_id}")
                cur.execute(
                    "SELECT first_name, last_name, email, phone_number,date_of_birth FROM admins WHERE admin_id = %s",
                    (admin_id,)
                )
                row = cur.fetchone()
                if not row:
                    logging.warning(f"[DASHBOARD DEBUG] Admin not found: admin_id={admin_id}")
                    return jsonify({"error": "Admin not found"}), 404

                first_name, last_name, email, phone,date_of_birth = row
                name = f"{first_name} {last_name}"
                logging.debug(f"[DASHBOARD DEBUG] Fetched admin: {row}")

        profile_picture_url = url_for('admin_bp.admin_profile_picture', route_admin_id=admin_id, route_role=role)
        logging.debug(f"[DASHBOARD DEBUG] profile_picture_url={profile_picture_url}")

        result = {
            "name": name,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "role": role.replace('_', ' ').capitalize(),
            "profile_picture": profile_picture_url,
            "date_of_birth": date_of_birth
        }
        logging.debug(f"[DASHBOARD DEBUG] Returning profile details: {result}")
        # Audit: log profile detail fetch
        log_audit(admin_id, role, "get_profile_details", f"Fetched profile details for {role} ID {admin_id}")
        return jsonify(result), 200
    except Exception as e:
        logging.exception(f"[DASHBOARD DEBUG] Exception in get_profile_details: {e}")
        log_incident(admin_id, role, f"Error fetching profile details: {e}", severity="High")
        return jsonify({"error": "Internal server error"}), 500
    
#route for updating profile details for logged in admin
@csrf.exempt
@admin_bp.route('/api/profile_details', methods=['POST'])
@token_required_with_roles(required_actions=["update_profile_details"])
def update_profile_details(admin_id, role, role_id):
    logging.debug(f"[DASHBOARD DEBUG] {request.method} {request.path} | function: update_profile_details")
    logging.debug(f"Received request to update profile for admin_id: {admin_id}, role: {role}")

    conn = get_db_connection()
    cur = conn.cursor()

    content_type = request.content_type
    logging.debug(f"Content-Type received: {content_type}")

    # Parse form or JSON
    if content_type and 'application/json' in content_type:
        data = request.get_json()
        file = None
    else:
        data = request.form
        file = request.files.get('profile_picture')

    # Parse incoming fields
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    profile_image_data = file.read() if file else None

    # --- Image compression and resizing ---
    compressed_image_bytes = None
    if profile_image_data:
        try:
            img = Image.open(io.BytesIO(profile_image_data))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((300, 300))
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=80)
            compressed_image_bytes = buffer.getvalue()
            buffer.close()
        except Exception as e:
            logging.exception("Failed to process uploaded profile image")
            return jsonify({"error": "Invalid image file"}), 400

    if role == 'super_admin':
        cur.execute(
            "SELECT first_name, last_name, email, phone_number, profile_image FROM super_admins WHERE super_admin_id = %s",
            (admin_id,)
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Super admin not found"}), 404
        current_first_name, current_last_name, current_email, current_phone, current_profile_image = row
    else:
        cur.execute(
            "SELECT first_name, last_name, email, phone_number, profile_image FROM admins WHERE admin_id = %s",
            (admin_id,)
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Admin not found"}), 404
        current_first_name, current_last_name, current_email, current_phone, current_profile_image = row

    # Use new value if provided; else use current
    first_name = data.get('first_name') or current_first_name
    last_name = data.get('last_name') or current_last_name
    email = data.get('email') or current_email
    phone = data.get('phone') or current_phone

    # Use compressed image if available, else current image
    image_to_save = psycopg2.Binary(compressed_image_bytes) if compressed_image_bytes else current_profile_image

    # --- Password update ---
    if current_password and new_password:
        logging.debug("Attempting password update")
        if role == 'super_admin':
            cur.execute("SELECT password_hash FROM super_admins WHERE super_admin_id = %s", (admin_id,))
        else:
            cur.execute("SELECT password FROM admins WHERE admin_id = %s", (admin_id,))
        result = cur.fetchone()
        if result and result[0]:
            stored_hash = result[0].encode('utf-8')
            try:
                if bcrypt.checkpw(current_password.encode('utf-8'), stored_hash):
                    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    logging.debug("Current password verified using bcrypt")
                    if role == 'super_admin':
                        cur.execute("UPDATE super_admins SET password_hash = %s WHERE super_admin_id = %s", (hashed_password, admin_id))
                    else:
                        cur.execute("UPDATE admins SET password_hash = %s WHERE admin_id = %s", (hashed_password, admin_id))
                else:
                    logging.error("Current password is incorrect (bcrypt check failed)")
                    return jsonify({"error": "Current password is incorrect"}), 400
            except Exception as e:
                logging.exception("Password hash validation failed (bcrypt)")
                return jsonify({"error": str(e)}), 400
        else:
            logging.error("No password hash found in DB")
            return jsonify({"error": "User not found or password missing"}), 404

    # --- Profile update ---
    if role == 'super_admin':
        cur.execute("""
            UPDATE super_admins
            SET first_name = %s, last_name = %s, email = %s, phone_number = %s, profile_image = %s
            WHERE super_admin_id = %s
        """, (first_name, last_name, email, phone, image_to_save, admin_id))
    else:
        cur.execute("""
            UPDATE admins
            SET first_name = %s, last_name = %s, email = %s, phone_number = %s, profile_image = %s
            WHERE admin_id = %s
        """, (first_name, last_name, email, phone, image_to_save, admin_id))

    conn.commit()
    cur.close()
    conn.close()
    logging.info("Profile update committed successfully")
    # Audit: log profile update
    log_audit(admin_id, role, "update_profile_details", f"Updated profile details for {role} ID {admin_id}")
    return jsonify({"message": "Profile updated successfully"}), 200


@admin_bp.route('/profile-picture/<string:route_role>/<int:route_admin_id>')
@token_required_with_roles(required_actions=["admin_profile_picture"])
def admin_profile_picture(admin_id, role, role_id, *args, **kwargs):
    logging.debug(f"[DASHBOARD DEBUG] {request.method} {request.path} | function: admin_profile_picture")
    """
    Returns the profile picture for the specified admin.
    - route_role: from the URL (e.g., 'super_admin' or 'admin')
    - route_admin_id: from the URL (the admin user id)
    - admin_id, role, role_id: injected by the decorator (token-based, currently logged in admin)
    """
    # Use URL params from kwargs to determine whose profile picture to serve
    route_role = kwargs.get('route_role')
    route_admin_id = kwargs.get('route_admin_id')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if route_role == 'super_admin':
            cursor.execute("SELECT profile_image FROM super_admins WHERE super_admin_id = %s", (route_admin_id,))
        else:
            cursor.execute("SELECT profile_image FROM admins WHERE admin_id = %s", (route_admin_id,))

        result = cursor.fetchone()

        if not result or not result[0]:
            logging.info(f"No profile picture for {route_role} {route_admin_id}. Returning default.")
            return send_file(os.path.join('static', 'default_resource.png'), mimetype='image/png')

        return Response(result[0], mimetype='image/png')  # change mimetype if needed

    except Exception as e:
        logging.error(f"Error retrieving profile picture for {route_role} {route_admin_id}: {e}", exc_info=True)
        return send_file(os.path.join('static', 'default_resource.png'), mimetype='image/png')

    finally:
        cursor.close()
        conn.close()