import datetime
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

# Route for updating records
@csrf.exempt
@admin_bp.route('/update_communication_records', methods=['POST'])
@token_required_with_roles(required_actions=["update_record"])
def update_record(admin_id, role,role_id):
    try:
        logging.debug(f"Request form data: {request.form}")
        logging.debug(f"Request JSON data: {request.get_json()}")

        if request.is_json:
            data = request.get_json()
            record_id = data.get('id')
            record_type = data.get('type')
            title = data.get('title')
            message = data.get('message')
            description = data.get('description')
            duration = data.get('duration')
            location = data.get('location')
            meeting_date = data.get('meeting_date')
            deadline = data.get('deadline')
        else:
            record_id = request.form.get('id')
            record_type = request.form.get('type')
            title = request.form.get('title')
            message = request.form.get('message')
            description = request.form.get('description')
            duration = request.form.get('duration')
            location = request.form.get('location')
            meeting_date = request.form.get('meeting_date')
            deadline = request.form.get('deadline')

        logging.debug(f"Extracted - ID: {record_id}, Type: {record_type}, Title: {title}, Message: {message}")

        if not record_id or not record_type:
            return jsonify({"error": "Record ID and type are required"}), 400

        update_map = {
            "announcement": ("announcements", "announcement_id"),
            "alert": ("alerts", "alert_id"),
            "meeting": ("meetings", "meeting_id"),
            "feedback": ("feedback_requests", "request_id")
        }

        table_info = update_map.get(record_type)
        if not table_info:
            return jsonify({"error": "Invalid record type"}), 400

        table_name, id_column = table_info

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(f"SELECT * FROM {table_name} WHERE {id_column} = %s", (record_id,))
        original_record = cur.fetchone()

        if not original_record:
            return jsonify({"error": "Record not found"}), 404

        update_fields = []
        values = []

        if title:
            update_fields.append("title = %s")
            values.append(title)
        if message and record_type != "meeting":
            update_fields.append("message = %s")
            values.append(message)
        if record_type == "meeting":
            if description:
                update_fields.append("description = %s")
                values.append(description)
            if duration:
                update_fields.append("duration = %s")
                values.append(duration)
            if location:
                update_fields.append("location = %s")
                values.append(location)
            if meeting_date:
                update_fields.append("meeting_date = %s")
                values.append(meeting_date)
        elif record_type == "feedback" and deadline:
            update_fields.append("deadline = %s")
            values.append(deadline)

        if not update_fields:
            return jsonify({"error": "At least one field must be provided"}), 400

        values.append(record_id)
        query = f"UPDATE {table_name} SET {', '.join(update_fields)} WHERE {id_column} = %s"

        cur.execute(query, values)
        conn.commit()

        cur.execute(f"SELECT * FROM {table_name} WHERE {id_column} = %s", (record_id,))
        updated_record = cur.fetchone()

        log_audit(admin_id, role, "Update Record", f"Updated {record_type} ID {record_id}. Before: {original_record}, After: {updated_record}")

    except Exception as e:
        logging.exception("Error updating record")
        return jsonify({"error": "An error occurred while updating the record", "details": str(e)}), 500

    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

    return jsonify({"message": "Record updated successfully"})


# Route for deleting records
@csrf.exempt
@admin_bp.route('/delete/<string:type>/<int:id>', methods=['DELETE'])
@token_required_with_roles(required_actions=["delete_record"])
def delete_record(admin_id, role, role_id, type, id):
    import logging
    
    logging.info(f"[DELETE_RECORD] Request initiated by admin_id={admin_id}, role={role} for {type} ID {id}")
    
    # Define table mappings and their dependent tables
    delete_map = {
        "announcement": {
            "main_table": "announcements",
            "id_column": "announcement_id",
            "dependent_tables": [
                ("announcement_reads", "announcement_id")
            ]
        },
        "alert": {
            "main_table": "alerts", 
            "id_column": "alert_id",
            "dependent_tables": [
                ("alert_reads", "alert_id")
            ]
        },
        "meeting": {
            "main_table": "meetings",
            "id_column": "meeting_id", 
            "dependent_tables": []  # No dependent tables currently
        },
        "feedback": {
            "main_table": "feedback_requests",
            "id_column": "request_id",
            "dependent_tables": [
                ("feedback_responses", "request_id")
            ]
        }
    }

    table_info = delete_map.get(type)
    if not table_info:
        logging.warning(f"[DELETE_RECORD] Invalid type requested: {type}")
        return jsonify({"error": "Invalid record type"}), 400

    main_table = table_info["main_table"]
    id_column = table_info["id_column"]
    dependent_tables = table_info["dependent_tables"]

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # First, check if the main record exists
        cur.execute(f"SELECT * FROM {main_table} WHERE {id_column} = %s", (id,))
        original_record = cur.fetchone()

        if not original_record:
            logging.warning(f"[DELETE_RECORD] Record not found: {type} ID {id}")
            return jsonify({"error": "Record not found"}), 404

        logging.info(f"[DELETE_RECORD] Found {type} record to delete: ID {id}")

        # CASCADE DELETE: Remove dependent records first
        deleted_dependents = []
        
        for dep_table, dep_id_column in dependent_tables:
            # Check if dependent records exist
            cur.execute(f"SELECT COUNT(*) FROM {dep_table} WHERE {dep_id_column} = %s", (id,))
            dependent_count = cur.fetchone()[0]
            
            if dependent_count > 0:
                logging.info(f"[DELETE_RECORD] Deleting {dependent_count} dependent records from {dep_table}")
                
                # Delete dependent records
                cur.execute(f"DELETE FROM {dep_table} WHERE {dep_id_column} = %s", (id,))
                deleted_dependents.append(f"{dependent_count} records from {dep_table}")
                
                logging.info(f"[DELETE_RECORD] Successfully deleted {dependent_count} records from {dep_table}")

        # Now delete the main record (foreign key constraints are satisfied)
        cur.execute(f"DELETE FROM {main_table} WHERE {id_column} = %s", (id,))
        
        # Commit all deletions in a single transaction
        conn.commit()
        
        # Prepare audit log message
        audit_message = f"Deleted {type} ID {id}"
        if deleted_dependents:
            audit_message += f" and dependent records: {', '.join(deleted_dependents)}"
        
        # Log the audit record
        log_audit(admin_id, role, "delete_record", audit_message)
        
        logging.info(f"[DELETE_RECORD] Successfully deleted {type} ID {id} and all dependent records")
        
        return jsonify({
            "message": "Record deleted successfully",
            "deleted_type": type,
            "deleted_id": id,
            "dependent_deletions": deleted_dependents if deleted_dependents else []
        }), 200

    except Exception as e:
        # Rollback transaction on any error
        conn.rollback()
        
        logging.error(f"[DELETE_RECORD][ERROR] Failed to delete {type} ID {id}: {str(e)}", exc_info=True)
        
        # Log incident for monitoring
        log_incident(admin_id, role, f"Error deleting {type} ID {id}: {str(e)}", severity="High")
        
        return jsonify({
            "error": "Failed to delete record", 
            "details": str(e),
            "type": type,
            "id": id
        }), 500

    finally:
        cur.close()
        conn.close()
        logging.debug(f"[DELETE_RECORD] Database connection closed for {type} ID {id}")
        
# Route for editing records - FULLY ROBUST VERSION
@admin_bp.route('/edit/<string:type>/<int:id>', methods=['GET'])
@token_required_with_roles(required_actions=["edit_record"])
def edit_record(admin_id, role, role_id, type, id):
    query_map = {
        "announcement": (
            "SELECT title, message FROM announcements WHERE announcement_id = %s",
            ["title", "message"]
        ),
        "alert": (
            "SELECT title, message FROM alerts WHERE alert_id = %s",
            ["title", "message"]
        ),
        "meeting": (
            "SELECT title, description, duration, location, meeting_date FROM meetings WHERE meeting_id = %s",
            ["title", "description", "duration", "location", "meeting_date"]
        ),
        "feedback": (
            "SELECT title, message, deadline FROM feedback_requests WHERE request_id = %s",
            ["title", "message", "deadline"]
        )
    }

    mapping = query_map.get(type)
    if not mapping:
        return jsonify({"error": "Invalid type"}), 400

    query, columns = mapping

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, (id,))
    data = cur.fetchone()
    cur.close()
    conn.close()

    if data:
        log_audit(admin_id, role, f"View Record", f"Viewed {type} record. ID: {id}")
        record = dict(zip(columns, data))
        for k, v in record.items():
            if hasattr(v, "isoformat"):
                try:
                    record[k] = v.isoformat(sep=' ')
                except TypeError:
                    record[k] = v.isoformat()
            elif isinstance(v, datetime.timedelta):
                record[k] = v.total_seconds()
        return jsonify(record)
    return jsonify({"error": "Record not found"}), 404

#route for rendering the page for notification and communication
@admin_bp.route('/notificationsandcommunication', methods=['GET'])
def notification_and_communication_page():
    # Just serve the HTML shell, no auth check here
    return render_template('Admin/NotificationAndCommunication.html')

#route for viewing responses for a feedback request
@admin_bp.route('/feedback_request_responses/<int:request_id>', methods=['GET'])
@token_required_with_roles(required_actions=["feedback_request_responses"])
def feedback_request_responses(admin_id, role, role_id, request_id):
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
        SELECT frs.response, frs.submitted_at, e.email, e.employee_id
        FROM feedback_responses frs
        LEFT JOIN employees e ON e.employee_id = frs.employee_id
        WHERE frs.request_id = %s
        ORDER BY frs.submitted_at DESC
    """
    cur.execute(query, (request_id,))
    columns = [desc[0] for desc in cur.description]
    responses = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(responses)

#route for fetching api for notification and communication page
@admin_bp.route('/notificationsandcommunication_data', methods=['GET'])
@token_required_with_roles(required_actions=["notification_and_communication_data"])
def notification_and_communication_data(admin_id, role, role_id):
    logging.debug("\n=== NOTIFICATIONS & COMMUNICATION DATA REQUEST ===")
    logging.debug(f"Authenticated as {role} ID {admin_id}")

    conn = get_db_connection()
    cur = conn.cursor()

    def fetch_and_process(cur):
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    # Announcements with team read counts
    queryAnnouncement = """
        WITH team_members_count AS (
            SELECT team_id, COUNT(DISTINCT employee_id) AS total_members
            FROM team_members
            GROUP BY team_id
        ),
        announcement_reads_count AS (
            SELECT announcement_id, team_id, COUNT(DISTINCT employee_id) AS read_count
            FROM announcement_reads
            WHERE team_id IS NOT NULL
            GROUP BY announcement_id, team_id
        )
        SELECT 
            e.email, 
            a.title, 
            a.team_id, 
            a.message, 
            a.employee_id, 
            a.created_at,
            CASE 
                WHEN a.team_id IS NULL THEN
                    -- For individual employee announcements
                    COALESCE(TO_CHAR(ar.read_at, 'YYYY-MM-DD HH24:MI:SS'), 'Unread')
                ELSE
                    -- For team announcements
                    CASE 
                        WHEN arc.read_count IS NULL OR arc.read_count = 0 THEN 'Unread by all team members'
                        WHEN arc.read_count = tmc.total_members THEN 'Read by all team members'
                        ELSE 'Read by ' || COALESCE(arc.read_count, 0) || ' of ' || COALESCE(tmc.total_members, 0) || ' members'
                    END
            END AS status,
            t.team_name, 
            a.announcement_id
        FROM 
            announcements a
        LEFT JOIN 
            employees e ON e.employee_id = a.employee_id
        LEFT JOIN 
            teams t ON t.team_id = a.team_id
        -- For individual announcements
        LEFT JOIN 
            announcement_reads ar ON (
                a.employee_id IS NOT NULL AND 
                ar.employee_id = a.employee_id AND 
                ar.announcement_id = a.announcement_id
            )
        -- For team member counts
        LEFT JOIN
            team_members_count tmc ON tmc.team_id = a.team_id
        -- For team announcement read counts
        LEFT JOIN
            announcement_reads_count arc ON arc.announcement_id = a.announcement_id AND arc.team_id = a.team_id
    """
    cur.execute(queryAnnouncement)
    announcements_data = fetch_and_process(cur)

    # Alerts with similar read count logic
    queryAlerts = """
        WITH team_members_count AS (
            SELECT team_id, COUNT(DISTINCT employee_id) AS total_members
            FROM team_members
            GROUP BY team_id
        ),
        alert_reads_count AS (
            SELECT alert_id, team_id, COUNT(DISTINCT employee_id) AS read_count
            FROM alert_reads
            WHERE team_id IS NOT NULL
            GROUP BY alert_id, team_id
        )
        SELECT 
            e.email, 
            t.team_name, 
            a.title, 
            a.message, 
            a.created_at, 
            a.employee_id, 
            a.team_id,
            CASE 
                WHEN a.team_id IS NULL THEN
                    -- For individual employee alerts
                    COALESCE(TO_CHAR(ar.read_at, 'YYYY-MM-DD HH24:MI:SS'), 'Unread')
                ELSE
                    -- For team alerts
                    CASE 
                        WHEN arc.read_count IS NULL OR arc.read_count = 0 THEN 'Unread by all team members'
                        WHEN arc.read_count = tmc.total_members THEN 'Read by all team members'
                        ELSE 'Read by ' || COALESCE(arc.read_count, 0) || ' of ' || COALESCE(tmc.total_members, 0) || ' members'
                    END
            END AS status,
            a.alert_id
        FROM 
            alerts a
        LEFT JOIN 
            employees e ON e.employee_id = a.employee_id
        LEFT JOIN 
            teams t ON t.team_id = a.team_id
        -- For individual alerts
        LEFT JOIN 
            alert_reads ar ON (
                a.employee_id IS NOT NULL AND 
                ar.employee_id = a.employee_id AND 
                ar.alert_id = a.alert_id
            )
        -- For team member counts
        LEFT JOIN
            team_members_count tmc ON tmc.team_id = a.team_id
        -- For team alert read counts
        LEFT JOIN
            alert_reads_count arc ON arc.alert_id = a.alert_id AND arc.team_id = a.team_id
    """
    cur.execute(queryAlerts)
    alerts_data = fetch_and_process(cur)

    # Meetings
    queryMeetings = """
        SELECT e.email, t.team_name, m.title, m.description, m.duration, 
               m.location, m.meeting_date, m.created_at, m.status, 
               e.employee_id, e.team_id, m.meeting_id
        FROM meetings m
        LEFT JOIN employees e ON e.employee_id = m.employee_id
        LEFT JOIN teams t ON t.team_id = m.team_id
    """
    cur.execute(queryMeetings)
    meetings_data = fetch_and_process(cur)

    # Convert duration timedelta to total seconds or string
    for meeting in meetings_data:
        duration = meeting.get("duration")
        if duration is not None:
            if hasattr(duration, 'total_seconds'):
                meeting["duration"] = duration.total_seconds()
            else:
                meeting["duration"] = str(duration)

    # --- FEEDBACK REQUESTS with read counts ---
    queryFeedback = """
        WITH team_members_count AS (
            SELECT team_id, COUNT(DISTINCT employee_id) AS total_members
            FROM team_members
            GROUP BY team_id
        ),
        feedback_response_count AS (
            SELECT request_id, COUNT(DISTINCT employee_id) AS responded_count
            FROM feedback_responses
            GROUP BY request_id
        )
        SELECT 
            fr.request_id, 
            fr.title, 
            fr.message, 
            fr.deadline, 
            fr.created_at, 
            fr.employee_id, 
            fr.team_id,
            e.email, 
            t.team_name,
            CASE 
                WHEN fr.team_id IS NULL THEN
                    -- For individual feedback requests
                    (SELECT COUNT(*) FROM feedback_responses frs WHERE frs.request_id = fr.request_id)
                ELSE
                    -- For team feedback requests
                    COALESCE(frc.responded_count, 0)
            END as response_count,
            CASE 
                WHEN fr.team_id IS NOT NULL THEN
                    COALESCE(tmc.total_members, 0)
                ELSE
                    1
            END as total_recipients
        FROM 
            feedback_requests fr
        LEFT JOIN 
            employees e ON e.employee_id = fr.employee_id
        LEFT JOIN 
            teams t ON t.team_id = fr.team_id
        LEFT JOIN
            team_members_count tmc ON tmc.team_id = fr.team_id
        LEFT JOIN
            feedback_response_count frc ON frc.request_id = fr.request_id
    """
    cur.execute(queryFeedback)
    feedback_data = fetch_and_process(cur)

    cur.close()
    conn.close()

    log_audit(admin_id, role, action="Viewed notifications and communication", details="Accessed all notifications and communication data")

    return jsonify({
        "announcements": announcements_data,
        "alerts": alerts_data,
        "meetings": meetings_data,
        "feedback_requests": feedback_data
    })

# Route for sending feedback requests
@csrf.exempt
@admin_bp.route('/create_feedback', methods=['POST'])
@token_required_with_roles(required_actions=["create_feedback"])
def create_feedback(admin_id, role,role_id):
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        title = data.get('title')
        message = data.get('content')
        deadline = data.get('deadline')
        target_group = data.get('target_group')
        target_id = data.get('target_id')

        if not title or not message or not deadline or not target_group:
            return jsonify({"error": "Missing required fields"}), 400

        created_at = datetime.datetime.now()
        is_super_admin = (role == 'super_admin')

        conn = get_db_connection()
        cur = conn.cursor()

        if target_group == "all":
            try:
                # Insert for all employees
                cur.execute("SELECT employee_id FROM employees")
                employees = cur.fetchall()

                for emp in employees:
                    if is_super_admin:
                        cur.execute(
                            "INSERT INTO feedback_requests (title, message, deadline, created_at, employee_id, assigned_by_super_admins) VALUES (%s, %s, %s, %s, %s, %s)",
                            (title, message, deadline, created_at, emp[0], admin_id)
                        )
                    else:
                        cur.execute(
                            "INSERT INTO feedback_requests (title, message, deadline, created_at, employee_id, assigned_by_admins) VALUES (%s, %s, %s, %s, %s, %s)",
                            (title, message, deadline, created_at, emp[0], admin_id)
                        )

                # Insert for all teams
                cur.execute("SELECT team_id FROM teams")
                teams = cur.fetchall()

                for team in teams:
                    if is_super_admin:
                        cur.execute(
                            "INSERT INTO feedback_requests (title, message, deadline, created_at, team_id, assigned_by_super_admins) VALUES (%s, %s, %s, %s, %s, %s)",
                            (title, message, deadline, created_at, team[0], admin_id)
                        )
                    else:
                        cur.execute(
                            "INSERT INTO feedback_requests (title, message, deadline, created_at, team_id, assigned_by_admins) VALUES (%s, %s, %s, %s, %s, %s)",
                            (title, message, deadline, created_at, team[0], admin_id)
                        )

                conn.commit()
                return jsonify({"message": "Feedback requests sent to all employees and teams successfully"}), 201

            except Exception as e:
                conn.rollback()
                logging.error(f"Error sending feedback to all: {e}", exc_info=True)
                return jsonify({"error": f"Failed to send feedback: {str(e)}"}), 500

        elif target_group == "employees" and target_id:
            try:
                if is_super_admin:
                    cur.execute(
                        "INSERT INTO feedback_requests (title, message, deadline, created_at, employee_id, assigned_by_super_admins) VALUES (%s, %s, %s, %s, %s, %s)",
                        (title, message, deadline, created_at, target_id, admin_id)
                    )
                else:
                    cur.execute(
                        "INSERT INTO feedback_requests (title, message, deadline, created_at, employee_id, assigned_by_admins) VALUES (%s, %s, %s, %s, %s, %s)",
                        (title, message, deadline, created_at, target_id, admin_id)
                    )

                conn.commit()
                return jsonify({"message": "Feedback request sent to employee successfully"}), 201

            except Exception as e:
                conn.rollback()
                logging.error(f"Error sending feedback to employee: {e}", exc_info=True)
                return jsonify({"error": f"Failed to send feedback: {str(e)}"}), 500

        elif target_group == "teams" and target_id:
            try:
                if is_super_admin:
                    cur.execute(
                        "INSERT INTO feedback_requests (title, message, deadline, created_at, team_id, assigned_by_super_admins) VALUES (%s, %s, %s, %s, %s, %s)",
                        (title, message, deadline, created_at, target_id, admin_id)
                    )
                else:
                    cur.execute(
                        "INSERT INTO feedback_requests (title, message, deadline, created_at, team_id, assigned_by_admins) VALUES (%s, %s, %s, %s, %s, %s)",
                        (title, message, deadline, created_at, target_id, admin_id)
                    )

                conn.commit()
                return jsonify({"message": "Feedback request sent to team successfully"}), 201

            except Exception as e:
                conn.rollback()
                logging.error(f"Error sending feedback to team: {e}", exc_info=True)
                return jsonify({"error": f"Failed to send feedback: {str(e)}"}), 500

        else:
            return jsonify({"error": "Invalid target group or missing target ID"}), 400

    except Exception as e:
        logging.error(f"Error creating feedback request: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

# Route for sending alerts to employees or teams
@csrf.exempt
@admin_bp.route('/create_alerts', methods=['POST', 'GET'])
@token_required_with_roles(required_actions=["manage_alerts"])
def manage_alerts(admin_id, role, role_id):
    import traceback
    import sys

    def debug_log(msg, **kwargs):
        print(f"[DEBUG][manage_alerts] {msg}")
        if kwargs:
            for k, v in kwargs.items():
                print(f"    {k}: {v}")

    conn = get_db_connection()
    cursor = conn.cursor()
    debug_log("Route called", method=request.method, admin_id=admin_id, role=role, role_id=role_id)

    if request.method == 'GET':
        try:
            debug_log("GET: Fetching alerts")
            cursor.execute("""
                SELECT alert_id, title, message, created_at, employee_id, team_id, alert_type, severity_level, assigned_by_admin, assigned_by_super_admin
                FROM alerts 
                ORDER BY created_at DESC
            """)
            alerts = cursor.fetchall()
            debug_log("GET: Alerts fetched", alert_count=len(alerts))
            results = [{
                "alert_id": a[0],
                "title": a[1],
                "message": a[2],
                "created_at": a[3].isoformat(),
                "employee_id": a[4],
                "team_id": a[5],
                "alert_type": a[6],
                "severity_level": a[7],
                "assigned_by_admin": a[8],
                "assigned_by_super_admin": a[9],
            } for a in alerts]
            return jsonify(results), 200
        except Exception as e:
            debug_log("GET: Exception occurred", error=str(e), traceback=traceback.format_exc())
            return jsonify({"error": str(e)}), 500
        finally:
            cursor.close()
            conn.close()

    # Handle POST
    try:
        data = request.json
        debug_log("POST: Payload received", data=data)

        title = data.get('title')
        message = data.get('message')
        target_group = data.get('target_group')
        alert_type = data.get('alert_type')
        severity_level = data.get('severity_level')

        assigned_by_admin = None
        assigned_by_super_admin = None
        if role == "super_admin":
            assigned_by_super_admin = admin_id
        else:
            assigned_by_admin = admin_id
        debug_log("POST: Assignment resolved", assigned_by_admin=assigned_by_admin, assigned_by_super_admin=assigned_by_super_admin)

        if not title or not message or not target_group:
            debug_log("POST: Missing required fields", title=title, message=message, target_group=target_group)
            cursor.close()
            conn.close()
            return jsonify({"error": "Missing required fields"}), 400

        if target_group == "all":
            debug_log("POST: Target group is 'all'")
            cursor.execute("SELECT employee_id FROM employees")
            all_employees = cursor.fetchall()
            debug_log("POST: Employees fetched", employee_count=len(all_employees))
            cursor.execute("SELECT team_id FROM teams")
            all_teams = cursor.fetchall()
            debug_log("POST: Teams fetched", team_count=len(all_teams))

            for emp in all_employees:
                debug_log("POST: Inserting alert for employee", employee_id=emp[0])
                cursor.execute(
                    """
                    INSERT INTO alerts 
                        (title, message, created_at, employee_id, team_id, alert_type, severity_level, assigned_by_admin, assigned_by_super_admin)
                    VALUES (%s, %s, NOW(), %s, NULL, %s, %s, %s, %s)
                    """,
                    (title, message, emp[0], alert_type, severity_level, assigned_by_admin, assigned_by_super_admin)
                )
            for team in all_teams:
                debug_log("POST: Inserting alert for team", team_id=team[0])
                cursor.execute(
                    """
                    INSERT INTO alerts 
                        (title, message, created_at, employee_id, team_id, alert_type, severity_level, assigned_by_admin, assigned_by_super_admin)
                    VALUES (%s, %s, NOW(), NULL, %s, %s, %s, %s, %s)
                    """,
                    (title, message, team[0], alert_type, severity_level, assigned_by_admin, assigned_by_super_admin)
                )

        elif target_group == "employees":
            employee_id = data.get('employee_id')
            debug_log("POST: Target group is 'employees'", employee_id=employee_id)
            if employee_id:
                cursor.execute(
                    """
                    INSERT INTO alerts 
                        (title, message, created_at, employee_id, team_id, alert_type, severity_level, assigned_by_admin, assigned_by_super_admin)
                    VALUES (%s, %s, NOW(), %s, NULL, %s, %s, %s, %s)
                    """,
                    (title, message, employee_id, alert_type, severity_level, assigned_by_admin, assigned_by_super_admin)
                )
            else:
                debug_log("POST: Missing employee_id for employees")
                return jsonify({"error": "Missing employee_id for target group 'employees'"}), 400

        elif target_group == "teams":
            team_id = data.get('team_id')
            debug_log("POST: Target group is 'teams'", team_id=team_id)
            if team_id:
                cursor.execute(
                    """
                    INSERT INTO alerts 
                        (title, message, created_at, employee_id, team_id, alert_type, severity_level, assigned_by_admin, assigned_by_super_admin)
                    VALUES (%s, %s, NOW(), NULL, %s, %s, %s, %s, %s)
                    """,
                    (title, message, team_id, alert_type, severity_level, assigned_by_admin, assigned_by_super_admin)
                )
            else:
                debug_log("POST: Missing team_id for teams")
                return jsonify({"error": "Missing team_id for target group 'teams'"}), 400

        else:
            debug_log("POST: Invalid target group", target_group=target_group)
            return jsonify({"error": "Invalid target group"}), 400

        conn.commit()
        debug_log("POST: Alerts committed to database")
        log_audit(admin_id, role, "Create Alert", f"Title: {title}, Target: {target_group}")
        debug_log("POST: Audit log entry created")
        return jsonify({"message": "Alert created successfully!"}), 201

    except Exception as e:
        conn.rollback()
        debug_log("POST: Exception occurred", error=str(e), traceback=traceback.format_exc())
        return jsonify({"error": "Database error", "details": str(e)}), 500

    finally:
        debug_log("POST: Closing cursor and connection")
        cursor.close()
        conn.close()
            
#route for creating an announcement
@csrf.exempt
@admin_bp.route('/create_announcement', methods=['POST'])
@token_required_with_roles(required_actions=["create_announcement"])
def create_announcement(admin_id, role,role_id):
    from datetime import datetime
    try:
        # Get the JSON data from the request
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        # Extract data from the request
        title = data.get('title')
        message = data.get('message')
        target_group = data.get('target_group')
        target_id = data.get('target_id')
        
        # Validate required fields
        if not title or not message or not target_group:
            return jsonify({"error": "Missing required fields"}), 400
            
        # Get current timestamp
        created_at = datetime.now()
        
        # Connect to the database
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Based on role, determine which admin column to use
        is_super_admin = (role == 'super_admin')
        
        if target_group == "all":
            # Insert announcements for all employees
            try:
                # Get all employees
                cur.execute("SELECT employee_id FROM employees")
                employees = cur.fetchall()
                
                # Insert announcement for each employee
                for employee in employees:
                    if is_super_admin:
                        cur.execute(
                            "INSERT INTO announcements (title, message, created_at, employee_id, assigned_by_super_admin) VALUES (%s, %s, %s, %s, %s)",
                            (title, message, created_at, employee[0], admin_id)
                        )
                    else:
                        cur.execute(
                            "INSERT INTO announcements (title, message, created_at, employee_id, assigned_by_admin) VALUES (%s, %s, %s, %s, %s)",
                            (title, message, created_at, employee[0], admin_id)
                        )
                
                # Get all teams
                cur.execute("SELECT team_id FROM teams")
                teams = cur.fetchall()
                
                # Insert announcement for each team
                for team in teams:
                    if is_super_admin:
                        cur.execute(
                            "INSERT INTO announcements (title, message, created_at, team_id, assigned_by_super_admin) VALUES (%s, %s, %s, %s, %s)",
                            (title, message, created_at, team[0], admin_id)
                        )
                    else:
                        cur.execute(
                            "INSERT INTO announcements (title, message, created_at, team_id, assigned_by_admin) VALUES (%s, %s, %s, %s, %s)",
                            (title, message, created_at, team[0], admin_id)
                        )
                
                conn.commit()
                return jsonify({"message": "Announcements sent to all employees and teams successfully"}), 201
                
            except Exception as e:
                conn.rollback()
                logging.error(f"Error sending announcements to all: {e}", exc_info=True)
                return jsonify({"error": f"Failed to send announcements: {str(e)}"}), 500
                
        elif target_group == "employees" and target_id:
            # Insert announcement for specific employee
            try:
                if is_super_admin:
                    cur.execute(
                        "INSERT INTO announcements (title, message, created_at, employee_id, assigned_by_super_admin) VALUES (%s, %s, %s, %s, %s)",
                        (title, message, created_at, target_id, admin_id)
                    )
                else:
                    cur.execute(
                        "INSERT INTO announcements (title, message, created_at, employee_id, assigned_by_admin) VALUES (%s, %s, %s, %s, %s)",
                        (title, message, created_at, target_id, admin_id)
                    )
                    
                conn.commit()
                return jsonify({"message": "Announcement sent to employee successfully"}), 201
                
            except Exception as e:
                conn.rollback()
                logging.error(f"Error sending announcement to employee: {e}", exc_info=True)
                return jsonify({"error": f"Failed to send announcement: {str(e)}"}), 500
                
        elif target_group == "teams" and target_id:
            # Insert announcement for specific team
            try:
                if is_super_admin:
                    cur.execute(
                        "INSERT INTO announcements (title, message, created_at, team_id, assigned_by_super_admin) VALUES (%s, %s, %s, %s, %s)",
                        (title, message, created_at, target_id, admin_id)
                    )
                else:
                    cur.execute(
                        "INSERT INTO announcements (title, message, created_at, team_id, assigned_by_admin) VALUES (%s, %s, %s, %s, %s)",
                        (title, message, created_at, target_id, admin_id)
                    )
                    
                conn.commit()
                return jsonify({"message": "Announcement sent to team successfully"}), 201
                
            except Exception as e:
                conn.rollback()
                logging.error(f"Error sending announcement to team: {e}", exc_info=True)
                return jsonify({"error": f"Failed to send announcement: {str(e)}"}), 500
                
        else:
            return jsonify({"error": "Invalid target group or missing target ID"}), 400
            
    except Exception as e:
        logging.error(f"Error creating announcement: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

#route for creating meetings
@csrf.exempt
@admin_bp.route('/create_meetings', methods=['POST'])
@token_required_with_roles(required_actions=["create_meeting"])
def create_meeting(admin_id, role,role_id):
    from datetime import datetime
    try:
        # Get the JSON data from the request
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        # Extract data from the request
        title = data.get('title')
        description = data.get('description')
        meeting_date_str = data.get('meeting_date')
        duration = data.get('duration')
        location = data.get('location')
        target_group = data.get('target_group')
        target_id = data.get('target_id')
        
        # Validate required fields
        if not all([title, description, meeting_date_str, duration, location, target_group]):
            return jsonify({"error": "Missing required fields"}), 400
            
        # Parse meeting date and time
        try:
            meeting_date = datetime.strptime(meeting_date_str, '%Y-%m-%d %H:%M')
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD HH:MM"}), 400
            
        # Get current timestamp for created_at
        created_at = datetime.now()
        
        # Default status for new meetings
        status = 'scheduled'
        
        # Connect to the database
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Based on role, determine which admin column to use
        is_super_admin = (role == 'super_admin')
        
        if target_group == "all":
            # Schedule meetings for all employees
            try:
                # Get all employees
                cur.execute("SELECT employee_id FROM employees")
                employees = cur.fetchall()
                
                # Insert meeting for each employee
                for employee in employees:
                    if is_super_admin:
                        cur.execute(
                            """INSERT INTO meetings 
                            (title, description, meeting_date, duration, location, created_at, 
                            employee_id, status, assigned_by_super_admins) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                            (title, description, meeting_date, duration, location, 
                            created_at, employee[0], status, admin_id)
                        )
                    else:
                        cur.execute(
                            """INSERT INTO meetings 
                            (title, description, meeting_date, duration, location, created_at, 
                            employee_id, status, assigned_by_admins) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                            (title, description, meeting_date, duration, location, 
                            created_at, employee[0], status, admin_id)
                        )
                
                # Get all teams
                cur.execute("SELECT team_id FROM teams")
                teams = cur.fetchall()
                
                # Insert meeting for each team
                for team in teams:
                    if is_super_admin:
                        cur.execute(
                            """INSERT INTO meetings 
                            (title, description, meeting_date, duration, location, created_at, 
                            team_id, status, assigned_by_super_admins) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                            (title, description, meeting_date, duration, location, 
                            created_at, team[0], status, admin_id)
                        )
                    else:
                        cur.execute(
                            """INSERT INTO meetings 
                            (title, description, meeting_date, duration, location, created_at, 
                            team_id, status, assigned_by_admins) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                            (title, description, meeting_date, duration, location, 
                            created_at, team[0], status, admin_id)
                        )
                
                conn.commit()
                return jsonify({"message": "Meeting scheduled for all employees and teams successfully"}), 201
                
            except Exception as e:
                conn.rollback()
                logging.error(f"Error scheduling meeting for all: {e}", exc_info=True)
                return jsonify({"error": f"Failed to schedule meeting: {str(e)}"}), 500
                
        elif target_group == "employees" and target_id:
            # Schedule meeting for specific employee
            try:
                if is_super_admin:
                    cur.execute(
                        """INSERT INTO meetings 
                        (title, description, meeting_date, duration, location, created_at, 
                        employee_id, status, assigned_by_super_admins) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (title, description, meeting_date, duration, location, 
                        created_at, target_id, status, admin_id)
                    )
                else:
                    cur.execute(
                        """INSERT INTO meetings 
                        (title, description, meeting_date, duration, location, created_at, 
                        employee_id, status, assigned_by_admins) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (title, description, meeting_date, duration, location, 
                        created_at, target_id, status, admin_id)
                    )
                    
                conn.commit()
                return jsonify({"message": "Meeting scheduled for employee successfully"}), 201
                
            except Exception as e:
                conn.rollback()
                logging.error(f"Error scheduling meeting for employee: {e}", exc_info=True)
                return jsonify({"error": f"Failed to schedule meeting: {str(e)}"}), 500
                
        elif target_group == "teams" and target_id:
            # Schedule meeting for specific team
            try:
                if is_super_admin:
                    cur.execute(
                        """INSERT INTO meetings 
                        (title, description, meeting_date, duration, location, created_at, 
                        team_id, status, assigned_by_super_admins) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (title, description, meeting_date, duration, location, 
                        created_at, target_id, status, admin_id)
                    )
                else:
                    cur.execute(
                        """INSERT INTO meetings 
                        (title, description, meeting_date, duration, location, created_at, 
                        team_id, status, assigned_by_admins) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (title, description, meeting_date, duration, location, 
                        created_at, target_id, status, admin_id)
                    )
                    
                conn.commit()
                return jsonify({"message": "Meeting scheduled for team successfully"}), 201
                
            except Exception as e:
                conn.rollback()
                logging.error(f"Error scheduling meeting for team: {e}", exc_info=True)
                return jsonify({"error": f"Failed to schedule meeting: {str(e)}"}), 500
                
        else:
            return jsonify({"error": "Invalid target group or missing target ID"}), 400
            
    except Exception as e:
        logging.error(f"Error scheduling meeting: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
