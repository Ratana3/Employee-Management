#route for displaying performance reviews
from datetime import datetime
import logging
from flask import g, jsonify, render_template, request
import requests
from routes.Auth.config import GITHUB_REPO, GITHUB_TOKEN
from routes.Auth.token import employee_jwt_required
from routes.Auth.utils import get_db_connection
from extensions import csrf
from . import employee_bp
from routes.Auth.audit import log_employee_incident,log_employee_audit

@employee_bp.route('/workandproductivity', methods=['GET'])
def work_and_productivity():
    return render_template('Employee/WorkAndProductivity.html')

@employee_bp.route('/performance_reviews', methods=['GET'])
@employee_jwt_required()
@csrf.exempt
def view_performance_reviews():
    employee_id = g.employee_id
    role = g.employee_role

    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized performance reviews access attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT review_date, reviewer, rating, feedback
            FROM performance_reviews
            WHERE employee_id = %s
            ORDER BY review_date DESC
        """, (employee_id,))
        reviews = cursor.fetchall()

        # Analytics for logging
        total_reviews = len(reviews)
        ratings = []
        numeric_ratings = []
        reviewers = set()
        recent_reviews = 0
        rating_distribution = {}
        
        # Rating conversion mapping for string ratings
        rating_to_numeric = {
            'excellent': 5,
            'very good': 4.5,
            'good': 4,
            'satisfactory': 3,
            'fair': 2.5,
            'needs improvement': 2,
            'poor': 1,
            'unsatisfactory': 1
        }
        
        current_date = datetime.now().date()
        
        for review in reviews:
            review_date, reviewer, rating, feedback = review
            
            if rating is not None:
                ratings.append(rating)
                rating_distribution[rating] = rating_distribution.get(rating, 0) + 1
                
                # Try to convert rating to numeric for average calculation
                if isinstance(rating, (int, float)):
                    # Already numeric
                    numeric_ratings.append(float(rating))
                elif isinstance(rating, str):
                    # Try to convert string rating to numeric
                    rating_lower = rating.lower().strip()
                    if rating_lower in rating_to_numeric:
                        numeric_ratings.append(rating_to_numeric[rating_lower])
                    else:
                        # Try to parse as number if it's a string number
                        try:
                            numeric_ratings.append(float(rating))
                        except (ValueError, TypeError):
                            # Skip non-convertible ratings
                            print(f"Warning: Could not convert rating '{rating}' to numeric value")
            
            if reviewer:
                reviewers.add(reviewer)
            
            if review_date and (current_date - review_date).days <= 365:  # Within last year
                recent_reviews += 1

        results = [{
            'review_date': str(row[0]),
            'reviewer': row[1],
            'rating': row[2],
            'feedback': row[3]
        } for row in reviews]

        # Log successful audit trail with proper rating handling
        if numeric_ratings:
            avg_rating = sum(numeric_ratings) / len(numeric_ratings)
            avg_rating_text = f"avg rating {avg_rating:.1f}"
        else:
            avg_rating_text = "no numeric ratings available"
        
        rating_summary = ', '.join([f"{count} rated {rating}" for rating, count in sorted(rating_distribution.items())]) if rating_distribution else "no ratings"
        reviewers_summary = f"{len(reviewers)} different reviewers" if reviewers else "no reviewers"
        
        log_employee_audit(
            employee_id=employee_id,
            action="view_performance_reviews",
            details=f"Retrieved {total_reviews} performance reviews: {avg_rating_text}, {recent_reviews} recent (last year) | Ratings: {rating_summary} | {reviewers_summary}"
        )

        cursor.close()
        conn.close()
        return jsonify(results), 200

    except Exception as e:
        logging.error("Error fetching performance reviews", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error while fetching performance reviews: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
            
# GET route to fetch all tasks and their parts for the logged-in employee
@employee_bp.route('/assigned_tasks', methods=['GET'])
@employee_jwt_required()
@csrf.exempt
def get_assigned_tasks():
    import logging
    import time
    from datetime import datetime
    
    # Start timing for performance analysis
    start_time = time.time()
    
    employee_id = g.employee_id
    role = g.employee_role
    request_id = f"req_{int(time.time())}_{employee_id}"  # Generate unique request ID for tracing

    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized assigned tasks access attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        logging.info(f"[ASSIGNED_TASKS][{request_id}] Request started at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        logging.info(f"[ASSIGNED_TASKS][{request_id}] Fetching for employee_id: {employee_id}, role: {role}")

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Log employee details for context
        cursor.execute("""
            SELECT first_name, last_name, email, team_id FROM employees WHERE employee_id = %s
        """, (employee_id,))
        emp_details = cursor.fetchone()
        
        # Initialize team_ids list and track sources
        team_ids = []
        team_sources = {}
        
        # FIRST SOURCE: Primary team from employees.team_id
        primary_team_id = None
        if emp_details:
            logging.info(f"[ASSIGNED_TASKS][{request_id}] Employee: {emp_details[0]} {emp_details[1]} ({emp_details[2]}), employees.team_id: {emp_details[3]}")
            primary_team_id = emp_details[3]
            
            if primary_team_id is not None:
                team_ids.append(primary_team_id)
                team_sources[primary_team_id] = "primary_team"
                logging.info(f"[ASSIGNED_TASKS][{request_id}] Added primary team_id={primary_team_id} from employees table")
        else:
            logging.warning(f"[ASSIGNED_TASKS][{request_id}] Could not find employee record for employee_id={employee_id}")

        # SECOND SOURCE: Get additional teams from team_members table
        logging.info(f"[ASSIGNED_TASKS][{request_id}] Fetching team_ids from team_members table")
        cursor.execute("""
            SELECT tm.team_id, t.team_name, tm.role 
            FROM team_members tm
            LEFT JOIN teams t ON tm.team_id = t.team_id
            WHERE tm.employee_id = %s
        """, (employee_id,))
        team_rows = cursor.fetchall()
        
        if team_rows:
            # Process teams from team_members
            for row in team_rows:
                team_id = row[0]
                team_name = row[1]
                member_role = row[2]
                
                if team_id not in team_ids:
                    team_ids.append(team_id)
                    team_sources[team_id] = "team_members"
                    logging.info(f"[ASSIGNED_TASKS][{request_id}] Added team_id={team_id} ({team_name}) from team_members, role: {member_role or 'Not specified'}")
                else:
                    # Team already in the list (from primary team)
                    team_sources[team_id] += "+team_members"
                    logging.info(f"[ASSIGNED_TASKS][{request_id}] Team {team_id} ({team_name}) already in list from primary team assignment")
        else:
            logging.info(f"[ASSIGNED_TASKS][{request_id}] Employee not found in any team_members records")
        
        # Log the final combined team membership
        if team_ids:
            logging.info(f"[ASSIGNED_TASKS][{request_id}] Final combined team membership: {len(team_ids)} teams - {team_ids}")
            for team_id in team_ids:
                logging.info(f"[ASSIGNED_TASKS][{request_id}] Team {team_id} source: {team_sources.get(team_id)}")
            
            # Get team names for better logging
            format_strings = ','.join(['%s'] * len(team_ids))
            cursor.execute(f"SELECT team_id, team_name FROM teams WHERE team_id IN ({format_strings})", tuple(team_ids))
            team_names = {row[0]: row[1] for row in cursor.fetchall()}
            
            team_details = [f"Team {t_id} ({team_names.get(t_id, 'Unknown')})" for t_id in team_ids]
            logging.info(f"[ASSIGNED_TASKS][{request_id}] Team details: {', '.join(team_details)}")
        else:
            logging.warning(f"[ASSIGNED_TASKS][{request_id}] Employee is not associated with any team")
        
        # Check for discrepancy for synchronization recommendation
        if primary_team_id and team_rows and primary_team_id not in [row[0] for row in team_rows]:
            logging.warning(f"[ASSIGNED_TASKS][{request_id}] SYNCHRONIZATION NEEDED: Employee has primary team_id={primary_team_id} but this team is not in team_members table")
        
        # Record timing for team lookup
        team_lookup_time = time.time() - start_time
        logging.debug(f"[ASSIGNED_TASKS][{request_id}] Team lookup completed in {team_lookup_time:.4f} seconds")

        # Fetch tasks assigned directly to employee
        logging.info(f"[ASSIGNED_TASKS][{request_id}] Fetching tasks directly assigned to employee_id={employee_id}")
        cursor.execute("""
            SELECT t.task_id, t.task_name, t.description, t.assigned_date, t.due_date, 
                   t.progress, t.status, 
                   p.project_id, p.project_name, p.description, p.start_date, p.end_date,
                   t.team_id
            FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.project_id
            WHERE t.employee_id = %s
        """, (employee_id,))
        employee_tasks = cursor.fetchall()
        
        # Detailed employee tasks info
        if employee_tasks:
            task_ids = [task[0] for task in employee_tasks]
            logging.info(f"[ASSIGNED_TASKS][{request_id}] Found {len(employee_tasks)} direct tasks: {task_ids}")
            for idx, task in enumerate(employee_tasks):
                logging.debug(f"[ASSIGNED_TASKS][{request_id}] Direct task {idx+1}: ID={task[0]}, Name='{task[1]}', Status={task[6]}, Progress={task[5]}%, Team={task[12]}")
        else:
            logging.info(f"[ASSIGNED_TASKS][{request_id}] No tasks directly assigned to employee")
        
        # Record timing for direct tasks lookup
        direct_tasks_time = time.time() - start_time - team_lookup_time
        logging.debug(f"[ASSIGNED_TASKS][{request_id}] Direct tasks lookup completed in {direct_tasks_time:.4f} seconds")

        # Fetch tasks assigned to the employee's team(s)
        team_tasks = []
        if team_ids:
            format_strings = ','.join(['%s'] * len(team_ids))
            logging.info(f"[ASSIGNED_TASKS][{request_id}] Fetching tasks assigned to teams: {team_ids}")
            team_query = f"""
                SELECT t.task_id, t.task_name, t.description, t.assigned_date, t.due_date, 
                       t.progress, t.status, 
                       p.project_id, p.project_name, p.description, p.start_date, p.end_date,
                       t.team_id, t.employee_id
                FROM tasks t
                LEFT JOIN projects p ON t.project_id = p.project_id
                WHERE t.team_id IN ({format_strings})
            """
            logging.debug(f"[ASSIGNED_TASKS][{request_id}] Team tasks query: {team_query} with params {tuple(team_ids)}")
            
            cursor.execute(team_query, tuple(team_ids))
            team_tasks = cursor.fetchall()
            
            # Detailed team tasks info
            if team_tasks:
                task_ids = [task[0] for task in team_tasks]
                teams_with_tasks = set([task[12] for task in team_tasks])
                logging.info(f"[ASSIGNED_TASKS][{request_id}] Found {len(team_tasks)} team tasks across {len(teams_with_tasks)} teams: {task_ids}")
                
                # Group tasks by team for better debugging
                team_task_counts = {}
                for task in team_tasks:
                    team_id = task[12]
                    if team_id not in team_task_counts:
                        team_task_counts[team_id] = 0
                    team_task_counts[team_id] += 1
                
                for team_id, count in team_task_counts.items():
                    team_source = team_sources.get(team_id, "unknown")
                    logging.info(f"[ASSIGNED_TASKS][{request_id}] Team {team_id} (source: {team_source}) has {count} tasks")
                
                for idx, task in enumerate(team_tasks):
                    team_id = task[12]
                    team_source = team_sources.get(team_id, "unknown")
                    logging.debug(f"[ASSIGNED_TASKS][{request_id}] Team task {idx+1}: ID={task[0]}, Name='{task[1]}', Status={task[6]}, " +
                                 f"Progress={task[5]}%, Team={team_id} (source: {team_source}), Direct Assignee={task[13] or 'None'}")
            else:
                logging.info(f"[ASSIGNED_TASKS][{request_id}] No tasks assigned to any of employee's teams")
        else:
            logging.info(f"[ASSIGNED_TASKS][{request_id}] Employee is not part of any team. No team tasks to fetch.")
        
        # Record timing for team tasks lookup
        team_tasks_time = time.time() - start_time - team_lookup_time - direct_tasks_time
        logging.debug(f"[ASSIGNED_TASKS][{request_id}] Team tasks lookup completed in {team_tasks_time:.4f} seconds")

        # Combine and deduplicate tasks (in case employee is assigned both directly and via team)
        all_tasks_dict = {}
        direct_count = 0
        team_count = 0
        duplicate_count = 0
        
        # First add direct tasks
        for task in employee_tasks:
            task_id = task[0]
            all_tasks_dict[task_id] = task
            direct_count += 1
        
        # Then add team tasks, tracking duplicates
        for task in team_tasks:
            task_id = task[0]
            if task_id in all_tasks_dict:
                duplicate_count += 1
                team_id = task[12]
                team_source = team_sources.get(team_id, "unknown")
                logging.debug(f"[ASSIGNED_TASKS][{request_id}] Task {task_id} '{task[1]}' is assigned both directly and via team {team_id} (source: {team_source})")
            else:
                all_tasks_dict[task_id] = task
                team_count += 1
        
        logging.info(f"[ASSIGNED_TASKS][{request_id}] Task breakdown: {direct_count} direct tasks, {team_count} team-only tasks, {duplicate_count} tasks with both assignments")
        logging.info(f"[ASSIGNED_TASKS][{request_id}] Total unique tasks after deduplication: {len(all_tasks_dict)}")
        
        # Record timing for deduplication
        dedup_time = time.time() - start_time - team_lookup_time - direct_tasks_time - team_tasks_time
        logging.debug(f"[ASSIGNED_TASKS][{request_id}] Deduplication completed in {dedup_time:.4f} seconds")

        # Fetch parts for each task and analyze task data
        all_tasks = []
        tasks_with_parts = 0
        total_parts = 0
        status_counts = {}
        overdue_tasks = 0
        high_progress_tasks = 0
        projects = set()
        avg_progress = 0
        
        current_date = datetime.now().date()
        
        for task in all_tasks_dict.values():
            task_id = task[0]
            task_status = task[6]
            task_progress = task[5] or 0
            due_date = task[4]
            project_id = task[7]
            
            # Analytics tracking
            status_counts[task_status] = status_counts.get(task_status, 0) + 1
            avg_progress += task_progress
            
            if task_progress >= 80:
                high_progress_tasks += 1
            
            if project_id:
                projects.add(project_id)
            
            if due_date:
                if hasattr(due_date, 'date'):
                    due_date_obj = due_date.date()
                elif isinstance(due_date, str):
                    try:
                        due_date_obj = datetime.strptime(due_date.split()[0], '%Y-%m-%d').date()
                    except:
                        due_date_obj = None
                else:
                    due_date_obj = due_date
                
                if due_date_obj and due_date_obj < current_date and task_status != 'Completed':
                    overdue_tasks += 1
            
            logging.debug(f"[ASSIGNED_TASKS][{request_id}] Fetching parts for task_id: {task_id}")
            
            cursor.execute("""
                SELECT part_id, part_name, part_percentage, completed
                FROM task_parts
                WHERE task_id = %s
            """, (task_id,))
            parts = cursor.fetchall()
            
            if parts:
                tasks_with_parts += 1
                total_parts += len(parts)
                logging.debug(f"[ASSIGNED_TASKS][{request_id}] Found {len(parts)} parts for task_id: {task_id}")
                part_details = [f"Part {p[0]} ({p[1]}): {p[2]}%, Completed: {p[3]}" for p in parts]
                logging.debug(f"[ASSIGNED_TASKS][{request_id}] Task {task_id} parts: {', '.join(part_details)}")
            else:
                logging.debug(f"[ASSIGNED_TASKS][{request_id}] No parts found for task_id: {task_id}")
            
            # Add source information for this task (direct, team, or both)
            task_source = "direct"
            team_id = task[12]
            if task in team_tasks:
                task_source = "team" if task not in employee_tasks else "both"
                
            # Build the task object with parts
            task_obj = {
                'task_id': task_id,
                'task_name': task[1],
                'description': task[2],
                'assigned_date': str(task[3]),
                'due_date': str(task[4]),
                'progress': task_progress,
                'status': task_status,
                'project': {
                    'project_id': task[7],
                    'project_name': task[8],
                    'description': task[9],
                    'start_date': str(task[10]) if task[10] else None,
                    'end_date': str(task[11]) if task[11] else None,
                } if task[7] else None,
                'team_id': team_id,
                'assignment_source': task_source,
                'parts': [
                    {
                        'part_id': p[0],
                        'part_name': p[1],
                        'part_percentage': p[2],
                        'completed': p[3]
                    } for p in parts
                ]
            }
            
            # Include team membership source if assigned via team
            if team_id and team_id in team_sources:
                task_obj['team_membership_source'] = team_sources[team_id]
                
            all_tasks.append(task_obj)
        
        logging.info(f"[ASSIGNED_TASKS][{request_id}] {tasks_with_parts} tasks have parts, with {total_parts} total parts")
        
        # Record timing for parts lookup
        parts_time = time.time() - start_time - team_lookup_time - direct_tasks_time - team_tasks_time - dedup_time
        logging.debug(f"[ASSIGNED_TASKS][{request_id}] Parts lookup completed in {parts_time:.4f} seconds")

        # Total execution time
        total_time = time.time() - start_time
        logging.info(f"[ASSIGNED_TASKS][{request_id}] Total execution time: {total_time:.4f} seconds")
        logging.info(f"[ASSIGNED_TASKS][{request_id}] Time breakdown: Teams {team_lookup_time:.4f}s, Direct tasks {direct_tasks_time:.4f}s, " +
                   f"Team tasks {team_tasks_time:.4f}s, Deduplication {dedup_time:.4f}s, Parts {parts_time:.4f}s")
        
        # Log successful audit trail
        avg_progress_calc = avg_progress / len(all_tasks_dict) if all_tasks_dict else 0
        status_summary = ', '.join([f"{count} {status}" for status, count in status_counts.items()]) if status_counts else "none"
        team_summary = ', '.join([f"Team {tid} ({team_sources.get(tid, 'unknown')})" for tid in team_ids]) if team_ids else "no teams"
        
        log_employee_audit(
            employee_id=employee_id,
            action="view_assigned_tasks",
            details=f"Retrieved {len(all_tasks_dict)} tasks ({direct_count} direct, {team_count} team-only, {duplicate_count} duplicates) from {len(projects)} projects: avg progress {avg_progress_calc:.1f}%, {high_progress_tasks} high progress (≥80%), {overdue_tasks} overdue | Status: {status_summary} | Teams: {team_summary} | {tasks_with_parts} tasks with {total_parts} parts | Query time: {total_time:.3f}s"
        )
        
        logging.info(f"[ASSIGNED_TASKS][{request_id}] Returning {len(all_tasks)} tasks in response")
        cursor.close()
        conn.close()
        return jsonify(all_tasks), 200

    except Exception as e:
        # Calculate how far we got before the error
        error_time = time.time() - start_time
        logging.error(f"[ASSIGNED_TASKS][{request_id}][ERROR] Error fetching tasks after {error_time:.4f} seconds: {e}", exc_info=True)
        
        # Try to get stack trace and more detailed error info
        import traceback
        error_details = traceback.format_exc()
        logging.error(f"[ASSIGNED_TASKS][{request_id}][ERROR] Stack trace: {error_details}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error while fetching assigned tasks (request_id: {request_id}): {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error', 'request_id': request_id}), 500
        
    finally:
        try:
            if 'cursor' in locals() and cursor:
                cursor.close()
                logging.debug(f"[ASSIGNED_TASKS][{request_id}] Cursor closed")
        except Exception as e:
            logging.warning(f"[ASSIGNED_TASKS][{request_id}] Failed to close cursor: {e}")
            
        try:
            if 'conn' in locals() and conn:
                conn.close()
                logging.debug(f"[ASSIGNED_TASKS][{request_id}] DB connection closed")
        except Exception as e:
            logging.warning(f"[ASSIGNED_TASKS][{request_id}] Failed to close DB connection: {e}")
        
        # Final timestamp
        end_time = time.time()
        total_time = end_time - start_time
        logging.info(f"[ASSIGNED_TASKS][{request_id}] Request completed at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC (total: {total_time:.4f}s)")

# PATCH route to update part completion and adjust progress
@employee_bp.route('/update_task_part', methods=['PATCH'])
@employee_jwt_required()
@csrf.exempt
def update_task_part():
    employee_id = g.employee_id
    role = g.employee_role

    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized task part update attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    if not data:
        log_employee_incident(
            employee_id=employee_id,
            description="Task part update attempted with no data provided",
            severity="Low"
        )
        return jsonify({'error': 'No data provided'}), 400

    part_id = data.get('part_id')
    task_id = data.get('task_id')
    completed = data.get('completed')  # true or false

    if part_id is None or task_id is None or completed is None:
        missing_fields = []
        if part_id is None: missing_fields.append('part_id')
        if task_id is None: missing_fields.append('task_id')
        if completed is None: missing_fields.append('completed')
        
        log_employee_incident(
            employee_id=employee_id,
            description=f"Task part update attempted with missing fields: {', '.join(missing_fields)}",
            severity="Low"
        )
        return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify the task part exists and get details for logging
        cursor.execute("""
            SELECT tp.part_percentage, tp.part_name, tp.completed, t.task_name, t.employee_id, t.team_id
            FROM task_parts tp
            JOIN tasks t ON tp.task_id = t.task_id
            WHERE tp.part_id = %s AND tp.task_id = %s
        """, (part_id, task_id))
        
        part_info = cursor.fetchone()
        
        if not part_info:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to update non-existent task part: part_id={part_id}, task_id={task_id}",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Part not found'}), 404

        percentage, part_name, current_completed, task_name, task_employee_id, task_team_id = part_info

        # Verify employee has permission to update this task part
        # Check if task is assigned directly to employee or to their team
        has_permission = False
        permission_source = ""
        
        if task_employee_id == employee_id:
            has_permission = True
            permission_source = "direct_assignment"
        elif task_team_id:
            # Check if employee is member of the task's team
            cursor.execute("""
                SELECT 1 FROM team_members 
                WHERE employee_id = %s AND team_id = %s
                UNION
                SELECT 1 FROM employees 
                WHERE employee_id = %s AND team_id = %s
            """, (employee_id, task_team_id, employee_id, task_team_id))
            
            if cursor.fetchone():
                has_permission = True
                permission_source = "team_membership"

        if not has_permission:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to update unauthorized task part: task '{task_name}' (task_id={task_id}, part_id={part_id}) - not assigned to employee or their team",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Access denied: Task not assigned to you or your team'}), 403

        # Check if this is actually a change
        if current_completed == completed:
            log_employee_audit(
                employee_id=employee_id,
                action="update_task_part",
                details=f"Attempted to update task part with no change: '{task_name}' part '{part_name}' ({percentage}%) already {'completed' if completed else 'not completed'} (task_id={task_id}, part_id={part_id})"
            )
            cursor.close()
            conn.close()
            return jsonify({'message': 'Task part already in requested state'}), 200

        # Get current task progress for logging
        cursor.execute("SELECT progress FROM tasks WHERE task_id = %s", (task_id,))
        current_progress = cursor.fetchone()[0] or 0

        # Update task_parts
        cursor.execute("""
            UPDATE task_parts
            SET completed = %s,
                executed_at = CURRENT_TIMESTAMP
            WHERE part_id = %s
        """, (completed, part_id))

        # Update tasks progress
        progress_change = percentage if completed else -percentage
        new_progress = max(0, min(100, current_progress + progress_change))  # Ensure progress stays within 0-100%
        
        cursor.execute("""
            UPDATE tasks
            SET progress = %s
            WHERE task_id = %s
        """, (new_progress, task_id))

        conn.commit()

        # Log successful audit trail
        action_description = "completed" if completed else "marked as incomplete"
        progress_info = f"progress: {current_progress}% → {new_progress}% ({progress_change:+}%)"
        
        log_employee_audit(
            employee_id=employee_id,
            action="update_task_part",
            details=f"Successfully {action_description} task part '{part_name}' ({percentage}%) for task '{task_name}': {progress_info} | Permission: {permission_source} (task_id={task_id}, part_id={part_id})"
        )

        cursor.close()
        conn.close()
        return jsonify({
            'message': 'Task part updated successfully',
            'new_progress': new_progress,
            'progress_change': progress_change
        }), 200

    except Exception as e:
        logging.error(f"Error updating task part: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error during task part update: part_id={part_id}, task_id={task_id}, completed={completed} - {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@employee_bp.route('/create-issue', methods=['POST'])
@employee_jwt_required()  # Added JWT requirement for security
def create_github_issue():
    try:
        employee_id = g.employee_id
        
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized GitHub issue creation attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({"message": "Unauthorized"}), 401

        logging.debug("Received request to /create-issue endpoint.")

        # Read input from frontend (JSON)
        data = request.get_json()
        logging.debug(f"Request JSON data: {data}")

        if not data:
            log_employee_incident(
                employee_id=employee_id,
                description="GitHub issue creation attempted with no data provided",
                severity="Low"
            )
            return jsonify({"message": "No data provided"}), 400

        title = data.get('title', '').strip()
        body = data.get('body', '').strip()
        
        logging.debug(f"Issue Title: {title}")
        logging.debug(f"Issue Body: {body}")

        # Validate required fields
        if not title:
            log_employee_incident(
                employee_id=employee_id,
                description="GitHub issue creation attempted with missing title",
                severity="Low"
            )
            return jsonify({"message": "Issue title is required"}), 400

        # Validate title length (GitHub limit is 256 characters)
        if len(title) > 256:
            log_employee_incident(
                employee_id=employee_id,
                description=f"GitHub issue creation attempted with title too long: {len(title)} characters",
                severity="Low"
            )
            return jsonify({"message": "Issue title too long (max 256 characters)"}), 400

        # Validate body length (reasonable limit for logging)
        if len(body) > 65536:  # 64KB limit
            log_employee_incident(
                employee_id=employee_id,
                description=f"GitHub issue creation attempted with body too long: {len(body)} characters",
                severity="Medium"
            )
            return jsonify({"message": "Issue body too long (max 64KB)"}), 400

        # Get employee info for better logging
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT first_name, last_name, email FROM employees WHERE employee_id = %s", (employee_id,))
        employee_info = cursor.fetchone()
        employee_name = f"{employee_info[0]} {employee_info[1]}" if employee_info else "Unknown Employee"
        employee_email = employee_info[2] if employee_info else "unknown@email.com"
        cursor.close()
        conn.close()

        # Add employee information to the issue body for tracking
        enhanced_body = f"{body}\n\n---\n**Created by:** {employee_name} ({employee_email})\n**Employee ID:** {employee_id}\n**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"

        # Payload for GitHub API
        payload = {
            "title": title,
            "body": enhanced_body,
            "labels": ["employee-reported"]  # Add label to track employee-created issues
        }
        logging.debug(f"GitHub API payload: {payload}")

        # Headers with authentication
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Employee-Portal-{employee_id}"  # Custom user agent for tracking
        }
        logging.debug(f"GitHub API headers: {headers}")

        # GitHub API endpoint
        github_api_url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
        logging.debug(f"GitHub API URL: {github_api_url}")

        # Make the POST request to GitHub
        response = requests.post(github_api_url, headers=headers, json=payload, timeout=30)
        logging.debug(f"GitHub response status code: {response.status_code}")
        logging.debug(f"GitHub response text: {response.text}")

        # Handle response
        if response.status_code == 201:
            logging.info("Issue created successfully on GitHub.")
            
            # Parse response to get issue details
            github_response = response.json()
            issue_number = github_response.get('number')
            issue_url = github_response.get('html_url')
            issue_id = github_response.get('id')
            
            # Log successful audit trail
            title_preview = title[:50] + "..." if len(title) > 50 else title
            body_preview = body[:100] + "..." if len(body) > 100 else body
            
            log_employee_audit(
                employee_id=employee_id,
                action="create_github_issue",
                details=f"Successfully created GitHub issue #{issue_number} (ID: {issue_id}): '{title_preview}' | Body: '{body_preview}' | URL: {issue_url} | Employee: {employee_name} ({employee_email})"
            )
            
            return jsonify({
                "message": "Issue created successfully!",
                "issue_number": issue_number,
                "issue_url": issue_url,
                "issue_id": issue_id
            }), 201
            
        else:
            # Log incident for GitHub API failure
            error_details = "Unknown error"
            try:
                error_response = response.json()
                error_details = error_response.get('message', str(error_response))
            except:
                error_details = response.text

            log_employee_incident(
                employee_id=employee_id,
                description=f"GitHub issue creation failed: HTTP {response.status_code} - {error_details} | Title: '{title[:50]}{'...' if len(title) > 50 else ''}' | Employee: {employee_name}",
                severity="Medium"
            )
            
            logging.error(f"Failed to create issue. Status: {response.status_code}, Details: {response.text}")
            return jsonify({
                "message": "Failed to create issue", 
                "details": error_details,
                "status_code": response.status_code
            }), response.status_code

    except requests.exceptions.Timeout:
        # Log incident for timeout
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description="GitHub issue creation failed due to timeout",
            severity="Medium"
        )
        
        logging.error("GitHub API request timed out")
        return jsonify({"message": "GitHub API request timed out", "error": "timeout"}), 408
        
    except requests.exceptions.ConnectionError:
        # Log incident for connection error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description="GitHub issue creation failed due to connection error",
            severity="High"
        )
        
        logging.error("Failed to connect to GitHub API")
        return jsonify({"message": "Failed to connect to GitHub API", "error": "connection_error"}), 503
        
    except requests.exceptions.RequestException as e:
        # Log incident for other request errors
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"GitHub issue creation failed due to request error: {str(e)}",
            severity="Medium"
        )
        
        logging.error(f"GitHub API request failed: {e}")
        return jsonify({"message": "GitHub API request failed", "error": str(e)}), 502

    except Exception as e:
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during GitHub issue creation: {str(e)}",
            severity="High"
        )
        
        logging.exception("An exception occurred in create_github_issue")
        return jsonify({"message": "An error occurred", "error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()