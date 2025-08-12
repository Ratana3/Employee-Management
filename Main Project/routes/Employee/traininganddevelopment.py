#route for dislaying training materials
from datetime import datetime
import logging
from flask import g, jsonify, render_template, request
from routes.Auth.token import verify_employee_token,employee_jwt_required
from routes.Auth.utils import get_db_connection
from . import employee_bp
from psycopg2.extras import RealDictCursor
from extensions import csrf
from routes.Auth.audit import log_employee_audit,log_employee_incident


#route for rendering training page
@employee_bp.route('/trainings', methods=['GET', 'POST'])
def training_and_development():
    return render_template('Employee/trainingAnddevelopment.html')

@employee_bp.route("/get_my_assessments", methods=["GET"])
@employee_jwt_required()
def get_my_assessments():
    employee_id = g.employee_id  # Extracted from the decorator

    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized assessments access attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Fetch all assessments for this employee
        cur.execute("""
            SELECT sa.assessment_id, sa.module_id, tm.module_name, sa.assessment_date,
                   sa.score, sa.feedback, sa.is_completed
            FROM skill_assessments sa
            JOIN training_modules tm ON sa.module_id = tm.module_id
            WHERE sa.employee_id = %s
            ORDER BY sa.assessment_date DESC, sa.assessment_id DESC
        """, (employee_id,))
        assessment_rows = cur.fetchall()
        assessments = []

        # Analytics for logging
        completed_assessments = 0
        pending_assessments = 0
        total_score = 0
        score_count = 0
        modules = set()
        recent_assessments = 0
        high_scores = 0  # scores >= 80%
        
        current_date = datetime.now().date()

        for row in assessment_rows:
            assessment_id, module_id, module_name, date, score, feedback, is_completed = row
            
            # Analytics tracking
            modules.add(module_name)
            if is_completed:
                completed_assessments += 1
                if score is not None:
                    total_score += score
                    score_count += 1
                    if score >= 80:
                        high_scores += 1
            else:
                pending_assessments += 1
            
            if date and (current_date - date.date()).days <= 30:
                recent_assessments += 1

            cur.execute("""
                SELECT 
                    q.question_id, q.question_text,
                    o.option_id, o.option_text, o.is_checked,
                    aa.selected_option_id AS selected_option_id
                FROM assessment_questions q
                LEFT JOIN assessment_options o ON q.question_id = o.question_id
                LEFT JOIN assessment_answers aa 
                    ON aa.question_id = q.question_id AND aa.employee_id = %s AND aa.assessment_id = %s
                WHERE q.assessment_id = %s
                ORDER BY q.question_id, o.option_id
            """, (employee_id, assessment_id, assessment_id))
            options_rows = cur.fetchall()

            question_map = {}
            for q_id, q_text, opt_id, opt_text, is_checked, selected_option_id in options_rows:
                if q_id not in question_map:
                    question_map[q_id] = {
                        "question_id": q_id,
                        "question_text": q_text,
                        "selected_option": selected_option_id,
                        "options": []
                    }

                if opt_id:
                    question_map[q_id]["options"].append({
                        "option_id": opt_id,
                        "option_text": opt_text,
                        "is_correct": is_checked,
                        "is_selected": selected_option_id == opt_id
                    })

            assessments.append({
                "assessment_id": assessment_id,
                "module_id": module_id,
                "module_name": module_name,
                "assessment_date": date.isoformat() if date else None,
                "score": score,
                "feedback": feedback,
                "submitted": is_completed,
                "questions": list(question_map.values())
            })

        # Log successful audit trail
        avg_score = total_score / score_count if score_count > 0 else 0
        modules_summary = ', '.join(list(modules)[:3]) + (f" and {len(modules)-3} others" if len(modules) > 3 else "")
        
        log_employee_audit(
            employee_id=employee_id,
            action="view_assessments",
            details=f"Retrieved {len(assessments)} assessments from {len(modules)} modules ({modules_summary}): {completed_assessments} completed, {pending_assessments} pending | Avg score: {avg_score:.1f}%, {high_scores} high scores (≥80%), {recent_assessments} recent (last 30 days)"
        )

        cur.close()
        conn.close()
        return jsonify({"success": True, "assessments": assessments})

    except Exception as e:
        print("❌ Error fetching employee assessments:", e)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error while fetching employee assessments: {str(e)}",
            severity="High"
        )
        
        return jsonify({"success": False, "message": "Server error"}), 500

    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

@employee_bp.route('/api/my_trainings', methods=['GET'])
@employee_jwt_required()
def get_my_trainings():
    employee_id = g.employee_id
    
    if not employee_id:
        logging.warning("Invalid or expired token. Returning empty result.")
        log_employee_incident(
            employee_id=None,
            description="Unauthorized training modules access attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify([])

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch assigned training modules, including assessment and certificate details
        cursor.execute("""
            SELECT tm.module_id, tm.module_name, tm.description, tm.deadline,
                   sa.score, sa.is_completed,
                   tc.certificate_status, tc.issued_date
            FROM training_modules tm
            LEFT JOIN skill_assessments sa ON sa.module_id = tm.module_id AND sa.employee_id = %s
            LEFT JOIN training_certificates tc ON tc.module_id = tm.module_id AND tc.employee_id = %s
            ORDER BY tm.deadline ASC, tm.module_name ASC
        """, (employee_id, employee_id))
        
        rows = cursor.fetchall()

        # Analytics for logging
        total_modules = len(rows)
        completed_modules = 0
        certified_modules = 0
        overdue_modules = 0
        high_score_modules = 0
        modules_with_deadlines = 0
        
        current_date = datetime.now().date()

        result = []
        for row in rows:
            module_deadline = row[3]
            assessment_score = row[4]
            assessment_completed = row[5]
            certificate_status = row[6]
            
            # Analytics tracking
            if assessment_completed:
                completed_modules += 1
                if assessment_score and assessment_score >= 80:
                    high_score_modules += 1
            
            if certificate_status:
                certified_modules += 1
            
            if module_deadline:
                modules_with_deadlines += 1
                if current_date > module_deadline and not assessment_completed:
                    overdue_modules += 1
            
            module = {
                'module_id': row[0],
                'module_name': row[1],
                'description': row[2],
                'deadline': module_deadline.strftime('%Y-%m-%d') if module_deadline else None,
                'assessment': {
                    'score': assessment_score,
                    'is_completed': assessment_completed
                } if assessment_score is not None else None,
                'certificate': {
                    'certificate_status': certificate_status,
                    'issued_date': row[7].strftime('%Y-%m-%d') if row[7] else None
                } if certificate_status else None
            }
            result.append(module)

        # Log successful audit trail
        completion_rate = (completed_modules / total_modules * 100) if total_modules > 0 else 0
        certification_rate = (certified_modules / total_modules * 100) if total_modules > 0 else 0
        
        log_employee_audit(
            employee_id=employee_id,
            action="view_training_modules",
            details=f"Retrieved {total_modules} training modules: {completed_modules} completed ({completion_rate:.1f}%), {certified_modules} certified ({certification_rate:.1f}%), {high_score_modules} high scores (≥80%), {overdue_modules} overdue out of {modules_with_deadlines} with deadlines"
        )

        cursor.close()
        conn.close()
        return jsonify(result)

    except Exception as e:
        logging.error(f"Error fetching training data: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error while fetching training modules: {str(e)}",
            severity="High"
        )
        
        return jsonify([])

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@csrf.exempt
@employee_bp.route("/submit_assessment/<int:assessment_id>", methods=["POST"])
@employee_jwt_required()
def submit_assessment(assessment_id):
    print(f"🔐 Submitting assessment: {assessment_id}")
    from datetime import datetime
    import traceback

    try:
        employee_id = g.employee_id  # Extracted from the decorator
        print(f"[{datetime.utcnow()}] Employee ID: {employee_id}")

        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description=f"Unauthorized assessment submission attempt for assessment {assessment_id} - no employee_id in session",
                severity="High"
            )
            return jsonify({"success": False, "message": "Unauthorized"}), 401

        data = request.get_json()
        print(f"[{datetime.utcnow()}] Raw request data: {data}")

        if not data or "answers" not in data:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Assessment {assessment_id} submission attempted with no answers data",
                severity="Low"
            )
            return jsonify({"success": False, "message": "No data provided"}), 400

        try:
            selected_option_ids = {int(k): int(v) for k, v in data.get("answers", {}).items()}
        except (ValueError, TypeError) as e:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Assessment {assessment_id} submission attempted with invalid answer format: {str(e)}",
                severity="Medium"
            )
            return jsonify({"success": False, "message": "Invalid answer format"}), 400

        print(f"[{datetime.utcnow()}] Parsed selected_option_ids: {selected_option_ids}")

        if not selected_option_ids:
            print(f"[{datetime.utcnow()}] No answers submitted")
            log_employee_incident(
                employee_id=employee_id,
                description=f"Assessment {assessment_id} submission attempted with no answers",
                severity="Low"
            )
            return jsonify({"success": False, "message": "No answers submitted"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # Get assessment and module info for logging
        cur.execute("""
            SELECT sa.module_id, tm.module_name, sa.score, sa.is_completed
            FROM skill_assessments sa
            JOIN training_modules tm ON sa.module_id = tm.module_id
            WHERE sa.assessment_id = %s AND sa.employee_id = %s
        """, (assessment_id, employee_id))
        assessment_info = cur.fetchone()
        
        if not assessment_info:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to submit non-existent or unauthorized assessment {assessment_id}",
                severity="High"
            )
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Assessment not found or access denied"}), 404

        module_id, module_name, current_score, is_completed = assessment_info

        print(f"[{datetime.utcnow()}] Checking if assessment already submitted...")
        if is_completed and current_score is not None:
            print(f"[{datetime.utcnow()}] Assessment already submitted for employee {employee_id} on assessment {assessment_id}")
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to re-submit already completed assessment {assessment_id} for module '{module_name}' (current score: {current_score}%)",
                severity="Medium"
            )
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Assessment already submitted"}), 403

        # Defensive: Validate all question_ids for this assessment exist
        cur.execute("""
            SELECT question_id FROM assessment_questions WHERE assessment_id = %s
        """, (assessment_id,))
        valid_question_ids = {row[0] for row in cur.fetchall()}
        print(f"[{datetime.utcnow()}] valid_question_ids for assessment {assessment_id}: {valid_question_ids}")

        invalid_questions = []
        for qid in selected_option_ids.keys():
            if qid not in valid_question_ids:
                invalid_questions.append(qid)

        if invalid_questions:
            print(f"[{datetime.utcnow()}] Invalid question_ids {invalid_questions} for assessment {assessment_id}")
            log_employee_incident(
                employee_id=employee_id,
                description=f"Assessment {assessment_id} submission attempted with invalid question IDs: {invalid_questions}",
                severity="High"
            )
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": f"Invalid questions in submission: {invalid_questions}"}), 400

        print(f"[{datetime.utcnow()}] Fetching options from assessment_options with ids: {list(selected_option_ids.values())}")
        cur.execute("""
            SELECT ao.question_id, ao.option_id, ao.is_checked
            FROM assessment_options ao
            WHERE ao.option_id = ANY(%s)
        """, (list(selected_option_ids.values()),))
        option_rows = cur.fetchall()
        print(f"[{datetime.utcnow()}] option_rows: {option_rows}")

        correct_map = {(qid, oid): is_checked for qid, oid, is_checked in option_rows}
        print(f"[{datetime.utcnow()}] correct_map: {correct_map}")

        score = 0
        total = len(selected_option_ids)
        correct_answers = 0
        incorrect_answers = 0

        for q_id, selected_oid in selected_option_ids.items():
            is_correct = correct_map.get((q_id, selected_oid), False)
            print(f"[{datetime.utcnow()}] QID: {q_id}, Selected Option: {selected_oid}, Is Correct: {is_correct}")
            if is_correct:
                score += 1
                correct_answers += 1
            else:
                incorrect_answers += 1

        percentage = (score / total) * 100 if total > 0 else 0
        print(f"[{datetime.utcnow()}] Calculated score: {score}/{total}, percentage: {percentage}")

        # Clear previous answers
        print(f"[{datetime.utcnow()}] Deleting previous answers for assessment_id={assessment_id}, employee_id={employee_id}")
        cur.execute("""
            DELETE FROM assessment_answers
            WHERE assessment_id = %s AND employee_id = %s
        """, (assessment_id, employee_id))

        # Save new answers
        print(f"[{datetime.utcnow()}] Inserting new answers...")
        for question_id, option_id in selected_option_ids.items():
            print(f"  Inserting answer: (assessment_id={assessment_id}, employee_id={employee_id}, question_id={question_id}, selected_option_id={option_id})")
            cur.execute("""
                INSERT INTO assessment_answers (assessment_id, employee_id, question_id, selected_option_id)
                VALUES (%s, %s, %s, %s)
            """, (assessment_id, employee_id, question_id, option_id))

        print(f"[{datetime.utcnow()}] Updating skill_assessments for score and completion status.")
        cur.execute("""
            UPDATE skill_assessments
            SET score = %s, is_completed = TRUE, assessment_date = NOW()
            WHERE assessment_id = %s AND employee_id = %s
        """, (percentage, assessment_id, employee_id))

        conn.commit()
        print(f"[{datetime.utcnow()}] Assessment submitted successfully. Score: {percentage}")

        # Log successful audit trail
        performance_category = "Excellent" if percentage >= 90 else "Good" if percentage >= 80 else "Satisfactory" if percentage >= 70 else "Needs Improvement"
        
        log_employee_audit(
            employee_id=employee_id,
            action="submit_assessment",
            details=f"Successfully submitted assessment {assessment_id} for module '{module_name}': {score}/{total} correct ({percentage:.1f}%) - {performance_category} | {correct_answers} correct, {incorrect_answers} incorrect answers"
        )

        cur.close()
        conn.close()
        return jsonify({"success": True, "score": percentage})

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        print("❌ Error submitting assessment:", e)
        print(traceback.format_exc())
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during assessment {assessment_id} submission: {str(e)}",
            severity="High"
        )
        
        return jsonify({"success": False, "message": "Server error"}), 500

    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()  

@employee_bp.route('/employee/learning_resources')
@employee_jwt_required()
def get_employee_learning_resources():
    employee_id = g.employee_id
    
    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized learning resources access attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify([]), 401

    search = request.args.get('search', '').strip()
    resource_type = request.args.get('type', '')
    sort_order = request.args.get('sort', 'desc')  # desc = Newest first

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        query = "SELECT * FROM learning_resources WHERE 1=1"
        params = []

        if search:
            query += " AND (title ILIKE %s OR description ILIKE %s)"
            params.extend([f'%{search}%', f'%{search}%'])

        if resource_type:
            query += " AND resource_type = %s"
            params.append(resource_type)

        query += f" ORDER BY created_at {'ASC' if sort_order == 'asc' else 'DESC'}"

        cursor.execute(query, tuple(params))
        resources = cursor.fetchall()

        # Analytics for logging
        total_resources = len(resources)
        resource_types = {}
        recent_resources = 0
        search_matches = 0
        
        current_date = datetime.now().date()
        
        for resource in resources:
            # Track resource types
            rtype = resource.get('resource_type', 'Unknown')
            resource_types[rtype] = resource_types.get(rtype, 0) + 1
            
            # Track recent resources (last 30 days)
            created_at = resource.get('created_at')
            if created_at:
                if hasattr(created_at, 'date'):
                    resource_date = created_at.date()
                elif isinstance(created_at, str):
                    try:
                        resource_date = datetime.strptime(created_at.split()[0], '%Y-%m-%d').date()
                    except:
                        resource_date = None
                else:
                    resource_date = None
                
                if resource_date and (current_date - resource_date).days <= 30:
                    recent_resources += 1
            
            # Check if search terms found in title/description
            if search:
                title = resource.get('title', '').lower()
                description = resource.get('description', '').lower()
                if search.lower() in title or search.lower() in description:
                    search_matches += 1

        # Log successful audit trail
        types_summary = ', '.join([f"{count} {rtype}" for rtype, count in list(resource_types.items())[:3]]) if resource_types else "none"
        if len(resource_types) > 3:
            types_summary += f" and {len(resource_types)-3} other types"
        
        search_info = f" | Search: '{search}' ({search_matches} matches)" if search else ""
        filter_info = f" | Type filter: '{resource_type}'" if resource_type else ""
        sort_info = f" | Sort: {sort_order}"
        
        log_employee_audit(
            employee_id=employee_id,
            action="view_learning_resources",
            details=f"Retrieved {total_resources} learning resources: {types_summary}, {recent_resources} recent (last 30 days){search_info}{filter_info}{sort_info}"
        )

        cursor.close()
        conn.close()
        return jsonify(resources)

    except Exception as e:
        logging.error("Error fetching learning resources", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error while fetching learning resources: {str(e)}",
            severity="High"
        )
        
        return jsonify([]), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# Route to fetch training modules and certificates
@employee_bp.route('/training', methods=['GET'])
@employee_jwt_required()
def fetch_training_modules():
    try:
        employee_id = g.employee_id  # Get employee_id from JWT decorator

        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized training modules access attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({"error": "Unauthorized"}), 401

        logging.debug(f"Fetching training modules for employee_id: {employee_id}")
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT 
                tm.module_id, tm.module_name, tm.description, tm.created_at, tm.deadline, tm.updated_at,
                tc.certificate_id, tc.issued_date, tc.certificate_status
            FROM training_modules tm
            JOIN module_assignments ma ON ma.module_id = tm.module_id
            LEFT JOIN training_certificates tc ON tc.module_id = tm.module_id AND tc.employee_id = %s
            WHERE ma.employee_id = %s
            ORDER BY tm.created_at DESC
        """

        cursor.execute(query, (employee_id, employee_id))
        rows = cursor.fetchall()

        # Analytics for logging
        total_modules = len(rows)
        modules_with_certificates = 0
        modules_with_deadlines = 0
        overdue_modules = 0
        recent_modules = 0
        certificate_statuses = {}
        upcoming_deadlines = 0
        
        current_date = datetime.now().date()

        result = []
        for row in rows:
            module_id, module_name, description, created_at, deadline, updated_at = row[:6]
            certificate_id, issued_date, certificate_status = row[6:9]
            
            # Analytics tracking
            if certificate_id:
                modules_with_certificates += 1
                status = certificate_status or 'Unknown'
                certificate_statuses[status] = certificate_statuses.get(status, 0) + 1
            
            if deadline:
                modules_with_deadlines += 1
                if isinstance(deadline, str):
                    try:
                        deadline_date = datetime.strptime(deadline.split()[0], '%Y-%m-%d').date()
                    except:
                        deadline_date = None
                elif hasattr(deadline, 'date'):
                    deadline_date = deadline.date()
                else:
                    deadline_date = deadline
                
                if deadline_date:
                    days_to_deadline = (deadline_date - current_date).days
                    if days_to_deadline < 0:
                        overdue_modules += 1
                    elif days_to_deadline <= 14:  # Within 2 weeks
                        upcoming_deadlines += 1
            
            if created_at:
                if hasattr(created_at, 'date'):
                    created_date = created_at.date()
                elif isinstance(created_at, str):
                    try:
                        created_date = datetime.strptime(created_at.split()[0], '%Y-%m-%d').date()
                    except:
                        created_date = None
                else:
                    created_date = None
                
                if created_date and (current_date - created_date).days <= 30:
                    recent_modules += 1

            result.append({
                "module_id": module_id,
                "module_name": module_name,
                "description": description,
                "created_at": str(created_at),
                "deadline": str(deadline),
                "updated_at": str(updated_at),
                "certificate": {
                    "certificate_id": certificate_id,
                    "issued_date": str(issued_date) if issued_date else None,
                    "certificate_status": certificate_status
                } if certificate_id else None
            })

        # Log successful audit trail
        certification_rate = (modules_with_certificates / total_modules * 100) if total_modules > 0 else 0
        deadline_info = f"{modules_with_deadlines} with deadlines ({overdue_modules} overdue, {upcoming_deadlines} due soon)"
        
        cert_status_summary = ', '.join([f"{count} {status}" for status, count in certificate_statuses.items()]) if certificate_statuses else "none"
        
        log_employee_audit(
            employee_id=employee_id,
            action="view_training_modules",
            details=f"Retrieved {total_modules} assigned training modules: {modules_with_certificates} certified ({certification_rate:.1f}%), {recent_modules} recent (last 30 days) | Deadlines: {deadline_info} | Certificates: {cert_status_summary}"
        )

        cursor.close()
        conn.close()
        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Error fetching training data: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while fetching training modules: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()