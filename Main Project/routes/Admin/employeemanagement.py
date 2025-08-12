import base64
from datetime import date, datetime, timedelta
import logging
import os
import traceback
import bcrypt
from flask import Blueprint, Response, flash, redirect, render_template, jsonify, request, send_file, url_for
import psycopg2
from routes.Auth.audit import log_audit, log_incident
from routes.Auth.token import token_required_with_roles, token_required_with_roles_and_2fa
from routes.Auth.utils import get_db_connection
from . import admin_bp
from extensions import csrf
from PIL import Image
import io
from psycopg2.errors import UniqueViolation
from werkzeug.security import check_password_hash,generate_password_hash


# route for rendering employee management page
@admin_bp.route('/employeemanagement', methods=['GET'])
def employeemanagement_page():
    # Just serve the HTML shell; no data fetching here
    return render_template('Admin/EmployeeManagement.html')

# route for rendering employee management API (NO PASSWORD, JOIN TEAMS)
@admin_bp.route('/employeemanagement_data', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["employeemanagement_data"])
def employeemanagement_data(admin_id, role, role_id):
    import base64
    import psycopg2
    import traceback

    connection = None
    try:
        print(f"[DEBUG] employeemanagement_data called by admin_id={admin_id}, role={role}, role_id={role_id}")
        connection = get_db_connection()
        cursor = connection.cursor()

        search_query = request.args.get('query', '').strip()
        print(f"[DEBUG] Search query: '{search_query}'")

        base_query = """
    SELECT 
        e.employee_id, e.first_name, e.last_name, e.email, e.phone_number, e.department, e.salary, e.status, 
        e.date_hired, e.date_terminated, e.profile, e.created, e.account_status, 
        e.address1, e.city, e.address2, 
        e.education, t.team_name, e.skills, e.certification, 
        e.language, e.hobbies, e.date_of_birth, e.gender, r.role_name,
        s.shift_name, s.start_time, s.end_time, s.is_rotating, s.location,
        e.team_id, e.role_id  -- <<-- ADD THESE
    FROM employees e
    LEFT JOIN teams t ON t.team_id = e.team_id
    LEFT JOIN roles r ON r.role_id = e.role_id
    LEFT JOIN (
        SELECT DISTINCT ON (es.employee_id)
            es.employee_id, es.shift_id, sh.shift_name, sh.start_time, sh.end_time, 
            es.is_rotating, es.location
        FROM employee_shifts es
        JOIN shifts sh ON sh.shift_id = es.shift_id
        ORDER BY es.employee_id, es.shift_date DESC
    ) s ON s.employee_id = e.employee_id
"""

        if search_query:
            if search_query.isdigit():
                query = base_query + " WHERE e.employee_id = %s OR e.phone_number = %s"
                print(f"[DEBUG] Executing SQL for digit query: {query} with params: ({int(search_query)}, {search_query})")
                cursor.execute(query, (int(search_query), search_query))
            else:
                query = base_query + """
                    WHERE 
                        e.first_name ILIKE %s OR 
                        e.last_name ILIKE %s OR 
                        e.email ILIKE %s OR 
                        e.department ILIKE %s
                """
                params = tuple(f"%{search_query}%" for _ in range(4))
                print(f"[DEBUG] Executing SQL for text query: {query} with params: {params}")
                cursor.execute(query, params)
        else:
            print(f"[DEBUG] Executing SQL for all employees: {base_query}")
            cursor.execute(base_query)

        total_employees = cursor.fetchall()
        print(f"[DEBUG] Number of employees fetched: {len(total_employees)}")

        employees_with_images = []
        for idx, emp in enumerate(total_employees):
            print(f"[DEBUG] Processing employee #{idx+1} (employee_id={emp[0]})")
            profile_image = emp[10]
            profile_image_base64 = (
                f"data:image/jpeg;base64,{base64.b64encode(profile_image).decode('utf-8')}"
                if profile_image else None
            )
            employee_data = {
                "employee_id": emp[0],
                "first_name": emp[1],
                "last_name": emp[2],
                "email": emp[3],
                "phone_number": emp[4],
                "department": emp[5],
                "salary": emp[6],
                "status": emp[7],
                "date_hired": emp[8],
                "date_terminated": emp[9],
                "profile_image": profile_image_base64,
                "created": emp[11],
                "account_status": emp[12],
                "address1": emp[13],
                "city": emp[14],
                "address2": emp[15],
                "education": emp[16],
                "team": emp[17],
                "skills": emp[18],
                "certification": emp[19],
                "language": emp[20],
                "hobbies": emp[21],
                "date_of_birth": emp[22],
                "gender": emp[23],
                "teamrole": emp[24],
                "shift_name": emp[25],
                "shift_start_time": emp[26].strftime('%H:%M:%S') if emp[26] else None,
                "shift_end_time": emp[27].strftime('%H:%M:%S') if emp[27] else None,
                "is_rotating": emp[28],
                "location": emp[29],
                "team_id": emp[30],   
                "role_id": emp[31]
            }
            employees_with_images.append(employee_data)

        print(f"[DEBUG] Finished processing all employees. Total processed: {len(employees_with_images)}")
        log_audit(admin_id, role, "Employee management datas", f"Visit employeee management page")
        print("[DEBUG] Audit log written for employeemanagement_data fetch.")

        return jsonify({"employees": employees_with_images})

    except psycopg2.Error as e:
        log_incident(admin_id, role, f"Database error in employeemanagement_data: {str(e)}", severity="High")
        print("[ERROR] Database error occurred:", e)
        traceback.print_exc()
        return jsonify({"error": "Database error"}), 500
    except Exception as ex:
        log_incident(admin_id, role, f"Unexpected error in employeemanagement_data: {str(ex)}", severity="High")
        print("[ERROR] Unexpected error:", ex)
        traceback.print_exc()
        return jsonify({"error": "Unexpected server error"}), 500
    finally:
        if connection:
            cursor.close()
            connection.close()
        print("[DEBUG] Database connection closed in employeemanagement_data.")

# route for deleting employee from database
@csrf.exempt
@admin_bp.route('/delete_employee/<int:employee_id>', methods=['DELETE'])
@token_required_with_roles_and_2fa(required_actions=["delete_employee"])
def delete_employee(admin_id, role, role_id, employee_id):
    connection = None
    cursor = None
    try:
        logging.info(f"[DELETE_EMPLOYEE] Admin ID: {admin_id}, Role: {role}, Target Employee ID: {employee_id}")
        connection = get_db_connection()
        cursor = connection.cursor()
        logging.info("[DELETE_EMPLOYEE] Database connection established.")

        # Nullify as employee team lead in teams
        logging.info(f"[DELETE_EMPLOYEE] Setting team_lead_employee_id = NULL in teams where team_lead_employee_id = %s", (employee_id,))
        cursor.execute("UPDATE teams SET team_lead_employee_id = NULL WHERE team_lead_employee_id = %s", (employee_id,))
        connection.commit()

        # --- FK-SAFE: Remove all employee_breaks for this employee FIRST ---
        logging.info(f"[DELETE_EMPLOYEE] Deleting from employee_breaks where employee_id = {employee_id}")
        cursor.execute("DELETE FROM employee_breaks WHERE employee_id = %s", (employee_id,))
        connection.commit()

        # --- Now safe: Remove all attendance_logs for this employee ---
        logging.info(f"[DELETE_EMPLOYEE] Deleting from attendance_logs where employee_id = {employee_id}")
        cursor.execute("DELETE FROM attendance_logs WHERE employee_id = %s", (employee_id,))
        connection.commit()

        # --- Defensive cleanup: REMOVE this section since attendance_logs.break_id no longer exists ---
        # cursor.execute("DELETE FROM attendance_logs WHERE break_id IS NOT NULL AND break_id NOT IN (SELECT break_id FROM employee_breaks)")
        # connection.commit()

        # --- Handle goals and their dependencies ---
        cursor.execute("SELECT goal_id FROM goals WHERE employee_id = %s", (employee_id,))
        goal_ids = [row[0] for row in cursor.fetchall()]
        for goal_id in goal_ids:
            logging.info(f"[DELETE_EMPLOYEE] Deleting from goal_action_plans where goal_id = {goal_id}")
            cursor.execute("DELETE FROM goal_action_plans WHERE goal_id = %s", (goal_id,))
            connection.commit()
            logging.info(f"[DELETE_EMPLOYEE] Deleting from goal_evaluations where goal_id = {goal_id}")
            cursor.execute("DELETE FROM goal_evaluations WHERE goal_id = %s", (goal_id,))
            connection.commit()

        # --- Delete from other tables referencing employee_id ---
        child_tables = [
            "badge_assignments",
            "bonuses_incentives",
            "expense_claims",
            "goal_progress",
            "goal_progress_notes",
            "goal_progress_percentage",
            "survey_responses",
            "savings_plans",
            "two_factor_verifications",
            "assessment_answers",
            "survey_assignments",
            "ticket_responses",
        ]
        for table in child_tables:
            logging.info(f"[DELETE_EMPLOYEE] Deleting from {table} where employee_id = {employee_id}")
            cursor.execute(f"DELETE FROM {table} WHERE employee_id = %s", (employee_id,))
            connection.commit()

        # --- Delete from goals ---
        logging.info(f"[DELETE_EMPLOYEE] Deleting from goals where employee_id = {employee_id}")
        cursor.execute("DELETE FROM goals WHERE employee_id = %s", (employee_id,))
        connection.commit()

        # --- Cross-table: If employee is also an admin, handle admin tables ---
        logging.info(f"[DELETE_EMPLOYEE] Fetching email for employee_id {employee_id}.")
        cursor.execute("SELECT email FROM employees WHERE employee_id = %s", (employee_id,))
        employee_row = cursor.fetchone()
        employee_email = employee_row[0] if employee_row else None

        target_admin_id = None
        if employee_email:
            logging.info(f"[DELETE_EMPLOYEE] Checking if employee with email {employee_email} is an admin.")
            cursor.execute("SELECT admin_id FROM admins WHERE email = %s", (employee_email,))
            admin_row = cursor.fetchone()
            if admin_row:
                target_admin_id = admin_row[0]
                # Nullify as admin team lead in teams
                logging.info(f"[DELETE_EMPLOYEE] Setting team_lead_admin_id = NULL in teams where team_lead_admin_id = {target_admin_id}")
                cursor.execute("UPDATE teams SET team_lead_admin_id = NULL WHERE team_lead_admin_id = %s", (target_admin_id,))
                connection.commit()
                # Delete from two_factor_verifications by admin_id
                logging.info(f"[DELETE_EMPLOYEE] Deleting from two_factor_verifications for admin_id {target_admin_id}")
                cursor.execute("DELETE FROM two_factor_verifications WHERE admin_id = %s", (target_admin_id,))
                connection.commit()
                # Delete from team_members by admin_id
                logging.info(f"[DELETE_EMPLOYEE] Deleting from team_members where admin_id = {target_admin_id}")
                cursor.execute("DELETE FROM team_members WHERE admin_id = %s", (target_admin_id,))
                connection.commit()
                # Now can safely delete from admins table
                logging.info(f"[DELETE_EMPLOYEE] Deleting from admins table where admin_id = {target_admin_id}")
                cursor.execute("DELETE FROM admins WHERE admin_id = %s", (target_admin_id,))
                connection.commit()
            else:
                logging.info(f"[DELETE_EMPLOYEE] Employee with email {employee_email} is not an admin.")
        else:
            logging.warning(f"[DELETE_EMPLOYEE] No employee found with employee_id {employee_id} (cannot check admin cross-deletion).")

        # --- Delete from other related tables (by employee_id) ---
        related_tables = [
            "team_members", "payroll", "tax_records", "feedback_requests", 
            "alerts", "meetings", "announcements", "bank_details"
        ]
        for table in related_tables:
            logging.info(f"[DELETE_EMPLOYEE] Deleting from {table} where employee_id = {employee_id}")
            cursor.execute(f"DELETE FROM {table} WHERE employee_id = %s", (employee_id,))
            connection.commit()

        # --- Finally, delete from employees table ---
        logging.info("[DELETE_EMPLOYEE] Deleting from employees table.")
        cursor.execute("DELETE FROM employees WHERE employee_id = %s;", (employee_id,))
        connection.commit()
        logging.info(f"[DELETE_EMPLOYEE] Deleted employee from employees table with ID {employee_id}.")

        log_audit(admin_id, role, "delete_employee", f"Deleted employee with ID {employee_id} (and from admins if applicable)")
        return jsonify({"message": "Employee deleted successfully"}), 200

    except psycopg2.Error as e:
        log_incident(admin_id, role, f"Database error in delete_employee: {str(e)}", severity="High")
        logging.error(f"[DELETE_EMPLOYEE][DB_ERROR] Code: {e.pgcode}, Message: {e.pgerror}", exc_info=True)
        return jsonify({"error": e.pgerror}), 500

    except Exception as ex:
        log_incident(admin_id, role, f"Unexpected error in delete_employee: {str(ex)}", severity="High")
        logging.error(f"[DELETE_EMPLOYEE][UNEXPECTED_ERROR] {str(ex)}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred."}), 500

    finally:
        if cursor:
            try:
                cursor.close()
                logging.info("[DELETE_EMPLOYEE] Cursor closed.")
            except Exception as ex:
                logging.warning(f"[DELETE_EMPLOYEE] Failed to close cursor: {str(ex)}")
        if connection:
            try:
                connection.close()
                logging.info("[DELETE_EMPLOYEE] Database connection closed.")
            except Exception as ex:
                logging.warning(f"[DELETE_EMPLOYEE] Failed to close DB connection: {str(ex)}")
                       
# Route to add new employee
@csrf.exempt
@admin_bp.route('/add_employee', methods=['GET', 'POST'])
@token_required_with_roles_and_2fa(required_actions=["add_employee"])
def add_employee(admin_id, role, role_id):
    import psycopg2
    import bcrypt
    import logging
    
    logging.info(f"[ADD_EMPLOYEE] Request initiated by admin_id={admin_id}, role={role}")
    
    if request.method == 'GET':
        # Get dropdown data without caching
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Execute both queries in one cursor operation
        cursor.execute("SELECT team_id, team_name FROM teams")
        teams = [{"team_id": row[0], "team_name": row[1]} for row in cursor.fetchall()]
        
        cursor.execute("SELECT role_id, role_name FROM roles WHERE role_id != 2")
        roles = [{"role_id": row[0], "role_name": row[1]} for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        logging.info(f"[ADD_EMPLOYEE] Returned {len(teams)} teams and {len(roles)} roles for dropdown")
        return jsonify({"teams": teams, "roles": roles}), 200

    # POST method - Adding employee
    logging.info("[ADD_EMPLOYEE] Processing POST request to add new employee")
    
    # Allowed columns for employees table
    emp_allowed_columns = [
        "first_name", "last_name", "email", "phone_number", "department", "salary",
        "status", "date_hired", "date_terminated", "profile", "account_status",
        "address1", "city", "address2", "password", "skills", "certification",
        "education", "language", "hobbies", "team_id", "role_id", "gender", "date_of_birth"
    ]

    # Collect form data - more efficient processing
    emp_data = {}
    profile_data = None
    password = request.form.get("password")
    team_id = request.form.get("team_id")  # Explicitly capture team_id for later use
    
    logging.debug(f"[ADD_EMPLOYEE] Team ID from form: {team_id}")
    
    # Get file data only once
    profile_file = request.files.get("profile")
    if profile_file and profile_file.filename:
        profile_data = psycopg2.Binary(profile_file.read())
        emp_data["profile"] = profile_data
        logging.debug("[ADD_EMPLOYEE] Profile image processed")
    
    # Get hashed password only if provided
    if password:
        # Offload password hashing to a background thread if possible
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")
        emp_data["password"] = hashed_password
        logging.debug("[ADD_EMPLOYEE] Password hashed")
    
    # Process form data more efficiently
    for col in emp_allowed_columns:
        if col not in ["profile", "password"] and col in request.form:
            val = request.form.get(col)
            if val:  # This handles None and empty string
                emp_data[col] = val

    if not emp_data:
        logging.warning("[ADD_EMPLOYEE] No valid data provided in request")
        return jsonify({"error": "No valid data provided."}), 400

    # Security check
    if "role_id" in emp_data and str(emp_data["role_id"]) == "2":
        logging.warning(f"[ADD_EMPLOYEE] Attempt to create super_admin by admin_id={admin_id}")
        return jsonify({"error": "You cannot create a super_admin using this interface."}), 403

    conn = None
    cursor = None
    new_employee_id = None
    new_admin_id = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First, check if team_members table has role column, add if missing
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'team_members' AND column_name = 'role'
        """)
        if not cursor.fetchone():
            logging.info("[ADD_EMPLOYEE] Adding 'role' column to team_members table")
            cursor.execute("""
                ALTER TABLE team_members ADD COLUMN role VARCHAR(50)
            """)
            conn.commit()
        
        # Start a single transaction for all operations
        # Build SQL dynamically
        emp_columns = list(emp_data.keys())
        emp_values = list(emp_data.values())
        emp_placeholders = ", ".join(["%s"] * len(emp_columns))
        emp_columns_sql = ", ".join(emp_columns)
        emp_insert_sql = f"INSERT INTO employees ({emp_columns_sql}) VALUES ({emp_placeholders}) RETURNING employee_id;"
        
        cursor.execute(emp_insert_sql, emp_values)
        new_employee_id = cursor.fetchone()[0]
        logging.info(f"[ADD_EMPLOYEE] Created employee with ID: {new_employee_id}")

        # Check if admin record should be created
        role_id_val = str(emp_data.get("role_id", ""))
        is_dual_role = False
        
        if role_id_val in ("1", "3", "4"):
            # Prepare admin data
            admin_data = {
                "email": emp_data.get("email"),
                "password": emp_data.get("password"),
                "first_name": emp_data.get("first_name"),
                "last_name": emp_data.get("last_name"),
                "role_id": emp_data.get("role_id"),
                "gender": emp_data.get("gender"),
                "date_of_birth": emp_data.get("date_of_birth"),
                "is_verified": False
            }
            
            if profile_data:
                admin_data["profile_image"] = profile_data
            
            # Filter out None values
            admin_data = {k: v for k, v in admin_data.items() if v is not None}
            
            if admin_data:
                admin_columns = list(admin_data.keys())
                admin_values = list(admin_data.values())
                admin_placeholders = ", ".join(["%s"] * len(admin_columns))
                admin_columns_sql = ", ".join(admin_columns)
                admin_insert_sql = f"INSERT INTO admins ({admin_columns_sql}) VALUES ({admin_placeholders}) RETURNING admin_id"
                cursor.execute(admin_insert_sql, admin_values)
                new_admin_id = cursor.fetchone()[0]
                is_dual_role = True
                logging.info(f"[ADD_EMPLOYEE] Created admin record with ID: {new_admin_id} (dual role)")

        # NEW CODE: Handle team membership if team_id was provided
        if team_id and team_id.strip():
            logging.info(f"[ADD_EMPLOYEE] Processing team membership for team_id={team_id}")
            
            # Check if team exists
            cursor.execute("SELECT team_id FROM teams WHERE team_id = %s", (team_id,))
            if cursor.fetchone():
                # Check if this is the team lead for this team
                cursor.execute(
                    "SELECT team_lead_employee_id, team_lead_admin_id FROM teams WHERE team_id = %s", 
                    (team_id,)
                )
                team_lead_info = cursor.fetchone()
                
                if team_lead_info and str(team_lead_info[0]) == str(new_employee_id):
                    # This employee is the team lead
                    member_role = "Team Manager"
                    logging.info(f"[ADD_EMPLOYEE] Employee {new_employee_id} is the Team Manager for team {team_id}")
                else:
                    # Regular team member
                    member_role = "Team Member"
                    logging.info(f"[ADD_EMPLOYEE] Employee {new_employee_id} is a Team Member for team {team_id}")
                
                # Insert into team_members with appropriate role
                if is_dual_role and new_admin_id:
                    # Dual role user (both employee and admin)
                    cursor.execute(
                        """
                        INSERT INTO team_members 
                        (team_id, employee_id, admin_id, assigned_at, role) 
                        VALUES (%s, %s, %s, NOW(), %s)
                        """,
                        (team_id, new_employee_id, new_admin_id, member_role)
                    )
                    logging.info(f"[ADD_EMPLOYEE] Added dual-role member to team_members: emp_id={new_employee_id}, admin_id={new_admin_id}")
                else:
                    # Employee-only user
                    cursor.execute(
                        """
                        INSERT INTO team_members 
                        (team_id, employee_id, assigned_at, role) 
                        VALUES (%s, %s, NOW(), %s)
                        """,
                        (team_id, new_employee_id, member_role)
                    )
                    logging.info(f"[ADD_EMPLOYEE] Added employee-only member to team_members: emp_id={new_employee_id}")
            else:
                logging.warning(f"[ADD_EMPLOYEE] Team with ID {team_id} not found, skipping team_members insertion")

        # Commit once at the end
        conn.commit()
        logging.info(f"[ADD_EMPLOYEE] All database operations committed successfully")
        
        # Log audit outside of DB transaction
        log_audit(admin_id, role, "add_employee", f"Added employee (ID: {new_employee_id}), Team: {team_id}")
        
        return jsonify({
            "message": "Employee added successfully.", 
            "employee_id": new_employee_id,
            "admin_id": new_admin_id,
            "team_added": bool(team_id and team_id.strip())
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"[ADD_EMPLOYEE][ERROR] Failed to add employee: {str(e)}", exc_info=True)
        log_incident(admin_id, role, f"Error adding employee: {str(e)}", severity="High")
        return jsonify({"error": f"Error: {e}"}), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        logging.debug("[ADD_EMPLOYEE] Database connections closed")

# route for fetching api for employee management page
@admin_bp.route('/team_management_data', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_team_management_data"])
def get_team_management_data(admin_id, role, role_id):
    from flask import request
    import base64
    
    logging.debug(f"Token verified: admin_id={admin_id}, role={role}")
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)  # Default 20 employees per page
    
    # Get filter parameters
    search = request.args.get('search', '')
    department = request.args.get('department', '')
    status = request.args.get('status', '')
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Build the query with pagination and filtering
        query = """
            SELECT 
                e.employee_id, first_name, last_name, email, phone_number, department, 
                status, date_hired, account_status, t.team_name
            FROM employees e
            LEFT JOIN teams t ON t.team_id = e.team_id
            WHERE 1=1
        """
        params = []
        
        # Add filters
        if search:
            query += " AND (first_name ILIKE %s OR last_name ILIKE %s OR email ILIKE %s)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        if department:
            query += " AND department = %s"
            params.append(department)
            
        if status:
            query += " AND status = %s"
            params.append(status)
            
        # Add ordering
        query += " ORDER BY employee_id"
        
        # Add pagination
        query += " LIMIT %s OFFSET %s"
        params.extend([per_page, (page - 1) * per_page])
        
        # Execute the query
        cursor.execute(query, params)
        employees_basic = cursor.fetchall()
        
        # Get total count for pagination
        count_query = """
            SELECT COUNT(*) FROM employees e
            LEFT JOIN teams t ON t.team_id = e.team_id
            WHERE 1=1
        """
        # Add the same filters to count query
        count_params = []
        if search:
            count_query += " AND (first_name ILIKE %s OR last_name ILIKE %s OR email ILIKE %s)"
            search_param = f"%{search}%"
            count_params.extend([search_param, search_param, search_param])
        
        if department:
            count_query += " AND department = %s"
            count_params.append(department)
            
        if status:
            count_query += " AND status = %s"
            count_params.append(status)
            
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()[0]
        
        # Process results - with minimal fields
        employees_with_basic_info = []
        for employee in employees_basic:
            employees_with_basic_info.append({
                "employee_id": employee[0],
                "first_name": employee[1],
                "last_name": employee[2],
                "email": employee[3],
                "phone_number": employee[4],
                "department": employee[5],
                "status": employee[6],
                "date_hired": str(employee[7]) if employee[7] else None,
                "account_status": employee[8],
                "team": employee[9]
            })
        
        # Get shifts and selectable employees data
        cursor.execute("SELECT shift_id, shift_name FROM shifts")
        shifts = cursor.fetchall()
        
        cursor.execute("SELECT employee_id, email FROM employees")
        selectable_employees = cursor.fetchall()
        
        # Audit: log successful fetch
        log_audit(admin_id, role, "get_team_management_data", f"Fetched team management data (page {page})")
        
        # Return paginated result
        return jsonify({
            "employees": employees_with_basic_info,
            "shifts": [{"shift_id": s[0], "shift_name": s[1]} for s in shifts],
            "selectable_employees": [{"employee_id": e[0], "email": e[1]} for e in selectable_employees],
            "pagination": {
                "total": total_count,
                "page": page,
                "per_page": per_page,
                "pages": (total_count + per_page - 1) // per_page
            }
        })

    except Exception as e:
        # Incident: log error on fetch
        log_incident(admin_id, role, f"Error loading team management data: {str(e)}", severity="High")
        logging.error(f"Error loading team management data: {e}", exc_info=True)
        return jsonify({"error": "Failed to load team data"}), 500

    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'connection' in locals() and connection:
            connection.close()

# route for fetching team's datas
@csrf.exempt
@admin_bp.route('/api/teams', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["view_teams"])
def get_teams_details(admin_id, role, role_id):
    import traceback
    try:
        print("[DEBUG] /api/teams called by admin_id:", admin_id, "role:", role, "role_id:", role_id)
        connection = get_db_connection()
        cursor = connection.cursor()

        # Fetch teams with both admin/employee lead info
        cursor.execute("""
            SELECT
                t.team_id,
                t.team_name,
                t.created_at,
                t.team_lead_employee_id,
                t.team_lead_admin_id,
                e.email as employee_lead_email,
                a.email as admin_lead_email
            FROM teams t
            LEFT JOIN employees e ON t.team_lead_employee_id = e.employee_id
            LEFT JOIN admins a ON t.team_lead_admin_id = a.admin_id
        """)
        team_rows = cursor.fetchall()
        print("[DEBUG] Teams fetched from DB:", team_rows)
        teams = []
        for row in team_rows:
            # Always try to provide a single `team_lead_email` field, preferring employee email (if both exist, they're the same anyway)
            team_lead_employee_email = row[5]
            team_lead_admin_email = row[6]
            team_lead_email = team_lead_employee_email or team_lead_admin_email

            teams.append({
                "team_id": row[0],
                "team_name": row[1],
                "created_at": row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else None,
                "team_lead_employee_id": row[3],
                "team_lead_admin_id": row[4],
                "team_lead_employee_email": team_lead_employee_email,
                "team_lead_admin_email": team_lead_admin_email,
                "team_lead_email": team_lead_email,  # <--- Unified email for frontend population!
            })
        print(f"[DEBUG] Teams constructed: {teams}")

        # Build user dict by email (unique, merge admin/employee IDs if dual role)
        user_by_email = {}

        # Add admins first
        cursor.execute("""
            SELECT a.admin_id, a.email, r.role_name, 'admin' as user_type
            FROM admins a
            LEFT JOIN roles r ON a.role_id = r.role_id
        """)
        admin_rows = cursor.fetchall()
        for row in admin_rows:
            email = (row[1] or "").lower()
            if email:
                user_by_email[email] = {
                    "admin_id": row[0],
                    "employee_id": None,
                    "id": row[0],  # for legacy compatibility
                    "email": row[1],
                    "role": row[2],
                    "user_type": row[3]
                }

        # Add employees, merge if email already present
        cursor.execute("""
            SELECT e.employee_id, e.email, r.role_name, 'employee' as user_type
            FROM employees e
            LEFT JOIN roles r ON e.role_id = r.role_id
            WHERE e.account_status = 'Activated'
        """)
        employee_rows = cursor.fetchall()
        for row in employee_rows:
            email = (row[1] or "").lower()
            if email in user_by_email:
                # Merge employee_id into existing user, update user_type if both
                user_by_email[email]["employee_id"] = row[0]
                user_by_email[email]["role"] += " / " + row[2]
                user_by_email[email]["user_type"] = "admin_employee"
            else:
                user_by_email[email] = {
                    "admin_id": None,
                    "employee_id": row[0],
                    "id": row[0],  # for legacy compatibility
                    "email": row[1],
                    "role": row[2],
                    "user_type": row[3]
                }

        users = list(user_by_email.values())
        print(f"[DEBUG] Final users list to return: {users}")

        # ----------- FETCH TEAM MEMBERS FOR EACH TEAM -------------
        # First, we'll create a member mapping using emails as keys to handle dual-role users properly
        team_members_by_team_id = {}
        
        cursor.execute("""
            SELECT
                tm.team_id,
                tm.admin_id,
                tm.employee_id,
                tm.role as team_role,
                a.email as admin_email,
                e.email as employee_email,
                r_a.role_name as admin_role_name,
                r_e.role_name as employee_role_name
            FROM team_members tm
            LEFT JOIN admins a ON tm.admin_id = a.admin_id
            LEFT JOIN employees e ON tm.employee_id = e.employee_id
            LEFT JOIN roles r_a ON a.role_id = r_a.role_id
            LEFT JOIN roles r_e ON e.role_id = r_e.role_id
        """)
        member_rows = cursor.fetchall()
        
        print(f"[DEBUG] Team members fetched: {len(member_rows)} rows")
        
        for row in member_rows:
            team_id = row[0]
            admin_id = row[1]
            employee_id = row[2]
            team_role = row[3] or "Team Member"  # Default role if not specified
            admin_email = row[4]
            employee_email = row[5]
            admin_role_name = row[6]
            employee_role_name = row[7]
            
            # Initialize the team's members list if it doesn't exist
            if team_id not in team_members_by_team_id:
                team_members_by_team_id[team_id] = {}
            
            # The email we'll use as key (prefer employee email if available)
            member_email = employee_email or admin_email
            if not member_email:
                print(f"[WARN] Team member without email: team_id={team_id}, admin_id={admin_id}, employee_id={employee_id}")
                continue
            
            member_email = member_email.lower()
            
            # Create or update the member entry
            if member_email not in team_members_by_team_id[team_id]:
                # New member
                member_data = {
                    "email": member_email,
                    "admin_id": admin_id,
                    "employee_id": employee_id,
                    "id": employee_id or admin_id,  # For compatibility with frontend
                    "role": employee_role_name or admin_role_name or "",
                    "team_role": team_role,
                }
                
                # Determine user type
                if employee_id and admin_id:
                    member_data["user_type"] = "admin_employee"
                elif employee_id:
                    member_data["user_type"] = "employee"
                else:
                    member_data["user_type"] = "admin"
                
                team_members_by_team_id[team_id][member_email] = member_data
            else:
                # Update existing member - might be dual role
                existing = team_members_by_team_id[team_id][member_email]
                
                # Update IDs if not already set
                if admin_id and not existing["admin_id"]:
                    existing["admin_id"] = admin_id
                if employee_id and not existing["employee_id"]:
                    existing["employee_id"] = employee_id
                    existing["id"] = employee_id  # Prefer employee ID for frontend
                
                # Update roles
                if admin_id and employee_id:
                    existing["user_type"] = "admin_employee"
                    role_parts = []
                    if employee_role_name:
                        role_parts.append(employee_role_name)
                    if admin_role_name and admin_role_name not in role_parts:
                        role_parts.append(admin_role_name)
                    existing["role"] = " / ".join(role_parts)
        
        # Now convert the dictionaries to lists and attach to teams
        for team in teams:
            team_id = team["team_id"]
            if team_id in team_members_by_team_id:
                team["members"] = list(team_members_by_team_id[team_id].values())
                print(f"[DEBUG] Team {team_id} has {len(team['members'])} members")
            else:
                team["members"] = []
                print(f"[DEBUG] Team {team_id} has no members")

        print("[DEBUG] Returning response with teams, members, and deduped users.")
        return jsonify({"teams": teams, "users": users}), 200
    except Exception as e:
        print("[ERROR] Exception occurred in /api/teams:", str(e))
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        if 'connection' in locals() and connection:
            cursor.close()
            connection.close()
            
# Edit existing team
# Helper function to get timestamp
def get_utc_timestamp():
    from datetime import datetime
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

@csrf.exempt
@admin_bp.route('/team_management/edit', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["edit_team"])
def edit_team(admin_id, role, role_id):
    connection = None
    cursor = None
    try:
        # Log request details
        print(f"[DEBUG] [{get_utc_timestamp()}] edit_team called by admin_id={admin_id}, role={role}, role_id={role_id}")
        
        # Get connection and cursor
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get form data
        team_id = request.form.get('team_id')
        team_name = request.form.get('team_name')
        team_lead_employee_id = request.form.get('team_lead_employee_id')
        team_lead_admin_id = request.form.get('team_lead_admin_id')
        
        print(f"[DEBUG] [{get_utc_timestamp()}] Form data - team_id: {team_id}, team_name: {team_name}, "
              f"team_lead_employee_id: {team_lead_employee_id}, team_lead_admin_id: {team_lead_admin_id}")
        
        # First, check if team_members table has role column, add if missing
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'team_members' AND column_name = 'role'
        """)
        if not cursor.fetchone():
            print(f"[INFO] [{get_utc_timestamp()}] Adding 'role' column to team_members table")
            cursor.execute("""
                ALTER TABLE team_members ADD COLUMN role VARCHAR(50)
            """)
            connection.commit()
        
        # Fetch current team lead information
        cursor.execute(
            "SELECT team_lead_employee_id, team_lead_admin_id FROM teams WHERE team_id = %s",
            (team_id,)
        )
        current_team_lead = cursor.fetchone()
        
        if not current_team_lead:
            print(f"[ERROR] [{get_utc_timestamp()}] Team with ID {team_id} not found")
            return jsonify({"error": f"Team with ID {team_id} not found"}), 404
        
        current_lead_employee_id = current_team_lead[0]
        current_lead_admin_id = current_team_lead[1]
        
        print(f"[DEBUG] [{get_utc_timestamp()}] Current team lead - employee_id: {current_lead_employee_id}, admin_id: {current_lead_admin_id}")
        print(f"[DEBUG] [{get_utc_timestamp()}] New team lead - employee_id: {team_lead_employee_id}, admin_id: {team_lead_admin_id}")
        
        # Update team info in teams table
        cursor.execute(
            "UPDATE teams SET team_name=%s, team_lead_employee_id=%s, team_lead_admin_id=%s WHERE team_id=%s",
            (team_name, 
             team_lead_employee_id if team_lead_employee_id else None, 
             team_lead_admin_id if team_lead_admin_id else None, 
             team_id)
        )
        print(f"[DEBUG] [{get_utc_timestamp()}] Updated team_lead_employee_id to {team_lead_employee_id}, team_lead_admin_id to {team_lead_admin_id}")
        
        # If team lead has changed, update team_members table
        lead_changed = (str(current_lead_employee_id) != str(team_lead_employee_id) or 
                        str(current_lead_admin_id) != str(team_lead_admin_id))
        
        if lead_changed:
            print(f"[DEBUG] [{get_utc_timestamp()}] Team lead has changed, updating team_members")
            
            # First, check if there are any existing 'Team Manager' roles and remove them
            cursor.execute(
                "DELETE FROM team_members WHERE team_id = %s AND role = 'Team Manager'",
                (team_id,)
            )
            print(f"[DEBUG] [{get_utc_timestamp()}] Removed existing Team Manager entries")
            
            # Now add the new team lead as a member with 'Team Manager' role
            if team_lead_employee_id or team_lead_admin_id:
                # Check if team lead is already a member (without Team Manager role)
                if team_lead_employee_id:
                    cursor.execute(
                        "SELECT * FROM team_members WHERE team_id = %s AND employee_id = %s",
                        (team_id, team_lead_employee_id)
                    )
                    existing_member = cursor.fetchone()
                    
                    if existing_member:
                        # Update existing member to have Team Manager role
                        cursor.execute(
                            "UPDATE team_members SET role = 'Team Manager', admin_id = %s WHERE team_id = %s AND employee_id = %s",
                            (team_lead_admin_id if team_lead_admin_id else None, team_id, team_lead_employee_id)
                        )
                        print(f"[DEBUG] [{get_utc_timestamp()}] Updated existing member to Team Manager - employee_id: {team_lead_employee_id}")
                    else:
                        # Insert new team member with Team Manager role
                        if team_lead_employee_id and team_lead_admin_id:
                            # Dual role lead
                            cursor.execute(
                                """
                                INSERT INTO team_members (team_id, employee_id, admin_id, assigned_at, role) 
                                VALUES (%s, %s, %s, NOW(), 'Team Manager')
                                """,
                                (team_id, team_lead_employee_id, team_lead_admin_id)
                            )
                            print(f"[DEBUG] [{get_utc_timestamp()}] Inserted team lead as member with DUAL ROLE: "
                                  f"employee_id={team_lead_employee_id}, admin_id={team_lead_admin_id}")
                        
                        elif team_lead_employee_id:
                            # Employee-only lead
                            cursor.execute(
                                """
                                INSERT INTO team_members (team_id, employee_id, assigned_at, role) 
                                VALUES (%s, %s, NOW(), 'Team Manager')
                                """,
                                (team_id, team_lead_employee_id)
                            )
                            print(f"[DEBUG] [{get_utc_timestamp()}] Inserted team lead as member with EMPLOYEE role: "
                                  f"employee_id={team_lead_employee_id}")
                elif team_lead_admin_id:
                    # Admin-only lead (rare case)
                    cursor.execute(
                        "SELECT * FROM team_members WHERE team_id = %s AND admin_id = %s",
                        (team_id, team_lead_admin_id)
                    )
                    existing_member = cursor.fetchone()
                    
                    if existing_member:
                        # Update existing member to have Team Manager role
                        cursor.execute(
                            "UPDATE team_members SET role = 'Team Manager' WHERE team_id = %s AND admin_id = %s",
                            (team_id, team_lead_admin_id)
                        )
                        print(f"[DEBUG] [{get_utc_timestamp()}] Updated existing member to Team Manager - admin_id: {team_lead_admin_id}")
                    else:
                        # Insert admin-only lead
                        cursor.execute(
                            """
                            INSERT INTO team_members (team_id, admin_id, assigned_at, role) 
                            VALUES (%s, %s, NOW(), 'Team Manager')
                            """,
                            (team_id, team_lead_admin_id)
                        )
                        print(f"[DEBUG] [{get_utc_timestamp()}] Inserted team lead as member with ADMIN role: "
                              f"admin_id={team_lead_admin_id}")
        
        # Commit all changes
        connection.commit()
        print(f"[DEBUG] [{get_utc_timestamp()}] Transaction committed.")
        
        # Log audit
        log_audit(
            admin_id, role, "edit_team",
            f"Team '{team_name}' (ID: {team_id}) updated with lead "
            f"employee_id={team_lead_employee_id} admin_id={team_lead_admin_id}"
        )
        
        return jsonify({"message": "Team updated successfully"}), 200
    
    except Exception as e:
        print(f"[ERROR] [{get_utc_timestamp()}] Exception occurred in edit_team: {e}")
        import traceback; traceback.print_exc()
        if connection:
            connection.rollback()
            print(f"[DEBUG] [{get_utc_timestamp()}] Transaction rolled back.")
        
        # Log incident
        log_incident(admin_id, role, f"Team edit failed: {str(e)}", severity="High")
        
        return jsonify({"error": str(e)}), 500
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
        print(f"[DEBUG] [{get_utc_timestamp()}] Connection closed.")

# Add new employee to existing team
@csrf.exempt
@admin_bp.route('/team_management/add_user', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["add_team_member"])
def add_user_to_team(admin_id, role, role_id):
    import traceback
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        team_id = request.form.get('team_id')
        user_email = request.form.get('user_email')
        assigned_at = datetime.now()

        if not team_id or not user_email:
            return jsonify({"error": "Missing team_id or user_email"}), 400

        # Look up in admins
        cursor.execute("SELECT admin_id FROM admins WHERE LOWER(email) = LOWER(%s)", (user_email,))
        admin_row = cursor.fetchone()
        admin_id_value = admin_row[0] if admin_row else None

        # Look up in employees
        cursor.execute("SELECT employee_id FROM employees WHERE LOWER(email) = LOWER(%s)", (user_email,))
        employee_row = cursor.fetchone()
        employee_id_value = employee_row[0] if employee_row else None

        if not admin_id_value and not employee_id_value:
            return jsonify({"error": "User not found in admins or employees table."}), 404

        # Check for existing membership (avoid duplicates)
        cursor.execute(
            "SELECT id FROM team_members WHERE team_id = %s AND ((admin_id = %s AND %s IS NOT NULL) OR (employee_id = %s AND %s IS NOT NULL))",
            (team_id, admin_id_value, admin_id_value, employee_id_value, employee_id_value)
        )
        if cursor.fetchone():
            return jsonify({"message": "User already added to team."}), 200

        # Insert
        cursor.execute(
            "INSERT INTO team_members (team_id, admin_id, employee_id, assigned_at) VALUES (%s, %s, %s, %s)",
            (team_id, admin_id_value, employee_id_value, assigned_at)
        )
        connection.commit()

        return jsonify({
            "message": "User added to team successfully",
            "debug": {
                "team_id": team_id,
                "user_email": user_email,
                "admin_id": admin_id_value,
                "employee_id": employee_id_value
            }
        }), 200

    except Exception as e:
        if connection:
            connection.rollback()
        tb = traceback.format_exc()
        print(tb)
        return jsonify({
            "error": str(e),
            "traceback": tb
        }), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# Delete team
@csrf.exempt
@admin_bp.route('/team_management/delete', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["delete_team"])
def delete_team(admin_id, role, role_id):
    import logging
    import time
    import traceback
    
    # Start timer for performance measurement
    start_time = time.time()
    
    # Log the request
    logging.info(f"[{admin_id}] DELETE TEAM request received at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"DEBUG: Admin {admin_id} ({role}) attempting to delete team")
    
    try:
        # Get request data and log it
        team_id = request.form.get('team_id')
        force_delete = request.form.get('force_delete') != 'false'
        
        logging.info(f"[{admin_id}] Request to delete team_id: {team_id}, force_delete: {force_delete}")
        print(f"DEBUG: Request parameters - team_id: {team_id}, force_delete: {force_delete}")
        
        # Validate input
        if not team_id:
            logging.warning(f"[{admin_id}] Missing team_id in delete request")
            print("DEBUG: Error - Missing team_id parameter")
            return jsonify({"error": "Missing team_id"}), 400
        
        # Helper function to execute safe database operations
        def safe_db_operation(operation_name, check_sql, delete_sql=None, description="records"):
            """Execute a database operation safely with its own connection"""
            connection = None
            cursor = None
            try:
                connection = get_db_connection()
                cursor = connection.cursor()
                
                # Check if records exist
                cursor.execute(check_sql, (team_id,))
                record_count = cursor.fetchone()[0]
                
                if record_count > 0 and delete_sql:
                    print(f"DEBUG: Found {record_count} {description} to remove from {operation_name}")
                    
                    # Execute cleanup
                    cursor.execute(delete_sql, (team_id,))
                    affected_rows = cursor.rowcount
                    
                    # Commit this specific operation
                    connection.commit()
                    
                    print(f"DEBUG: Successfully removed {affected_rows} {description} from {operation_name}")
                    logging.info(f"[{admin_id}] Removed {affected_rows} {description} from {operation_name}")
                    
                    # Log audit for this operation
                    log_audit(
                        admin_id, role, f"remove_{operation_name}",
                        f"Automatically removed {affected_rows} {description} during team deletion"
                    )
                    
                    return affected_rows
                else:
                    print(f"DEBUG: No {description} found in {operation_name} for team {team_id}")
                    return 0
                    
            except Exception as op_error:
                print(f"DEBUG: Error in {operation_name} cleanup: {str(op_error)}")
                logging.error(f"[{admin_id}] Error in {operation_name} cleanup: {str(op_error)}")
                if connection:
                    connection.rollback()
                raise op_error
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    connection.close()
        
        # Helper function for cascade deletion (handles dependencies)
        def safe_cascade_operation(operation_name, parent_table, parent_id_col, child_tables, description="records"):
            """Execute cascade deletion - remove child records first, then parent"""
            connection = None
            cursor = None
            try:
                connection = get_db_connection()
                cursor = connection.cursor()
                
                # Check if parent records exist
                cursor.execute(f"SELECT COUNT(*) FROM {parent_table} WHERE {parent_id_col} = %s", (team_id,))
                record_count = cursor.fetchone()[0]
                
                if record_count > 0:
                    print(f"DEBUG: Found {record_count} {description} to cascade delete from {operation_name}")
                    
                    total_removed = 0
                    
                    # First, remove all child records
                    for child_table, child_foreign_key in child_tables:
                        try:
                            # Get IDs of parent records we're about to delete
                            if parent_table == "goals":
                                parent_record_id_col = "goal_id"
                            elif parent_table == "alerts":
                                parent_record_id_col = "alert_id"
                            else:
                                parent_record_id_col = parent_table.rstrip('s') + '_id'
                            
                            cursor.execute(f"SELECT {parent_record_id_col} FROM {parent_table} WHERE {parent_id_col} = %s", (team_id,))
                            parent_ids = [row[0] for row in cursor.fetchall()]
                            
                            if parent_ids:
                                # Delete child records for each parent ID
                                for parent_id in parent_ids:
                                    cursor.execute(f"DELETE FROM {child_table} WHERE {child_foreign_key} = %s", (parent_id,))
                                    child_removed = cursor.rowcount
                                    if child_removed > 0:
                                        print(f"DEBUG: Removed {child_removed} records from {child_table} for {parent_table} ID {parent_id}")
                                        total_removed += child_removed
                        except Exception as child_error:
                            print(f"DEBUG: Error removing {child_table} records: {str(child_error)}")
                            # Continue with other child tables
                            continue
                    
                    # Now delete parent records
                    cursor.execute(f"DELETE FROM {parent_table} WHERE {parent_id_col} = %s", (team_id,))
                    parent_removed = cursor.rowcount
                    total_removed += parent_removed
                    
                    # Commit this specific operation
                    connection.commit()
                    
                    print(f"DEBUG: Successfully cascade deleted {total_removed} total records from {operation_name}")
                    logging.info(f"[{admin_id}] Cascade deleted {total_removed} total records from {operation_name}")
                    
                    # Log audit for this operation
                    log_audit(
                        admin_id, role, f"cascade_remove_{operation_name}",
                        f"Automatically cascade deleted {total_removed} records from {operation_name} during team deletion"
                    )
                    
                    return total_removed
                else:
                    print(f"DEBUG: No {description} found in {operation_name} for team {team_id}")
                    return 0
                    
            except Exception as op_error:
                print(f"DEBUG: Error in {operation_name} cascade cleanup: {str(op_error)}")
                logging.error(f"[{admin_id}] Error in {operation_name} cascade cleanup: {str(op_error)}")
                if connection:
                    connection.rollback()
                raise op_error
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    connection.close()
        
        # First, check if the team exists
        connection = get_db_connection()
        cursor = connection.cursor()
        
        try:
            cursor.execute("SELECT team_name FROM teams WHERE team_id = %s", (team_id,))
            team_info = cursor.fetchone()
            
            if not team_info:
                logging.warning(f"[{admin_id}] Team not found: team_id={team_id}")
                print(f"DEBUG: No team found with team_id {team_id}")
                return jsonify({"error": "Team not found"}), 404
                
            team_name = team_info[0]
            print(f"DEBUG: Found team: {team_name} (ID: {team_id})")
        finally:
            cursor.close()
            connection.close()
        
        # If force_delete is false, check for dependencies and provide detailed feedback
        if not force_delete:
            dependencies = []
            
            # Check each dependency safely (UPDATED WITH ALL KNOWN DEPENDENCIES)
            dependency_checks = [
                ("goal_progress", "SELECT COUNT(*) FROM goal_progress WHERE team_id = %s", "goal progress records"),
                ("goal_progress_notes", "SELECT COUNT(*) FROM goal_progress_notes WHERE team_id = %s", "goal progress notes"),
                ("goal_progress_percentage", "SELECT COUNT(*) FROM goal_progress_percentage WHERE team_id = %s", "goal progress percentages"),
                ("badge_assignments", "SELECT COUNT(*) FROM badge_assignments WHERE team_id = %s", "badge assignments"),
                ("employees", "SELECT COUNT(*) FROM employees WHERE team_id = %s", "employees assigned"),
                ("team_members", "SELECT COUNT(*) FROM team_members WHERE team_id = %s", "team members"),
                ("alerts", "SELECT COUNT(*) FROM alerts WHERE team_id = %s", "alerts"),
                ("goals", "SELECT COUNT(*) FROM goals WHERE team_id = %s", "goals"),
                ("event_participants", "SELECT COUNT(*) FROM event_participants WHERE team_id = %s", "event participants")
            ]
            
            for table_name, check_sql, description in dependency_checks:
                try:
                    count = safe_db_operation(table_name, check_sql, description=description)
                    if count > 0:
                        dependencies.append({
                            "table": table_name,
                            "count": count,
                            "description": f"{count} {description}"
                        })
                except Exception as dep_check_error:
                    print(f"DEBUG: Error checking {table_name}: {str(dep_check_error)}")
                    # Continue checking other dependencies
                    continue
            
            # If dependencies exist, return detailed information
            if dependencies:
                dependency_descriptions = [dep["description"] for dep in dependencies]
                
                return jsonify({
                    "error": f"Cannot delete team: This team has {', '.join(dependency_descriptions)} that must be removed first.",
                    "dependencies": dependencies,
                    "team_id": team_id,
                    "team_name": team_name,
                    "requires_force_delete": True,
                    "fix_instruction": "Use force_delete=true to automatically remove all dependencies and delete the team."
                }), 400
            
            # No dependencies - safe to delete
            try:
                connection = get_db_connection()
                cursor = connection.cursor()
                
                cursor.execute("DELETE FROM teams WHERE team_id = %s", (team_id,))
                teams_deleted = cursor.rowcount
                
                if teams_deleted == 0:
                    logging.warning(f"[{admin_id}] Team deletion failed: team_id={team_id}")
                    print(f"DEBUG: Failed to delete team with team_id {team_id}")
                    connection.rollback()
                    return jsonify({"error": "Failed to delete team"}), 500
                
                connection.commit()
                
                # Log audit event
                log_audit(
                    admin_id, role, "delete_team", 
                    f"Deleted team '{team_name}' (ID: {team_id})."
                )
                
                return jsonify({
                    "message": f"Team '{team_name}' deleted successfully.",
                    "team_id": team_id,
                    "team_name": team_name
                }), 200
                
            except Exception as delete_error:
                print(f"DEBUG: Error deleting team: {str(delete_error)}")
                logging.error(f"[{admin_id}] Error deleting team: {str(delete_error)}")
                if connection:
                    connection.rollback()
                return jsonify({"error": f"Error deleting team: {str(delete_error)}"}), 500
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    connection.close()
        
        # FORCE DELETE - CASCADE DELETE ALL DEPENDENCIES
        else:
            print(f"DEBUG: Force delete enabled, attempting to remove dependencies for team {team_id}")
            logging.info(f"[{admin_id}] Force delete enabled, attempting to remove dependencies for team {team_id}")
            
            # Track what was removed
            removed_items = {}
            
            # PHASE 1: Remove direct team dependencies (deepest level first)
            phase1_operations = [
                ("goal_progress", "SELECT COUNT(*) FROM goal_progress WHERE team_id = %s", 
                 "DELETE FROM goal_progress WHERE team_id = %s", "goal progress records"),
                
                ("goal_progress_notes", "SELECT COUNT(*) FROM goal_progress_notes WHERE team_id = %s", 
                 "DELETE FROM goal_progress_notes WHERE team_id = %s", "goal progress notes"),
                
                ("goal_progress_percentage", "SELECT COUNT(*) FROM goal_progress_percentage WHERE team_id = %s", 
                 "DELETE FROM goal_progress_percentage WHERE team_id = %s", "goal progress percentages"),
                
                ("badge_assignments", "SELECT COUNT(*) FROM badge_assignments WHERE team_id = %s", 
                 "DELETE FROM badge_assignments WHERE team_id = %s", "badge assignments"),
                
                ("team_members", "SELECT COUNT(*) FROM team_members WHERE team_id = %s", 
                 "DELETE FROM team_members WHERE team_id = %s", "team members"),
                
                ("employees_updated", "SELECT COUNT(*) FROM employees WHERE team_id = %s", 
                 "UPDATE employees SET team_id = NULL WHERE team_id = %s", "employees unassigned"),

                 ("event_participants", "SELECT COUNT(*) FROM event_participants WHERE team_id = %s", 
                    "DELETE FROM event_participants WHERE team_id = %s", "event participants"),
            ]
            
            print("DEBUG: Starting Phase 1 - Direct team dependencies")
            for operation_name, check_sql, delete_sql, description in phase1_operations:
                try:
                    affected_rows = safe_db_operation(operation_name, check_sql, delete_sql, description)
                    if affected_rows > 0:
                        removed_items[operation_name] = affected_rows
                except Exception as cleanup_error:
                    print(f"DEBUG: Non-critical error in {operation_name} cleanup: {str(cleanup_error)}")
                    logging.warning(f"[{admin_id}] Non-critical error in {operation_name} cleanup: {str(cleanup_error)}")
                    continue
            
            # PHASE 2: Cascade delete operations (items with their own dependencies)
            phase2_cascade_operations = [
                # Alerts and their reads
                ("alerts", "alerts", "team_id", [("alert_reads", "alert_id")], "alerts with reads"),
                
                # Goals and their action plans + evaluations
                ("goals", "goals", "team_id", [
                    ("goal_action_plans", "goal_id"),
                    ("goal_evaluations", "goal_id")
                ], "goals with action plans and evaluations"),
            ]
            
            print("DEBUG: Starting Phase 2 - Cascade deletions")
            for operation_name, parent_table, parent_id_col, child_tables, description in phase2_cascade_operations:
                try:
                    affected_rows = safe_cascade_operation(operation_name, parent_table, parent_id_col, child_tables, description)
                    if affected_rows > 0:
                        removed_items[operation_name] = affected_rows
                except Exception as cascade_error:
                    print(f"DEBUG: Non-critical error in {operation_name} cascade cleanup: {str(cascade_error)}")
                    logging.warning(f"[{admin_id}] Non-critical error in {operation_name} cascade cleanup: {str(cascade_error)}")
                    continue
            
            # PHASE 3: Simple deletions (items with no known dependencies)
            phase3_operations = [
                ("feedback_requests", "SELECT COUNT(*) FROM feedback_requests WHERE team_id = %s", 
                 "DELETE FROM feedback_requests WHERE team_id = %s", "feedback requests"),
                
                ("announcements", "SELECT COUNT(*) FROM announcements WHERE team_id = %s", 
                 "DELETE FROM announcements WHERE team_id = %s", "announcements"),
                
                ("meetings", "SELECT COUNT(*) FROM meetings WHERE team_id = %s", 
                 "DELETE FROM meetings WHERE team_id = %s", "meetings"),
                
                ("tasks", "SELECT COUNT(*) FROM tasks WHERE team_id = %s", 
                 "DELETE FROM tasks WHERE team_id = %s", "tasks")
            ]
            
            print("DEBUG: Starting Phase 3 - Simple deletions")
            for operation_name, check_sql, delete_sql, description in phase3_operations:
                try:
                    affected_rows = safe_db_operation(operation_name, check_sql, delete_sql, description)
                    if affected_rows > 0:
                        removed_items[operation_name] = affected_rows
                except Exception as cleanup_error:
                    print(f"DEBUG: Non-critical error in {operation_name} cleanup: {str(cleanup_error)}")
                    logging.warning(f"[{admin_id}] Non-critical error in {operation_name} cleanup: {str(cleanup_error)}")
                    continue
            
            # PHASE 4: Finally, delete the team itself
            print("DEBUG: Starting Phase 4 - Team deletion")
            try:
                connection = get_db_connection()
                cursor = connection.cursor()
                
                cursor.execute("DELETE FROM teams WHERE team_id = %s", (team_id,))
                teams_deleted = cursor.rowcount
                
                if teams_deleted == 0:
                    print(f"DEBUG: Failed to delete team {team_id} even after removing dependencies")
                    logging.warning(f"[{admin_id}] Failed to delete team {team_id} even after removing dependencies")
                    connection.rollback()
                    
                    return jsonify({
                        "error": "Failed to delete team even after removing dependencies. The team may not exist.",
                        "removed_items": removed_items
                    }), 500
                
                connection.commit()
                print(f"DEBUG: Successfully deleted team {team_id}")
                logging.info(f"[{admin_id}] Successfully deleted team {team_id}")
                
            except Exception as final_delete_error:
                print(f"DEBUG: Final team deletion failed: {str(final_delete_error)}")
                logging.error(f"[{admin_id}] Final team deletion failed: {str(final_delete_error)}")
                if connection:
                    connection.rollback()
                
                return jsonify({
                    "error": f"Failed to delete team: {str(final_delete_error)}",
                    "removed_items": removed_items
                }), 500
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    connection.close()
            
            # Build success message
            success_message = f"Team '{team_name}' deleted successfully."
            details = []
            
            for key, count in removed_items.items():
                if key == "employees_updated":
                    details.append(f"{count} employees unassigned")
                else:
                    details.append(f"{count} {key.replace('_', ' ')} removed")
                
            if details:
                success_message += f" ({', '.join(details)})."
            
            # Log final audit event
            log_audit(
                admin_id, role, "delete_team", 
                f"Deleted team '{team_name}' (ID: {team_id}) with force_delete option. {', '.join(details) if details else 'No dependencies removed'}"
            )
            
            return jsonify({
                "message": success_message,
                "team_id": team_id,
                "team_name": team_name,
                "removed_items": removed_items
            }), 200
            
    except Exception as e:
        # Handle general errors
        error_traceback = traceback.format_exc()
        logging.error(f"[{admin_id}] Error in delete_team: {str(e)}\n{error_traceback}")
        print(f"DEBUG ERROR: Exception in delete_team: {str(e)}")
        
        # Log incident for security tracking
        log_incident(admin_id, role, f"Error deleting team: {str(e)}", severity="Medium")
        
        return jsonify({"error": str(e)}), 500
        
    finally:
        # Calculate total execution time
        total_time = time.time() - start_time
        logging.info(f"[{admin_id}] Total execution time: {total_time:.4f} seconds")

@csrf.exempt
@admin_bp.route('/team_management/remove_member', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["remove_team_member"])
def remove_user_from_team(admin_id, role, role_id):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        team_id = request.form.get('team_id')
        employee_id = request.form.get('employee_id')
        admin_id_value = request.form.get('admin_id')

        if not team_id or (not employee_id and not admin_id_value):
            return jsonify({"error": "Missing team_id and employee_id/admin_id"}), 400

        # Check if the member exists in the team
        if employee_id:
            cursor.execute("""
                SELECT id FROM team_members
                WHERE team_id = %s AND employee_id = %s
            """, (team_id, employee_id))
        else:
            cursor.execute("""
                SELECT id FROM team_members
                WHERE team_id = %s AND admin_id = %s
            """, (team_id, admin_id_value))
        row = cursor.fetchone()
        if not row:
            return jsonify({"message": "User is not a member of this team."}), 200

        # Remove the member
        if employee_id:
            cursor.execute("""
                DELETE FROM team_members
                WHERE team_id = %s AND employee_id = %s
            """, (team_id, employee_id))
        else:
            cursor.execute("""
                DELETE FROM team_members
                WHERE team_id = %s AND admin_id = %s
            """, (team_id, admin_id_value))
        connection.commit()

        return jsonify({"message": "User removed from team successfully."}), 200

    except Exception as e:
        if connection:
            connection.rollback()
        tb = traceback.format_exc()
        print(tb)
        return jsonify({"error": str(e), "traceback": tb}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()         

# route for creating a team 
@csrf.exempt
@admin_bp.route('/team_management', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["create_team"])
def create_team(admin_id, role, role_id):
    import logging
    logging.debug(f"[TEAM_MANAGEMENT] Team creation request by admin_id={admin_id}, role={role}")
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # First, check if team_members table has role column, add if missing
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'team_members' AND column_name = 'role'
        """)
        if not cursor.fetchone():
            logging.info("[TEAM_MANAGEMENT] Adding 'role' column to team_members table")
            cursor.execute("""
                ALTER TABLE team_members ADD COLUMN role VARCHAR(50)
            """)
            connection.commit()

        team_name = request.form.get('team_name')
        team_lead_input = request.form.get('team_lead')
        logging.debug(f"[TEAM_MANAGEMENT] Raw team_lead from form: '{team_lead_input}'")

        team_lead_employee_id = None
        team_lead_admin_id = None
        team_lead_email = None  # Store email for logging

        # Normalize identifier for lookup
        if team_lead_input and "@" in team_lead_input:
            identifier = team_lead_input.strip().lower()
            cursor.execute("SELECT employee_id, email FROM employees WHERE LOWER(TRIM(email)) = %s", (identifier,))
            employee = cursor.fetchone()
            cursor.execute("SELECT admin_id, email FROM admins WHERE LOWER(TRIM(email)) = %s", (identifier,))
            admin = cursor.fetchone()
            team_lead_email = identifier  # Store email
        else:
            identifier = team_lead_input.strip()
            cursor.execute("SELECT employee_id, email FROM employees WHERE CAST(employee_id AS TEXT) = %s", (identifier,))
            employee = cursor.fetchone()
            if employee:
                team_lead_employee_id = employee[0]
                email = employee[1].strip().lower() if employee[1] else None
                team_lead_email = email  # Store email
                if email:
                    cursor.execute("SELECT admin_id, email FROM admins WHERE LOWER(TRIM(email)) = %s", (email,))
                    admin = cursor.fetchone()
                else:
                    admin = None
            else:
                email = None
                admin = None

        logging.debug(f"[TEAM_MANAGEMENT] Employee lookup result: {employee}")
        logging.debug(f"[TEAM_MANAGEMENT] Admin lookup result: {admin}")

        # Set both fields if both found, else set only one
        if employee and admin:
            team_lead_employee_id = employee[0]
            team_lead_admin_id = admin[0]
            logging.debug(f"[TEAM_MANAGEMENT] Team lead found in BOTH tables. employee_id={team_lead_employee_id}, admin_id={team_lead_admin_id}")
        elif employee:
            team_lead_employee_id = employee[0]
            logging.debug(f"[TEAM_MANAGEMENT] Team lead found in EMPLOYEES only. employee_id={team_lead_employee_id}")
        elif admin:
            team_lead_admin_id = admin[0]
            logging.debug(f"[TEAM_MANAGEMENT] Team lead found in ADMINS only. admin_id={team_lead_admin_id}")
        else:
            logging.error(f"[TEAM_MANAGEMENT] Team lead not found for identifier: '{identifier}'")
            return jsonify({
                "error": "Team lead not found in employees or admins",
                "debug": {
                    "team_lead_input": team_lead_input,
                    "normalized_identifier": identifier,
                    "employee_lookup": str(employee),
                    "admin_lookup": str(admin)
                }
            }), 400

        members = request.form.getlist('members')
        logging.debug(f"[TEAM_MANAGEMENT] Members received from form: {members}")

        # Insert team with new structure
        cursor.execute(
            """
            INSERT INTO teams (team_name, team_lead_employee_id, team_lead_admin_id, created_at)
            VALUES (%s, %s, %s, NOW()) RETURNING team_id
            """,
            (team_name, team_lead_employee_id, team_lead_admin_id)
        )
        team_id = cursor.fetchone()[0]
        logging.debug(f"[TEAM_MANAGEMENT] Inserted team with team_id: {team_id}")

        # AUTO-INSERT TEAM LEAD AS TEAM MANAGER MEMBER - NEW CODE
        if team_lead_employee_id or team_lead_admin_id:
            logging.debug(f"[TEAM_MANAGEMENT] Auto-inserting team lead as Team Manager in team_members")
            
            if team_lead_employee_id and team_lead_admin_id:
                # Dual role lead
                cursor.execute(
                    """
                    INSERT INTO team_members (team_id, employee_id, admin_id, assigned_at, role) 
                    VALUES (%s, %s, %s, NOW(), 'Team Manager')
                    """,
                    (team_id, team_lead_employee_id, team_lead_admin_id)
                )
                logging.debug(f"[TEAM_MANAGEMENT] Inserted team lead as member with DUAL ROLE: employee_id={team_lead_employee_id}, admin_id={team_lead_admin_id}")
            
            elif team_lead_employee_id:
                # Employee-only lead
                cursor.execute(
                    """
                    INSERT INTO team_members (team_id, employee_id, assigned_at, role) 
                    VALUES (%s, %s, NOW(), 'Team Manager')
                    """,
                    (team_id, team_lead_employee_id)
                )
                logging.debug(f"[TEAM_MANAGEMENT] Inserted team lead as member with EMPLOYEE role: employee_id={team_lead_employee_id}")
            
            elif team_lead_admin_id:
                # Admin-only lead (rare case but handled)
                cursor.execute(
                    """
                    INSERT INTO team_members (team_id, admin_id, assigned_at, role) 
                    VALUES (%s, %s, NOW(), 'Team Manager')
                    """,
                    (team_id, team_lead_admin_id)
                )
                logging.debug(f"[TEAM_MANAGEMENT] Inserted team lead as member with ADMIN role: admin_id={team_lead_admin_id}")
        
        # Process other members
        for employee_id in members:
            # Skip if this is the team lead to avoid duplication
            if employee_id == str(team_lead_employee_id):
                logging.debug(f"[TEAM_MANAGEMENT] Skipping member insert for employee_id={employee_id} as they are already the team lead")
                continue
                
            cursor.execute("SELECT email FROM employees WHERE employee_id = %s", (employee_id,))
            emp_result = cursor.fetchone()
            logging.debug(f"[TEAM_MANAGEMENT] Member employee lookup for employee_id={employee_id}: {emp_result}")
            if emp_result:
                email = emp_result[0].strip().lower() if emp_result[0] else None
                admin_result = None
                if email:
                    cursor.execute("SELECT admin_id FROM admins WHERE LOWER(TRIM(email)) = %s", (email,))
                    admin_result = cursor.fetchone()
                logging.debug(f"[TEAM_MANAGEMENT] Member admin lookup for email={email}: {admin_result}")
                if admin_result:
                    admin_id = admin_result[0]
                    logging.debug(f"[TEAM_MANAGEMENT] Inserting team member: team_id={team_id}, employee_id={employee_id}, admin_id={admin_id} (dual role)")
                    cursor.execute(
                        "INSERT INTO team_members (team_id, employee_id, admin_id, assigned_at, role) VALUES (%s, %s, %s, NOW(), 'Team Member')",
                        (team_id, employee_id, admin_id)
                    )
                else:
                    logging.debug(f"[TEAM_MANAGEMENT] Inserting team member: team_id={team_id}, employee_id={employee_id} (employee only)")
                    cursor.execute(
                        "INSERT INTO team_members (team_id, employee_id, assigned_at, role) VALUES (%s, %s, NOW(), 'Team Member')",
                        (team_id, employee_id)
                    )
            else:
                logging.warning(f"[TEAM_MANAGEMENT] Employee ID {employee_id} not found in employees table, skipping.")

        connection.commit()
        logging.debug(f"[TEAM_MANAGEMENT] Team created and all members inserted successfully.")

        log_audit(
            admin_id, role, "create_team",
            f"Team '{team_name}' (ID: {team_id}) created with lead "
            f"employee_id={team_lead_employee_id} admin_id={team_lead_admin_id} and members {members}"
        )

        return jsonify({"message": "Team created successfully", "team_id": team_id}), 200

    except Exception as e:
        if connection:
            connection.rollback()
        log_incident(admin_id, role, f"Team creation failed: {str(e)}", severity="High")
        logging.error(f"[TEAM_MANAGEMENT][ERROR] Team creation failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
            logging.debug("[TEAM_MANAGEMENT] Cursor closed")
        if connection:
            connection.close()
            logging.debug("[TEAM_MANAGEMENT] DB connection closed")
            
# route for updating employee details

# [Include the helper functions from previous response]
def handle_admin_synchronization(cursor, new_role_id, employee_email, emp_data, employee_id):
    """Handle admin table synchronization based on role changes"""
    admin_id_result = None
    
    if str(new_role_id) in ("1", "3", "4"):
        # Employee should have admin record
        admin_data = {"is_verified": False}
        
        if "profile" in emp_data:
            admin_data["profile_image"] = emp_data["profile"]
        
        for k in ["email", "password", "first_name", "last_name", "role_id", "gender", "date_of_birth"]:
            if k in emp_data:
                admin_data[k] = emp_data[k]
        
        # Remove None/empty values
        admin_cleaned = {k: v for k, v in admin_data.items() if v not in [None, ""]}
        
        # Sync missing fields from employee record
        sync_cols = ["email", "password", "first_name", "last_name", "profile_image", "role_id", "gender", "date_of_birth"]
        for col in sync_cols:
            if col not in admin_cleaned:
                src_col = col if col != "profile_image" else "profile"
                cursor.execute(f"SELECT {src_col} FROM employees WHERE employee_id = %s", (employee_id,))
                row = cursor.fetchone()
                if row and row[0] not in (None, "", b""):
                    admin_cleaned[col] = row[0]
        
        # Check if admin exists
        cursor.execute("SELECT admin_id FROM admins WHERE email = %s", (employee_email,))
        admin_result = cursor.fetchone()
        
        if admin_result:
            # Update existing admin
            admin_id_result = admin_result[0]
            if admin_cleaned:
                admin_columns = list(admin_cleaned.keys())
                admin_values = [admin_cleaned[c] for c in admin_columns]
                set_clause_admin = ", ".join([f"{col} = %s" for col in admin_columns])
                update_admin_sql = f"UPDATE admins SET {set_clause_admin} WHERE admin_id = %s"
                cursor.execute(update_admin_sql, admin_values + [admin_id_result])
                logging.info(f"[UPDATE_EMPLOYEE] Updated admin record (admin_id={admin_id_result})")
        else:
            # Create new admin
            if admin_cleaned:
                admin_columns_sql = ", ".join(admin_cleaned.keys())
                admin_placeholders = ", ".join(["%s"] * len(admin_cleaned))
                admin_values = list(admin_cleaned.values())
                insert_admin_sql = f"INSERT INTO admins ({admin_columns_sql}) VALUES ({admin_placeholders}) RETURNING admin_id"
                cursor.execute(insert_admin_sql, admin_values)
                admin_id_result = cursor.fetchone()[0]
                logging.info(f"[UPDATE_EMPLOYEE] Created new admin record with admin_id={admin_id_result}")
    else:
        # Employee should not have admin record
        cursor.execute("SELECT admin_id FROM admins WHERE email = %s", (employee_email,))
        admin_result = cursor.fetchone()
        if admin_result:
            admin_id_to_remove = admin_result[0]
            cursor.execute("DELETE FROM admins WHERE admin_id = %s", (admin_id_to_remove,))
            logging.info(f"[UPDATE_EMPLOYEE] Removed admin record (admin_id={admin_id_to_remove}) - role no longer admin")
    
    return admin_id_result

def ensure_team_membership_consistency(cursor, employee_id, team_id, role_id, employee_email, first_name, last_name, admin_id=None):
    """
    Ensures team membership consistency regardless of whether changes were made.
    Always checks and corrects team_members table entries.
    Returns True if any team membership changes were made.
    """
    logging.info(f"[TEAM_MEMBERSHIP] Ensuring consistency for employee_id={employee_id}, team_id={team_id}")
    
    membership_updated = False
    
    # Get current team memberships
    cursor.execute("SELECT team_id, role FROM team_members WHERE employee_id = %s", (employee_id,))
    current_memberships = cursor.fetchall()
    current_team_ids = [str(row[0]) for row in current_memberships]
    
    logging.debug(f"[TEAM_MEMBERSHIP] Current memberships: {current_team_ids}")
    
    # Scenario 1: Employee should have a team
    if team_id and str(team_id).strip():
        target_team_id = str(team_id)
        
        # Check if employee is already in the correct team
        if target_team_id not in current_team_ids:
            # Remove from all other teams first
            if current_memberships:
                cursor.execute("DELETE FROM team_members WHERE employee_id = %s", (employee_id,))
                logging.info(f"[TEAM_MEMBERSHIP] Removed employee from teams: {current_team_ids}")
                membership_updated = True
            
            # Determine appropriate role for the team
            cursor.execute("SELECT team_lead_employee_id FROM teams WHERE team_id = %s", (target_team_id,))
            team_lead_result = cursor.fetchone()
            
            if team_lead_result and str(team_lead_result[0]) == str(employee_id):
                member_role = "Team Manager"
                logging.info(f"[TEAM_MEMBERSHIP] Employee is Team Manager for team_id={target_team_id}")
            else:
                member_role = "Team Member"
                logging.info(f"[TEAM_MEMBERSHIP] Employee is Team Member for team_id={target_team_id}")
            
            # Insert into team_members
            if admin_id:
                cursor.execute("""
                    INSERT INTO team_members (team_id, employee_id, admin_id, assigned_at, role) 
                    VALUES (%s, %s, %s, NOW(), %s)
                """, (target_team_id, employee_id, admin_id, member_role))
                logging.info(f"[TEAM_MEMBERSHIP] Added dual-role member to team_id={target_team_id}")
            else:
                cursor.execute("""
                    INSERT INTO team_members (team_id, employee_id, assigned_at, role) 
                    VALUES (%s, %s, NOW(), %s)
                """, (target_team_id, employee_id, member_role))
                logging.info(f"[TEAM_MEMBERSHIP] Added employee-only member to team_id={target_team_id}")
            
            membership_updated = True
            
        elif current_memberships:
            # Employee is in the right team, but verify role consistency
            current_membership = next((m for m in current_memberships if str(m[0]) == target_team_id), None)
            if current_membership:
                current_role = current_membership[1]
                
                # Check if role needs updating
                cursor.execute("SELECT team_lead_employee_id FROM teams WHERE team_id = %s", (target_team_id,))
                team_lead_result = cursor.fetchone()
                
                expected_role = "Team Manager" if (team_lead_result and str(team_lead_result[0]) == str(employee_id)) else "Team Member"
                
                if current_role != expected_role:
                    cursor.execute("""
                        UPDATE team_members SET role = %s 
                        WHERE employee_id = %s AND team_id = %s
                    """, (expected_role, employee_id, target_team_id))
                    logging.info(f"[TEAM_MEMBERSHIP] Updated role from '{current_role}' to '{expected_role}' for team_id={target_team_id}")
                    membership_updated = True
                
                # If employee has multiple team memberships but should only be in one, clean up
                if len(current_memberships) > 1:
                    cursor.execute("""
                        DELETE FROM team_members 
                        WHERE employee_id = %s AND team_id != %s
                    """, (employee_id, target_team_id))
                    removed_teams = [str(m[0]) for m in current_memberships if str(m[0]) != target_team_id]
                    logging.info(f"[TEAM_MEMBERSHIP] Cleaned up extra team memberships: {removed_teams}")
                    membership_updated = True
    
    # Scenario 2: Employee should not have any team
    else:
        if current_memberships:
            cursor.execute("DELETE FROM team_members WHERE employee_id = %s", (employee_id,))
            logging.info(f"[TEAM_MEMBERSHIP] Removed employee from all teams: {current_team_ids}")
            membership_updated = True
    
    if membership_updated:
        logging.info(f"[TEAM_MEMBERSHIP] Team membership updated for employee_id={employee_id}")
    else:
        logging.debug(f"[TEAM_MEMBERSHIP] Team membership already consistent for employee_id={employee_id}")
    
    return membership_updated

@admin_bp.route('/update_employee/<int:employee_id>', methods=['GET', 'POST'])
@token_required_with_roles_and_2fa(required_actions=["update_employee"])
def update_employee(admin_id, role, role_id, employee_id):
    import psycopg2
    import bcrypt
    import base64
    import logging
    from datetime import date, datetime

    logging.info(f"[UPDATE_EMPLOYEE] Request initiated by admin_id={admin_id}, role={role} for employee_id={employee_id}")

    emp_allowed_columns = [
        "first_name", "last_name", "email", "phone_number", "department", "salary", "status",
        "date_hired", "date_terminated", "profile", "account_status", "address1", "city",
        "address2", "password", "skills", "certification", "education", "language", "hobbies",
        "goal_id", "team_id", "announcement_id", "role_id", "current_jti", "gender", "date_of_birth"
    ]

    # Define date columns that need special handling
    date_columns = ["date_hired", "date_terminated", "date_of_birth"]

    if request.method == "GET":
        # [GET logic remains the same]
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT employee_id, first_name, last_name, email, phone_number, department, salary,
                    status, date_hired, date_terminated, profile, created, account_status, address1, city, address2,
                    password, skills, certification, education, language, hobbies, goal_id, team_id, announcement_id,
                    role_id, current_jti, gender, date_of_birth
                FROM employees
                WHERE employee_id=%s
            """, (employee_id,))
            emp = cursor.fetchone()
            if not emp:
                logging.warning(f"[UPDATE_EMPLOYEE] Employee ID {employee_id} not found")
                return jsonify({"error": "Employee not found"}), 404

            # Profile image
            profile_image = emp[10]
            profile_image_base64 = (
                f"data:image/jpeg;base64,{base64.b64encode(profile_image).decode('utf-8')}"
                if profile_image else None
            )
            # Build employee dict
            employee = {
                "employee_id": emp[0],
                "first_name": emp[1],
                "last_name": emp[2],
                "email": emp[3],
                "phone_number": emp[4],
                "department": emp[5],
                "salary": emp[6],
                "status": emp[7],
                "date_hired": emp[8].isoformat() if isinstance(emp[8], (date, datetime)) and emp[8] else "",
                "date_terminated": emp[9].isoformat() if isinstance(emp[9], (date, datetime)) and emp[9] else "",
                "profile_image": profile_image_base64,
                "created": emp[11].isoformat() if isinstance(emp[11], (date, datetime)) and emp[11] else "",
                "account_status": emp[12],
                "address1": emp[13],
                "city": emp[14],
                "address2": emp[15],
                "skills": emp[17],
                "certification": emp[18],
                "education": emp[19],
                "language": emp[20],
                "hobbies": emp[21],
                "goal_id": emp[22],
                "team_id": emp[23],
                "announcement_id": emp[24],
                "role_id": emp[25],
                "current_jti": emp[26],
                "gender": emp[27],
                "date_of_birth": emp[28].isoformat() if isinstance(emp[28], (date, datetime)) and emp[28] else "",
            }

            cursor.execute("SELECT team_id, team_name FROM teams ORDER BY team_name")
            teams = [{"team_id": row[0], "team_name": row[1]} for row in cursor.fetchall()]

            cursor.execute("SELECT role_id, role_name FROM roles ORDER BY role_name")
            roles = [{"role_id": row[0], "role_name": row[1]} for row in cursor.fetchall()]

            logging.info(f"[UPDATE_EMPLOYEE] Successfully retrieved employee data for employee_id={employee_id}")
            return jsonify({"employee": employee, "teams": teams, "roles": roles})

        finally:
            cursor.close()
            conn.close()
            logging.debug("[UPDATE_EMPLOYEE] DB connection closed for GET request")

    # ---------- POST method: update employee ----------
    logging.info(f"[UPDATE_EMPLOYEE] Processing POST request to update employee_id={employee_id}")
    
    conn = None
    cursor = None
    
    try:
        # Initialize database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Ensure team_members table has role column
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'team_members' AND column_name = 'role'
        """)
        if not cursor.fetchone():
            logging.info("[UPDATE_EMPLOYEE] Adding 'role' column to team_members table")
            cursor.execute("ALTER TABLE team_members ADD COLUMN role VARCHAR(50)")
            conn.commit()
        
        # Get current employee data FIRST for comprehensive comparison
        cursor.execute(
            "SELECT team_id, role_id, email, first_name, last_name FROM employees WHERE employee_id = %s", 
            (employee_id,)
        )
        current_emp = cursor.fetchone()
        if not current_emp:
            logging.warning(f"[UPDATE_EMPLOYEE] Employee ID {employee_id} not found during update")
            return jsonify({"error": "Employee not found"}), 404
            
        current_team_id = current_emp[0]
        current_role_id = str(current_emp[1]) if current_emp[1] else ""
        employee_email = current_emp[2]
        employee_first_name = current_emp[3]
        employee_last_name = current_emp[4]
        
        logging.info(f"[UPDATE_EMPLOYEE] Current employee data - team_id: {current_team_id}, role_id: {current_role_id}, email: {employee_email}")
        
        # Gather form data to update with PROPER DATE HANDLING
        emp_data = {}
        form_has_data = False  # Track if any form data was actually submitted
        
        for col in emp_allowed_columns:
            if col == "profile":
                file = request.files.get("profile")
                if file and file.filename:
                    emp_data[col] = psycopg2.Binary(file.read())
                    form_has_data = True
                    logging.debug("[UPDATE_EMPLOYEE] New profile image processed")
            elif col == "password":
                pwd = request.form.get("password")
                if pwd and pwd.strip():  # Only process non-empty passwords
                    emp_data[col] = bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")
                    form_has_data = True
                    logging.debug("[UPDATE_EMPLOYEE] New password hashed")
            elif col in request.form:
                val = request.form.get(col)
                
                # ENHANCED DATE FIELD HANDLING
                if col in date_columns:
                    if val and val.strip():  # Only update if date value is provided and not empty
                        try:
                            # Validate date format
                            datetime.strptime(val, '%Y-%m-%d')
                            emp_data[col] = val
                            form_has_data = True
                            logging.debug(f"[UPDATE_EMPLOYEE] Valid date provided for {col}: {val}")
                        except ValueError:
                            logging.warning(f"[UPDATE_EMPLOYEE] Invalid date format for {col}: {val}")
                            return jsonify({"error": f"Invalid date format for {col}. Use YYYY-MM-DD format."}), 400
                    else:
                        # Empty date field - skip it to preserve existing value
                        logging.debug(f"[UPDATE_EMPLOYEE] Empty date field {col} - preserving existing value")
                        continue
                else:
                    # Non-date fields - handle normally
                    if val is not None:  # Accept empty strings for non-date fields
                        emp_data[col] = val
                        form_has_data = True

        # NEW LOGIC: Handle no-change scenario gracefully
        if not form_has_data:
            logging.info("[UPDATE_EMPLOYEE] No form data submitted - performing team membership verification only")
            
            # Still verify and fix team membership even with no changes
            team_membership_updated = ensure_team_membership_consistency(
                cursor, employee_id, current_team_id, current_role_id, 
                employee_email, employee_first_name, employee_last_name
            )
            
            conn.commit()
            
            return jsonify({
                "message": "No changes made to employee data. Team membership verified.",
                "team_updated": team_membership_updated,
                "role_updated": False
            }), 200

        # Determine what's changing
        new_team_id = emp_data.get("team_id", current_team_id)
        new_role_id = emp_data.get("role_id", current_role_id)
        
        team_changing = str(new_team_id) != str(current_team_id)
        role_changing = str(new_role_id) != str(current_role_id)
        
        if team_changing:
            logging.info(f"[UPDATE_EMPLOYEE] Team changing from {current_team_id} to {new_team_id}")
        if role_changing:
            logging.info(f"[UPDATE_EMPLOYEE] Role changing from {current_role_id} to {new_role_id}")

        # Security check: Prevent super_admin role assignment
        if str(new_role_id) == "2":
            logging.warning(f"[UPDATE_EMPLOYEE] Attempt to set super_admin role for employee_id={employee_id}")
            return jsonify({"error": "You cannot set super_admin using this interface."}), 403

        # Update employee record only if there are changes
        if emp_data:
            emp_columns = list(emp_data.keys())
            emp_values = list(emp_data.values())
            set_clause = ", ".join([f"{col} = %s" for col in emp_columns])
            update_sql = f"UPDATE employees SET {set_clause} WHERE employee_id = %s"
            
            cursor.execute(update_sql, emp_values + [employee_id])
            logging.info(f"[UPDATE_EMPLOYEE] Updated employee record with fields: {', '.join(emp_columns)}")

        # Admin table synchronization logic
        admin_id_result = handle_admin_synchronization(
            cursor, new_role_id, employee_email, emp_data, employee_id
        )

        # ENHANCED TEAM MEMBERSHIP MANAGEMENT - ALWAYS RUNS
        team_membership_updated = ensure_team_membership_consistency(
            cursor, employee_id, new_team_id, new_role_id, 
            employee_email, 
            emp_data.get("first_name", employee_first_name),
            emp_data.get("last_name", employee_last_name),
            admin_id_result
        )
        
        # Commit all changes
        conn.commit()
        
        # Log audit record
        log_audit(
            admin_id, role, "update_employee", 
            f"Updated employee (ID: {employee_id}, fields: {list(emp_data.keys()) if emp_data else []}, " +
            f"team_changed: {team_changing}, role_changed: {role_changing})"
        )
        
        logging.info(f"[UPDATE_EMPLOYEE] Successfully updated employee_id={employee_id}")
        return jsonify({
            "message": "Employee updated successfully.",
            "team_updated": team_changing or team_membership_updated,
            "role_updated": role_changing
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"[UPDATE_EMPLOYEE][ERROR] Failed to update employee: {str(e)}", exc_info=True)
        log_incident(admin_id, role, f"Error updating employee: {str(e)}", severity="High")
        return jsonify({"error": f"Error: {e}"}), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        logging.debug("[UPDATE_EMPLOYEE] Database connections closed")

# route for terminating employee status in database
@csrf.exempt
@admin_bp.route('/terminate/<int:employee_id>', methods=['PATCH'])
@token_required_with_roles_and_2fa(required_actions=["terminate_employee"])
def terminate_employee(admin_id, role, role_id,employee_id):
    connection = None
    cursor = None
    try:
        logging.info(f"[TERMINATE_EMPLOYEE] Admin ID: {admin_id}, Role: {role}, Target Employee ID: {employee_id}")
        connection = get_db_connection()
        cursor = connection.cursor()
        logging.info("[TERMINATE_EMPLOYEE] Database connection established.")

        cursor.execute(
            "UPDATE employees SET account_status = 'Terminated', date_terminated = CURRENT_DATE WHERE employee_id = %s",
            (employee_id,)
        )
        connection.commit()
        logging.info(f"[TERMINATE_EMPLOYEE] Employee ID {employee_id} marked as Terminated.")

        # Audit: log successful termination
        log_audit(admin_id, role, "terminate_employee", f"Terminated employee ID {employee_id}")
        logging.info(f"[TERMINATE_EMPLOYEE] Audit log created for employee ID {employee_id}.")

    except psycopg2.Error as e:
        # Incident: log database error
        log_incident(admin_id, role, f"Database error during termination of employee {employee_id}: {e.pgerror}", severity="High")
        logging.error(f"[TERMINATE_EMPLOYEE][DB_ERROR] {e.pgcode} - {e.pgerror}", exc_info=True)
        flash("An error occurred while terminating the employee.", "danger")

    finally:
        if cursor:
            cursor.close()
            logging.info("[TERMINATE_EMPLOYEE] Cursor closed.")
        if connection:
            connection.close()
            logging.info("[TERMINATE_EMPLOYEE] Database connection closed.")

    return jsonify({'message': 'Employee successfully terminated.'}), 200


# route for activating employee status in database
@csrf.exempt
@admin_bp.route('/activate/<int:employee_id>', methods=['PATCH'])
@token_required_with_roles_and_2fa(required_actions=["activate_employee"])
def activate_employee(admin_id, role,role_id ,employee_id):
    connection = None
    cursor = None
    try:
        logging.info(f"[ACTIVATE_EMPLOYEE] Admin ID: {admin_id}, Role: {role}, Target Employee ID: {employee_id}")
        connection = get_db_connection()
        cursor = connection.cursor()
        logging.info("[ACTIVATE_EMPLOYEE] Database connection established.")

        cursor.execute(
            "UPDATE employees SET account_status = 'Activated', date_terminated = NULL WHERE employee_id = %s",
            (employee_id,)
        )
        connection.commit()
        logging.info(f"[ACTIVATE_EMPLOYEE] Employee ID {employee_id} activated.")

        # Audit: log successful activation
        log_audit(admin_id, role, "activate_employee", f"Activated employee ID {employee_id}")
        logging.info(f"[ACTIVATE_EMPLOYEE] Audit log created for employee ID {employee_id}.")

    except psycopg2.Error as e:
        # Incident: log database error
        log_incident(admin_id, role, f"Database error during activation of employee {employee_id}: {e.pgerror}", severity="High")
        logging.error(f"[ACTIVATE_EMPLOYEE][DB_ERROR] {e.pgcode} - {e.pgerror}", exc_info=True)
        flash("An error occurred while activating the employee.", "danger")

    finally:
        if cursor:
            cursor.close()
            logging.info("[ACTIVATE_EMPLOYEE] Cursor closed.")
        if connection:
            connection.close()
            logging.info("[ACTIVATE_EMPLOYEE] Database connection closed.")

    return jsonify({'message': 'Employee successfully activated.'}), 200


# route for deactivating employee status in database
@csrf.exempt
@admin_bp.route('/deactivate/<int:employee_id>', methods=['PATCH'])
@token_required_with_roles_and_2fa(required_actions=["deactivate_employee"])
def deactivate_employee(admin_id, role, role_id,employee_id):
    connection = None
    cursor = None
    try:
        logging.info(f"[DEACTIVATE_EMPLOYEE] Admin ID: {admin_id}, Role: {role}, Target Employee ID: {employee_id}")
        connection = get_db_connection()
        cursor = connection.cursor()
        logging.info("[DEACTIVATE_EMPLOYEE] Database connection established.")

        cursor.execute(
            "UPDATE employees SET account_status = 'Deactivated', date_terminated = NULL WHERE employee_id = %s",
            (employee_id,)
        )
        connection.commit()
        logging.info(f"[DEACTIVATE_EMPLOYEE] Employee ID {employee_id} deactivated.")

        # Audit: log successful deactivation
        log_audit(admin_id, role, "deactivate_employee", f"Deactivated employee ID {employee_id}")
        logging.info(f"[DEACTIVATE_EMPLOYEE] Audit log created for employee ID {employee_id}.")

    except psycopg2.Error as e:
        # Incident: log database error
        log_incident(admin_id, role, f"Database error during deactivation of employee {employee_id}: {e.pgerror}", severity="High")
        logging.error(f"[DEACTIVATE_EMPLOYEE][DB_ERROR] {e.pgcode} - {e.pgerror}", exc_info=True)
        flash("An error occurred while deactivating the employee.", "danger")

    finally:
        if cursor:
            cursor.close()
            logging.info("[DEACTIVATE_EMPLOYEE] Cursor closed.")
        if connection:
            connection.close()
            logging.info("[DEACTIVATE_EMPLOYEE] Database connection closed.")

    return jsonify({'message': 'Employee successfully deactivated.'}), 200

# Employee management ( End )

