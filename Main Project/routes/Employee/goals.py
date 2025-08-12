
# Route for updating progress percentage and adding notes for goal progress
from datetime import datetime
import logging
from flask import g, jsonify, render_template, request, url_for
from extensions import csrf
from routes.Auth.token import employee_jwt_required
from routes.Auth.utils import get_db_connection
from routes.Auth.config import generate_action_plan, generate_goal_evaluation
from . import employee_bp
from routes.Auth.audit import log_employee_incident,log_employee_audit

@employee_bp.route('/goals', methods=['GET'])
def goals_shell():
    return render_template('Employee/goals.html')  # No auth here; handled on the JS/API side

@csrf.exempt
@employee_bp.route('/submit_goal_progress', methods=['POST'])
@employee_jwt_required()
def submit_goal_progress():
    logging.info("Received request to submit goal progress.")

    try:
        employee_id_from_jwt = g.employee_id
        
        if not employee_id_from_jwt:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized goal progress submission attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.get_json()
        logging.info(f"Received data: {data}")

        goal_id = str(data.get('goal_id', '')).strip()
        employee_id = str(data.get('employee_id', '')).strip()
        team_id = str(data.get('team_id', '')).strip()
        progress_percentage = str(data.get('progress_percentage', '')).strip()
        note = str(data.get('note', '')).strip()

        team_id = None if team_id.lower() == 'none' or team_id == '' else team_id

        if not goal_id.isdigit() or not employee_id.isdigit() or (team_id and not team_id.isdigit()):
            logging.warning(f"Invalid input values detected: goal_id={goal_id}, employee_id={employee_id}, team_id={team_id}")
            log_employee_incident(
                employee_id=employee_id_from_jwt,
                description=f"Goal progress submission attempted with invalid input values: goal_id={goal_id}, employee_id={employee_id}, team_id={team_id}",
                severity="Low"
            )
            return jsonify({'error': 'Invalid input values'}), 400

        goal_id = int(goal_id)
        employee_id = int(employee_id)
        team_id = int(team_id) if team_id else None

        # Verify the employee_id in the request matches the JWT employee_id
        if employee_id != employee_id_from_jwt:
            log_employee_incident(
                employee_id=employee_id_from_jwt,
                description=f"Goal progress submission attempted for different employee: JWT employee_id={employee_id_from_jwt}, request employee_id={employee_id}",
                severity="High"
            )
            return jsonify({'error': 'Unauthorized: Cannot submit progress for another employee'}), 403

        if progress_percentage and not progress_percentage.isdigit():
            logging.warning(f"Invalid progress percentage detected: {progress_percentage}")
            log_employee_incident(
                employee_id=employee_id_from_jwt,
                description=f"Goal progress submission attempted with invalid progress percentage: '{progress_percentage}'",
                severity="Low"
            )
            return jsonify({'error': 'Invalid progress percentage'}), 400
        progress_percentage = int(progress_percentage) if progress_percentage else None

        if progress_percentage is not None and (progress_percentage < 0 or progress_percentage > 100):
            log_employee_incident(
                employee_id=employee_id_from_jwt,
                description=f"Goal progress submission attempted with out-of-range progress percentage: {progress_percentage}",
                severity="Low"
            )
            return jsonify({'error': 'Progress percentage must be between 0 and 100'}), 400

        logging.info(f"Validated inputs - goal_id: {goal_id}, team_id: {team_id}, employee_id: {employee_id}, progress_percentage: {progress_percentage}")

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # First verify the goal exists and employee has access to it
            cursor.execute("""
                SELECT g.goal_name, g.status, g.employee_id, g.team_id, t.team_name,
                       (SELECT team_id FROM employees WHERE employee_id = %s) as employee_team_id
                FROM goals g
                LEFT JOIN teams t ON g.team_id = t.team_id
                WHERE g.goal_id = %s
            """, (employee_id_from_jwt, goal_id))
            
            goal_info = cursor.fetchone()
            
            if not goal_info:
                log_employee_incident(
                    employee_id=employee_id_from_jwt,
                    description=f"Employee attempted to submit progress for non-existent goal {goal_id}",
                    severity="Medium"
                )
                cursor.close()
                conn.close()
                return jsonify({'error': 'Goal not found'}), 404

            goal_name, current_status, goal_employee_id, goal_team_id, team_name, employee_team_id = goal_info

            # Check if employee has access to this goal
            has_access = (goal_employee_id == employee_id_from_jwt) or (goal_team_id == employee_team_id)
            
            if not has_access:
                log_employee_incident(
                    employee_id=employee_id_from_jwt,
                    description=f"Employee attempted to submit progress for unauthorized goal {goal_id} ('{goal_name}') - goal_employee_id: {goal_employee_id}, goal_team_id: {goal_team_id}, employee_team_id: {employee_team_id}",
                    severity="High"
                )
                cursor.close()
                conn.close()
                return jsonify({'error': 'Access denied to this goal'}), 403

            percentage_id = None
            if progress_percentage is not None:
                cursor.execute("SELECT progress_percentage_id FROM goal_progress_percentage WHERE goal_id = %s", (goal_id,))
                result = cursor.fetchone()

                if result:
                    percentage_id = result[0]
                    cursor.execute("""
                        UPDATE goal_progress_percentage 
                        SET progress_percentage = %s, percentage_updated_at = NOW() 
                        WHERE goal_id = %s
                    """, (progress_percentage, goal_id))
                else:
                    cursor.execute("""
                        INSERT INTO goal_progress_percentage (progress_percentage, percentage_created_at, percentage_updated_at, employee_id, team_id, goal_id)
                        VALUES (%s, NOW(), NOW(), %s, %s, %s) RETURNING progress_percentage_id
                    """, (progress_percentage, employee_id, team_id, goal_id))
                    percentage_id = cursor.fetchone()[0]

            note_id = None
            if note:
                cursor.execute("""
                    INSERT INTO goal_progress_notes (note_description, notes_created_at, notes_updated_at, goal_id, employee_id, team_id)
                    VALUES (%s, NOW(), NOW(), %s, %s, %s) RETURNING note_id
                """, (note, goal_id, employee_id, team_id))
                note_id = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO goal_progress (goal_id, employee_id, team_id, progress_percentage_id, note_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (goal_id, employee_id, team_id, percentage_id, note_id if note else None))

            # Only update status if progress_percentage is provided
            status = None
            if progress_percentage is not None:
                if progress_percentage == 0:
                    status = "Not Yet Started"
                elif 0 < progress_percentage < 100:
                    status = "Pending"
                else:
                    status = "Completed"

                cursor.execute("""
                    UPDATE goals SET status = %s WHERE goal_id = %s
                """, (status, goal_id))
                logging.info(f"Updated goal status to '{status}' for goal_id {goal_id}")

            goal_evaluation_response = generate_goal_evaluation(goal_id)
            action_plan_response = generate_action_plan(goal_id)

            goal_evaluation = goal_evaluation_response if isinstance(goal_evaluation_response, dict) else None
            action_plan = action_plan_response if isinstance(action_plan_response, dict) else None

            conn.commit()

            # Log successful audit trail
            progress_info = f"{progress_percentage}%" if progress_percentage is not None else "no percentage update"
            note_info = f" with note: '{note[:100]}...'" if len(note) > 100 else f" with note: '{note}'" if note else ""
            team_info = f" (team: {team_name})" if team_name else ""
            status_info = f", status updated to '{status}'" if status else ""
            
            log_employee_audit(
                employee_id=employee_id_from_jwt,
                action="submit_goal_progress",
                details=f"Successfully submitted progress for goal {goal_id} ('{goal_name}'){team_info}: {progress_info}{note_info}{status_info}"
            )

            return jsonify({
                'success': True,
                'message': 'Progress updated successfully',
                'goal_id': goal_id,
                'progress_percentage': progress_percentage,
                'status': status,
                'goal_evaluation': goal_evaluation,
                'action_plan': action_plan,
                'note_description': note,
                'note_created_at': datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')
            }), 200

        except Exception as e:
            conn.rollback()
            logging.error(f"Error while updating progress: {str(e)}")
            
            # Log incident for system error
            log_employee_incident(
                employee_id=employee_id_from_jwt,
                description=f"System error during goal progress submission for goal {goal_id}: {str(e)}",
                severity="High"
            )
            
            return jsonify({'error': str(e)}), 500

        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during goal progress submission: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Invalid request payload'}), 400
        
@employee_bp.route('/api/goals', methods=['GET'])
@employee_jwt_required()
def api_goals():
    employee_id = g.employee_id
    logging.debug(f"Fetching goal data for employee_id: {employee_id}")

    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized goals API access attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get employee's team_id for logging
        cursor.execute("SELECT team_id FROM employees WHERE employee_id = %s", (employee_id,))
        employee_team_info = cursor.fetchone()
        employee_team_id = employee_team_info[0] if employee_team_info else None

        # Fetch all goals assigned to the employee or their team
        cursor.execute("""
        SELECT g.goal_id, g.goal_name, g.description, g.specific_goal, g.measurable_goal, g.achievable_goal,
               g.relevant_goal, g.time_bound_goal, g.status, g.employee_id, g.team_id,
               t.team_name,
               gpp.progress_percentage, gpp.percentage_updated_at,
               ge.final_score, ge.lessons_learned, ge.action_plan, ge.course
        FROM goals g
        LEFT JOIN goal_progress_percentage gpp ON g.goal_id = gpp.goal_id
        LEFT JOIN goal_evaluations ge ON g.goal_id = ge.goal_id
        LEFT JOIN teams t ON t.team_id = g.team_id
        WHERE (g.employee_id = %s OR (g.team_id IS NOT NULL AND g.team_id = (SELECT team_id FROM employees WHERE employee_id = %s)))
        """, (employee_id, employee_id))
        goal_rows = cursor.fetchall()

        if not goal_rows:
            # Log audit for no goals found
            log_employee_audit(
                employee_id=employee_id,
                action="view_goals",
                details=f"Retrieved goals: no goals found (employee_team_id: {employee_team_id})"
            )
            cursor.close()
            conn.close()
            return jsonify({'goals': []})

        # Collect goal_ids for notes/feedback lookups
        goal_ids = [row[0] for row in goal_rows]

        # Fetch all notes for these goals
        cursor.execute("""
            SELECT goal_id, note_description, notes_created_at, notes_updated_at
            FROM goal_progress_notes
            WHERE goal_id = ANY(%s)
            ORDER BY notes_created_at DESC
        """, (goal_ids,))
        notes_rows = cursor.fetchall()
        notes_by_goal = {}
        for row in notes_rows:
            notes_by_goal.setdefault(row[0], []).append({
                'note_description': row[1],
                'created_at': row[2].isoformat() if hasattr(row[2], "isoformat") else row[2],
                'updated_at': row[3].isoformat() if hasattr(row[3], "isoformat") else row[3]
            })

        # Fetch all feedback for these goals
        cursor.execute("""
            SELECT goal_id, feedback_description, feedback_created_at, feedback_updated_at
            FROM goal_progress_feedback
            WHERE goal_id = ANY(%s)
            ORDER BY feedback_created_at DESC
        """, (goal_ids,))
        feedback_rows = cursor.fetchall()
        feedback_by_goal = {}
        for row in feedback_rows:
            feedback_by_goal.setdefault(row[0], []).append({
                'feedback_description': row[1],
                'created_at': row[2].isoformat() if hasattr(row[2], "isoformat") else row[2],
                'updated_at': row[3].isoformat() if hasattr(row[3], "isoformat") else row[3]
            })

        # Build response and analyze data for logging
        goals = []
        individual_goals = 0
        team_goals = 0
        status_counts = {}
        total_notes = 0
        total_feedback = 0
        
        for row in goal_rows:
            goal_id = row[0]
            goal_employee_id = row[9]
            goal_team_id = row[10]
            goal_status = row[8] or 'Unknown'
            
            # Count goal types
            if goal_employee_id == employee_id:
                individual_goals += 1
            elif goal_team_id == employee_team_id:
                team_goals += 1
                
            # Count statuses
            status_counts[goal_status] = status_counts.get(goal_status, 0) + 1
            
            # Count notes and feedback
            goal_notes = notes_by_goal.get(goal_id, [])
            goal_feedback = feedback_by_goal.get(goal_id, [])
            total_notes += len(goal_notes)
            total_feedback += len(goal_feedback)
            
            goals.append({
                'goal_id': goal_id,
                'goal_name': row[1],
                'description': row[2],
                'specific_goal': row[3],
                'measurable_goal': row[4],
                'achievable_goal': row[5],
                'relevant_goal': row[6],
                'time_bound_goal': row[7],
                'status': goal_status,
                'employee_id': goal_employee_id,
                'team_id': goal_team_id,
                'team_name': row[11],
                'progress_percentage': row[12],
                'progress_updated_at': row[13],
                'final_score': row[14],
                'lessons_learned': row[15],
                'action_plan': row[16],
                'course': row[17],
                'notes': goal_notes,
                'feedback': goal_feedback
            })

        # Log successful audit trail
        status_summary = ', '.join([f"{count} {status}" for status, count in status_counts.items()])
        log_employee_audit(
            employee_id=employee_id,
            action="view_goals",
            details=f"Retrieved {len(goals)} goals ({individual_goals} individual, {team_goals} team) with {total_notes} notes and {total_feedback} feedback entries | Status: {status_summary} (employee_team_id: {employee_team_id})"
        )

        cursor.close()
        conn.close()
        logging.debug("Database connection closed")

        return jsonify({'goals': goals})

    except Exception as e:
        logging.error(f"Error in /api/goals: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error while fetching goals data: {str(e)}",
            severity="High"
        )
        
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        
        return jsonify({'error': 'Internal server error'}), 500