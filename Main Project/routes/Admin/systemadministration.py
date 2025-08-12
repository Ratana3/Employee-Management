    
from datetime import datetime, timedelta
import logging
import os
import subprocess
import bcrypt
from flask import Blueprint, Response, render_template, jsonify, request, send_file, send_from_directory, url_for
import psycopg2
from routes.Auth.audit import log_audit, log_incident
from routes.Auth.token import token_required_with_roles, token_required_with_roles_and_2fa
from routes.Auth.utils import get_db_connection
from routes.Auth.config import BACKUP_DIR, DB_HOST, DB_NAME, DB_PASSWORD, DB_USER, PG_DUMP_PATH, PG_PSQL_PATH
from . import admin_bp
from extensions import csrf

# Fetch Leave Balances
@admin_bp.route('/api/leave-balances', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_leave_balances"])
def get_leave_balances(admin_id, role, role_id):
    logging.debug(f"get_leave_balances called by admin_id={admin_id}, role={role}, role_id={role_id}")
    try:
        logging.debug("Attempting to get DB connection...")
        conn = get_db_connection()
        logging.debug("DB connection established.")
        cursor = conn.cursor()
        logging.debug("DB cursor created.")

        query = """
        SELECT lb.balance_id, lb.employee_id, e.first_name, e.last_name, e.email,
               lb.sick_leave, lb.vacation_leave, lb.personal_leave, lb.unpaid_leave
        FROM leave_balances AS lb
        JOIN employees AS e ON lb.employee_id = e.employee_id
        ORDER BY e.first_name, e.last_name;
        """

        logging.debug(f"Executing query: {query}")

        cursor.execute(query)
        balances = cursor.fetchall()
        logging.debug(f"Query executed. Rows fetched: {len(balances)}")
        
        # Structure data
        balances_list = []
        for idx, row in enumerate(balances):
            logging.debug(f"Row {idx}: {row}")
            balances_list.append({
                "balance_id": row[0],
                "employee_id": row[1],
                "employee_name": f"{row[2]} {row[3]}",
                "employee_email": row[4],
                "sick_leave": row[5],
                "vacation_leave": row[6],
                "personal_leave": row[7],
                "unpaid_leave": row[8]
            })
        logging.debug(f"Structured balances_list: {balances_list}")

        # Audit: log leave balances fetch
        log_audit(admin_id, role, "get_leave_balances", "Fetched all leave balances")
        logging.debug("Audit log recorded for leave balances fetch.")

        logging.debug("Returning balances_list as JSON.")
        return jsonify(balances_list)

    except Exception as e:
        logging.error(f"Error fetching leave balances: {str(e)}", exc_info=True)
        log_incident(admin_id, role, f"Error fetching leave balances: {e}", severity="High")
        return jsonify({"error": "Failed to fetch leave balances"}), 500

    finally:
        try:
            if cursor:
                cursor.close()
                logging.debug("DB cursor closed.")
        except Exception as e:
            logging.error(f"Error closing cursor: {str(e)}")
        try:
            if conn:
                conn.close()
                logging.debug("Database connection closed.")
        except Exception as e:
            logging.error(f"Error closing connection: {str(e)}")
            
# Get Employee Leave Balance Details
@admin_bp.route('/api/leave-balances/<int:employee_id>', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_employee_leave_details"])
def get_employee_leave_details(admin_id, role, role_id, employee_id):
    logging.debug(f"Fetching leave balance details for employee_id: {employee_id}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
        SELECT lb.balance_id, lb.employee_id, e.first_name, e.last_name, e.email,
               lb.sick_leave, lb.vacation_leave, lb.personal_leave, lb.unpaid_leave
        FROM leave_balances AS lb
        JOIN employees AS e ON lb.employee_id = e.employee_id
        WHERE lb.employee_id = %s;
        """

        cursor.execute(query, (employee_id,))
        balance = cursor.fetchone()

        if not balance:
            log_incident(admin_id, role, f"Employee leave balance not found for employee_id {employee_id}", severity="Low")
            return jsonify({"error": "Employee leave balance not found"}), 404

        balance_details = {
            "balance_id": balance[0],
            "employee_id": balance[1],
            "employee_name": f"{balance[2]} {balance[3]}",
            "employee_email": balance[4],
            "leave_types": {
                "sick_leave": balance[5],
                "vacation_leave": balance[6],
                "personal_leave": balance[7],
                "unpaid_leave": balance[8]
            }
        }

        # Audit: log employee leave balance fetch
        log_audit(admin_id, role, "get_employee_leave_details", f"Fetched leave details for employee_id {employee_id}")

        return jsonify(balance_details)

    except Exception as e:
        logging.error(f"Error fetching employee leave details: {str(e)}", exc_info=True)
        log_incident(admin_id, role, f"Error fetching leave details for employee_id {employee_id}: {e}", severity="High")
        return jsonify({"error": "Failed to fetch employee leave details"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            logging.debug("Database connection closed.")


# Edit Leave Balance Amount
@csrf.exempt
@admin_bp.route('/api/leave-balances/<int:employee_id>/edit', methods=['PUT'])
@token_required_with_roles_and_2fa(required_actions=["edit_leave_balance"])
def edit_leave_balance(admin_id, role, role_id, employee_id):
    logging.debug(f"Editing leave balance for employee_id: {employee_id}")
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build dynamic update query based on provided leave types
        update_parts = []
        params = []
        
        if 'sick_leave' in data and data['sick_leave'] >= 0:
            update_parts.append("sick_leave = %s")
            params.append(data['sick_leave'])
        
        if 'vacation_leave' in data and data['vacation_leave'] >= 0:
            update_parts.append("vacation_leave = %s")
            params.append(data['vacation_leave'])
        
        if 'personal_leave' in data and data['personal_leave'] >= 0:
            update_parts.append("personal_leave = %s")
            params.append(data['personal_leave'])
        
        if 'unpaid_leave' in data and data['unpaid_leave'] >= 0:
            update_parts.append("unpaid_leave = %s")
            params.append(data['unpaid_leave'])

        if not update_parts:
            return jsonify({"error": "No valid leave types to update"}), 400

        params.append(employee_id)
        query = f"""
        UPDATE leave_balances 
        SET {', '.join(update_parts)}
        WHERE employee_id = %s;
        """

        cursor.execute(query, params)
        
        if cursor.rowcount == 0:
            log_incident(admin_id, role, f"Employee leave balance not found for editing: employee_id {employee_id}", severity="Low")
            return jsonify({"error": "Employee leave balance not found"}), 404

        conn.commit()

        # Audit: log leave balance edit
        log_audit(admin_id, role, "edit_leave_balance", f"Edited leave balance for employee_id {employee_id}")

        return jsonify({"message": "Leave balance updated successfully"})

    except Exception as e:
        logging.error(f"Error editing leave balance: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
        log_incident(admin_id, role, f"Error editing leave balance for employee_id {employee_id}: {e}", severity="High")
        return jsonify({"error": "Failed to edit leave balance"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            logging.debug("Database connection closed.")

# View Holiday
@admin_bp.route("/holidays/view", methods=["GET"])
@token_required_with_roles_and_2fa(required_actions=["view_holiday"])
def view_holiday(admin_id, role, role_id):
    holiday_id = request.args.get("holiday_id")
    if not holiday_id:
        return jsonify({"error": "Holiday ID is required"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Fetch holiday details
        cur.execute("SELECT holiday_name, holiday_date FROM holidays WHERE id = %s", (holiday_id,))
        holiday = cur.fetchone()
        
        if not holiday:
            log_incident(admin_id, role, f"Holiday not found: holiday_id {holiday_id}", severity="Low")
            return jsonify({"error": "Holiday not found"}), 404

        holiday_name, holiday_date = holiday

        # Fetch assigned employees and teams in one query
        cur.execute("""
            SELECT 
                e.email AS employee_email, 
                t.team_name AS team_name
            FROM holiday_assignments ha
            LEFT JOIN employees e ON ha.employee_id = e.employee_id
            LEFT JOIN teams t ON ha.team_id = t.team_id
            WHERE ha.holiday_id = %s
        """, (holiday_id,))

        assigned_employees = []
        assigned_teams = []

        for row in cur.fetchall():
            if row[0]:  # If employee email exists
                assigned_employees.append(row[0])
            if row[1]:  # If team name exists
                assigned_teams.append(row[1])

        cur.close()
        conn.close()

        # Audit: log holiday view
        log_audit(admin_id, role, "view_holiday", f"Viewed holiday ID {holiday_id}")

        return jsonify({
            "holiday_name": holiday_name,
            "date": holiday_date,
            "assigned_employees": assigned_employees,
            "assigned_teams": assigned_teams
        })

    except Exception as e:
        print(f"Error fetching holiday details: {e}")
        log_incident(admin_id, role, f"Error fetching holiday details for holiday_id {holiday_id}: {e}", severity="High")
        return jsonify({"error": "An error occurred while fetching holiday details"}), 500
        
# Edit Holiday
# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

@csrf.exempt
@admin_bp.route('/holidays/edit', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["edit_holiday"])
def edit_holiday(admin_id, role, role_id):
    try:
        data = request.json
        logging.debug(f"Request data: {data}")

        holiday_id = data.get("holiday_id")
        holiday_name = data.get("holiday_name")
        date = data.get("date")
        selection_type = data.get("selection_type")
        selected_ids = data.get("selected_ids", [])
        is_paid = data.get("is_paid")

        if not holiday_id:
            return jsonify({"error": "Holiday ID is required."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # ✅ Update only the holiday details in `holidays`
        cursor.execute(
            """
            UPDATE holidays 
            SET holiday_name = COALESCE(%s, holiday_name),
                holiday_date = COALESCE(%s, holiday_date),
                is_paid = COALESCE(%s, is_paid)
            WHERE id = %s
            """,
            (holiday_name, date, is_paid, holiday_id),
        )
        logging.info(f"Updated holiday {holiday_id} in the database.")

        # ✅ Delete previous assignments
        cursor.execute("DELETE FROM holiday_assignments WHERE holiday_id = %s", (holiday_id,))
        logging.debug(f"Deleted previous assignments for holiday_id: {holiday_id}")

        # ✅ Insert new assignments
        for selected_id in selected_ids:
            # Check if the ID belongs to a team or an employee
            cursor.execute("SELECT COUNT(*) FROM employees WHERE employee_id = %s", (selected_id,))
            is_employee = cursor.fetchone()[0] > 0

            cursor.execute("SELECT COUNT(*) FROM teams WHERE team_id = %s", (selected_id,))
            is_team = cursor.fetchone()[0] > 0

            if is_employee:
                logging.info(f"Assigning employee {selected_id} to holiday {holiday_id}")
                cursor.execute(
                    """
                    INSERT INTO holiday_assignments (holiday_id, employee_id)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING
                    """,
                    (holiday_id, selected_id),
                )

            if is_team:
                logging.info(f"Assigning team {selected_id} to holiday {holiday_id}")
                cursor.execute(
                    """
                    INSERT INTO holiday_assignments (holiday_id, team_id)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING
                    """,
                    (holiday_id, selected_id),
                )

        # ✅ Commit and close
        conn.commit()
        cursor.close()
        conn.close()

        logging.info(f"Holiday {holiday_id} updated successfully with new assignments.")
        # Audit: log holiday edit
        log_audit(admin_id, role, "edit_holiday", f"Edited holiday ID {holiday_id}")
        return jsonify({"message": "Holiday updated successfully."})

    except Exception as e:
        logging.error(f"Error updating holiday: {str(e)}", exc_info=True)
        log_incident(admin_id, role, f"Error updating holiday ID {holiday_id}: {e}", severity="High")
        return jsonify({"error": "An error occurred while updating the holiday."}), 500

# Delete Holiday
@csrf.exempt
@admin_bp.route('/holidays/delete', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["delete_holiday"])
def delete_holiday(admin_id, role, role_id):
    data = request.json
    holiday_id = data.get("holiday_id")
    
    if not holiday_id:
        return jsonify({"error": "Invalid holiday ID."})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM holidays WHERE id = %s", (holiday_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted == 0:
        # Incident: log not found
        log_incident(admin_id, role, f"Attempted to delete non-existent holiday ID {holiday_id}", severity="Low")
        return jsonify({"error": "Holiday not found"}), 404

    # Audit: log holiday delete
    log_audit(admin_id, role, "delete_holiday", f"Deleted holiday ID {holiday_id}")
    return jsonify({"message": "Holiday deleted successfully."})

# DELETE leave request
@csrf.exempt
@admin_bp.route('/leave_requests/delete', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["delete_leave_request"])
def delete_leave_request(admin_id, role, role_id):
    data = request.json
    request_id = data.get("request_id")

    logging.debug(f"Received delete request for ID: {request_id}")

    if not request_id or request_id == "undefined":
        logging.error("Delete failed: Request ID is missing or invalid")
        return jsonify({"error": "Request ID is required and must be valid"}), 400

    try:
        logging.debug(f"Connecting to database to delete leave request ID: {request_id}")
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM leave_requests WHERE request_id = %s", (request_id,))
            deleted = cursor.rowcount
            conn.commit()
            logging.debug(f"Leave request {request_id} deleted from database")

        if deleted == 0:
            log_incident(admin_id, role, f"Attempted to delete non-existent leave request ID {request_id}", severity="Low")
            return jsonify({"error": "Leave request not found"}), 404

        # Audit: log leave request delete
        log_audit(admin_id, role, "delete_leave_request", f"Deleted leave request ID {request_id}")
        logging.info(f"Leave request {request_id} deleted successfully")
        return jsonify({"message": "Leave request deleted successfully"})

    except Exception as e:
        logging.exception(f"Delete failed for leave request ID {request_id}: {str(e)}")
        log_incident(admin_id, role, f"Error deleting leave request ID {request_id}: {e}", severity="High")
        return jsonify({"error": "Delete failed", "details": str(e)}), 500

# EDIT leave request
@csrf.exempt
@admin_bp.route('/leave_requests/edit', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["edit_leave_request"])
def edit_leave_request(admin_id, role, role_id):
    data = request.get_json()

    if not data:
        logging.error("Edit failed: No JSON data received")
        return jsonify({"error": "Invalid request. No data received."}), 400

    request_id = data.get("request_id")
    leave_type = data.get("leave_type")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    status = data.get("status")
    remarks = data.get("remarks")

    if not request_id:
        logging.error("Edit failed: Request ID is missing")
        return jsonify({"error": "Request ID is required"}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Check if leave request exists
            cursor.execute("SELECT COUNT(*) FROM leave_requests WHERE request_id = %s", (request_id,))
            exists = cursor.fetchone()[0]
            if exists == 0:
                logging.warning(f"Leave request {request_id} not found")
                log_incident(admin_id, role, f"Attempted to edit non-existent leave request ID {request_id}", severity="Low")
                return jsonify({"error": "Leave request not found"}), 404

            # Debug: Fetch existing leave request details
            cursor.execute("SELECT * FROM leave_requests WHERE request_id = %s", (request_id,))
            existing_request = cursor.fetchone()
            logging.debug(f"Existing leave request details: {existing_request}")

            # Calculate total_days if start_date and end_date are provided
            total_days = None
            if start_date and end_date:
                cursor.execute("SELECT DATE(%s) - DATE(%s) + 1", (end_date, start_date))
                total_days = cursor.fetchone()[0]

            # Debug: Log values before updating
            logging.info(f"Updating leave request {request_id} with: "
                         f"leave_type={leave_type}, start_date={start_date}, end_date={end_date}, "
                         f"total_days={total_days}, status={status}, remarks={remarks}")

            # Debug: Fetch allowed status values
            cursor.execute("""
                SELECT conname, pg_get_constraintdef(oid) 
                FROM pg_constraint 
                WHERE conrelid = 'leave_requests'::regclass
                AND conname = 'leave_requests_status_check'
            """)
            status_constraint = cursor.fetchone()
            logging.debug(f"Status constraint found: {status_constraint}")

            # Debug: Print available statuses if constraint is found
            if status_constraint:
                logging.debug(f"Check constraint details: {status_constraint[1]}")

            # Perform update
            cursor.execute("""
                UPDATE leave_requests 
                SET leave_type = %s, start_date = %s, end_date = %s, total_days = %s, status = %s, remarks = %s 
                WHERE request_id = %s
            """, (leave_type, start_date, end_date, total_days, status, remarks, request_id))
            conn.commit()

            # Audit: log leave request edit
            log_audit(admin_id, role, "edit_leave_request", f"Edited leave request ID {request_id}")

            logging.info(f"Leave request {request_id} updated successfully")

        return jsonify({"message": "Leave request updated successfully"})

    except Exception as e:
        logging.exception(f"Update failed for leave request ID {request_id}: {str(e)}")
        log_incident(admin_id, role, f"Error editing leave request ID {request_id}: {e}", severity="High")
        # Debug: Return more details about the error
        return jsonify({
            "error": "Update failed",
            "details": str(e),
            "debug_info": {
                "request_id": request_id,
                "leave_type": leave_type,
                "start_date": start_date,
                "end_date": end_date,
                "total_days": total_days if 'total_days' in locals() else None,
                "status": status,
                "remarks": remarks
            }
        }), 500

# VIEW leave request details with employee name
@admin_bp.route('/leave_requests/view', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["view_leave_request"])
def view_leave_request(admin_id, role, role_id):
    request_id = request.args.get("request_id")
    if not request_id:
        return jsonify({"error": "Missing request_id"}), 400

    logging.debug(f"Fetching leave request with ID: {request_id}")

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT lr.request_id, lr.leave_type, lr.start_date, lr.end_date, lr.total_days, lr.status, lr.remarks,
                       e.employee_id, e.email 
                FROM leave_requests lr
                JOIN employees e ON lr.employee_id = e.employee_id
                WHERE lr.request_id = %s
            """, (request_id,))
            leave_request = cursor.fetchone()

        if not leave_request:
            log_incident(admin_id, role, f"Leave request not found: request_id {request_id}", severity="Low")
            return jsonify({"error": "Leave request not found"}), 404

        leave_request_dict = {
            "request_id": leave_request[0],
            "leave_type": leave_request[1],
            "start_date": leave_request[2],
            "end_date": leave_request[3],
            "total_days": leave_request[4],
            "status": leave_request[5],
            "remarks": leave_request[6],
            "employee_id": leave_request[7],
            "email": leave_request[8],
        }

        # Audit: log leave request view
        log_audit(admin_id, role, "view_leave_request", f"Viewed leave request ID {request_id}")

        return jsonify(leave_request_dict)

    except Exception as e:
        logging.exception("Failed to fetch leave request details")
        log_incident(admin_id, role, f"Error fetching leave request ID {request_id}: {e}", severity="High")
        return jsonify({"error": "Failed to fetch leave request details", "details": str(e)}), 500


# Route 1: Fetch Holidays
@admin_bp.route('/api/holidays', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_holidays"])
def get_holidays(admin_id, role, role_id):
    import logging
    logging.debug(f"Route /api/holidays called by admin_id={admin_id}, role={role}, role_id={role_id}")
    conn = None
    cursor = None
    try:
        logging.debug("Getting DB connection...")
        conn = get_db_connection()
        logging.debug("DB connection established.")
        cursor = conn.cursor()
        logging.debug("DB cursor created.")

        query = """
SELECT h.id, 'Holiday' AS module_name, h.holiday_name, h.holiday_date, h.is_paid,
       h.created_at,
       COALESCE(e.employee_id, t.team_id) AS assigned_id,
       e.email AS employee_email, t.team_name
FROM holidays AS h
LEFT JOIN holiday_assignments AS ha ON ha.holiday_id = h.id
LEFT JOIN employees AS e ON ha.employee_id = e.employee_id
LEFT JOIN teams AS t ON ha.team_id = t.team_id;
"""

        logging.debug(f"Executing query:\n{query}")
        cursor.execute(query)
        holidays = cursor.fetchall()
        logging.debug(f"Query executed. {len(holidays)} rows fetched.")

        # Structure data
        holidays_dict = {}
        for idx, row in enumerate(holidays):
            logging.debug(f"Row {idx}: {row}")
            holiday_id = row[0]
            if holiday_id not in holidays_dict:
                holidays_dict[holiday_id] = {
                    "id": row[0],
                    "module_name": row[1],
                    "name": row[2],
                    "date": row[3],
                    "is_paid": row[4],
                    "created_at": row[5],
                    "assigned_employees": [],
                    "assigned_teams": []
                }

            # Append assigned employees and teams
            if row[7]:  # employee_email
                holidays_dict[holiday_id]["assigned_employees"].append(row[7])
            if row[8]:  # team_name
                holidays_dict[holiday_id]["assigned_teams"].append(row[8])

        logging.debug(f"Holidays structured: {holidays_dict}")

        # Audit: log holidays fetch
        log_audit(admin_id, role, "get_holidays", f"Fetched holidays list (count: {len(holidays_dict)})")

        logging.debug("Returning holidays JSON response.")
        return jsonify(list(holidays_dict.values()))

    except Exception as e:
        logging.error(f"Error fetching holidays: {str(e)}", exc_info=True)
        log_incident(admin_id, role, f"Error fetching holidays: {e}", severity="High")
        return jsonify({"error": "Failed to fetch holidays"}), 500

    finally:
        if cursor:
            cursor.close()
            logging.debug("DB cursor closed.")
        if conn:
            conn.close()
            logging.debug("DB connection closed.")
            
# Route 2: Fetch Leave Requests
@admin_bp.route('/api/leave-requests', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_leave_requests"])
def get_leave_requests(admin_id, role, role_id):
    logging.debug("Fetching leave requests...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
        SELECT lr.request_id, lr.leave_type, 
               e.email, lr.status, lr.remarks, lr.start_date, lr.end_date, lb.sick_leave,lb.vacation_leave,lb.personal_leave,lb.unpaid_leave
        FROM leave_requests lr
        JOIN leave_balances lb ON lb.employee_id = lr.employee_id
        JOIN employees e ON e.employee_id = lr.employee_id
        """
        cursor.execute(query)
        leaves = cursor.fetchall()

        leaves_data = [
            {
                "id": row[0],
                "leave_type": row[1],
                "assigned_to": row[2],
                "status": row[3], 
                "remarks": row[4],
                "start_date": row[5].isoformat() if isinstance(row[5], datetime) else row[5],  
                "end_date": row[6].isoformat() if isinstance(row[6], datetime) else row[6],
                "sick_leave_amount": row[7],
                "vacation_leave": row[8],
                "personal_leave": row[9],
                "unpaid_leave": row[10]
            }
            for row in leaves
        ]

        # Audit: log leave requests fetch
        log_audit(admin_id, role, "get_leave_requests", f"Fetched leave requests list (count: {len(leaves_data)})")

        return jsonify(leaves_data)

    except Exception as e:
        logging.error(f"Error fetching leave requests: {str(e)}", exc_info=True)
        log_incident(admin_id, role, f"Error fetching leave requests: {e}", severity="High")
        return jsonify({"error": str(e)}), 500  

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            logging.debug("Database connection closed.")

@csrf.exempt
@admin_bp.route('/backup', methods=['DELETE'])
@token_required_with_roles_and_2fa(required_actions=["delete_backup"])
def delete_backup(admin_id, role, role_id):
    data = request.json
    backup_file = data.get("file")
    
    if not backup_file:
        return jsonify({"error": "No backup file specified"}), 400

    backup_path = os.path.join(BACKUP_DIR, backup_file)
    
    if not os.path.exists(backup_path):
        log_incident(admin_id, role, f"Attempted to delete non-existent backup file: {backup_file}", severity="Low")
        return jsonify({"error": "Backup file not found"}), 404

    try:
        os.remove(backup_path)
        # Audit: log backup delete
        log_audit(admin_id, role, "delete_backup", f"Deleted backup file: {backup_file}")
        return jsonify({"message": "Backup deleted successfully"})
    except Exception as e:
        log_incident(admin_id, role, f"Failed to delete backup {backup_file}: {e}", severity="High")
        return jsonify({"error": "Failed to delete backup", "details": str(e)}), 500

@csrf.exempt
@admin_bp.route('/backup', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["create_backup"])
def create_backup(admin_id, role, role_id):
    import subprocess, os
    from datetime import datetime
    timestamp = int(datetime.now().timestamp())
    backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.sql")

    os.environ['PGPASSWORD'] = DB_PASSWORD
    try:
        command = [
            PG_DUMP_PATH,
            "-h", DB_HOST,
            "-U", DB_USER,
            "-d", DB_NAME,
            "--inserts",
            "--no-owner",
            "--no-privileges",
            "--no-comments",
            "--clean",
            "--if-exists",
            "--encoding=UTF8",
            "-f", backup_file
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"pg_dump failed: {result.stderr}")
    finally:
        del os.environ['PGPASSWORD']

    return jsonify({"message": "Backup created successfully", "file": backup_file})

@csrf.exempt
@admin_bp.route('/backups', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["list_backups"])
def list_backups(admin_id, role, role_id):
    logging.info("🔹 [START] Listing available backups.")

    try:
        backups = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".sql")]
        logging.info(f"📜 Found {len(backups)} backup files: {backups}")
        # Audit: log backup listing
        log_audit(admin_id, role, "list_backups", f"Listed {len(backups)} backup files")
        return jsonify({"backups": backups})
    except Exception as e:
        logging.error(f"❌ Error listing backups: {e}")
        log_incident(admin_id, role, f"Error listing backups: {e}", severity="High")
        return jsonify({"error": "Could not list backups", "details": str(e)}), 500

@csrf.exempt
@admin_bp.route('/restore', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["restore_backup"])
def restore_backup(admin_id, role, role_id):
    data = request.json
    backup_file = data.get("file")
    if not backup_file:
        return jsonify({"error": "No backup file specified"}), 400

    backup_path = os.path.join(BACKUP_DIR, backup_file)
    if not os.path.exists(backup_path):
        log_incident(admin_id, role, f"Attempted to restore non-existent backup file: {backup_file}", severity="Low")
        return jsonify({"error": "Backup file not found"}), 404

    # --- Drop all tables in the database (CASCADE) ---
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
        DO $$ DECLARE
            r RECORD;
        BEGIN
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
            END LOOP;
        END $$;
        """)
        cur.close()
        conn.close()
    except Exception as e:
        log_incident(admin_id, role, f"Failed to drop tables before restore: {e}", severity="High")
        return jsonify({"error": "Failed to drop tables before restore", "details": str(e)}), 500

    # --- Now run the restore as before ---
    try:
        os.environ['PGPASSWORD'] = DB_PASSWORD

        command = [
            PG_PSQL_PATH,
            "-h", DB_HOST,
            "-U", DB_USER,
            "-d", DB_NAME,
            "-v", "ON_ERROR_STOP=1",
            "-f", backup_path
        ]
        result = subprocess.run(command, text=True, capture_output=True)
        del os.environ['PGPASSWORD']

        # Check for errors in output
        if result.returncode != 0 or "ERROR" in result.stdout or "ERROR" in result.stderr:
            log_incident(admin_id, role, f"Restore failed: {result.stderr}", severity="High")
            return jsonify({
                "error": "Restore failed",
                "details": result.stderr,
                "stdout": result.stdout
            }), 500

        log_audit(admin_id, role, "restore_backup", f"Restored backup file: {backup_file}")
        return jsonify({"message": "Database restored successfully"})

    except Exception as e:
        log_incident(admin_id, role, f"Restore failed for backup {backup_file}: {e}", severity="High")
        return jsonify({"error": "Restore failed", "details": str(e)}), 500
     
@csrf.exempt
@admin_bp.route('/backup/<filename>', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["download_backup"])
def download_backup(admin_id, role, role_id, filename):
    # Security: Prevent path traversal
    if not filename.endswith('.sql') or '/' in filename or '\\' in filename:
        log_incident(
            admin_id, role,
            f"Attempted download with invalid filename: {filename}",
            severity="Low"
        )
        return jsonify({"error": "Invalid filename"}), 400
    try:
        response = send_from_directory(BACKUP_DIR, filename, as_attachment=True)
        log_audit(
            admin_id, role,
            "download_backup",
            f"Downloaded backup file: {filename}"
        )
        return response
    except Exception as e:
        log_incident(
            admin_id, role,
            f"Download failed for backup {filename}: {e}",
            severity="Medium"
        )
        return jsonify({"error": "Failed to download backup", "details": str(e)}), 500
        
@admin_bp.route('/systemadministration', methods=['GET', 'POST'], endpoint='systemadministration')
def systemadministration():
    return render_template('Admin/systemadministration.html')

@admin_bp.route('/get_selection_data', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_selection_data"])
def get_selection_data(admin_id, role, role_id):
    data_type = request.args.get('type')
    print(f"DEBUG: Received request for get_selection_data with type={data_type}")

    conn = get_db_connection()
    cursor = conn.cursor()

    def build_employee_obj(row):
        emp_id, email = row
        display_name = email if email else f"Employee ID: {emp_id}"
        return {
            "id": emp_id,
            "email": email,
            "name": display_name
        }

    if data_type == "teams":
        query = "SELECT team_id, team_name FROM teams"
        try:
            cursor.execute(query)
            result = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
            print(f"DEBUG: Retrieved {len(result)} teams")
        except Exception as e:
            print(f"ERROR: Database query failed - {e}")
            log_incident(admin_id, role, f"Error fetching selection data: {e}", severity="High")
            return jsonify({"error": "Database error"}), 500
        finally:
            cursor.close()
            conn.close()
        log_audit(admin_id, role, "get_selection_data", f"Fetched selection data for type={data_type}")
        return jsonify(result)

    elif data_type == "employees":
        query = "SELECT employee_id, email FROM employees"
        try:
            cursor.execute(query)
            # Build the proper employee object with both email and display name
            result = [build_employee_obj(row) for row in cursor.fetchall()]
            print(f"DEBUG: Retrieved {len(result)} employees")
        except Exception as e:
            print(f"ERROR: Database query failed - {e}")
            log_incident(admin_id, role, f"Error fetching selection data: {e}", severity="High")
            return jsonify({"error": "Database error"}), 500
        finally:
            cursor.close()
            conn.close()
        log_audit(admin_id, role, "get_selection_data", f"Fetched selection data for type={data_type}")
        return jsonify(result)

    elif data_type == "both":
        teams_query = "SELECT team_id, team_name FROM teams"
        employees_query = "SELECT employee_id, email FROM employees"
        try:
            cursor.execute(teams_query)
            teams = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
            cursor.execute(employees_query)
            employees = [build_employee_obj(row) for row in cursor.fetchall()]
            result = {"teams": teams, "employees": employees}
            print(f"DEBUG: Retrieved {len(teams)} teams and {len(employees)} employees")
        except Exception as e:
            print(f"ERROR: Database query failed - {e}")
            log_incident(admin_id, role, f"Error fetching selection data: {e}", severity="High")
            return jsonify({"error": "Database error"}), 500
        finally:
            cursor.close()
            conn.close()
        log_audit(admin_id, role, "get_selection_data", f"Fetched selection data for type={data_type} (teams and employees)")
        return jsonify(result)

    else:
        print("ERROR: Invalid selection type")
        log_incident(admin_id, role, f"Invalid selection type: {data_type}", severity="Low")
        return jsonify({"error": "Invalid type"}), 400
    
@csrf.exempt
@admin_bp.route('/create_leave_balance', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["create_leave_balance"])
def create_leave_balance(admin_id, role, role_id):
    data = request.json
    employee_id = data.get('employee_id')
    leave_type = data.get('leave_type')
    leave_amount = data.get('leave_amount')

    print(f"DEBUG: Received leave request data - {data}")

    try:
        employee_id = int(employee_id)
        leave_amount = int(leave_amount)
    except (ValueError, TypeError):
        print(f"DEBUG: Invalid data types - employee_id: {employee_id}, leave_amount: {leave_amount}")
        return jsonify({"error": "Invalid employee_id or leave_amount format"}), 400

    valid_leave_types = ['sick_leave', 'vacation_leave', 'personal_leave', 'unpaid_leave']
    if leave_type not in valid_leave_types:
        print(f"DEBUG: Invalid leave type - {leave_type}")
        return jsonify({"error": "Invalid leave type"}), 400

    if leave_amount <= 0:
        print(f"DEBUG: Invalid leave amount - {leave_amount}")
        return jsonify({"error": "Leave amount must be positive"}), 400

    print(f"DEBUG: Valid leave type received: {leave_type}")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM leave_balances WHERE employee_id = %s", (employee_id,))
        record_exists = cur.fetchone()

        if record_exists:
            print(f"DEBUG: Employee {employee_id} has leave balance record. Adding {leave_amount} to existing {leave_type} balance.")
            update_query = f"""
                UPDATE leave_balances 
                SET {leave_type} = COALESCE({leave_type}, 0) + %s 
                WHERE employee_id = %s
            """
            cur.execute(update_query, (leave_amount, employee_id))
            cur.execute(f"SELECT {leave_type} FROM leave_balances WHERE employee_id = %s", (employee_id,))
            new_balance = cur.fetchone()[0]
            print(f"DEBUG: Updated {leave_type} balance for employee {employee_id}: {new_balance}")
            
        else:
            print(f"DEBUG: No leave balance record found for employee {employee_id}. Inserting a new record.")
            leave_defaults = {
                'sick_leave': 0,
                'vacation_leave': 0,
                'personal_leave': 0,
                'unpaid_leave': 0
            }
            leave_defaults[leave_type] = leave_amount
            
            insert_query = """
                INSERT INTO leave_balances (employee_id, sick_leave, vacation_leave, personal_leave, unpaid_leave) 
                VALUES (%s, %s, %s, %s, %s)
            """
            cur.execute(insert_query, (
                employee_id,
                leave_defaults['sick_leave'],
                leave_defaults['vacation_leave'],
                leave_defaults['personal_leave'],
                leave_defaults['unpaid_leave']
            ))
            
            print(f"DEBUG: Created new leave balance record for employee {employee_id} with {leave_amount} {leave_type}")
        
        conn.commit()
        print("DEBUG: Commit successful")

        if record_exists:
            msg = f"Leave balance updated successfully. Added {leave_amount} days to {leave_type.replace('_', ' ').title()}."
        else:
            msg = f"Leave balance created successfully with {leave_amount} days of {leave_type.replace('_', ' ').title()}."

        log_audit(admin_id, role, "create_leave_balance", f"{msg} (employee_id={employee_id})")
        return jsonify({"message": msg})

    except Exception as e:
        print(f"ERROR: Leave balance submission failed - {e}")
        conn.rollback()
        log_incident(admin_id, role, f"Leave balance submission failed: {e}", severity="High")
        return jsonify({"error": "Leave balance submission failed", "details": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@csrf.exempt
@admin_bp.route('/add_holiday', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["add_holiday"])
def add_holiday(admin_id, role, role_id):
    data = request.json
    print(f"DEBUG: Received holiday data - {data}")

    holiday_name = data.get('holiday_name')
    holiday_date = data.get('holiday_date')
    applies_to = data.get('applies_to')
    selected_ids = data.get('selected_ids')

    print(f"DEBUG: Parsed values - holiday_name: {holiday_name}, holiday_date: {holiday_date}, applies_to: {applies_to}, selected_ids: {selected_ids}")
    print(f"DEBUG: Admin - admin_id: {admin_id}, role: {role}, role_id: {role_id}")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if role == 'super_admin':
            print("DEBUG: Inserting holiday as SUPER ADMIN")
            cur.execute(
                """
                INSERT INTO holidays (holiday_name, holiday_date, assigned_by_super_admins)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (holiday_name, holiday_date, admin_id)
            )
        else:
            print("DEBUG: Inserting holiday as ADMIN")
            cur.execute(
                """
                INSERT INTO holidays (holiday_name, holiday_date, assigned_by_admins)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (holiday_name, holiday_date, admin_id)
            )

        holiday_id = cur.fetchone()[0]
        print(f"DEBUG: Created holiday with ID {holiday_id}")

        # Handle assignment for employees, teams, or both
        if applies_to == 'both':
            print(f"DEBUG: Assigning holiday to BOTH teams and employees: {selected_ids}")
            for selected_id in selected_ids:
                print(f"DEBUG: Processing selected_id: {selected_id}")
                if str(selected_id).startswith('team_'):
                    team_id = str(selected_id).replace('team_', '')
                    print(f"DEBUG: Assigning to TEAM: {team_id}")
                    cur.execute(
                        "INSERT INTO holiday_assignments (holiday_id, team_id) VALUES (%s, %s)",
                        (holiday_id, team_id)
                    )
                elif str(selected_id).startswith('emp_'):
                    emp_id = str(selected_id).replace('emp_', '')
                    print(f"DEBUG: Assigning to EMPLOYEE: {emp_id}")
                    cur.execute(
                        "INSERT INTO holiday_assignments (holiday_id, employee_id) VALUES (%s, %s)",
                        (holiday_id, emp_id)
                    )
                else:
                    print(f"DEBUG: Could not determine type for {selected_id}, assigning as EMPLOYEE by default.")
                    cur.execute(
                        "INSERT INTO holiday_assignments (holiday_id, employee_id) VALUES (%s, %s)",
                        (holiday_id, selected_id)
                    )
        elif applies_to == 'teams':
            print(f"DEBUG: Assigning holiday to TEAMS: {selected_ids}")
            for selected_id in selected_ids:
                print(f"DEBUG: Assigning to TEAM: {selected_id}")
                cur.execute(
                    "INSERT INTO holiday_assignments (holiday_id, team_id) VALUES (%s, %s)",
                    (holiday_id, selected_id)
                )
        else:  # employees
            print(f"DEBUG: Assigning holiday to EMPLOYEES: {selected_ids}")
            for selected_id in selected_ids:
                print(f"DEBUG: Assigning to EMPLOYEE: {selected_id}")
                cur.execute(
                    "INSERT INTO holiday_assignments (holiday_id, employee_id) VALUES (%s, %s)",
                    (holiday_id, selected_id)
                )

        conn.commit()
        print(f"DEBUG: Successfully committed holiday and assignments for holiday_id {holiday_id}")
        log_audit(admin_id, role, "add_holiday", f"Added holiday '{holiday_name}' (ID {holiday_id}) for {applies_to}: {selected_ids}")
        return jsonify({"message": "Holiday added successfully"})

    except Exception as e:
        print(f"ERROR: Failed to add holiday - {e}")
        log_incident(admin_id, role, f"Failed to add holiday: {e}", severity="High")
        return jsonify({"error": "Failed to add holiday"}), 500
    finally:
        print("DEBUG: Closing DB cursor and connection")
        cur.close()
        conn.close()