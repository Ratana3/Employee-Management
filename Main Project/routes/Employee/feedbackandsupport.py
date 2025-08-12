
#route for submitting ticket request
import logging
import os
import traceback
from flask import g, jsonify, render_template, request
from routes.Auth.config import UPLOAD_FOLDER_TICKETS
from routes.Auth.token import employee_jwt_required
from . import employee_bp
from routes.Auth.utils import get_db_connection
from werkzeug.utils import secure_filename
import psycopg2
from extensions import csrf
from routes.Auth.audit import log_employee_audit,log_employee_incident

#route for displaying notifications
@employee_bp.route('/feedbackandsupport', methods=['GET', 'POST'])
def feedback_and_support():
    return render_template('Employee/feedbackandsupport.html')

@employee_bp.route('/submit_ticket_request', methods=['POST'])
@employee_jwt_required()
def submit_ticket_request():
    try:
        logging.info("Received ticket submission request")
        logging.debug(f"Request form: {request.form}")
        logging.debug(f"Request files: {request.files}")

        employee_id = g.employee_id
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized ticket submission attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        category = request.form.get('category')
        subject = request.form.get('subject')
        description = request.form.get('description')
        priority = request.form.get('priority')
        file = request.files.get('attachment')

        logging.debug(f"Parsed inputs - Category: {category}, Subject: {subject}, "
                      f"Description: {description}, Priority: {priority}, File: {'Yes' if file else 'No'}")

        if not all([category, subject, description, priority]):
            logging.warning("Missing one or more required fields")
            log_employee_incident(
                employee_id=employee_id,
                description=f"Ticket submission attempted with missing required fields - Category: {bool(category)}, Subject: {bool(subject)}, Description: {bool(description)}, Priority: {bool(priority)}",
                severity="Low"
            )
            return jsonify({'error': 'Missing required fields'}), 400

        file_path = None
        file_info = ""
        if file:
            # Validate file
            if file.filename == '':
                log_employee_incident(
                    employee_id=employee_id,
                    description="Ticket submission attempted with empty file attachment",
                    severity="Low"
                )
                return jsonify({'error': 'Invalid file attachment'}), 400
            
            filename = secure_filename(file.filename)
            if not filename:
                log_employee_incident(
                    employee_id=employee_id,
                    description=f"Ticket submission attempted with invalid filename: '{file.filename}'",
                    severity="Low"
                )
                return jsonify({'error': 'Invalid filename'}), 400
            
            file_path = os.path.join(UPLOAD_FOLDER_TICKETS, filename)
            try:
                file.save(file_path)
                file_info = f" with attachment '{filename}'"
                logging.info(f"File saved to {file_path}")
            except Exception as file_error:
                log_employee_incident(
                    employee_id=employee_id,
                    description=f"File upload failed during ticket submission: {str(file_error)}",
                    severity="Medium"
                )
                return jsonify({'error': 'File upload failed'}), 500

        conn = get_db_connection()
        cursor = conn.cursor()

        logging.debug(f"Inserting ticket for employee_id={employee_id}")
        cursor.execute("""
            INSERT INTO tickets (employee_id, category, subject, description, priority, status, created_at, file_path)
            VALUES (%s, %s, %s, %s, %s, 'Open', NOW(), %s)
            RETURNING ticket_id
        """, (employee_id, category, subject, description, priority, file_path))

        ticket_id = cursor.fetchone()[0] if cursor.rowcount > 0 else None
        conn.commit()
        logging.info("Ticket inserted successfully")

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="submit_ticket",
            details=f"Successfully submitted {priority} priority ticket (ID: {ticket_id}) in category '{category}' with subject '{subject}'{file_info}"
        )

        cursor.close()
        conn.close()

        return jsonify({'message': 'Ticket submitted successfully'}), 201

    except Exception as e:
        logging.error(f"Error submitting ticket: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during ticket submission: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500

# Updated route for fetching tickets with search, filter, and sort
@employee_bp.route('/get_my_tickets', methods=['GET'])
@employee_jwt_required()
def get_my_tickets():
    conn = None
    cursor = None
    try:
        employee_id = g.employee_id
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized ticket retrieval attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        search_query = request.args.get('search', '')
        sort_order = request.args.get('sort', 'desc')
        deadline_filter = request.args.get('deadline')

        if sort_order not in ['asc', 'desc']:
            sort_order = 'desc'

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        query = f"""
            SELECT 
                t.ticket_id,
                t.employee_id,
                t.category,
                t.subject,
                t.description,
                t.priority,
                t.status,
                t.created_at,
                t.updated_at,
                t.file_path,
                COALESCE(json_agg(
                    json_build_object(
                        'response_id', r.response_id,
                        'ticket_id', r.ticket_id,
                        'employee_id', r.employee_id,
                        'response', r.response,
                        'responded_at', r.responded_at,
                        'responded_by', r.responded_by,
                        'admin_response', r.admin_response,
                        'responded_by_admin', r.responded_by_admin
                    )
                ) FILTER (WHERE r.response_id IS NOT NULL), '[]') AS responses
            FROM tickets t
            LEFT JOIN ticket_responses r ON t.ticket_id = r.ticket_id
            WHERE t.employee_id = %s
        """
        params = [employee_id]

        filter_details = []
        if search_query:
            query += " AND (t.subject ILIKE %s OR t.description ILIKE %s)"
            params.extend([f"%{search_query}%", f"%{search_query}%"])
            filter_details.append(f"search='{search_query}'")

        if deadline_filter == 'upcoming':
            query += " AND (t.updated_at IS NOT NULL AND t.updated_at > NOW())"
            filter_details.append("deadline=upcoming")
        elif deadline_filter == 'past':
            query += " AND (t.updated_at IS NOT NULL AND t.updated_at <= NOW())"
            filter_details.append("deadline=past")

        query += f" GROUP BY t.ticket_id ORDER BY t.created_at {sort_order.upper()}"

        cursor.execute(query, params)
        tickets = cursor.fetchall()

        result = []
        for t in tickets:
            ticket_data = {
                'ticket_id': t['ticket_id'],
                'employee_id': t['employee_id'],
                'category': t['category'],
                'subject': t['subject'],
                'description': t['description'],
                'priority': t['priority'],
                'status': t['status'],
                'created_at': t['created_at'].isoformat() if t['created_at'] else None,
                'updated_at': t['updated_at'].isoformat() if t['updated_at'] else None,
                'file_path': t['file_path'],
                'responses': t['responses']
            }
            result.append(ticket_data)

        # Log successful audit trail
        filter_text = f" with filters: {', '.join(filter_details)}" if filter_details else ""
        log_employee_audit(
            employee_id=employee_id,
            action="get_my_tickets",
            details=f"Retrieved {len(tickets)} tickets (sort: {sort_order}){filter_text}"
        )

        return jsonify(result), 200
        
    except Exception as e:
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while retrieving tickets: {str(e)}",
            severity="High"
        )
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# route for deleting ticket response
@employee_bp.route('/delete-response/<int:response_id>', methods=['POST'])
@employee_jwt_required()
def delete_response(response_id):
    try:
        employee_id = g.employee_id
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized ticket response deletion attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        conn = get_db_connection()
        cursor = conn.cursor()

        # First, verify the response belongs to this employee and get details for logging
        cursor.execute("""
            SELECT tr.response_id, tr.ticket_id, tr.response, t.subject, t.employee_id
            FROM ticket_responses tr
            JOIN tickets t ON tr.ticket_id = t.ticket_id
            WHERE tr.response_id = %s
        """, (response_id,))
        
        response_data = cursor.fetchone()
        
        if not response_data:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to delete non-existent ticket response {response_id}",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Response not found'}), 404

        response_id_db, ticket_id, response_text, ticket_subject, ticket_owner = response_data

        # Check if the employee owns the ticket (employees should only delete responses on their own tickets)
        if ticket_owner != employee_id:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to delete ticket response {response_id} on ticket {ticket_id} that doesn't belong to them",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Unauthorized: Cannot delete response on ticket that does not belong to you'}), 403

        # Perform the deletion
        query = "DELETE FROM ticket_responses WHERE response_id = %s"
        cursor.execute(query, (response_id,))
        
        if cursor.rowcount == 0:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Unexpected error: Ticket response {response_id} deletion failed after validation checks passed",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Failed to delete response'}), 500

        conn.commit()

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="delete_ticket_response",
            details=f"Successfully deleted response {response_id} on ticket {ticket_id} ('{ticket_subject}'): '{response_text[:100]}...'"
        )

        cursor.close()
        conn.close()

        return jsonify({'message': 'Response deleted successfully'})

    except Exception as e:
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during ticket response deletion: {str(e)}",
            severity="High"
        )
        
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        
        return jsonify({'error': 'Failed to delete response'}), 500
     
# Route for fetching feedback requests
@employee_bp.route('/feedback_requests', methods=['GET'])
@employee_jwt_required()
def get_feedback_requests():
    employee_id = g.employee_id
    logging.debug(f"[FEEDBACK] Fetching requests for employee_id: {employee_id}")

    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized feedback requests access attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # First get employee's team_id for logging
        cursor.execute("SELECT team_id FROM employees WHERE employee_id = %s", (employee_id,))
        team_info = cursor.fetchone()
        team_id = team_info[0] if team_info else None

        query = """
            SELECT request_id, title, message, deadline, created_at, employee_id, team_id
            FROM feedback_requests
            WHERE employee_id = %s OR team_id = (
                SELECT team_id FROM employees WHERE employee_id = %s
            )
            ORDER BY created_at DESC
        """
        cursor.execute(query, (employee_id, employee_id))
        requests = cursor.fetchall()
        logging.debug(f"[FEEDBACK] {len(requests)} feedback requests retrieved.")

        all_requests = [{
            'request_id': r[0],
            'title': r[1],
            'message': r[2],
            'deadline': str(r[3]),
            'created_at': str(r[4]),
            'employee_id': r[5],
            'team_id': r[6],
        } for r in requests]

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="get_feedback_requests",
            details=f"Retrieved {len(requests)} feedback requests (team_id: {team_id})"
        )

        return jsonify(all_requests), 200
        
    except Exception as e:
        logging.error(f"[FEEDBACK] Error fetching feedback requests: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error while fetching feedback requests: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Route for submitting feedback responses
@employee_bp.route('/submit_feedback_response', methods=['POST'])
@employee_jwt_required()
def submit_feedback_response():
    try:
        employee_id = g.employee_id
        
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized feedback response submission attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        request_id = data.get('request_id')
        response = data.get('response', '').strip()

        if not request_id or not response:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Feedback response submission attempted with missing data - request_id: {bool(request_id)}, response: {bool(response)}",
                severity="Low"
            )
            return jsonify({'error': 'Missing request_id or response'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get employee info for logging
        cursor.execute("SELECT first_name, last_name, email FROM employees WHERE employee_id = %s", (employee_id,))
        employee_info = cursor.fetchone()
        employee_name = f"{employee_info[0]} {employee_info[1]}" if employee_info else f"Employee {employee_id}"
        employee_email = employee_info[2] if employee_info else "unknown@email.com"

        # 1. APPLICATION-LEVEL CHECK (for better user experience)
        cursor.execute("""
            SELECT response_id, submitted_at FROM feedback_responses 
            WHERE request_id = %s AND employee_id = %s
        """, (request_id, employee_id))
        
        existing_response = cursor.fetchone()
        
        if existing_response:
            existing_response_id, submitted_at = existing_response
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee {employee_name} ({employee_email}) attempted duplicate feedback response to request {request_id} - previous response {existing_response_id} at {submitted_at}",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({
                'error': 'You have already responded to this feedback request',
                'previous_submission': str(submitted_at) if submitted_at else 'Unknown',
                'response_id': existing_response_id
            }), 400

        # Verify access permissions (your existing code)
        cursor.execute("""
            SELECT fr.title, fr.employee_id, fr.team_id, e.team_id as employee_team_id
            FROM feedback_requests fr
            JOIN employees e ON e.employee_id = %s
            WHERE fr.request_id = %s
        """, (employee_id, request_id))
        
        request_info = cursor.fetchone()
        
        if not request_info:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee {employee_name} attempted to respond to non-existent feedback request {request_id}",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Feedback request not found'}), 404

        request_title, target_employee_id, target_team_id, employee_team_id = request_info
        has_access = (target_employee_id == employee_id) or (target_team_id == employee_team_id)
        
        if not has_access:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee {employee_name} attempted unauthorized access to feedback request {request_id}",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Access denied to this feedback request'}), 403

        try:
            # 2. DATABASE-LEVEL PROTECTION (ultimate safety net)
            current_time = datetime.utcnow()
            cursor.execute("""
                INSERT INTO feedback_responses (request_id, employee_id, response, submitted_at)
                VALUES (%s, %s, %s, %s)
                RETURNING response_id
            """, (request_id, employee_id, response, current_time))
            
            response_id = cursor.fetchone()[0] if cursor.rowcount > 0 else None
            conn.commit()

            # Log successful submission
            response_preview = response[:100] + "..." if len(response) > 100 else response
            log_employee_audit(
                employee_id=employee_id,
                action="submit_feedback_response",
                details=f"Successfully submitted feedback response (ID: {response_id}) to request {request_id} ('{request_title}'): '{response_preview}' | Employee: {employee_name} ({employee_email})"
            )

            cursor.close()
            conn.close()
            return jsonify({
                'message': 'Feedback response submitted successfully',
                'response_id': response_id,
                'submitted_at': current_time.strftime('%Y-%m-%d %H:%M:%S')
            }), 201

        except psycopg2.IntegrityError as e:
            # DATABASE CONSTRAINT VIOLATION - This catches race conditions!
            conn.rollback()
            
            if 'unique_employee_request_response' in str(e) or 'duplicate key' in str(e).lower():
                log_employee_incident(
                    employee_id=employee_id,
                    description=f"Database constraint prevented duplicate feedback response from {employee_name} to request {request_id} (race condition detected)",
                    severity="High"
                )
                cursor.close()
                conn.close()
                return jsonify({
                    'error': 'You have already responded to this feedback request (detected by database)',
                    'details': 'This was prevented by database-level protection'
                }), 409  # 409 Conflict
            else:
                # Other database integrity errors
                raise e

    except Exception as e:
        logging.error(f"Error submitting feedback response: {e}", exc_info=True)
        
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during feedback response submission: {str(e)}",
            severity="High"
        )
        
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        
        return jsonify({'error': 'Internal server error'}), 500
    
#route for fetching employee's response
@employee_bp.route('/feedback_responses', methods=['GET'])
@employee_jwt_required()
def get_feedback_responses():
    employee_id = g.employee_id
    
    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized feedback responses access attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # First get employee's team_id for logging
        cursor.execute("SELECT team_id FROM employees WHERE employee_id = %s", (employee_id,))
        team_info = cursor.fetchone()
        team_id = team_info[0] if team_info else None

        # Get all responses for requests visible to this employee
        cursor.execute("""
            SELECT r.response_id, r.request_id, r.employee_id, r.response, r.submitted_at, e.email,
                   fr.title, fr.employee_id as request_target_employee, fr.team_id as request_target_team
            FROM feedback_responses r
            JOIN employees e ON r.employee_id = e.employee_id
            JOIN feedback_requests fr ON r.request_id = fr.request_id
            WHERE r.request_id IN (
                SELECT request_id FROM feedback_requests
                WHERE employee_id = %s OR team_id = (
                    SELECT team_id FROM employees WHERE employee_id = %s
                )
            )
            ORDER BY r.request_id, r.submitted_at
        """, (employee_id, employee_id))
        results = cursor.fetchall()

        responses = [
            {
                'response_id': row[0],
                'request_id': row[1],
                'employee_id': row[2],
                'response': row[3],
                'submitted_at': str(row[4]),
                'employee_email': row[5]
            }
            for row in results
        ]

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="get_feedback_responses",
            details=f"Retrieved {len(responses)} feedback responses for accessible requests (team_id: {team_id})"
        )

        return jsonify(responses)
        
    except Exception as e:
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error while fetching feedback responses: {str(e)}",
            severity="High"
        )
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cursor.close()
        conn.close()

# Route for fetching assigned surveys for employee, with detailed debugging and fetching all correct columns
@employee_bp.route('/assigned_surveys', methods=['GET'])
@employee_jwt_required()
def get_assigned_surveys():
    import logging

    employee_id = g.employee_id
    logging.debug(f"[ASSIGNED_SURVEYS] employee_id: {employee_id}")

    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized assigned surveys access attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Only grab assignments where this employee is the assignee and has not submitted
        cursor.execute("""
            SELECT sa.survey_id, sa.assignment_id, sa.employee_id, sa.team_id, sa.has_submitted
            FROM survey_assignments sa
            WHERE sa.employee_id = %s
              AND COALESCE(sa.has_submitted, FALSE) = FALSE
        """, (employee_id,))
        assignments = cursor.fetchall()
        logging.debug(f"[ASSIGNED_SURVEYS] assignments found: {assignments}")

        if not assignments:
            logging.info("[ASSIGNED_SURVEYS] No active assignments found for employee.")
            
            # Log successful audit trail for no assignments
            log_employee_audit(
                employee_id=employee_id,
                action="get_assigned_surveys",
                details="Retrieved assigned surveys: no active assignments found"
            )
            
            return jsonify([]), 200

        survey_ids = [a[0] for a in assignments]
        assignment_ids = [a[1] for a in assignments]
        logging.debug(f"[ASSIGNED_SURVEYS] survey_ids: {survey_ids}")

        # Fetch survey details for those assignments (must still be globally active)
        format_strings = ','.join(['%s'] * len(survey_ids))
        # Fetch all columns relevant from your create_survey route
        query = f"""
            SELECT s.survey_id, s.title, s.description, s.created_at,
                   s.is_active, s.super_admin_id, s.admin_id, s.created_by
            FROM surveys s
            WHERE s.is_active = TRUE
            AND s.survey_id IN ({format_strings})
            ORDER BY s.created_at DESC
        """
        logging.debug(f"[ASSIGNED_SURVEYS] Survey details query: {query}")
        logging.debug(f"[ASSIGNED_SURVEYS] Query params: {tuple(survey_ids)}")
        cursor.execute(query, tuple(survey_ids))
        surveys = cursor.fetchall()
        logging.debug(f"[ASSIGNED_SURVEYS] Survey records: {surveys}")

        # Check for surveys that are assigned but not active (potential data integrity issue)
        found_survey_ids = [s[0] for s in surveys]
        missing_survey_ids = [sid for sid in survey_ids if sid not in found_survey_ids]
        
        if missing_survey_ids:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee has assignments to inactive or non-existent surveys: {missing_survey_ids}",
                severity="Medium"
            )

        result = [{
            'survey_id': s[0],
            'title': s[1],
            'description': s[2],
            'created_at': str(s[3]),
            'is_active': s[4],
            'super_admin_id': s[5],
            'admin_id': s[6],
            'created_by': s[7]
        } for s in surveys]

        # Log successful audit trail
        survey_titles = [s[1] for s in surveys]
        log_employee_audit(
            employee_id=employee_id,
            action="get_assigned_surveys",
            details=f"Retrieved {len(result)} assigned surveys: {', '.join(survey_titles[:3])}{' and others' if len(survey_titles) > 3 else ''} (assignment_ids: {assignment_ids[:3]}{'...' if len(assignment_ids) > 3 else ''})"
        )

        logging.info(f"[ASSIGNED_SURVEYS] Returning {len(result)} survey(s) for employee_id {employee_id}")
        return jsonify(result), 200

    except Exception as e:
        import traceback
        logging.error(f"[ASSIGNED_SURVEYS] Error fetching assigned surveys: {e}")
        logging.error(traceback.format_exc())
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error while fetching assigned surveys: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500

    finally:
        if 'conn' in locals() and conn:
            cursor.close()
            conn.close()

import logging

# Route for fetching options for survey questions
@employee_bp.route('/survey_question_options/<int:question_id>', methods=['GET'])
@employee_jwt_required()
def get_question_options(question_id):
    try:
        employee_id = g.employee_id
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized survey question options access attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First verify the question exists and get survey info for logging
        cursor.execute("""
            SELECT sq.question_text, sq.survey_id, s.title
            FROM survey_questions sq
            JOIN surveys s ON sq.survey_id = s.survey_id
            WHERE sq.question_id = %s
        """, (question_id,))
        question_info = cursor.fetchone()
        
        if not question_info:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to access options for non-existent survey question {question_id}",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Question not found'}), 404
        
        question_text, survey_id, survey_title = question_info
        
        cursor.execute("""
            SELECT option_id, option_text
            FROM survey_question_options
            WHERE question_id = %s
            ORDER BY option_id
        """, (question_id,))
        options = [{
            'option_id': row[0],
            'option_text': row[1]
        } for row in cursor.fetchall()]
        
        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="get_question_options",
            details=f"Retrieved {len(options)} options for question {question_id} in survey '{survey_title}' (survey_id: {survey_id})"
        )
        
        return jsonify(options), 200
        
    except Exception as e:
        logging.error(f"Error fetching options: {str(e)}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while fetching survey question options for question {question_id}: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            cursor.close()
            conn.close()

# Route for submitting response to the survey
@employee_bp.route('/survey/<int:survey_id>/submit', methods=['POST'])
@employee_jwt_required()
@csrf.exempt
def submit_survey_response(survey_id):
    logging.debug(f"[SURVEY SUBMIT] Survey submission initiated for survey_id: {survey_id}")

    employee_id = g.employee_id
    logging.debug(f"[SURVEY SUBMIT] Verified employee_id from token: {employee_id}")

    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description=f"Unauthorized survey submission attempt for survey {survey_id} - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    # Debug print the full request data
    try:
        data = request.get_json(force=True)
    except Exception as e:
        logging.error("[SURVEY SUBMIT] Failed to parse JSON from request: %s", e)
        log_employee_incident(
            employee_id=employee_id,
            description=f"Survey submission failed for survey {survey_id} due to invalid JSON: {str(e)}",
            severity="Low"
        )
        return jsonify({'error': 'Invalid JSON'}), 400

    logging.debug(f"[SURVEY SUBMIT] Raw request data: {data}")

    responses = data.get('responses')

    if not responses:
        logging.warning("[SURVEY SUBMIT] No responses provided in request.")
        log_employee_incident(
            employee_id=employee_id,
            description=f"Survey submission attempted for survey {survey_id} with no responses provided",
            severity="Low"
        )
        return jsonify({'error': 'Missing responses'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get survey title for logging
        cursor.execute("SELECT title FROM surveys WHERE survey_id = %s", (survey_id,))
        survey_info = cursor.fetchone()
        survey_title = survey_info[0] if survey_info else f"Survey {survey_id}"

        logging.debug(f"[SURVEY SUBMIT] Checking for unsubmitted assignment for employee {employee_id}, survey {survey_id}...")
        cursor.execute("""
            SELECT assignment_id, attempt_number FROM survey_assignments
            WHERE survey_id = %s AND employee_id = %s AND COALESCE(has_submitted, FALSE) = FALSE
            ORDER BY attempt_number DESC NULLS LAST LIMIT 1
        """, (survey_id, employee_id))
        assignment = cursor.fetchone()
        logging.debug(f"[SURVEY SUBMIT] assignment fetch result: {assignment}")

        if not assignment:
            logging.warning("[SURVEY SUBMIT] No unsubmitted assignment found for this survey and employee.")
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to submit survey {survey_id} ('{survey_title}') without valid assignment or after already submitting",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'You are not permitted to submit this survey.'}), 403

        assignment_id, attempt_number = assignment if assignment else (None, 1)
        logging.debug(f"[SURVEY SUBMIT] Using assignment_id: {assignment_id}, attempt_number: {attempt_number}")

        # Validate all responses before inserting
        question_ids = [r.get('question_id') for r in responses]
        if not all(question_ids):
            log_employee_incident(
                employee_id=employee_id,
                description=f"Survey submission for survey {survey_id} contained responses with missing question IDs",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Invalid response format - missing question IDs'}), 400

        # Insert responses for this attempt
        for idx, r in enumerate(responses):
            logging.debug(f"[SURVEY SUBMIT] Inserting response #{idx+1}: {r}")
            cursor.execute("""
                INSERT INTO survey_responses (survey_id, question_id, employee_id, response_text, attempt_number, submitted_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (survey_id, r['question_id'], employee_id, r['response_text'], attempt_number))

        # Mark assignment as submitted
        logging.debug(f"[SURVEY SUBMIT] Marking assignment as submitted (assignment_id: {assignment_id})")
        cursor.execute("""
            UPDATE survey_assignments
            SET has_submitted = TRUE
            WHERE assignment_id = %s
        """, (assignment_id,))

        conn.commit()
        
        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="submit_survey_response",
            details=f"Successfully submitted {len(responses)} responses to survey {survey_id} ('{survey_title}') - attempt #{attempt_number} (assignment_id: {assignment_id})"
        )
        
        logging.info(f"[SURVEY SUBMIT] Responses submitted successfully for employee_id: {employee_id}, survey_id: {survey_id}, attempt_number: {attempt_number}")
        return jsonify({'message': f'Responses submitted successfully (attempt #{attempt_number})'}), 201

    except Exception as e:
        logging.exception("[SURVEY SUBMIT] Exception occurred while submitting survey responses.")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error during survey {survey_id} submission: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        if 'conn' in locals() and conn:
            cursor.close()
            conn.close()

# Route for fetching questions of the survey
@employee_bp.route('/survey/<int:survey_id>/questions', methods=['GET'])
@employee_jwt_required()
def get_survey_questions(survey_id):
    try:
        employee_id = g.employee_id
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description=f"Unauthorized survey questions access attempt for survey {survey_id} - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First check if survey exists and get title for logging
        cursor.execute("SELECT title, is_active FROM surveys WHERE survey_id = %s", (survey_id,))
        survey_info = cursor.fetchone()
        
        if not survey_info:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to access questions for non-existent survey {survey_id}",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Survey not found'}), 404
        
        survey_title, is_active = survey_info
        
        if not is_active:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to access questions for inactive survey {survey_id} ('{survey_title}')",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Survey is not active'}), 403
        
        # Check if employee has access to this survey
        cursor.execute("""
            SELECT assignment_id FROM survey_assignments
            WHERE survey_id = %s AND employee_id = %s
        """, (survey_id, employee_id))
        assignment = cursor.fetchone()
        
        if not assignment:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to access questions for survey {survey_id} ('{survey_title}') they are not assigned to",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Access denied to this survey'}), 403
        
        cursor.execute("""
            SELECT question_id, question_text, question_type
            FROM survey_questions
            WHERE survey_id = %s
            ORDER BY question_id
        """, (survey_id,))
        questions = cursor.fetchall()

        result = []
        for q in questions:
            question = {
                'question_id': q[0],
                'question_text': q[1],
                'question_type': q[2]
            }
            result.append(question)

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="get_survey_questions",
            details=f"Retrieved {len(result)} questions for survey {survey_id} ('{survey_title}')"
        )

        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Error retrieving survey questions: {e}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while fetching questions for survey {survey_id}: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        if 'conn' in locals() and conn:
            cursor.close()
            conn.close()

# route for editing ticket response
@employee_bp.route('/edit-response/<int:response_id>', methods=['POST'])
@employee_jwt_required()
def edit_response(response_id):
    logging.debug(f"[EDIT_RESPONSE] Edit request received for response_id: {response_id}")
    conn = None
    try:
        employee_id = g.employee_id
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description=f"Unauthorized ticket response edit attempt for response {response_id} - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json
        logging.debug(f"[EDIT_RESPONSE] Received request data: {data}")
        updated_response = data.get('response')
        logging.debug(f"[EDIT_RESPONSE] Updated response content: {updated_response}")

        if not updated_response:
            logging.warning("[EDIT_RESPONSE] No response provided in request")
            log_employee_incident(
                employee_id=employee_id,
                description=f"Ticket response edit attempted for response {response_id} with no content provided",
                severity="Low"
            )
            return jsonify({'error': 'Response content is required'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # First verify the response exists and get details for logging and authorization
        cursor.execute("""
            SELECT tr.response_id, tr.ticket_id, tr.response, tr.employee_id, 
                   t.subject, t.employee_id as ticket_owner_id
            FROM ticket_responses tr
            JOIN tickets t ON tr.ticket_id = t.ticket_id
            WHERE tr.response_id = %s
        """, (response_id,))
        
        response_data = cursor.fetchone()
        
        if not response_data:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to edit non-existent ticket response {response_id}",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Response not found'}), 404

        response_id_db, ticket_id, old_response, response_owner_id, ticket_subject, ticket_owner_id = response_data

        # Check if the employee owns the response OR owns the ticket
        if response_owner_id != employee_id and ticket_owner_id != employee_id:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to edit ticket response {response_id} on ticket {ticket_id} that doesn't belong to them (response owner: {response_owner_id}, ticket owner: {ticket_owner_id})",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Unauthorized: Cannot edit response that does not belong to you'}), 403

        query = """
            UPDATE ticket_responses
            SET response = %s,
                responded_at = CURRENT_TIMESTAMP
            WHERE response_id = %s
        """
        logging.debug(f"[EDIT_RESPONSE] Executing query: {query.strip()} with values: ({updated_response}, {response_id})")
        cursor.execute(query, (updated_response, response_id))
        
        if cursor.rowcount == 0:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Unexpected error: Ticket response {response_id} edit failed after validation checks passed",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Failed to update response'}), 500
        
        conn.commit()
        logging.info("[EDIT_RESPONSE] Update committed successfully")

        # Log successful audit trail
        old_preview = old_response[:50] + "..." if len(old_response) > 50 else old_response
        new_preview = updated_response[:50] + "..." if len(updated_response) > 50 else updated_response
        log_employee_audit(
            employee_id=employee_id,
            action="edit_ticket_response",
            details=f"Successfully edited response {response_id} on ticket {ticket_id} ('{ticket_subject}'): changed from '{old_preview}' to '{new_preview}'"
        )

        cursor.close()
        logging.debug("[EDIT_RESPONSE] Cursor closed")
        conn.close()
        logging.debug("[EDIT_RESPONSE] Database connection closed")

        return jsonify({'message': 'Response updated successfully'})

    except Exception as e:
        logging.error(f"[EDIT_RESPONSE] Error updating response: {e}")
        logging.error(traceback.format_exc())
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during ticket response edit for response {response_id}: {str(e)}",
            severity="High"
        )
        
        if conn:
            try:
                conn.rollback()
                logging.debug("[EDIT_RESPONSE] Rolled back transaction due to error")
            except Exception as rollback_err:
                logging.error(f"[EDIT_RESPONSE] Error during rollback: {rollback_err}")
        return jsonify({'error': 'Failed to update response'}), 500
    
# Route for submitting ticket response
@employee_bp.route('/submit_ticket_response', methods=['POST'])
@employee_jwt_required()
def submit_ticket_response():
    try:
        employee_id = g.employee_id
        employee_role = g.employee_role

        if not employee_id:
            logging.warning("Unauthorized access to /submit_ticket_response")
            log_employee_incident(
                employee_id=None,
                description="Unauthorized ticket response submission attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json
        ticket_id = data.get('ticket_id')
        response = data.get('response')
       
        if not ticket_id or not response:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Ticket response submission attempted with missing data - ticket_id: {bool(ticket_id)}, response: {bool(response)}",
                severity="Low"
            )
            return jsonify({'error': 'Missing ticket_id or response'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # First verify the ticket exists and get details for logging
        cursor.execute("""
            SELECT t.ticket_id, t.employee_id, t.subject, t.status
            FROM tickets t
            WHERE t.ticket_id = %s
        """, (ticket_id,))
        
        ticket_info = cursor.fetchone()
        
        if not ticket_info:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to respond to non-existent ticket {ticket_id}",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Ticket not found'}), 404

        ticket_id_db, ticket_owner_id, ticket_subject, ticket_status = ticket_info

        # Check if employee has permission to respond to this ticket
        # Generally, ticket owner and support staff can respond
        if ticket_owner_id != employee_id and employee_role not in ['admin', 'super_admin']:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to respond to ticket {ticket_id} ('{ticket_subject}') that doesn't belong to them (owner: {ticket_owner_id})",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Access denied: Cannot respond to this ticket'}), 403

        # Format the 'responded_by' string
        if employee_role == 'super_admin':
            responded_by = f"Super Admin ID: {employee_id}"
        elif employee_role == 'admin':
            responded_by = f"Admin ID: {employee_id}"
        else:
            responded_by = f"Employee ID: {employee_id}"

        cursor.execute("""
            INSERT INTO ticket_responses (ticket_id, employee_id, response, responded_by, responded_at)
            VALUES (%s, %s, %s, %s, NOW())
            RETURNING response_id
        """, (ticket_id, employee_id, response, responded_by))

        response_id = cursor.fetchone()[0] if cursor.rowcount > 0 else None
        conn.commit()

        # Log successful audit trail
        response_preview = response[:100] + "..." if len(response) > 100 else response
        log_employee_audit(
            employee_id=employee_id,
            action="submit_ticket_response",
            details=f"Successfully submitted response (ID: {response_id}) to ticket {ticket_id} ('{ticket_subject}') as {employee_role}: '{response_preview}'"
        )

        cursor.close()
        conn.close()

        return jsonify({'message': 'Response submitted successfully'}), 201

    except Exception as e:
        logging.error(f"Error submitting ticket response: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during ticket response submission: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500

@employee_bp.route('/employee/badges', methods=['GET'])
@employee_jwt_required()
def get_employee_badges():
    employee_id = g.employee_id  # Retrieved from JWT
    logging.debug(f"[BADGES] Access attempt by employee_id: {employee_id}")

    if not employee_id:
        logging.warning("[BADGES] Unauthorized access attempt — no valid token.")
        log_employee_incident(
            employee_id=None,
            description="Unauthorized employee badges access attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get the team_id for the employee (if any)
        cursor.execute("SELECT team_id FROM employees WHERE employee_id = %s", (employee_id,))
        result = cursor.fetchone()
        team_id = result[0] if result else None

        if not result:
            log_employee_incident(
                employee_id=employee_id,
                description="Employee badges requested but employee not found in database",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Employee not found'}), 404

        # Get badges assigned directly to employee
        query_employee = """
            SELECT b.badge_id, b.name, b.description, b.icon_url, ba.assigned_at, NULL as source
            FROM badge_assignments ba
            JOIN badges b ON ba.badge_id = b.badge_id
            WHERE ba.employee_id = %s
            ORDER BY ba.assigned_at DESC
        """
        cursor.execute(query_employee, (employee_id,))
        badges_employee = cursor.fetchall()

        badges = [{
            'badge_id': badge[0],
            'title': badge[1],
            'description': badge[2],
            'icon_url': badge[3],
            'assigned_at': badge[4].strftime('%Y-%m-%d'),
            'source': 'employee'
        } for badge in badges_employee]

        employee_badge_count = len(badges)

        # If employee has a team, fetch team badges
        team_badge_count = 0
        if team_id:
            query_team = """
                SELECT b.badge_id, b.name, b.description, b.icon_url, ba.assigned_at, %s as source
                FROM badge_assignments ba
                JOIN badges b ON ba.badge_id = b.badge_id
                WHERE ba.team_id = %s
                ORDER BY ba.assigned_at DESC
            """
            cursor.execute(query_team, (team_id, team_id))
            badges_team = cursor.fetchall()

            team_badges = [{
                'badge_id': badge[0],
                'title': badge[1],
                'description': badge[2],
                'icon_url': badge[3],
                'assigned_at': badge[4].strftime('%Y-%m-%d'),
                'source': 'team'
            } for badge in badges_team]
            
            badges += team_badges
            team_badge_count = len(team_badges)

        # Optional: Remove duplicates (same badge assigned via both team and employee)
        # Use badge_id + source to keep both if both assignments are needed
        seen = set()
        deduped_badges = []
        duplicate_count = 0
        
        for badge in badges:
            key = (badge['badge_id'], badge['source'])
            if key not in seen:
                deduped_badges.append(badge)
                seen.add(key)
            else:
                duplicate_count += 1

        # Log successful audit trail
        audit_details = f"Retrieved {len(deduped_badges)} badges: {employee_badge_count} individual, {team_badge_count} team-based"
        if team_id:
            audit_details += f" (team_id: {team_id})"
        if duplicate_count > 0:
            audit_details += f", removed {duplicate_count} duplicates"
            
        log_employee_audit(
            employee_id=employee_id,
            action="get_employee_badges",
            details=audit_details
        )

        return jsonify(deduped_badges)

    except Exception as e:
        logging.error(f"[BADGES] Error fetching badges: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error while fetching employee badges: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()