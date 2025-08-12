
import logging
import traceback
from flask import g, jsonify, render_template, request
from routes.Auth.token import employee_jwt_required
from routes.Auth.device_tracking import detect_device_info
from routes.Auth.token import generate_token
from routes.Auth.utils import get_db_connection
from . import SECRET_KEY, login_bp
from extensions import csrf
import bcrypt
import jwt
from user_agents import parse


# Route for logging in (For employee)
@csrf.exempt
@login_bp.route('/', methods=['GET', 'POST'])
def employeelogin():
    import sys

    def debug_log(msg):
        # You can replace this with any logging framework or file writing as needed
        print(f"[DEBUG][employeelogin]: {msg}", file=sys.stderr)

    if request.method == 'POST':
        debug_log(f"Incoming POST request. Content-Type: {request.content_type}")

        if request.content_type != 'application/json':
            debug_log("Unsupported Media Type")
            return jsonify({'error': 'Unsupported Media Type, expected application/json'}), 415

        try:
            data = request.get_json()
            debug_log(f"Parsed JSON data: {data}")
            email = data.get('email')
            password = data.get('password')

            if not email or not password:
                debug_log(f"Missing credentials - email: {email}, password: {'present' if password else 'missing'}")
                return jsonify({'error': 'Email and password are required'}), 400
        except Exception as ex:
            debug_log(f"Exception in parsing JSON: {traceback.format_exc()}")
            return jsonify({'error': 'Invalid JSON data'}), 400

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            debug_log(f"Querying for user with email: {email}")
            cursor.execute("SELECT employee_id, password, account_status FROM employees WHERE email = %s", (email,))
            user = cursor.fetchone()
            debug_log(f"User fetch result: {user}")
            cursor.close()
            conn.close()
        except Exception as ex:
            debug_log(f"Exception during DB user fetch: {traceback.format_exc()}")
            return jsonify({'error': 'Internal server error on user lookup'}), 500

        if user:
            user_id, hashed_password, account_status = user
            debug_log(f"Account status: {account_status}")

            try:
                hashed_password = hashed_password.encode('utf-8')
            except Exception as ex:
                debug_log(f"Exception encoding hashed password: {traceback.format_exc()}")
                return jsonify({'error': 'Password encoding error'}), 500

            if account_status == 'Deactivated':
                debug_log("Account is deactivated")
                return jsonify({'status': 'Deactivated', 'message': 'Your account is deactivated.'}), 403
            elif account_status == 'Terminated':
                debug_log("Account is terminated")
                return jsonify({'status': 'Terminated', 'message': 'Your account is terminated.'}), 403
            elif account_status != 'Activated':
                debug_log(f"Account status not permitted: {account_status}")
                return jsonify({'status': 'Unknown', 'message': f'Your account status \"{account_status}\" is not permitted for login.'}), 403

            try:
                password_match = bcrypt.checkpw(password.encode('utf-8'), hashed_password)
                debug_log(f"Password match: {password_match}")
            except Exception as ex:
                debug_log(f"Exception in password check: {traceback.format_exc()}")
                return jsonify({'error': 'Password verification error'}), 500

            if password_match:
                try:
                    # 🔐 Generate JWT token and extract JTI
                    token, jti, issued_at = generate_token(user_id)
                    debug_log(f"Generated token for user_id: {user_id}, jti: {jti}, issued_at: {issued_at}")

                    # 🛠 Collect device info
                    device_info = detect_device_info()
                    device_name = device_info['device_name']
                    device_os = device_info['device_os']
                    browser_name = device_info['browser_name']
                    browser_version = device_info['browser_version']
                    ip_address = device_info['ip_address']

                    debug_log(f"Device info: {device_info}")

                    # 💾 Insert into devices and update employee status to Active
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    debug_log("Inserting device info into devices table and updating current_jti and status")
                    cursor.execute("""
                        INSERT INTO devices (
                            employee_id, device_name, device_os, browser_name,
                            browser_version, ip_address, jti, issued_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        user_id, device_name, device_os, browser_name,
                        browser_version, ip_address, jti, issued_at
                    ))
                    
                    # Update both current_jti and status in one query
                    cursor.execute("""
                        UPDATE employees 
                        SET current_jti = %s, status = 'Active' 
                        WHERE employee_id = %s
                    """, (jti, user_id))
                    
                    conn.commit()
                    cursor.close()
                    conn.close()
                    debug_log("Device info inserted and employee current_jti/status updated successfully")

                    return jsonify({"message": "Login successful", "token": token}), 200
                except Exception as ex:
                    debug_log(f"Exception during token generation/device insert: {traceback.format_exc()}")
                    return jsonify({'error': 'Internal server error during login process'}), 500
            else:
                debug_log("Password did not match")
                return jsonify({'error': 'Invalid email or password'}), 401
        else:
            debug_log("No user found with that email")
            return jsonify({'error': 'Invalid email or password'}), 401

    reason = request.args.get("reason")
    debug_log(f"Rendering login page, reason: {reason}")
    return render_template('Login/EmployeeLogin.html', reason=reason)

# Route for logging out (For employee)
@csrf.exempt
@login_bp.route('/logout', methods=['POST'], endpoint='logout')
@employee_jwt_required()  # Requires token in Authorization header
def employee_logout():
    try:
        # 1. Log incoming Authorization header
        auth_header = request.headers.get('Authorization')
        print(f"[LOGOUT] Authorization Header: {auth_header}")
        logging.debug(f"[LOGOUT] Authorization Header: {auth_header}")

        if not auth_header or not auth_header.startswith("Bearer "):
            print("[LOGOUT] Missing or malformed Authorization header.")
            logging.warning("[LOGOUT] Missing or malformed Authorization header.")
            return jsonify({"error": "Authorization header is missing or invalid"}), 401

        # 2. Extract token
        try:
            token = auth_header.split()[1]
            print(f"[LOGOUT] Extracted Token: {token}")
            logging.debug(f"[LOGOUT] Extracted Token: {token}")
        except Exception as e:
            print(f"[LOGOUT] Error extracting token: {e}")
            logging.error(f"[LOGOUT] Error extracting token: {e}")
            return jsonify({"error": "Failed to extract token from header"}), 400

        # 3. Decode token
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            print(f"[LOGOUT] Decoded Payload: {payload}")
            logging.debug(f"[LOGOUT] Decoded Payload: {payload}")
        except Exception as e:
            print(f"[LOGOUT] Failed to decode JWT: {e}")
            logging.error(f"[LOGOUT] Failed to decode JWT: {e}")
            return jsonify({"error": f"JWT decode failed: {str(e)}"}), 400

        # 4. Get jti and employee_id
        jti = payload.get("jti")
        employee_id = g.get('employee_id')
        print(f"[LOGOUT] Employee ID: {employee_id}, JTI: {jti}")
        logging.debug(f"[LOGOUT] Employee ID: {employee_id}, JTI: {jti}")

        if not jti or not employee_id:
            print("[LOGOUT] Missing JTI or Employee ID.")
            logging.warning("[LOGOUT] Missing JTI or Employee ID.")
            return jsonify({"error": "Invalid token data", "details": {"jti": jti, "employee_id": employee_id}}), 400

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 5. Update employee status to Inactive
            cursor.execute("""
                UPDATE employees
                SET status = 'Inactive'
                WHERE employee_id = %s
            """, (employee_id,))
            
            # 6. Blacklist the token
            cursor.execute("""
                INSERT INTO blacklisted_tokens (jti, employee_id)
                VALUES (%s, %s)
                ON CONFLICT (jti) DO NOTHING
            """, (jti, employee_id))
            
            conn.commit()
            print("[LOGOUT] Token successfully blacklisted and employee status set to Inactive.")
            logging.info("[LOGOUT] Token successfully blacklisted and employee status set to Inactive.")
        except Exception as db_error:
            print(f"[LOGOUT] Failed to update DB during logout: {db_error}")
            logging.error(f"[LOGOUT] Failed to update DB during logout: {db_error}")
            return jsonify({"error": "Logout failed", "db_error": str(db_error)}), 500
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception as close_error:
                print(f"[LOGOUT] Error closing connection: {close_error}")
                logging.error(f"[LOGOUT] Error closing connection: {close_error}")

        print("[LOGOUT] Logout successful!")
        logging.info("[LOGOUT] Logout successful!")
        return jsonify({
            "success": True,
            "message": "Logged out successfully"
        }), 200

    except Exception as general_error:
        print(f"[LOGOUT] Unhandled exception during logout: {general_error}")
        logging.error(f"[LOGOUT] Unhandled exception during logout: {general_error}")
        return jsonify({"error": "Unexpected error during logout", "exception": str(general_error)}), 500