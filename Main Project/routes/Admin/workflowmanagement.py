from datetime import date, datetime, timedelta
from functools import wraps
import logging
import os
import traceback
import bcrypt
from flask import Blueprint, Response, render_template, jsonify, request, send_file, url_for
import psycopg2
from routes.Auth.audit import log_audit, log_incident
from routes.Auth.token import get_admin_from_token, token_required_with_roles
from routes.Auth.utils import get_db_connection
from . import admin_bp
from extensions import csrf
from PIL import Image
import io

@admin_bp.route('/workflowmanagement', methods=['GET', 'POST'])
def workflowmanagement():
    return render_template('Admin/workflowmanagement.html')
     

# Route for responding to a specific employee response on a ticket
@csrf.exempt
@admin_bp.route('/respond-ticket', methods=['POST'])
@token_required_with_roles(required_actions=["respond_to_ticket"])
def respond_to_ticket(admin_id, role, role_id):
    data = request.json
    logging.debug(f"Decoded token payload: admin_id={admin_id}, role={role}")
    logging.debug(f"Received respond ticket request with data: {data}")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        response_id = data.get('response_id')  # <-- NEW: get the employee's response_id
        admin_response = data['admin_response'].strip()

        if not admin_response:
            return jsonify({'error': 'Response message cannot be empty.'}), 400
        if not response_id:
            return jsonify({'error': 'Missing response_id.'}), 400

        # Format the responded_by_admin field
        responded_by_admin = f"{role}, ID: {admin_id}"

        # Check if the response exists
        cursor.execute("SELECT response_id FROM ticket_responses WHERE response_id = %s", (response_id,))
        if cursor.fetchone():
            # Update the existing response
            update_query = """
                UPDATE ticket_responses
                SET admin_response = %s,
                    responded_by_admin = %s,
                    responded_at = CURRENT_TIMESTAMP
                WHERE response_id = %s
            """
            cursor.execute(update_query, (admin_response, responded_by_admin, response_id))
        else:
            return jsonify({'error': 'Response not found.'}), 404

        conn.commit()
        log_audit(admin_id, role, "respond_to_ticket", f"Responded to response ID {response_id}")
        return jsonify({'message': 'Response sent successfully!'})

    except Exception as e:
        conn.rollback()
        logging.error("Error during ticket response: %s", str(e))
        log_incident(admin_id, role, f"Error responding to response ID {response_id}: {e}", severity="High")
        return jsonify({'error': 'An error occurred while sending the response.'}), 500

    finally:
        cursor.close()
        conn.close()
        logging.debug("Database connection closed")

# Route for viewing ticket details
@admin_bp.route('/view-ticket/<int:ticket_id>', methods=['GET'])
@token_required_with_roles(required_actions=["view_ticket"])
def view_ticket(admin_id, role, role_id, ticket_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get ticket + employee info
    ticket_query = """
    SELECT 
        t.ticket_id,
        t.employee_id,
        e.first_name,
        e.last_name,
        t.category,
        t.subject,
        t.description,
        t.priority,
        t.status,
        t.created_at,
        t.updated_at,
        t.file_path,
        e.email
    FROM tickets t
    LEFT JOIN employees e ON t.employee_id = e.employee_id
    WHERE t.ticket_id = %s
    """

    cursor.execute(ticket_query, (ticket_id,))
    ticket_row = cursor.fetchone()

    if not ticket_row:
        cursor.close()
        conn.close()
        log_incident(admin_id, role, f"Ticket not found: ticket_id {ticket_id}", severity="Low")
        return jsonify({"error": "Ticket not found"}), 404

    # Get all responses for this ticket
    response_query = """
    SELECT
        tr.response_id,
        tr.ticket_id,
        tr.employee_id,
        tr.response,
        tr.responded_at,
        tr.responded_by,
        tr.admin_response,
        tr.responded_by_admin
    FROM ticket_responses tr
    WHERE tr.ticket_id = %s
    ORDER BY tr.responded_at ASC
    """
    cursor.execute(response_query, (ticket_id,))
    responses = cursor.fetchall()

    cursor.close()
    conn.close()

    # Construct ticket data
    ticket_data = {
        "ticket_id": ticket_row[0],
        "employee_id": ticket_row[1],
        "employee_name": f"{ticket_row[2]} {ticket_row[3]}",
        "category": ticket_row[4],
        "subject": ticket_row[5],
        "description": ticket_row[6],
        "priority": ticket_row[7],
        "status": ticket_row[8],
        "created_at": ticket_row[9].isoformat() if ticket_row[9] else None,
        "updated_at": ticket_row[10].isoformat() if ticket_row[10] else None,
        "file_path": ticket_row[11],
        "email": ticket_row[12],
        "responses": []
    }

    # Add all response columns for each response
    for resp in responses:
        ticket_data["responses"].append({
            "response_id": resp[0],
            "ticket_id": resp[1],
            "employee_id": resp[2],
            "response": resp[3],
            "responded_at": resp[4].isoformat() if resp[4] else None,
            "responded_by": resp[5],
            "admin_response": resp[6],
            "responded_by_admin": resp[7]
        })

    log_audit(admin_id, role, "view_ticket", f"Viewed ticket ID {ticket_id}")
    return jsonify(ticket_data)

# Route for fetching ticket details for a specific ticket (for edit)
@admin_bp.route('/get-ticket/<int:ticket_id>', methods=['GET'])
@token_required_with_roles(required_actions=["get_edit_ticket"])
def get_edit_ticket(admin_id, role, role_id,ticket_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            t.ticket_id, t.category, t.subject, t.description, 
            t.priority, t.status,
            tr.responded_by, tr.response, tr.responded_at
        FROM tickets t
        LEFT JOIN (
            SELECT DISTINCT ON (ticket_id) ticket_id, responded_by, response, responded_at
            FROM ticket_responses
            WHERE ticket_id = %s
            ORDER BY ticket_id, responded_at DESC
        ) tr ON t.ticket_id = tr.ticket_id
        WHERE t.ticket_id = %s
    """
    cursor.execute(query, (ticket_id, ticket_id))
    ticket = cursor.fetchone()
    cursor.close()
    conn.close()

    if not ticket:
        log_incident(admin_id, role, f"Ticket not found: ticket_id {ticket_id}", severity="Low")
        return jsonify({"error": "Ticket not found"}), 404

    ticket_data = {
        "ticket_id": ticket[0],
        "category": ticket[1],
        "subject": ticket[2],
        "description": ticket[3],
        "priority": ticket[4],
        "status": ticket[5],
        "responded_by": ticket[6],
        "response_message": ticket[7],
        "responded_at": ticket[8].isoformat() if ticket[8] else None
    }
    log_audit(admin_id, role, "get_edit_ticket", f"Fetched ticket for editing: ticket_id {ticket_id}")
    return jsonify(ticket_data)

# Route for fetching ticket details to display in a table
@admin_bp.route('/get-tickets', methods=['GET'])
@token_required_with_roles(required_actions=["get_tickets"])
def get_tickets(admin_id, role, role_id):
    search_query = request.args.get('search', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Only join tickets and employees
    query = """
    SELECT 
        t.ticket_id, 
        t.employee_id, 
        e.first_name, 
        e.last_name,
        t.category, 
        t.subject, 
        t.description, 
        t.priority,
        t.status, 
        t.created_at, 
        t.updated_at,
        t.file_path,
        e.email
    FROM tickets t
    LEFT JOIN employees e ON t.employee_id = e.employee_id
    WHERE 
        CAST(t.ticket_id AS TEXT) ILIKE %s OR
        e.first_name ILIKE %s OR
        e.last_name ILIKE %s OR
        t.category ILIKE %s OR
        t.subject ILIKE %s OR 
        t.description ILIKE %s OR
        t.priority ILIKE %s OR
        t.status ILIKE %s
    ORDER BY t.created_at DESC
    """

    search_param = f"%{search_query}%"
    cursor.execute(query, (
        search_param, search_param, search_param,
        search_param, search_param, search_param,
        search_param, search_param
    ))

    tickets = cursor.fetchall()
    cursor.close()
    conn.close()

    ticket_list = [
        {
            "ticket_id": row[0],
            "employee_id": row[1],
            "employee_name": f"{row[2] or ''} {row[3] or ''}".strip(),
            "category": row[4],
            "subject": row[5],
            "description": row[6],
            "priority": row[7],
            "status": row[8],
            "created_at": row[9].strftime("%Y-%m-%d %H:%M:%S") if row[9] else "",
            "updated_at": row[10].strftime("%Y-%m-%d %H:%M:%S") if row[10] else "",
            "file_path": row[11] or "",
            "email": row[12] or ""
        }
        for row in tickets
    ]
    log_audit(admin_id, role, "get_tickets", f"Fetched tickets with search '{search_query}' (count: {len(ticket_list)})")
    return jsonify({'tickets': ticket_list})

# Route for editing ticket
@csrf.exempt
@admin_bp.route('/edit-ticket', methods=['POST'])
@token_required_with_roles(required_actions=["edit_ticket"])
def edit_ticket(admin_id, role, role_id):
    data = request.json
    print("Received edit ticket request with data:", data)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Update ticket info
        ticket_update_query = """
            UPDATE tickets
            SET category = %s, subject = %s, description = %s,
                priority = %s, status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE ticket_id = %s
        """
        cursor.execute(ticket_update_query, (
            data['category'], data['subject'], data['description'],
            data['priority'], data['status'], data['ticket_id']
        ))

        # Check if response exists
        cursor.execute("SELECT response_id FROM ticket_responses WHERE ticket_id = %s", (data['ticket_id'],))
        response = cursor.fetchone()

        response_message = data.get('response_message', '').strip()
        responded_by = data.get('responded_by', '').strip()
        responded_at = data.get('responded_at')

        if response and response_message and responded_by and responded_at:
            try:
                responded_at_dt = datetime.fromisoformat(responded_at)
                response_update_query = """
                    UPDATE ticket_responses
                    SET response = %s, responded_by = %s, responded_at = %s
                    WHERE ticket_id = %s
                """
                cursor.execute(response_update_query, (
                    response_message,
                    responded_by,
                    responded_at_dt,
                    data['ticket_id']
                ))
            except Exception as e:
                print("Error parsing or updating response fields:", e)
        else:
            print("Skipping response update (no response or incomplete data).")

        conn.commit()
        log_audit(admin_id, role, "edit_ticket", f"Edited ticket ID {data['ticket_id']}")
        return jsonify({'message': 'Ticket updated successfully!'})

    except Exception as e:
        conn.rollback()
        print("Error during ticket update:", str(e))
        log_incident(admin_id, role, f"Error updating ticket ID {data.get('ticket_id', '<unknown>')}: {e}", severity="High")
        return jsonify({'error': 'An error occurred while updating the ticket.'}), 500

    finally:
        cursor.close()
        conn.close()

# Route for deleting ticket
@csrf.exempt
@admin_bp.route('/delete-ticket/<int:ticket_id>', methods=['DELETE'])
@token_required_with_roles(required_actions=["delete_ticket"])
def delete_ticket(admin_id, role, role_id,ticket_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM tickets WHERE ticket_id = %s", (ticket_id,))
    conn.commit()
    cursor.close()
    conn.close()
    log_audit(admin_id, role, "delete_ticket", f"Deleted ticket ID {ticket_id}")

    return jsonify({'message': 'Ticket deleted successfully!'})

# Route for updating timesheet status (approve/reject)
@csrf.exempt
@admin_bp.route("/update-timesheet-status", methods=["POST"])
@token_required_with_roles(required_actions=["update_timesheet_status"])
def update_timesheet_status(admin_id, role, role_id):
    logging.debug("Received request to update timesheet status.")
    
    data = request.get_json()
    logging.debug(f"Request data: {data}")
    
    timesheet_id = data.get("timesheet_id")
    status = data.get("status")
    logging.debug(f"Parsed timesheet_id: {timesheet_id}, status: {status}")
    
    if not timesheet_id or status not in ['approved', 'rejected']:
        logging.warning("Invalid input: missing timesheet_id or invalid status.")
        return jsonify({"message": "Invalid input. Timesheet ID and status (Approved/Rejected) are required."}), 400

    try:
        logging.debug("Connecting to the database.")
        conn = get_db_connection()
        cursor = conn.cursor()

        approved_by = f"{role}, ID: {admin_id}"
        logging.debug(f"Constructed approved_by: {approved_by}")

        query = """
            UPDATE timesheets
            SET status = %s,
                approved_by = %s
            WHERE timesheet_id = %s
        """
        logging.debug(f"Executing SQL query: {query}")
        logging.debug(f"With parameters: ({status}, {approved_by}, {timesheet_id})")

        cursor.execute(query, (status, approved_by, timesheet_id))
        conn.commit()

        logging.info(f"Timesheet ID {timesheet_id} updated to status '{status}' by {approved_by}.")
        log_audit(admin_id, role, "update_timesheet_status", f"Updated timesheet ID {timesheet_id} to status '{status}'")
        return jsonify({"message": f"Timesheet {status.lower()} successfully."})

    except Exception as e:
        logging.error(f"Error updating timesheet status: {e}")
        conn.rollback()
        log_incident(admin_id, role, f"Error updating timesheet ID {timesheet_id}: {e}", severity="High")
        return jsonify({"message": "Error updating timesheet status.", "error": str(e)}), 500

    finally:
        logging.debug("Closing database connection.")
        cursor.close()
        conn.close()

# Route for deleting timesheet
@csrf.exempt
@admin_bp.route("/delete-timesheet", methods=["POST"])
@token_required_with_roles(required_actions=["delete_timesheet"])
def delete_timesheet(admin_id, role, role_id):
    data = request.get_json()
    timesheet_id = data.get("timesheet_id")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM timesheets WHERE timesheet_id = %s", (timesheet_id,))
    conn.commit()
    log_audit(admin_id, role, "delete_timesheet", f"Deleted timesheet ID {timesheet_id}")
    return jsonify({"message": "Timesheet deleted successfully."})

# Route for editing timesheet
@csrf.exempt
@admin_bp.route("/edit-timesheet", methods=["POST"])
@token_required_with_roles(required_actions=["edit_timesheet"])
def edit_timesheet(admin_id, role, role_id):
    data = request.get_json()
    timesheet_id = data.get("timesheet_id")
    total_work_hours = data.get("total_work_hours")
    total_break_time = data.get("total_break_time")
    overtime = data.get("overtime")

    conn = get_db_connection()
    cursor = conn.cursor()

    update_fields = []
    update_values = []

    if total_work_hours is not None:
        update_fields.append("total_work_hours = %s")
        update_values.append(total_work_hours)

    if total_break_time is not None:
        update_fields.append("total_break_time = %s")
        update_values.append(total_break_time)

    if overtime is not None:
        update_fields.append("overtime = %s")
        update_values.append(overtime)

    if not update_fields:
        return jsonify({"message": "No updates provided"}), 400

    # Add updated_at
    update_fields.append("updated_at = NOW()")

    update_values.append(timesheet_id)
    query = f"UPDATE timesheets SET {', '.join(update_fields)} WHERE timesheet_id = %s"

    try:
        cursor.execute(query, update_values)
        conn.commit()
        log_audit(admin_id, role, "edit_timesheet", f"Edited timesheet ID {timesheet_id}")
        return jsonify({"message": "Timesheet updated successfully."})
    except Exception as e:
        conn.rollback()
        log_incident(admin_id, role, f"Error editing timesheet ID {timesheet_id}: {e}", severity="High")
        return jsonify({"message": "Error updating timesheet.", "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
        
def format_seconds_to_hms(seconds):
    if not seconds:
        return '0 hours 0 minutes 0 seconds'
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    # Build a human-readable format
    time_parts = []
    
    if hours > 0:
        time_parts.append(f"{int(hours)} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        time_parts.append(f"{int(minutes)} minute{'s' if minutes != 1 else ''}")
    if seconds > 0:
        time_parts.append(f"{int(seconds)} second{'s' if seconds != 1 else ''}")
    
    # If there are no parts (i.e., all are 0), display 0 for all
    if not time_parts:
        return '0 hours 0 minutes 0 seconds'
    
    return ' '.join(time_parts)

# Route for fetching timesheet details 
@admin_bp.route('/get-timesheet-details', methods=['GET'])
@token_required_with_roles(required_actions=["get_timesheet_details"])
def get_timesheet_details(admin_id, role, role_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            t.timesheet_id, e.employee_id, e.email, 
            t.log_date, t.total_work_hours, t.total_break_time, 
            t.overtime, t.status
        FROM timesheets t
        JOIN employees e ON t.employee_id = e.employee_id
    """

    cursor.execute(query)
    timesheets = cursor.fetchall()
    cursor.close()
    conn.close()

    def format_time_hms(time_value):
        if time_value is None:
            return "00:00:00"
        if isinstance(time_value, timedelta):
            seconds = int(time_value.total_seconds())
        else:
            seconds = int(time_value)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        remaining_seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"

    timesheet_list = [
        {
            "timesheet_id": row[0],
            "employee_id": row[1],
            "employee_name": row[2],
            "log_date": row[3].strftime("%Y-%m-%d"),
            "total_work_hours": format_time_hms(row[4]),
            "total_break_time": format_time_hms(row[5]),
            "overtime": format_time_hms(row[6]),
            "status": row[7]
        } for row in timesheets
    ]

    log_audit(admin_id, role, "get_timesheet_details", f"Fetched {len(timesheet_list)} timesheet details")
    return jsonify({'timesheets': timesheet_list})

# Route for searching employees
@admin_bp.route('/get_employees_timesheet', methods=['GET'])
@token_required_with_roles(required_actions=["get_employees_timesheet"])
def get_employees_timesheet(admin_id, role, role_id):
    logging.debug(f"Admin {admin_id} with role '{role}' accessed /search-employees")

    search_query = request.args.get('query', '')
    logging.debug(f"Search query received: '{search_query}'")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        logging.debug("Database connection established.")

        query = """
            SELECT 
                e.employee_id, 
                e.email, 
                t.timesheet_id,
                t.log_date,
                t.total_work_hours,
                t.total_break_time,
                t.overtime,
                t.status,
                t.submitted_at,
                t.approved_by,
                r.role_name
            FROM employees e
            LEFT JOIN timesheets t ON e.employee_id = t.employee_id
            LEFT JOIN roles r ON r.role_id = e.role_id
            WHERE e.email ILIKE %s
            ORDER BY t.log_date DESC NULLS LAST
        """

        params = (f"%{search_query}%",)
        logging.debug(f"Executing SQL query with parameters: {params}")
        cursor.execute(query, params)

        rows = cursor.fetchall()
        logging.debug(f"Query executed successfully. {len(rows)} record(s) found.")

        colnames = [desc[0] for desc in cursor.description]

        def serialize(value):
            if isinstance(value, (datetime, timedelta)):
                return str(value)
            return value

        results = [ {col: serialize(val) for col, val in zip(colnames, row)} for row in rows ]

        log_audit(admin_id, role, "search_employees_timesheet", f"Searched employees with query '{search_query}', found {len(results)} results")
        return jsonify({'employees': results})

    except Exception as e:
        logging.error(f"Error during search query: {e}")
        log_incident(admin_id, role, f"Error searching employees for timesheet: {e}", severity="High")
        return jsonify({"message": "Error retrieving employees", "error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
            logging.debug("Database cursor closed.")
        if conn:
            conn.close()
            logging.debug("Database connection closed.")

# Route for generating timesheet
@csrf.exempt
@admin_bp.route('/generate-timesheet', methods=['POST'])
@token_required_with_roles(required_actions=["generate_timesheet"])
def generate_timesheet(admin_id, role, role_id):
    from datetime import timedelta
    from dateutil.parser import isoparse

    data = request.json
    employee_id = data.get('employee_id')
    log_date = data.get('log_date')

    logging.debug("Received timesheet generation request.")
    logging.debug(f"Employee ID: {employee_id}, Log Date: {log_date}")

    if not employee_id or not log_date:
        logging.warning("Missing employee_id or log_date in request.")
        return jsonify({'message': 'Missing employee_id or log_date'}), 400

    try:
        logging.debug("Connecting to the database.")
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT log_id, clock_in_time, clock_out_time
            FROM attendance_logs
            WHERE employee_id = %s AND date = %s AND clock_in_time IS NOT NULL AND clock_out_time IS NOT NULL
            """,
            (employee_id, log_date)
        )
        log_row = cursor.fetchone()
        if not log_row:
            logging.warning("No valid attendance log found for the given employee and date.")
            return jsonify({'message': 'No valid attendance data found.'}), 400

        log_id, clock_in_time, clock_out_time = log_row

        clock_in_str = f"{log_date}T{clock_in_time}"
        clock_out_str = f"{log_date}T{clock_out_time}"
        clock_in_dt = isoparse(clock_in_str)
        clock_out_dt = isoparse(clock_out_str)
        work_duration = clock_out_dt - clock_in_dt

        cursor.execute(
            """
            SELECT 
                array_agg(b.break_id) AS break_ids,
                COALESCE(SUM(b.break_duration), INTERVAL '0 seconds') AS total_break_time
            FROM employee_breaks b
            WHERE b.log_id = %s
            """,
            (log_id,)
        )
        breaks_row = cursor.fetchone()
        break_ids = breaks_row[0] if breaks_row and breaks_row[0] is not None else []
        if break_ids is None:
            break_ids = []
        break_ids = list(break_ids)  # <-- Ensure it is a list

        logging.debug(f"break_ids type: {type(break_ids)}, value: {break_ids}")

        total_break_time_pg = breaks_row[1] if breaks_row else timedelta(0)

        if isinstance(total_break_time_pg, str):
            (h, m, s) = total_break_time_pg.split(':')
            if '.' in s:
                s, ms = s.split('.')
                ms = int(ms.ljust(6, "0"))  # pad to microseconds
            else:
                ms = 0
            total_break_td = timedelta(hours=int(h), minutes=int(m), seconds=int(s), microseconds=int(ms))
        else:
            total_break_td = total_break_time_pg if total_break_time_pg else timedelta(0)

        total_work_hours = work_duration - total_break_td
        overtime = total_work_hours - timedelta(hours=8)
        if overtime < timedelta(0):
            overtime = timedelta(0)

        insert_query = """
            INSERT INTO timesheets (
                employee_id, log_date, total_work_hours, total_break_time, overtime, break_id, log_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s
            ) RETURNING timesheet_id;
        """
        cursor.execute(
            insert_query,
            (
                employee_id,
                log_date,
                str(total_work_hours),
                str(total_break_td),
                str(overtime),
                break_ids,  # THIS IS ALWAYS A LIST!
                log_id
            )
        )
        result = cursor.fetchone()

        if result:
            logging.debug(f"Timesheet inserted, ID: {result[0]}")
            conn.commit()
            log_audit(admin_id, role, "generate_timesheet", f"Generated timesheet ID {result[0]} for employee {employee_id} on {log_date}")
            return jsonify({'message': 'Timesheet generated successfully!', 'timesheet_id': result[0]})
        else:
            logging.warning("Failed to insert timesheet for the given employee and date.")
            return jsonify({'message': 'Failed to insert timesheet.'}), 400

    except Exception as e:
        logging.error(f"Error executing query: {e}")
        conn.rollback()
        log_incident(admin_id, role, f"Error generating timesheet for employee {employee_id} on {log_date}: {e}", severity="High")
        return jsonify({'message': 'Error generating timesheet.', 'error': str(e)}), 500

    finally:
        logging.debug("Closing database connection.")
        cursor.close()
        conn.close() 

# route for viewing details of timesheet
def serialize_timesheet_row(row, columns):
    timesheet = {}
    for key, value in zip(columns, row):
        if isinstance(value, timedelta):
            total_seconds = int(value.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            timesheet[key] = f"{hours}:{minutes}:{seconds}"
        elif isinstance(value, (datetime, date)):
            timesheet[key] = value.isoformat()
        else:
            timesheet[key] = value
    return timesheet

def serialize_break_row(row, columns):
    out = {}
    for key, value in zip(columns, row):
        if isinstance(value, timedelta):
            total_seconds = int(value.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            out[key] = f"{hours}:{minutes}:{seconds}"
        elif isinstance(value, (datetime, date)):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out

@csrf.exempt
@admin_bp.route('/get-timesheet-detail/<int:timesheet_id>', methods=['GET'])
@token_required_with_roles(required_actions=["view_timesheet"])
def get_timesheet_detail(admin_id, role, role_id, timesheet_id):
    logging.debug("Received request to fetch timesheet details.")
    logging.debug(f"Admin ID: {admin_id}, Role: {role}, Role ID: {role_id}, Timesheet ID: {timesheet_id}")

    try:
        logging.debug("Connecting to the database.")
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Get timesheet (with employee), make sure to fetch log_id for break lookup
        query_ts = """
            SELECT 
                t.timesheet_id,
                t.employee_id,
                e.first_name || ' ' || e.last_name AS employee_name,
                t.log_date,
                t.total_work_hours,
                t.total_break_time,
                t.overtime,
                t.status,
                t.submitted_at,
                t.updated_at,
                t.log_id -- fetch log_id for break lookup
            FROM timesheets t
            LEFT JOIN employees e ON t.employee_id = e.employee_id
            WHERE t.timesheet_id = %s
        """
        logging.debug(f"Executing SQL query for timesheet: {query_ts.strip()}")
        logging.debug(f"With parameter: timesheet_id = {timesheet_id}")

        cursor.execute(query_ts, (timesheet_id,))
        row = cursor.fetchone()
        logging.debug(f"Timesheet query result: {row}")

        if not row:
            logging.warning(f"Timesheet with ID {timesheet_id} not found.")
            return jsonify({"message": "Timesheet not found."}), 404
        
        columns = [desc[0] for desc in cursor.description]
        timesheet = serialize_timesheet_row(row, columns)
        logging.debug(f"Timesheet details dict (serialized): {timesheet}")

        log_id = row[columns.index('log_id')]

        # 2. Get all breaks for this timesheet's log_id (recommended approach)
        query_breaks = """
            SELECT break_id, break_type, break_start, break_end, break_duration
            FROM employee_breaks
            WHERE log_id = %s
            ORDER BY break_start
        """
        logging.debug(f"Executing SQL query for breaks: {query_breaks.strip()}")
        logging.debug(f"With parameter: log_id={log_id}")

        cursor.execute(query_breaks, (log_id,))
        break_rows = cursor.fetchall()
        break_columns = [desc[0] for desc in cursor.description]
        logging.debug(f"Breaks columns: {break_columns}")
        logging.debug(f"Breaks row count: {len(break_rows)}")

        breaks = [serialize_break_row(br, break_columns) for br in break_rows]
        logging.debug(f"Breaks details list (serialized): {breaks}")

        # Compose the response
        detail = timesheet
        detail['breaks'] = breaks

        return jsonify({"timesheet": detail}), 200

    except Exception as e:
        logging.error(f"Error fetching timesheet details: {e}", exc_info=True)
        return jsonify({"message": "Error fetching timesheet details", "error": str(e)}), 500
    finally:
        logging.debug("Closing database connection and cursor.")
        try:
            cursor.close()
        except Exception as e:
            logging.error(f"Error closing cursor: {e}")
        try:
            conn.close()
        except Exception as e:
            logging.error(f"Error closing connection: {e}")
            
#function to check if permission that admin has is approved or not
def require_approved_admin(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Correctly unpack the returned values
        admin_id, role = get_admin_from_token()

        if not admin_id or not role:
            logging.error("Unauthorized access attempt. No valid admin found in token.")
            return jsonify({'error': 'Unauthorized'}), 403

        conn = get_db_connection()
        cursor = conn.cursor()

        # Super Admins are automatically approved
        if role == "super_admin":
            logging.debug(f"Super Admin {admin_id} has full access. No approval required.")
            return func(*args, **kwargs)

        # Get the current route name and remove blueprint prefix if it exists
        route_name = request.endpoint
        if not route_name:
            logging.error("Unable to determine the requested route.")
            return jsonify({'error': 'Unauthorized'}), 403

        # Remove the blueprint prefix if present
        if '.' in route_name:
            route_name = route_name.split('.', 1)[-1]  # Keep only the last part

        logging.debug(f"Checking approval for route: {route_name}")

        # Check if the route exists in pending_approvals for the admin
        cursor.execute("""
            SELECT status FROM pending_approvals
            WHERE admin_id = %s AND route = %s
        """, (admin_id, route_name))
        approval_status = cursor.fetchone()

        cursor.close()
        conn.close()

        if not approval_status or approval_status[0] != 'approved':
            logging.debug(f"Admin with ID {admin_id} does not have approval for route {route_name}.")
            return jsonify({'error': 'You are not approved to access this route yet.'}), 403

        return func(*args, **kwargs)

    return wrapper

# --- ROUTE: Get all routes and their actions (with description) ---
@admin_bp.route("/routes_request", methods=["GET"])
@token_required_with_roles(required_actions=["get_all_routes_and_actions_to_request"])
def get_all_routes_and_actions_to_request(admin_id, role, role_id):
    # Optional: admin_id to pre-check which actions are granted
    target_admin_id = request.args.get("admin_id", type=int)
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get all routes and their actions
        cur.execute("""
            SELECT r.id, r.route_name, r.description, a.id, a.action_name, a.description
            FROM routes r
            LEFT JOIN route_actions ra ON r.id = ra.route_id
            LEFT JOIN actions a ON ra.action_id = a.id
            ORDER BY r.route_name, a.action_name
        """)
        rows = cur.fetchall()

        # If admin_id is provided, get granted actions for each route
        granted = {}
        if target_admin_id:
            cur.execute("""
                SELECT r.id AS route_id, a.id AS action_id
                FROM admin_route_actions ara
                JOIN routes r ON ara.route_id = r.id
                JOIN actions a ON ara.action_id = a.id
                WHERE ara.admin_id = %s
            """, (target_admin_id,))
            for route_id, action_id in cur.fetchall():
                granted.setdefault(route_id, set()).add(action_id)

        cur.close()
        conn.close()

        # Organize response
        routes_dict = {}
        for route_id, route_name, route_desc, action_id, action_name, action_desc in rows:
            if route_id not in routes_dict:
                routes_dict[route_id] = {
                    "route_id": route_id,
                    "route_name": route_name,
                    "description": route_desc,
                    "actions": []
                }
            if action_id:
                # Mark granted if in set
                is_granted = False
                if target_admin_id and route_id in granted and action_id in granted[route_id]:
                    is_granted = True
                routes_dict[route_id]["actions"].append({
                    "action_id": action_id,
                    "action_name": action_name,
                    "description": action_desc,
                    "granted": is_granted
                })
        routes = list(routes_dict.values())

        log_audit(admin_id, role, "get_all_routes_and_actions_to_request", f"Fetched all routes and their actions, admin_id={target_admin_id}")
        return jsonify({"routes": routes})
    except Exception as e:
        log_incident(admin_id, role, f"Failed to fetch all routes and actions: {str(e)}", severity="Medium")
        return jsonify({"error": "Failed to fetch routes and actions"}), 500

# --- 2. Submit access request ---
@csrf.exempt
@admin_bp.route("/request-access", methods=["POST"])
@token_required_with_roles(required_actions=["request_access"])
def request_access(admin_id, role, role_id):
    data = request.json
    requests = data.get("requests", [])
    if not requests:
        return jsonify({"error": "No requests provided."}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        inserted = 0
        for req in requests:
            route_id = req.get("route_id")
            action_id = req.get("action_id")
            if not route_id or not action_id:
                continue

            # Check for existing pending/approved requests for this admin OR super_admin
            if role == "super_admin":
                cur.execute("""
                    SELECT 1 FROM admin_access_requests
                    WHERE super_admin_id=%s AND route_id=%s AND action_id=%s AND status IN ('pending','approved')
                """, (admin_id, route_id, action_id))
            else:
                cur.execute("""
                    SELECT 1 FROM admin_access_requests
                    WHERE admin_id=%s AND route_id=%s AND action_id=%s AND status IN ('pending','approved')
                """, (admin_id, route_id, action_id))
            if cur.fetchone():
                continue

            if role == "super_admin":
                cur.execute("""
                    INSERT INTO admin_access_requests (super_admin_id, route_id, action_id, requested_at, status)
                    VALUES (%s, %s, %s, %s, 'pending')
                """, (admin_id, route_id, action_id, datetime.utcnow()))
            else:
                cur.execute("""
                    INSERT INTO admin_access_requests (admin_id, route_id, action_id, requested_at, status)
                    VALUES (%s, %s, %s, %s, 'pending')
                """, (admin_id, route_id, action_id, datetime.utcnow()))
            inserted += 1
        conn.commit()
        log_audit(admin_id, role, "request_access", f"Requested access for {inserted} route actions")
        return jsonify({"message": f"Submitted {inserted} request(s)."}), 201
    except Exception as e:
        conn.rollback()
        log_incident(admin_id, role, f"Failed to request access: {str(e)}", severity="High")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# --- 3. List my requests ---
@csrf.exempt
@admin_bp.route("/my_requests", methods=["GET"])
@token_required_with_roles(required_actions=["get_my_requests"])
def get_my_requests(admin_id, role, role_id):
    import logging
    logging.debug(f"my_requests() called with admin_id={admin_id}, role={role}, role_id={role_id}")

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        logging.debug("Database connection and cursor established.")

        # Log which query will be executed
        if role == "super_admin":
            query = """
                SELECT ar.id, r.route_name, a.action_name, ar.status, ar.requested_at
                FROM admin_access_requests ar
                JOIN routes r ON ar.route_id = r.id
                JOIN actions a ON ar.action_id = a.id
                WHERE ar.super_admin_id = %s
                ORDER BY ar.requested_at DESC
            """
            params = (admin_id,)
            logging.debug(f"Executing query for super_admin: {query} with params {params}")
            cur.execute(query, params)
        else:
            query = """
                SELECT ar.id, r.route_name, a.action_name, ar.status, ar.requested_at
                FROM admin_access_requests ar
                JOIN routes r ON ar.route_id = r.id
                JOIN actions a ON ar.action_id = a.id
                WHERE ar.admin_id = %s
                ORDER BY ar.requested_at DESC
            """
            params = (admin_id,)
            logging.debug(f"Executing query for admin: {query} with params {params}")
            cur.execute(query, params)

        rows = cur.fetchall()
        logging.debug(f"Fetched {len(rows)} rows from the database.")

        requests = [
            {
                "id": row[0],
                "route_name": row[1],
                "action_name": row[2],
                "status": row[3],
                "requested_at": row[4].isoformat() if row[4] else None
            }
            for row in rows
        ]
        logging.debug(f"Constructed requests list: {requests}")

        log_audit(admin_id, role, "my-requests", f"Fetched {len(requests)} requests for self")
        return jsonify({"requests": requests})

    except Exception as e:
        logging.error(f"Exception in my_requests: {str(e)}")
        logging.error(traceback.format_exc())
        log_incident(admin_id, role, f"Error fetching my requests: {e}", severity="High")
        return jsonify({"error": "Failed to fetch requests", "details": str(e)}), 500

    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
            logging.debug("Database connection and cursor closed.")
        except Exception as close_err:
            logging.error(f"Error closing DB resources: {str(close_err)}")
            
#Route for workflow management (End)