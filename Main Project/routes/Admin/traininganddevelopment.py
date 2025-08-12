from datetime import datetime, timedelta
import logging
import os
import bcrypt
from flask import Blueprint, Response, render_template, jsonify, request, send_file, url_for
import psycopg2
from routes.Auth.audit import log_audit, log_incident
from routes.Auth.token import token_required_with_roles
from routes.Auth.utils import get_db_connection
from routes.Auth.config import UPLOAD_FOLDER, allowed_file
from . import admin_bp
from extensions import csrf
from PIL import Image
import io
from werkzeug.utils import secure_filename


@admin_bp.route('/traininganddevelopment', methods=['GET', 'POST'])
def traininganddevelopment():
    return render_template('Admin/traininganddevelopment.html')

# Get assign options for dropdown
@admin_bp.route('/admin/assign-options')
@token_required_with_roles(required_actions=["get_assign_options"])
def get_assign_options(admin_id, role, role_id):
    assign_type = request.args.get('type')
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()

        if assign_type == 'employee':
            cursor.execute("SELECT employee_id, email AS name FROM employees")
            options = cursor.fetchall()
        elif assign_type == 'team':
            cursor.execute("SELECT team_id AS employee_id, team_name FROM teams")
            options = cursor.fetchall()
        else:
            return jsonify([])

        # Audit log
        log_audit(admin_id, role, "get_assign_options", f"Fetched assign options for type '{assign_type}'")
        return jsonify([{"id": o[0], "name": o[1]} for o in options])

    except Exception as e:
        log_incident(admin_id, role, f"Error fetching assign options: {e}", severity="High")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Route for assigning badge for employee or team
@admin_bp.route('/admin/assign_badge', methods=['POST'])
@token_required_with_roles(required_actions=["assign_badge"])
def assign_badge(admin_id, role, role_id):
    badge_id = request.form.get('badge_id')
    target_type = request.form.get('type')  # 'employee' or 'team'
    target_id = request.form.get('target_id')

    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        if target_type == 'employee':
            cursor.execute("""
                INSERT INTO badge_assignments (badge_id, employee_id, assigned_at)
                VALUES (%s, %s, NOW())
            """, (badge_id, target_id))
        elif target_type == 'team':
            cursor.execute("""
                INSERT INTO badge_assignments (badge_id, team_id, assigned_at)
                VALUES (%s, %s, NOW())
            """, (badge_id, target_id))
        else:
            return jsonify({"error": "Invalid target type"}), 400

        conn.commit()
        log_audit(admin_id, role, "assign_badge", f"Assigned badge ID {badge_id} to {target_type} ID {target_id}")
        return jsonify({"message": "Badge assigned successfully!"})

    except Exception as e:
        conn.rollback()
        log_incident(admin_id, role, f"Error assigning badge: {e}", severity="High")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Route for removing badge assignment(s) from employee or team, and also fetch assignments for the badge
@csrf.exempt
@admin_bp.route('/admin/remove_badge_assignment', methods=['POST'])
@token_required_with_roles(required_actions=["remove_badge_assignment"])
def remove_badge_assignment(admin_id, role, role_id):
    badge_id = request.json.get('badge_id')
    target_type = request.json.get('type')  # 'employee' or 'team'
    target_ids = request.json.get('target_ids')  # list of employee/team ids

    if not badge_id:
        return jsonify({"error": "Missing badge_id"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Remove assignments if requested
        if target_type and isinstance(target_ids, list):
            try:
                target_ids = [int(x) for x in target_ids]
            except Exception:
                return jsonify({"error": "target_ids must be integers"}), 400
            if target_type == 'employee':
                cursor.execute(
                    "DELETE FROM badge_assignments WHERE badge_id = %s AND employee_id = ANY(%s)",
                    (badge_id, target_ids)
                )
            elif target_type == 'team':
                cursor.execute(
                    "DELETE FROM badge_assignments WHERE badge_id = %s AND team_id = ANY(%s)",
                    (badge_id, target_ids)
                )
            else:
                return jsonify({"error": "Invalid target type"}), 400
            conn.commit()
            log_audit(admin_id, role, "remove_badge_assignment", f"Removed badge ID {badge_id} from {target_type} IDs {target_ids}")

        # Always fetch current assignments for this badge after mutation (for modal/table refresh)
        cursor.execute("""
            SELECT a.assignment_id, a.employee_id, a.team_id, a.assigned_at, e.email, t.team_name
            FROM badge_assignments a
            LEFT JOIN employees e ON a.employee_id = e.employee_id
            LEFT JOIN teams t ON a.team_id = t.team_id
            WHERE a.badge_id = %s
        """, (badge_id,))
        assignments = []
        for row in cursor.fetchall():
            if row[1]:
                assignments.append({
                    'id': row[1],
                    'type': 'employee',
                    'target': row[4] if row[4] else f'Employee ID: {row[1]}',
                    'assigned_at': row[3].strftime('%Y-%m-%d %H:%M')
                })
            elif row[2]:
                assignments.append({
                    'id': row[2],
                    'type': 'team',
                    'target': row[5] if row[5] else f'Team ID: {row[2]}',
                    'assigned_at': row[3].strftime('%Y-%m-%d %H:%M')
                })

        cursor.close()
        conn.close()
        return jsonify({
            "message": "Badge assignment(s) removed successfully!" if target_type else "Fetched assignments.",
            "assignments": assignments
        })
    except Exception as e:
        conn.rollback()
        log_incident(admin_id, role, f"Error removing badge assignment: {e}", severity="High")
        return jsonify({"error": str(e)}), 500
    finally:
        if not cursor.closed:
            cursor.close()
        if conn:
            conn.close()

# Get all badges with assignments
@admin_bp.route('/admin/badges_with_assignments')
@token_required_with_roles(required_actions=["get_badges_with_assignments"])
def get_badges_with_assignments(admin_id, role, role_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM badges")
        badges = cursor.fetchall()

        data = []

        for badge in badges:
            badge_id = badge[0]  # Assuming badge_id is first column
            badge_name = badge[1]
            description = badge[2]

            cursor.execute("""
                SELECT 
                    a.assignment_id, a.employee_id, a.team_id, a.assigned_at,
                    e.email AS employee_email, t.team_name AS team_name
                FROM badge_assignments a
                LEFT JOIN employees e ON a.employee_id = e.employee_id
                LEFT JOIN teams t ON a.team_id = t.team_id
                WHERE a.badge_id = %s
            """, (badge_id,))
            assignments = cursor.fetchall()

            formatted_assignments = []
            for a in assignments:
                assignment_id = a[0]
                employee_id = a[1]
                team_id = a[2]
                assigned_at = a[3]
                employee_email = a[4]
                team_name = a[5]

                target = employee_email or team_name or 'Unknown'
                target_type = 'Employee' if employee_id else 'Team'

                formatted_assignments.append({
                    "assignment_id": assignment_id,
                    "target": target,
                    "type": target_type,
                    "assigned_at": assigned_at.strftime("%Y-%m-%d %H:%M") if assigned_at else "N/A"
                })

            data.append({
                "badge_id": badge_id,
                "badge_name": badge_name,
                "description": description,
                "assignments": formatted_assignments
            })

        log_audit(admin_id, role, "get_badges_with_assignments", f"Fetched badges with assignments (count {len(data)})")
        return jsonify(data)

    except Exception as e:
        log_incident(admin_id, role, f"Error fetching badges with assignments: {e}", severity="High")
        print("Error in /admin/badges_with_assignments:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        if conn:
            conn.close()

# Add badge
@admin_bp.route('/admin/badges', methods=['POST'])
@token_required_with_roles(required_actions=["add_badge"])
def add_badge(admin_id, role, role_id):
    name = request.form.get('name')
    description = request.form.get('description')
    file = request.files.get('icon')
    
    if not name or not description or not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid input'}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    icon_url = f"/{file_path}"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO badges (name, description, icon_url)
        VALUES (%s, %s, %s)
    """, (name, description, icon_url))
    conn.commit()
    conn.close()
    log_audit(admin_id, role, "add_badge", f"Added badge '{name}'")
    return jsonify({'message': 'Badge added successfully'})

# Edit badge
@admin_bp.route('/admin/badges/<int:badge_id>', methods=['POST'])
@token_required_with_roles(required_actions=["update_badge"])
def update_badge(admin_id, role, role_id, badge_id):
    name = request.form.get('name')
    description = request.form.get('description')
    file = request.files.get('icon')

    if not name or not description:
        return jsonify({'error': 'Name and description are required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT icon_url FROM badges WHERE badge_id = %s", (badge_id,))
    result = cursor.fetchone()
    old_icon_url = result[0] if result else None

    icon_url = None
    if file and allowed_file(file.filename):
        if old_icon_url:
            old_file_path = old_icon_url.lstrip('/')
            if os.path.exists(old_file_path):
                os.remove(old_file_path)

        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        icon_url = f"/{file_path}"

    if icon_url:
        cursor.execute("""
            UPDATE badges
            SET name = %s, description = %s, icon_url = %s
            WHERE badge_id = %s
        """, (name, description, icon_url, badge_id))
    else:
        cursor.execute("""
            UPDATE badges
            SET name = %s, description = %s
            WHERE badge_id = %s
        """, (name, description, badge_id))

    conn.commit()
    conn.close()
    log_audit(admin_id, role, "update_badge", f"Updated badge ID {badge_id}")
    return jsonify({'message': 'Badge updated successfully'})

# Route for deleting badge
@admin_bp.route('/admin/badges/<int:badge_id>', methods=['DELETE'])
@token_required_with_roles(required_actions=["delete_badge"])
def delete_badge(admin_id, role, role_id, badge_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM badge_assignments WHERE badge_id = %s", (badge_id,))
    cursor.execute("DELETE FROM badges WHERE badge_id = %s", (badge_id,))
    conn.commit()
    conn.close()
    log_audit(admin_id, role, "delete_badge", f"Deleted badge ID {badge_id}")
    return jsonify({'message': 'Badge deleted successfully'})

# View badge (optional if needed separately)
@admin_bp.route('/admin/badges/<int:badge_id>', methods=['GET'])
@token_required_with_roles(required_actions=["view_badge"])
def view_badge(admin_id, role, role_id, badge_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM badges WHERE badge_id = %s", (badge_id,))
    badge = cursor.fetchone()
    if badge:
        column_names = [desc[0] for desc in cursor.description]
        conn.close()
        log_audit(admin_id, role, "view_badge", f"Viewed badge ID {badge_id}")
        return jsonify(dict(zip(column_names, badge)))
    else:
        conn.close()
        log_incident(admin_id, role, f"Badge not found: ID {badge_id}", severity="Low")
        return jsonify({'error': 'Badge not found'}), 404

# Route for updating learning resource
@csrf.exempt
@admin_bp.route('/learning_resources/update/<int:resource_id>', methods=['PUT'])
@token_required_with_roles(required_actions=["update_learning_resource"])
def update_learning_resource(admin_id, role, role_id, resource_id):
    try:
        data = request.get_json()
        title = data.get('title')
        description = data.get('description')
        resource_type = data.get('resource_type')
        content = data.get('content')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE learning_resources
            SET title = %s, description = %s, resource_type = %s, content = %s
            WHERE resource_id = %s
        """, (title, description, resource_type, content, resource_id))
        conn.commit()
        log_audit(admin_id, role, "update_learning_resource", f"Updated learning resource ID {resource_id}")
        return jsonify({'success': True})

    except Exception as e:
        logging.error("Error updating resource via JSON", exc_info=True)
        log_incident(admin_id, role, f"Error updating learning resource ID {resource_id}: {e}", severity="High")
        return jsonify({'success': False, 'error': 'Update failed'}), 500

    finally:
        cursor.close()
        conn.close()

# Route for deleting learning resource
@csrf.exempt
@admin_bp.route('/learning_resources/delete/<int:resource_id>', methods=['DELETE'])
@token_required_with_roles(required_actions=["delete_learning_resource"])
def delete_learning_resource(admin_id, role, role_id,resource_id):
    logging.debug(f"Received DELETE request for learning resource with ID: {resource_id}")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the resource exists before attempting delete
        cursor.execute("SELECT * FROM learning_resources WHERE resource_id = %s", (resource_id,))
        resource = cursor.fetchone()

        if not resource:
            logging.warning(f"Resource with ID {resource_id} not found.")
            log_incident(admin_id, role, f"Attempted to delete non-existent learning resource ID {resource_id}", severity="Low")
            return jsonify({'success': False, 'error': 'Resource not found'}), 404

        cursor.execute("DELETE FROM learning_resources WHERE resource_id = %s", (resource_id,))
        conn.commit()

        logging.info(f"Successfully deleted resource with ID {resource_id}")
        log_audit(admin_id, role, "delete_learning_resource", f"Deleted learning resource ID {resource_id}")
        return jsonify({'success': True})

    except Exception as e:
        logging.error(f"Error deleting resource with ID {resource_id}", exc_info=True)
        log_incident(admin_id, role, f"Error deleting learning resource ID {resource_id}: {e}", severity="High")
        return jsonify({'success': False, 'error': 'Delete failed'}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# Route for adding learning resources
@csrf.exempt
@admin_bp.route('/add_learning_resources', methods=['POST'])
@token_required_with_roles(required_actions=["add_learning_resource"])
def add_learning_resource(admin_id, role, role_id):
    conn = None
    cursor = None
    try:
        data = request.get_json()
        title = data.get('title')
        description = data.get('description')
        resource_type = data.get('resource_type')
        content = data.get('content')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO learning_resources (title, description, resource_type, content)
            VALUES (%s, %s, %s, %s)
        """, (title, description, resource_type, content))
        conn.commit()

        log_audit(admin_id, role, "add_learning_resource", f"Added learning resource '{title}'")
        return jsonify({'success': True})

    except Exception as e:
        logging.error(f"Error adding learning resource: {e}", exc_info=True)
        log_incident(admin_id, role, f"Error adding learning resource '{title if 'title' in locals() else ''}': {e}", severity="High")
        return jsonify({'success': False, 'error': 'Failed to add learning resource'})

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Route for fetching learning resources details
@admin_bp.route('/learning_resources', methods=['GET'])
@token_required_with_roles(required_actions=["get_all_learning_resources"])
def get_all_learning_resources(admin_id, role, role_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM learning_resources ORDER BY created_at DESC")
        rows = cursor.fetchall()

        resources = []
        for row in rows:
            resources.append({
                'resource_id': row[0],
                'title': row[1],
                'description': row[2],
                'resource_type': row[3],
                'content': row[4],
                'created_at': row[5].strftime('%Y-%m-%d') if row[5] else ''
            })

        log_audit(admin_id, role, "get_all_learning_resources", f"Fetched {len(resources)} learning resources")
        return jsonify(resources)

    except Exception as e:
        logging.error("Error fetching resources", exc_info=True)
        log_incident(admin_id, role, f"Error fetching all learning resources: {e}", severity="High")
        return jsonify({'error': 'Failed to load learning resources'}), 500

    finally:
        cursor.close()
        conn.close()

# Route for fetching learning resources details for viewing 
@admin_bp.route('/learning_resources/<int:resource_id>', methods=['GET'])
@token_required_with_roles(required_actions=["get_learning_resource_by_id"])
def get_learning_resource_by_id(admin_id, role, role_id,resource_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT resource_id, title, description, resource_type, content, created_at
            FROM learning_resources
            WHERE resource_id = %s
        """, (resource_id,))
        row = cursor.fetchone()

        if row:
            resource = {
                'resource_id': row[0],
                'title': row[1],
                'description': row[2],
                'resource_type': row[3],
                'content': row[4],
                'created_at': row[5].strftime('%Y-%m-%d') if row[5] else ''
            }
            log_audit(admin_id, role, "get_learning_resource_by_id", f"Viewed learning resource ID {resource_id}")
            return jsonify(resource)
        else:
            log_incident(admin_id, role, f"Learning resource not found: ID {resource_id}", severity="Low")
            return jsonify({'error': 'Resource not found'}), 404

    except Exception as e:
        logging.error("Error fetching resource by ID", exc_info=True)
        log_incident(admin_id, role, f"Error fetching learning resource by ID {resource_id}: {e}", severity="High")
        return jsonify({'error': 'Failed to fetch learning resource'}), 500

    finally:
        cursor.close()
        conn.close()

# Route for displaying assessment
@admin_bp.route('/get_assessments', methods=['GET'])
@token_required_with_roles(required_actions=["get_assessments"])
def get_assessments(admin_id, role, role_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = '''
            SELECT sa.employee_id, sa.score, sa.feedback, sa.assessment_date, 
                   tm.module_name, sa.assessment_id
            FROM skill_assessments sa
            LEFT JOIN training_modules tm ON tm.module_id = sa.module_id
        '''
        cursor.execute(query)

        assessments_data = [
            {
                "employee_id": row[0],
                "score": row[1],
                "feedback": row[2],
                "assessment_date": row[3].strftime('%Y-%m-%d') if row[3] else None,
                "module_name": row[4],
                "assessment_id": row[5]
            }
            for row in cursor.fetchall()
        ]

        # Audit log
        log_audit(admin_id, role, "get_assessments", f"Fetched {len(assessments_data)} assessments")
        return jsonify({"assessments": assessments_data}), 200

    except Exception as e:
        log_incident(admin_id, role, f"Error fetching assessments: {e}", severity="High")
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

# Route to delete a skill assessment
@csrf.exempt
@admin_bp.route("/delete_assessment/<int:assessment_id>", methods=["DELETE"])
@token_required_with_roles(required_actions=["delete_assessment"])
def delete_assessment(admin_id, role, role_id,assessment_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT 1 FROM skill_assessments WHERE assessment_id = %s", (assessment_id,))
        if not cur.fetchone():
            log_incident(admin_id, role, f"Attempted to delete non-existent assessment ID {assessment_id}", severity="Low")
            return jsonify({"error": "Assessment not found"}), 404

        cur.execute("DELETE FROM assessment_answers WHERE question_id IN (SELECT question_id FROM assessment_questions WHERE assessment_id = %s)", (assessment_id,))
        cur.execute("DELETE FROM assessment_options WHERE question_id IN (SELECT question_id FROM assessment_questions WHERE assessment_id = %s)", (assessment_id,))
        cur.execute("DELETE FROM assessment_questions WHERE assessment_id = %s", (assessment_id,))
        cur.execute("DELETE FROM skill_assessments WHERE assessment_id = %s", (assessment_id,))
        conn.commit()

        # Audit log
        log_audit(admin_id, role, "delete_assessment", f"Deleted assessment ID {assessment_id}")
        return jsonify({"success": True})

    except Exception as e:
        conn.rollback()
        log_incident(admin_id, role, f"Error deleting assessment ID {assessment_id}: {e}", severity="High")
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()

# Route to update a skill assessment
@admin_bp.route("/update_assessment/<int:assessment_id>", methods=["PUT"])
@token_required_with_roles(required_actions=["update_assessment"])
def update_assessment(admin_id, role, role_id, assessment_id):
    try:
        print(f"🛠 Received PUT request to update assessment ID: {assessment_id}")
        data = request.get_json()
        print("📦 Request JSON data:", data)

        conn = get_db_connection()
        cur = conn.cursor()

        print("🔍 Checking if assessment exists...")
        cur.execute("SELECT 1 FROM skill_assessments WHERE assessment_id = %s", (assessment_id,))
        if not cur.fetchone():
            print(f"❌ Assessment ID {assessment_id} not found.")
            log_incident(admin_id, role, f"Attempted to update non-existent assessment ID {assessment_id}", severity="Low")
            return jsonify({"error": "Assessment not found"}), 404
        print("✅ Assessment exists.")

        update_fields = []
        update_values = []

        if "assessment_date" in data and data["assessment_date"].strip():
            update_fields.append("assessment_date = %s")
            update_values.append(data["assessment_date"].strip())

        # --- Fixed score handling: allow setting to NULL and reset is_completed ---
        if "score" in data:
            score_val = data["score"]
            if score_val is None or (isinstance(score_val, str) and score_val.strip() == ""):
                update_fields.append("score = %s")
                update_values.append(None)
                update_fields.append("is_completed = %s")
                update_values.append(False)
            else:
                update_fields.append("score = %s")
                update_values.append(float(score_val))
                # Do NOT update is_completed here; business logic may require it to be set elsewhere

        if "module_id" in data and str(data["module_id"]).strip():
            update_fields.append("module_id = %s")
            update_values.append(int(data["module_id"]))

        if "feedback" in data and data["feedback"].strip():
            update_fields.append("feedback = %s")
            update_values.append(data["feedback"].strip())

        if update_fields:
            update_values.append(assessment_id)
            update_query = f"""
                UPDATE skill_assessments SET {', '.join(update_fields)} WHERE assessment_id = %s
            """
            print("📝 Executing update query for assessment:", update_query)
            print("📎 With values:", update_values)
            cur.execute(update_query, update_values)

        # --- Only update questions/options if "questions" is in the payload ---
        if "questions" in data:
            print("🔄 Processing questions update...")
            cur.execute("SELECT question_id FROM assessment_questions WHERE assessment_id = %s", (assessment_id,))
            existing_question_ids = {row[0] for row in cur.fetchall()}
            print("📚 Existing question IDs:", existing_question_ids)
            received_question_ids = set()

            for question in data.get("questions", []):
                q_text = question.get("question_text", "").strip()
                options = question.get("options", [])
                print("➕ Processing question:", q_text)

                if "question_id" in question:
                    qid = question["question_id"]
                    received_question_ids.add(qid)
                    print(f"🔧 Updating question ID {qid}")

                    cur.execute("""
                        UPDATE assessment_questions SET question_text = %s
                        WHERE question_id = %s AND assessment_id = %s
                    """, (q_text, qid, assessment_id))

                    print(f"🗑 Deleting old options for question ID {qid}")
                    cur.execute("DELETE FROM assessment_options WHERE question_id = %s", (qid,))
                    
                    for opt in options:
                        print(f"➕ Inserting option for question ID {qid}: {opt}")
                        cur.execute("""
                            INSERT INTO assessment_options (question_id, option_text, is_checked)
                            VALUES (%s, %s, %s)
                        """, (qid, opt["option_text"], opt["is_checked"]))
                else:
                    print("🆕 Inserting new question:", q_text)
                    cur.execute("""
                        INSERT INTO assessment_questions (assessment_id, question_text)
                        VALUES (%s, %s) RETURNING question_id
                    """, (assessment_id, q_text))
                    new_qid = cur.fetchone()[0]
                    print(f"✅ Inserted new question with ID {new_qid}")
                    received_question_ids.add(new_qid)

                    for opt in options:
                        print(f"➕ Inserting option for new question ID {new_qid}: {opt}")
                        cur.execute("""
                            INSERT INTO assessment_options (question_id, option_text, is_checked)
                            VALUES (%s, %s, %s)
                        """, (new_qid, opt["option_text"], opt["is_checked"]))

            questions_to_delete = existing_question_ids - received_question_ids
            print("🗑 Questions to delete:", questions_to_delete)

            for qid in questions_to_delete:
                print(f"🧹 Deleting answers and options for question ID {qid}")
                cur.execute("DELETE FROM assessment_answers WHERE question_id = %s", (qid,))
                cur.execute("DELETE FROM assessment_options WHERE question_id = %s", (qid,))
                cur.execute("DELETE FROM assessment_questions WHERE question_id = %s", (qid,))

        conn.commit()
        print("✅ Assessment update completed successfully.")

        # Audit log
        log_audit(admin_id, role, "update_assessment", f"Updated assessment ID {assessment_id}")
        return jsonify({"success": True})

    except Exception as e:
        print("🔥 Error occurred during update:", str(e))
        conn.rollback()
        log_incident(admin_id, role, f"Error updating assessment ID {assessment_id}: {e}", severity="High")
        return jsonify({"error": str(e)}), 500

    finally:
        print("🔒 Closing database connection.")
        cur.close()
        conn.close()

# Route to delete a module
@csrf.exempt
@admin_bp.route("/delete_module/<int:module_id>", methods=["DELETE"])
@token_required_with_roles(required_actions=["delete_module"])
def delete_module(admin_id, role, role_id,module_id):
    try:
        logging.debug(f"Received DELETE request for module_id: {module_id}")

        conn = get_db_connection()
        cur = conn.cursor()

        # Check if the module exists
        cur.execute("SELECT module_name FROM training_modules WHERE module_id = %s", (module_id,))
        module = cur.fetchone()
        if not module:
            logging.warning(f"Module with ID {module_id} not found.")
            log_incident(admin_id, role, f"Attempted to delete non-existent module ID {module_id}", severity="Low")
            return jsonify({"error": "Module not found"}), 404

        logging.debug(f"Deleting module: {module[0]} (ID: {module_id})")

        # Step 1: Get all assessment_ids linked to this module
        cur.execute("SELECT assessment_id FROM skill_assessments WHERE module_id = %s", (module_id,))
        assessment_ids = [row[0] for row in cur.fetchall()]

        for assessment_id in assessment_ids:
            # Step 2: Delete from assessment_answers
            cur.execute("DELETE FROM assessment_answers WHERE assessment_id = %s", (assessment_id,))
            # Step 3: Delete from assessment_options
            cur.execute("""
                DELETE FROM assessment_options 
                WHERE question_id IN (
                    SELECT question_id FROM assessment_questions WHERE assessment_id = %s
                )
            """, (assessment_id,))
            # Step 4: Delete from assessment_questions
            cur.execute("DELETE FROM assessment_questions WHERE assessment_id = %s", (assessment_id,))

        # Step 5: Delete from skill_assessments
        cur.execute("DELETE FROM skill_assessments WHERE module_id = %s", (module_id,))

        # Step 6: Delete from training_modules
        cur.execute("DELETE FROM training_modules WHERE module_id = %s", (module_id,))

        conn.commit()
        cur.close()
        conn.close()

        logging.info(f"Successfully deleted module ID {module_id}")
        # Audit log
        log_audit(admin_id, role, "delete_module", f"Deleted module ID {module_id}")
        return jsonify({"success": True})

    except Exception as e:
        logging.error(f"Error deleting module ID {module_id}: {str(e)}", exc_info=True)
        conn.rollback()
        log_incident(admin_id, role, f"Error deleting module ID {module_id}: {e}", severity="High")
        return jsonify({"error": str(e)}), 500

# Route to update a module
@csrf.exempt
@admin_bp.route("/update_module/<int:module_id>", methods=["PUT"])
@token_required_with_roles(required_actions=["update_module"])
def update_module(admin_id, role, role_id,module_id):
    try:
        data = request.get_json()
        logging.debug(f"Received PUT request for module_id {module_id} with data: {data}")

        # Validate required fields
        required_fields = ["module_name", "description", "deadline"]
        for field in required_fields:
            if field not in data or not data[field].strip():
                logging.warning(f"Missing or empty field: {field}")
                return jsonify({"error": f"Missing required field: {field}"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # Check if module exists
        cur.execute("SELECT module_id FROM training_modules WHERE module_id = %s", (module_id,))
        if not cur.fetchone():
            logging.warning(f"Module with ID {module_id} not found.")
            log_incident(admin_id, role, f"Attempted to update non-existent module ID {module_id}", severity="Low")
            return jsonify({"error": "Module not found"}), 404

        # Update the module (no status field)
        update_query = """
            UPDATE training_modules 
            SET module_name = %s, description = %s, deadline = %s, updated_at = NOW()
            WHERE module_id = %s
        """
        cur.execute(update_query, (
            data["module_name"],
            data["description"],
            data["deadline"],
            module_id
        ))

        conn.commit()
        cur.close()
        conn.close()

        logging.info(f"Successfully updated module ID {module_id}")
        # Audit log
        log_audit(admin_id, role, "update_module", f"Updated module ID {module_id}")
        return jsonify({"success": True})

    except Exception as e:
        logging.error(f"Error updating module ID {module_id}: {str(e)}", exc_info=True)
        log_incident(admin_id, role, f"Error updating module ID {module_id}: {e}", severity="High")
        return jsonify({"error": str(e)}), 500

# Route to retrieve training modules
@admin_bp.route("/get_modules", methods=["GET"])
@token_required_with_roles(required_actions=["get_modules"])
def get_modules(admin_id, role, role_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT 
                tm.module_id, tm.module_name, tm.description, tm.deadline,
                tm.created_at, tm.updated_at
            FROM training_modules tm
        """)
        modules = cur.fetchall()

        cur.close()
        conn.close()

        if not modules:
            logging.info("No training modules found in the database")
            return jsonify({"modules": []})

        module_list = []
        for row in modules:
            module = {
                "module_id": row[0],
                "module_name": row[1],
                "description": row[2],
                "deadline": row[3].isoformat() if row[3] else None,
                "created_at": row[4],
                "updated_at": row[5]
            }
            module_list.append(module)

        logging.debug(f"Fetched modules: {module_list}")

        # Audit log
        log_audit(admin_id, role, "get_modules", f"Fetched {len(module_list)} training modules")
        return jsonify({"modules": module_list})

    except Exception as e:
        logging.error(f"Error retrieving modules: {str(e)}", exc_info=True)
        log_incident(admin_id, role, f"Error retrieving modules: {e}", severity="High")
        return jsonify({'error': 'Internal server error'}), 500

# Route to get certificates
@admin_bp.route('/get_certificates', methods=['GET'])
@token_required_with_roles(required_actions=["get_certificates"])
def get_certificates(admin_id, role, role_id):
    try:
        logging.info("Fetching certificates from the database...")
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT 
                tc.certificate_id,
                e.email,
                tm.module_name,
                tc.issued_date,
                tc.certificate_status,
                e.employee_id,
                tc.module_id,
                sa.score
            FROM training_certificates tc
            JOIN employees e ON tc.employee_id = e.employee_id
            JOIN training_modules tm ON tc.module_id = tm.module_id
            LEFT JOIN skill_assessments sa ON
                sa.employee_id = tc.employee_id
        """
        logging.debug(f"Executing query:\n{query}")

        cursor.execute(query)
        certificates = cursor.fetchall()
        logging.debug(f"Raw fetched certificates: {certificates}")

        certificate_list = [
            {
                "certificate_id": row[0],
                "employee_email": row[1],
                "module_name": row[2],
                "issued_date": row[3],
                "certificate_status": row[4],
                "employee_id": row[5],
                "module_id": row[6],
                "score": row[7]
            }
            for row in certificates
        ]

        logging.info(f"Formatted certificate list: {certificate_list}")
        cursor.close()
        conn.close()

        # Audit log
        log_audit(admin_id, role, "get_certificates", f"Fetched {len(certificate_list)} certificates")
        return jsonify({"certificates": certificate_list}), 200

    except Exception as e:
        logging.error(f"Error fetching certificates: {e}", exc_info=True)
        log_incident(admin_id, role, f"Error fetching certificates: {e}", severity="High")
        return jsonify({"error": str(e)}), 500

# Route to update a certificate
@admin_bp.route('/update_certificate/<int:certificate_id>', methods=['PUT'])
@token_required_with_roles(required_actions=["update_certificate"])
def update_certificate(admin_id, role, role_id,certificate_id):
    try:
        data = request.json
        logging.info(f"Updating certificate ID {certificate_id} with data: {data}")

        conn = get_db_connection()
        cur = conn.cursor()

        # Update the training_certificates table
        logging.debug("Updating training_certificates...")
        cur.execute("""
            UPDATE training_certificates 
            SET module_id = %s, issued_date = %s, certificate_status = %s 
            WHERE certificate_id = %s
        """, (data['module_id'], data['issued_date'], data['certificate_status'], certificate_id))
        logging.debug(f"Affected rows (certificates): {cur.rowcount}")

        # Get the employee_id for this certificate to update the corresponding assessment
        cur.execute("SELECT employee_id FROM training_certificates WHERE certificate_id = %s", (certificate_id,))
        employee = cur.fetchone()
        if employee:
            employee_id = employee[0]
            score = data.get("score")

            if score is not None:
                logging.debug(f"Updating score {score} for employee_id {employee_id}, module_id {data['module_id']}")
                
                # Check if assessment exists
                cur.execute("""
                    SELECT assessment_id FROM skill_assessments
                    WHERE employee_id = %s AND module_id = %s
                """, (employee_id, data['module_id']))
                assessment = cur.fetchone()

                if assessment:
                    # Update existing assessment
                    cur.execute("""
                        UPDATE skill_assessments
                        SET score = %s
                        WHERE employee_id = %s AND module_id = %s
                    """, (score, employee_id, data['module_id']))
                    logging.debug(f"Affected rows (assessment update): {cur.rowcount}")
                else:
                    # Insert new assessment if none exists
                    cur.execute("""
                        INSERT INTO skill_assessments (employee_id, module_id, score)
                        VALUES (%s, %s, %s)
                    """, (employee_id, data['module_id'], score))
                    logging.debug("Inserted new assessment row")

        conn.commit()
        cur.close()
        conn.close()

        logging.info(f"Certificate ID {certificate_id} updated successfully")
        # Audit log
        log_audit(admin_id, role, "update_certificate", f"Updated certificate ID {certificate_id}")
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Error updating certificate {certificate_id}: {e}", exc_info=True)
        log_incident(admin_id, role, f"Error updating certificate ID {certificate_id}: {e}", severity="High")
        return jsonify({"error": str(e)}), 500

# Route to delete a certificate
@admin_bp.route('/delete_certificate/<int:certificate_id>', methods=['DELETE'])
@token_required_with_roles(required_actions=["delete_certificate"])
def delete_certificate(admin_id, role, role_id,certificate_id):
    try:
        logging.info(f"Deleting certificate ID {certificate_id}")
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM training_certificates WHERE certificate_id = %s", (certificate_id,))
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()

        if deleted == 0:
            log_incident(admin_id, role, f"Attempted to delete non-existent certificate ID {certificate_id}", severity="Low")
            return jsonify({"error": "Certificate not found"}), 404

        logging.info(f"Certificate ID {certificate_id} deleted successfully")
        # Audit log
        log_audit(admin_id, role, "delete_certificate", f"Deleted certificate ID {certificate_id}")
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Error deleting certificate {certificate_id}: {e}")
        log_incident(admin_id, role, f"Error deleting certificate ID {certificate_id}: {e}", severity="High")
        return jsonify({"error": str(e)}), 500
    
# Route for displaying assessment details
@admin_bp.route("/get_assessment_details/<int:assessment_id>")
@token_required_with_roles(required_actions=["get_assessment_details"])
def get_assessment_details(admin_id, role, role_id,assessment_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Fetch assessment info
        cur.execute("""
            SELECT sa.assessment_id, sa.employee_id, sa.module_id, tm.module_name, 
                   sa.assessment_date, sa.score, sa.feedback, sa.score, e.email
            FROM skill_assessments sa
            LEFT JOIN training_modules tm ON sa.module_id = tm.module_id
            LEFT JOIN employees e ON e.employee_id = sa.employee_id
            WHERE sa.assessment_id = %s
        """, (assessment_id,))
        result = cur.fetchone()

        if not result:
            log_incident(admin_id, role, f"Assessment not found: assessment_id {assessment_id}", severity="Low")
            return jsonify({"success": False, "message": "Assessment not found"}), 404

        assessment = {
            "assessment_id": result[0],
            "employee_id": result[1],
            "module_id": result[2],
            "skill_name": result[3],
            "assessment_date": result[4].isoformat() if result[4] else None,
            "score": result[5],
            "feedback": result[6],
            "score": result[7],
            "email": result[8],
            "questions": []
        }

        # Fetch questions and options
        cur.execute("""
            SELECT q.question_id, q.question_text, o.option_id, o.option_text, o.is_checked
            FROM assessment_questions q
            LEFT JOIN assessment_options o ON q.question_id = o.question_id
            WHERE q.assessment_id = %s
        """, (assessment_id,))

        question_map = {}
        for q_id, q_text, opt_id, opt_text, is_checked in cur.fetchall():
            if q_id not in question_map:
                question_map[q_id] = {
                    "question_id": q_id,
                    "question_text": q_text,
                    "options": []
                }
            if opt_id is not None:
                question_map[q_id]["options"].append({
                    "option_id": opt_id,
                    "option_text": opt_text,
                    "is_checked": is_checked
                })

        assessment["questions"] = list(question_map.values())
        # Audit log
        log_audit(admin_id, role, "get_assessment_details", f"Viewed assessment details for assessment_id {assessment_id}")
        return jsonify({"success": True, "assessment": assessment})

    except Exception as e:
        log_incident(admin_id, role, f"Error fetching assessment details for assessment_id {assessment_id}: {e}", severity="High")
        return jsonify({"success": False, "message": str(e)}), 500

# Route for certificate issue 
@admin_bp.route('/issue_certificate', methods=['POST'])
@token_required_with_roles(required_actions=["issue_certificate"])
def issue_certificate(admin_id, role, role_id):
    data = request.json
    logging.debug("Received data: %s", data)

    employee_id = data.get('employee_id')
    module_id = data.get('module_id')
    issued_date = data.get('issued_date')
    certificate_status = data.get('certificate_status')

    if not all([employee_id, module_id, issued_date, certificate_status]):
        logging.error("Missing required fields: employee_id=%s, module_id=%s, issued_date=%s, certificate_status=%s", 
                      employee_id, module_id, issued_date, certificate_status)
        return jsonify({"error": "All fields are required"}), 400

    try:
        logging.debug("Establishing database connection...")
        conn = get_db_connection()
        cursor = conn.cursor()

        logging.debug("Inserting certificate into training_certificates table: employee_id=%s, module_id=%s, issued_date=%s, certificate_status=%s", 
                      employee_id, module_id, issued_date, certificate_status)
        
        cursor.execute("""
            INSERT INTO training_certificates (employee_id, module_id, issued_date, certificate_status)
            VALUES (%s, %s, %s, %s)
        """, (employee_id, module_id, issued_date, certificate_status))

        conn.commit()

        cursor.close()
        conn.close()

        logging.debug("Database connection closed.")
        # Audit log
        log_audit(admin_id, role, "issue_certificate", f"Issued certificate to employee_id {employee_id} for module_id {module_id}")
        return jsonify({"message": "Certificate issued successfully"}), 201

    except Exception as e:
        logging.error("Error while issuing certificate: %s", str(e))
        log_incident(admin_id, role, f"Error issuing certificate to employee_id {employee_id} for module_id {module_id}: {e}", severity="High")
        return jsonify({"error": str(e)}), 500
    
# Route for assigning assessment
@admin_bp.route('/assign_assessment', methods=['POST'])
@token_required_with_roles(required_actions=["assign_assessment"])
def assign_assessment(admin_id, role, role_id):
    import traceback
    import json

    data = request.get_json()
    print(f"🔎 Received request data: {data}")
    conn = get_db_connection()
    cursor = conn.cursor()
    debug_info = {}

    try:
        employee_id = data.get('employee_id')
        module_id = data.get('module_id')
        assessment_date = data.get('assessment_date')
        # score = data.get('score')  # IGNORE any incoming score!
        feedback = data.get('feedback', '')
        questions = data.get('questions', [])

        debug_info['employee_id'] = employee_id
        debug_info['module_id'] = module_id
        debug_info['assessment_date'] = assessment_date
        debug_info['score'] = None      # Always None on assignment
        debug_info['feedback'] = feedback
        debug_info['questions_count'] = len(questions)

        print(f"🔎 Parsed fields: {json.dumps(debug_info)}")

        if not all([employee_id, module_id, assessment_date, questions]):
            print(f"⚠️ Missing required data: {json.dumps(debug_info)}")
            return jsonify({"success": False, "message": "Missing required data!", "debug": debug_info}), 400

        # Insert assessment with score always NULL (None)
        print(f"🟡 Inserting skill_assessments: ({employee_id}, {module_id}, {assessment_date}, None, {feedback})")
        cursor.execute("""
            INSERT INTO skill_assessments (employee_id, module_id, assessment_date, score, feedback)
            VALUES (%s, %s, %s, %s, %s) RETURNING assessment_id
        """, (employee_id, module_id, assessment_date, None, feedback))
        assessment_id = cursor.fetchone()[0]
        print(f"🟢 Inserted skill_assessments: assessment_id={assessment_id}")

        # Insert questions and options
        question_ids = []
        for idx, q in enumerate(questions):
            question_text = q.get("question_text")
            options = q.get("options", [])
            print(f"🟡 Inserting assessment_question {idx+1}: '{question_text}' (options: {len(options)})")

            cursor.execute("""
                INSERT INTO assessment_questions (question_text, assessment_id)
                VALUES (%s, %s) RETURNING question_id
            """, (question_text, assessment_id))
            question_id = cursor.fetchone()[0]
            print(f"🟢 Inserted assessment_question: question_id={question_id}")
            question_ids.append(question_id)

            for opt_idx, opt in enumerate(options):
                option_text = opt.get("option_text")
                is_checked = opt.get("is_checked", False)
                print(f"    🟡 Inserting option {opt_idx+1}: '{option_text}', is_checked={is_checked}")

                cursor.execute("""
                    INSERT INTO assessment_options (question_id, option_text, is_checked)
                    VALUES (%s, %s, %s)
                """, (question_id, option_text, is_checked))

        conn.commit()
        print(f"✅ Committed all inserts for assessment_id={assessment_id}")
        # Audit: log assessment assignment
        log_audit(admin_id, role, "assign_assessment", f"Assigned assessment to employee {employee_id} for module {module_id}")

        return jsonify({"success": True, "message": "Assessment assigned successfully!", "debug": debug_info}), 201

    except Exception as e:
        conn.rollback()
        error_trace = traceback.format_exc()
        print("❌ Error assigning assessment:", e)
        print(error_trace)
        log_incident(admin_id, role, f"Error assigning assessment: {e}\nTraceback:\n{error_trace}", severity="High")
        return jsonify({"success": False, "message": f"Error: {str(e)}", "debug": debug_info, "trace": error_trace}), 500

    finally:
        cursor.close()
        conn.close()

# Route to insert a training module
@csrf.exempt
@admin_bp.route('/insert_module', methods=['POST'])
@token_required_with_roles(required_actions=["insert_module"])
def insert_module(admin_id, role, role_id):
    try:
        if not request.is_json:
            logging.error("Request does not contain valid JSON")
            return jsonify({'error': 'Invalid request. Expected JSON'}), 400

        data = request.get_json(silent=True)
        if not data:
            logging.error("Received empty JSON request body")
            return jsonify({'error': 'Empty request body'}), 400

        logging.debug(f"Received data: {data}")

        module_name = data.get('module_name')
        module_description = data.get('module_description')
        module_deadline = data.get('module_deadline')

        logging.debug(f"Module name: {module_name}, Module description: {module_description}, Module deadline: {module_deadline}")

        if not module_name or not module_description or not module_deadline:
            logging.warning("Missing required fields in request")
            return jsonify({'error': 'Missing required fields'}), 400

        conn = get_db_connection()
        logging.debug("Database connection established.")

        cursor = conn.cursor()
        logging.debug("Cursor created for database interaction.")

        cursor.execute(
            "INSERT INTO training_modules (module_name, description, deadline) VALUES (%s, %s, %s)",
            (module_name, module_description, module_deadline)
        )
        conn.commit()
        logging.debug("Database commit successful.")

        logging.info(f"Module '{module_name}' inserted successfully")

        cursor.close()
        conn.close()
        logging.debug("Database connection closed.")

        # Audit: log module insertion
        log_audit(admin_id, role, "insert_module", f"Inserted module '{module_name}'")

        return jsonify({'message': 'Module added successfully'}), 200

    except Exception as e:
        logging.error(f"Error inserting module: {str(e)}", exc_info=True)
        log_incident(admin_id, role, f"Error inserting module: {e}", severity="High")
        return jsonify({'error': 'Internal server error'}), 500
