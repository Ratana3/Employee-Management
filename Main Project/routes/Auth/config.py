from datetime import datetime, timedelta
import logging
import os

from flask import jsonify

from routes.Auth.utils import get_db_connection

# ============== Folder for storing expense claims,tickets that are submitted by employees ==============

UPLOAD_FOLDER = os.path.join('static', 'ExpenseClaimsUploads')  # Store in static/uploads
UPLOAD_FOLDER_TICKETS = os.path.join('static', 'Tickets')  # adjust path as needed

# ============== Folder for storing expense claims,tickets that are submitted by employees ==============


# ============ Github Token & Repository Setup ============

## Example Config
GITHUB_TOKEN = 'yourtoken'
GITHUB_REPO = 'Username/repositoryname'

#---

## How to Create a New Repository

#1. Log in to GitHub with your account.
#2. On the top right, click the **+** icon, then select **"New repository"**.
#3. Fill out the repository name (e.g., `testing`).  
#   Optionally, add a description.
#4. Choose **Public** or **Private** visibility.
#5. (Optional) Check "Add a README file" for easier setup.
#6. Click **"Create repository"**.
#7. Your repository is now created!  
#   Example: `VonxBone/testing`

#---

## How to Get a New Token

# 1. Log in to GitHub with your account.
# 2. Go to **Settings > Developer settings > Personal access tokens**.
# 3. Click **"Fine-grained tokens"** or **"Personal access tokens (classic)"**  
#    *(Classic is still widely used, but fine-grained is more secure and recommended.)*
# 4. Click **"Generate new token"**.
# 5. Give it a name (e.g., `employee-issue-token`).
# 6. Set the expiration (recommended: 30 days, or as needed).
# 7. Select the repository you want to allow issue creation for.
# 8. Under **Repository permissions**, set at least:
#    - **Issues:** Read and write
# 9. Generate the token.
# 10. **Copy the token! You will not be able to see it again.**

# ============ Github Token & Repository Setup ============



# Directory for tax documents
TAX_DOCS_FOLDER = "TaxDocuments"
os.makedirs(TAX_DOCS_FOLDER, exist_ok=True)
UPLOAD_FOLDER = 'static/badges'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
HEALTH_RESOURCES = 'static/health_resources'
os.makedirs(HEALTH_RESOURCES, exist_ok=True)
HEALTH_RESOURCES_FILE_PATH = os.path.join(os.getcwd(), HEALTH_RESOURCES)
# Document Repository Configuration
DOCUMENT_REPOSITORY = 'static/DocumentRepository'
os.makedirs(DOCUMENT_REPOSITORY, exist_ok=True)
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'xlsx', 'pptx', 'txt', 'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Configuration for backing up database

#Path for storing the backup
BACKUP_DIR = "D:/EmployeeAttendance/Backups"

#Database that uses to backup 
# Note: This could be different from the one you use in get_db_connection() 
# so make sure u set the correct database to backup inside here
# changing database inside get_db_connection() , it only changes the database u use for the system
# for backup , u have to change the database here 
DB_HOST = "localhost"
DB_NAME = "YourDatabaseName"
DB_USER = "Username"
DB_PASSWORD = "123"
# Full path to pg_dump (Update it according to your PostgreSQL version)
PG_DUMP_PATH = r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"
PG_PSQL_PATH = "C:/Program Files/PostgreSQL/17/bin/psql.exe"  # Adjust path accordingly
PG_RESTORE_PATH = r"C:\Program Files\PostgreSQL\17\bin\pg_restore.exe"
os.makedirs(BACKUP_DIR, exist_ok=True)

# Route to generate goal evaluation automatically
def generate_goal_evaluation(goal_id):
    """
    Automatically generates a goal evaluation based on progress percentage.
    Admins can later edit the evaluation and recommend courses.
    """
    try:
        # Check if goal_id is provided in the request JSON, else use the passed goal_id
        if not goal_id or not str(goal_id).isdigit():
            return jsonify({'error': 'Invalid goal_id'}), 400
        
        goal_id = int(goal_id)
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get the latest progress percentage
        cursor.execute("""
            SELECT gpp.progress_percentage
            FROM goal_progress_percentage gpp
            WHERE gpp.goal_id = %s
            ORDER BY gpp.percentage_updated_at DESC
            LIMIT 1
        """, (goal_id,))
        
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'No progress found for this goal'}), 404

        progress_percentage = result[0]
        
        # Determine the evaluation text based on progress
        if progress_percentage == 0:
            final_score = "Not Yet Started"
            lessons_learned = "No work has been initiated yet."
            action_plan = "Begin initial steps to start working on this goal."
        elif 0 < progress_percentage < 50:
            final_score = "Needs Improvement"
            lessons_learned = "Progress is slow; need to improve focus and efficiency."
            action_plan = "Set weekly milestones to track progress more effectively."
        elif 50 <= progress_percentage < 80:
            final_score = "On Track"
            lessons_learned = "Goal is progressing well, but more effort is needed."
            action_plan = "Maintain momentum and address any blockers proactively."
        elif 80 <= progress_percentage < 100:
            final_score = "Almost Completed"
            lessons_learned = "Goal is close to completion; final refinements needed."
            action_plan = "Wrap up the final steps and ensure quality completion."
        else:  # 100%
            final_score = "Completed"
            lessons_learned = "Goal successfully achieved with all requirements met."
            action_plan = "Review the process and document key takeaways for future improvements."

        
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert into goal_evaluations
        cursor.execute("""
            INSERT INTO goal_evaluations (goal_id, final_score, lessons_learned, action_plan, created_at, course)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (goal_id) DO UPDATE 
            SET final_score = EXCLUDED.final_score,
                lessons_learned = EXCLUDED.lessons_learned,
                action_plan = EXCLUDED.action_plan,
                created_at = EXCLUDED.created_at
        """, (goal_id, final_score, lessons_learned, action_plan, created_at, "No recommended course"))

        conn.commit()
        cursor.close()
        conn.close()

        return {'success': True, 'message': 'Goal evaluation generated successfully'}

    except Exception as e:
        logging.error(f"Error in generate_goal_evaluation: {str(e)}")
        return {'error': str(e)}


# Route to generate action plans automatically
def generate_action_plan(goal_id):
    """
    Automatically generates an action plan for a goal based on evaluation.
    """
    try:
        # Check if goal_id is provided in the request JSON, else use the passed goal_id
        if not goal_id or not str(goal_id).isdigit():
            return jsonify({'error': 'Invalid goal_id'}), 400
        
        goal_id = int(goal_id)
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get the latest evaluation for reference
        cursor.execute("""
            SELECT action_plan FROM goal_evaluations WHERE goal_id = %s
        """, (goal_id,))
        eval_result = cursor.fetchone()

        if not eval_result:
            return jsonify({'error': 'No evaluation found for this goal'}), 404

        action_plan_text = eval_result[0]
        due_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')  # Default due in 30 days
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert default action plan
        cursor.execute("""
            INSERT INTO goal_action_plans (goal_id, action_item, due_date, status, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (goal_id) DO UPDATE 
            SET action_item = EXCLUDED.action_item,
                due_date = EXCLUDED.due_date,
                status = EXCLUDED.status,
                created_at = EXCLUDED.created_at
        """, (goal_id, action_plan_text, due_date, "Pending", created_at))

        conn.commit()
        cursor.close()
        conn.close()

        return {'success': True, 'message': 'Action plan generated successfully'}

    except Exception as e:
        logging.error(f"Error in generate_action_plan: {str(e)}")
        return {'error': 'An error occurred while updating progress'}


def format_datetime(value):
    """Format datetime to AM/PM, Day, Month, Year"""
    if value:
        return value.strftime('%I:%M %p, %A, %B %d, %Y')  # Example: 02:30 PM, Monday, February 11, 2025
    return None
