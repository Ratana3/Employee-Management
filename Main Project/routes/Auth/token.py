# function to check for token , role, permission to routes (Start)
import base64
from datetime import datetime, timedelta
from functools import wraps
import logging
import uuid
import jwt
from flask import current_app, g, jsonify, redirect, request, url_for
from routes.Auth.utils import get_db_connection
from psycopg2.errors import UniqueViolation
import psycopg2
from psycopg2 import DatabaseError,extras
from psycopg2.extras import RealDictCursor

from routes.Login import SECRET_KEY



# Below are the endpoints for all routes for a specific page so that the system can check whether the admin that is logged in has access to a certain features or not 
# (Except for super_admin, super_admin has access to everything)
#function names for dashboard

# Dashboard endpoints
DASHBOARD_ENDPOINTS = {
    "get_users_by_role",
    "get_unread_messages",
    "mark_message_as_read",
    "get_message_inbox",
    "send_message",
    "dashboard",
    "admin_profile_picture",
    "get_profile_details",
    "update_profile_details"
}

# Attendance and Time Tracking endpoints
ATTENDANCE_AND_TIME_TRACKING_ENDPOINTS = {
    "delete_shift_swap_request",
    "reject_shift_swap_request",
    "approve_shift_swap_request",
    "get_shift_swap_requests",
    "get_leave_request_details",
    "leave_requests_data",
    "disapprove_leaverequests",
    "verify_leaverequests",
    "disapprove_attendance",
    "disapprove_overtime",
    "verify_overtime",
    "verify_attendance_admin",
    "get_attendance_details",
    "edit_attendance",
    "delete_attendance",
    "assign_shift",
    "delete_assigned_shift",
    "get_employee_shifts",
    "get_employee_details",
    "get_shifts",
    "manage_leave",
    "add_shift",
    "update_shift",
    "delete_shift",
    "attendanceandtimetracking_data",
    "delete_absent",
    "mark_absent"
}

# Employee Engagement endpoints
EMPLOYEE_ENGAGEMENT_ENDPOINTS = {
    "delete_travel_request",
    "allow_resubmission",
    "get_survey_assignments",
    "get_travel_requests",
    "approve_travel_request",
    "reject_travel_request",
    "get_health_resource_details",
    "delete_health_resource",
    "edit_health_resource",
    "add_health_resource",
    "get_health_resources",
    "get_event_details",
    "update_event",
    "delete_event",
    "create_event",
    "get_events",
    "get_survey_details",
    "survey_responses",
    "edit_survey",
    "delete_survey",
    "create_survey",
    "get_surveys",
    "delete_recognition",
    "edit_recognition",
    "add_recognition",
    "get_recognitions"
}

# Employee Management endpoints
EMPLOYEE_MANAGEMENT_ENDPOINTS = {
    "view_teams",
    "edit_team",
    "add_team_member",
    "delete_team",
    "remove_team_member",
    "deactivate_employee",
    "activate_employee",
    "terminate_employee",
    "update_employee",
    "create_team",
    "get_team_management_data",
    "add_employee",
    "delete_employee",
    "employeemanagement_data"
}

# Import Data endpoints
IMPORT_DATA_ENDPOINTS = {
    "import_employees"
}

# Notifications and Communication endpoints
NOTIFICATIONS_AND_COMMUNICATION_ENDPOINTS = {
    "feedback_request_responses",
    "update_record",
    "delete_record",
    "edit_record",
    "notification_and_communication_data",
    "create_feedback",
    "manage_alerts",
    "create_announcement",
    "create_meeting",
}

# Payroll and Financial Management endpoints
PAYROLL_AND_FINANCIAL_MANAGEMENT_ENDPOINTS = {
    "get_savings_plan_request",
    "delete_savings_plan_request",
    "delete_payroll",
    "update_payment_status_paid",
    "update_payment_status_not_yet_paid",
    "edit_payroll",
    "get_payrolls",
    "view_payroll_details",
    "process_payroll",
    "get_employee_details_salary",
    "reject_expense",
    "approve_expense",
    "get_expense_claims",
    "delete_expense",
    "generate_tax_document",
    "get_tax_documents",
    "serve_tax_document",
    "edit_tax_document",
    "delete_tax_document",
    "update_bonus",
    "get_all_bonuses",
    "add_bonus",
    "delete_bonus",
    "get_bonus",
    "get_savings_plans",
    "get_saving_plan_details",
    "create_savings_plan",
    "get_all_employees",
    "update_savings_plan",
    "delete_savings_plan",
    "respond_savings_plan_request"
}

# Performance Management endpoints
PERFORMANCE_MANAGEMENT_ENDPOINTS = {
    "update_goal_evaluation",
    "get_team_goals",
    "update_progress",
    "edit_note",
    "delete_note",
    "get_goal_evaluation",
    "delete_feedback",
    "edit_feedback",
    "submit_feedback",
    "get_goals",
    "edit_review",
    "delete_review",
    "delete_goal",
    "assign_goal",
    "performance_data",
    "submit_review",
    "get_tasks",
    "get_employees",
    "get_teams",
    "assign_task",
    "update_task",
    "delete_task",
    "delete_task_part",
    "add_task_part"
}

# Profile endpoints
PROFILE_ENDPOINTS = {
    "get_profile_details",
    "update_profile_details",
    "admin_profile_picture"
}

# Report and Analytics endpoints
REPORT_AND_ANALYTICS_ENDPOINTS = {
    "get_productivity_report",
    "get_performance_report",
    "payroll_report",
    "get_attendance_report",
    "generate_reports",
    "reporting_and_analytics_data"
}

# Security and Compliance endpoints
SECURITY_AND_COMPLIANCE_ENDPOINTS = {
    "search_incidents",
    "search_compliance",
    "report_incident",
    "display_incidents",
    "display_compliance",
    "view_incident",
    "view_compliance",
    "delete_incident",
    "delete_compliance",
    "edit_incident",
    "edit_compliance",
    "get_document_categories",
    "get_document_history",
    "delete_document",
    "edit_document",
    "download_document",
    "upload_document",
    "delete_category",
    "create_category",
    "list_documents"
}

# System Administration endpoints
SYSTEM_ADMINISTRATION_ENDPOINTS = {
    "download_backup",
    "add_holiday",
    "create_leave_balance",
    "get_selection_data",
    "restore_backup",
    "list_backups",
    "create_backup",
    "delete_backup",
    "get_leave_requests",
    "get_holidays",
    "view_leave_request",
    "edit_leave_request",
    "delete_leave_request",
    "delete_holiday",
    "edit_holiday",
    "view_holiday",
    "edit_leave_balance",
    "get_employee_leave_details",
    "get_leave_balances"
}

# Training and Development endpoints
TRAINING_AND_DEVELOPMENT_ENDPOINTS = {
    "remove_badge_assignment",
    "insert_module",
    "assign_assessment",
    "issue_certificate",
    "get_assessment_details",
    "delete_certificate",
    "update_certificate",
    "get_certificates",
    "get_modules",
    "update_module",
    "delete_module",
    "update_assessment",
    "delete_assessment",
    "get_assessments",
    "get_learning_resource_by_id",
    "get_all_learning_resources",
    "add_learning_resource",
    "delete_learning_resource",
    "update_learning_resource",
    "view_badge",
    "delete_badge",
    "update_badge",
    "add_badge",
    "get_badges_with_assignments",
    "assign_badge",
    "get_assign_options"
}

# Verification endpoints
VERIFICATION_ENDPOINTS = {
    "review_requests_action",
    "review_requests",
    "reject_admin",
    "verify_admin",
    "get_pending_registrations",
    "delete_admin",
    "remove_access",
    "grant_access",
    "get_admins",
    "get_admin_permissions",
    "get_actions_for_route",
    "get_all_routes_and_actions",
    "delete_action",
    "update_action",
    "create_action",
    "delete_route",
    "update_route",
    "create_route",
    "list_routes"
}

# Workflow Management endpoints
WORKFLOW_MANAGEMENT_ENDPOINTS = {
    "view_timesheet",
    "get_my_requests",
    "get_all_routes_and_actions_to_request",
    "approve_stage",
    "get_approval_status",
    "approve_access",
    "request_access",
    "reject_request",
    "approve_request",
    "get_pending_approvals",
    "generate_timesheet",
    "get_employees_timesheet",
    "get_timesheet_details",
    "edit_timesheet",
    "delete_timesheet",
    "update_timesheet_status",
    "delete_ticket",
    "edit_ticket",
    "get_tickets",
    "get_edit_ticket",
    "view_ticket",
    "respond_to_ticket"
}

# Map endpoint_name to route_name for all known endpoints
ENDPOINT_TO_ROUTE_MAP = {}

for endpoint in DASHBOARD_ENDPOINTS:
    ENDPOINT_TO_ROUTE_MAP[endpoint] = "dashboard"
for endpoint in ATTENDANCE_AND_TIME_TRACKING_ENDPOINTS:
    ENDPOINT_TO_ROUTE_MAP[endpoint] = "attendanceandtimetracking"
for endpoint in EMPLOYEE_ENGAGEMENT_ENDPOINTS:
    ENDPOINT_TO_ROUTE_MAP[endpoint] = "employeeengagement"
for endpoint in EMPLOYEE_MANAGEMENT_ENDPOINTS:
    ENDPOINT_TO_ROUTE_MAP[endpoint] = "employeemanagement"
for endpoint in IMPORT_DATA_ENDPOINTS:
    ENDPOINT_TO_ROUTE_MAP[endpoint] = "importdata"
for endpoint in NOTIFICATIONS_AND_COMMUNICATION_ENDPOINTS:
    ENDPOINT_TO_ROUTE_MAP[endpoint] = "notificationsandcommunication"
for endpoint in PAYROLL_AND_FINANCIAL_MANAGEMENT_ENDPOINTS:
    ENDPOINT_TO_ROUTE_MAP[endpoint] = "payrollandfinancialmanagement"
for endpoint in PERFORMANCE_MANAGEMENT_ENDPOINTS:
    ENDPOINT_TO_ROUTE_MAP[endpoint] = "performancemanagement"
for endpoint in PROFILE_ENDPOINTS:
    ENDPOINT_TO_ROUTE_MAP[endpoint] = "profile"
for endpoint in REPORT_AND_ANALYTICS_ENDPOINTS:
    ENDPOINT_TO_ROUTE_MAP[endpoint] = "reportandanalytics"
for endpoint in SECURITY_AND_COMPLIANCE_ENDPOINTS:
    ENDPOINT_TO_ROUTE_MAP[endpoint] = "securityandcompliance"
for endpoint in SYSTEM_ADMINISTRATION_ENDPOINTS:
    ENDPOINT_TO_ROUTE_MAP[endpoint] = "systemadministration"
for endpoint in TRAINING_AND_DEVELOPMENT_ENDPOINTS:
    ENDPOINT_TO_ROUTE_MAP[endpoint] = "traininganddevelopment"
for endpoint in VERIFICATION_ENDPOINTS:
    ENDPOINT_TO_ROUTE_MAP[endpoint] = "verification"
for endpoint in WORKFLOW_MANAGEMENT_ENDPOINTS:
    ENDPOINT_TO_ROUTE_MAP[endpoint] = "workflowmanagement"


# Helper function to verify JWT token for admin
def verify_admin_token(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            logging.warning("Missing or invalid Authorization header")
            return jsonify({'error': 'Missing or invalid token'}), 401

        token = auth_header.split(' ', 1)[-1].strip()
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            logging.debug(f"Decoded token payload: {payload}")
        except jwt.ExpiredSignatureError:
            logging.warning("Token expired")
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError as e:
            logging.warning(f"Invalid token: {e}")
            return jsonify({'error': 'Invalid token'}), 401

        admin_id = payload.get('admin_id')
        role = payload.get('role')
        admin_type = payload.get('admin_type')
        jti = payload.get('jti')
        role_id = payload.get('role_id')

        # Fallback: fetch role_id from DB if not in token
        if not role_id and admin_id:
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT role_id FROM admins WHERE admin_id = %s", (admin_id,))
                res = cur.fetchone()
                cur.close()
                conn.close()
                if res:
                    role_id = res[0]
            except Exception as e:
                logging.error(f"Error fetching role_id from DB: {e}", exc_info=True)
                return jsonify({'error': 'Internal server error'}), 500

        if not all([admin_id, role, admin_type, jti, role_id]):
            logging.error("Token payload missing required fields")
            return jsonify({'error': 'Invalid token payload'}), 401

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            if role == 'super_admin':
                cur.execute("SELECT jti FROM super_admins WHERE super_admin_id = %s", (admin_id,))
            else:
                cur.execute("""
                    SELECT jti FROM admins
                    WHERE admin_id = %s AND role_id = (
                        SELECT role_id FROM roles WHERE role_name = %s
                    )
                """, (admin_id, role))

            result = cur.fetchone()
            cur.close()
            conn.close()

            if not result:
                logging.warning(f"No JTI found for {role} ID {admin_id}")
                return jsonify({'error': 'Invalid admin credentials'}), 403

            db_jti = result[0]
            if db_jti != jti:
                logging.warning(f"JTI mismatch for {role} {admin_id}: token={jti}, db={db_jti}")
                return jsonify({'error': 'session_conflict'}), 403

            g.admin_id = admin_id
            g.admin_role = role
            g.admin_type = admin_type
            g.role_id = role_id
            g.jti = jti
            request.admin_payload = payload

            logging.debug(f"Verified {role} token for admin_id={admin_id}")
            return fn(admin_id, role, role_id, *args, **kwargs)

        except Exception as e:
            logging.error(f"Error verifying token in DB: {e}", exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500

    return wrapper

# function to check for token authentication for logged in admin and permission to routes
def token_required_with_roles(allowed_roles=None, required_actions=None, require="any"):
    """
    Decorator for verifying admin JWT and fine-grained action permission(s) for a route.
    If allowed_roles is provided, checks against that list.
    If allowed_roles is None, checks admin_route_actions (per-action) using IDs.
    :param required_actions: (optional) a string or list/tuple of actions to check
    :param require: "any" (default) or "all" – require any or all actions to be present
    """
    def decorator(view_function):
        @verify_admin_token
        @wraps(view_function)
        def decorated_function(admin_id, role, role_id, *args, **kwargs):
            # Always allow super_admin for any route/action
            if role == 'super_admin':
                logging.debug(f"Super admin access granted for admin_id={admin_id}")
                return view_function(admin_id, role, role_id, *args, **kwargs)

            # Get endpoint name (function name)
            endpoint_name = (request.endpoint.split('.', 1)[-1] if request.endpoint else None)

            # --- SAFE JSON ACCESS FIX ---
            json_data = None
            if request.method == "POST" and request.is_json:
                json_data = request.get_json(silent=True) or {}
            else:
                json_data = {}

            original_route_name = (
                (json_data.get("route") if request.method == "POST" and request.is_json else None)
                or request.args.get("route")
                or endpoint_name
            )

            # --- Universal endpoint-to-route mapping ---
            # Check both endpoint_name and required_actions for mapping
            route_name = ENDPOINT_TO_ROUTE_MAP.get(endpoint_name)

            # Try required_actions mapping if endpoint_name not found
            if not route_name and required_actions:
                if isinstance(required_actions, str):
                    route_name = ENDPOINT_TO_ROUTE_MAP.get(required_actions)
                elif isinstance(required_actions, (list, tuple)):
                    for action in required_actions:
                        route_name = ENDPOINT_TO_ROUTE_MAP.get(action)
                        if route_name:
                            break

            # Fallback (old logic)
            if not route_name:
                route_name = original_route_name

            # Determine actions to check
            actions = required_actions
            if actions is None and request.method == "POST" and request.is_json:
                # Allow API to send action(s) in payload
                payload_action = json_data.get("action") or json_data.get("actions")
                if payload_action:
                    actions = payload_action

            # Normalize to a list of actions
            if actions is None:
                actions = []
            elif isinstance(actions, str):
                actions = [actions]
            elif isinstance(actions, (list, tuple)):
                actions = list(actions)
            else:
                raise ValueError("required_actions should be a string or list/tuple")

            # DEBUG: Log all mapping decisions
            logging.debug(f"[PERMISSION DEBUG] endpoint: {request.endpoint}, endpoint_name: {endpoint_name}, original_route_name: {original_route_name}, mapped_route_name: {route_name}, required_actions: {actions}")

            has_permission = False
            has_role_permission = False

            if allowed_roles is None and route_name and actions:
                conn = get_db_connection()
                with conn.cursor() as cur:
                    # Get route_id
                    cur.execute("SELECT id FROM routes WHERE route_name = %s", (route_name,))
                    route_row = cur.fetchone()
                    if not route_row:
                        logging.warning(f"Route '{route_name}' not found.")
                        conn.close()
                        return jsonify({"error": f"Route '{route_name}' not found."}), 403
                    route_id = route_row[0]

                    # Get action_ids
                    action_ids = []
                    for action in actions:
                        cur.execute("SELECT id FROM actions WHERE action_name = %s", (action,))
                        row = cur.fetchone()
                        if not row:
                            logging.warning(f"Action '{action}' not found.")
                            continue
                        action_ids.append(row[0])

                    # Query all granted action_ids for this admin/route
                    cur.execute(
                        "SELECT action_id FROM admin_route_actions WHERE admin_id = %s AND route_id = %s",
                        (admin_id, route_id)
                    )
                    granted_action_ids = {row[0] for row in cur.fetchall()}

                    if require == "all":
                        has_permission = all(
                            aid in granted_action_ids for aid in action_ids
                        )
                    else:  # require == "any"
                        has_permission = any(
                            aid in granted_action_ids for aid in action_ids
                        )
                conn.close()
            elif allowed_roles is not None:
                has_role_permission = (role_id in allowed_roles)

            # Deny if not allowed
            if (allowed_roles is not None and not has_role_permission) or (
                allowed_roles is None and not has_permission
            ):
                logging.warning(
                    f"Unauthorized access by admin_id={admin_id}, role_id={role_id}, route={route_name}, actions={actions}, require={require}"
                )
                return jsonify({"error": "Forbidden: Not authorized"}), 403

            # --- Verified Admin Check ---
            if role != 'super_admin':
                try:
                    conn = get_db_connection()
                    with conn.cursor() as cur:
                        cur.execute("SELECT is_verified FROM admins WHERE admin_id = %s", (admin_id,))
                        result = cur.fetchone()
                        if not result:
                            logging.warning(f"Admin ID {admin_id} not found.")
                            return jsonify({"error": "Access denied. Admin not found."}), 403
                        if not result[0]:
                            logging.warning(f"Admin ID {admin_id} is not verified.")
                            return jsonify({"error": "Access denied. Admin not verified."}), 403
                except Exception as e:
                    logging.error(f"Database error in role check: {e}", exc_info=True)
                    return jsonify({"error": "Internal server error"}), 500
                finally:
                    conn.close()

            logging.debug(f"Permission check passed for admin_id={admin_id}, route={route_name}, actions={actions}, require={require}")
            return view_function(admin_id, role, role_id, *args, **kwargs)
        return decorated_function
    return decorator

# How to use the token decorator

# Check if admin has "edit_profile" or "send_message" on dashboard (ANY):

# Python
# @admin_bp.route("/dashboard/some-action", methods=["POST"])
# @token_required_with_roles(required_actions=["edit_profile", "send_message"], require="any")
# def dashboard_action(admin_id, role, role_id):
#     ...


# Check if admin has BOTH "edit_profile" AND "send_message":

# Python
# @admin_bp.route("/dashboard/complex-action", methods=["POST"])
# @token_required_with_roles(required_actions=["edit_profile", "send_message"], require="all")
# def dashboard_action(admin_id, role, role_id):
#     ...


# Role-based only:

# Python
# @admin_bp.route("/admin-only", methods=["POST"])
# @token_required_with_roles(allowed_roles=[1, 2])
# def admin_only(admin_id, role, role_id):
#     ...


# Just JWT and verification only :

# Python
# @admin_bp.route("/admin-only", methods=["POST"])
# @token_required_with_roles()
# def admin_only(admin_id, role, role_id):
#     ...


# function to check for token authentication for logged in admin and permission to routes but use this for route that requires two-authentication
# the same use as @token_required_with_roles() but if u want to check for 2FA for a route then just swap the name like example below
# No checking for 2FA :
# @token_required_with_roles(required_actions=["delete_employee"])
# Check for 2FA:
# token_required_with_roles_and_2fa(required_actions=["delete_employee"])
def token_required_with_roles_and_2fa(allowed_roles=None, required_actions=None, require="any"):
    from routes.Auth.two_authentication import require_2fa_admin
    def decorator(view_function):
        @token_required_with_roles(allowed_roles=allowed_roles, required_actions=required_actions, require=require)
        @require_2fa_admin
        @wraps(view_function)
        def wrapper(*args, **kwargs):
            return view_function(*args, **kwargs)
        return wrapper
    return decorator


# Utility: Fix padding on JWT tokens
def fix_jwt_padding(token):
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]

        # Basic structural check
        parts = token.split('.')
        if len(parts) != 3:
            logging.error(f"[JWT] Invalid token structure: {token}")
            raise Exception("Invalid JWT token format")

        def pad(b64_string):
            return b64_string + '=' * (-len(b64_string) % 4)

        # Decode header and payload with padding
        header = base64.urlsafe_b64decode(pad(parts[0]))
        payload = base64.urlsafe_b64decode(pad(parts[1]))
        signature = parts[2]  # No decoding needed

        # Rebuild and return normalized token
        return f"{base64.urlsafe_b64encode(header).decode().rstrip('=')}." \
               f"{base64.urlsafe_b64encode(payload).decode().rstrip('=')}." \
               f"{signature}"
    except Exception as e:
        logging.exception(f"[JWT] Error fixing padding for token: {token}")
        raise Exception("Invalid JWT token format") from e
  
# Helper function to generate JWT token (Employee)
def generate_token(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.role_id, r.role_name
        FROM employees e
        JOIN roles r ON e.role_id = r.role_id
        WHERE e.employee_id = %s
    """, (user_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if not result:
        raise Exception("User not found")

    role_id, role_name = result
    jti = str(uuid.uuid4())  # Unique token ID

    payload = {
        'user_id': user_id,
        'role_id': role_id,
        'role_name': role_name,
        'jti': jti,
        'exp': datetime.utcnow() + timedelta(hours=8),
        'iat': datetime.utcnow()
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return token, jti, payload['iat']


# Function to generate a JWT token for admin or super admin
def generate_admin_token(admin_id, role, role_id, is_super_admin=False):
    jti = str(uuid.uuid4())  # Unique token ID
    payload = {
        'admin_id':admin_id,
        'jti': jti,
        'role': role,
        'role_id': role_id,
        'exp': datetime.utcnow() + timedelta(days=7),
        'iat': datetime.utcnow(),
        'admin_type': 'super_admin' if is_super_admin else 'admin'
    }

    if is_super_admin:
        payload['super_admin_id'] = admin_id
    else:
        payload['admin_id'] = admin_id

    if role_id:
        payload['role_id'] = role_id

    # Save JTI to database
    conn = get_db_connection()
    cur = conn.cursor()
    if is_super_admin:
        cur.execute("UPDATE super_admins SET jti = %s WHERE super_admin_id = %s", (jti, admin_id))
    else:
        cur.execute("UPDATE admins SET jti = %s WHERE admin_id = %s", (jti, admin_id))
    conn.commit()
    cur.close()
    conn.close()

    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


# Utility: Extract admin_id and role from JWT token
def get_admin_from_token(token=None):
    """
    Extracts admin_id and role from JWT in Authorization header or given token.
    Returns: (admin_id, role, error_reason or None)
    """
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logging.debug("Missing or invalid Authorization header.")
            return None, None, "unauthorized"
        token = auth_header.split("Bearer ")[1].strip()

    try:
        payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        logging.debug(f"Decoded token payload: {payload}")
        
        admin_id = payload.get("admin_id")
        role = payload.get("role")
        jti = payload.get("jti")

        if not admin_id or not role or not jti:
            logging.error("Missing admin_id, role, or jti in payload")
            return None, None, "unauthorized"

        return admin_id, role, None

    except jwt.ExpiredSignatureError:
        logging.warning("Token expired")
        return None, None, "expired"
    except jwt.InvalidTokenError as e:
        logging.warning(f"Invalid token: {str(e)}")
        return None, None, "unauthorized"
    except Exception as e:
        logging.error(f"Unexpected token decoding error: {str(e)}")
        return None, None, "unauthorized"


# Helper function to verify token for employee
def verify_employee_token(token):
    conn = None
    cursor = None
    try:
        # Fix padding for base64 if needed
        token = fix_jwt_padding(token)
        logging.debug(f"Token: {token}")

        # Decode the token (verify_exp=False disables expiration check; use only if needed)
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'], options={"verify_exp": False})

        user_id = payload.get('user_id')
        role_id = payload.get('role_id')

        if not user_id or not role_id:
            raise Exception("Invalid token payload")

        # Query role_name from database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role_name FROM roles WHERE role_id = %s", (role_id,))
        result = cursor.fetchone()

        if not result:
            raise Exception("Role not found")

        return user_id, result[0]  # (employee_id, role_name)

    except jwt.ExpiredSignatureError:
        logging.warning("Token has expired")
        return None, None

    except jwt.InvalidTokenError as e:
        logging.error(f"Invalid JWT: {e}")
        return None, None

    except Exception as e:
        logging.error(f"Error verifying token: {e}", exc_info=True)
        return None, None

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# decorator to check for logged in employee's token
def get_employee_token():
    # 1. Authorization header (for API, fetch, AJAX)
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header.split(' ')[1]
    # 2. Cookie (for browser navigation)
    cookie_token = request.cookies.get('employeeToken') or request.cookies.get('token')
    if cookie_token:
        return cookie_token
    # 3. Classic form POST (for 2FA and similar forms)
    if request.method == "POST":
        form_token = request.form.get('token')
        if form_token:
            return form_token
    return None

def employee_jwt_required(check_jti=True):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            def is_api_request():
                # Adjust this logic as needed for your API route naming conventions
                return (request.path.startswith('/api')
                        or request.is_json
                        or request.headers.get('Accept') == 'application/json'
                        or request.method == 'POST')  # Optional: treat POSTs as API

            token = get_employee_token()
            print(f"[JWT DECORATOR] Token from header/cookie/form: {token}")
            logging.debug(f"[JWT DECORATOR] Token from header/cookie/form: {token}")

            if not token:
                print("[JWT DECORATOR] No token found in header, cookie, or form.")
                logging.debug("[JWT DECORATOR] No token found in header, cookie, or form.")
                if is_api_request():
                    return jsonify({'error': 'Unauthorized', 'debug': 'No token found'}), 401
                return redirect(url_for('login_bp.employeelogin', reason='session_expired'))

            conn = None
            cursor = None
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
                print(f"[JWT DECORATOR] JWT payload: {payload}")
                logging.debug(f"[JWT DECORATOR] JWT payload: {payload}")

                jti = payload.get('jti')
                print(f"[JWT DECORATOR] JTI from payload: {jti}")
                logging.debug(f"[JWT DECORATOR] JTI from payload: {jti}")

                conn = get_db_connection()
                cursor = conn.cursor()

                # Check if token is blacklisted
                cursor.execute("SELECT 1 FROM blacklisted_tokens WHERE jti = %s", (jti,))
                blacklisted = cursor.fetchone()
                print(f"[JWT DECORATOR] Token blacklisted? {blacklisted is not None}")
                logging.debug(f"[JWT DECORATOR] Token blacklisted? {blacklisted is not None}")
                if blacklisted:
                    print("[JWT DECORATOR] Token found in blacklist.")
                    logging.debug("[JWT DECORATOR] Token found in blacklist.")
                    if is_api_request():
                        return jsonify({'error': 'Unauthorized', 'debug': 'Token is blacklisted'}), 401
                    return redirect(url_for('login_bp.employeelogin', reason='session_expired'))

                employee_id = payload.get('employee_id') or payload.get('user_id') or payload.get('sub')
                employee_role = payload.get('role_name')
                role_id = payload.get('role_id')
                print(f"[JWT DECORATOR] employee_id: {employee_id}, employee_role: {employee_role}, role_id: {role_id}")
                logging.debug(f"[JWT DECORATOR] employee_id: {employee_id}, employee_role: {employee_role}, role_id: {role_id}")

                if not employee_id:
                    print("[JWT DECORATOR] Missing employee_id in token payload.")
                    logging.debug("[JWT DECORATOR] Missing employee_id in token payload.")
                    if is_api_request():
                        return jsonify({'error': 'Unauthorized', 'debug': 'Missing employee_id in token'}), 401
                    return redirect(url_for('login_bp.employeelogin', reason='session_expired'))

                if check_jti:
                    cursor.execute("SELECT current_jti FROM employees WHERE employee_id = %s", (employee_id,))
                    result = cursor.fetchone()
                    print(f"[JWT DECORATOR] current_jti from DB: {result[0] if result else None}")
                    logging.debug(f"[JWT DECORATOR] current_jti from DB: {result[0] if result else None}")
                    if result is None or result[0] != jti:
                        print("[JWT DECORATOR] JTI mismatch or user not found in DB.")
                        logging.debug("[JWT DECORATOR] JTI mismatch or user not found in DB.")
                        if is_api_request():
                            return jsonify({'error': 'Unauthorized', 'debug': 'JTI mismatch or not found in DB'}), 401
                        return redirect(url_for('login_bp.employeelogin', reason='session_expired'))

                g.employee_id = employee_id
                g.employee_role = employee_role
                g.role_id = role_id

                print("[JWT DECORATOR] Passed all checks, proceeding with request.")
                logging.debug("[JWT DECORATOR] Passed all checks, proceeding with request.")
                return f(*args, **kwargs)
            except jwt.ExpiredSignatureError:
                print("[JWT DECORATOR] Token expired.")
                logging.debug("[JWT DECORATOR] Token expired.")
                if is_api_request():
                    return jsonify({'error': 'Session expired', 'debug': 'Token expired'}), 401
                return redirect(url_for('login_bp.employeelogin', reason='session_expired'))
            except jwt.InvalidTokenError as e:
                print(f"[JWT DECORATOR] Invalid token: {e}")
                logging.debug(f"[JWT DECORATOR] Invalid token: {e}")
                if is_api_request():
                    return jsonify({'error': 'Invalid token', 'debug': str(e)}), 401
                return redirect(url_for('login_bp.employeelogin', reason='session_expired'))
            except Exception as e:
                print(f"[JWT DECORATOR] Exception: {e}")
                logging.debug(f"[JWT DECORATOR] Exception: {e}")
                if is_api_request():
                    return jsonify({'error': 'Unauthorized', 'debug': str(e)}), 401
                return redirect(url_for('login_bp.employeelogin', reason='session_expired'))
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
        return decorated_function
    return wrapper