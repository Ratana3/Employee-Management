from datetime import datetime, timedelta
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

# Route for displaying goal details for a specific employee 
@admin_bp.route('/get_team_goals', methods=['GET'])
@token_required_with_roles(required_actions=["get_team_goals"])
def get_team_goals(admin_id, role, role_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("Fetching goals from database...")  

        cursor.execute("""
            SELECT t.team_id, t.team_name,
                   g.goal_id, g.time_bound_goal, g.status, g.goal_name, g.description,
                   g.specific_goal, g.measurable_goal, g.achievable_goal, g.relevant_goal,
                   g.created_at, g.updated_at,
                   gpp.progress_percentage_id, gpp.progress_percentage, gpp.percentage_created_at, gpp.percentage_updated_at,
                   ge.final_score, ge.lessons_learned, ge.action_plan, ge.course
            FROM teams t
            LEFT JOIN goals g ON g.team_id = t.team_id AND g.employee_id IS NULL
            LEFT JOIN goal_progress_percentage gpp ON gpp.goal_id = g.goal_id
            LEFT JOIN goal_evaluations ge ON ge.goal_id = g.goal_id
        """)

        team_goals = cursor.fetchall()
        print(f"Total goals fetched: {len(team_goals)}")  

        team_goal_list = {}

        for team_goal in team_goals:
            team_goal_id = team_goal[2]  # goal_id
            if not team_goal_id:
                continue

            if team_goal_id not in team_goal_list:
                team_goal_list[team_goal_id] = {
                    "team_id": team_goal[0],
                    "team_name": team_goal[1],
                    "goal_id": team_goal[2],
                    "time_bound_goal": team_goal[3],
                    "status": team_goal[4],
                    "goal_name": team_goal[5],
                    "description": team_goal[6],
                    "specific_goal": team_goal[7],
                    "measurable_goal": team_goal[8],
                    "achievable_goal": team_goal[9],
                    "relevant_goal": team_goal[10],
                    "created_at": team_goal[11],
                    "updated_at": team_goal[12],
                    "progress_percentage_id": team_goal[13],
                    "progress_percentage": team_goal[14] if team_goal[14] is not None else 0,
                    "percentage_created_at": team_goal[15],
                    "percentage_updated_at": team_goal[16],
                    "final_score": team_goal[17] if team_goal[17] is not None else "",
                    "lessons_learned": team_goal[18] if team_goal[18] is not None else "",
                    "action_plan": team_goal[19] if team_goal[19] is not None else "",
                    "course": team_goal[20] if team_goal[20] is not None else "",
                    "notes": [],
                    "feedback": []
                }

        print("Fetching notes...")  
        cursor.execute("""
            SELECT goal_id, note_description, notes_created_at, note_id
            FROM goal_progress_notes
            ORDER BY note_id DESC
        """)
        notes = cursor.fetchall()

        for note in notes:
            team_goal_id = note[0]
            if team_goal_id in team_goal_list:
                team_goal_list[team_goal_id]["notes"].append({
                    "note_description": note[1],
                    "notes_created_at": note[2],
                    "note_id": note[3]
                })

        print("Fetching feedback...")  
        cursor.execute("""
            SELECT goal_id, feedback_description, feedback_created_at, feedback_id, feedback_updated_at
            FROM goal_progress_feedback
        """)
        feedbacks = cursor.fetchall()

        for feedback in feedbacks:
            team_goal_id = feedback[0]
            if team_goal_id in team_goal_list:
                team_goal_list[team_goal_id]["feedback"].append({
                    "feedback_description": feedback[1],
                    "feedback_date": feedback[2],
                    "feedback_id": feedback[3],
                    "feedback_updated_at": feedback[4]
                })

        cursor.close()
        conn.close()

        # Audit: log successful fetch of team goals
        log_audit(admin_id, role, "get_team_goals", "Fetched team goals and related notes/feedback.")

        return jsonify(list(team_goal_list.values()))  # Convert to list before returning JSON

    except Exception as e:
        print("Error fetching team goals:", str(e))
        # Incident: log error fetching team goals
        log_incident(admin_id, role, f"Error fetching team goals: {str(e)}", severity="High")
        return jsonify({"error": "Failed to fetch team goals"}), 500

#route for updating goal's progress for a specific employee's goal
@csrf.exempt
@admin_bp.route('/update_progress/<int:goal_id>', methods=['PUT'])
@token_required_with_roles(required_actions=["update_progress"])
def update_progress(admin_id, role, role_id,goal_id):
    logging.debug(f"[START] Received request to update progress for goal_id: {goal_id} by admin_id: {admin_id}")

    try:
        data = request.json
        logging.debug(f"[REQUEST] Data received: {data}")

        if not data or "progress_percentage" not in data:
            logging.error("[ERROR] Missing 'progress_percentage' in request data")
            return jsonify({"error": "Missing 'progress_percentage' in request data"}), 400

        new_progress = data.get("progress_percentage")
        logging.debug(f"[VALIDATION] Extracted progress_percentage: {new_progress}")

        if not isinstance(new_progress, (int, float)) or not (0 <= new_progress <= 100):
            logging.error(f"[ERROR] Invalid progress_percentage: {new_progress}")
            return jsonify({"error": "progress_percentage must be a number between 0 and 100"}), 400

        # Determine the new status based on progress percentage
        if new_progress == 0:
            new_status = "Not Started"
        elif 1 <= new_progress <= 99:
            new_status = "Pending"
        else:
            new_status = "Completed"
        logging.debug(f"[STATUS UPDATE] New status determined: {new_status}")

        conn = get_db_connection()
        cursor = conn.cursor()
        logging.debug("[DB] Database connection established.")

        # ** Update goal_progress_percentage and goals in a single transaction **
        update_progress_query = """
            UPDATE goal_progress_percentage
            SET progress_percentage = %s, percentage_updated_at = NOW()
            WHERE goal_id = %s
            RETURNING goal_id;
        """
        logging.debug(f"[QUERY] Executing: {update_progress_query} with values ({new_progress}, {goal_id})")

        cursor.execute(update_progress_query, (new_progress, goal_id))
        updated_goal = cursor.fetchone()

        if not updated_goal:
            logging.warning(f"[WARNING] No progress record found for goal_id: {goal_id}")
            return jsonify({"error": "No progress record found for the given goal_id"}), 404

        # Update goal status in goals table
        update_goal_status_query = """
            UPDATE goals
            SET status = %s
            WHERE goal_id = %s;
        """
        logging.debug(f"[QUERY] Updating goal status for goal_id {goal_id} to {new_status}")
        cursor.execute(update_goal_status_query, (new_status, goal_id))

        conn.commit()
        logging.debug("[DB] Database commit successful.")

        # Audit: log successful update
        log_audit(admin_id, role, "update_progress", f"Goal progress for goal_id {goal_id} updated to {new_progress}% with status {new_status}")

        return jsonify({"message": "Progress and status updated successfully"}), 200

    except psycopg2.DatabaseError as e:
        if 'conn' in locals():
            conn.rollback()
        logging.exception(f"[DB ERROR] Database error occurred: {e}")
        # Incident: log db error
        log_incident(admin_id, role, f"Database error updating progress for goal_id {goal_id}: {str(e)}", severity="High")
        return jsonify({"error": "Database error occurred"}), 500

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        logging.exception(f"[ERROR] Unexpected error: {e}")
        # Incident: log generic error
        log_incident(admin_id, role, f"Unexpected error updating progress for goal_id {goal_id}: {str(e)}", severity="High")
        return jsonify({"error": "An unexpected error occurred"}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
            logging.debug("[DB] Database cursor closed.")
        if 'conn' in locals():
            conn.close()
            logging.debug("[DB] Database connection closed.")

@csrf.exempt
@admin_bp.route('/edit_note/<int:note_id>', methods=['PUT'])
@token_required_with_roles(required_actions=["edit_note"])
def edit_note(admin_id, role, role_id,note_id):
    data = request.json
    new_description = data.get('note_description')

    if not new_description:
        logging.error("[ERROR] Missing note description in request")
        return jsonify({"error": "Note description is required"}), 400

    logging.debug(f"[EDIT NOTE] Editing note with note_id: {note_id}, new description: {new_description}, by admin_id: {admin_id}")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Fetch the original note before updating
        cur.execute("SELECT note_description FROM goal_progress_notes WHERE note_id = %s", (note_id,))
        original_note = cur.fetchone()

        if not original_note:
            logging.error(f"[ERROR] Note with note_id {note_id} not found")
            return jsonify({"error": "Note not found"}), 404

        original_description = original_note[0]

        # Update the note
        cur.execute("""
            UPDATE goal_progress_notes
            SET note_description = %s, notes_updated_at = NOW()
            WHERE note_id = %s
        """, (new_description, note_id))

        conn.commit()
        logging.debug("[DB] Note updated successfully.")

        # Audit: log successful note edit
        log_audit(admin_id, role, "edit_note", f"Edited note_id {note_id}. Original: '{original_description}'. Updated: '{new_description}'")

    except Exception as e:
        conn.rollback()
        logging.exception(f"[ERROR] Error editing note with note_id {note_id}: {e}")
        # Incident: log error on note edit
        log_incident(admin_id, role, f"Error editing note_id {note_id}: {str(e)}", severity="High")
        return jsonify({"error": "Failed to update note"}), 500

    finally:
        cur.close()
        conn.close()

    return jsonify({"message": "Note updated successfully"}), 200

@csrf.exempt
@admin_bp.route('/delete_note/<int:note_id>', methods=['DELETE'])
@token_required_with_roles(required_actions=["delete_note"])
def delete_note(admin_id, role, role_id,note_id):
    logging.debug(f"[START] Received request to delete note with note_id: {note_id} by admin_id: {admin_id}")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Fetch the note before deleting
        cur.execute("SELECT note_description FROM goal_progress_notes WHERE note_id = %s", (note_id,))
        note = cur.fetchone()

        if not note:
            logging.error(f"[ERROR] Note with note_id {note_id} not found")
            return jsonify({"error": "Note not found"}), 404

        note_description = note[0]

        # Delete the note
        cur.execute("DELETE FROM goal_progress_notes WHERE note_id = %s", (note_id,))
        conn.commit()
        logging.debug(f"[DB] Note with note_id {note_id} deleted successfully.")

        # Log the action for auditing
        log_audit(admin_id, role, "delete_note",
                  f"Deleted note_id {note_id}. Content: '{note_description}'")

    except Exception as e:
        conn.rollback()
        logging.exception(f"[ERROR] Error deleting note with note_id {note_id}: {e}")
        # Incident: log error deleting note
        log_incident(admin_id, role, f"Error deleting note_id {note_id}: {str(e)}", severity="High")
        return jsonify({"error": "Failed to delete note"}), 500

    finally:
        cur.close()
        conn.close()

    return jsonify({"message": "Note deleted successfully"}), 200

#route updating goal evaluation for specific employee or team
@csrf.exempt
@admin_bp.route('/update_goal_evaluation', methods=['PUT'])
@token_required_with_roles(required_actions=["update_goal_evaluation"])
def update_goal_evaluation(admin_id, role, role_id):
    try:
        data = request.get_json()
        goal_id = data.get('goal_id')
        final_score = data.get('final_score')
        lessons_learned = data.get('lessons_learned')
        course = data.get('course')
        action_plan = data.get('action_plan')

        logging.debug(f"[REQUEST] Received data for updating goal evaluation: {data}")

        if not goal_id or final_score is None:
            logging.error("[ERROR] Missing required fields: goal_id or final_score")
            return jsonify({'error': 'Missing required fields'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT final_score, lessons_learned, action_plan, course FROM goal_evaluations WHERE goal_id = %s", (goal_id,))
        original_evaluation = cursor.fetchone()

        if not original_evaluation:
            logging.warning(f"[WARNING] Goal evaluation with goal_id {goal_id} not found")
            return jsonify({"error": "Goal evaluation not found"}), 404

        original_final_score, original_lessons_learned, original_action_plan, original_course = original_evaluation

        cursor.execute("""
            UPDATE goal_evaluations 
            SET final_score = %s, lessons_learned = %s, action_plan = %s, course = %s, updated_at = NOW()
            WHERE goal_id = %s
        """, (final_score, lessons_learned, action_plan, course, goal_id))

        conn.commit()

        log_audit(admin_id, role, "update_goal_evaluation", 
                  f"Goal evaluation for goal_id {goal_id} updated. "
                  f"Final Score: {original_final_score} -> {final_score}, "
                  f"Lessons Learned: '{original_lessons_learned}' -> '{lessons_learned}', "
                  f"Action Plan: '{original_action_plan}' -> '{action_plan}', "
                  f"Course: '{original_course}' -> '{course}'")

        return jsonify({'success': True, 'message': 'Goal evaluation updated successfully'}), 200

    except Exception as e:
        logging.error(f"[ERROR] Error updating goal evaluation: {str(e)}")
        # Incident: log error updating goal evaluation
        log_incident(admin_id, role, f"Error updating goal evaluation for goal_id {goal_id}: {str(e)}", severity="High")
        return jsonify({'error': str(e)}), 500

    finally:
        cursor.close()
        conn.close()

#route to get goal evaluation for a specific employee or team
@admin_bp.route('/get_goal_evaluation', methods=['GET'])
@token_required_with_roles(required_actions=["get_goal_evaluation"])
def get_goal_evaluation(admin_id, role, role_id):
    goal_id = request.args.get('goal_id')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT final_score, lessons_learned, action_plan, course FROM goal_evaluations WHERE goal_id = %s", (goal_id,))
        result = cursor.fetchone()
        if result:
            evaluation = dict(zip(['final_score', 'lessons_learned', 'action_plan', 'course'], result))
            # Audit: log successful fetch
            log_audit(admin_id, role, "get_goal_evaluation", f"Fetched goal evaluation for goal_id={goal_id}")
            return jsonify({'success': True, 'evaluation': evaluation})
        else:
            # Incident: log not found
            log_incident(admin_id, role, f"Goal evaluation not found for goal_id={goal_id}", severity="Low")
            return jsonify({'success': False, 'message': 'No evaluation found'}), 404
    except Exception as e:
        # Incident: log error
        log_incident(admin_id, role, f"Error fetching goal evaluation for goal_id={goal_id}: {str(e)}", severity="High")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


#route for deleting feedback for a specific goal
@csrf.exempt
@admin_bp.route('/delete_feedback/<int:feedback_id>', methods=['DELETE'])
@token_required_with_roles(required_actions=["delete_feedback"])
def delete_feedback(admin_id, role, role_id,feedback_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        logging.debug(f"[REQUEST] Attempting to delete feedback with ID: {feedback_id}")
        print(f"DEBUG: Extracted admin_id: {admin_id}")

        # Check if feedback exists
        cursor.execute("SELECT * FROM goal_progress_feedback WHERE feedback_id = %s", (feedback_id,))
        feedback = cursor.fetchone()

        if not feedback:
            logging.warning(f"[WARNING] Feedback with ID {feedback_id} not found")
            # Incident: log not found
            log_incident(admin_id, role, f"Feedback with ID {feedback_id} not found", severity="Low")
            return jsonify({"error": "Feedback not found"}), 404

        feedback_description = feedback[1]  # Adjust index as per schema
        log_audit(admin_id, role, "delete_feedback", f"Feedback with ID {feedback_id} and description '{feedback_description}' is about to be deleted")

        cursor.execute("DELETE FROM goal_progress_feedback WHERE feedback_id = %s", (feedback_id,))
        conn.commit()

        logging.debug(f"[DB] Feedback with ID {feedback_id} deleted successfully.")
        # Audit: log successful delete
        log_audit(admin_id, role, "delete_feedback", f"Feedback with ID {feedback_id} deleted")

        return jsonify({"message": "Feedback deleted successfully"}), 200

    except Exception as e:
        # Incident: log error
        log_incident(admin_id, role, f"Error deleting feedback with ID {feedback_id}: {str(e)}", severity="High")
        logging.error(f"[ERROR] Error in delete_feedback: {str(e)}")
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

# Edit Feedback route for a specific goal
@csrf.exempt
@admin_bp.route('/edit_feedback/<int:feedback_id>', methods=['PUT'])
@token_required_with_roles(required_actions=["edit_feedback"])
def edit_feedback(admin_id, role, role_id,feedback_id):
    try:
        data = request.json
        new_feedback = data.get("feedback_description")

        if not new_feedback:
            logging.error("[ERROR] Feedback description is required")
            return jsonify({"error": "Feedback description is required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        logging.debug(f"[REQUEST] Attempting to update feedback {feedback_id} with: {new_feedback}")

        # Check if feedback exists
        cursor.execute("SELECT * FROM goal_progress_feedback WHERE feedback_id = %s", (feedback_id,))
        feedback = cursor.fetchone()

        if not feedback:
            logging.warning(f"[WARNING] Feedback with ID {feedback_id} not found")
            # Incident: log not found
            log_incident(admin_id, role, f"Feedback with ID {feedback_id} not found", severity="Low")
            return jsonify({"error": "Feedback not found"}), 404

        original_feedback = feedback[1]  # Adjust index as per schema

        cursor.execute("UPDATE goal_progress_feedback SET feedback_description = %s, feedback_updated_at = NOW() WHERE feedback_id = %s", 
                       (new_feedback, feedback_id))
        conn.commit()

        if cursor.rowcount == 0:
            logging.warning(f"[WARNING] No changes made to feedback with ID {feedback_id}")
            return jsonify({"error": "No changes made"}), 400

        logging.debug(f"[DB] Feedback with ID {feedback_id} updated successfully.")

        # Audit: log successful feedback edit
        log_audit(admin_id, role, "edit_feedback", f"Feedback with ID {feedback_id} updated FROM '{original_feedback}' TO '{new_feedback}'")

        return jsonify({"message": "Feedback updated successfully"}), 200

    except Exception as e:
        logging.error(f"[ERROR] Error in edit_feedback: {str(e)}")
        # Incident: log error
        log_incident(admin_id, role, f"Error editing feedback_id {feedback_id}: {str(e)}", severity="High")
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

# route for submitting feedback about a specific employee's goal
@csrf.exempt
@admin_bp.route('/submit_feedback', methods=['POST'])
@token_required_with_roles(required_actions=["submit_feedback"])
def submit_feedback(admin_id, role, role_id):
    try:
        data = request.json
        goal_id = data.get("goal_id")
        feedback_description = data.get("feedback_description")

        print(f"DEBUG: Extracted admin_id: {admin_id}")

        logging.debug(f"[REQUEST] Data received: goal_id={goal_id}, feedback_description={feedback_description}, admin_id={admin_id}")

        if not goal_id or not feedback_description:
            logging.error("[ERROR] Missing goal_id or feedback_description in request data")
            return jsonify({"error": "Missing goal_id or feedback_description in request data"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        logging.debug(f"[QUERY] Checking if goal_id {goal_id} exists in goal_progress table")

        cursor.execute("SELECT * FROM goal_progress WHERE goal_id = %s", (goal_id,))
        goal_exists = cursor.fetchone()

        if not goal_exists:
            logging.warning(f"[WARNING] Goal ID {goal_id} not found in goal_progress table")
            # Incident: log not found
            log_incident(admin_id, role, f"Goal ID {goal_id} not found in goal_progress table", severity="Low")
            cursor.close()
            conn.close()
            return jsonify({"error": "Goal ID not found"}), 400

        logging.debug(f"[QUERY] Inserting feedback for goal_id {goal_id}")

        cursor.execute("""
            INSERT INTO goal_progress_feedback (goal_id, feedback_description, feedback_created_at, employee_id, team_id)
            VALUES (%s, %s, NOW(), %s, %s)
        """, (goal_id, feedback_description, data.get("employee_id"), data.get("team_id")))

        conn.commit()
        logging.debug("[DB] Feedback inserted successfully.")

        # Audit: log successful feedback submission
        log_audit(admin_id, role, "submit_feedback", f"Feedback for goal_id {goal_id} submitted with description: {feedback_description}")

        cursor.close()
        conn.close()

        return jsonify({"message": "Feedback submitted successfully"}), 201

    except Exception as e:
        logging.error(f"[ERROR] An error occurred: {str(e)}")
        # Incident: log error
        log_incident(admin_id, role, f"Error submitting feedback for goal_id {goal_id}: {str(e)}", severity="High")
        return jsonify({"error": "An unexpected error occurred"}), 500

# Route for displaying goal details for a specific employee 
@admin_bp.route('/get_goals', methods=['GET'])
@token_required_with_roles(required_actions=["get_goals"])
def get_goals(admin_id, role, role_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("Fetching goals from database...")  # Debugging

        cursor.execute("""
            SELECT e.employee_id, e.email, e.team_id,
                   t.team_id, t.team_name,
                   g.goal_id, g.time_bound_goal, g.status, g.goal_name, g.description,
                   g.specific_goal, g.measurable_goal, g.achievable_goal, g.relevant_goal,
                   g.created_at, g.updated_at,
                   gpp.progress_percentage_id, gpp.progress_percentage, gpp.percentage_created_at, gpp.percentage_updated_at,
                   ge.final_score, ge.lessons_learned, ge.action_plan, ge.course
            FROM employees e
            LEFT JOIN teams t ON t.team_id = e.team_id
            LEFT JOIN goals g ON g.employee_id = e.employee_id
            LEFT JOIN goal_progress_percentage gpp ON gpp.employee_id = g.employee_id AND gpp.goal_id = g.goal_id
            LEFT JOIN goal_evaluations ge ON ge.goal_id = g.goal_id
        """)

        goals = cursor.fetchall()
        print(f"Total goals fetched: {len(goals)}")  # Debugging

        goal_list = {}

        for goal in goals:
            goal_id = goal[5]
            if not goal_id:
                continue

            if goal_id not in goal_list:
                goal_list[goal_id] = {
                    "goal_id": goal_id,
                    "employee_id": goal[0],
                    "email": goal[1],
                    "team_id": goal[2],
                    "team_name": goal[4],
                    "time_bound_goal": goal[6],
                    "status": goal[7],
                    "goal_name": goal[8],
                    "description": goal[9],
                    "specific_goal": goal[10],
                    "measurable_goal": goal[11],
                    "achievable_goal": goal[12],
                    "relevant_goal": goal[13],
                    "created_at": goal[14],
                    "updated_at": goal[15],
                    "progress_percentage": goal[17] if goal[17] is not None else 0,
                    "progress_created_at": goal[18],
                    "progress_updated_at": goal[19],
                    "final_score": goal[20] if goal[20] is not None else "",
                    "lessons_learned": goal[21] if goal[21] is not None else "",
                    "action_plan": goal[22] if goal[22] is not None else "",
                    "course": goal[23] if goal[23] is not None else "",
                    "notes": [],
                    "feedback": []
                }

        print("Fetching notes...")  # Debugging
        cursor.execute("""
            SELECT goal_id, note_description, notes_created_at, note_id
            FROM goal_progress_notes
            ORDER BY note_id DESC
        """)
        notes = cursor.fetchall()
        print(f"Total notes fetched: {len(notes)}")  # Debugging

        for note in notes:
            goal_id = note[0]
            if goal_id in goal_list:
                goal_list[goal_id]["notes"].append({
                    "note_description": note[1],
                    "notes_created_at": note[2],
                    "note_id": note[3]
                })

        print("Fetching feedback...")  # Debugging
        cursor.execute("""
            SELECT goal_id, feedback_description, feedback_created_at, feedback_id, feedback_updated_at
            FROM goal_progress_feedback
        """)
        feedbacks = cursor.fetchall()
        print(f"Total feedbacks fetched: {len(feedbacks)}")  # Debugging

        for feedback in feedbacks:
            goal_id = feedback[0]
            if goal_id in goal_list:
                goal_list[goal_id]["feedback"].append({
                    "feedback_description": feedback[1],
                    "feedback_date": feedback[2],
                    "feedback_id": feedback[3],
                    "feedback_updated_at": feedback[4]
                })

        cursor.close()
        conn.close()

        print("Returning goal data...")  # Debugging

        # Audit: log successful fetch of goals
        log_audit(admin_id, role, "get_goals", "Fetched individual goals, notes, and feedback.")

        return jsonify(list(goal_list.values()))
    
    except Exception as e:
        print(f"Error in get_goals: {str(e)}")  # Debugging
        # Incident: log error
        log_incident(admin_id, role, f"Error fetching goals: {str(e)}", severity="High")
        return jsonify({"error": str(e)}), 500
    
# Route for editing performance review details
@csrf.exempt
@admin_bp.route('/edit_review/<int:review_id>', methods=['POST'])
@token_required_with_roles(required_actions=["edit_review"])
def edit_review(admin_id, role, role_id,review_id):
    logging.debug(f"Received request to edit review with ID: {review_id}")

    try:
        data = request.json
        logging.debug(f"Request data: {data}")

        if not data or not all(key in data for key in ["review_date", "feedback", "rating", "employee_id"]):
            logging.error("Missing required fields: review_date, feedback, rating, or employee_id.")
            return jsonify({"error": "Missing required fields"}), 400

        review_date = data["review_date"]
        feedback = data["feedback"]
        rating = data["rating"]
        employee_id = data["employee_id"]

        conn = get_db_connection()
        cursor = conn.cursor()
        logging.debug("Database connection established.")

        update_query = """
            UPDATE performance_reviews
            SET employee_id = %s, review_date = %s, feedback = %s, rating = %s
            WHERE review_id = %s
            RETURNING review_id;
        """
        cursor.execute(update_query, (employee_id, review_date, feedback, rating, review_id))
        updated_review = cursor.fetchone()

        if not updated_review:
            logging.warning(f"No review found for review_id: {review_id}")
            log_incident(admin_id, role, f"No review found for review_id={review_id}", severity="Low")
            return jsonify({"error": "No review found for the given review_id"}), 404

        conn.commit()
        action_details = f"Edited review ID {review_id}: Employee ID {employee_id}, Rating: {rating}"
        log_audit(admin_id, role, 'edit_review', action_details)

        return jsonify({"message": "Review updated successfully"}), 200

    except psycopg2.DatabaseError as e:
        if 'conn' in locals():
            conn.rollback()
        logging.exception(f"Database error occurred: {e}")
        log_incident(admin_id, role, f"Database error editing review {review_id}: {str(e)}", severity="High")
        return jsonify({"error": "Database error occurred"}), 500

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        logging.exception(f"Unexpected error: {e}")
        log_incident(admin_id, role, f"Unexpected error editing review {review_id}: {str(e)}", severity="High")
        return jsonify({"error": "An unexpected error occurred"}), 500

    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

# Route for deleting performance review
@csrf.exempt
@admin_bp.route('/delete_review/<int:review_id>', methods=['DELETE'])
@token_required_with_roles(required_actions=["delete_review"])
def delete_review(admin_id=None, role=None, role_id=None,review_id=None):
    logging.debug(f"Received request to delete review with ID: {review_id}")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        delete_query = """
            DELETE FROM performance_reviews
            WHERE review_id = %s
            RETURNING employee_id, rating;
        """
        cursor.execute(delete_query, (review_id,))
        deleted_review = cursor.fetchone()

        if not deleted_review:
            logging.warning(f"No review found for review_id: {review_id}")
            log_incident(admin_id, role, f"No review found for review_id={review_id}", severity="Low")
            return jsonify({"error": "No review found for the given review_id"}), 404

        conn.commit()
        employee_id, rating = deleted_review
        action_details = f"Deleted review ID {review_id}: Employee ID {employee_id}, Rating: {rating}"
        log_audit(admin_id, role, 'delete_review', action_details)

        return jsonify({"message": "Review deleted successfully"}), 200

    except psycopg2.DatabaseError as e:
        if 'conn' in locals():
            conn.rollback()
        logging.exception(f"Database error occurred: {e}")
        log_incident(admin_id, role, f"Database error deleting review {review_id}: {str(e)}", severity="High")
        return jsonify({"error": "Database error occurred"}), 500

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        logging.exception(f"Unexpected error: {e}")
        log_incident(admin_id, role, f"Unexpected error deleting review {review_id}: {str(e)}", severity="High")
        return jsonify({"error": "An unexpected error occurred"}), 500

    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

#route for deleting a goal 
@csrf.exempt
@admin_bp.route('/delete_goal/<int:goal_id>', methods=['DELETE'])
@token_required_with_roles(required_actions=["delete_goal"])
def delete_goal(admin_id, role, role_id,goal_id):
    logging.info(f"Attempting to delete goal with ID: {goal_id}")
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Delete dependent records first (if ON DELETE CASCADE not defined in DB)
        cur.execute("DELETE FROM goal_progress_feedback WHERE goal_id = %s", (goal_id,))
        cur.execute("DELETE FROM goal_progress_notes WHERE goal_id = %s", (goal_id,))
        cur.execute("DELETE FROM goal_progress WHERE goal_id = %s", (goal_id,))
        cur.execute("DELETE FROM goal_progress_percentage WHERE goal_id = %s", (goal_id,))
        cur.execute("DELETE FROM goal_evaluations WHERE goal_id = %s", (goal_id,))

        # Delete the goal last
        cur.execute("DELETE FROM goals WHERE goal_id = %s", (goal_id,))
        conn.commit()

        log_audit(admin_id, role, 'delete_goal', f'Deleted goal with ID {goal_id}')
        return jsonify({"message": "Goal deleted successfully"}), 200

    except psycopg2.DatabaseError as db_err:
        conn.rollback()
        logging.exception(f"Database error while deleting goal: {db_err}")
        log_incident(admin_id, role, f"Database error deleting goal {goal_id}: {db_err}", severity="High")
        return jsonify({"error": "Database error occurred while deleting goal"}), 500

    except Exception as e:
        conn.rollback()
        logging.exception(f"Unexpected error while deleting goal: {e}")
        log_incident(admin_id, role, f"Unexpected error deleting goal {goal_id}: {e}", severity="High")
        return jsonify({"error": "Unexpected error occurred while deleting goal"}), 500

    finally:
        cur.close()
        conn.close()


#route for assigning goals to employees and teams
@csrf.exempt
@admin_bp.route('/assign_goal', methods=['POST'])
@token_required_with_roles(required_actions=["assign_goal"])
def assign_goal(admin_id, role, role_id):
    logging.debug("Received request to assign goal.")

    try:
        # Get form data
        goal_name = request.form.get('goal_name')
        description = request.form.get('description')
        specific_goal = request.form.get('specific_goal')
        measurable_goal = request.form.get('measurable_goal')
        achievable_goal = request.form.get('achievable_goal')
        relevant_goal = request.form.get('relevant_goal')
        time_bound_goal = request.form.get('time_bound_goal')
        employee_or_team = request.form.get('employee_or_team')

        logging.debug(f"Form Data Received: goal_name={goal_name}, description={description}, "
                      f"specific_goal={specific_goal}, measurable_goal={measurable_goal}, "
                      f"achievable_goal={achievable_goal}, relevant_goal={relevant_goal}, "
                      f"time_bound_goal={time_bound_goal}, employee_or_team={employee_or_team}")

        if not all([goal_name, description, specific_goal, measurable_goal, achievable_goal, relevant_goal, time_bound_goal, employee_or_team]):
            logging.error("Missing required form fields.")
            return jsonify({"error": "Missing required form fields"}), 400

        employee_id = request.form.get('employee_id') if employee_or_team == 'employee' else None
        team_id = request.form.get('team_id') if employee_or_team == 'team' else None

        logging.debug(f"Assigning goal to {'employee' if employee_id else 'team'}: employee_id={employee_id}, team_id={team_id}")

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO goals (goal_name, description, specific_goal, measurable_goal, achievable_goal, 
                               relevant_goal, time_bound_goal, employee_id, team_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Not Started') RETURNING goal_id
        """, (goal_name, description, specific_goal, measurable_goal, achievable_goal,
              relevant_goal, time_bound_goal, employee_id, team_id))
        goal_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO goal_progress_percentage (progress_percentage, percentage_created_at, percentage_updated_at, employee_id, team_id, goal_id)
            VALUES (0, NOW(), NOW(), %s, %s, %s) RETURNING progress_percentage_id
        """, (employee_id, team_id, goal_id))
        progress_percentage_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO goal_progress (goal_id, employee_id, team_id, progress_percentage_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
        """, (goal_id, employee_id, team_id, progress_percentage_id))

        cur.execute("""
            INSERT INTO goal_evaluations (goal_id, final_score, lessons_learned, action_plan, course)
            VALUES (%s, %s, %s, %s, %s)
        """, (goal_id, 'Not assigned yet', 'Not assigned yet', 'Not assigned yet', 'Not assigned yet'))

        conn.commit()
        log_audit(
            admin_id, role, 'assign_goal',
            f"Assigned goal '{goal_name}' to {'Employee ID: ' + str(employee_id) if employee_id else 'Team ID: ' + str(team_id)}"
        )
        return jsonify({"message": "Goal assigned successfully"}), 200

    except psycopg2.DatabaseError as db_err:
        conn.rollback()
        logging.exception(f"Database error occurred: {db_err}")
        log_incident(admin_id, role, f"Database error assigning goal '{goal_name}': {db_err}", severity="High")
        return jsonify({"error": f"Database Error: {db_err}"}), 500

    except Exception as e:
        conn.rollback()
        logging.exception(f"Unexpected error: {e}")
        log_incident(admin_id, role, f"Unexpected error assigning goal '{goal_name}': {e}", severity="High")
        return f"Unexpected Error: {e}", 500

    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()


# route to display the details of performance reviewed by 
@admin_bp.route('/perfomancemanagement_data', methods=['GET'])
@token_required_with_roles(required_actions=["performance_data"])
def performance_data(admin_id, role, role_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch employees
    cur.execute("SELECT employee_id, email FROM employees")
    employees = [{"employee_id": row[0], "email": row[1]} for row in cur.fetchall()]

    # Fetch teams
    cur.execute("SELECT team_id, team_name FROM teams")
    teams = [{"team_id": row[0], "team_name": row[1]} for row in cur.fetchall()]

    # Fetch performance reviews
    cur.execute("""
        SELECT pr.review_id, pr.employee_id, pr.review_date, pr.feedback, pr.rating, e.email, 
               COALESCE(t.team_name, 'No Team') AS team_name
        FROM performance_reviews pr
        JOIN employees e ON pr.employee_id = e.employee_id
        LEFT JOIN teams t ON e.team_id = t.team_id
    """)
    reviews = [
        {
            "review_id": row[0],
            "employee_id": row[1],
            "review_date": row[2].strftime("%Y-%m-%d"),
            "feedback": row[3],
            "rating": row[4],
            "employee_email": row[5],
            "team_name": row[6]
        }
        for row in cur.fetchall()
    ]

    cur.close()
    conn.close()

    # Audit: log successful performance data fetch
    log_audit(admin_id, role, "performance_data", "Fetched performance management data (employees, teams, reviews)")

    return jsonify({
        "employees": employees,
        "teams": teams,
        "reviews": reviews,
        "admin_id": admin_id,
        "admin_role": role
    })

#route for rendering a page for checkin employee's performance
@admin_bp.route('/perfomancemanagement', methods=['GET'])
def performance_page():
    return render_template('Admin/PerformanceManagement.html')


# Route to submit performance review
@csrf.exempt
@admin_bp.route('/submit_review', methods=['POST'])
@token_required_with_roles(required_actions=["submit_review"])
def submit_review(admin_id, role, role_id):
    try:
        data = request.json
        print(f"DEBUG: Incoming request data: {data}")  # Log incoming request

        employee_id = data.get('employee_id')
        review_date = data.get('review_date')
        feedback = data.get('feedback')
        rating = data.get('rating')
        reviewer = f"{role}, ID: {role_id}"

        if not (employee_id and review_date and feedback and rating):
            print("DEBUG: Missing required fields")
            return jsonify({"error": "All fields are required"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        print(f"DEBUG: Extracted admin_id: {admin_id}")  # Log admin ID

        sql_query = """
            INSERT INTO performance_reviews (employee_id, review_date, feedback, rating,reviewer)
            VALUES (%s, %s, %s, %s,%s);
        """
        values = (employee_id, review_date, feedback, rating,reviewer)
        print(f"DEBUG: Executing SQL Query: {sql_query} with values {values}")

        cur.execute(sql_query, values)
        conn.commit()
        print("DEBUG: Database commit successful")

        action_details = f"Submitted performance review for Employee ID {employee_id} with rating {rating}"
        print(f"DEBUG: Logging audit: {action_details}")
        log_audit(admin_id, role, 'submit_review', action_details)

        cur.close()
        conn.close()
        print("DEBUG: Database connection closed")

        return jsonify({"message": "Performance review submitted successfully"}), 201

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        print(traceback.format_exc())

        if 'conn' in locals():
            conn.rollback()
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

        return jsonify({"error": str(e)}), 500
  

# Route for fetching task details for employee or team
@admin_bp.route('/get_tasks', methods=['GET'])
@token_required_with_roles(required_actions=["get_tasks"])
def get_tasks(admin_id, role, role_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                t.task_id, 
                t.task_name, 
                t.description, 
                e.email AS assigned_employee, 
                tm.team_name, 
                t.progress, 
                t.status,
                tp.part_id, 
                tp.part_name, 
                tp.part_percentage
            FROM tasks t
            LEFT JOIN employees e ON t.employee_id = e.employee_id
            LEFT JOIN teams tm ON t.team_id = tm.team_id
            LEFT JOIN task_parts tp ON t.task_id = tp.task_id
            ORDER BY 
                CASE 
                    WHEN e.email IS NOT NULL THEN e.email 
                    WHEN tm.team_name IS NOT NULL THEN tm.team_name 
                    ELSE 'Unassigned'
                END,
                t.task_name
        """)

        tasks = cursor.fetchall()
        cursor.close()
        conn.close()

        grouped = {}
        # Use a nested dict: grouped[assigned_to][task_id] = task_data
        for task in tasks:
            assigned_to = task[3] or task[4] or "Unassigned"
            if assigned_to not in grouped:
                grouped[assigned_to] = {}

            task_id = task[0]
            if task_id not in grouped[assigned_to]:
                grouped[assigned_to][task_id] = {
                    "task_id": task[0],
                    "name": task[1],
                    "description": task[2],
                    "progress": task[5],
                    "status": task[6],
                    "task_parts": []
                }

            # Add the part if it exists
            if task[7]:
                grouped[assigned_to][task_id]["task_parts"].append({
                    "task_part_id": task[7],
                    "part_name": task[8],
                    "part_percentage": task[9]
                })

        # Convert inner dicts to lists for output
        grouped_final = {k: list(v.values()) for k, v in grouped.items()}
        return jsonify(grouped_final)

    except Exception as e:
        print(f"Error fetching tasks: {str(e)}")  # Log the error for debugging
        return jsonify({"error": "Internal Server Error"}), 500
    
# Route to fetch employees
@admin_bp.route('/get_employees', methods=['GET'])
@token_required_with_roles(required_actions=["get_employees"])
def get_employees(admin_id, role, role_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT employee_id, email FROM employees")
    employees = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify([{"employee_id": emp[0], "email": emp[1] if emp[1] else ""} for emp in employees])

# Route to fetch teams
@admin_bp.route('/get_teams', methods=['GET'])
@token_required_with_roles(required_actions=["get_teams"])
def get_teams(admin_id, role, role_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT team_id, team_name FROM teams")
    teams = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify([{"team_id": team[0], "team_name": team[1]} for team in teams])

#route for assigning tasks 
@csrf.exempt
@admin_bp.route('/assign_task', methods=['POST'])
@token_required_with_roles(required_actions=["assign_task"])
def assign_task(admin_id, role, role_id):
    try:
        data = request.json
        print(f"DEBUG: Incoming request data: {data}")

        task_name = data.get('task_name')
        description = data.get('description')
        assigned_to = data.get('assigned_to')
        assigned_ids = data.get('assigned_ids')  # {'employee_ids': [], 'team_ids': []}
        due_date = data.get('due_date')
        task_parts = data.get('task_parts', [])
        is_project = data.get('is_project', False)

        project_id = None
        project_name = data.get('project_name')
        project_description = data.get('project_description')
        project_start_date = data.get('start_date')
        project_end_date = data.get('end_date')

        if not task_name or not description or not assigned_to:
            return jsonify({'error': 'Missing required fields'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now()
        task_ids_created = []
        duplicates_skipped = []

        if is_project:
            if not project_name or not project_description or not project_start_date or not project_end_date:
                return jsonify({'error': 'Missing project details'}), 400

            cursor.execute("""
                INSERT INTO projects (project_name, description, start_date, end_date, status)
                VALUES (%s, %s, %s, %s, 'Pending') RETURNING project_id
            """, (project_name, project_description, project_start_date, project_end_date))
            project_id = cursor.fetchone()[0]
            print(f"DEBUG: New project created with ID {project_id}")
            log_audit(admin_id, role, 'create_project', f"Created project '{project_name}'")

        def insert_task(emp_id=None, team_id=None):
            # Check for duplicates first
            if emp_id:
                cursor.execute("SELECT task_id FROM tasks WHERE employee_id = %s AND task_name = %s", (emp_id, task_name))
            elif team_id:
                cursor.execute("SELECT task_id FROM tasks WHERE team_id = %s AND task_name = %s", (team_id, task_name))

            if cursor.fetchone():
                duplicates_skipped.append({'employee_id': emp_id, 'team_id': team_id, 'reason': 'Duplicate task'})
                return  # skip, don't raise error

            cursor.execute("""
                INSERT INTO tasks (task_name, description, employee_id, assigned_date, due_date, status, progress, team_id, project_id)
                VALUES (%s, %s, %s, %s, %s, 'Pending', 0, %s, %s) RETURNING task_id
            """, (task_name, description, emp_id, now, due_date, team_id, project_id))
            task_id = cursor.fetchone()[0]
            task_ids_created.append(task_id)

            for part in task_parts:
                if part.get("part_name") and part.get("part_percentage"):
                    cursor.execute("""
                        INSERT INTO task_parts (task_id, part_name, part_percentage, completed)
                        VALUES (%s, %s, %s, FALSE)
                    """, (task_id, part["part_name"], part["part_percentage"]))

            assigned = f"employee_id {emp_id}" if emp_id else f"team_id {team_id}"
            log_audit(admin_id, role, 'assign_task', f"Assigned task '{task_name}' to {assigned}")

        # Perform assignment based on type
        if assigned_to in ['employee', 'both']:
            for emp_id in assigned_ids.get("employee_ids", []):
                insert_task(emp_id=int(emp_id))

        if assigned_to in ['team', 'both']:
            for team_id in assigned_ids.get("team_ids", []):
                insert_task(team_id=int(team_id))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'message': 'Task assignment completed',
            'assigned_task_ids': task_ids_created,
            'skipped_duplicates': duplicates_skipped,
            'project_id': project_id
        }), 201

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

#route for updating task 
@csrf.exempt
@admin_bp.route('/update_task/<int:task_id>', methods=['PUT'])
@token_required_with_roles(required_actions=["update_task"])
def update_task(admin_id, role, role_id,task_id):
    try:
        data = request.json
        print(f"Received update data for task {task_id}: {data}")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT task_name, description, due_date, progress, status FROM tasks WHERE task_id = %s", (task_id,))
        existing = cursor.fetchone()
        if not existing:
            return jsonify({"error": "Task not found"}), 404

        task_name = data.get('task_name', existing[0])
        description = data.get('description', existing[1])
        due_date = data.get('due_date', existing[2])
        progress = data.get('progress', existing[3])
        status = data.get('status', existing[4])

        cursor.execute("""
            UPDATE tasks
            SET task_name = %s, description = %s, due_date = %s, progress = %s, status = %s
            WHERE task_id = %s
        """, (task_name, description, due_date, progress, status, task_id))

        if "task_parts" in data:
            cursor.execute("DELETE FROM task_parts WHERE task_id = %s", (task_id,))
            for part in data["task_parts"]:
                cursor.execute("""
                    INSERT INTO task_parts (task_id, part_name, part_percentage, completed)
                    VALUES (%s, %s, %s, %s)
                """, (task_id, part["part_name"], part["part_percentage"], False))

        log_audit(admin_id, role, 'update_task', f"Updated task {task_id}")
        conn.commit()
        return jsonify({"message": "Task updated successfully"})

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Route for deleting task
@csrf.exempt
@admin_bp.route('/delete_task/<int:task_id>', methods=['DELETE'])
@token_required_with_roles(required_actions=["delete_task"])
def delete_task(admin_id, role, role_id,task_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM task_parts WHERE task_id = %s", (task_id,))
        cursor.execute("DELETE FROM tasks WHERE task_id = %s", (task_id,))

        log_audit(admin_id, role, 'delete_task', f"Deleted task {task_id}")
        conn.commit()
        return jsonify({"message": "Task deleted successfully"})

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        # Incident: log error deleting task
        log_incident(admin_id, role, f"Error deleting task {task_id}: {str(e)}", severity="High")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Route for deleting a specific task part
@csrf.exempt
@admin_bp.route('/delete_task_part/<int:task_part_id>', methods=['DELETE'])
@token_required_with_roles(required_actions=["delete_task_part"])
def delete_task_part(admin_id, role, role_id,task_part_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM task_parts WHERE part_id = %s", (task_part_id,))

        log_audit(admin_id, role, 'delete_task_part', f"Deleted task part {task_part_id}")
        conn.commit()
        return jsonify({"message": "Task part deleted successfully"})

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        # Incident: log error deleting task part
        log_incident(admin_id, role, f"Error deleting task part {task_part_id}: {str(e)}", severity="High")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Route for adding new task part for existing tasks
@csrf.exempt
@admin_bp.route('/add_task_part', methods=['POST'])
@token_required_with_roles(required_actions=["add_task_part"])
def add_task_part(admin_id, role, role_id):
    data = request.get_json()

    task_id = data.get('task_id')
    part_name = data.get('part_name')
    part_percentage = data.get('part_percentage')

    if not all([task_id, part_name, part_percentage]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO task_parts (task_id, part_name, part_percentage, completed)
            VALUES (%s, %s, %s, %s)
        """, (task_id, part_name, part_percentage, False))

        log_audit(admin_id, role, 'add_task_part', f"Added part '{part_name}' to task {task_id}")
        conn.commit()

        return jsonify({'success': True}), 201

    except Exception as e:
        logging.error(f"Error adding task part: {e}", exc_info=True)
        # Incident: log error adding task part
        log_incident(admin_id, role, f"Error adding task part to task {task_id}: {str(e)}", severity="High")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

    finally:
        cursor.close()
        conn.close()
        
# Performance management ( End )