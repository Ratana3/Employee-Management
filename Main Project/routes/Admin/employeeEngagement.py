from datetime import datetime, timedelta
import logging
import os
import traceback
import bcrypt
from flask import Blueprint, Response, json, render_template, jsonify, request, send_file, send_from_directory, url_for
import psycopg2
from routes.Auth.token import token_required_with_roles,get_admin_from_token
from routes.Auth.utils import get_db_connection
from routes.Auth.config import HEALTH_RESOURCES, allowed_file
from . import admin_bp
from extensions import csrf
from PIL import Image
import io
from werkzeug.utils import secure_filename

@admin_bp.route('/employeeEngagement', methods=['GET', 'POST'])
def employeeEngagement():
    return render_template('Admin/employeeEngagement.html')


# Route to fetch all travel requests (fetching all columns in travel_requests)
@admin_bp.route("/admin/travel-requests", methods=["GET"])
@token_required_with_roles(required_actions=["get_travel_requests"])
def get_travel_requests(admin_id, role, role_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        query = """
            SELECT tr.request_id, tr.employee_id, tr.destination, tr.start_date, tr.end_date, 
                   tr.purpose, tr.estimated_expense, tr.status, tr.submission_date, 
                   tr.approved_by, tr.remarks, e.email
            FROM travel_requests tr
            JOIN employees e ON e.employee_id = tr.employee_id
            ORDER BY tr.submission_date DESC
        """
        cur.execute(query)
        rows = cur.fetchall()

        travel_requests = []
        for row in rows:
            travel_requests.append({
                "request_id": row[0],
                "employee_id": row[1],
                "destination": row[2],
                "start_date": row[3].strftime("%Y-%m-%d") if row[3] else None,
                "end_date": row[4].strftime("%Y-%m-%d") if row[4] else None,
                "purpose": row[5],
                "estimated_expense": float(row[6]) if row[6] is not None else None,
                "status": row[7],
                "submission_date": row[8].strftime("%Y-%m-%d %H:%M:%S") if row[8] else None,
                "approved_by": row[9],
                "remarks": row[10],
                "email": row[11]
            })

        cur.close()
        conn.close()

        return jsonify(travel_requests)

    except Exception as e:
        print("Error fetching travel requests:", e)
        return jsonify({"error": "Failed to fetch travel requests"}), 500
    
# Route to approve a travel request
@csrf.exempt
@admin_bp.route("/admin/travel-requests/<int:request_id>/approve", methods=["POST"])
@token_required_with_roles(required_actions=["approve_travel_request"])
def approve_travel_request(admin_id, role, role_id,request_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        data = request.get_json(silent=True) or {}
        remarks = data.get("remarks", None)

        if remarks is not None:
            query = """
                UPDATE travel_requests
                SET status = 'Approved',
                    approved_by = %s,
                    remarks = %s
                WHERE request_id = %s
            """
            cur.execute(query, (f"{role} ID:{admin_id}", remarks, request_id))
        else:
            query = """
                UPDATE travel_requests
                SET status = 'Approved',
                    approved_by = %s
                WHERE request_id = %s
            """
            cur.execute(query, (f"{role} ID:{admin_id}", request_id))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Travel request approved"})

    except Exception as e:
        print("Error approving travel request:", e)
        return jsonify({"error": "Failed to approve travel request"}), 500
    
# Route to delete a travel request
@csrf.exempt
@admin_bp.route("/admin/travel-requests/<int:request_id>/delete", methods=["POST"])
@token_required_with_roles(required_actions=["delete_travel_request"])
def delete_travel_request(admin_id, role, role_id, request_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Delete the travel request
        query = "DELETE FROM travel_requests WHERE request_id = %s"
        cur.execute(query, (request_id,))
        conn.commit()

        cur.close()
        conn.close()

        if cur.rowcount == 0:
            return jsonify({"success": False, "message": "Travel request not found"}), 404

        return jsonify({"success": True, "message": "Travel request deleted"})

    except Exception as e:
        print("Error deleting travel request:", e)
        return jsonify({"error": "Failed to delete travel request"}), 500

# Route to reject a travel request
@csrf.exempt
@admin_bp.route("/admin/travel-requests/<int:request_id>/reject", methods=["POST"])
@token_required_with_roles(required_actions=["reject_travel_request"])
def reject_travel_request(admin_id, role,role_id, request_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        data = request.get_json(silent=True) or {}
        remarks = data.get("remarks", None)

        if remarks is not None:
            query = """
                UPDATE travel_requests
                SET status = 'Rejected',
                    approved_by = %s,
                    remarks = %s
                WHERE request_id = %s
            """
            cur.execute(query, (f"{role} ID:{admin_id}", remarks, request_id))
        else:
            query = """
                UPDATE travel_requests
                SET status = 'Rejected',
                    approved_by = %s
                WHERE request_id = %s
            """
            cur.execute(query, (f"{role} ID:{admin_id}", request_id))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Travel request rejected"})

    except Exception as e:
        print("Error rejecting travel request:", e)
        return jsonify({"error": "Failed to reject travel request"}), 500

#route for fetching details of specific health resource to view
@csrf.exempt
@admin_bp.route('/admin/get_health_resource/<int:resource_id>', methods=['GET'])
@token_required_with_roles(required_actions=["get_health_resource_details"])
def get_health_resource(admin_id,role,role_id,resource_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT title, description, category, url, file_path
        FROM health_wellness_resources
        WHERE resource_id = %s
    """, (resource_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return jsonify({
            'title': row[0],
            'description': row[1],
            'category': row[2],
            'url': row[3],
            'file_path': row[4]
        })
    else:
        return jsonify({'error': 'Resource not found'}), 404

#route for deleting health resources
@csrf.exempt
@admin_bp.route('/admin/delete_health_resource/<int:resource_id>', methods=['DELETE'])
@token_required_with_roles(required_actions=["delete_health_resource"])
def delete_health_resource(admin_id,role,role_id,resource_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch file path to delete file from disk
        cursor.execute(
            "SELECT file_path FROM health_wellness_resources WHERE resource_id = %s",
            (resource_id,)
        )
        fetch = cursor.fetchone()

        if fetch:
            file_path = fetch[0]
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        else:
            return jsonify({'status': 'error', 'message': 'Resource not found'}), 404

        # Delete the resource from the database
        cursor.execute(
            "DELETE FROM health_wellness_resources WHERE resource_id = %s",
            (resource_id,)
        )
        conn.commit()

        return jsonify({'status': 'deleted'})

    except Exception as e:
        conn.rollback()  # Rollback in case of an error
        return jsonify({'status': 'error', 'message': str(e)}), 500

    finally:
        cursor.close()
        conn.close()

#route for editing health resources
@csrf.exempt
@admin_bp.route('/admin/edit_health_resource/<int:resource_id>', methods=['POST'])
@token_required_with_roles(required_actions=["edit_health_resource"])
def edit_health_resource(admin_id,role,role_id,resource_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    title = request.form['title']
    description = request.form.get('description')
    category = request.form['category']
    url = request.form.get('url')
    file = request.files.get('file')

    print("\n[DEBUG] Edit Health Resource:")
    print("Resource ID:", resource_id)
    print("Title:", title)
    print("Description:", description)
    print("Category:", category)
    print("URL:", url)

    file_path = None
    if file:
        print("File received:", file.filename)
        if allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = filename
            save_path = os.path.join(HEALTH_RESOURCES, filename)
            print("Saving file to:", save_path)
            file.save(save_path)
        else:
            print("File type not allowed.")
    else:
        print("No new file uploaded.")

    if file_path:
        update_query = """
            UPDATE health_wellness_resources
            SET title = %s, description = %s, category = %s,
                url = %s, file_path = %s
            WHERE resource_id = %s
        """
        params = (title, description, category, url, file_path, resource_id)
    else:
        update_query = """
            UPDATE health_wellness_resources
            SET title = %s, description = %s, category = %s,
                url = %s
            WHERE resource_id = %s
        """
        params = (title, description, category, url, resource_id)

    print("Executing query with params:", params)

    cursor.execute(update_query, params)
    conn.commit()
    return jsonify({'status': 'updated'})

#route for adding health resources
@csrf.exempt
@admin_bp.route('/admin/add_health_resource', methods=['POST'])
@token_required_with_roles(required_actions=["add_health_resource"])
def add_health_resource(admin_id, role,role_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    title = request.form.get('title')
    description = request.form.get('description')
    category = request.form.get('category')
    url = request.form.get('url')
    file = request.files.get('file')

    print("\n[DEBUG] Add Health Resource:")
    print("Title:", title)
    print("Description:", description)
    print("Category:", category)
    print("URL:", url)

    file_path = None
    if file:
        print("File received:", file.filename)
        if allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = filename
            save_path = os.path.join(HEALTH_RESOURCES, filename)
            print("Saving file to:", save_path)
            file.save(save_path)
        else:
            print("File type not allowed.")
    else:
        print("No file uploaded.")

    print("File path stored in DB:", file_path)

    cursor.execute('''
        INSERT INTO health_wellness_resources (title, description, category, url, file_path)
        VALUES (%s, %s, %s, %s, %s)
    ''', (title, description, category, url, file_path))

    conn.commit()
    return "Resource added successfully", 200

#route for fetching health resources details
@csrf.exempt
@admin_bp.route('/admin/health_resources')
@token_required_with_roles(required_actions=["get_health_resources"])
def get_health_resources(admin_id, role,role_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM health_wellness_resources"
    cursor.execute(query)
    result = cursor.fetchall()

    data = []
    for row in result:
        data.append({
            'resource_id': row[0],
            'title': row[1],
            'description': row[2],
            'category': row[3],
            'url': row[4],
            'file_path': row[5]
        })

    conn.close()
    return jsonify(data)

#route for retrieving events to edit 
@admin_bp.route('/get_event/<int:event_id>', methods=['GET'])
@token_required_with_roles(required_actions=["get_event_details"])
def get_event(admin_id,role,role_id,event_id):
    logging.debug(f"Fetching event with event_id: {event_id}")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch the event details from the database
        query = "SELECT * FROM events WHERE event_id = %s"
        cursor.execute(query, (event_id,))
        event = cursor.fetchone()

        if not event:
            logging.warning(f"Event with event_id {event_id} not found.")
            return jsonify({"error": "Event not found"}), 404

        cursor.close()
        conn.close()

        logging.debug(f"Event with event_id {event_id} fetched successfully.")
        return jsonify({
            "event_id": event[0],
            "title": event[1],
            "description": event[2],
            "event_date": event[3],
            "location": event[4],
            "budget": event[5],
            "status": event[7],
            "organizer_id": event[5],
            "recurrence": event[6]
        }), 200

    except Exception as e:
        logging.exception(f"Error fetching event with event_id {event_id}: {str(e)}")
        return jsonify({"error": "An error occurred while fetching the event.", "details": str(e)}), 500

    finally:
        if 'conn' in locals():
            conn.close()
            logging.debug("Database connection closed")


#route for updating the events after editing
@csrf.exempt
@admin_bp.route('/update_event/<int:event_id>', methods=['PUT'])
@token_required_with_roles(required_actions=["update_event"])
def update_event(admin_id,role,role_id,event_id):
    logging.debug(f"Starting update_event route for event_id: {event_id}")

    try:
        data = request.get_json()

        # Extract event data from request
        title = data.get('title')
        description = data.get('description')
        event_date = data.get('event_date')
        location = data.get('location')
        budget = data.get('budget')
        recurrence = data.get('recurrence')
        status = data.get('status')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Update the event with the new data
        query = """
            UPDATE events
            SET title = %s, description = %s, event_date = %s, location = %s,
                budget = %s, recurrence = %s, status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE event_id = %s
        """
        cursor.execute(query, (title, description, event_date, location, budget, recurrence, status, event_id))

        conn.commit()

        cursor.close()
        conn.close()

        logging.info(f"Event with event_id {event_id} updated successfully.")
        return jsonify({"message": "Event updated successfully"}), 200

    except Exception as e:
        logging.exception(f"Error updating event with event_id {event_id}")
        return jsonify({"error": "An error occurred while updating the event.", "details": str(e)}), 500

#route for deleting event
@csrf.exempt
@admin_bp.route('/delete_event/<int:event_id>', methods=['DELETE'])
@token_required_with_roles(required_actions=["delete_event"])
def delete_event(admin_id,role,role_id,event_id):
    logging.debug(f"Starting delete_event route for event_id: {event_id}")

    try:
        logging.debug("Establishing database connection.")
        conn = get_db_connection()
        cursor = conn.cursor()

        # Log the query being executed
        query = "DELETE FROM events WHERE event_id = %s"
        logging.debug(f"Executing query: {query} with event_id: {event_id}")

        cursor.execute(query, (event_id,))

        # Log the commit action
        logging.debug(f"Committing the deletion of event_id: {event_id}")
        conn.commit()

        cursor.close()
        conn.close()

        logging.info(f"Event with event_id {event_id} deleted successfully.")
        return jsonify({"message": "Event deleted successfully"}), 200

    except Exception as e:
        logging.exception(f"Error deleting event with event_id {event_id}: {str(e)}")
        return jsonify({"error": "An error occurred while deleting the event.", "details": str(e)}), 500

    finally:
        if 'conn' in locals():
            conn.close()
            logging.debug("Database connection closed")

# Route: Create Event
@csrf.exempt
@admin_bp.route('/create_event', methods=['POST'])
@token_required_with_roles(required_actions=["create_event"])
def create_event(admin_id, role,role_id):
    conn = None
    cursor = None
    
    try:
        # Get database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        logging.info("Database connection established for event creation")

        # Extract and validate basic event data
        event_data = extract_event_data(request.form)
        validate_event_data(event_data)
        
        # Create the event record
        event_id = create_event_record(cursor, event_data, admin_id, role)
        
        # Add participants (employees and teams)
        participant_data = extract_participant_data(request.form)
        add_event_participants(cursor, event_id, participant_data)
        
        # Commit all changes
        conn.commit()
        
        logging.info(f"Event {event_id} created successfully with participants")
        return jsonify({
            "message": "Event created successfully!",
            "event_id": event_id
        }), 200

    except ValueError as e:
        logging.warning(f"Validation error creating event: {str(e)}")
        return jsonify({"error": str(e)}), 400
        
    except Exception as e:
        logging.exception("Unexpected error creating event")
        if conn:
            conn.rollback()
        return jsonify({"error": "Failed to create event. Please try again."}), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def extract_event_data(form_data):
    """Extract and clean event data from form"""
    return {
        'title': form_data.get('title', '').strip(),
        'description': form_data.get('description', '').strip(),
        'location': form_data.get('location', '').strip(),
        'date': form_data.get('date'),
        'budget': form_data.get('budget'),
        'recurrence': form_data.get('recurrence', 'none'),
        'status': form_data.get('status', 'upcoming')
    }


def validate_event_data(event_data):
    """Validate required event fields"""
    required_fields = ['title', 'description', 'location']
    
    for field in required_fields:
        if not event_data[field]:
            raise ValueError(f"{field.replace('_', ' ').title()} is required")
    
    # Validate date format if provided
    if event_data['date']:
        try:
            event_data['date'] = datetime.strptime(event_data['date'], "%Y-%m-%dT%H:%M")
        except ValueError:
            raise ValueError("Invalid date format")
    else:
        event_data['date'] = None
    
    # Validate budget
    if event_data['budget']:
        try:
            event_data['budget'] = float(event_data['budget'])
            if event_data['budget'] < 0:
                raise ValueError("Budget cannot be negative")
        except (ValueError, TypeError):
            raise ValueError("Invalid budget amount")
    else:
        event_data['budget'] = 0.0


def create_event_record(cursor, event_data, admin_id, role):
    """Create the main event record and return event_id"""
    # Determine admin assignment based on role
    assigned_by_admins = admin_id if role != 'super_admin' else None
    assigned_by_super_admins = admin_id if role == 'super_admin' else None
    
    cursor.execute("""
        INSERT INTO events 
        (title, description, event_date, location, budget, recurrence, status, 
         assigned_by_admins, assigned_by_super_admins)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING event_id
    """, (
        event_data['title'],
        event_data['description'],
        event_data['date'],
        event_data['location'],
        event_data['budget'],
        event_data['recurrence'],
        event_data['status'],
        assigned_by_admins,
        assigned_by_super_admins
    ))
    
    return cursor.fetchone()[0]

def extract_participant_data(form_data):
    """Extract and clean participant data from form"""
    employee_ids = form_data.getlist('employee_ids[]')
    admin_ids = form_data.getlist('admin_ids[]')  # Add this line
    team_ids = form_data.getlist('team_ids[]')
    
    # Clean and validate employee IDs
    valid_employee_ids = []
    for emp_id in employee_ids:
        if emp_id and str(emp_id).strip().isdigit():
            valid_employee_ids.append(int(emp_id))
    
    # Clean and validate admin IDs
    valid_admin_ids = []
    for admin_id in admin_ids:
        if admin_id and str(admin_id).strip().isdigit():
            valid_admin_ids.append(int(admin_id))
    
    # Clean and validate team IDs
    valid_team_ids = []
    for team_id in team_ids:
        if team_id and str(team_id).strip().isdigit():
            valid_team_ids.append(int(team_id))
    
    return {
        'employee_ids': valid_employee_ids,
        'admin_ids': valid_admin_ids,  # Add this line
        'team_ids': valid_team_ids
    }

def add_event_participants(cursor, event_id, participant_data):
    """Add participants (employees, admins, and teams) to the event"""
    participants_added = 0
    
    # Add individual employees
    for emp_id in participant_data['employee_ids']:
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM event_participants 
                WHERE event_id = %s AND employee_id = %s
            """, (event_id, emp_id))
            
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO event_participants (event_id, employee_id) 
                    VALUES (%s, %s)
                """, (event_id, emp_id))
                participants_added += cursor.rowcount
                
        except Exception as e:
            logging.warning(f"Failed to add employee {emp_id} to event {event_id}: {e}")
    
    # Add admins (if they should be stored separately)
    for admin_id in participant_data.get('admin_ids', []):
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM event_participants 
                WHERE event_id = %s AND admin_id = %s
            """, (event_id, admin_id))
            
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO event_participants (event_id, admin_id) 
                    VALUES (%s, %s)
                """, (event_id, admin_id))
                participants_added += cursor.rowcount
                
        except Exception as e:
            logging.warning(f"Failed to add admin {admin_id} to event {event_id}: {e}")
    
    # Add teams
    for team_id in participant_data['team_ids']:
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM event_participants 
                WHERE event_id = %s AND team_id = %s
            """, (event_id, team_id))
            
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO event_participants (event_id, team_id) 
                    VALUES (%s, %s)
                """, (event_id, team_id))
                participants_added += cursor.rowcount
                
        except Exception as e:
            logging.warning(f"Failed to add team {team_id} to event {event_id}: {e}")
    
    logging.info(f"Added {participants_added} participants to event {event_id}")

# Route: Get Events
@admin_bp.route('/get_events', methods=['GET'])
@token_required_with_roles(required_actions=["get_events"])
def get_events(admin_id, role,role_id):
    logging.debug("Starting /get_events route")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
SELECT 
    e.event_id, 
    e.title, 
    e.description,
    e.event_date, 
    e.location, 
    e.budget, 
    e.status,
    a.email AS admin_email,
    sa.email AS super_admin_email,
    e.recurrence,
    COALESCE(json_agg(
        CASE
            WHEN emp.employee_id IS NOT NULL THEN
                json_build_object(
                    'employee_id', emp.employee_id,
                    'first_name', emp.first_name,
                    'last_name', emp.last_name,
                    'email', emp.email,
                    'type', 'employee'
                )
            WHEN admin_part.admin_id IS NOT NULL THEN
                json_build_object(
                    'employee_id', admin_part.admin_id,
                    'first_name', admin_part.first_name,
                    'last_name', admin_part.last_name,
                    'email', admin_part.email,
                    'type', 'admin'
                )
        END
    ) FILTER (WHERE emp.employee_id IS NOT NULL OR admin_part.admin_id IS NOT NULL), '[]') AS participants,
    COALESCE(json_agg(
        CASE
            WHEN t.team_id IS NOT NULL THEN
                json_build_object(
                    'team_id', t.team_id,
                    'team_name', t.team_name
                )
        END
    ) FILTER (WHERE t.team_id IS NOT NULL), '[]') AS teams
FROM events e
LEFT JOIN admins a ON a.admin_id = e.assigned_by_admins 
LEFT JOIN super_admins sa ON sa.super_admin_id = e.assigned_by_super_admins
LEFT JOIN event_participants ep ON e.event_id = ep.event_id
LEFT JOIN employees emp ON ep.employee_id = emp.employee_id
LEFT JOIN admins admin_part ON ep.admin_id = admin_part.admin_id
LEFT JOIN teams t ON ep.team_id = t.team_id
GROUP BY e.event_id, a.email, sa.email
ORDER BY e.event_date DESC;
"""

        logging.debug("Executing SQL query: %s", query)

        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        events = [dict(zip(columns, row)) for row in cursor.fetchall()]

        logging.debug("Fetched events: %s", events[:5] if len(events) > 5 else events)

        cursor.close()
        conn.close()
        return jsonify(events)

    except Exception as e:
        logging.exception("Error fetching events")
        return jsonify({"error": "An error occurred while fetching events.", "details": str(e)}), 500

    finally:
        if 'conn' in locals():
            conn.close()
            logging.debug("Database connection closed")

#route for fetching the status of survey for resubmission
@admin_bp.route('/survey/<int:survey_id>/assignments', methods=['GET'])
@token_required_with_roles(required_actions=["get_survey_assignments"])
def get_survey_assignments(admin_id, role, role_id, survey_id):
    """
    Returns all assignments for a survey, with employee_id, email, and has_submitted.
    """
    print(f"[DEBUG] Route called: /survey/{survey_id}/assignments by admin_id={admin_id} role={role} role_id={role_id}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        print(f"[DEBUG] Database connection established.")

        # Get all assignments for this survey (for employees)
        query = """
            SELECT
                sa.employee_id,
                e.email,
                sa.has_submitted
            FROM survey_assignments sa
            JOIN employees e ON sa.employee_id = e.employee_id
            WHERE sa.survey_id = %s
        """
        print(f"[DEBUG] Executing SQL: {query.strip()} with survey_id={survey_id}")
        cursor.execute(query, (survey_id,))
        rows = cursor.fetchall()
        print(f"[DEBUG] Query executed. Number of rows fetched: {len(rows)}")

        # Format as list of dicts
        assignments = []
        for row in rows:
            assignments.append({
                "employee_id": row[0],
                "email": row[1],
                "has_submitted": bool(row[2])
            })
        print(f"[DEBUG] Assignments to return: {assignments}")

        return jsonify(assignments)
    except Exception as e:
        print(f"[ERROR] Exception in get_survey_assignments: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            print("[DEBUG] Closing database connection.")
            conn.close()
            
# Updated get_survey_details route
@admin_bp.route("/get_survey_details/<int:survey_id>", methods=["GET"])
@token_required_with_roles(required_actions=["get_survey_details"])
def get_survey_details(admin_id, role, role_id, survey_id):
    import logging
    conn = None
    cursor = None
    try:
        print(f"Fetching details for survey_id: {survey_id}")
        logging.debug(f"[DEBUG] Fetching details for survey_id: {survey_id}")
        conn = get_db_connection()
        cursor = conn.cursor()

        # --- 1. Fetch survey metadata ---
        cursor.execute("""
            SELECT survey_id, title, description, created_at, is_active 
            FROM surveys WHERE survey_id = %s
        """, (survey_id,))
        survey_row = cursor.fetchone()
        logging.debug(f"[DEBUG] Survey metadata fetched: {survey_row}")
        if not survey_row:
            logging.warning(f"[DEBUG] Survey ID {survey_id} not found.")
            return jsonify({"error": "Survey not found"}), 404

        survey = {
            "survey_id": survey_row[0],
            "title": survey_row[1],
            "description": survey_row[2],
            "created_at": survey_row[3],
            "is_active": survey_row[4]
        }
        logging.debug(f"[DEBUG] Survey dict: {survey}")

        # --- 2. Fetch ALL assignments ---
        cursor.execute("""
            SELECT employee_id, team_id FROM survey_assignments WHERE survey_id = %s
        """, (survey_id,))
        assignments = cursor.fetchall()
        logging.debug(f"[DEBUG] Assignments fetched: {assignments}")

        assigned_employees = []
        assigned_team = None
        team_members = []
        assignment_type = None

        employee_ids = [row[0] for row in assignments if row[0] is not None]
        team_ids = [row[1] for row in assignments if row[1] is not None]

        # --- Improved assignment detection logic ---
        # If all assignments have non-null team_id and employee_id, it's a "team" assignment.
        # If all assignments have only employee_id, it's an "employee" assignment.
        # If both are present (mixed), prefer "team" if team_ids exist.

        assigned_id = ""
        assigned_display_name = ""

        if team_ids:
            assignment_type = "team"
            # Only consider the first team_id (should only be one per survey usually)
            team_id = team_ids[0]
            cursor.execute("SELECT team_id, team_name FROM teams WHERE team_id = %s", (team_id,))
            team_row = cursor.fetchone()
            if team_row:
                assigned_team = {"team_id": team_row[0], "team_name": team_row[1]}
                survey["assigned_team"] = assigned_team
                assigned_id = assigned_team["team_id"]
                assigned_display_name = assigned_team["team_name"]
                # Get all employees in this team (even if not in survey_assignments)
                cursor.execute("SELECT employee_id, email FROM employees WHERE team_id = %s", (team_id,))
                team_members = [
                    {"employee_id": emp_id, "email": email}
                    for emp_id, email in cursor.fetchall()
                ]
                survey["team_members"] = team_members
                logging.debug(f"[DEBUG] assigned_team: {assigned_team}")
                logging.debug(f"[DEBUG] team_members: {team_members}")
            else:
                survey["assigned_team"] = None
                survey["team_members"] = []
            survey["assigned_employees"] = []  # Keep for frontend compatibility
        elif employee_ids:
            assignment_type = "employee"
            format_strings = ','.join(['%s'] * len(employee_ids))
            cursor.execute(f"""
                SELECT employee_id, email FROM employees WHERE employee_id IN ({format_strings})
            """, tuple(employee_ids))
            assigned_employees = [
                {"employee_id": emp_id, "email": email}
                for emp_id, email in cursor.fetchall()
            ]
            survey["assigned_employees"] = assigned_employees
            logging.debug(f"[DEBUG] assigned_employees: {assigned_employees}")
            survey["assigned_team"] = None
            survey["team_members"] = []

            if len(assigned_employees) == 1:
                assigned_id = assigned_employees[0]["employee_id"]
                assigned_display_name = assigned_employees[0]["email"]
            elif len(assigned_employees) > 1:
                # If multiple employees assigned, join emails for display
                assigned_id = ""
                assigned_display_name = ", ".join(emp["email"] for emp in assigned_employees)
            else:
                assigned_id = ""
                assigned_display_name = ""
        else:
            assignment_type = None
            survey["assigned_employees"] = []
            survey["assigned_team"] = None
            survey["team_members"] = []
            assigned_id = ""
            assigned_display_name = ""

        survey["assignment_type"] = assignment_type
        survey["assigned_id"] = assigned_id
        survey["assigned_display_name"] = assigned_display_name

        # --- 3. Fetch questions ---
        cursor.execute("""
            SELECT question_id, question_text, question_type 
            FROM survey_questions WHERE survey_id = %s
        """, (survey_id,))
        questions = []
        question_rows = cursor.fetchall()
        logging.debug(f"[DEBUG] Questions fetched: {question_rows}")
        for (question_id, question_text, question_type) in question_rows:
            questions.append({
                "question_id": question_id,
                "question_text": question_text,
                "question_type": question_type,
                "options": []
            })
        logging.debug(f"[DEBUG] Questions list: {questions}")

        # --- 4. Fetch options ---
        for idx, question in enumerate(questions):
            cursor.execute("""
                SELECT option_id, option_text, is_correct 
                FROM survey_question_options 
                WHERE question_id = %s
            """, (question["question_id"],))
            option_rows = cursor.fetchall()
            logging.debug(f"[DEBUG] Options for question {question['question_id']} fetched: {option_rows}")
            for (option_id, option_text, is_correct) in option_rows:
                question["options"].append({
                    "option_id": option_id,
                    "option_text": option_text,
                    "is_correct": is_correct
                })
            logging.debug(f"[DEBUG] Question after adding options: {question}")

        survey["questions"] = questions
        logging.debug(f"[DEBUG] Final survey dict to return: {survey}")
        return jsonify(survey)

    except Exception as e:
        print(f"Error in get_survey_details: {str(e)}")
        logging.error(f"[DEBUG] Error in get_survey_details: {str(e)}")
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
#route for fetching survey responses
@admin_bp.route('/admin/survey/<int:survey_id>/responses')
@token_required_with_roles(required_actions=["survey_responses"])
def survey_responses(admin_id, role, role_id, survey_id):
    import logging
    import traceback

    conn = None
    try:
        logging.debug(f"[SURVEY_RESPONSES] admin_id={admin_id}, role={role}, role_id={role_id}, survey_id={survey_id}")

        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Get survey title
        logging.debug(f"[SURVEY_RESPONSES] Fetching survey title for survey_id={survey_id}")
        cursor.execute("""
            SELECT title FROM surveys WHERE survey_id = %s
        """, (survey_id,))
        survey = cursor.fetchone()
        
        if not survey:
            logging.warning(f"[SURVEY_RESPONSES] No survey found with survey_id={survey_id}")
            return jsonify({'error': 'Survey not found'}), 404

        # 2. Get all responses with employee details and option_text if available
        logging.debug(f"[SURVEY_RESPONSES] Fetching all responses and employee details for survey_id={survey_id}")
        cursor.execute("""
            SELECT 
                sr.response_id,
                sr.response_text,
                sqo.option_text,
                sr.submitted_at,
                e.employee_id,
                e.email,
                q.question_text,
                q.question_id,
                e.first_name,
                e.last_name,
                q.question_type
            FROM 
                survey_responses sr
            JOIN 
                employees e ON sr.employee_id = e.employee_id
            JOIN 
                survey_questions q ON sr.question_id = q.question_id
            LEFT JOIN 
                survey_question_options sqo ON sr.option_id = sqo.option_id
            WHERE 
                sr.survey_id = %s
            ORDER BY 
                sr.submitted_at DESC
        """, (survey_id,))
        
        responses = cursor.fetchall()
        logging.debug(f"[SURVEY_RESPONSES] Number of responses found: {len(responses)}")

        # Format the data
        formatted_responses = []
        for resp in responses:
            formatted_response = {
                'response_id': resp[0],
                'response_text': resp[1] if resp[1] else resp[2],  # show text if present, else option_text
                'option_text': resp[2],
                'submitted_at': resp[3].isoformat() if resp[3] else None,
                'employee_id': resp[4],
                'email': resp[5],
                'question_text': resp[6],
                'question_id': resp[7],
                'first_name': resp[8],
                'last_name': resp[9],
                'question_type': resp[10]
            }
            logging.debug(f"[SURVEY_RESPONSES] Response fetched: {formatted_response}")
            formatted_responses.append(formatted_response)

        result = {
            'survey_title': survey[0],
            'responses': formatted_responses
        }
        logging.debug(f"[SURVEY_RESPONSES] Final response data: {result}")

        return jsonify(result)

    except Exception as e:
        logging.error(f"[SURVEY_RESPONSES] Exception: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# Updated edit_survey route
@admin_bp.route("/edit_survey/<int:survey_id>", methods=["POST"])
@token_required_with_roles(required_actions=["edit_survey"])
def edit_survey(admin_id, role, role_id, survey_id):
    import logging
    from pprint import pformat

    logging.debug(f"\n==== EDIT SURVEY {survey_id} ====")
    try:
        data = request.get_json()
        logging.debug(f"Received data: {pformat(data)}")
        title = data.get("title")
        description = data.get("description")
        questions = data.get("questions", [])
        assignment_type = data.get("assignment_type")
        assigned_id = data.get("assigned_id")

        if not title or not questions:
            logging.warning("Survey title or questions missing.")
            return jsonify({"success": False, "message": "Survey title and questions are required."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        logging.debug("Updating surveys table...")
        cursor.execute("""
            UPDATE surveys SET title=%s, description=%s WHERE survey_id=%s
        """, (title, description, survey_id))

        # --- Get existing questions and options ---
        cursor.execute("SELECT question_id FROM survey_questions WHERE survey_id=%s", (survey_id,))
        db_qids = {row[0] for row in cursor.fetchall()}

        # Map question_id to list of option_ids
        db_options_by_qid = {}
        for qid in db_qids:
            cursor.execute("SELECT option_id FROM survey_question_options WHERE question_id=%s", (qid,))
            db_options_by_qid[qid] = {row[0] for row in cursor.fetchall()}

        # --- Process questions ---
        payload_qids = set()
        for q in questions:
            qid = q.get("question_id")
            q_text = q.get("question_text")
            q_type = q.get("question_type")
            options = q.get("options", [])

            if qid:  # Existing question: update
                payload_qids.add(qid)
                cursor.execute("""
                    UPDATE survey_questions SET question_text=%s, question_type=%s WHERE question_id=%s
                """, (q_text, q_type, qid))

                # Handle options
                db_oids = db_options_by_qid.get(qid, set())
                payload_oids = set()
                for opt in options:
                    oid = opt.get("option_id")
                    opt_text = opt.get("option_text") or opt.get("text")
                    is_correct = opt.get("is_correct", False)
                    if oid:  # Existing option: update
                        payload_oids.add(oid)
                        cursor.execute("""
                            UPDATE survey_question_options SET option_text=%s, is_correct=%s WHERE option_id=%s
                        """, (opt_text, is_correct, oid))
                    else:  # New option: insert
                        cursor.execute("""
                            INSERT INTO survey_question_options (question_id, option_text, is_correct)
                            VALUES (%s, %s, %s)
                        """, (qid, opt_text, is_correct))
                # Delete options not in payload
                for oid in db_oids - payload_oids:
                    cursor.execute("DELETE FROM survey_question_options WHERE option_id=%s", (oid,))

            else:  # New question: insert
                cursor.execute("""
                    INSERT INTO survey_questions (survey_id, question_text, question_type)
                    VALUES (%s, %s, %s)
                    RETURNING question_id
                """, (survey_id, q_text, q_type))
                new_qid = cursor.fetchone()[0]
                for opt in options:
                    opt_text = opt.get("option_text") or opt.get("text")
                    is_correct = opt.get("is_correct", False)
                    cursor.execute("""
                        INSERT INTO survey_question_options (question_id, option_text, is_correct)
                        VALUES (%s, %s, %s)
                    """, (new_qid, opt_text, is_correct))

        # --- Delete questions (and their options) missing from payload ---
        for qid in db_qids - payload_qids:
            cursor.execute("DELETE FROM survey_question_options WHERE question_id=%s", (qid,))
            cursor.execute("DELETE FROM survey_questions WHERE question_id=%s", (qid,))

                # --- Handle assignments (delete old, insert new as before) ---
        cursor.execute("DELETE FROM survey_assignments WHERE survey_id=%s", (survey_id,))
        if assignment_type == "employee":
            # Fix: if assigned_id is '', set to None so it inserts as SQL NULL
            if not assigned_id:  # catches None and ''
                assigned_id_sql = None
            else:
                assigned_id_sql = assigned_id
            cursor.execute("""
                INSERT INTO survey_assignments (survey_id, employee_id, assigned_at)
                VALUES (%s, %s, NOW())
            """, (survey_id, assigned_id_sql))
        elif assignment_type == "team":
            # Assign to all current employees in the team
            cursor.execute("""
                SELECT employee_id FROM employees WHERE team_id = %s
            """, (assigned_id,))
            team_member_ids = cursor.fetchall()
            logging.debug(f"[EDIT_SURVEY] Found team members for team_id {assigned_id}: {team_member_ids}")
            if not team_member_ids:
                logging.warning(f"[EDIT_SURVEY] No employees found in team_id {assigned_id}. No assignments will be created.")
            for (employee_id,) in team_member_ids:
                logging.debug(f"[EDIT_SURVEY] Assigning to team member employee_id: {employee_id}")
                cursor.execute("""
                    INSERT INTO survey_assignments (survey_id, employee_id, team_id, assigned_at)
                    VALUES (%s, %s, %s, NOW())
                """, (survey_id, employee_id, assigned_id))
        else:
            logging.warning("[EDIT_SURVEY] No valid assignment_type provided.")

        conn.commit()
        logging.info(f"Survey {survey_id} updated successfully.")
        return jsonify({"success": True, "message": "Survey updated"})
    except Exception as e:
        logging.exception(f"Exception occurred while editing survey {survey_id}: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            
#route for allowing employee to submit the survey again
@csrf.exempt
@admin_bp.route('/allow_resubmission', methods=['POST'])
@token_required_with_roles(required_actions=["allow_resubmission"])
def allow_resubmission(admin_id, role, role_id):
    logging.debug(f"[ALLOW_RESUBMISSION] Admin {admin_id} ({role}) requested resubmission for role_id={role_id}")

    data = request.get_json()
    survey_id = data.get('survey_id')
    employee_id = data.get('employee_id')
    logging.debug(f"[ALLOW_RESUBMISSION] Received data: survey_id={survey_id}, employee_id={employee_id}")

    if not survey_id or not employee_id:
        logging.warning(f"[ALLOW_RESUBMISSION] Missing survey_id or employee_id in request")
        return jsonify({'error': 'survey_id and employee_id are required'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        logging.debug(f"[ALLOW_RESUBMISSION] Connected to DB, checking max attempt for survey_id={survey_id}, employee_id={employee_id}")

        # Find the next attempt number for this employee/survey
        cursor.execute("""
            SELECT COALESCE(MAX(attempt_number), 0) + 1
            FROM survey_assignments
            WHERE survey_id = %s AND employee_id = %s
        """, (survey_id, employee_id))
        next_attempt = cursor.fetchone()[0]
        logging.debug(f"[ALLOW_RESUBMISSION] Next attempt number for employee {employee_id} on survey {survey_id} is {next_attempt}")

        # Insert a new assignment row
        cursor.execute("""
    INSERT INTO survey_assignments (survey_id, employee_id, attempt_number, assigned_at, has_submitted)
    VALUES (%s, %s, %s, NOW(), FALSE)
""", (survey_id, employee_id, next_attempt))
        logging.info(f"[ALLOW_RESUBMISSION] Inserted new assignment row: survey_id={survey_id}, employee_id={employee_id}, attempt_number={next_attempt}")

        conn.commit()
        logging.info(f"[ALLOW_RESUBMISSION] Commit successful for resubmission.")

        return jsonify({'success': True, 'message': 'Resubmission allowed.', 'attempt_number': next_attempt}), 200
    except Exception as e:
        logging.error(f"[ALLOW_RESUBMISSION] Exception: {str(e)}", exc_info=True)
        if 'conn' in locals() and conn:
            conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            logging.debug(f"[ALLOW_RESUBMISSION] DB connection closed.")

# Updated delete_survey route
@csrf.exempt
@admin_bp.route("/delete_survey/<int:survey_id>", methods=["DELETE"])
@token_required_with_roles(required_actions=["delete_survey"])
def delete_survey(admin_id,role,role_id,survey_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete in proper order to maintain referential integrity
        cursor.execute("""
            DELETE FROM survey_responses 
            WHERE question_id IN (
                SELECT question_id FROM survey_questions WHERE survey_id = %s
            )
        """, (survey_id,))
        
        cursor.execute("""
            DELETE FROM survey_question_options 
            WHERE question_id IN (
                SELECT question_id FROM survey_questions WHERE survey_id = %s
            )
        """, (survey_id,))
        
        cursor.execute("""
            DELETE FROM survey_questions WHERE survey_id = %s
        """, (survey_id,))
        
        cursor.execute("""
            DELETE FROM survey_assignments WHERE survey_id = %s
        """, (survey_id,))
        
        cursor.execute("""
            DELETE FROM surveys WHERE survey_id = %s
        """, (survey_id,))

        conn.commit()
        return jsonify({"success": True, "message": "Survey deleted successfully"})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            cursor.close()
            conn.close()

# Route to create a new survey
@admin_bp.route("/create_survey", methods=["POST"])
@token_required_with_roles(required_actions=["create_survey"])
def create_survey(admin_id, role, role_id):
    import traceback
    import logging
    from pprint import pformat

    logging.debug("======== [CREATE_SURVEY] ========")
    data = request.get_json()
    logging.debug(f"[CREATE_SURVEY] Raw data received: {pformat(data)}")

    title = data.get("title")
    description = data.get("description")
    questions = data.get("questions", [])
    assignment_type = data.get("assignment_type")
    assigned_id = data.get("assigned_id")

    logging.debug(f"[CREATE_SURVEY] title: {title}")
    logging.debug(f"[CREATE_SURVEY] description: {description}")
    logging.debug(f"[CREATE_SURVEY] assignment_type: {assignment_type}, assigned_id: {assigned_id}")
    logging.debug(f"[CREATE_SURVEY] questions: {pformat(questions)}")
    logging.debug(f"[CREATE_SURVEY] admin_id: {admin_id}, role: {role}, role_id: {role_id}")

    if not title or not questions:
        logging.warning("[CREATE_SURVEY] Missing title or questions.")
        return jsonify({"success": False, "message": "Survey title and questions are required."}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Choose column for admin or super_admin
        if role == "super_admin":
            logging.info("[CREATE_SURVEY] Role is super_admin, inserting ID into super_admin_id column.")
            cursor.execute("""
                INSERT INTO surveys (title, description, created_at, is_active, super_admin_id, admin_id, created_by)
                VALUES (%s, %s, NOW(), TRUE, %s, NULL, %s) RETURNING survey_id
            """, (title, description, admin_id, role))
        else:
            logging.info(f"[CREATE_SURVEY] Role is {role}, inserting ID into admin_id column.")
            cursor.execute("""
                INSERT INTO surveys (title, description, created_at, is_active, super_admin_id, admin_id, created_by)
                VALUES (%s, %s, NOW(), TRUE, NULL, %s, %s) RETURNING survey_id
            """, (title, description, admin_id, role))
        survey_id = cursor.fetchone()[0]
        logging.info(f"[CREATE_SURVEY] Survey inserted with ID: {survey_id}")

        for q_index, q in enumerate(questions):
            q_text = q.get("question_text")
            q_type = q.get("question_type")
            logging.debug(f"[CREATE_SURVEY] Inserting question {q_index+1}: '{q_text}' (type: {q_type}) [{pformat(q)}]")

            cursor.execute("""
                INSERT INTO survey_questions (survey_id, question_text, question_type)
                VALUES (%s, %s, %s) RETURNING question_id
            """, (
                survey_id, q_text, q_type
            ))
            question_id = cursor.fetchone()[0]
            logging.info(f"[CREATE_SURVEY] Question inserted with ID: {question_id}")

            if q_type == "multiple_choice":
                for opt_index, opt in enumerate(q.get("options", [])):
                    opt_text = opt.get("option_text") or opt.get("text")
                    is_correct = opt.get("is_correct", False)
                    logging.debug(f"[CREATE_SURVEY]    Inserting option {opt_index+1}: '{opt_text}' (is_correct={is_correct}) [{pformat(opt)}]")
                    cursor.execute("""
                        INSERT INTO survey_question_options (question_id, option_text, is_correct)
                        VALUES (%s, %s, %s)
                    """, (question_id, opt_text, is_correct))
        
        # Debug: Print all questions inserted for survey
        cursor.execute("SELECT question_id, question_text, question_type FROM survey_questions WHERE survey_id = %s", (survey_id,))
        inserted_questions = cursor.fetchall()
        logging.debug(f"[CREATE_SURVEY] All questions inserted: {pformat(inserted_questions)}")

        # Assign the survey
        logging.info("[CREATE_SURVEY] Creating assignment...")
        if assignment_type == "employee":
            logging.info(f"[CREATE_SURVEY] Assigning to employee_id: {assigned_id}")
            cursor.execute("""
                INSERT INTO survey_assignments (survey_id, employee_id, assigned_at)
                VALUES (%s, %s, NOW())
            """, (survey_id, assigned_id))
        
        elif assignment_type == "team":
            logging.info(f"[CREATE_SURVEY] Assigning to all employees in team_id: {assigned_id}")
            # Get all current employees in the team
            cursor.execute("""
                SELECT employee_id FROM employees WHERE team_id = %s
            """, (assigned_id,))
            team_member_ids = cursor.fetchall()
            logging.debug(f"[CREATE_SURVEY] Found team members for team_id {assigned_id}: {team_member_ids}")
            # Insert assignment for each employee (team_id must be NULL)
            for (employee_id,) in team_member_ids:
                logging.debug(f"[CREATE_SURVEY] Assigning to team member employee_id: {employee_id}")
                cursor.execute("""
                    INSERT INTO survey_assignments (survey_id, employee_id, assigned_at)
                    VALUES (%s, %s, NOW())
                """, (survey_id, employee_id))
        else:
            logging.warning("[CREATE_SURVEY] No valid assignment_type provided.")

        # Debug: Print all assignments for this survey
        cursor.execute("SELECT * FROM survey_assignments WHERE survey_id = %s", (survey_id,))
        all_assignments = cursor.fetchall()
        logging.debug(f"[CREATE_SURVEY] All assignments after insert: {pformat(all_assignments)}")

        conn.commit()
        logging.info("[CREATE_SURVEY] Survey creation committed successfully.")
        return jsonify({"success": True, "survey_id": survey_id}), 200
    except Exception as e:
        logging.error(f"[CREATE_SURVEY] Exception occurred: {e}")
        logging.error(traceback.format_exc())
        if 'conn' in locals() and conn:
            conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            
# Route to fetch all surveys
@admin_bp.route("/get_surveys", methods=["GET"])
@token_required_with_roles(required_actions=["get_surveys"])
def get_surveys(admin_id, role,role_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                s.survey_id, s.title, s.description, s.created_at, s.is_active,
                COUNT(DISTINCT q.question_id) AS question_count,
                COUNT(DISTINCT r.response_id) AS response_count
            FROM surveys s
            LEFT JOIN survey_questions q ON s.survey_id = q.survey_id
            LEFT JOIN survey_responses r ON q.question_id = r.question_id
            GROUP BY s.survey_id
            ORDER BY s.created_at DESC
        """)

        surveys = []
        survey_rows = cursor.fetchall()

        for row in survey_rows:
            survey_id, title, description, created_at, is_active, question_count, response_count = row

            # Fetch related questions
            cursor.execute("""
                SELECT question_id, question_text, question_type 
                FROM survey_questions 
                WHERE survey_id = %s
            """, (survey_id,))
            question_rows = cursor.fetchall()
            questions = []
            for q in question_rows:
                question_id, question_text, question_type = q

                # Fetch options for multiple choice/rating
                cursor.execute("""
                    SELECT option_id, option_text 
                    FROM survey_question_options 
                    WHERE question_id = %s
                """, (question_id,))
                option_rows = cursor.fetchall()
                options = [{"option_id": opt[0], "option_text": opt[1]} for opt in option_rows]

                questions.append({
                    "question_id": question_id,
                    "question_text": question_text,
                    "question_type": question_type,
                    "options": options
                })

            surveys.append({
                "survey_id": survey_id,
                "title": title,
                "description": description,
                "created_at": created_at,
                "is_active": is_active,
                "question_count": question_count,
                "response_count": response_count,
                "questions": questions
            })

        return jsonify(surveys)

    except Exception as e:
        print("Error in /get_surveys:", str(e))
        traceback.print_exc()  # 🛠️ Print full error
        return jsonify({"error": str(e)}), 500

    finally:
        if conn:
            cursor.close()
            conn.close()

#Route for deleting the recognition
@admin_bp.route('/delete_recognition/<int:recognition_id>', methods=['DELETE'])
@token_required_with_roles(required_actions=["delete_recognition"])
def delete_recognition(admin_id,role,role_id,recognition_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM employee_recognition WHERE recognition_id = %s", (recognition_id,))
    conn.commit()

    cur.close()
    conn.close()

    return jsonify({"message": "Recognition deleted successfully"}), 200


#Route for editing the recognition
@admin_bp.route('/edit_recognition/<int:recognition_id>', methods=['PUT'])
@token_required_with_roles(required_actions=["edit_recognition"])
def edit_recognition(admin_id,role,role_id,recognition_id):
    data = request.json
    print(f"Received data for updating: {data}")  # Debugging line
    employee_id = data.get('employee_id')
    recognition_type = data.get('recognition_type')
    reason = data.get('reason')
    date_awarded = data.get('date_awarded')

    # Assign appropriate awarded_by_admin or awarded_by_super_admin
    awarded_by_admin = admin_id if role == "admin" else None
    awarded_by_super_admin = admin_id if role == "super_admin" else None

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE employee_recognition
        SET employee_id = %s, recognition_type = %s, reason = %s, date_awarded = %s,
            awarded_by_admin = %s, awarded_by_super_admin = %s
        WHERE recognition_id = %s
    """, (employee_id, recognition_type, reason, date_awarded, awarded_by_admin, awarded_by_super_admin, recognition_id))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"message": "Recognition updated successfully"}), 200


# Route to insert recognition data
@csrf.exempt
@admin_bp.route('/add_recognition', methods=['POST'])
@token_required_with_roles(required_actions=["add_recognition"])
def add_recognition(admin_id, role,role_id):
    data = request.json
    employee_id = data.get('employee_id')
    recognition_type = data.get('recognition_type')
    reason = data.get('reason')
    date_awarded = data.get('date_awarded')

    awarded_by_admin = None
    awarded_by_super_admin = None

    # Assign the appropriate column based on role
    if role == "admin":
        awarded_by_admin = admin_id
    elif role == "super_admin":
        awarded_by_super_admin = admin_id
    else:
        return jsonify({"error": "Unauthorized role"}), 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO employee_recognition 
            (employee_id, recognition_type, reason, date_awarded, awarded_by_admin, awarded_by_super_admin)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (employee_id, recognition_type, reason, date_awarded, awarded_by_admin, awarded_by_super_admin)
        )
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500
    finally:
        cur.close()
        conn.close()

    return jsonify({"message": "Recognition added successfully"}), 201

# Route to fetch recognition data
@admin_bp.route('/get_recognitions', methods=['GET'])
@token_required_with_roles(required_actions=["get_recognitions"])
def get_recognitions(admin_id, role,role_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
                select e.email,er.employee_id,er.recognition_type,er.reason,er.date_awarded,er.awarded_by_admin,er.awarded_by_super_admin,a.email,sa.email,er.recognition_id
                from employee_recognition er
                left join admins a ON a.admin_id = er.awarded_by_admin
                left join super_admins sa ON sa.super_admin_id = er.awarded_by_super_admin 
                left join employees e ON e.employee_id = er.employee_id
        """)
    recognitions = cur.fetchall()
    cur.close()
    conn.close()
    
    recognition_list = []
    for rec in recognitions:
        recognition_list.append({
            "email": rec[0],
            "employee_id": rec[1],
            "recognition_type": rec[2],
            "reason": rec[3],
            "date_awarded": rec[4],
            "awarded_by_admin": rec[5],
            "awarded_by_super_admin": rec[6],
            "admin": rec[7],
            "super_admin": rec[8],
            "recognition_id": rec[9]
        })
    
    return jsonify(recognition_list)
    
