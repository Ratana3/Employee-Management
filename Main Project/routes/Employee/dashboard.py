from datetime import datetime, timedelta, timezone
import logging
from flask import g, jsonify, render_template, request, url_for
import jwt
from extensions import csrf
from routes.Auth.token import employee_jwt_required
from routes.Auth.token import verify_employee_token
from routes.Auth.utils import get_db_connection
from . import employee_bp
from routes.Auth.two_authentication import require_employee_2fa
from routes.Auth.audit import log_employee_incident,log_employee_audit

@employee_bp.route('/user')
def user_page_shell():
    return render_template('Employee/home_page.html')  # No auth check here

@employee_bp.route('/employee/recognitions', methods=['GET'])
@employee_jwt_required()
def view_employee_recognitions():
    logging.debug("Received request to view recognitions")
    employee_id = g.employee_id

    if not employee_id:
        logging.warning("Unauthorized access attempt to recognitions")
        # Log incident for unauthorized access
        log_employee_incident(
            employee_id=None,
            description="Unauthorized access attempt to employee recognitions - no employee_id in session",
            severity="High"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    recognition_type_filter = request.args.get('type', '').strip()
    search = request.args.get('search', '').strip()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        base_query = """
            SELECT
                recognition_id, employee_id, recognition_type, reason, date_awarded,
                awarded_by_admin, awarded_by_super_admin
            FROM employee_recognition
            WHERE employee_id = %s
        """
        params = [employee_id]

        # Build filter details for logging
        filter_details = []
        if recognition_type_filter and recognition_type_filter.lower() != 'all':
            base_query += " AND recognition_type = %s"
            params.append(recognition_type_filter)
            filter_details.append(f"type='{recognition_type_filter}'")

        if search:
            base_query += " AND (LOWER(recognition_type) LIKE %s OR LOWER(reason) LIKE %s)"
            params.extend([f"%{search.lower()}%", f"%{search.lower()}%"])
            filter_details.append(f"search='{search}'")

        base_query += " ORDER BY date_awarded DESC"
        cursor.execute(base_query, params)
        recs = cursor.fetchall()

        # Log successful audit trail
        filter_text = f" with filters: {', '.join(filter_details)}" if filter_details else ""
        log_employee_audit(
            employee_id=employee_id,
            action="view_employee_recognitions",
            details=f"Retrieved {len(recs)} employee recognitions{filter_text}"
        )

    except Exception as e:
        logging.error(f"Database error while fetching recognitions: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"Database error while fetching employee recognitions: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cursor.close()
        conn.close()

    results = [{
        'recognition_id': row[0],
        'employee_id': row[1],
        'recognition_type': row[2],
        'reason': row[3],
        'date_awarded': str(row[4]),
        'awarded_by_admin': bool(row[5]),
        'awarded_by_super_admin': bool(row[6])
    } for row in recs]

    logging.info(f"Fetched {len(results)} recognition(s) for employee {employee_id}")
    return jsonify(results), 200

@employee_bp.route('/api/view_only_shift_swap_requests', methods=['GET'])
@employee_jwt_required()
def view_only_shift_swap_requests():
    try:
        employee_id = g.employee_id
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                sr.shift_request_id, sr.sender_id, sr.sender_role, sr.subject, sr.body, sr.is_read, sr.timestamp, sr.is_approved,
                r.role_name as approver_role_name
            FROM shift_request sr
            LEFT JOIN roles r ON sr.approver_role = r.role_id
            ORDER BY sr.timestamp DESC
        """)
        rows = cursor.fetchall()
        
        requests = [
            {
                'shift_request_id': r[0],
                'sender_id': r[1],
                'sender_role': r[2],
                'subject': r[3],
                'body': r[4],
                'is_read': r[5],
                'timestamp': r[6].isoformat() if r[6] else "",
                'is_approved': r[7],
                'approver_role_name': r[8]
            }
            for r in rows
        ]

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="view_shift_swap_requests",
            details=f"Retrieved {len(requests)} shift swap requests"
        )

        cursor.close()
        conn.close()
        return jsonify(requests), 200

    except Exception as e:
        # Log incident for system error
        log_employee_incident(
            employee_id=g.employee_id if hasattr(g, 'employee_id') else None,
            description=f"System error while fetching shift swap requests: {str(e)}",
            severity="High"
        )
        
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        
        return jsonify({'error': 'Internal server error'}), 500

@employee_bp.route('/api/user-info', methods=['GET'])
@employee_jwt_required()
def api_user_info():
    logging.debug("Received request at /api/user-info")

    user_id = g.employee_id
    role = g.employee_role

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT employee_id, first_name, last_name, email, 
                   phone_number, department, date_hired, address1, address2 
            FROM employees WHERE employee_id = %s
        """, (user_id,))
        user = cursor.fetchone()

        if not user:
            # Log incident for user not found
            log_employee_incident(
                employee_id=user_id,
                description=f"Employee ID {user_id} not found in database during user info fetch",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 404

        cursor.execute("""
            SELECT sick_leave, vacation_leave, personal_leave, unpaid_leave
            FROM leave_balances WHERE employee_id = %s
        """, (user_id,))
        leave_data = cursor.fetchone() or (0, 0, 0, 0)

        cursor.execute("""
            select t.team_name,e.team_id
            from employees e 
            join teams t on t.team_id = e.team_id
            where e.employee_id = %s
        """, (user_id,))
        team_data = cursor.fetchone()

        # Log successful audit trail
        log_employee_audit(
            employee_id=user_id,
            action="api_user_info",
            details=f"Retrieved user info for employee: {user[1]} {user[2]} (ID: {user_id})"
        )

    except Exception as e:
        logging.error(f"DB error: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=user_id if 'user_id' in locals() else None,
            description=f"Database error while fetching user info: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cursor.close()
        conn.close()

    # Safe profile picture URL resolution
    try:
        profile_picture_url = url_for('employee_bp.profile_picture', user_id=user_id)
    except Exception as e:
        logging.warning(f"Could not resolve profile picture URL: {e}")
        profile_picture_url = '/static/default_resource.png'
        
        # Log incident for profile picture URL resolution failure
        log_employee_incident(
            employee_id=user_id,
            description=f"Failed to resolve profile picture URL: {str(e)}",
            severity="Low"
        )

    # Safely handle team_data if user is not assigned to a team
    team_name = team_data[0] if team_data else None
    team_id = team_data[1] if team_data else None

    response_data = {
        'user': {
            'employee_id': user[0],
            'first_name': user[1],
            'last_name': user[2],
            'email': user[3],
            'phone_number': user[4],
            'department': user[5],
            'date_hired': user[6].isoformat() if user[6] and hasattr(user[6], 'isoformat') else user[6],
            'address1': user[7],
            'address2': user[8],
            'profile_picture_url': profile_picture_url
        },
        'leave_balances': {
            'sick_leave': leave_data[0],
            'vacation_leave': leave_data[1],
            'personal_leave': leave_data[2],
            'unpaid_leave': leave_data[3]
        },
        'team_data': {
            'team_name': team_name,
            'team_id': team_id
        },
        'employee_role': role
    }

    logging.debug("Returning user info response: %s", response_data)

    return jsonify(response_data)

#route to fetch the roles
@employee_bp.route("/employee/roles", methods=["GET"])
def get_roles():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT role_id, role_name FROM roles")
        rows = cur.fetchall()
        roles = [{"role_id": row[0], "role_name": row[1]} for row in rows]
        
        # Note: This route doesn't require authentication, so we can't log with specific employee_id
        # You might want to add authentication if this contains sensitive role information
        print(f"📋 Roles fetched: {len(roles)} roles returned (unauthenticated request)")
        
        return jsonify(roles)
        
    except Exception as e:
        print(f"Error fetching roles: {e}")
        # Log system incident without employee_id since route is unauthenticated
        log_employee_incident(
            employee_id=None,
            description=f"System error while fetching roles (unauthenticated): {str(e)}",
            severity="Medium"
        )
        return jsonify({"error": "Failed to fetch roles"}), 500
        
    finally:
        cur.close()
        conn.close()

#route for fetching the user who has the specific role
@employee_bp.route("/employee/users/by_role/<int:role_id>", methods=["GET"])
@employee_jwt_required()
def get_users_by_role(role_id):
    try:
        employee_id = g.employee_id
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT admin_id AS user_id , email, 'Admin' AS role_type
            FROM admins WHERE role_id = %s
            UNION
            SELECT super_admin_id AS user_id, email, 'Super Admin' AS role_type
            FROM super_admins WHERE role_id = %s
            UNION
            SELECT employee_id AS user_id, email, 'Employee' AS role_type
            FROM employees WHERE role_id = %s
        """, (role_id, role_id, role_id))
        
        rows = cur.fetchall()
        seen_emails = set()
        users = []
        for row in rows:
            email = row[1]
            if email not in seen_emails:
                users.append({
                    "user_id": row[0],
                    "email": email,
                    "role_type": row[2]
                })
                seen_emails.add(email)
        
        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="get_users_by_role",
            details=f"Retrieved {len(users)} users for role_id {role_id}"
        )
        
        return jsonify(users)
        
    except Exception as e:
        print(f"Error fetching users by role: {e}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=g.employee_id if hasattr(g, 'employee_id') else None,
            description=f"System error while fetching users by role {role_id}: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": "Failed to fetch users"}), 500
        
    finally:
        cur.close()
        conn.close()

@employee_bp.route('/team-average')
@employee_jwt_required()
def team_average():
    logging.debug("[TEAM AVERAGE] Route hit.")
    token = request.headers.get('Authorization')
    logging.debug(f"[TEAM AVERAGE] Authorization header: {token}")
    
    if not token:
        logging.warning("[TEAM AVERAGE] No token provided in Authorization header.")
        log_employee_incident(
            employee_id=None,
            description="Team average access attempted without authorization token",
            severity="Medium"
        )
        return jsonify({'success': False, 'message': 'Unauthorized: Token missing'}), 401

    try:
        employee_id, role = verify_employee_token(token)
        logging.debug(f"[TEAM AVERAGE] Token verified. Employee ID: {employee_id}, Role: {role}")
    except jwt.ExpiredSignatureError:
        logging.warning("[TEAM AVERAGE] Token has expired.")
        log_employee_incident(
            employee_id=None,
            description="Team average access attempted with expired token",
            severity="Medium"
        )
        return jsonify({'success': False, 'message': 'Token has expired'}), 401
    except Exception as e:
        logging.error(f"[TEAM AVERAGE] Error verifying token: {e}", exc_info=True)
        log_employee_incident(
            employee_id=None,
            description=f"Team average access attempted with invalid token: {str(e)}",
            severity="Medium"
        )
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    if not employee_id:
        logging.warning("[TEAM AVERAGE] employee_id after token verification is None or falsy.")
        log_employee_incident(
            employee_id=None,
            description="Team average access with valid token but no employee_id",
            severity="High"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    days_range = request.args.get('range', default=30, type=int)
    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=days_range)
    logging.debug(f"[TEAM AVERAGE] Date range: {start_date} to {end_date}")

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        logging.debug(f"[TEAM AVERAGE] Connected to DB. Fetching team for employee_id {employee_id}.")

        # Get employee's team_id
        cur.execute("SELECT team_id FROM employees WHERE employee_id = %s", (employee_id,))
        result = cur.fetchone()
        logging.debug(f"[TEAM AVERAGE] Team query result: {result}")

        if not result or not result[0]:
            logging.info("[TEAM AVERAGE] No team found for employee.")
            
            # Log audit for no team found
            log_employee_audit(
                employee_id=employee_id,
                action="team_average",
                details=f"Team average requested but employee not assigned to any team (range: {days_range} days)"
            )
            
            return jsonify({
                "team_found": False,
                "message": "Employee is not assigned to any team.",
                "your_hours": 0,
                "team_average_hours": 0
            }), 200

        team_id = result[0]

        # Total hours for this employee
        cur.execute("""
            SELECT COALESCE(SUM(hours_worked + overtime_hours), 0)
            FROM attendance_logs
            WHERE employee_id = %s AND date BETWEEN %s AND %s
        """, (employee_id, start_date, end_date))
        your_hours = cur.fetchone()[0]
        logging.debug(f"[TEAM AVERAGE] Your hours: {your_hours}")

        # Team average hours
        cur.execute("""
            SELECT COALESCE(AVG(total_hours), 0)
            FROM (
                SELECT SUM(hours_worked + overtime_hours) AS total_hours
                FROM attendance_logs al
                JOIN employees e ON al.employee_id = e.employee_id
                WHERE e.team_id = %s AND date BETWEEN %s AND %s
                GROUP BY al.employee_id
            ) AS team_totals
        """, (team_id, start_date, end_date))
        team_average_hours = cur.fetchone()[0]
        logging.debug(f"[TEAM AVERAGE] Team average hours: {team_average_hours}")

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="team_average",
            details=f"Retrieved team average for team_id {team_id}: your hours={round(your_hours, 2)}, team average={round(team_average_hours, 2)} (range: {days_range} days)"
        )

    except Exception as e:
        logging.error(f"[TEAM AVERAGE] DB error: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"Database error while calculating team average: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Database error'}), 500
    finally:
        try:
            if cur:
                cur.close()
            if conn:
                conn.close()
            logging.debug("[TEAM AVERAGE] DB connection closed.")
        except Exception as e:
            logging.warning(f"[TEAM AVERAGE] Error closing DB: {e}")

    response = {
        "team_found": True,
        "message": "Employee team and average found.",
        'your_hours': round(your_hours, 2) if your_hours is not None else 0,
        'team_average_hours': round(team_average_hours, 2) if team_average_hours is not None else 0
    }
    logging.debug(f"[TEAM AVERAGE] Returning response: {response}")

    return jsonify(response), 200

@employee_bp.route('/goals-progress')
@employee_jwt_required()
def goals_progress():
    try:
        print("[goals_progress] Starting route handler...")

        employee_id = g.employee_id
        print(f"[goals_progress] Logged-in employee ID: {employee_id}")

        conn = get_db_connection()
        cur = conn.cursor()

        today = datetime.today()
        start_of_month = today.replace(day=1)
        end_of_month = today.replace(day=28) + timedelta(days=4)
        end_of_month = end_of_month - timedelta(days=end_of_month.day)

        print(f"[goals_progress] Calculated date range: {start_of_month.date()} to {end_of_month.date()}")

        sql = """
            SELECT 
                COALESCE(SUM(hours_worked), 0)
            FROM 
                attendance_logs
            WHERE 
                attendance_verified = true
                AND employee_id = %s
                AND date BETWEEN %s AND %s
        """
        print("[goals_progress] Executing SQL query...")
        cur.execute(sql, (employee_id, start_of_month, end_of_month))

        current_hours = cur.fetchone()[0] or 0
        print(f"[goals_progress] Current verified hours worked this month: {current_hours}")

        goal_target = 170
        result = {
            'goal_name': today.strftime("%B Work Hours"),
            'target_hours': goal_target,
            'current_hours': current_hours
        }

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="goals_progress",
            details=f"Retrieved goals progress for {today.strftime('%B')}: {current_hours}/{goal_target} hours"
        )

        print(f"[goals_progress] Final response: {result}")
        return jsonify(result)

    except Exception as e:
        print(f"[goals_progress] ERROR: {e}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=g.employee_id if hasattr(g, 'employee_id') else None,
            description=f"System error while fetching goals progress: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'An error occurred while fetching goals progress.'}), 500

@employee_bp.route('/work-hours-summary')
def work_hours_summary():
    try:
        print("[work_hours_summary] Starting route handler...")
        
        # Note: This route doesn't have @employee_jwt_required() decorator
        # You might want to add it for security and proper logging
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        days_range = request.args.get('range', default=7, type=int)
        print(f"[work_hours_summary] Requested range: {days_range} days")

        end_date = datetime.today().date()
        start_date = end_date - timedelta(days=days_range)
        print(f"[work_hours_summary] Date range: {start_date} to {end_date}")

        sql = """
            SELECT 
                date,
                SUM(hours_worked) AS total_hours_worked,
                SUM(CASE WHEN is_overtime_approved = true THEN overtime_hours ELSE 0 END) AS total_approved_overtime
            FROM 
                attendance_logs
            WHERE 
                attendance_verified = true
                AND date BETWEEN %(start_date)s AND %(end_date)s
            GROUP BY 
                date
            ORDER BY 
                date ASC;
        """
        print("[work_hours_summary] Executing SQL query...")
        cur.execute(sql, {
            'start_date': start_date,
            'end_date': end_date
        })

        rows = cur.fetchall()
        print(f"[work_hours_summary] Query returned {len(rows)} rows")

        daily_breakdown = []
        total_hours = 0.0

        for row in rows:
            print(f"[work_hours_summary] Processing row: {row}")
            daily_breakdown.append({
                'date': row[0].strftime('%Y-%m-%d'),
                'hours_worked': float(row[1] or 0),
                'overtime_hours': float(row[2] or 0)
            })
            total_hours += float(row[1] or 0) + float(row[2] or 0)

        result = {
            'total_hours': round(total_hours, 2),
            'daily_breakdown': daily_breakdown
        }

        # Log without employee_id since route is unauthenticated
        print(f"📊 Work hours summary accessed (unauthenticated): {days_range} days range, {total_hours} total hours")

        print(f"[work_hours_summary] Final response: {result}")
        return jsonify(result)

    except Exception as e:
        print(f"[work_hours_summary] ERROR: {e}")
        
        # Log incident without employee_id since route is unauthenticated
        log_employee_incident(
            employee_id=None,
            description=f"System error while fetching work hours summary (unauthenticated): {str(e)}",
            severity="Medium"
        )
        
        return jsonify({'error': 'An error occurred while fetching work hours summary.'}), 500

#route for fetching health resource details 
@employee_bp.route('/employee/health_resources', methods=['GET'])
def get_employee_resources():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT resource_id, title, category, description, url, file_path FROM health_wellness_resources")
        rows = cursor.fetchall()

        resources = []
        for row in rows:
            resources.append({
                "resource_id": row[0],
                "title": row[1],
                "category": row[2],
                "description": row[3],
                "url": row[4],
                "file_path": row[5]
            })

        # Log without employee_id since route is unauthenticated
        print(f"🏥 Health resources fetched (unauthenticated): {len(resources)} resources returned")

        return jsonify(resources)

    except Exception as e:
        print(f"Error fetching health resources: {e}")
        
        # Log incident without employee_id since route is unauthenticated
        log_employee_incident(
            employee_id=None,
            description=f"System error while fetching health resources (unauthenticated): {str(e)}",
            severity="Medium"
        )
        
        return jsonify({"error": "Internal Server Error"}), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

#route for requesting shift swap and time off
@employee_bp.route('/send_request', methods=['POST'])
@employee_jwt_required()
@csrf.exempt
def send_request():
    try:
        employee_id = g.employee_id
        employee_role = g.employee_role

        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Shift request attempted without valid employee session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.get_json()
        subject = data.get('subject')
        message = data.get('message')

        if not subject or not message:
            log_employee_incident(
                employee_id=employee_id,
                description="Shift request attempted with missing subject or message",
                severity="Low"
            )
            return jsonify({'error': 'Subject and message are required'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO shift_request (sender_id, sender_role, subject, body, is_read,timestamp)
            VALUES (%s, %s, %s, %s,'false',NOW())
        """, (employee_id, employee_role, subject, message))
        conn.commit()

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="send_shift_request",
            details=f"Successfully submitted shift request with subject: '{subject}'"
        )

        cursor.close()
        conn.close()
        return jsonify({'message': 'Request sent successfully'}), 200

    except Exception as e:
        print(f"Error inserting request: {e}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=g.employee_id if hasattr(g, 'employee_id') else None,
            description=f"System error while sending shift request: {str(e)}",
            severity="High"
        )
        
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': 'Internal server error'}), 500

@employee_bp.route('/attendance_logs', methods=['GET'])
@employee_jwt_required()
def view_attendance_logs():
    logging.debug("Received request to view attendance logs")
    employee_id = g.employee_id

    if not employee_id:
        logging.warning("Unauthorized access attempt to attendance logs")
        log_employee_incident(
            employee_id=None,
            description="Unauthorized access attempt to attendance logs - no employee_id in session",
            severity="High"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    date_filter = request.args.get('date', '').strip()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch all attendance logs for the employee (optionally filter by date)
        base_query = """
            SELECT 
                log_id, date, clock_in_time, clock_out_time, status, hours_worked, 
                attendance_verified, is_overtime_approved
            FROM attendance_logs
            WHERE employee_id = %s
        """
        params = [employee_id]

        filter_details = []
        if date_filter:
            # Match partial dates like '2024', '05', or '2024-05'
            base_query += " AND TO_CHAR(date, 'YYYY-MM-DD') LIKE %s"
            params.append(f"%{date_filter}%")
            filter_details.append(f"date='{date_filter}'")

        base_query += " ORDER BY date DESC"
        cursor.execute(base_query, params)
        attendance_records = cursor.fetchall()

        # For all log_ids, fetch breaks in a single query
        log_ids = [row[0] for row in attendance_records]
        breaks_by_log = {}
        if log_ids:
            format_strings = ','.join(['%s'] * len(log_ids))
            cursor.execute(f"""
                SELECT log_id, break_id, break_type, break_start, break_end, break_duration, status
                FROM employee_breaks
                WHERE log_id IN ({format_strings})
                ORDER BY break_start
            """, tuple(log_ids))
            breaks = cursor.fetchall()
            for br in breaks:
                log_id = br[0]
                break_info = {
                    'break_id': br[1],
                    'break_type': br[2],
                    'break_start': str(br[3]) if br[3] else None,
                    'break_end': str(br[4]) if br[4] else None,
                    'break_duration': br[5].total_seconds() if br[5] is not None else None,
                    'break_status': br[6]
                }
                breaks_by_log.setdefault(log_id, []).append(break_info)

        # Log successful audit trail
        filter_text = f" with filters: {', '.join(filter_details)}" if filter_details else ""
        log_employee_audit(
            employee_id=employee_id,
            action="view_attendance_logs",
            details=f"Retrieved {len(attendance_records)} attendance logs{filter_text}"
        )

    except Exception as e:
        logging.error(f"Database error while fetching attendance logs: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"Database error while fetching attendance logs: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cursor.close()
        conn.close()

    logging.info(f"Fetched {len(attendance_records)} attendance record(s) for employee {employee_id}")

    results = []
    for row in attendance_records:
        log_id = row[0]
        results.append({
            'date': str(row[1]),
            'clock_in_time': str(row[2]) if row[2] else None,
            'clock_out_time': str(row[3]) if row[3] else None,
            'status': row[4],
            'hours_worked': float(row[5]) if row[5] else 0.0,
            'verified': 'Yes' if row[6] else 'No',
            'overtime_status': 'Verified' if row[7] else 'Rejected',
            # List all breaks for this log
            'breaks': breaks_by_log.get(log_id, [])
        })

    return jsonify(results), 200

@employee_bp.route('/leave_requests', methods=['GET'])
@employee_jwt_required()
def view_leave_requests():
    logging.debug("Received request to view leave history")

    employee_id = g.employee_id

    if not employee_id:
        logging.warning("Unauthorized access attempt to leave requests - no valid employee ID")
        log_employee_incident(
            employee_id=None,
            description="Unauthorized access attempt to leave requests - no employee_id in session",
            severity="High"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        logging.debug("Database connection established")

        # Deactivate expired leave requests
        update_query = """
            UPDATE leave_requests
            SET status = 'inactive'
            WHERE employee_id = %s
            AND end_date < CURRENT_DATE
            AND status != 'inactive'
        """
        logging.debug("Updating expired leave requests to 'inactive'")
        cursor.execute(update_query, (employee_id,))
        expired_count = cursor.rowcount
        conn.commit()

        # Fetch leave request history
        query = """
            SELECT start_date, end_date, leave_type, status, verification_status, remarks
            FROM leave_requests
            WHERE employee_id = %s
            ORDER BY start_date DESC
        """
        logging.debug(f"Executing query: {query.strip()} with employee_id={employee_id}")
        cursor.execute(query, (employee_id,))
        leave_requests = cursor.fetchall()
        logging.debug(f"Query returned {len(leave_requests)} row(s)")

        # Log successful audit trail
        audit_details = f"Retrieved {len(leave_requests)} leave requests"
        if expired_count > 0:
            audit_details += f", updated {expired_count} expired requests to inactive"
        
        log_employee_audit(
            employee_id=employee_id,
            action="view_leave_requests",
            details=audit_details
        )

    except Exception as e:
        logging.error(f"Database error while fetching leave history: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"Database error while fetching leave requests: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cursor.close()
        conn.close()
        logging.debug("Database connection closed")

    results = [{
        'start_date': str(row[0]),
        'end_date': str(row[1]),
        'leave_type': row[2],
        'status': row[3],
        'verified': 'Yes' if row[4] else 'No',
        'remarks': row[5]
    } for row in leave_requests]

    logging.debug(f"Formatted response data: {results}")
    logging.info(f"Fetched {len(leave_requests)} leave request(s) for employee {employee_id}")
    return jsonify(results), 200

@employee_bp.route('/employee-shift', methods=['GET'])
@employee_jwt_required()
def get_employee_shift():
    logging.debug("[EMPLOYEE SHIFT] Route hit.")
    token = request.headers.get('Authorization')
    logging.debug(f"[EMPLOYEE SHIFT] Authorization header: {token}")
    
    if not token:
        logging.warning("[EMPLOYEE SHIFT] No token provided in Authorization header.")
        log_employee_incident(
            employee_id=None,
            description="Employee shift access attempted without authorization token",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized: Token missing'}), 401

    try:
        employee_id, role = verify_employee_token(token)
        logging.debug(f"[EMPLOYEE SHIFT] Token verified. Employee ID: {employee_id}, Role: {role}")
    except jwt.ExpiredSignatureError:
        logging.warning("[EMPLOYEE SHIFT] Token has expired.")
        log_employee_incident(
            employee_id=None,
            description="Employee shift access attempted with expired token",
            severity="Medium"
        )
        return jsonify({'error': 'Token has expired'}), 401
    except Exception as e:
        logging.error(f"[EMPLOYEE SHIFT] Error verifying token: {e}", exc_info=True)
        log_employee_incident(
            employee_id=None,
            description=f"Employee shift access attempted with invalid token: {str(e)}",
            severity="Medium"
        )
        return jsonify({'error': 'Invalid token'}), 401

    if not employee_id:
        logging.warning("[EMPLOYEE SHIFT] employee_id after token verification is None or falsy.")
        log_employee_incident(
            employee_id=None,
            description="Employee shift access with valid token but no employee_id",
            severity="High"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        logging.debug(f"[EMPLOYEE SHIFT] Connected to DB. Querying shift for employee_id {employee_id}.")

        cursor.execute("""
            SELECT s.shift_name, s.start_time, s.end_time, es.shift_date, es.location
            FROM employee_shifts es
            JOIN shifts s ON es.shift_id = s.shift_id
            WHERE es.employee_id = %s
            ORDER BY es.shift_date DESC
            LIMIT 1
        """, (employee_id,))
        shift = cursor.fetchone()
        logging.debug(f"[EMPLOYEE SHIFT] Query result: {shift}")

        if not shift:
            logging.info("[EMPLOYEE SHIFT] No shift assigned to employee.")
            
            # Log audit for no shift found
            log_employee_audit(
                employee_id=employee_id,
                action="get_employee_shift",
                details="Employee shift requested but no shift assigned"
            )
            
            return jsonify({
                "shift_assigned": False,
                "message": "Employee has no shift assigned.",
                "shift_details": None
            }), 200

        shift_name, start_time, end_time, shift_date, location = shift
        logging.debug(f"[EMPLOYEE SHIFT] Parsed shift: {shift_name}, {start_time}, {end_time}, {shift_date}, {location}")

        shift_details = {
            "shift_name": shift_name,
            "shift_time": f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}" if start_time and end_time else "N/A",
            "shift_date": shift_date.strftime('%B %d, %Y') if shift_date else "N/A",
            "location": location
        }

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="get_employee_shift",
            details=f"Retrieved shift details: {shift_name} on {shift_date} at {location}"
        )

        logging.debug(f"[EMPLOYEE SHIFT] Returning shift details: {shift_details}")
        return jsonify({
            "shift_assigned": True,
            "message": "Employee shift details found.",
            "shift_details": shift_details
        }), 200

    except Exception as e:
        logging.error(f"[EMPLOYEE SHIFT] DB error: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id if 'employee_id' in locals() else None,
            description=f"Database error while fetching employee shift: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Database error'}), 500
    finally:
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
            logging.debug("[EMPLOYEE SHIFT] DB connection closed.")
        except Exception as e:
            logging.warning(f"[EMPLOYEE SHIFT] Error closing DB: {e}")

@employee_bp.route('/clock_in', methods=['POST'])
@employee_jwt_required()
@csrf.exempt
def clock_in():
    try:
        employee_id = getattr(g, 'employee_id', None)
        role_id = getattr(g, 'role_id', None)
        logging.debug("Received clock-in request.")
        logging.debug(f"Employee ID from JWT: {employee_id}, Role ID: {role_id}")

        if not employee_id:
            logging.warning('Unauthorized clock-in attempt: No employee_id in g')
            log_employee_incident(
                employee_id=None,
                description="Unauthorized clock-in attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        if not role_id:
            logging.warning("Role ID missing.")
            log_employee_incident(
                employee_id=employee_id,
                description="Clock-in attempted with missing role_id",
                severity="Medium"
            )
            return jsonify({'error': 'Role ID missing'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc)
        today = now.date()

        # Fetch any attendance log for today
        cursor.execute("SELECT * FROM attendance_logs WHERE employee_id = %s AND date = %s", (employee_id, today))
        log = cursor.fetchone()
        logging.debug(f"Existing log: {log}")

        # If log exists and it's not a leave log and has clock_in_time, block clock-in
        if log and log[3] is not None:
            logging.info(f"Employee {employee_id} has already clocked in today.")
            log_employee_incident(
                employee_id=employee_id,
                description="Employee attempted to clock in multiple times in the same day",
                severity="Low"
            )
            return jsonify({'message': 'Already clocked in today.'}), 400

        # If log exists and status is On Leave, update the leave log to a work log (clock in)
        if log and log[5] == 'On Leave':
            cursor.execute("""
                UPDATE attendance_logs 
                SET clock_in_time = %s, status = %s, leave_type = NULL
                WHERE log_id = %s
            """, (now.timetz(), "Present", log[0]))
            logging.info(f"Employee {employee_id} is clocking in after being marked as On Leave. Leave log updated.")
            
            # Log successful audit trail for leave override
            log_employee_audit(
                employee_id=employee_id,
                action="clock_in_override_leave",
                details=f"Successfully clocked in and overrode leave status at {now.strftime('%H:%M:%S UTC')}"
            )
        else:
            # No log for today or not a leave log; insert new work log
            cursor.execute("""
                INSERT INTO attendance_logs (employee_id, date, clock_in_time, status, role_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (employee_id, today, now.timetz(), "Present", role_id))
            logging.info(f"Employee {employee_id} clocked in successfully.")
            
            # Log successful audit trail for normal clock-in
            log_employee_audit(
                employee_id=employee_id,
                action="clock_in",
                details=f"Successfully clocked in at {now.strftime('%H:%M:%S UTC')} on {today}"
            )

        conn.commit()
        return jsonify({'message': 'Clock-in successful.'}), 200

    except Exception as e:
        logging.exception(f'Unhandled exception during clock-in: {e}')
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during clock-in: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception as e:
            logging.error(f'Failed to close cursor: {e}')
        try:
            if conn:
                conn.close()
        except Exception as e:
            logging.error(f'Failed to close connection: {e}')

@employee_bp.route('/clock_out', methods=['POST'])
@employee_jwt_required()
@csrf.exempt
def clock_out():
    """Logs the clock-out time and marks an employee as absent if they worked less than 4 hours."""
    try:
        employee_id = getattr(g, 'employee_id', None)
        role_id = getattr(g, 'role_id', None)
        logging.debug(f"[CLOCK_OUT] Employee ID from JWT: {employee_id}, Role ID: {role_id}")

        if not employee_id:
            logging.warning('[CLOCK_OUT] Unauthorized clock-out attempt: No employee_id in g')
            log_employee_incident(
                employee_id=None,
                description="Unauthorized clock-out attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        if not role_id:
            logging.warning("[CLOCK_OUT] Role ID missing.")
            log_employee_incident(
                employee_id=employee_id,
                description="Clock-out attempted with missing role_id",
                severity="Medium"
            )
            return jsonify({'error': 'Role ID missing'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get aware datetime in UTC
        now = datetime.now(timezone.utc)
        today = now.date()
        shift_end_time = datetime.combine(today, datetime.strptime("17:00:00", "%H:%M:%S").time()).replace(tzinfo=timezone.utc)

        logging.debug(f'[CLOCK_OUT] Current time: {now}, Shift end time: {shift_end_time}')

        # Check if employee has a clock-in record for today
        cursor.execute(
            "SELECT log_id, clock_in_time, clock_out_time FROM attendance_logs WHERE employee_id = %s AND date = %s",
            (employee_id, today)
        )
        log = cursor.fetchone()
        logging.debug(f'[CLOCK_OUT] Attendance log result: {log}')

        if not log:
            logging.warning(f'[CLOCK_OUT] Employee {employee_id} attempted to clock out without clocking in')
            log_employee_incident(
                employee_id=employee_id,
                description="Employee attempted to clock out without clocking in first",
                severity="Medium"
            )
            return jsonify({'error': 'You need to clock in first'}), 400

        log_id, clock_in_time, clock_out_time = log
        logging.debug(f'[CLOCK_OUT] log_id: {log_id}, clock_in_time: {clock_in_time}, previous clock_out_time: {clock_out_time}')

        # Check if clock_in_time is None
        if clock_in_time is None:
            logging.warning(f'[CLOCK_OUT] Employee {employee_id} has no clock-in time recorded for today')
            log_employee_incident(
                employee_id=employee_id,
                description="Employee attempted to clock out with no clock-in time recorded",
                severity="Medium"
            )
            return jsonify({'error': 'Clock in time missing. Please clock in first.'}), 400

        # Prevent multiple clock outs
        if clock_out_time is not None:
            logging.info(f'[CLOCK_OUT] Employee {employee_id} has already clocked out today')
            log_employee_incident(
                employee_id=employee_id,
                description="Employee attempted to clock out multiple times in the same day",
                severity="Low"
            )
            return jsonify({'message': 'You have already clocked out today'}), 400

        try:
            # clock_in_time is a time with tz; combine with today's date and use its tzinfo
            clock_in_datetime = datetime.combine(today, clock_in_time)
            if hasattr(clock_in_time, "tzinfo") and clock_in_time.tzinfo is not None:
                # Convert both to UTC for accurate difference
                clock_in_datetime = clock_in_datetime.astimezone(timezone.utc)
            hours_worked = (now - clock_in_datetime).total_seconds() / 3600
        except Exception as e:
            logging.error(f'[CLOCK_OUT] Error calculating hours_worked: {e}')
            log_employee_incident(
                employee_id=employee_id,
                description=f"Error calculating hours worked during clock-out: {str(e)}",
                severity="High"
            )
            return jsonify({'error': 'Internal error calculating hours worked.'}), 500

        is_overtime = "Yes" if hours_worked > 8 else "No"
        overtime_hours = max(0, hours_worked - 8)

        logging.debug(f'[CLOCK_OUT] Hours worked: {hours_worked}, Overtime: {is_overtime}, Overtime hours: {overtime_hours}')

        if hours_worked < 4:
            status = "Absent"
            remarks = "Insufficient Work Hours"
        else:
            status = "Present"
            remarks = "Early Leave" if now < shift_end_time else ""

        logging.debug(f'[CLOCK_OUT] Updating attendance_logs with status={status}, remarks={remarks}')
        cursor.execute("""
            UPDATE attendance_logs
            SET clock_out_time = %s, hours_worked = %s, is_overtime = %s, overtime_hours = %s, status = %s, remarks = %s, role_id = %s
            WHERE log_id = %s
        """, (now.timetz(), hours_worked, is_overtime, overtime_hours, status, remarks, role_id, log_id))

        conn.commit()
        logging.info(f'[CLOCK_OUT] Clock-out successful for Employee {employee_id}. Status: {status}, Overtime: {is_overtime}')

        # Log successful audit trail
        audit_details = f"Successfully clocked out at {now.strftime('%H:%M:%S UTC')}: {hours_worked:.2f} hours worked"
        if status == "Absent":
            audit_details += " (marked absent due to insufficient hours)"
        elif overtime_hours > 0:
            audit_details += f" with {overtime_hours:.2f} overtime hours"
        if remarks:
            audit_details += f", remarks: {remarks}"
            
        log_employee_audit(
            employee_id=employee_id,
            action="clock_out",
            details=audit_details
        )

        return jsonify({
            'message': f'Clock-out successful. Status: {status}. Overtime: {is_overtime}',
            'clock_out_time': str(now.timetz()),
            'hours_worked': hours_worked,
            'overtime': is_overtime
        }), 200

    except Exception as e:
        logging.exception(f'[CLOCK_OUT] Unhandled exception: {e}')
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during clock-out: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception as e:
            logging.error(f'[CLOCK_OUT] Failed to close cursor: {e}')
        try:
            if conn:
                conn.close()
        except Exception as e:
            logging.error(f'[CLOCK_OUT] Failed to close connection: {e}')

@employee_bp.route('/break', methods=['POST'])
@employee_jwt_required()
@csrf.exempt
def handle_break():
    from datetime import datetime, timezone
    import sys
    import traceback

    try:
        print("DEBUG: Entered /break endpoint", flush=True)
        employee_id = getattr(g, 'employee_id', None)
        role_id = getattr(g, 'role_id', None)
        data = request.get_json()
        print(f"DEBUG: employee_id={employee_id}, role_id={role_id}, data={data}", flush=True)
        action = data.get("action")
        break_type = data.get("break_type")

        if not employee_id:
            print("DEBUG: Unauthorized access (no employee_id)", flush=True)
            log_employee_incident(
                employee_id=None,
                description="Unauthorized break action attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized. Please log in to continue.'}), 401

        allowed_types = {"lunch", "short", "personal", "other"}
        if action == "start":
            if not break_type or break_type not in allowed_types:
                print(f"DEBUG: Invalid break_type: {break_type}", flush=True)
                log_employee_incident(
                    employee_id=employee_id,
                    description=f"Employee attempted to start break with invalid type: '{break_type}'",
                    severity="Low"
                )
                return jsonify({'error': f"Invalid break type selected. Please choose one of: {', '.join(allowed_types)}."}), 400

        now = datetime.now(timezone.utc)
        print(f"DEBUG: Current datetime (UTC): {now}", flush=True)
        conn = get_db_connection()
        cursor = conn.cursor()

        # Find today's attendance log for this employee
        today = now.date()
        print(f"DEBUG: Looking up attendance log for employee_id={employee_id} on {today}", flush=True)
        cursor.execute("SELECT log_id, clock_out_time FROM attendance_logs WHERE employee_id = %s AND date = %s", (employee_id, today))
        log_row = cursor.fetchone()
        print(f"DEBUG: attendance_logs row: {log_row}", flush=True)
        
        if not log_row:
            print("DEBUG: No attendance log found for today", flush=True)
            log_employee_incident(
                employee_id=employee_id,
                description="Employee attempted break action without clocking in first",
                severity="Medium"
            )
            return jsonify({'error': 'You must clock in before taking a break.'}), 400
            
        log_id, clock_out_time = log_row

        # Prevent break actions if already clocked out
        if clock_out_time is not None:
            print("DEBUG: Break not allowed, already clocked out.", flush=True)
            log_employee_incident(
                employee_id=employee_id,
                description="Employee attempted break action after already clocking out",
                severity="Medium"
            )
            return jsonify({'error': 'You cannot take a break after you have clocked out.'}), 400

        if action == "start":
            print(f"DEBUG: Checking for ongoing break for employee_id={employee_id}, log_id={log_id}", flush=True)
            cursor.execute("""
                SELECT break_id FROM employee_breaks 
                WHERE employee_id = %s AND log_id = %s AND status = 'ongoing'
            """, (employee_id, log_id))
            existing_break = cursor.fetchone()
            print(f"DEBUG: existing ongoing break: {existing_break}", flush=True)
            
            if existing_break:
                log_employee_incident(
                    employee_id=employee_id,
                    description="Employee attempted to start new break while already on break",
                    severity="Low"
                )
                return jsonify({'error': 'You are already on a break. Please end your current break before starting a new one.'}), 400

            print(f"DEBUG: Inserting new break: {break_type} for employee_id={employee_id}, log_id={log_id}", flush=True)
            cursor.execute("""
                INSERT INTO employee_breaks (employee_id, log_id, break_type, break_start, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING break_id
            """, (employee_id, log_id, break_type, now, 'ongoing', now))
            break_id = cursor.fetchone()[0]
            print(f"DEBUG: New break_id: {break_id}", flush=True)

            conn.commit()
            print(f"DEBUG: Break started and committed.", flush=True)
            
            # Log successful audit trail for break start
            log_employee_audit(
                employee_id=employee_id,
                action="start_break",
                details=f"Started {break_type} break at {now.strftime('%H:%M:%S UTC')} (break_id: {break_id})"
            )
            
            return jsonify({'message': 'Break started.', 'break_id': break_id, 'break_start': now.isoformat()}), 200

        elif action == "end":
            print(f"DEBUG: Finding ongoing break to end for employee_id={employee_id}, log_id={log_id}", flush=True)
            cursor.execute("""
                SELECT break_id, break_start, break_type FROM employee_breaks 
                WHERE employee_id = %s AND log_id = %s AND status = 'ongoing'
                ORDER BY break_start DESC LIMIT 1
            """, (employee_id, log_id))
            row = cursor.fetchone()
            print(f"DEBUG: Ongoing break row: {row}", flush=True)
            
            if not row:
                print("DEBUG: No ongoing break found to end.", flush=True)
                log_employee_incident(
                    employee_id=employee_id,
                    description="Employee attempted to end break but no ongoing break found",
                    severity="Low"
                )
                return jsonify({'error': 'No ongoing break found to end.'}), 400
                
            break_id, break_start, break_type = row
            break_end = now

            # Ensure break_start is timezone-aware (assume UTC if naive)
            if break_start.tzinfo is None:
                break_start = break_start.replace(tzinfo=timezone.utc)

            break_duration_seconds = (break_end - break_start).total_seconds()
            break_duration_minutes = break_duration_seconds / 60

            print(f"DEBUG: Ending break_id={break_id}, started at={break_start}, break_end={break_end}, duration={break_end - break_start}", flush=True)

            cursor.execute("""
                UPDATE employee_breaks
                SET break_end = %s, status = 'completed'
                WHERE break_id = %s
            """, (break_end, break_id))

            conn.commit()
            print(f"DEBUG: Break ended and committed.", flush=True)

            # Log successful audit trail for break end
            log_employee_audit(
                employee_id=employee_id,
                action="end_break",
                details=f"Ended {break_type} break at {now.strftime('%H:%M:%S UTC')}: {break_duration_minutes:.1f} minutes duration (break_id: {break_id})"
            )

            return jsonify({
                'message': 'Break ended.',
                'break_id': break_id,
                'break_end': break_end.isoformat(),
                'break_duration_seconds': break_duration_seconds
            }), 200
        else:
            print(f"DEBUG: Invalid action: {action}", flush=True)
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted break action with invalid action: '{action}'",
                severity="Low"
            )
            return jsonify({'error': 'Invalid action requested. Please use "start" or "end".'}), 400

    except Exception as e:
        print("DEBUG: Exception occurred:", file=sys.stderr, flush=True)
        traceback.print_exc()
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during break action: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'We are experiencing technical difficulties. Please try again later.'}), 500
    finally:
        try:
            if cursor: cursor.close()
        except Exception:
            pass
        try:
            if conn: conn.close()
        except Exception:
            pass

@employee_bp.route('/mark_leave', methods=['POST'])
@employee_jwt_required()
@require_employee_2fa
@csrf.exempt
def mark_leave():
    try:
        employee_id = g.employee_id
        role_id = getattr(g, 'role_id', None)
        logging.debug(f"Employee ID from JWT: {employee_id}, Role ID: {role_id}")

        if not employee_id:
            logging.warning("Unauthorized access attempt")
            log_employee_incident(
                employee_id=None,
                description="Unauthorized leave marking attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        if not role_id:
            logging.warning("Role ID missing in mark_leave")
            log_employee_incident(
                employee_id=employee_id,
                description="Leave marking attempted with missing role_id",
                severity="Medium"
            )
            return jsonify({'error': 'Role ID missing'}), 400

        data = request.get_json()
        logging.debug(f"Request data: {data}")
        leave_type = data.get('leave_type')
        number_of_days = data.get('number_of_days') or data.get('leave_days')

        # Validate input
        if not leave_type:
            logging.error("Leave type missing from request")
            log_employee_incident(
                employee_id=employee_id,
                description="Leave marking attempted without specifying leave type",
                severity="Low"
            )
            return jsonify({'error': 'Leave type is required'}), 400

        try:
            number_of_days = int(number_of_days)
            if number_of_days <= 0:
                raise ValueError
        except (TypeError, ValueError):
            logging.error("Invalid number of days provided")
            log_employee_incident(
                employee_id=employee_id,
                description=f"Leave marking attempted with invalid number of days: '{number_of_days}'",
                severity="Low"
            )
            return jsonify({'error': 'Please provide a valid number of leave days'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        today = datetime.now().date()
        logging.debug(f"Checking attendance for employee {employee_id} on {today}")

        # Check if attendance already exists for today
        cursor.execute(
            "SELECT * FROM attendance_logs WHERE employee_id = %s AND date = %s",
            (employee_id, today)
        )
        existing_log = cursor.fetchone()

        if existing_log:
            logging.info("Attendance record already exists for today")
            log_employee_incident(
                employee_id=employee_id,
                description="Employee attempted to mark leave but attendance record already exists for today",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'You already have an attendance record today'}), 400

        leave_column_map = {
            "Sick Leave": "sick_leave",
            "Vacation Leave": "vacation_leave",
            "Personal Leave": "personal_leave",
            "Unpaid Leave": "unpaid_leave"
        }

        if leave_type not in leave_column_map:
            logging.error("Invalid leave type provided")
            log_employee_incident(
                employee_id=employee_id,
                description=f"Leave marking attempted with invalid leave type: '{leave_type}'",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Invalid leave type'}), 400

        leave_column = leave_column_map[leave_type]
        logging.debug(f"Checking leave balance for {leave_column}")

        cursor.execute(f"SELECT {leave_column} FROM leave_balances WHERE employee_id = %s", (employee_id,))
        balance = cursor.fetchone()

        if not balance:
            logging.error("Leave balance not found for employee")
            log_employee_incident(
                employee_id=employee_id,
                description="Leave marking attempted but no leave balance record found for employee",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Leave balance not found'}), 400

        remaining_leave = balance[0]
        logging.debug(f"Remaining {leave_type}: {remaining_leave}")

        if leave_type != "Unpaid Leave" and remaining_leave < number_of_days:
            logging.warning(f"Not enough {leave_type} days left")
            log_employee_incident(
                employee_id=employee_id,
                description=f"Leave marking attempted with insufficient balance: requested {number_of_days} {leave_type} days but only {remaining_leave} available",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': f'Not enough {leave_type} days left. You only have {remaining_leave} days.'}), 400

        # Insert attendance log for today (add role_id)
        logging.debug("Inserting leave record into attendance_logs")
        cursor.execute("""
            INSERT INTO attendance_logs (employee_id, role_id, date, status, leave_type, attendance_verified)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (employee_id, role_id, today, "On Leave", leave_type, False))

        # Insert leave request
        end_date = today + timedelta(days=number_of_days - 1)
        logging.debug("Inserting record into leave_requests")
        cursor.execute("""
            INSERT INTO leave_requests (
                employee_id, leave_type, start_date, end_date,
                total_days, status, remarks, verification_status, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING request_id
        """, (
            employee_id, leave_type,
            today, end_date, number_of_days,
            'inactive', 'Wait for approval!',
            'False'
        ))

        # Get the request_id for logging
        request_id = cursor.fetchone()[0] if cursor.rowcount > 0 else None

        conn.commit()

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="mark_leave",
            details=f"Successfully submitted {leave_type} request for {number_of_days} days from {today} to {end_date} (request_id: {request_id}), remaining balance: {remaining_leave} days"
        )

        cursor.close()
        conn.close()
        logging.info(f"Leave marked and request logged for {leave_type} ({number_of_days} days) for employee {employee_id}")

        return jsonify({'message': f'Leave request for {leave_type} ({number_of_days} day(s)) has been submitted and is pending approval.'}), 200

    except Exception as e:
        logging.exception(f"Unhandled exception during mark_leave: {e}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during leave marking: {str(e)}",
            severity="High"
        )
        
        # Clean up database connections
        if 'cursor' in locals():
            try:
                cursor.close()
            except Exception:
                pass
        if 'conn' in locals():
            try:
                conn.close()
            except Exception:
                pass
        
        return jsonify({'error': 'Internal server error occurred while processing leave request'}), 500