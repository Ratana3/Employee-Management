from datetime import datetime, timedelta
import logging
import os
import traceback
import bcrypt
from flask import Blueprint, Response, current_app, render_template, jsonify, request, send_file, send_from_directory, url_for
from fpdf import FPDF
import psycopg2
from routes.Auth.audit import log_audit, log_incident
from routes.Auth.token import get_admin_from_token, token_required_with_roles, token_required_with_roles_and_2fa
from routes.Auth.utils import get_db_connection
from routes.Auth.config import TAX_DOCS_FOLDER
from . import admin_bp
from extensions import csrf
from PIL import Image
import io
from werkzeug.utils import secure_filename
from psycopg2.extras import RealDictCursor

# function to generate tax
def compute_salary_tax(gross_income):
    brackets = [
        (1300000, 0.00),
        (2000000, 0.05),
        (8500000, 0.10),
        (12500000, 0.15),
        (float('inf'), 0.20)
    ]
    remaining = gross_income
    tax = 0
    last_limit = 0
    for limit, rate in brackets:
        if remaining <= 0:
            break
        income_in_bracket = min(limit - last_limit, remaining)
        tax += income_in_bracket * rate
        remaining -= income_in_bracket
        last_limit = limit
    return round(tax, 2)


    
@admin_bp.route('/payrollandfinancialmanagement', methods=['GET', 'POST'])
def payrollandfinancial():
    return render_template('Admin/payrollandfinancial.html')

# route for responding to request change for savings plan
@csrf.exempt
@admin_bp.route('/admin/respond_savings_plan_request/<int:request_id>', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["respond_savings_plan_request"])
def respond_savings_plan_request(admin_id, role, role_id, request_id):
    import logging
    from datetime import datetime

    # Setup logger
    logger = logging.getLogger("respond_savings_plan_request")
    logger.info(f"[{datetime.now().isoformat()}] Called respond_savings_plan_request with request_id={request_id}")

    # Debug: Log request headers and method
    logger.debug(f"[{datetime.now().isoformat()}] Request method: {request.method}")
    logger.debug(f"[{datetime.now().isoformat()}] Request headers: {dict(request.headers)}")

    # Debug: Log raw data if JSON parsing fails
    try:
        data = request.get_json(force=True)
        logger.info(f"[{datetime.now().isoformat()}] Incoming data: {data}")
    except Exception as e:
        logger.error(f"[{datetime.now().isoformat()}] Failed to parse JSON: {e}")
        logger.error(f"[{datetime.now().isoformat()}] Raw data: {request.data}")
        return jsonify({'error': 'Invalid JSON'}), 400

    response_text = data.get('response')
    status = data.get('status')
    reviewed_by = f"{role}, ID: {admin_id}"

    logger.info(f"[{datetime.now().isoformat()}] Parsed values - response: {response_text}, status: {status}, reviewed_by: {reviewed_by}")

    if not response_text or not status:
        logger.warning(f"[{datetime.now().isoformat()}] Missing response or status. Response: {response_text}, Status: {status}")
        log_incident(
            admin_id, role,
            f"Attempted to respond to savings plan request {request_id} with missing response or status.",
            severity="Low"
        )
        return jsonify({'error': 'Response and status are required.'}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            logger.info(f"[{datetime.now().isoformat()}] Executing UPDATE for request_id={request_id}")
            cur.execute("""
                UPDATE savings_plan_requests
                SET response=%s, status=%s, reviewed_by=%s, reviewed_at=NOW()
                WHERE request_id=%s
            """, (response_text, status, reviewed_by, request_id))
            logger.info(f"[{datetime.now().isoformat()}] UPDATE executed, rowcount={cur.rowcount}")

        conn.commit()
        logger.info(f"[{datetime.now().isoformat()}] Commit successful for request_id={request_id}")
        log_audit(
            admin_id, role,
            "respond_savings_plan_request",
            f"Responded to savings plan request {request_id} with status '{status}'."
        )
        # Debug: Return rowcount
        return jsonify({'message': 'Request response recorded successfully!', 'updated_rows': cur.rowcount})
    except Exception as e:
        conn.rollback()
        logger.error(f"[{datetime.now().isoformat()}] Exception occurred: {e}", exc_info=True)
        log_incident(
            admin_id, role,
            f"Error responding to savings plan request {request_id}: {e}",
            severity="High"
        )
        return jsonify({'error': str(e)}), 500

# Delete a savings plan request (admin only)
@csrf.exempt
@admin_bp.route('/admin/delete_savings_plan_request/<int:request_id>', methods=['DELETE'])
@token_required_with_roles_and_2fa(required_actions=["delete_savings_plan_request"])
def delete_savings_plan_request(admin_id, role, role_id, request_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM savings_plan_requests WHERE request_id = %s", (request_id,))
            if cur.rowcount == 0:
                return jsonify({"error": "Request not found"}), 404
        conn.commit()
        return jsonify({"message": "Request deleted successfully"})
    except Exception as e:
        conn.rollback()
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
     
# route for deleting the saving plans
@csrf.exempt
@admin_bp.route('/admin/delete_savings_plan/<int:plan_id>', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["delete_savings_plan"])
def delete_savings_plan(admin_id, role, role_id, plan_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM savings_plans WHERE plan_id = %s", (plan_id,))
        conn.commit()
        log_audit(
            admin_id, role,
            "delete_savings_plan",
            f"Deleted savings plan with plan_id={plan_id}"
        )
        return jsonify({'message': 'Savings plan deleted successfully'})
    except Exception as e:
        conn.rollback()
        log_incident(
            admin_id, role,
            f"Error deleting savings plan with plan_id={plan_id}: {e}",
            severity="High"
        )
        return jsonify({'error': str(e)}), 500

# route for updating the saving plans
@csrf.exempt
@admin_bp.route('/admin/update_savings_plan/<int:plan_id>', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["update_savings_plan"])
def update_savings_plan(admin_id, role, role_id, plan_id):
    logger = logging.getLogger("update_savings_plan")
    debug_time = datetime.now().isoformat()
    logger.info(f"[{debug_time}] Called update_savings_plan for plan_id={plan_id} by admin_id={admin_id}")

    # Log all form fields and files for debugging
    logger.debug(f"[{debug_time}] request.form: {dict(request.form)}")
    logger.debug(f"[{debug_time}] request.files: {[f for f in request.files]}")

    fields = {}
    document_path = None

    # Log each field assignment
    if request.form.get('employee_id'):
        fields['employee_id'] = request.form.get('employee_id')
        logger.debug(f"[{debug_time}] employee_id set: {fields['employee_id']}")
    if request.form.get('plan_type'):
        fields['plan_type'] = request.form.get('plan_type')
        logger.debug(f"[{debug_time}] plan_type set: {fields['plan_type']}")
    if request.form.get('provider'):
        fields['provider'] = request.form.get('provider')
        logger.debug(f"[{debug_time}] provider set: {fields['provider']}")
    # Contribution Amount, Unit, Percent
    if request.form.get('contribution_amount'):
        fields['contribution_amount'] = request.form.get('contribution_amount')
        logger.debug(f"[{debug_time}] contribution_amount set: {fields['contribution_amount']}")
    if request.form.get('contribution_unit'):
        fields['contribution_unit'] = request.form.get('contribution_unit')
        logger.debug(f"[{debug_time}] contribution_unit set: {fields['contribution_unit']}")
    if request.form.get('contribution_percent'):
        fields['contribution_percent'] = request.form.get('contribution_percent')
        logger.debug(f"[{debug_time}] contribution_percent set: {fields['contribution_percent']}")
    # Employer Match Amount, Unit, Percent
    if request.form.get('employer_match_amount'):
        fields['employer_match_amount'] = request.form.get('employer_match_amount')
        logger.debug(f"[{debug_time}] employer_match_amount set: {fields['employer_match_amount']}")
    if request.form.get('employer_match_unit'):
        fields['employer_match_unit'] = request.form.get('employer_match_unit')
        logger.debug(f"[{debug_time}] employer_match_unit set: {fields['employer_match_unit']}")
    if request.form.get('employer_match_percent'):
        fields['employer_match_percent'] = request.form.get('employer_match_percent')
        logger.debug(f"[{debug_time}] employer_match_percent set: {fields['employer_match_percent']}")
    if request.form.get('status'):
        fields['status'] = request.form.get('status')
        logger.debug(f"[{debug_time}] status set: {fields['status']}")
    if request.form.get('edit_start_date'):
        fields['start_date'] = request.form.get('edit_start_date')
        logger.debug(f"[{debug_time}] start_date set: {fields['start_date']}")
    if request.form.get('notes'):
        fields['notes'] = request.form.get('notes')
        logger.debug(f"[{debug_time}] notes set: {fields['notes']}")

    document = request.files.get('document')
    if document:
        filename = secure_filename(document.filename)
        document_path = os.path.join('static\\SavingPlans', filename)
        full_path = os.path.join(current_app.root_path, document_path)
        try:
            document.save(full_path)
            fields['document_path'] = document_path
            logger.info(f"[{debug_time}] Document uploaded and saved as {document_path}")
        except Exception as file_err:
            logger.error(f"[{debug_time}] Failed to save document: {file_err}")
            log_incident(
                admin_id, role,
                f"Failed to save updated document for savings plan {plan_id}: {file_err}",
                severity="Medium"
            )
            return jsonify({'error': f"Failed to save document: {str(file_err)}"}), 500

    if not fields:
        logger.warning(f"[{debug_time}] No valid fields provided for update for savings plan {plan_id}")
        log_incident(
            admin_id, role,
            f"No valid fields provided for update for savings plan {plan_id}",
            severity="Low"
        )
        return jsonify({'error': 'No valid fields to update'}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            set_clauses = [f"{key} = %s" for key in fields.keys()]
            values = list(fields.values())

            query = f"""
                UPDATE savings_plans
                SET {', '.join(set_clauses)}
                WHERE plan_id = %s
            """
            values.append(plan_id)

            logger.info(f"[{debug_time}] Executing SQL: {query} with values: {values}")
            cur.execute(query, values)

        conn.commit()
        logger.info(f"[{debug_time}] Update committed for plan_id={plan_id}")
        log_audit(
            admin_id, role,
            "update_savings_plan",
            f"Updated savings plan with plan_id={plan_id}. Updated fields: {list(fields.keys())}"
        )
        return jsonify({'message': 'Savings plan updated successfully'})
    except Exception as e:
        logger.error(f"[{debug_time}] Exception occurred: {e}", exc_info=True)
        conn.rollback()
        log_incident(
            admin_id, role,
            f"Error updating savings plan with plan_id={plan_id}: {e}",
            severity="High"
        )
        return jsonify({'error': str(e)}), 500
    
# route for fetching employees to display in dropdown for create savings table
@admin_bp.route('/admin/employees/all', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_all_employees"])
def get_all_employees(admin_id, role,role_id):
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT employee_id, email
                FROM employees
            """)
            employees = cur.fetchall()
        return jsonify(employees)
    except Exception as e:
        print(f"[ERROR] Failed to fetch employees: {e}")
        return jsonify({'error': str(e)}), 500

# route for creating saving plans
@admin_bp.route('/admin/create_savings_plan', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["create_savings_plan"])
def create_savings_plan(admin_id, role, role_id):
    print("[DEBUG] Starting create_savings_plan")

    employee_id = request.form.get('employee_id')
    plan_type = request.form.get('plan_type')
    provider = request.form.get('provider')
    contribution_amount = request.form.get('contribution_amount')
    contribution_unit = request.form.get('contribution_unit')
    employer_match_amount = request.form.get('employer_match_amount')
    employer_match_unit = request.form.get('employer_match_unit')
    status = request.form.get('status')
    start_date = request.form.get('start_date')
    notes = request.form.get('notes')
    document = request.files.get('document')

    print(f"[DEBUG] Form data: employee_id={employee_id}, plan_type={plan_type}, provider={provider}, "
          f"contribution_amount={contribution_amount}, contribution_unit={contribution_unit}, "
          f"employer_match_amount={employer_match_amount}, employer_match_unit={employer_match_unit}, "
          f"status={status}, start_date={start_date}, notes={notes}")

    if not employee_id or not plan_type or not contribution_amount or not contribution_unit or not start_date:
        print("[ERROR] Missing required fields")
        log_incident(
            admin_id, role,
            f"Attempted to create savings plan with missing required fields: employee_id={employee_id}, plan_type={plan_type}, contribution_amount={contribution_amount}, contribution_unit={contribution_unit}, start_date={start_date}",
            severity="Low"
        )
        return jsonify({'error': 'Missing required fields'}), 400

    document_path = None
    if document:
        filename = secure_filename(document.filename)
        relative_folder = os.path.join('static', 'SavingPlans')
        document_path = os.path.join(relative_folder, filename)
        full_path = os.path.join(current_app.root_path, document_path)
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            document.save(full_path)
        except Exception as file_err:
            print(f"[ERROR] Failed to save document: {file_err}")
            log_incident(
                admin_id, role,
                f"Failed to save document for savings plan: {file_err}",
                severity="Medium"
            )
            return jsonify({'error': f"Failed to save document: {str(file_err)}"}), 500

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            print("[DEBUG] Inserting savings plan into database")
            cur.execute("""
                INSERT INTO savings_plans (
                    employee_id, plan_type, provider, contribution_amount,
                    contribution_unit, employer_match_amount, employer_match_unit, 
                    status, start_date, notes, document_path
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                employee_id, plan_type, provider, contribution_amount, contribution_unit,
                employer_match_amount, employer_match_unit, status, start_date, notes, document_path
            ))
        conn.commit()
        print("[DEBUG] Savings plan inserted successfully")
        log_audit(
            admin_id, role,
            "create_savings_plan",
            f"Created savings plan for employee_id={employee_id}, plan_type={plan_type}, provider={provider}"
        )
        return jsonify({'message': 'Savings plan created successfully'})
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Database error: {e}")
        log_incident(
            admin_id, role,
            f"Database error when creating savings plan: {e}",
            severity="High"
        )
        return jsonify({'error': str(e)}), 500
    
# Route for viewing saving plan details
@admin_bp.route('/get_saving_plan/<int:plan_id>', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_saving_plan_details"])
def get_saving_plan_details( admin_id, role, role_id,plan_id):
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
        SELECT 
            sp.plan_id,
            sp.employee_id,
            e.email,
            sp.plan_type,
            sp.provider,
            sp.contribution_amount,
            sp.contribution_unit,
            sp.contribution_percent,
            sp.employer_match_amount,
            sp.employer_match_unit,
            sp.employer_match_percent,
            sp.status,
            sp.start_date,
            sp.notes,
            sp.document_path
        FROM 
            savings_plans sp
        JOIN 
            employees e ON sp.employee_id = e.employee_id
        WHERE 
            sp.plan_id = %s
    """
    cur.execute(query, (plan_id,))
    row = cur.fetchone()

    if row:
        colnames = [desc[0] for desc in cur.description]
        conn.close()
        return jsonify(dict(zip(colnames, row)))
    else:
        conn.close()
        return jsonify({'error': 'Plan not found'}), 404

# Route for fetching requests for a savings plan
@csrf.exempt
@admin_bp.route('/admin/savings_plan_requests/<int:plan_id>', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["savings_plan_requests_for_plan"])
def savings_plan_requests_for_plan(admin_id, role, role_id, plan_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    request_id,
                    plan_id,
                    status,
                    message,
                    response,
                    submitted_at,
                    reviewed_at
                FROM savings_plan_requests
                WHERE plan_id = %s
                ORDER BY submitted_at
            """, (plan_id,))
            requests = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            requests_list = [dict(zip(columns, row)) for row in requests]
        return jsonify({'requests': requests_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# route for fetching details for a specific request
@csrf.exempt
@admin_bp.route('/admin/savings_plan_request/<int:request_id>', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_savings_plan_request"])
def get_savings_plan_request(admin_id, role, role_id, request_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    r.request_id,
                    r.plan_id,
                    r.status,
                    r.message,
                    r.response,
                    r.submitted_at,
                    r.reviewed_at,
                    p.plan_type,
                    p.provider,
                    p.contribution_percent,
                    e.email as employee_email
                FROM savings_plan_requests r
                JOIN savings_plans p ON r.plan_id = p.plan_id
                JOIN employees e ON p.employee_id = e.employee_id
                WHERE r.request_id = %s
                """, (request_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'Request not found'}), 404
            columns = [desc[0] for desc in cur.description]
            return jsonify(dict(zip(columns, row)))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
# Route for fetching all savings plans (summary, for table)
@admin_bp.route('/admin/savings_plans', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_savings_plans"])
def get_savings_plans(admin_id, role, role_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    p.plan_id,
                    p.employee_id,
                    e.email,
                    p.plan_type,
                    p.provider,
                    p.contribution_amount,
                    p.contribution_unit,
                    p.contribution_percent,
                    p.employer_match_amount,
                    p.employer_match_unit,
                    p.employer_match_percent,
                    p.status as plan_status,
                    p.start_date,
                    p.notes,
                    p.document_path
                FROM savings_plans p
                JOIN employees e ON p.employee_id = e.employee_id
                ORDER BY p.plan_id
            """)
            plans = cur.fetchall()
            if not plans:
                return jsonify({'plans': [], 'message': 'No plans found'})
            columns = [desc[0] for desc in cur.description]
            plans_list = [dict(zip(columns, row)) for row in plans]
            return jsonify({'plans': plans_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
# Route for viewing details of the bonus, now joined with employees to show email
@admin_bp.route('/get_bonus/<int:bonus_id>', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_bonus"])
def get_bonus(admin_id, role, role_id, bonus_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Join bonuses_incentives with employees to get employee email
        cursor.execute("""
            SELECT b.*, e.email
            FROM bonuses_incentives b
            LEFT JOIN employees e ON b.employee_id = e.employee_id
            WHERE b.id = %s
        """, (bonus_id,))
        bonus = cursor.fetchone()
        if bonus:
            columns = [desc[0] for desc in cursor.description]
            bonus_dict = dict(zip(columns, bonus))
            return jsonify(bonus_dict)
        else:
            return jsonify({'status': 'error', 'message': 'Bonus not found'}), 404
    except Exception as e:
        print("Error fetching bonus:", e)
        return jsonify({'status': 'error', 'message': 'Server error'}), 500
    
# Route to delete a bonus by ID
@csrf.exempt
@admin_bp.route('/delete_bonus/<int:bonus_id>', methods=['DELETE'])
@token_required_with_roles_and_2fa(required_actions=["delete_bonus"])
def delete_bonus(admin_id,role,role_id,bonus_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bonuses_incentives WHERE id = %s", (bonus_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Bonus deleted successfully.'})
    except Exception as e:
        print(e)
        return jsonify({'status': 'error', 'message': 'Failed to delete bonus.'})

#route for adding bonus
@admin_bp.route('/add_bonus', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["add_bonus"])
def add_bonus(admin_id=None,role=None,role_id=None):
    employee_id = request.form.get('employee_id')
    amount = request.form.get('amount')
    description = request.form.get('description', '')
    bonus_type = request.form.get('type')

    if not all([employee_id, amount, bonus_type]):
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO bonuses_incentives (employee_id, amount, description, type, awarded_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (employee_id, amount, description, bonus_type, datetime.utcnow()))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Bonus added successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        cur.close()
        conn.close()

#route for fetching bonus to display
@admin_bp.route('/get_all_bonuses')
@token_required_with_roles_and_2fa(required_actions=["get_all_bonuses"])
def get_all_bonuses(admin_id,role,role_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM bonuses_incentives ORDER BY awarded_date DESC")
    bonuses = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(bonuses)

#route for updating bonus
@csrf.exempt
@admin_bp.route('/update_bonus', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["update_bonus"])
def update_bonus(admin_id,role,role_id):
    bonus_id = request.form['bonus_id']
    amount = request.form['amount']
    description = request.form['description']
    bonus_type = request.form['type']
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE bonuses_incentives
        SET amount = %s, description = %s, type = %s
        WHERE id = %s
    """, (amount, description, bonus_type, bonus_id))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'success', 'message': 'Bonus updated successfully'})


#route for deleting tax document details 
@csrf.exempt
@admin_bp.route('/delete-tax-document/<int:document_id>', methods=['DELETE'])
@token_required_with_roles_and_2fa(required_actions=["delete_tax_document"])
def delete_tax_document(admin_id,role,role_id,document_id):
    try:
        logging.debug(f"Attempting to delete tax document with ID: {document_id}")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the record exists
        cursor.execute("SELECT file_path FROM tax_documents WHERE document_id = %s", (document_id,))
        record = cursor.fetchone()
        logging.debug(f"Record found: {record}")

        if not record:
            logging.warning(f"Tax document with ID {document_id} not found.")
            return jsonify({'status': 'error', 'message': 'Tax document not found.'}), 404

        # Log details about the file path before deletion (for debugging purposes)
        logging.debug(f"Deleting tax document with file path: {record[0]}")

        # Delete the record from both tax_records and tax_documents
        cursor.execute("DELETE FROM tax_records WHERE document_id = %s", (document_id,))
        cursor.execute("DELETE FROM tax_documents WHERE document_id = %s", (document_id,))
        conn.commit()

        logging.info(f"Tax document with ID {document_id} and associated records deleted successfully.")

        # Retrieve admin details (admin_id and role)
        logging.debug(f"Admin details retrieved: admin_id={admin_id}, role={role}")
        
        # Log the audit with more details
        log_audit(
            admin_id,
            role,
            'Delete tax document',
            f'Deleted tax document with ID : {document_id}',
        )

        cursor.close()
        conn.close()

        logging.debug(f"Tax document with ID {document_id} deleted and audit logged successfully.")
        return jsonify({'status': 'success', 'message': 'Tax document deleted successfully.'})

    except Exception as e:
        logging.error(f"Error deleting tax document {document_id}: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Route for editing tax document details
@csrf.exempt
@admin_bp.route('/edit-tax-document/<int:document_id>', methods=['PUT'])
@token_required_with_roles_and_2fa(required_actions=["edit_tax_document"])
def edit_tax_document(admin_id,role,role_id,document_id):
    try:
        data = request.json
        new_tax_year = data.get('tax_year')
        new_document_type = data.get('document_type')
        new_file_path = data.get('file_path')

        logging.debug(f"Attempting to edit tax document with ID: {document_id}")
        logging.debug(f"New data received: tax_year={new_tax_year}, document_type={new_document_type}, file_path={new_file_path}")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch the old record before updating
        cursor.execute("SELECT tax_year, document_type, file_path FROM tax_documents WHERE document_id = %s", (document_id,))
        old_record = cursor.fetchone()
        logging.debug(f"Old record retrieved: {old_record}")

        if not old_record:
            logging.warning(f"Tax document with ID {document_id} not found.")
            return jsonify({'status': 'error', 'message': 'Tax document not found.'}), 404

        # Proceed to update the record
        logging.debug(f"Updating tax document with ID {document_id} to new values: tax_year={new_tax_year}, document_type={new_document_type}, file_path={new_file_path}")
        
        cursor.execute("""
            UPDATE tax_documents
            SET tax_year = %s, document_type = %s, file_path = %s
            WHERE document_id = %s
        """, (new_tax_year, new_document_type, new_file_path, document_id))

        conn.commit()

        logging.info(f"Tax document with ID {document_id} updated successfully.")

        # Log audit after successful update
        logging.debug(f"Admin details retrieved: admin_id={admin_id}, role={role}")
        
        # Log the update action
        log_audit(admin_id, role, 'Update tax document', f'Updated tax document details ID : {document_id}')

        cursor.close()
        conn.close()

        logging.debug(f"Tax document with ID {document_id} updated and audit logged successfully.")
        return jsonify({'status': 'success', 'message': 'Tax document updated successfully.'})

    except Exception as e:
        logging.error(f"Error editing tax document {document_id}: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

#route to view image of tax documents
@csrf.exempt
@admin_bp.route("/TaxDocuments/<filename>")
@token_required_with_roles_and_2fa(required_actions=["serve_tax_document"])
def serve_tax_document(admin_id,role,role_id,filename):
    """Serve tax documents without authentication for direct PDF viewing"""
    return send_from_directory("TaxDocuments", filename)

#route for displaying tax details for employees
@admin_bp.route('/admin/get-tax-documents', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_tax_documents"])
def get_tax_documents(admin_id=None,role=None,role_id=None):
    try:
        logging.debug("Attempting to retrieve tax documents from the database.")
        
        conn = get_db_connection()
        cursor = conn.cursor()

        # SQL query to retrieve tax documents
        query = """
           select e.email,td.tax_year,td.document_type,td.file_path,td.created_at,tr.gross_income,tr.tax_deducted,tr.net_income,td.document_id
            from tax_documents td
            left join tax_records tr ON tr.document_id = td.document_id
            left join employees e ON e.employee_id = td.employee_id
        """
        
        logging.debug(f"Executing query: {query}")
        
        cursor.execute(query)
        tax_documents = cursor.fetchall()

        # Log the number of records retrieved
        logging.debug(f"Retrieved {len(tax_documents)} tax document(s).")

        cursor.close()
        conn.close()

        # Prepare the response
        response = [
            {
                "email": row[0],
                "tax_year": row[1],
                "document_type": row[2],
                "file_path": row[3],
                "gross_income": row[5],
                "tax_deducted": row[6],
                "net_income": row[7],
                "tax_document_id": row[8],
            } 
            for row in tax_documents
        ]
        
        logging.debug(f"Returning {len(response)} tax document(s) in response.")
        
        return jsonify(response)

    except Exception as e:
        logging.error(f"Error retrieving tax documents: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# route for generating tax document 
@csrf.exempt
@admin_bp.route('/generate-tax-document', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["generate_tax_document"])
def generate_tax_document(admin_id=None, role=None, role_id=None):
    try:
        data = request.json
        current_app.logger.debug(f"Received data: {data}")

        # --- USD conversion rate (update as needed) ---
        KHR_TO_USD_RATE = 4100  # Example: 4100 KHR = 1 USD, update as needed

        employee_id = data.get('employee_id')
        tax_year = data.get('tax_year')
        document_type = data.get('document_type', 'Tax Report')  # Shortened to match DB constraint
        gross_income_khr = float(data.get('gross_income', 0))  # In KHR

        if not all([employee_id, tax_year, document_type, gross_income_khr]):
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

        # Cambodian tax calculation (KHR)
        def compute_salary_tax_khr(gross):
            brackets = [
                (1300000, 0.00),
                (2000000, 0.05),
                (8500000, 0.10),
                (12500000, 0.15),
                (float('inf'), 0.20)
            ]
            remaining = gross
            tax = 0
            last_limit = 0
            for limit, rate in brackets:
                if remaining <= 0:
                    break
                income_in_bracket = min(limit - last_limit, remaining)
                tax += income_in_bracket * rate
                remaining -= income_in_bracket
                last_limit = limit
            return round(tax, 2)

        salary_tax_khr = compute_salary_tax_khr(gross_income_khr)
        nssf_employee_khr = round(gross_income_khr * 0.013, 2)
        nssf_employer_khr = round(gross_income_khr * 0.028, 2)
        net_income_khr = round(gross_income_khr - salary_tax_khr - nssf_employee_khr, 2)

        # --- Convert to USD ---
        gross_income_usd = round(gross_income_khr / KHR_TO_USD_RATE, 2)
        salary_tax_usd = round(salary_tax_khr / KHR_TO_USD_RATE, 2)
        nssf_employee_usd = round(nssf_employee_khr / KHR_TO_USD_RATE, 2)
        nssf_employer_usd = round(nssf_employer_khr / KHR_TO_USD_RATE, 2)
        net_income_usd = round(net_income_khr / KHR_TO_USD_RATE, 2)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch employee details
        cursor.execute("SELECT first_name, last_name, email FROM employees WHERE employee_id = %s", (employee_id,))
        employee = cursor.fetchone()
        if not employee:
            return jsonify({'status': 'error', 'message': 'Employee not found'}), 404

        first_name, last_name, email = employee
        current_app.logger.debug(f"Employee details: {first_name} {last_name}, {email}")

        # Ensure directory exists
        os.makedirs(TAX_DOCS_FOLDER, exist_ok=True)

        # Generate tax document PDF (show both KHR and USD)
        file_name = f"{employee_id}_{tax_year}_tax.pdf"
        file_path = os.path.join(TAX_DOCS_FOLDER, file_name)
        current_app.logger.debug(f"Saving PDF to: {file_path}")

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, "Cambodian Payroll Tax Report", ln=True, align='C')
        pdf.cell(200, 10, f"Employee: {first_name} {last_name}", ln=True, align='C')
        pdf.cell(200, 10, f"Year: {tax_year}", ln=True, align='C')
        pdf.cell(200, 10, f"Email: {email}", ln=True, align='C')
        pdf.ln(5)
        pdf.cell(200, 10, f"Gross Income: KHR {gross_income_khr:,.2f} / USD {gross_income_usd:,.2f}", ln=True, align='C')
        pdf.cell(200, 10, f"Salary Tax: KHR {salary_tax_khr:,.2f} / USD {salary_tax_usd:,.2f}", ln=True, align='C')
        pdf.cell(200, 10, f"NSSF (Employee): KHR {nssf_employee_khr:,.2f} / USD {nssf_employee_usd:,.2f}", ln=True, align='C')
        pdf.cell(200, 10, f"NSSF (Employer): KHR {nssf_employer_khr:,.2f} / USD {nssf_employer_usd:,.2f}", ln=True, align='C')
        pdf.cell(200, 10, f"Net Income: KHR {net_income_khr:,.2f} / USD {net_income_usd:,.2f}", ln=True, align='C')
        pdf.output(file_path)

        # Save tax document metadata (use only filename for DB constraint)
        relative_path = file_name
        cursor.execute("""
            INSERT INTO tax_documents (employee_id, tax_year, document_type, file_path) 
            VALUES (%s, %s, %s, %s) RETURNING document_id
        """, (employee_id, tax_year, document_type, relative_path))

        doc_row = cursor.fetchone()
        if not doc_row:
            raise Exception("Failed to retrieve document_id after insert.")
        document_id = doc_row[0]
        current_app.logger.debug(f"Inserted tax document ID: {document_id}")

        # Save tax record in USD (for reporting consistency)
        cursor.execute("""
            INSERT INTO tax_records (employee_id, gross_income, tax_deducted, net_income, document_id) 
            VALUES (%s, %s, %s, %s, %s)
        """, (employee_id, gross_income_usd, salary_tax_usd, net_income_usd, document_id))

        conn.commit()
        current_app.logger.debug(f"Tax record committed for employee_id {employee_id}")
        cursor.close()
        conn.close()

        # Audit log
        log_audit(admin_id, role_id, 'generate-tax-document', 
                  f'Generated tax document for employee ID: {employee_id} for year {tax_year} (USD).')

        return jsonify({
            'status': 'success',
            'message': 'Cambodian tax document and record (in USD) saved successfully',
            'file_path': file_name
        }), 201

    except Exception as e:
        current_app.logger.exception("Error in /generate-tax-document")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
# Route for deleting an expense claim
@csrf.exempt
@admin_bp.route('/delete-expense/<int:claim_id>', methods=['DELETE'])
@token_required_with_roles_and_2fa(required_actions=["delete_expense"])
def delete_expense(admin_id,role,role_id,claim_id):
    try:
        logging.debug(f"Attempting to delete expense claim with ID: {claim_id}")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Retrieve file path before deletion
        cursor.execute("SELECT receipt_path FROM expense_claims WHERE claim_id = %s", (claim_id,))
        result = cursor.fetchone()

        if not result:
            logging.warning(f"Expense claim with ID {claim_id} not found.")
            return jsonify({'status': 'error', 'message': 'Expense claim not found'}), 404

        receipt_path = result[0]

        if not isinstance(receipt_path, str) or not receipt_path.strip():
            logging.error("Receipt path is invalid or empty.")
            return jsonify({'status': 'error', 'message': "Invalid receipt file path."}), 500

        file_path = os.path.join('ExpenseClaimsUploads', os.path.basename(receipt_path))
        logging.debug(f"Resolved file path: {file_path}")

        # Delete file if exists
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logging.debug(f"Successfully deleted file: {file_path}")
            except Exception as file_error:
                logging.error(f"Error deleting file {file_path}: {file_error}")
                return jsonify({'status': 'error', 'message': f"Error deleting file: {file_error}"}), 500
        else:
            logging.warning(f"File {file_path} does not exist.")

        # Delete database record
        cursor.execute("DELETE FROM expense_claims WHERE claim_id = %s", (claim_id,))
        conn.commit()
        logging.debug(f"Successfully deleted expense claim from database with ID: {claim_id}")

        cursor.close()
        conn.close()

        # 🔥 Add proper audit logging
        log_audit(admin_id, role, 'Delete Expense', f'Deleted expense claim with ID {claim_id}.')

        return jsonify({'status': 'success', 'message': 'Expense claim deleted successfully'}), 200

    except Exception as e:
        logging.error(f"Unexpected error while deleting expense claim ID {claim_id}: {e}")
        logging.error(traceback.format_exc())
        return jsonify({'status': 'error', 'message': f"Server error: {str(e)}"}), 500

# Route to fetch the expense claim details to approve and reject
@admin_bp.route('/get-expense-claims', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_expense_claims"])
def get_expense_claims(admin_id=None, role=None, role_id=None):
    try:
        logging.debug("Connecting to the database...")
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch claims with employee emails
        logging.debug("Executing query to fetch expense claims (with employee emails)...")
        cursor.execute("""
            SELECT 
                c.claim_id, 
                c.employee_id, 
                c.amount, 
                c.description, 
                c.receipt_path, 
                c.status,
                e.email
            FROM expense_claims c
            LEFT JOIN employees e ON c.employee_id = e.employee_id;
        """)
        claims = cursor.fetchall()
        logging.debug(f"Fetched claims: {claims}")

        conn.commit()
        
        expense_claims = []
        for claim in claims:
            employee_id = claim[1]
            email = claim[6]
            if email and email.strip():
                employee_display = email
            else:
                employee_display = f"Employee ID: {employee_id}"
            expense_claims.append({
                'claim_id': claim[0],
                'employee_id': employee_id,
                'employee_display': employee_display,
                'amount': str(claim[2]),
                'description': claim[3],
                'receipt': f"/{claim[4]}" if claim[4] else None,
                'status': claim[5],
            })

        cursor.close()
        conn.close()

        log_audit(admin_id, role, 'get-expense-claims', 'Fetched all expense claims.')

        return jsonify({'status': 'success', 'claims': expense_claims}), 200

    except Exception as e:
        logging.error(f"Error occurred: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
# Route for approving expense
@csrf.exempt
@admin_bp.route('/approve-expense/<int:claim_id>', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["approve_expense"])
def approve_expense(admin_id,role,role_id,claim_id):
    try:
        logging.debug(f"Received request to approve expense with ID: {claim_id}")
        
        conn = get_db_connection()
        cursor = conn.cursor()

        # Update status to 'approved'
        logging.debug(f"Updating expense claim status to 'approved' for expense_id: {claim_id}")
        cursor.execute("UPDATE expense_claims SET status = 'approved' WHERE claim_id = %s", (claim_id,))
        conn.commit()

        # Log the action in audit trail
        log_audit(admin_id, role,'Approve Expense', f'Approved expense claim ID {claim_id}')

        cursor.close()
        conn.close()

        logging.debug(f"Expense claim with ID: {claim_id} approved successfully.")
        return jsonify({'status': 'success', 'message': 'Expense claim approved'}), 200
    except Exception as e:
        logging.error(f"Error occurred while approving expense with ID: {claim_id}. Error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Route for rejecting expense
@csrf.exempt
@admin_bp.route('/reject-expense/<int:claim_id>', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["reject_expense"])
def reject_expense(admin_id,role,role_id,claim_id,):
    try:
        logging.debug(f"Received request to reject expense with ID: {claim_id}")
        
        conn = get_db_connection()
        cursor = conn.cursor()

        # Update status to 'rejected'
        logging.debug(f"Updating expense claim status to 'rejected' for expense_id: {claim_id}")
        cursor.execute("UPDATE expense_claims SET status = 'rejected' WHERE claim_id = %s", (claim_id,))
        conn.commit()

        # Log the action in audit trail
        log_audit(admin_id, role,'Reject Expense', f'Rejected expense claim ID {claim_id}')

        cursor.close()
        conn.close()

        logging.debug(f"Expense claim with ID: {claim_id} rejected successfully.")
        return jsonify({'status': 'success', 'message': 'Expense claim rejected'}), 200
    except Exception as e:
        logging.error(f"Error occurred while rejecting expense with ID: {claim_id}. Error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Route to fetch specific employee details
@admin_bp.route('/get_employee_details_salary/<int:employee_id>', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_employee_details_salary"])
def get_employee_details_salary(admin_id,role,role_id,employee_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.employee_id, e.email, al.hours_worked, al.overtime_hours
        FROM employees e
        LEFT JOIN attendance_logs al ON al.employee_id = e.employee_id
        WHERE e.employee_id = %s
    """, (employee_id,))
    
    employee = cursor.fetchone()
    cursor.close()
    conn.close()

    if employee:
        log_audit(admin_id, role,'Fetch Employee Details', f'Viewed salary details for employee ID {employee_id}')

        return jsonify({
            "employee_id": employee[0],
            "email": employee[1],
            "hours_worked": employee[2],
            "overtime_hours": employee[3],
        })
    else:
        return jsonify({"error": "Employee not found"}), 404

# Route to create or update payroll, now with payslip PDF generation
@csrf.exempt
@admin_bp.route('/process_payroll', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["process_payroll"])
def process_payroll(admin_id, role, role_id):
    import sys
    import traceback
    from datetime import datetime
    from flask import current_app, jsonify
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    import os

    def debug(msg, *args):
        print(f"[DEBUG][process_payroll] {msg}", *args, file=sys.stderr)
        try:
            current_app.logger.debug(f"[process_payroll] {msg} {args if args else ''}")
        except Exception:
            pass

    def generate_payslip_pdf(payroll_id, payroll_data):
        folder = "static/payslips"
        os.makedirs(folder, exist_ok=True)
        pdf_path = os.path.join(folder, f"payslip_{payroll_id}.pdf")
        c = canvas.Canvas(pdf_path, pagesize=letter)
        width, height = letter
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, height-72, "Payslip")
        c.setFont("Helvetica", 12)
        c.drawString(72, height-100, f"Payroll ID: {payroll_id}")
        c.drawString(72, height-120, f"Employee ID: {payroll_data.get('employee_id', 'N/A')}")
        c.drawString(72, height-140, f"Month: {payroll_data.get('month', 'N/A')}")
        y = height-180
        c.setFont("Helvetica-Bold", 13)
        c.drawString(72, y, "Details:")
        y -= 20
        c.setFont("Helvetica", 12)
        c.drawString(90, y, f"Base Salary: ${payroll_data.get('base_salary', 0):,.2f}")
        y -= 20
        c.drawString(90, y, f"Hours Worked: {payroll_data.get('hours_worked', 0)}")
        y -= 20
        c.drawString(90, y, f"Overtime Hours: {payroll_data.get('overtime_hours', 0)}")
        y -= 20
        c.drawString(90, y, f"Overtime Pay: ${payroll_data.get('overtime_pay', 0):,.2f}")
        y -= 20
        c.drawString(90, y, f"Bonuses: ${payroll_data.get('bonuses', 0):,.2f}")
        y -= 20
        c.drawString(90, y, f"Tax Rate: {payroll_data.get('tax_rate', 0)}%")
        y -= 20
        c.drawString(90, y, f"Tax: ${payroll_data.get('tax', 0):,.2f}")
        y -= 20
        c.drawString(90, y, f"Net Salary: ${payroll_data.get('net_salary', 0):,.2f}")
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(72, 72, "Generated by Payroll System")
        c.save()
        debug(f"Generated payslip PDF: {pdf_path}")
        return pdf_path

    data = request.json
    debug("Received Data:", data)

    try:
        employee_id = data['employee_id']
        month_str = data['month']
        base_salary = float(data['base_salary'])
        hours_worked = float(data['hours_worked'])
        overtime_hours = float(data['overtime_hours'])
        overtime_pay = float(data['overtime_pay'])
        bonuses = float(data['bonuses'])
        tax_rate = float(data['tax_rate'])

        debug(f"Parsed inputs: employee_id={employee_id}, month_str={month_str}, base_salary={base_salary}, hours_worked={hours_worked}, overtime_hours={overtime_hours}, overtime_pay={overtime_pay}, bonuses={bonuses}, tax_rate={tax_rate}")

        month = datetime.strptime(month_str, "%Y-%m").date()
        debug(f"Parsed month: {month}")

        total_salary = base_salary + overtime_pay + bonuses
        tax = total_salary * (tax_rate / 100)
        net_salary = total_salary - tax

    except (KeyError, ValueError, TypeError) as e:
        debug("Invalid input exception:", e)
        debug("Traceback:", traceback.format_exc())
        return jsonify({"status": "Error", "message": "Invalid input data", "error": str(e)}), 400

    debug(f"Payroll Calculation: Total={total_salary}, Tax={tax}, Net Salary={net_salary}")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        debug("Checking for existing payroll record...")
        cursor.execute('SELECT payroll_id FROM payroll WHERE employee_id = %s AND month = %s', (employee_id, month))
        existing_payroll = cursor.fetchone()
        debug("Existing payroll record:", existing_payroll)

        if existing_payroll:
            payroll_id = existing_payroll[0]
            debug("Updating existing payroll record (payroll_id=%s)...", payroll_id)
            cursor.execute("""
                UPDATE payroll
                SET base_salary = %s, hours_worked = %s, overtime_hours = %s, 
                    overtime_pay = %s, bonuses = %s, tax_rate = %s, tax = %s, net_salary = %s
                WHERE payroll_id = %s
            """, (base_salary, hours_worked, overtime_hours, overtime_pay, bonuses, tax_rate, tax, net_salary, payroll_id))
            action = "Updated payroll"
        else:
            debug("Inserting new payroll record...")
            cursor.execute("""
                INSERT INTO payroll (employee_id, month, base_salary, hours_worked, 
                                     overtime_hours, overtime_pay, bonuses, tax_rate, 
                                     tax, net_salary, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (employee_id, month, base_salary, hours_worked, overtime_hours,
                  overtime_pay, bonuses, tax_rate, tax, net_salary))
            payroll_id = cursor.lastrowid
            action = "Created payroll"

        conn.commit()
        log_audit(admin_id, role, action, f'{action} for employee ID {employee_id} for {month}')
        debug("Payroll successfully inserted/updated. Action:", action)

        # Prepare payroll_data dict for PDF
        payroll_data = {
            "employee_id": employee_id,
            "month": str(month),
            "base_salary": base_salary,
            "hours_worked": hours_worked,
            "overtime_hours": overtime_hours,
            "overtime_pay": overtime_pay,
            "bonuses": bonuses,
            "tax_rate": tax_rate,
            "tax": tax,
            "net_salary": net_salary
        }
        # Generate payslip PDF
        try:
            generate_payslip_pdf(payroll_id, payroll_data)
        except Exception as pdf_err:
            debug("Payslip PDF generation error:", pdf_err)
            # Do not fail the payroll route if PDF generation fails; just log

        return jsonify({
            "status": "Success",
            "message": f"Payroll successfully {action.lower()}",
            "data": {
                "employee_id": employee_id,
                "month": str(month),
                "net_salary": net_salary,
                "tax": tax,
                "total_salary": total_salary
            }
        }), 200

    except Exception as e:
        debug("Database Error:", e)
        debug("Traceback:", traceback.format_exc())
        conn.rollback()
        return jsonify({"status": "Error", "message": "Failed to process payroll", "error": str(e)}), 500

    finally:
        debug("Closing DB connection.")
        cursor.close()
        conn.close()

@csrf.exempt
@admin_bp.route('/process-payroll/all', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["process_payroll"])
def process_payroll_all(admin_id, role, role_id):
    """
    Process payroll for all employees for the current month.
    """
    import sys
    import traceback
    from datetime import datetime
    from flask import current_app, jsonify
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    import os

    def debug(msg, *args):
        print(f"[DEBUG][process_payroll_all] {msg}", *args, file=sys.stderr)
        try:
            current_app.logger.debug(f"[process_payroll_all] {msg} {args if args else ''}")
        except Exception:
            pass

    def generate_payslip_pdf(payroll_id, payroll_data):
        folder = "static/payslips"
        os.makedirs(folder, exist_ok=True)
        pdf_path = os.path.join(folder, f"payslip_{payroll_id}.pdf")
        c = canvas.Canvas(pdf_path, pagesize=letter)
        width, height = letter
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, height-72, "Payslip")
        c.setFont("Helvetica", 12)
        c.drawString(72, height-100, f"Payroll ID: {payroll_id}")
        c.drawString(72, height-120, f"Employee ID: {payroll_data.get('employee_id', 'N/A')}")
        c.drawString(72, height-140, f"Month: {payroll_data.get('month', 'N/A')}")
        y = height-180
        c.setFont("Helvetica-Bold", 13)
        c.drawString(72, y, "Details:")
        y -= 20
        c.setFont("Helvetica", 12)
        c.drawString(90, y, f"Base Salary: ${payroll_data.get('base_salary', 0):,.2f}")
        y -= 20
        c.drawString(90, y, f"Hours Worked: {payroll_data.get('hours_worked', 0)}")
        y -= 20
        c.drawString(90, y, f"Overtime Hours: {payroll_data.get('overtime_hours', 0)}")
        y -= 20
        c.drawString(90, y, f"Overtime Pay: ${payroll_data.get('overtime_pay', 0):,.2f}")
        y -= 20
        c.drawString(90, y, f"Bonuses: ${payroll_data.get('bonuses', 0):,.2f}")
        y -= 20
        c.drawString(90, y, f"Tax Rate: {payroll_data.get('tax_rate', 0)}%")
        y -= 20
        c.drawString(90, y, f"Tax: ${payroll_data.get('tax', 0):,.2f}")
        y -= 20
        c.drawString(90, y, f"Net Salary: ${payroll_data.get('net_salary', 0):,.2f}")
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(72, 72, "Generated by Payroll System")
        c.save()
        debug(f"Generated payslip PDF: {pdf_path}")
        return pdf_path

    debug("Starting bulk payroll processing...")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        month = datetime.now().replace(day=1).date()
        debug(f"Processing payroll for month: {month}")

        # Get all employees
        cursor.execute("SELECT employee_id, email FROM employees")
        employees = cursor.fetchall()
        debug(f"Found {len(employees)} employees for payroll.")

        processed = []
        errors = []
        base_salary = 3000  # You may want to fetch this per employee

        for emp in employees:
            try:
                employee_id = emp[0]
                email = emp[1]

                # Default values; replace with actual logic if available
                # You might want to get these from a timesheet, bonuses table, etc.
                hours_worked = 0.0
                overtime_hours = 0.0
                bonuses = 0.0
                tax_rate = 0.0

                # If you have a source for hours/bonuses/tax_rate, query here

                overtime_pay = overtime_hours * (base_salary / 160) * 1.5
                total_salary = base_salary + overtime_pay + bonuses
                tax = total_salary * (tax_rate / 100)
                net_salary = total_salary - tax

                # Check existing payroll
                cursor.execute('SELECT payroll_id FROM payroll WHERE employee_id = %s AND month = %s', (employee_id, month))
                existing_payroll = cursor.fetchone()

                if existing_payroll:
                    payroll_id = existing_payroll[0]
                    cursor.execute("""
                        UPDATE payroll
                        SET base_salary = %s, hours_worked = %s, overtime_hours = %s, 
                            overtime_pay = %s, bonuses = %s, tax_rate = %s, tax = %s, net_salary = %s
                        WHERE payroll_id = %s
                    """, (base_salary, hours_worked, overtime_hours, overtime_pay, bonuses, tax_rate, tax, net_salary, payroll_id))
                    action = "Updated payroll"
                else:
                    cursor.execute("""
                        INSERT INTO payroll (employee_id, month, base_salary, hours_worked, 
                                             overtime_hours, overtime_pay, bonuses, tax_rate, 
                                             tax, net_salary, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (employee_id, month, base_salary, hours_worked, overtime_hours,
                          overtime_pay, bonuses, tax_rate, tax, net_salary))
                    payroll_id = cursor.lastrowid
                    action = "Created payroll"

                conn.commit()
                log_audit(admin_id, role, action, f'{action} for employee ID {employee_id} for {month}')

                payroll_data = {
                    "employee_id": employee_id,
                    "email": email,
                    "month": str(month),
                    "base_salary": base_salary,
                    "hours_worked": hours_worked,
                    "overtime_hours": overtime_hours,
                    "overtime_pay": overtime_pay,
                    "bonuses": bonuses,
                    "tax_rate": tax_rate,
                    "tax": tax,
                    "net_salary": net_salary
                }

                try:
                    generate_payslip_pdf(payroll_id, payroll_data)
                except Exception as pdf_err:
                    debug("Payslip PDF generation error (employee_id=%s): %s", employee_id, pdf_err)

                processed.append(payroll_data)
            except Exception as e:
                debug("Error processing payroll for employee_id=%s: %s", emp[0], e)
                errors.append({"employee_id": emp[0], "error": str(e)})
                conn.rollback()

        debug("Bulk payroll processing complete. Success: %d, Errors: %d", len(processed), len(errors))
        return jsonify({
            "status": "Success" if not errors else "Partial Success",
            "message": f"Processed payroll for {len(processed)} employees. {len(errors)} errors.",
            "data": processed,
            "errors": errors
        }), (200 if not errors else 207)

    except Exception as e:
        debug("Bulk payroll DB Error:", e)
        debug("Traceback:", traceback.format_exc())
        return jsonify({"status": "Error", "message": "Bulk payroll processing failed", "error": str(e)}), 500

    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass

# ---- Update Payment Status to "Paid" ----
@csrf.exempt
@admin_bp.route('/update_payment_status/paid/<int:payroll_id>', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["update_payment_status_paid"])
def update_payment_status_paid(admin_id, role, role_id, payroll_id):
    from datetime import datetime
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Set payment_status to 'Paid' and payment_date to now
        cursor.execute(
            "UPDATE payroll SET payment_status=%s, payment_date=%s WHERE payroll_id=%s",
            ("Paid", datetime.utcnow(), payroll_id)
        )
        conn.commit()
        return jsonify({"status": "Success", "message": "Payment status updated to 'Paid' and payment date set."}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "Error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ---- Update Payment Status to "Not Yet Paid" ----
@csrf.exempt
@admin_bp.route('/update_payment_status/not_yet_paid/<int:payroll_id>', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["update_payment_status_not_yet_paid"])
def update_payment_status_not_yet_paid(admin_id, role, role_id, payroll_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Set payment_status to 'Not Yet Paid' and payment_date to NULL
        cursor.execute(
            "UPDATE payroll SET payment_status=%s, payment_date=%s WHERE payroll_id=%s",
            ("Not Yet Paid", None, payroll_id)
        )
        conn.commit()
        return jsonify({"status": "Success", "message": "Payment status updated to 'Not Yet Paid' and payment date cleared."}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "Error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ---- View Payroll Details ----
@admin_bp.route('/payroll/<int:payroll_id>', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_payroll"])
def get_payroll(admin_id, role, role_id, payroll_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT * FROM payroll WHERE payroll_id=%s", (payroll_id,))
        row = cursor.fetchone()
        if row:
            # Format payment_date as YYYY-MM-DD if it exists
            payment_date = None
            if row["payment_date"]:
                # If it's a datetime object, use strftime, else, fallback to str and slice
                try:
                    payment_date = row["payment_date"].strftime("%Y-%m-%d")
                except Exception:
                    payment_date = str(row["payment_date"])[:10]
            data = {
                "payroll_id": row["payroll_id"],
                "employee_id": row["employee_id"],
                "month": str(row["month"]),
                "base_salary": float(row["base_salary"]) if row["base_salary"] is not None else None,
                "hours_worked": float(row["hours_worked"]) if row["hours_worked"] is not None else None,
                "overtime_hours": float(row["overtime_hours"]) if row["overtime_hours"] is not None else None,
                "overtime_pay": float(row["overtime_pay"]) if row["overtime_pay"] is not None else None,
                "bonuses": float(row["bonuses"]) if row["bonuses"] is not None else None,
                "tax_rate": float(row["tax_rate"]) if row["tax_rate"] is not None else None,
                "deductions": float(row["deductions"]) if row["deductions"] is not None else None,
                "payment_status": row["payment_status"],
                "net_salary": float(row["net_salary"]) if row["net_salary"] is not None else None,
                "payment_date": payment_date,
            }
            return jsonify({"status": "Success", "data": data}), 200
        else:
            return jsonify({"status": "Error", "message": "Payroll not found"}), 404
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ---- Edit Payroll ----
@csrf.exempt
@admin_bp.route('/edit_payroll/<int:payroll_id>', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["edit_payroll"])
def edit_payroll(admin_id, role, role_id, payroll_id):
    import traceback
    data = request.json
    print(f"[DEBUG] Received data for payroll_id={payroll_id}: {data}")
    # Only allow specific fields to be updated
    allowed_fields = [
        'base_salary', 'hours_worked', 'overtime_hours', 'overtime_pay', 'bonuses',
        'tax_rate', 'deductions', 'payment_status', 'payment_date'
    ]
    updates = {k: data[k] for k in allowed_fields if k in data}
    print(f"[DEBUG] Filtered updates: {updates}")
    if not updates:
        print("[DEBUG] No allowed fields to update.")
        return jsonify({"status": "Error", "message": "No fields to update"}), 400

    # Build update query dynamically
    set_clause = ', '.join(f"{k}=%s" for k in updates)
    values = list(updates.values())
    values.append(payroll_id)
    print(f"[DEBUG] Update SQL: UPDATE payroll SET {set_clause} WHERE payroll_id=%s")
    print(f"[DEBUG] Values: {values}")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"UPDATE payroll SET {set_clause} WHERE payroll_id=%s", values)
        conn.commit()
        print(f"[DEBUG] Payroll {payroll_id} updated successfully.")
        return jsonify({"status": "Success", "message": "Payroll updated successfully"}), 200
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Exception occurred: {e}")
        print(traceback.format_exc())
        return jsonify({"status": "Error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ---- Delete Payroll ----
@csrf.exempt
@admin_bp.route('/delete_payroll/<int:payroll_id>', methods=['DELETE'])
@token_required_with_roles_and_2fa(required_actions=["delete_payroll"])
def delete_payroll(admin_id, role, role_id, payroll_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM payroll WHERE payroll_id=%s", (payroll_id,))
        conn.commit()
        return jsonify({"status": "Success", "message": "Payroll deleted successfully"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "Error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/payrolls', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_payrolls"])
def get_payrolls(admin_id, role, role_id):
    import traceback
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("payrolls")

    search = request.args.get('search', '').strip()
    logger.info(f"Received GET /payrolls request | Admin: {admin_id}, Role: {role}, RoleID: {role_id}, Search: '{search}'")

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        base_query = """
            SELECT p.payroll_id, p.employee_id, p.month, p.net_salary, p.payment_status, e.email
            FROM payroll p
            LEFT JOIN employees e ON p.employee_id = e.employee_id
        """
        params = []
        where_clauses = []
        if search:
            where_clauses.append(
                "(CAST(p.payroll_id AS TEXT) ILIKE %s OR "
                "CAST(p.employee_id AS TEXT) ILIKE %s OR "
                "CAST(p.month AS TEXT) ILIKE %s OR "
                "CAST(p.net_salary AS TEXT) ILIKE %s OR "
                "p.payment_status ILIKE %s OR "
                "e.email ILIKE %s)"
            )
            s = f"%{search}%"
            params.extend([s, s, s, s, s, s])

        if where_clauses:
            base_query += " WHERE " + " AND ".join(where_clauses)
        base_query += " ORDER BY p.payroll_id DESC LIMIT 100"

        logger.debug(f"Executing SQL: {base_query} | Params: {params}")

        cursor.execute(base_query, params)
        rows = cursor.fetchall()
        logger.info(f"Payrolls fetched: {len(rows)} rows")

        payrolls = []
        for row in rows:
            if row["email"]:
                employee_display = row["email"]
            else:
                employee_display = f"Employee ID: {row['employee_id']}"
            payrolls.append({
                "payroll_id": row["payroll_id"],
                "employee_id": row["employee_id"],
                "employee_display": employee_display,
                "month": row["month"].strftime("%Y-%m"),
                "net_salary": float(row["net_salary"]),
                "payment_status": row["payment_status"]
            })
        logger.debug(f"Returning payrolls: {payrolls}")
        return jsonify({"status": "success", "data": payrolls})

    except Exception as e:
        logger.error("Error loading payrolls: %s", e)
        logger.error(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
        logger.info("DB connection closed for /payrolls route")