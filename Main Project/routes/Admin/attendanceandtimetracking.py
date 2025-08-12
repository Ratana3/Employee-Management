import base64
import sys
import traceback
from flask import flash, redirect
from datetime import datetime, timedelta
import logging
import os
import bcrypt
from flask import Blueprint, Response, render_template, jsonify, request, send_file, url_for
import psycopg2
from routes.Auth.audit import log_audit, log_incident
from routes.Auth.token import token_required_with_roles_and_2fa,token_required_with_roles,get_admin_from_token
from routes.Auth.utils import get_db_connection
from . import admin_bp
from extensions import csrf
from PIL import Image
import io

# Get all shift swap requests (for approvers)
@admin_bp.route('/api/shift_swap_requests', methods=['GET'])
@token_required_with_roles(required_actions=['get_shift_swap_requests'])
def get_shift_swap_requests(admin_id,role,role_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            sr.shift_request_id, sr.sender_id, sr.sender_role, sr.subject, sr.body, sr.is_read, sr.timestamp, sr.is_approved,
            r.role_name as approver_role_name,
            e.email as sender_email
        FROM shift_request sr
        LEFT JOIN roles r ON sr.approver_role = r.role_id
        LEFT JOIN employees e ON sr.sender_id = e.employee_id
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
            'approver_role_name': r[8],
            'sender_email': r[9]  # Added sender email
        }
        for r in rows
    ]
    cursor.close()
    conn.close()
    return jsonify(requests), 200

# Approve shift swap request
@csrf.exempt
@admin_bp.route('/api/shift_swap_requests/<int:shift_request_id>/approve', methods=['POST'])
@token_required_with_roles(required_actions=['approve_shift_swap_request'])
def approve_shift_swap_request(admin_id,role,role_id,shift_request_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # g.role_id is assumed to be available from your decorator
    cursor.execute("""
        UPDATE shift_request
        SET is_read = TRUE, is_approved = TRUE, approver_role=%s
        WHERE shift_request_id = %s
    """, (role_id, shift_request_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Request approved'}), 200

# Reject shift swap request
@csrf.exempt
@admin_bp.route('/api/shift_swap_requests/<int:shift_request_id>/reject', methods=['POST'])
@token_required_with_roles(required_actions=['reject_shift_swap_request'])
def reject_shift_swap_request(admin_id,role,role_id,shift_request_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE shift_request
        SET is_read = TRUE, is_approved = FALSE, approver_role=%s
        WHERE shift_request_id = %s
    """, (role_id, shift_request_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Request rejected'}), 200

#route for setiing verify to false
@admin_bp.route('/disapprove_attendance', methods=['POST'])
@token_required_with_roles(required_actions=["disapprove_attendance"])
@csrf.exempt
def disapprove_attendance(admin_id, role,role_id):
    data = request.get_json()
    log_id = data.get('log_id')

    if not log_id:
        return jsonify({'message': 'Missing log_id'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE attendance_logs SET attendance_verified = 'False' WHERE log_id = %s", (log_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'Attendance successfully disapproved'})
    except Exception as e:
        print("Error disapproving attendance:", e)
        return jsonify({'message': 'Error disapproving attendance'}), 500
    
# verify_overtime
@admin_bp.route('/verify_overtime', methods=['POST'])
@token_required_with_roles(required_actions=["verify_overtime"])
@csrf.exempt
def verify_overtime(admin_id, role, role_id):
    data = request.get_json()
    log_id = data.get('log_id')

    if not log_id:
        return jsonify({'message': 'Missing log_id'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Approve overtime request
        cur.execute("""
            UPDATE attendance_logs
            SET is_overtime_approved = TRUE
            WHERE log_id = %s
        """, (log_id,))
        conn.commit()

        # Fetch employee ID and role name for the log
        cur.execute("""
            SELECT e.employee_id, r.role_name
            FROM attendance_logs a
            JOIN employees e ON a.employee_id = e.employee_id
            JOIN roles r ON e.role_id = r.role_id
            WHERE a.log_id = %s
        """, (log_id,))
        row = cur.fetchone()
        if row:
            employee_id, receiver_role = row

            # Send approval message to employee
            cur.execute("""
                INSERT INTO messages (sender_id, sender_role, receiver_id, receiver_role, subject, body, is_read, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                admin_id,
                role,
                employee_id,
                receiver_role,
                "Overtime Request Approved",
                "Your overtime request has been approved. Please check your records.",
                False
            ))
            conn.commit()

        cur.close()
        conn.close()
        return jsonify({'message': 'Overtime successfully verified and employee notified'})
    except Exception as e:
        print("Error verifying overtime:", e)
        return jsonify({'message': 'Error verifying overtime'}), 500

# disapprove_overtime
@admin_bp.route('/disapprove_overtime', methods=['POST'])
@token_required_with_roles(required_actions=["disapprove_overtime"])
@csrf.exempt
def disapprove_overtime(admin_id, role, role_id):
    data = request.get_json()
    log_id = data.get('log_id')
    rejection_reason = data.get('rejection_reason', '')  # Optional

    if not log_id:
        return jsonify({'message': 'Missing log_id'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Update overtime status to not approved
        cur.execute("UPDATE attendance_logs SET is_overtime_approved = FALSE WHERE log_id = %s", (log_id,))
        conn.commit()

        # Fetch employee ID and role name for the log
        cur.execute("""
            SELECT e.employee_id, r.role_name
            FROM attendance_logs a
            JOIN employees e ON a.employee_id = e.employee_id
            JOIN roles r ON e.role_id = r.role_id
            WHERE a.log_id = %s
        """, (log_id,))
        row = cur.fetchone()
        if row:
            employee_id, receiver_role = row

            # Insert rejection message into messages table
            cur.execute("""
                INSERT INTO messages (sender_id, sender_role, receiver_id, receiver_role, subject, body, is_read, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                admin_id,
                role,
                employee_id,
                receiver_role,
                "Overtime Request Rejected",
                f"Your overtime request has been rejected." + (f" Reason: {rejection_reason}" if rejection_reason else ""),
                False
            ))
            conn.commit()

        cur.close()
        conn.close()
        return jsonify({'message': 'Overtime successfully disapproved and employee notified'})
    except Exception as e:
        print("Error disapproving overtime:", e)
        return jsonify({'message': 'Error disapproving overtime'}), 500
     
#route for verifying attendance
@admin_bp.route('/verify_attendance_admin', methods=['POST'])
@token_required_with_roles(required_actions=["verify_attendance_admin"])
@csrf.exempt
def verify_attendance_admin(admin_id, role,role_id):
    data = request.get_json()
    log_id = data.get('log_id')

    if not log_id:
        return jsonify({'message': 'Missing log_id'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE attendance_logs SET attendance_verified = 'True' WHERE log_id = %s", (log_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'message': 'Attendance successfully verified'})
    except Exception as e:
        print("Error verifying attendance:", e)
        return jsonify({'message': 'Error verifying attendance'}), 500

#route for displaying details of attendance logs for specific employee (View attendance logs table )
@csrf.exempt
@admin_bp.route("/get_attendance_details", methods=["POST"])
@token_required_with_roles(required_actions=["get_attendance_details"])
def get_attendance_details(admin_id,role,role_id):
    try:
        log_id = request.form.get("log_id")
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get the attendance log
        cursor.execute("SELECT * FROM attendance_logs WHERE log_id = %s", (log_id,))
        log = cursor.fetchone()

        # Get all breaks for this log_id
        cursor.execute("""
            SELECT break_id, break_type, break_start, break_end, break_duration, status 
            FROM employee_breaks 
            WHERE log_id = %s
            ORDER BY break_start ASC
        """, (log_id,))
        breaks = cursor.fetchall()

        cursor.close()
        conn.close()

        if log:
            # Safely convert time and date fields to string
            def safe_time(val):
                return val.strftime('%H:%M:%S') if val is not None else None

            def safe_date(val):
                return val.strftime('%Y-%m-%d') if val is not None else None

            def safe_dt(val):
                return val.strftime('%Y-%m-%d %H:%M:%S') if val is not None else None

            def safe_duration(val):
                return val.total_seconds() if val is not None else None

            # Serialize breaks
            breaks_list = [{
                "break_id": b[0],
                "break_type": b[1],
                "break_start": safe_dt(b[2]),
                "break_end": safe_dt(b[3]),
                "break_duration_seconds": safe_duration(b[4]),
                "break_status": b[5]
            } for b in breaks]

            return jsonify({
                "success": True,
                "log_id": log[0],
                "employee_id": log[1],
                "date": safe_date(log[2]),
                "clock_in_time": safe_time(log[3]),
                "clock_out_time": safe_time(log[4]),
                "status": log[5],
                "hours_worked": float(log[6]) if log[6] is not None else None,
                "shift_id": log[7],
                "overtime_hours": float(log[8]) if log[8] is not None else None,
                "is_overtime": log[9],
                "remarks": log[10],
                "leave_type": log[11],
                "attendance_verified": 'Yes' if log[12] else 'No',
                "breaks": breaks_list
            })
        else:
            return jsonify({"success": False, "message": "Attendance log not found!"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    
#route for editing attendance logs for specific employee (View attendance logs table )
# Configure logging
logging.basicConfig(level=logging.DEBUG)
@admin_bp.route("/edit_attendance", methods=["POST"])
@token_required_with_roles(required_actions=["edit_attendance"])
@csrf.exempt
def edit_attendance(admin_id, role,role_id):
    conn = None
    cursor = None
    try:
        logging.debug("Received request to edit attendance.")

        data = request.get_json()
        if not data:
            return jsonify({"message": "Invalid request body", "success": False}), 400

        logging.debug(f"Parsed JSON Data: {data}")

        employee_id = data.get("employee_id")
        date = data.get("date")
        original_date = data.get("original_date")
        clock_in_time = data.get("clock_in_time")
        clock_out_time = data.get("clock_out_time")
        status = data.get("status")
        remarks = data.get("remarks")
        leave_type = data.get("leave_type")

        if not employee_id or not employee_id.isdigit():
            return jsonify({"success": False, "message": "Invalid Employee ID"}), 400
        employee_id = int(employee_id)

        if not date or not original_date:
            return jsonify({"success": False, "message": "Date and original date are required"}), 400

        try:
            date = datetime.strptime(date, "%Y-%m-%d").date()
            original_date = datetime.strptime(original_date, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"success": False, "message": "Invalid date format"}), 400

        clock_in_time_value = f"{clock_in_time}:00" if clock_in_time else None
        clock_out_time_value = f"{clock_out_time}:00" if clock_out_time else None

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 1 FROM attendance_logs WHERE employee_id = %s AND date = %s
        """, (employee_id, original_date))
        if cursor.fetchone() is None:
            return jsonify({"success": False, "message": "Attendance log not found"}), 404

        query = """
            UPDATE attendance_logs 
            SET 
                date = %s, 
                clock_in_time = COALESCE(%s::time, clock_in_time),
                clock_out_time = COALESCE(%s::time, clock_out_time),
                status = %s, 
                remarks = %s, 
                leave_type = %s
            WHERE employee_id = %s AND date = %s
        """
        params = (
            date,
            clock_in_time_value,
            clock_out_time_value,
            status,
            remarks,
            leave_type,
            employee_id,
            original_date
        )

        cursor.execute(query, params)
        conn.commit()

        action = f"Edited attendance log for Employee ID {employee_id} on {original_date}"
        details = f"Updated to: Date={date}, Status={status}, Clock-in={clock_in_time}, Clock-out={clock_out_time}, Remarks={remarks}, Leave Type={leave_type}"
        log_audit(admin_id, role, action, details)

        cursor.close()
        conn.close()
        return jsonify({"success": True, "message": "Attendance log updated successfully!"})

    except psycopg2.Error as db_err:
        logging.error(f"Database Error: {db_err}")
        if cursor:
            cursor.close()
        if conn:
            conn.rollback()
            conn.close()
        return jsonify({"success": False, "message": "Database error occurred"}), 500

    except Exception as e:
        logging.error(f"Unexpected Error: {e}")
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return jsonify({"success": False, "message": str(e)}), 500


#route for deleting attendance logs for specific employee (View attendance logs table )
# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
@csrf.exempt
@admin_bp.route("/delete_attendance", methods=["POST"])
@token_required_with_roles(required_actions=["delete_attendance"])
def delete_attendance(admin_id, role, role_id):
    try:
        data = request.get_json()
        log_id = data.get("log_id")
        logging.debug(f"Received request to delete attendance log with log_id: {log_id}")

        if not log_id:
            return jsonify({"success": False, "message": "Missing log_id."})

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the attendance log exists
        cursor.execute("SELECT * FROM attendance_logs WHERE log_id = %s", (log_id,))
        record = cursor.fetchone()

        if not record:
            cursor.close()
            conn.close()
            return jsonify({"success": False, "message": "Attendance log not found."})

        # First delete related timesheets
        cursor.execute("DELETE FROM timesheets WHERE log_id = %s", (log_id,))
        logging.info(f"Deleted related timesheets for log_id: {log_id}")

        # Then delete related employee_breaks
        cursor.execute("DELETE FROM employee_breaks WHERE log_id = %s", (log_id,))
        logging.info(f"Deleted related breaks for log_id: {log_id}")

        # Then delete the attendance log
        cursor.execute("DELETE FROM attendance_logs WHERE log_id = %s", (log_id,))
        conn.commit()
        logging.info(f"Successfully deleted attendance log with log_id: {log_id}")

        action_details = f"Deleted attendance log with log_id: {log_id} and related timesheets and breaks"
        log_audit(admin_id, role, "DELETE_ATTENDANCE", action_details)

        cursor.close()
        conn.close()
        return jsonify({"success": True, "message": "Attendance log and all related records deleted successfully!"})

    except Exception as e:
        logging.error(f"Error deleting attendance log: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)})
    
#route for assigning shift to a specific employee
@csrf.exempt
@admin_bp.route("/assign_shift", methods=["POST"])
@token_required_with_roles(required_actions=["assign_shift"])
def assign_shift(admin_id, role,role_id):
    try:
        data = request.json
        logging.debug(f"Received assign_shift request: {data}")

        assigned_by = f"Assigned by {role}, ID: {admin_id}"

        employee_id = data.get("employee_id")
        shift_id = data.get("shift_id")
        is_rotating = bool(data.get("is_rotating"))
        location = data.get("location")
        shift_date = data.get("shift_date")

        if not employee_id or not shift_id or not location or not shift_date:
            logging.error("Missing required fields")
            return jsonify({"error": "Employee ID, Shift ID, Location, and Shift Date are required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the employee already has an assigned shift
        cursor.execute("SELECT shift_id FROM employee_shifts WHERE employee_id = %s", (employee_id,))
        existing_shift = cursor.fetchone()

        if existing_shift:
            logging.error(f"Employee {employee_id} already has an assigned shift.")
            return jsonify({"error": "Employee already has an assigned shift"}), 400

        # Insert new shift assignment including assigned_by
        cursor.execute("""
            INSERT INTO employee_shifts (employee_id, shift_id, is_rotating, location, shift_date, assigned_by) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (employee_id, shift_id, is_rotating, location, shift_date, assigned_by))

        conn.commit()
        cursor.close()
        conn.close()

        logging.debug(f"Successfully assigned shift {shift_id} to employee {employee_id} by {assigned_by}")
        return jsonify({"success": True, "message": "Shift assigned successfully"})

    except Exception as e:
        logging.error(f"Error assigning shift: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal Server Error"}), 500


#route for deleting shift from a specific employee
# Set up logging for debugging
logging.basicConfig(level=logging.DEBUG)
@csrf.exempt
@admin_bp.route('/delete_Assignedshift', methods=['POST'])
@token_required_with_roles(required_actions=["delete_assigned_shift"])
def delete_assigned_shift(admin_id, role,role_id):
    try:
        data = request.get_json()
        employee_id = data.get('employee_id')
        shift_id = data.get('shift_id')

        if not employee_id or not shift_id:
            return jsonify({'error': 'Employee ID or Shift ID missing'}), 400

        query = """
        DELETE FROM employee_shifts
        WHERE employee_id = %s AND shift_id = %s
        RETURNING *;
        """

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(query, (employee_id, shift_id))
        result = cursor.fetchall()
        connection.commit()

        if not result:
            return jsonify({'error': 'No shift assignment found to delete'}), 404

        return jsonify({'success': True, 'message': 'Shift successfully deleted.'})

    except Exception as e:
        logging.error(f"Error deleting assigned shift: {e}", exc_info=True)
        return jsonify({'error': 'Internal Server Error'}), 500
    finally:
        cursor.close()
        connection.close()

#route for displaying assigned shift for specific employee
@admin_bp.route('/get_employee_shifts')
@token_required_with_roles(required_actions=["get_employee_shifts"])
def get_employee_shifts(admin_id,role,role_id):
    employee_id = request.args.get('employee_id')
    logging.debug(f"Fetching assigned shifts for employee ID: {employee_id}")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.shift_id, s.shift_name, s.start_time, s.end_time
        FROM employee_shifts es
        JOIN shifts s ON es.shift_id = s.shift_id
        WHERE es.employee_id = %s
        ORDER BY s.shift_name
    """, (employee_id,))
    
    shifts = cursor.fetchall()
    conn.close()

    if not shifts:
        logging.debug("No assigned shifts found for this employee.")

    shift_data = []
    for shift in shifts:
        shift_id, shift_name, start_time, end_time = shift
        logging.debug(f"Shift found: {shift_id} - {shift_name} ({start_time} - {end_time})")
        shift_data.append({
            "shift_id": shift_id,
            "shift_name": shift_name,
            "start_time": start_time.strftime('%H:%M') if start_time else None,
            "end_time": end_time.strftime('%H:%M') if end_time else None
        })

    logging.debug(f"Returning shift data: {shift_data}")
    return jsonify(shift_data)

# Route to fetch shift details for editing (For "Edit shift" button)
@admin_bp.route('/get_shifts', methods=['GET'])
@token_required_with_roles(required_actions=["get_shifts"])
def get_shifts(admin_id,role,role_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT shift_id, shift_name, start_time, end_time FROM shifts")
    shifts = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify([
    {
        "shift_id": row[0],
        "shift_name": row[1],
        "start_time": row[2].strftime("%I:%M %p") if row[2] else "N/A",
        "end_time": row[3].strftime("%I:%M %p") if row[3] else "N/A"
    }
    for row in shifts
])


#route for approving and rejecting leave requests
@csrf.exempt
@admin_bp.route('/manage_leave/<request_id>/<action>', methods=['POST'])
@token_required_with_roles(required_actions=["manage_leave"])
def manage_leave(admin_id, role, role_id, request_id, action):
    print(f"[DEBUG] manage_leave called with request_id={request_id}, action={action}", file=sys.stderr)
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        print(f"[DEBUG] Fetching leave request for request_id: {request_id}", file=sys.stderr)
        cursor.execute("SELECT employee_id, leave_type, total_days, verification_status FROM leave_requests WHERE request_id = %s;", (request_id,))
        leave_request = cursor.fetchone()
        print(f"[DEBUG] leave_request fetched: {leave_request}", file=sys.stderr)

        if not leave_request:
            print("[DEBUG] Leave request not found", file=sys.stderr)
            return jsonify({"success": False, "error": "Leave request not found!"})

        employee_id, leave_type, total_days, verification_status = leave_request

        # Check verification_status before proceeding
        if action == "approve":
            if verification_status is True or verification_status == 'true' or verification_status == 1:
                print("[DEBUG] Leave request already approved", file=sys.stderr)
                return jsonify({"success": False, "error": "Leave request already approved!"})
            # Only approve if status is False
            leave_col = leave_type.lower().replace(" ", "_")
            print(f"[DEBUG] Approving leave: updating balances for employee_id={employee_id}, leave_col={leave_col}, total_days={total_days}", file=sys.stderr)

            cursor.execute(f"""
                UPDATE leave_balances
                SET {leave_col} = {leave_col} - %s
                WHERE employee_id = %s AND {leave_col} >= %s;
            """, (total_days, employee_id, total_days))
            print(f"[DEBUG] Balance update cursor.rowcount: {cursor.rowcount}", file=sys.stderr)

            if cursor.rowcount == 0:
                print("[DEBUG] Not enough leave balance!", file=sys.stderr)
                return jsonify({"success": False, "error": "Not enough leave balance!"})

            print("[DEBUG] Updating leave_requests.verification_status = true and remarks", file=sys.stderr)
            cursor.execute("""
                UPDATE leave_requests
                SET verification_status = true, remarks = %s
                WHERE request_id = %s;
            """, ("Your request has been approved!", request_id))
            print(f"[DEBUG] verification_status and remarks update cursor.rowcount: {cursor.rowcount}", file=sys.stderr)

            cursor.execute("SELECT verification_status, remarks FROM leave_requests WHERE request_id = %s;", (request_id,))
            updated_status = cursor.fetchone()
            print(f"[DEBUG] Updated verification_status, remarks for request_id={request_id}: {updated_status}", file=sys.stderr)

            # Notify employee via messages table
            cursor.execute("""
                INSERT INTO messages (sender_id, sender_role, receiver_id, receiver_role, subject, body, is_read, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW());
            """, (
                admin_id, "admin",
                employee_id, "employee",
                "Leave Request Approved",
                f"Your {leave_type} leave request for {total_days} days has been approved.",
                False
            ))

        elif action == "reject":
            if verification_status is False or verification_status == 'false' or verification_status == 0:
                print("[DEBUG] Leave request already rejected", file=sys.stderr)
                return jsonify({"success": False, "error": "Leave request already rejected!"})
            # Only reject if status is True
            rejection_reason = request.form.get('rejection_reason', '')
            print(f"[DEBUG] Rejecting leave: setting verification_status = false, rejection_reason={rejection_reason}", file=sys.stderr)

            print("[DEBUG] Updating leave_requests.verification_status = false and remarks", file=sys.stderr)
            cursor.execute("""
                UPDATE leave_requests
                SET verification_status = false, remarks = %s
                WHERE request_id = %s;
            """, ("Your request has been rejected!", request_id))
            print(f"[DEBUG] verification_status and remarks update cursor.rowcount: {cursor.rowcount}", file=sys.stderr)

            cursor.execute("SELECT verification_status, remarks FROM leave_requests WHERE request_id = %s;", (request_id,))
            updated_status = cursor.fetchone()
            print(f"[DEBUG] Updated verification_status, remarks for request_id={request_id}: {updated_status}", file=sys.stderr)

            # Compose message body with optional rejection reason
            body = "Your leave request has been rejected."
            if rejection_reason:
                body += f"\nReason: {rejection_reason}"

            cursor.execute("""
                INSERT INTO messages (sender_id, sender_role, receiver_id, receiver_role, subject, body, is_read, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW());
            """, (
                admin_id, "admin",
                employee_id, "employee",
                "Leave Request Rejected",
                body,
                False
            ))

        else:
            print(f"[DEBUG] Invalid action: {action}", file=sys.stderr)
            return jsonify({"success": False, "error": "Invalid action!"})

        connection.commit()
        print("[DEBUG] Transaction committed successfully", file=sys.stderr)
        return jsonify({"success": True, "message": "Leave request processed successfully!"})

    except Exception as e:
        print("[ERROR] Exception occurred:", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        connection.rollback()
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()})

    finally:
        cursor.close()
        connection.close()
        print("[DEBUG] Database connection closed", file=sys.stderr)
        
#route for deleting shift swap request
@csrf.exempt
@admin_bp.route('/api/shift_swap_requests/<int:request_id>/delete', methods=['DELETE'])
@token_required_with_roles(required_actions=["delete_shift_swap_request"])
def delete_shift_swap_request(admin_id, role, role_id, request_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        print(f"Attempting to delete shift swap request with id: {request_id}")
        cursor.execute("DELETE FROM shift_request WHERE shift_request_id = %s", (request_id,))
        rows_deleted = cursor.rowcount
        print(f"Rows deleted: {rows_deleted}")
        connection.commit()
        if rows_deleted == 0:
            return jsonify({"success": False, "message": "No shift swap request found with that id."}), 404
        return jsonify({"success": True, "message": "Shift swap request deleted.", "rows_deleted": rows_deleted})
    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "error": str(e)})
    finally:
        cursor.close()
        connection.close()

# Route: Get leave request details (JSON)
@csrf.exempt
@admin_bp.route('/get_leave_request_details', methods=['POST'])
@token_required_with_roles(required_actions=["get_leave_request_details"])
def get_leave_request_details(admin_id, role, role_id):
    req_id = request.form.get('request_id')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT lr.request_id, lr.employee_id, e.first_name, e.last_name, e.email,
               lr.leave_type, lr.start_date, lr.end_date, lr.total_days,
               lr.status, lr.remarks, lr.verification_status, lr.created_at
        FROM leave_requests lr
        JOIN employees e ON lr.employee_id = e.employee_id
        WHERE lr.request_id = %s
    """, (req_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return jsonify({
            "success": True,
            "request_id": row[0],
            "employee_id": row[1],
            "first_name": row[2],
            "last_name": row[3],
            "email": row[4],
            "leave_type": row[5],
            "start_date": row[6],
            "end_date": row[7],
            "total_days": row[8],
            "status": row[9],
            "remarks": row[10],
            "verification": row[11],
            "created_at": row[12],
        })
    else:
        return jsonify({"success": False, "message": "Leave request not found."})

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
#route for adding new shift
@csrf.exempt
@admin_bp.route('/add_shift', methods=['POST'])
@token_required_with_roles(required_actions=["add_shift"])
def add_shift(admin_id, role,role_id):
    try:
        data = request.get_json()
        if not data:
            raise ValueError("No JSON data received")

        shift_name = data.get('shift_name')
        start_time = data.get('start_time')
        end_time = data.get('end_time')

        logging.debug(f"Received shift data: shift_name={shift_name}, start_time={start_time}, end_time={end_time}")

        if not shift_name or not start_time or not end_time:
            return jsonify({"error": "All fields are required"}), 400

        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            INSERT INTO shifts (shift_name, start_time, end_time)
            VALUES (%s, %s, %s);
        """
        cursor.execute(query, (shift_name, start_time, end_time))
        connection.commit()

        log_audit(admin_id, role, "Add Shift", f"Added new shift: {shift_name} ({start_time} - {end_time})")

        logging.info("Shift added successfully")
        return jsonify({"message": "Shift added successfully"}), 200

    except ValueError as ve:
        logging.error(f"ValueError: {ve}")
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logging.error(f"Error inserting shift: {e}", exc_info=True)
        return jsonify({"error": "Database error occurred"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

# route for updating shift
@csrf.exempt
@admin_bp.route('/update_shift', methods=['POST'])
@token_required_with_roles(required_actions=["update_shift"])
def update_shift(admin_id, role,role_id):
    logging.debug("Received request to update shift.")

    try:
        data = request.get_json()
        logging.debug(f"Received JSON data: {data}")
    except Exception as e:
        logging.error(f"Failed to parse JSON: {str(e)}")
        return jsonify({'error': 'Invalid JSON data'}), 400

    shift_id = data.get('shift_id')
    shift_name = data.get('shift_name')
    start_time = data.get('start_time')
    end_time = data.get('end_time')

    logging.debug(f"Extracted values - shift_id: {shift_id}, shift_name: {shift_name}, start_time: {start_time}, end_time: {end_time}")

    if not shift_id or not shift_name or not start_time or not end_time:
        logging.error("Missing required fields.")
        return jsonify({'error': 'All fields (shift_id, shift_name, start_time, end_time) are required!'}), 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM shifts WHERE shift_id = %s;", (shift_id,))
        shift = cursor.fetchone()

        if not shift:
            logging.warning(f"Shift with ID {shift_id} not found.")
            return jsonify({'error': 'Shift not found!'}), 404

        cursor.execute("""
            UPDATE shifts 
            SET shift_name = %s, start_time = %s, end_time = %s
            WHERE shift_id = %s;
        """, (shift_name, start_time, end_time, shift_id))

        connection.commit()

        log_audit(admin_id, role, "Update Shift", f"Updated shift {shift_id} to: {shift_name} ({start_time} - {end_time})")

        logging.info(f"Shift {shift_id} updated successfully.")
        return jsonify({'message': 'Shift updated successfully!'}), 200

    except Exception as e:
        logging.exception(f"Error updating shift ID {shift_id}: {str(e)}")
        return jsonify({'error': f'Error updating shift: {str(e)}'}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# route for deleting shift
# Configure logging
logging.basicConfig(level=logging.DEBUG)
@admin_bp.route("/delete_shift", methods=["POST"])
@csrf.exempt  # Exempt from CSRF since you're using token-based auth now
@token_required_with_roles(required_actions=["delete_shift"])
def delete_shift(admin_id, role,role_id):
    logging.debug(f"Received request to delete shift from admin {admin_id} with role {role}.")

    try:
        shift_id = request.form.get("shift_id")
        logging.debug(f"Extracted shift_id: {shift_id}")

        if not shift_id:
            logging.error("Shift ID is missing in request.")
            return jsonify({"error": "Shift ID is required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT shift_name, start_time, end_time FROM shifts WHERE shift_id = %s", (shift_id,))
        shift = cursor.fetchone()

        if not shift:
            logging.warning(f"Shift with ID {shift_id} not found.")
            return jsonify({"error": "Shift not found"}), 404

        shift_name, start_time, end_time = shift
        cursor.execute("DELETE FROM shifts WHERE shift_id = %s", (shift_id,))
        conn.commit()

        log_audit(admin_id, role, "Delete Shift", f"Deleted shift {shift_id}: {shift_name} ({start_time} - {end_time})")
        logging.info(f"Shift {shift_id} deleted successfully.")
        return jsonify({"message": "Shift deleted successfully"}), 200

    except Exception as e:
        logging.exception(f"Error deleting shift with ID {shift_id}: {str(e)}")
        return jsonify({"error": "Internal Server Error"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

#route for rendering the attendance page
@admin_bp.route('/attendanceandtimetracking', methods=['GET'])
def attendanceandtimetracking_page():
    return render_template('Admin/AttendanceAndTimetracking.html')

# route for displaying employees in attendance logs table, display absent employees, display employees' shifts
@admin_bp.route('/attendanceandtimetracking_data', methods=['GET'])
@token_required_with_roles(required_actions=["attendanceandtimetracking_data"])
def attendanceandtimetracking_data(admin_id, role, role_id):
    """Return attendance logs, absent employees, employee shifts, and overtime logs as JSON (no leave requests data)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Attendance logs (NO leave_requests join)
    cursor.execute("""
    SELECT 
        a.log_id,
        e.employee_id,
        e.email,
        a.date,
        a.clock_in_time,
        a.clock_out_time,
        a.status,
        a.remarks,
        a.leave_type,
        a.hours_worked,
        a.overtime_hours,
        a.attendance_verified,
        a.is_overtime_approved,
        r.role_name
    FROM attendance_logs a
    JOIN employees e ON a.employee_id = e.employee_id
    JOIN roles r ON e.role_id = r.role_id
    ORDER BY a.date DESC;
    """)
    logs = cursor.fetchall()

    attendance_logs = [
        {
            "log_id": row[0],
            "employee_id": row[1],
            "email": row[2],
            "date": row[3],
            "clock_in_time": row[4].strftime('%H:%M:%S') if row[4] else None,
            "clock_out_time": row[5].strftime('%H:%M:%S') if row[5] else None,
            "status": row[6],
            "remarks": row[7],
            "leave_type": row[8],
            "hours_worked": row[9],
            "overtime_hours": row[10],
            "attendance_verified": row[11],
            "is_overtime_approved": row[12],
            "role_name": row[13],
        }
        for row in logs
    ]

    # Absent employees
    today = datetime.now().date()
    cursor.execute("""
        SELECT e.employee_id, e.email, 
               al.date, al.clock_in_time, al.clock_out_time, 
               COALESCE(al.status, 'Absent') AS status, 
               al.remarks, al.hours_worked
        FROM employees e
        LEFT JOIN attendance_logs al ON e.employee_id = al.employee_id 
        WHERE al.employee_id IS NULL OR al.status = 'Absent'
    """)
    absent_employees = [
        {
            "employee_id": row[0],
            "email": row[1],
            "date": row[2] if row[2] else today,
            "clock_in": row[3].strftime('%H:%M:%S') if row[3] else '-',
            "clock_out": row[4].strftime('%H:%M:%S') if row[4] else '-',
            "status": row[5],
            "remarks": row[6],
            "hours_worked": row[7] if row[7] else '0'
        }
        for row in cursor.fetchall()
    ]

    # Shift data
    cursor.execute("""
        SELECT e.employee_id, e.first_name, e.last_name, e.email, e.profile, 
               COALESCE(s.shift_name, 'No Shift Assigned'), 
               s.start_time, s.end_time, es.shift_id, es.shift_date, es.location, es.is_rotating
        FROM employees e
        LEFT JOIN employee_shifts es ON e.employee_id = es.employee_id
        LEFT JOIN shifts s ON es.shift_id = s.shift_id
        ORDER BY e.email;
    """)
    employees = cursor.fetchall()

    employee_data = []
    for row in employees:
        profile_img = base64.b64encode(row[4]).decode('utf-8') if row[4] else None
        employee_data.append({
            "employee_id": row[0],
            "first_name": row[1],
            "last_name": row[2],
            "email": row[3],
            "image_src": f"data:image/jpeg;base64,{profile_img}" if profile_img else "/static/Admin/images/example.png",
            "shift_name": row[5],
            "start_time": row[6].strftime('%I:%M %p') if row[6] else "N/A",
            "end_time": row[7].strftime('%I:%M %p') if row[7] else "N/A",
            "shift_id": row[8],
            "shift_date": row[9],
            "location": row[10],
            "is_rotating": row[11]
        })

    # Overtime logs
    cursor.execute("""
        SELECT a.log_id, e.employee_id, e.first_name, e.last_name, a.date, 
               COALESCE(a.overtime_hours, 0), a.is_overtime_approved, e.profile
        FROM attendance_logs a
        JOIN employees e ON a.employee_id = e.employee_id
        WHERE a.overtime_hours IS NOT NULL AND a.overtime_hours > 0;
    """)
    overtime_rows = cursor.fetchall()
    overtime_data = []
    for row in overtime_rows:
        profile_image = base64.b64encode(row[7]).decode('utf-8') if row[7] else None
        overtime_data.append({
            "log_id": row[0],
            "employee_id": row[1],
            "first_name": row[2],
            "last_name": row[3],
            "date": row[4],
            "overtime_hours": row[5],
            "is_overtime_approved": row[6],
            "profile_image": profile_image
        })

    conn.close()

    return jsonify({
        "attendance_logs": attendance_logs,
        "absent_employees": absent_employees,
        "employee_data": employee_data,
        "overtime_data": overtime_data,
        "no_overtime_message": "No overtime records found." if not overtime_data else None
    })

# New route: Only leave requests (no attendance logs)
@admin_bp.route('/leave_requests_data', methods=['GET'])
@token_required_with_roles(required_actions=["leave_requests_data"])
def leave_requests_data(admin_id, role, role_id):
    """Return only leave requests with employee info"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            lr.request_id,
            lr.employee_id,
            e.first_name,
            e.last_name,
            e.email,
            lr.leave_type,
            lr.start_date,
            lr.end_date,
            lr.status,
            lr.remarks,
            lr.verification_status,
            lr.created_at,
            lr.total_days
        FROM leave_requests lr
        JOIN employees e ON lr.employee_id = e.employee_id
        ORDER BY lr.created_at DESC
    """)
    results = cursor.fetchall()
    leave_requests = [
        {
            "request_id": row[0],
            "employee_id": row[1],
            "first_name": row[2],
            "last_name": row[3],
            "email": row[4],
            "leave_type": row[5],
            "start_date": row[6],
            "end_date": row[7],
            "status": row[8],
            "remarks": row[9],
            "verification_status": row[10],
            "created_at": row[11],
            "total_days": row[12]
        }
        for row in results
    ]

    conn.close()
    return jsonify({"leave_requests": leave_requests})

# route for deleting absent employee for attendance logs table
@csrf.exempt
@admin_bp.route('/delete_absent', methods=['POST'])
@token_required_with_roles(required_actions=["delete_absent"])
def delete_absent(admin_id, role, role_id):
    """Remove an 'Absent' record from attendance_logs."""
    try:
        # Get data from form
        employee_id = request.form.get('employee_id')
        date = request.form.get('date')

        # Log the received parameters for debugging
        logging.debug(f"delete_absent received: employee_id={employee_id}, date={date}")
        
        # Validate parameters
        if not employee_id or not date:
            log_incident(admin_id, role, f"Missing parameters in delete_absent: employee_id={employee_id}, date={date}", 
                        severity="Medium")
            return jsonify({'error': 'Missing employee_id or date'}), 400
            
        # Ensure employee_id is an integer
        try:
            employee_id = int(employee_id)
        except ValueError:
            log_incident(admin_id, role, f"Invalid employee_id format in delete_absent: {employee_id}", 
                        severity="Medium")
            return jsonify({'error': f'Invalid employee_id format: {employee_id}'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if record exists
        cursor.execute("SELECT * FROM attendance_logs WHERE employee_id = %s AND date = %s AND status = 'Absent'",
                      (employee_id, date))
        record = cursor.fetchone()

        if not record:
            log_incident(admin_id, role, f"Absent record not found for employee {employee_id} on {date}",
                        severity="Medium", status="Under Review")
            return jsonify({'error': 'No matching absent record found'}), 404

        # Delete the record
        cursor.execute("DELETE FROM attendance_logs WHERE employee_id = %s AND date = %s AND status = 'Absent'",
                      (employee_id, date))
        conn.commit()

        log_audit(admin_id, role, "DELETE_ABSENT", f"Deleted 'Absent' record for Employee ID: {employee_id} on {date}")
        return jsonify({'success': 'Absent record deleted'}), 200

    except Exception as e:
        log_incident(admin_id, role, f"Error deleting absent record: {str(e)}", severity="Critical")
        return jsonify({'error': str(e)}), 500
    
# route for marking absent employee and display it in attendance logs table
# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
@csrf.exempt
@admin_bp.route('/mark_absent', methods=['POST'])
@token_required_with_roles(required_actions=["mark_absent"])
def mark_absent(admin_id, role, role_id):
    """Manually mark an employee's attendance status in attendance_logs."""
    logging.debug("Received request to mark employee attendance.")
    
    # Get required fields
    employee_id = request.form.get('employee_id')
    date = request.form.get('date')
    
    # Get optional fields with defaults
    remarks = request.form.get('remarks', '')
    clock_in_time = request.form.get('clock_in_time')
    clock_out_time = request.form.get('clock_out_time')
    status = request.form.get('status', 'Absent')  # Default to 'Absent' if not provided
    leave_type = request.form.get('leave_type', '')
    
    logging.debug(f"Extracted data - Employee ID: {employee_id}, Date: {date}, Status: {status}, "
                 f"Clock In: {clock_in_time}, Clock Out: {clock_out_time}, "
                 f"Leave Type: {leave_type}, Remarks: {remarks}, Admin ID: {admin_id}")

    if not employee_id or not date:
        logging.warning("Missing required data: employee_id or date")
        return jsonify({'error': 'Missing required data'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        logging.debug("Database connection established.")

        # Check if an entry already exists
        cursor.execute("SELECT * FROM attendance_logs WHERE employee_id = %s AND date = %s", (employee_id, date))
        existing_entry = cursor.fetchone()
        logging.debug(f"Existing entry check: {existing_entry}")

        if existing_entry:
            logging.warning("Attendance record already exists for the given employee and date.")
            return jsonify({'error': 'Attendance record already exists'}), 400

        # Calculate hours worked if both clock in and clock out are provided
        hours_worked = 0  # Default to 0
        if clock_in_time and clock_out_time:
            try:
                # Parse time strings (assuming format like "09:00")
                clock_in_dt = datetime.strptime(clock_in_time, "%H:%M")
                clock_out_dt = datetime.strptime(clock_out_time, "%H:%M")
                
                # Calculate the time difference in hours
                time_diff = clock_out_dt - clock_in_dt
                hours_worked = time_diff.total_seconds() / 3600
                
                # Handle negative hours (if clock out is before clock in)
                if hours_worked < 0:
                    hours_worked += 24  # Assuming shift doesn't span more than 24 hours
                    
                logging.debug(f"Calculated hours worked: {hours_worked}")
            except Exception as e:
                logging.error(f"Error calculating hours worked: {str(e)}")
                # Continue with default hours_worked if calculation fails

        # Build the SQL query dynamically based on which fields are provided
        fields = ["employee_id", "date", "status", "remarks", "hours_worked"]
        values = [employee_id, date, status, remarks, hours_worked]
        
        # Add is_overtime field with default value "No"
        fields.append("is_overtime")
        values.append("No")
        
        # Add optional fields if they exist
        if clock_in_time:
            fields.append("clock_in_time")
            values.append(clock_in_time)
        
        if clock_out_time:
            fields.append("clock_out_time")
            values.append(clock_out_time)
        
        if leave_type:
            fields.append("leave_type")
            values.append(leave_type)
            
        # Add attendance_verified and is_overtime_approved fields
        fields.append("attendance_verified")
        values.append(False)
        
        fields.append("is_overtime_approved")
        values.append(False)
            
        # Insert the attendance record
        placeholders = ", ".join(["%s"] * len(values))
        field_names = ", ".join(fields)
        
        query = f"""
            INSERT INTO attendance_logs ({field_names})
            VALUES ({placeholders})
        """
        cursor.execute(query, values)
        conn.commit()
        
        # Create a descriptive success message
        status_description = f"'{status}'" if status else "'Absent'"
        success_message = f"Employee marked as {status_description} on {date}"
        
        # Log audit action with detailed information
        action_details = f"Added attendance record for Employee ID: {employee_id} - Status: {status_description} on {date}"
        if clock_in_time:
            action_details += f", Clock In: {clock_in_time}"
        if clock_out_time:
            action_details += f", Clock Out: {clock_out_time}"
        if leave_type:
            action_details += f", Leave Type: {leave_type}"
        if remarks:
            action_details += f", Remarks: {remarks}"
            
        log_audit(admin_id, role, "MARK_ATTENDANCE", action_details)
        logging.info(f"Audit log recorded for admin {admin_id}: {action_details}")

        cursor.close()
        conn.close()
        logging.debug("Database connection closed.")

        return jsonify({'success': success_message}), 200
    except Exception as e:
        logging.error(f"Error occurred: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500