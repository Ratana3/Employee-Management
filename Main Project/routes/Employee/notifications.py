from datetime import datetime
import logging
from flask import g, jsonify, redirect, render_template, request, url_for

from routes.Auth.token import verify_employee_token
from . import employee_bp
from routes.Auth.token import employee_jwt_required
from routes.Auth.utils import get_db_connection
from extensions import csrf
from routes.Auth.audit import log_employee_incident,log_employee_audit

#route to fetch meeting details to display
@employee_bp.route('/api/employees/meetings', methods=['GET'])
@employee_jwt_required()
def get_employee_meetings():
    # Get the employee ID from JWT decorator
    employee_id = g.employee_id
    
    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized employee meetings access attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get meetings that are either global or specific to the employee's department or role
        cursor.execute("""
            SELECT * FROM meetings
            WHERE participants LIKE %s
            ORDER BY scheduled_for DESC;
        """, (f'%{employee_id}%',))  # Assuming `participants` is a list of employee IDs
        meetings = cursor.fetchall()
        
        meeting_list = []
        upcoming_meetings = 0
        past_meetings = 0
        meeting_locations = {}
        
        current_time = datetime.now()
        
        for meet in meetings:
            meeting_datetime = meet[4]  # scheduled_for
            is_upcoming = meeting_datetime > current_time if meeting_datetime else False
            
            if is_upcoming:
                upcoming_meetings += 1
            else:
                past_meetings += 1
            
            location = meet[5] or 'Not specified'
            meeting_locations[location] = meeting_locations.get(location, 0) + 1
            
            meeting_list.append({
                'meeting_id': meet[0],
                'title': meet[1],
                'description': meet[2],
                'scheduled_by': meet[3],
                'scheduled_for': meet[4],
                'location': location,
                'meeting_link': meet[6],
                'participants': meet[7],
                'created_at': meet[8]
            })
        
        # Log successful audit trail
        location_summary = ', '.join([f"{count} at {loc}" for loc, count in list(meeting_locations.items())[:3]]) if meeting_locations else "none"
        if len(meeting_locations) > 3:
            location_summary += " and others"
            
        log_employee_audit(
            employee_id=employee_id,
            action="view_meetings",
            details=f"Retrieved {len(meeting_list)} meetings ({upcoming_meetings} upcoming, {past_meetings} past): {location_summary}"
        )
        
    except Exception as e:
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error while fetching employee meetings: {str(e)}",
            severity="High"
        )
        
        cursor.close()
        conn.close()
        return jsonify({'error': 'Internal server error'}), 500
    
    cursor.close()
    conn.close()
    
    return jsonify(meeting_list)

@employee_bp.route('/reminders', methods=['GET'])
@employee_jwt_required()
def get_employee_reminders():
    try:
        # Get the token from the Authorization header (Bearer token)
        auth_header = request.headers.get('Authorization', '')
        token = ''
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
        logging.debug(f"Token received from Authorization header: {token}")

        employee_id, role = verify_employee_token(token)

        if not employee_id:
            logging.warning("Unauthorized access attempt to /reminders")
            log_employee_incident(
                employee_id=None,
                description="Unauthorized employee reminders access attempt - token verification failed",
                severity="Medium"
            )
            return jsonify({"error": "Unauthorized"}), 401

        conn = get_db_connection()
        cursor = conn.cursor()

        # Upcoming tasks (due in next 10 days)
        cursor.execute("""
            SELECT task_name, due_date, status
            FROM tasks
            WHERE employee_id = %s AND due_date >= CURRENT_DATE AND due_date <= CURRENT_DATE + INTERVAL '10 days'
            ORDER BY due_date
        """, (employee_id,))
        tasks = cursor.fetchall()

        # Upcoming meetings (in next 3 days)
        cursor.execute("""
            SELECT title, meeting_date, location
            FROM meetings
            WHERE employee_id = %s AND meeting_date >= CURRENT_DATE AND meeting_date <= CURRENT_DATE + INTERVAL '3 days'
            ORDER BY meeting_date
        """, (employee_id,))
        meetings = cursor.fetchall()

        # Ongoing projects nearing end (within 10 days)
        cursor.execute("""
            SELECT project_name, end_date, progress
            FROM projects
            WHERE project_id IN (
                SELECT DISTINCT project_id FROM tasks WHERE employee_id = %s
            )
            AND end_date >= CURRENT_DATE AND end_date <= CURRENT_DATE + INTERVAL '10 days'
            ORDER BY end_date
        """, (employee_id,))
        projects = cursor.fetchall()

        # Analyze data for logging
        task_statuses = {}
        for task in tasks:
            status = task[2] or 'Unknown'
            task_statuses[status] = task_statuses.get(status, 0) + 1

        project_progress = {}
        for project in projects:
            progress = project[2] or 0
            if progress < 50:
                progress_category = 'Low Progress'
            elif progress < 80:
                progress_category = 'Medium Progress'
            else:
                progress_category = 'High Progress'
            project_progress[progress_category] = project_progress.get(progress_category, 0) + 1

        reminders = {
            "tasks": [
                {"task_name": t[0], "due_date": str(t[1]), "status": t[2]} for t in tasks
            ],
            "meetings": [
                {"title": m[0], "meeting_date": str(m[1]), "location": m[2]} for m in meetings
            ],
            "projects": [
                {"project_name": p[0], "end_date": str(p[1]), "progress": p[2]} for p in projects
            ]
        }

        # Log successful audit trail
        task_summary = ', '.join([f"{count} {status}" for status, count in task_statuses.items()]) if task_statuses else "no tasks"
        project_summary = ', '.join([f"{count} {progress}" for progress, count in project_progress.items()]) if project_progress else "no projects"
        
        log_employee_audit(
            employee_id=employee_id,
            action="view_reminders",
            details=f"Retrieved reminders: {len(tasks)} upcoming tasks ({task_summary}), {len(meetings)} upcoming meetings, {len(projects)} ending projects ({project_summary})"
        )

        logging.debug(f"Reminders for employee_id {employee_id}: {reminders}")
        cursor.close()
        conn.close()

        return jsonify(reminders), 200

    except Exception as e:
        logging.error(f"Error fetching reminders: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(locals(), 'employee_id', None) or getattr(g, 'employee_id', None),
            description=f"System error while fetching employee reminders: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

#route for rendering notification page
@employee_bp.route('/notifications', methods=['GET', 'POST'])
def notifications():
    return render_template('Employee/notifications.html')

# Route for fetching announcements for a specific employee with read status
@employee_bp.route('/announcements', methods=['GET'])
@employee_jwt_required()
def get_announcements():
    employee_id = g.employee_id

    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized announcements access attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        logging.debug(f"Fetching announcements for employee_id: {employee_id}")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get employee's team_id for logging
        cursor.execute("SELECT team_id FROM employees WHERE employee_id = %s", (employee_id,))
        employee_team_info = cursor.fetchone()
        employee_team_id = employee_team_info[0] if employee_team_info else None

        query = """
            SELECT
                a.announcement_id,
                a.title,
                a.message,
                a.created_at,
                a.employee_id,
                a.team_id,
                COALESCE(r1.role_name, r2.role_name, 'Admin') AS creator_name,
                ar.read_at
            FROM announcements a
            LEFT JOIN admins ad ON a.assigned_by_admin = ad.admin_id
            LEFT JOIN roles r1 ON ad.role_id = r1.role_id
            LEFT JOIN super_admins sad ON a.assigned_by_super_admin = sad.super_admin_id
            LEFT JOIN roles r2 ON sad.role_id = r2.role_id
            LEFT JOIN announcement_reads ar
                ON ar.announcement_id = a.announcement_id AND ar.employee_id = %s
            WHERE a.employee_id = %s
               OR a.team_id = (SELECT team_id FROM employees WHERE employee_id = %s)
            ORDER BY a.created_at DESC
        """

        cursor.execute(query, (employee_id, employee_id, employee_id))
        announcements = cursor.fetchall()

        all_announcements = []
        read_count = 0
        unread_count = 0
        creator_roles = {}
        individual_announcements = 0
        team_announcements = 0
        
        for a in announcements:
            is_read = a[7] is not None  # read_at timestamp
            creator_role = a[6] or 'Unknown'
            announcement_employee_id = a[4]
            announcement_team_id = a[5]
            
            if is_read:
                read_count += 1
            else:
                unread_count += 1
                
            creator_roles[creator_role] = creator_roles.get(creator_role, 0) + 1
            
            if announcement_employee_id == employee_id:
                individual_announcements += 1
            elif announcement_team_id == employee_team_id:
                team_announcements += 1
            
            announcement_data = {
                'announcement_id': a[0],
                'title': a[1],
                'message': a[2],
                'created_at': str(a[3]),
                'employee_id': announcement_employee_id,
                'team_id': announcement_team_id,
                'creator_name': creator_role,
                'read_at': str(a[7]) if a[7] else None
            }
            logging.debug(f"Announcement fetched: {announcement_data}")
            all_announcements.append(announcement_data)

        # Log successful audit trail
        creator_summary = ', '.join([f"{count} from {role}" for role, count in creator_roles.items()]) if creator_roles else "none"
        log_employee_audit(
            employee_id=employee_id,
            action="view_announcements",
            details=f"Retrieved {len(all_announcements)} announcements ({individual_announcements} individual, {team_announcements} team): {unread_count} unread, {read_count} read | Creators: {creator_summary} (employee_team_id: {employee_team_id})"
        )

        cursor.close()
        conn.close()
        return jsonify(all_announcements), 200

    except Exception as e:
        logging.error(f"Error fetching announcements: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error while fetching announcements: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# Route to fetch events
@employee_bp.route('/events', methods=['GET'])
@employee_jwt_required()
def fetch_events():
    try:
        employee_id = g.employee_id
        
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized events access attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401
        
        logging.debug(f"Fetching events for employee_id: {employee_id}")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT e.title, e.event_date, e.status
            FROM events e
            JOIN event_participants ep ON e.event_id = ep.event_id
            WHERE ep.employee_id = %s
            ORDER BY e.event_date DESC
        """, (employee_id,))
        rows = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]
        events = [dict(zip(columns, row)) for row in rows]

        # Analyze events for logging
        status_counts = {}
        upcoming_events = 0
        past_events = 0
        current_date = datetime.now().date()
        
        for event in events:
            status = event.get('status', 'Unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
            
            event_date = event.get('event_date')
            if event_date:
                if isinstance(event_date, str):
                    event_date = datetime.strptime(event_date.split()[0], '%Y-%m-%d').date()
                elif hasattr(event_date, 'date'):
                    event_date = event_date.date()
                    
                if event_date >= current_date:
                    upcoming_events += 1
                else:
                    past_events += 1

        # Log successful audit trail
        status_summary = ', '.join([f"{count} {status}" for status, count in status_counts.items()]) if status_counts else "no events"
        log_employee_audit(
            employee_id=employee_id,
            action="view_events",
            details=f"Retrieved {len(events)} events ({upcoming_events} upcoming, {past_events} past): {status_summary}"
        )

        logging.info(f"Fetched {len(events)} events for employee_id: {employee_id}")
        cursor.close()
        conn.close()
        return jsonify(events), 200
        
    except Exception as e:
        logging.error(f"Error fetching events: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while fetching events: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# Route to fetch holidays
@employee_bp.route('/holidays', methods=['GET'])
@employee_jwt_required()
def fetch_holidays():
    try:
        employee_id = g.employee_id
        
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized holidays access attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401
        
        logging.debug(f"Fetching holidays for employee_id: {employee_id}")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                h.id, 
                h.holiday_name, 
                h.holiday_date, 
                h.is_paid, 
                h.created_at, 
                h.assigned_by_admins, 
                h.assigned_by_super_admins
            FROM holidays h
            LEFT JOIN holiday_assignments ha ON h.id = ha.holiday_id
            WHERE ha.employee_id = %s OR h.assigned_by_admins = 1 OR h.assigned_by_super_admins = 1
            ORDER BY h.holiday_date DESC
        """, (employee_id,))
        rows = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]
        holidays = [dict(zip(columns, row)) for row in rows]

        # Analyze holidays for logging
        paid_holidays = 0
        unpaid_holidays = 0
        upcoming_holidays = 0
        past_holidays = 0
        assigned_by_admin = 0
        assigned_by_super_admin = 0
        individual_assignments = 0
        current_date = datetime.now().date()
        
        for holiday in holidays:
            # Count paid vs unpaid
            if holiday.get('is_paid'):
                paid_holidays += 1
            else:
                unpaid_holidays += 1
            
            # Count assignment types
            if holiday.get('assigned_by_admins'):
                assigned_by_admin += 1
            if holiday.get('assigned_by_super_admins'):
                assigned_by_super_admin += 1
            else:
                individual_assignments += 1
            
            # Count upcoming vs past
            holiday_date = holiday.get('holiday_date')
            if holiday_date:
                if isinstance(holiday_date, str):
                    holiday_date = datetime.strptime(holiday_date.split()[0], '%Y-%m-%d').date()
                elif hasattr(holiday_date, 'date'):
                    holiday_date = holiday_date.date()
                    
                if holiday_date >= current_date:
                    upcoming_holidays += 1
                else:
                    past_holidays += 1

        # Log successful audit trail
        assignment_info = []
        if assigned_by_admin > 0:
            assignment_info.append(f"{assigned_by_admin} admin-assigned")
        if assigned_by_super_admin > 0:
            assignment_info.append(f"{assigned_by_super_admin} super-admin-assigned")
        if individual_assignments > 0:
            assignment_info.append(f"{individual_assignments} individual")
        
        assignment_summary = ', '.join(assignment_info) if assignment_info else "none"
        
        log_employee_audit(
            employee_id=employee_id,
            action="view_holidays",
            details=f"Retrieved {len(holidays)} holidays ({upcoming_holidays} upcoming, {past_holidays} past): {paid_holidays} paid, {unpaid_holidays} unpaid | Assignments: {assignment_summary}"
        )

        logging.info(f"Fetched {len(holidays)} holidays for employee_id: {employee_id}")
        cursor.close()
        conn.close()
        return jsonify(holidays), 200
        
    except Exception as e:
        logging.error(f"Error fetching holidays: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while fetching holidays: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# Route to fetch alerts for the logged-in employee, including read status
@employee_bp.route('/alerts', methods=['GET'])
@employee_jwt_required()
def fetch_alerts():
    try:
        employee_id = g.employee_id
        
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized alerts access attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401
        
        logging.debug(f"Fetching alerts for employee_id: {employee_id}")

        conn = get_db_connection()
        cursor = conn.cursor()

        # First, get the employee's team_id
        cursor.execute("SELECT team_id FROM employees WHERE employee_id = %s", (employee_id,))
        team_row = cursor.fetchone()
        team_id = team_row[0] if team_row else None

        # Now fetch relevant alerts, plus read status via LEFT JOIN
        cursor.execute("""
            SELECT 
                a.alert_id,
                a.title,
                a.message,
                a.created_at,
                a.employee_id,
                a.team_id,
                a.alert_type,
                a.severity_level,
                a.assigned_by_admin,
                a.assigned_by_super_admin,
                e.email,
                ar.alert_read_id IS NOT NULL AS is_read
            FROM alerts a
            LEFT JOIN employees e ON a.employee_id = e.employee_id
            LEFT JOIN alert_reads ar ON a.alert_id = ar.alert_id AND ar.employee_id = %s
            WHERE 
                a.employee_id = %s
                OR (a.team_id = %s AND a.team_id IS NOT NULL)
                OR (a.team_id IS NULL AND a.employee_id IS NULL)
            ORDER BY a.created_at DESC
        """, (employee_id, employee_id, team_id))

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        alerts = [dict(zip(columns, row)) for row in rows]

        # Analyze alerts for logging
        read_count = 0
        unread_count = 0
        severity_counts = {}
        alert_types = {}
        individual_alerts = 0
        team_alerts = 0
        global_alerts = 0
        assigned_by_admin = 0
        assigned_by_super_admin = 0
        
        for alert in alerts:
            # Count read vs unread
            if alert.get('is_read'):
                read_count += 1
            else:
                unread_count += 1
            
            # Count severity levels
            severity = alert.get('severity_level', 'Unknown')
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Count alert types
            alert_type = alert.get('alert_type', 'Unknown')
            alert_types[alert_type] = alert_types.get(alert_type, 0) + 1
            
            # Count assignment types
            alert_employee_id = alert.get('employee_id')
            alert_team_id = alert.get('team_id')
            
            if alert_employee_id == employee_id:
                individual_alerts += 1
            elif alert_team_id == team_id:
                team_alerts += 1
            elif not alert_employee_id and not alert_team_id:
                global_alerts += 1
            
            # Count who assigned
            if alert.get('assigned_by_admin'):
                assigned_by_admin += 1
            if alert.get('assigned_by_super_admin'):
                assigned_by_super_admin += 1

        # Log successful audit trail
        severity_summary = ', '.join([f"{count} {severity}" for severity, count in severity_counts.items()]) if severity_counts else "none"
        type_summary = ', '.join([f"{count} {atype}" for atype, count in list(alert_types.items())[:3]]) if alert_types else "none"
        if len(alert_types) > 3:
            type_summary += " and others"
        
        assignment_info = []
        if assigned_by_admin > 0:
            assignment_info.append(f"{assigned_by_admin} admin")
        if assigned_by_super_admin > 0:
            assignment_info.append(f"{assigned_by_super_admin} super-admin")
        assignment_summary = ', '.join(assignment_info) if assignment_info else "system"
        
        log_employee_audit(
            employee_id=employee_id,
            action="view_alerts",
            details=f"Retrieved {len(alerts)} alerts ({individual_alerts} individual, {team_alerts} team, {global_alerts} global): {unread_count} unread, {read_count} read | Severity: {severity_summary} | Types: {type_summary} | Assigned by: {assignment_summary} (employee_team_id: {team_id})"
        )

        logging.info(f"Fetched {len(alerts)} alerts for employee_id: {employee_id}")
        cursor.close()
        conn.close()
        return jsonify(alerts), 200
        
    except Exception as e:
        logging.error(f"Error fetching alerts: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while fetching alerts: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# Route to mark an announcement as read
@csrf.exempt
@employee_bp.route('/announcements/<int:announcement_id>/read', methods=['POST'])
@employee_jwt_required()
def mark_announcement_as_read_specific(announcement_id):
    try:
        employee_id = g.employee_id
        
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description=f"Unauthorized announcement mark-as-read attempt for announcement {announcement_id} - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        conn = get_db_connection()
        cursor = conn.cursor()

        # First verify the announcement exists and get details for logging
        cursor.execute("""
            SELECT title, message, employee_id, team_id
            FROM announcements
            WHERE announcement_id = %s
        """, (announcement_id,))
        
        announcement_info = cursor.fetchone()
        
        if not announcement_info:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to mark non-existent announcement {announcement_id} as read",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Announcement not found'}), 404

        announcement_title, announcement_message, announcement_employee_id, announcement_team_id = announcement_info

        # Get employee's team_id (if any)
        cursor.execute("SELECT team_id FROM employees WHERE employee_id = %s", (employee_id,))
        team_row = cursor.fetchone()
        team_id = team_row[0] if team_row else None

        # Verify employee has access to this announcement
        has_access = (
            announcement_employee_id == employee_id or 
            (announcement_team_id == team_id and team_id is not None)
        )
        
        if not has_access:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to mark unauthorized announcement {announcement_id} ('{announcement_title}') as read - announcement_employee_id: {announcement_employee_id}, announcement_team_id: {announcement_team_id}, employee_team_id: {team_id}",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Access denied to this announcement'}), 403

        # Check if already marked as read
        cursor.execute("""
            SELECT read_id FROM announcement_reads 
            WHERE employee_id = %s AND announcement_id = %s
        """, (employee_id, announcement_id))
        already = cursor.fetchone()

        if already:
            # Log audit for already read announcement
            log_employee_audit(
                employee_id=employee_id,
                action="mark_announcement_read",
                details=f"Attempted to mark already-read announcement {announcement_id} as read: '{announcement_title}'"
            )
            cursor.close()
            conn.close()
            return jsonify({"message": "Announcement already marked as read."}), 200

        # Insert new read record
        cursor.execute("""
            INSERT INTO announcement_reads (employee_id, read_at, team_id, announcement_id)
            VALUES (%s, NOW(), %s, %s)
            RETURNING read_id
        """, (employee_id, team_id, announcement_id))
        
        read_id = cursor.fetchone()[0] if cursor.rowcount > 0 else None
        conn.commit()

        # Log successful audit trail
        message_preview = announcement_message[:50] + "..." if announcement_message and len(announcement_message) > 50 else announcement_message or "No message"
        log_employee_audit(
            employee_id=employee_id,
            action="mark_announcement_read",
            details=f"Successfully marked announcement {announcement_id} as read (read_id: {read_id}): '{announcement_title}' - '{message_preview}'"
        )

        cursor.close()
        conn.close()
        return jsonify({"message": "Announcement marked as read."}), 200

    except Exception as e:
        if 'conn' in locals() and conn: 
            conn.rollback()
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while marking announcement {announcement_id} as read: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor: 
            cursor.close()
        if 'conn' in locals() and conn: 
            conn.close()

# Route to mark an alert as read
@csrf.exempt
@employee_bp.route('/alerts/<int:alert_id>/read', methods=['POST'])
@employee_jwt_required()
def mark_alert_as_read_specific(alert_id):
    try:
        employee_id = g.employee_id
        logging.debug(f"[mark_alert_as_read_specific] employee_id: {employee_id}, alert_id: {alert_id}")
        
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description=f"Unauthorized alert mark-as-read attempt for alert {alert_id} - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        conn = get_db_connection()
        cursor = conn.cursor()

        # First verify the alert exists and get details for logging
        cursor.execute("""
            SELECT title, message, alert_type, severity_level, employee_id, team_id
            FROM alerts
            WHERE alert_id = %s
        """, (alert_id,))
        
        alert_info = cursor.fetchone()
        
        if not alert_info:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to mark non-existent alert {alert_id} as read",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Alert not found'}), 404

        alert_title, alert_message, alert_type, severity_level, alert_employee_id, alert_team_id = alert_info

        # Get employee's team_id (if any)
        cursor.execute("SELECT team_id FROM employees WHERE employee_id = %s", (employee_id,))
        team_row = cursor.fetchone()
        team_id = team_row[0] if team_row else None
        logging.debug(f"[mark_alert_as_read_specific] Fetched team_id: {team_id} for employee_id: {employee_id}")

        # Verify employee has access to this alert
        has_access = (
            alert_employee_id == employee_id or 
            (alert_team_id == team_id and team_id is not None) or
            (alert_employee_id is None and alert_team_id is None)  # Global alerts
        )
        
        if not has_access:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to mark unauthorized alert {alert_id} ('{alert_title}') as read - alert_employee_id: {alert_employee_id}, alert_team_id: {alert_team_id}, employee_team_id: {team_id}",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Access denied to this alert'}), 403

        # Check if already marked as read
        cursor.execute("""
            SELECT alert_read_id FROM alert_reads 
            WHERE employee_id = %s AND alert_id = %s
        """, (employee_id, alert_id))
        already = cursor.fetchone()
        logging.debug(f"[mark_alert_as_read_specific] Already read? {already}")

        if already:
            logging.info(f"[mark_alert_as_read_specific] Alert {alert_id} already marked as read by employee {employee_id}")
            # Log audit for already read alert
            log_employee_audit(
                employee_id=employee_id,
                action="mark_alert_read",
                details=f"Attempted to mark already-read alert {alert_id} as read: '{alert_title}' ({alert_type}, {severity_level})"
            )
            cursor.close()
            conn.close()
            return jsonify({"message": "Alert already marked as read."}), 200

        # Insert new read record
        logging.debug(f"[mark_alert_as_read_specific] Inserting read record: employee_id={employee_id}, team_id={team_id}, alert_id={alert_id}")
        cursor.execute("""
            INSERT INTO alert_reads (employee_id, read_at, team_id, alert_id)
            VALUES (%s, NOW(), %s, %s)
            RETURNING alert_read_id
        """, (employee_id, team_id, alert_id))
        
        alert_read_id = cursor.fetchone()[0] if cursor.rowcount > 0 else None
        conn.commit()
        logging.info(f"[mark_alert_as_read_specific] Alert {alert_id} marked as read by employee {employee_id}")

        # Log successful audit trail
        message_preview = alert_message[:50] + "..." if alert_message and len(alert_message) > 50 else alert_message or "No message"
        log_employee_audit(
            employee_id=employee_id,
            action="mark_alert_read",
            details=f"Successfully marked alert {alert_id} as read (read_id: {alert_read_id}): '{alert_title}' ({alert_type}, {severity_level}) - '{message_preview}'"
        )

        cursor.close()
        conn.close()
        return jsonify({"message": "Alert marked as read."}), 200

    except Exception as e:
        if 'conn' in locals() and conn: 
            conn.rollback()
        logging.error(f"[mark_alert_as_read_specific] Error: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while marking alert {alert_id} as read: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor: 
            cursor.close()
        if 'conn' in locals() and conn: 
            conn.close()

# Route to fetch meetings
@employee_bp.route('/meetings', methods=['GET'])
@employee_jwt_required()
def fetch_meetings():
    try:
        employee_id = g.employee_id
        
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized meetings access attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401
        
        logging.debug(f"Fetching meetings for employee_id: {employee_id}")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get employee's team_id
        cursor.execute("SELECT team_id FROM employees WHERE employee_id = %s", (employee_id,))
        team_row = cursor.fetchone()
        team_id = team_row[0] if team_row else None

        # Fetch meetings for employee, their team, or for all
        cursor.execute("""
            SELECT 
                meeting_id,
                title,
                description,
                meeting_date,
                duration,
                location,
                created_at,
                employee_id,
                team_id,
                status,
                assigned_by_admins,
                assigned_by_super_admins
            FROM meetings
            WHERE
                (employee_id = %s)
                OR (team_id = %s AND team_id IS NOT NULL)
                OR (employee_id IS NULL AND team_id IS NULL)
            ORDER BY meeting_date DESC
        """, (employee_id, team_id))

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        meetings = []
        
        # Analyze meetings for logging
        individual_meetings = 0
        team_meetings = 0
        global_meetings = 0
        status_counts = {}
        upcoming_meetings = 0
        past_meetings = 0
        assigned_by_admin = 0
        assigned_by_super_admin = 0
        locations = {}
        total_duration_minutes = 0
        
        current_datetime = datetime.now()
        
        for row in rows:
            m = dict(zip(columns, row))
            
            # Convert timedelta to string if present and calculate total duration
            if isinstance(m['duration'], (str, type(None))):
                pass  # already fine
            else:
                duration_str = str(m['duration'])
                m['duration'] = duration_str
                
                # Extract minutes for total calculation
                try:
                    if ':' in duration_str:
                        time_parts = duration_str.split(':')
                        hours = int(time_parts[0])
                        minutes = int(time_parts[1])
                        total_duration_minutes += (hours * 60) + minutes
                except:
                    pass  # Skip if duration parsing fails
            
            meetings.append(m)
            
            # Analyze meeting data for logging
            meeting_employee_id = m.get('employee_id')
            meeting_team_id = m.get('team_id')
            meeting_status = m.get('status', 'Unknown')
            meeting_date = m.get('meeting_date')
            meeting_location = m.get('location', 'Not specified')
            
            # Count meeting types
            if meeting_employee_id == employee_id:
                individual_meetings += 1
            elif meeting_team_id == team_id:
                team_meetings += 1
            elif not meeting_employee_id and not meeting_team_id:
                global_meetings += 1
            
            # Count status
            status_counts[meeting_status] = status_counts.get(meeting_status, 0) + 1
            
            # Count upcoming vs past
            if meeting_date and meeting_date > current_datetime:
                upcoming_meetings += 1
            else:
                past_meetings += 1
            
            # Count assignment types
            if m.get('assigned_by_admins'):
                assigned_by_admin += 1
            if m.get('assigned_by_super_admins'):
                assigned_by_super_admin += 1
            
            # Count locations
            locations[meeting_location] = locations.get(meeting_location, 0) + 1

        # Log successful audit trail
        status_summary = ', '.join([f"{count} {status}" for status, count in status_counts.items()]) if status_counts else "no meetings"
        
        location_summary = ', '.join([f"{count} at {loc}" for loc, count in list(locations.items())[:3]]) if locations else "none"
        if len(locations) > 3:
            location_summary += " and others"
        
        assignment_info = []
        if assigned_by_admin > 0:
            assignment_info.append(f"{assigned_by_admin} admin")
        if assigned_by_super_admin > 0:
            assignment_info.append(f"{assigned_by_super_admin} super-admin")
        assignment_summary = ', '.join(assignment_info) if assignment_info else "employee/system"
        
        duration_hours = total_duration_minutes / 60 if total_duration_minutes > 0 else 0
        
        log_employee_audit(
            employee_id=employee_id,
            action="view_meetings",
            details=f"Retrieved {len(meetings)} meetings ({individual_meetings} individual, {team_meetings} team, {global_meetings} global): {upcoming_meetings} upcoming, {past_meetings} past | Status: {status_summary} | Locations: {location_summary} | Total duration: {duration_hours:.1f}h | Assigned by: {assignment_summary} (employee_team_id: {team_id})"
        )

        logging.info(f"Fetched {len(meetings)} meetings for employee_id: {employee_id}")
        cursor.close()
        conn.close()
        return jsonify(meetings), 200
        
    except Exception as e:
        logging.error(f"Error fetching meetings: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while fetching meetings: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()