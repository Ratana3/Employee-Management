
# Route to update employee details
import io
import logging
import re
from PIL import Image
import bcrypt
from flask import Response, g, jsonify, make_response, redirect, render_template, request, send_file, url_for
from . import employee_bp
from routes.Auth.token import employee_jwt_required
from routes.Auth.two_authentication import require_employee_2fa
from routes.Auth.utils import get_db_connection
from routes.Auth.audit import log_employee_incident,log_employee_audit

@employee_bp.route('/profile', methods=['GET','POST'])
def profile_page_shell():
    return render_template('Employee/profile.html')  # Only serves the HTML shell

@employee_bp.route('/update_profile', methods=['POST'])
@employee_jwt_required()
@require_employee_2fa
def update_profile():
    print("✅ /update_profile route was hit")
    data = request.form
    employee_id = g.employee_id  # Retrieved from JWT

    print("📨 Raw Form Data:", data)
    print("👤 Employee ID from JWT:", employee_id)

    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized profile update attempt with 2FA - no employee_id in session",
            severity="High"
        )
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    # Helper to clean and convert input
    def clean_input(field_name, field_type=str):
        value = data.get(field_name)
        print(f"🔍 Checking field '{field_name}':", value)
        if value is None or value.strip() == "":
            return None
        if field_type == int:
            try:
                return int(value)
            except ValueError:
                print(f"⚠️ Cannot convert '{field_name}' to int:", value)
                return None
        return value.strip()
    
    # Extract fields, now including gender
    fields_to_update = {
        "first_name": clean_input('first_name'),
        "last_name": clean_input('last_name'),
        "email": clean_input('email'),
        "phone_number": clean_input('phone_number'),
        "department": clean_input('department'),
        "salary": clean_input('salary', int),
        "position": clean_input('position'),
        "date_hired": clean_input('date_hired'),
        "address1": clean_input('address1'),
        "address2": clean_input('address2'),
        "city": clean_input('city'),
        "status": clean_input('status'),
        "permission": clean_input('permission'),
        "date_terminated": clean_input('date_terminated'),
        "created": clean_input('created'),
        "account_status": clean_input('account_status'),
        "skills": clean_input('skills'),
        "certification": clean_input('certification'),
        "education": clean_input('education'),
        "language": clean_input('language'),
        "hobbies": clean_input('hobbies'),
        "gender": clean_input('gender')
    }

    # Profile image upload and compression with debugging
    profile_image_updated = False
    profile_image = request.files.get('profile')
    if profile_image:
        print("📷 Found profile image field")
        if profile_image.filename:
            print("📎 Image filename:", profile_image.filename)
            try:
                img = Image.open(profile_image)
                img_format = img.format
                print(f"🖼️ Image opened, format: {img_format}, size: {img.size}")
                # Resize if larger than 512x512 (for example)
                max_size = (512, 512)
                # Use Pillow 10+ compatible resampling
                try:
                    resample = Image.Resampling.LANCZOS
                except AttributeError:
                    resample = Image.LANCZOS  # For Pillow <10
                img.thumbnail(max_size, resample)
                print(f"🖼️ Image resized to: {img.size}")
                img_io = io.BytesIO()
                if img_format == 'PNG':
                    img.save(img_io, format='PNG', optimize=True)
                else:
                    img.save(img_io, format='JPEG', quality=70, optimize=True)
                img_io.seek(0)
                img_bytes = img_io.read()
                print(f"✅ Image successfully compressed and read ({len(img_bytes)} bytes)")
                fields_to_update["profile"] = img_bytes
                profile_image_updated = True
            except Exception as e:
                print("❌ Error reading/compressing image data:", e)
                log_employee_incident(
                    employee_id=employee_id,
                    description=f"Profile image processing failed during profile update: {str(e)}",
                    severity="Medium"
                )
        else:
            print("⚠️ Image field present but filename is empty")
    else:
        print("⚠️ No image uploaded in request")

    # Check if email is the correct format
    email = clean_input('email')
    if email and not re.match(r'^[a-zA-Z0-9._%+-]+@gmail\.com$', email):
        print(f"❌ Invalid email format: {email}")
        log_employee_incident(
            employee_id=employee_id,
            description=f"Profile update attempted with invalid email format: {email}",
            severity="Low"
        )
        return jsonify({"success": False, "message": "Invalid email format. Only Gmail addresses are allowed."}), 400

    # Handle password update ONLY if user typed a new one
    password_updated = False
    password = clean_input('password')
    if password and password != "Leave blank to keep current password":
        print("🔐 Password provided, hashing...")
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        fields_to_update["password"] = hashed_password
        password_updated = True

    # Remove keys with None values
    original_fields_count = len(fields_to_update)
    fields_to_update = {k: v for k, v in fields_to_update.items() if v is not None}
    updated_fields_count = len(fields_to_update)

    if updated_fields_count == 0:
        log_employee_incident(
            employee_id=employee_id,
            description="Profile update attempted with no valid fields to update",
            severity="Low"
        )
        return jsonify({"success": False, "message": "No valid fields to update"}), 400

    print("📝 Final Fields to Update:", list(fields_to_update.keys()))
    if "profile" in fields_to_update:
        print(f"📝 Profile image will be updated, size: {len(fields_to_update['profile'])} bytes")
    else:
        print("📝 Profile image will NOT be updated")

    # Build SQL dynamically
    set_clause = ", ".join([f"{key} = %s" for key in fields_to_update.keys()])
    query = f"UPDATE employees SET {set_clause} WHERE employee_id = %s"
    params = list(fields_to_update.values()) + [employee_id]

    print("🔧 SQL Query:", query)
    print("📦 Parameters (Types):", [(type(p).__name__, str(p)[:100]) for p in params])  # Preview large blob data

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get employee's current name for logging
        cursor.execute("SELECT first_name, last_name, email FROM employees WHERE employee_id = %s", (employee_id,))
        current_info = cursor.fetchone()
        current_name = f"{current_info[0]} {current_info[1]}" if current_info else "Unknown"
        current_email = current_info[2] if current_info else "unknown@email.com"

        cursor.execute(query, tuple(params))
        
        if cursor.rowcount == 0:
            log_employee_incident(
                employee_id=employee_id,
                description="Profile update failed: no rows affected despite valid fields",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({"success": False, "message": "Profile update failed"}), 500

        conn.commit()
        print("✅ Update successful.")
        
        # Double-check DB after update
        cursor.execute("SELECT octet_length(profile) FROM employees WHERE employee_id = %s", (employee_id,))
        profile_len = cursor.fetchone()
        print(f"🔬 DB profile image length after update: {profile_len[0] if profile_len else 'N/A'}")

        # Log successful audit trail
        updated_fields_list = [k for k in fields_to_update.keys() if k != 'profile' and k != 'password']
        special_updates = []
        if profile_image_updated:
            special_updates.append(f"profile image ({len(fields_to_update['profile'])} bytes)")
        if password_updated:
            special_updates.append("password")
        
        fields_summary = ', '.join(updated_fields_list) if updated_fields_list else "none"
        special_summary = ', '.join(special_updates) if special_updates else "none"
        
        new_email = fields_to_update.get('email', current_email)
        email_change = f" (email: {current_email} → {new_email})" if new_email != current_email else ""
        
        log_employee_audit(
            employee_id=employee_id,
            action="update_profile",
            details=f"Successfully updated profile for {current_name}{email_change}: {updated_fields_count} fields updated | Fields: {fields_summary} | Special: {special_summary}"
        )

        cursor.close()
        conn.close()
        return jsonify({"success": True, "message": "Profile updated successfully!"})
        
    except Exception as e:
        print("❌ Error during database update:", e)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error during secure profile update: {str(e)}",
            severity="High"
        )
        
        return jsonify({"success": False, "message": f"An error occurred: {str(e)}"}), 500
      
@employee_bp.route('/api/profile-info', methods=['GET'])
@employee_jwt_required()
def api_profile_info():
    logging.debug("Received request at /api/profile-info")

    user_id = g.employee_id
    role = g.employee_role
    
    if not user_id:
        logging.warning("Invalid or expired token.")
        log_employee_incident(
            employee_id=None,
            description="Unauthorized profile info access attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        logging.debug(f"📦 Fetching user data for employee_id={user_id}")

        cursor.execute("""
            SELECT 
                e.employee_id, e.first_name, e.last_name, e.email, e.phone_number, 
                e.department, e.date_hired, e.address1, e.address2, e.certification, e.skills, 
                e.education, e.language, e.hobbies, e.password, e.city,
                t.team_name,r.role_name,e.date_of_birth,e.gender,
                e.salary, e.status, e.account_status
            FROM employees e
            LEFT JOIN teams t ON e.team_id = t.team_id
            LEFT JOIN roles r ON e.role_id = r.role_id
            WHERE e.employee_id = %s
        """, (user_id,))
        user = cursor.fetchone()

        if not user:
            logging.warning(f"⚠️ No user found for employee_id={user_id}")
            log_employee_incident(
                employee_id=user_id,
                description=f"Profile info access attempted but employee {user_id} not found in database",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 404

        # Log successful audit trail
        employee_name = f"{user[1]} {user[2]}" if user[1] and user[2] else "Unknown"
        department = user[5] or "Unknown"
        team_name = user[16] or "No team"
        role_name = user[17] or "Unknown role"
        
        log_employee_audit(
            employee_id=user_id,
            action="view_profile_info",
            details=f"Accessed profile information for {employee_name} in {department} ({team_name}, {role_name})"
        )

    except Exception as e:
        logging.error(f"💥 Database error while fetching user data: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=user_id,
            description=f"System error while fetching profile information: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cursor.close()
        conn.close()

    try:
        profile_picture_url = url_for('employee_bp.profile_picture', user_id=user_id)
    except Exception as e:
        logging.warning(f"⚠️ Failed to generate profile_picture_url: {e}")
        profile_picture_url = '/static/default_resource.png'

    user_details = {
        'employee_id': user[0],
        'first_name': user[1],
        'last_name': user[2],
        'email': user[3],
        'phone_number': user[4],
        'department': user[5],
        'date_hired': user[6].isoformat() if user[6] and hasattr(user[6], 'isoformat') else user[6],
        'address1': user[7],
        'address2': user[8],
        'certification': user[9],
        'skills': user[10],
        'education': user[11],
        'language': user[12],
        'hobbies': user[13],
        'password': user[14],
        'city': user[15],
        'team_name': user[16],
        'role_name': user[17],
        'date_of_birth': user[18],
        'gender': user[19],
        'salary': user[20],
        'status': user[21],
        'account_status': user[22],
        'profile_picture_url': profile_picture_url
    }
    logging.debug("✅ Returning profile info.")
    return jsonify({'user': user_details, 'employee_role': role})

@employee_bp.route('/profile-picture/<int:user_id>')
@employee_jwt_required()
def profile_picture(user_id):
    try:
        requesting_employee_id = g.employee_id
        
        if not requesting_employee_id:
            log_employee_incident(
                employee_id=None,
                description=f"Unauthorized profile picture access attempt for user {user_id} - no employee_id in session",
                severity="Medium"
            )
            return send_file('static/default_resource.png', mimetype='image/png')

        print(f"🖼️ Serving profile picture for user_id={user_id}")
        
        # Basic access control - employees can view their own profile picture
        # For stricter control, you could add team/department checks here
        if requesting_employee_id != user_id:
            # Log access to other employee's profile picture (might be legitimate for team views)
            log_employee_audit(
                employee_id=requesting_employee_id,
                action="view_profile_picture",
                details=f"Accessed profile picture for employee {user_id}"
            )
        else:
            # Log own profile picture access
            log_employee_audit(
                employee_id=requesting_employee_id,
                action="view_own_profile_picture",
                details=f"Accessed own profile picture"
            )
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT profile FROM employees WHERE employee_id = %s", (user_id,))
        result = cursor.fetchone()
        
        if not result or not result[0]:
            print(f"⚠️ No profile picture found for user {user_id}. Returning default.")
            cursor.close()
            conn.close()
            return send_file('static/default_resource.png', mimetype='image/png')
            
        # Convert memoryview (from some DBs) to bytes
        image_bytes = bytes(result[0])
        print(f"🖼️ Retrieved {len(image_bytes)} bytes from DB for user {user_id}")

        # Try to detect format (PNG/JPEG)
        if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            mimetype = 'image/png'
        elif image_bytes[:2] == b'\xff\xd8':
            mimetype = 'image/jpeg'
        else:
            mimetype = 'application/octet-stream'
        print(f"🖼️ Detected image mimetype: {mimetype}")

        response = make_response(image_bytes)
        response.headers['Content-Type'] = mimetype
        # Prevent caching
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        print("🖼️ Response ready, returning image data.")
        
        cursor.close()
        conn.close()
        return response

    except Exception as e:
        print(f"❌ Error retrieving profile picture for user {user_id}: {e}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while serving profile picture for user {user_id}: {str(e)}",
            severity="Medium"
        )
        
        return send_file('static/default_resource.png', mimetype='image/png')
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@employee_bp.route('/get_employee_for_update/<int:id>', methods=['GET'])
@employee_jwt_required()
def get_employee(id):
    try:
        requesting_employee_id = g.employee_id
        
        if not requesting_employee_id:
            log_employee_incident(
                employee_id=None,
                description=f"Unauthorized employee data access attempt for employee {id} - no employee_id in session",
                severity="High"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        # Security check: employees should typically only access their own data
        # Unless they have special permissions (admin/manager roles)
        if requesting_employee_id != id:
            log_employee_incident(
                employee_id=requesting_employee_id,
                description=f"Employee attempted to access another employee's data: requested employee {id} data",
                severity="High"
            )
            return jsonify({'error': 'Access denied: Cannot access other employee data'}), 403

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Enhanced query to get more context for logging
        cursor.execute("""
            SELECT e.employee_id, e.first_name, e.last_name, e.email, e.password, e.phone_number,
                   e.education, e.language, e.hobbies, e.certification, e.skill,
                   e.shift, e.team, e.team_role, e.address1, e.address2, e.city,
                   e.salary, e.status, e.date_hired, e.date_terminated, e.position,
                   e.permission, e.created, e.account_status, e.address, e.profile,
                   e.department, t.team_name, r.role_name
            FROM employees e
            LEFT JOIN teams t ON e.team_id = t.team_id
            LEFT JOIN roles r ON e.role_id = r.role_id
            WHERE e.employee_id = %s
        """, (id,))
        
        employee = cursor.fetchone()

        if not employee:
            log_employee_incident(
                employee_id=requesting_employee_id,
                description=f"Employee attempted to access non-existent employee data: employee {id} not found",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Employee not found'}), 404

        # Convert to dictionary for JSON response
        columns = [desc[0] for desc in cursor.description]
        employee_dict = dict(zip(columns, employee))
        
        # Remove sensitive data from response (keep password hash but don't expose it fully)
        if 'password' in employee_dict:
            employee_dict['password'] = '********'  # Mask password in response
        
        # Handle profile image (convert to indication rather than raw bytes)
        profile_size = 0
        if 'profile' in employee_dict and employee_dict['profile']:
            profile_size = len(employee_dict['profile'])
            employee_dict['profile'] = f"Profile image present ({profile_size} bytes)"
        else:
            employee_dict['profile'] = "No profile image"

        # Log successful audit trail
        employee_name = f"{employee_dict.get('first_name', 'Unknown')} {employee_dict.get('last_name', 'Unknown')}"
        department = employee_dict.get('department', 'Unknown')
        team_name = employee_dict.get('team_name', 'No team')
        role_name = employee_dict.get('role_name', 'Unknown role')
        status = employee_dict.get('status', 'Unknown')
        position = employee_dict.get('position', 'Unknown position')
        
        # Determine what type of data was accessed
        sensitive_fields = ['salary', 'password', 'account_status', 'permission']
        personal_fields = ['email', 'phone_number', 'address1', 'address2', 'city']
        professional_fields = ['department', 'position', 'team_name', 'role_name', 'date_hired']
        
        data_categories = []
        if any(field in employee_dict and employee_dict[field] for field in sensitive_fields):
            data_categories.append("sensitive")
        if any(field in employee_dict and employee_dict[field] for field in personal_fields):
            data_categories.append("personal")
        if any(field in employee_dict and employee_dict[field] for field in professional_fields):
            data_categories.append("professional")
        
        categories_summary = ', '.join(data_categories) if data_categories else "basic"
        profile_info = f", profile image ({profile_size} bytes)" if profile_size > 0 else ", no profile image"
        
        log_employee_audit(
            employee_id=requesting_employee_id,
            action="get_employee_for_update",
            details=f"Retrieved own employee data for {employee_name} in {department} ({team_name}, {role_name}): {position}, status: {status} | Data categories: {categories_summary}{profile_info}"
        )

        cursor.close()
        conn.close()
        return jsonify(employee_dict), 200

    except Exception as e:
        print("Error fetching employee:", e)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while fetching employee data for employee {id}: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal Server Error'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()