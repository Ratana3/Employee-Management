
from datetime import datetime, timedelta
import logging
import uuid

from flask import current_app, jsonify, render_template, request
from routes.Auth.audit import log_audit
from routes.Auth.token import get_admin_from_token
from routes.Auth.utils import get_db_connection
from extensions import csrf
import bcrypt
import jwt
from jwt import ExpiredSignatureError
from . import SECRET_KEY, login_bp

@csrf.exempt
@login_bp.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    logging.debug("\n=== NEW ADMIN LOGIN REQUEST ===")
    conn = None
    cursor = None

    if request.method == 'GET':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT role_name FROM roles ORDER BY role_name ASC")
            roles = [row[0] for row in cursor.fetchall()]
            return render_template('Login/AdminLogin.html', roles=roles)
        except Exception as e:
            logging.error(f"Error fetching roles: {e}", exc_info=True)
            return render_template('Login/AdminLogin.html', roles=[])
        finally:
            if cursor:
                cursor.close()
            conn.close()

    try:
        if request.content_type != 'application/json':
            logging.warning("Unsupported Media Type - expected application/json")
            return jsonify({'error': 'Unsupported Media Type, expected application/json'}), 415

        data = request.get_json()
        logging.debug(f"Parsed JSON: {data}")

        email = data.get('email')
        password = data.get('password')
        role = data.get('role')  # e.g., 'HR', 'IT', 'super_admin'

        if not email or not password or not role:
            logging.warning("Missing email, password, or role")
            return jsonify({'error': 'Email, password, and role are required'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # --- Get admin info and role_id ---
        if role == 'super_admin':
            cursor.execute("""
                SELECT super_admin_id, password_hash,role_id
                FROM super_admins
                WHERE email = %s
            """, (email,))
            result = cursor.fetchone()
            if result:
                admin_id, hashed_password,role_id = result
                is_verified = True
            else:
                logging.error("Super admin not found")
                return jsonify({'error': 'Admin not found or role mismatch'}), 401
        else:
            cursor.execute("""
                SELECT a.admin_id, a.password, a.is_verified, a.role_id
                FROM admins a
                WHERE a.email = %s AND a.role_id = (SELECT role_id FROM roles WHERE role_name = %s)
            """, (email, role))
            result = cursor.fetchone()
            if result:
                admin_id, hashed_password, is_verified, role_id = result
            else:
                logging.error("Admin not found or role mismatch")
                return jsonify({'error': 'Admin not found or role mismatch'}), 401

        if not is_verified:
            logging.warning("Admin is not verified")
            return jsonify({'error': 'Access denied. Admin is not verified.'}), 403

        if not bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8')):
            logging.error("Incorrect password")
            return jsonify({'error': 'Incorrect password'}), 401

        # ✅ Generate token with unique JTI and proper claims
        jti = str(uuid.uuid4())
        payload = {
            'admin_id': admin_id,
            'role': role,
            'role_id': role_id,  # <-- always include, even for super_admin
            'admin_type': 'super_admin' if role == 'super_admin' else 'admin',
            'jti': jti,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=8)
        }
        if role_id is not None:
            payload['role_id'] = role_id

        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

        # ✅ Store JTI in the database
        if role == 'super_admin':
            cursor.execute(
                "UPDATE super_admins SET jti = %s WHERE super_admin_id = %s",
                (jti, admin_id)
            )
        else:
            cursor.execute(
                "UPDATE admins SET jti = %s WHERE admin_id = %s",
                (jti, admin_id)
            )
        conn.commit()

        logging.debug(f"Generated admin token payload: {payload}")
        logging.info(f"Admin login successful - admin_id: {admin_id}, role: {role}, role_id: {role_id}")

        return jsonify({'message': 'Login successful', 'token': token})

    except Exception as e:
        logging.error(f"Admin login error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

    finally:
        if cursor:
            cursor.close()
        conn.close()

# Route for logging out (For admin and super admin)
@login_bp.route('/admin_logout', methods=['POST'])
def admin_logout():
    current_app.logger.debug("Admin logout requested")

    auth_header = request.headers.get('Authorization', '')
    token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else None

    if not token:
        current_app.logger.warning("No token found during logout")
    else:
        try:
            admin_id, role = get_admin_from_token(token)
            if admin_id:
                current_app.logger.debug(f"Token decoded - admin_id: {admin_id}, role: {role}")
                log_audit(admin_id, role, "Logout", f"{role.capitalize()} logged out")

                # Reset 2FA
                try:
                    conn = get_db_connection()
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            UPDATE two_factor_verifications
                            SET is_verified = FALSE
                            WHERE admin_id = %s
                        """, (admin_id,))
                        conn.commit()
                        current_app.logger.debug("2FA reset for admin")
                except Exception as db_err:
                    current_app.logger.error(f"2FA DB error: {db_err}")
                finally:
                    if 'conn' in locals():
                        conn.close()

        except ExpiredSignatureError:
            current_app.logger.debug("Token expired - still processing logout")
        except Exception as e:
            current_app.logger.error(f"Logout token error: {e}")

    return jsonify({'message': 'Logged out'})
