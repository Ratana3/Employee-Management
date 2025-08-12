#route for submitting expense
from datetime import datetime
import logging
import os
from flask import g, jsonify, redirect, render_template, request, url_for
from routes.Auth.token import employee_jwt_required
from routes.Auth.token import verify_employee_token
from routes.Auth.utils import get_db_connection
from extensions import csrf
from . import employee_bp
from werkzeug.utils import secure_filename
from routes.Auth.audit import log_employee_incident,log_employee_audit

#route for rendering financial management page
@employee_bp.route('/financialmanagement', methods=['GET', 'POST'])
@employee_jwt_required()
@csrf.exempt
def financial_management():
    logging.debug("Received request at /financialmanagement")

    user_id = g.employee_id

    if not user_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized financial management page access attempt - no employee_id in session",
            severity="Medium"
        )
        return redirect(url_for('login_bp.employeelogin'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch user details
        cursor.execute("""
            SELECT e.employee_id, e.first_name, e.last_name, e.email,
                   e.phone_number, e.department, e.date_hired, e.address1, e.address2, r.role_name, t.team_name
            FROM employees e 
            LEFT JOIN roles r ON r.role_id = e.role_id
            LEFT JOIN teams t ON t.team_id = e.team_id
            WHERE e.employee_id = %s
        """, (user_id,))
        user = cursor.fetchone()

        if not user:
            logging.warning(f"No user found with ID: {user_id}. Redirecting to login.")
            log_employee_incident(
                employee_id=user_id,
                description=f"Financial management page accessed but employee {user_id} not found in database",
                severity="High"
            )
            cursor.close()
            conn.close()
            return redirect(url_for('login_bp.employeelogin'))

        # Log successful audit trail
        log_employee_audit(
            employee_id=user_id,
            action="access_financial_management",
            details=f"Successfully accessed financial management page for {user[1]} {user[2]} in {user[5]} department"
        )

        logging.debug(f"User details fetched: {user}")

    except Exception as e:
        logging.error(f"Database query error: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=user_id,
            description=f"System error while accessing financial management page: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500

    finally:
        cursor.close()
        conn.close()

    # Prepare context data
    user_details = {
        'employee_id': user[0],
        'first_name': user[1],
        'last_name': user[2],
        'email': user[3],
        'phone_number': user[4],
        'department': user[5],
        'date_hired': user[6],
        'address1': user[7],
        'address2': user[8],
        'role': user[9],
        'team_name': user[10],
        'profile_picture_url': url_for('employee_bp.profile_picture', user_id=user_id)
    }

    logging.info(f"Rendering financial management page for user ID: {user_id}")
    return render_template('Employee/FinancialManagement.html', user=user_details)

@employee_bp.route('/submit-expense', methods=['POST'])
@employee_jwt_required()
@csrf.exempt
def submit_expense():
    try:
        employee_id = g.employee_id

        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized expense claim submission attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

        # Get data from request
        title = request.form.get('title')
        amount = request.form.get('amount')
        date = request.form.get('date')
        category = request.form.get('category')
        description = request.form.get('description')
        file = request.files.get('receipt')

        # Validate required fields
        if not all([title, amount, date, category, file]):
            missing_fields = []
            if not title: missing_fields.append('title')
            if not amount: missing_fields.append('amount')
            if not date: missing_fields.append('date')
            if not category: missing_fields.append('category')
            if not file: missing_fields.append('receipt')
            
            log_employee_incident(
                employee_id=employee_id,
                description=f"Expense claim submission attempted with missing required fields: {', '.join(missing_fields)}",
                severity="Low"
            )
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

        # Validate amount is numeric and positive
        try:
            amount_float = float(amount)
            if amount_float <= 0:
                raise ValueError("Amount must be positive")
        except ValueError as ve:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Expense claim submission attempted with invalid amount: '{amount}' - {str(ve)}",
                severity="Low"
            )
            return jsonify({'status': 'error', 'message': 'Invalid amount provided'}), 400

        # Validate file
        if file.filename == '':
            log_employee_incident(
                employee_id=employee_id,
                description="Expense claim submission attempted with empty receipt filename",
                severity="Low"
            )
            return jsonify({'status': 'error', 'message': 'Invalid receipt file'}), 400

        # Prepare and create the upload directory if needed
        upload_folder = os.path.join('static', 'ExpenseClaimsUploads')
        try:
            os.makedirs(upload_folder, exist_ok=True)
        except Exception as dir_error:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Failed to create expense claims upload directory: {str(dir_error)}",
                severity="High"
            )
            return jsonify({'status': 'error', 'message': 'File system error'}), 500

        # Secure and save receipt file
        filename = secure_filename(file.filename)
        if not filename:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Expense claim submission attempted with invalid filename: '{file.filename}'",
                severity="Low"
            )
            return jsonify({'status': 'error', 'message': 'Invalid filename'}), 400

        receipt_path = os.path.join(upload_folder, filename)
        
        try:
            file.save(receipt_path)
        except Exception as file_error:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Failed to save expense receipt file '{filename}': {str(file_error)}",
                severity="Medium"
            )
            return jsonify({'status': 'error', 'message': 'File upload failed'}), 500

        # Insert into DB (store filename only, not full path)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO expense_claims (employee_id, title, amount, claim_date, category, description, receipt_path, status, submitted_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', NOW())
            RETURNING claim_id
        """, (employee_id, title, amount_float, date, category, description, filename))
        
        claim_id = cursor.fetchone()[0] if cursor.rowcount > 0 else None
        conn.commit()

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="submit_expense_claim",
            details=f"Successfully submitted expense claim (ID: {claim_id}): '{title}' for ${amount_float:.2f} in category '{category}' with receipt '{filename}'"
        )

        cursor.close()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Expense claim submitted successfully'}), 200

    except Exception as e:
        logging.error(f"Error submitting expense: {str(e)}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during expense claim submission: {str(e)}",
            severity="High"
        )
        
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

#route for fetching expense claims details
@employee_bp.route('/my-expense-claims')
@employee_jwt_required()
@csrf.exempt
def my_expense_claims():
    try:
        employee_id = g.employee_id

        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized expense claims access attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        query = """
            SELECT claim_id, title, amount, claim_date, category, description, status, receipt_path, submitted_at
            FROM expense_claims
            WHERE employee_id = %s
            ORDER BY submitted_at DESC
        """

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (employee_id,))
        rows = cursor.fetchall()

        claim_data = []
        total_amount = 0
        status_counts = {'pending': 0, 'approved': 0, 'rejected': 0}
        
        for row in rows:
            claim_id, title, amount, date, category, description, status, receipt_filename, submitted_at = row
            
            # Count statistics
            total_amount += float(amount) if amount else 0
            if status in status_counts:
                status_counts[status] += 1
            
            claim_data.append({
                'claim_id': claim_id,
                'title': title,
                'amount': str(amount),
                'date': date.strftime('%Y-%m-%d'),
                'category': category,
                'description': description,
                'status': status,
                'submitted_at': submitted_at.strftime('%Y-%m-%d %H:%M') if submitted_at else '',
                'receipt_url': url_for('static', filename='ExpenseClaimsUploads/' + receipt_filename) if receipt_filename else ''
            })

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="view_expense_claims",
            details=f"Retrieved {len(claim_data)} expense claims: ${total_amount:.2f} total, {status_counts['pending']} pending, {status_counts['approved']} approved, {status_counts['rejected']} rejected"
        )

        cursor.close()
        conn.close()

        return jsonify(claim_data)

    except Exception as e:
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while fetching expense claims: {str(e)}",
            severity="High"
        )
        
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        
        return jsonify({'error': 'Internal server error'}), 500
    
#route for fetching bonuses
@employee_bp.route('/my_bonuses', methods=['GET'])
@employee_jwt_required()
@csrf.exempt
def my_bonuses():
    try:
        employee_id = g.employee_id
        
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized bonuses access attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, type, amount, awarded_date, description
            FROM bonuses_incentives
            WHERE employee_id = %s
            ORDER BY awarded_date DESC
        """, (employee_id,))
        rows = cursor.fetchall()

        bonuses = []
        total_amount = 0
        bonus_types = {}
        
        for row in rows:
            bonus_amount = float(row[2]) if row[2] else 0
            total_amount += bonus_amount
            
            bonus_type = row[1] or 'Unknown'
            bonus_types[bonus_type] = bonus_types.get(bonus_type, 0) + 1
            
            bonuses.append({
                'id': row[0],
                'type': bonus_type,
                'amount': bonus_amount,
                'awarded_date': row[3].isoformat() if row[3] else None,
                'description': row[4]
            })

        # Log successful audit trail
        type_summary = ', '.join([f"{count} {btype}" for btype, count in bonus_types.items()]) if bonus_types else "none"
        log_employee_audit(
            employee_id=employee_id,
            action="view_bonuses",
            details=f"Retrieved {len(bonuses)} bonuses totaling ${total_amount:.2f}: {type_summary}"
        )

        cursor.close()
        conn.close()

        return jsonify({'bonuses': bonuses})

    except Exception as e:
        logging.error(f"Error fetching bonuses: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while fetching employee bonuses: {str(e)}",
            severity="High"
        )
        
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        
        return jsonify({'error': 'Internal server error'}), 500

#route for fetching bonus details
@employee_bp.route('/bonus_details/<int:bonus_id>', methods=['GET'])
@employee_jwt_required()
@csrf.exempt
def bonus_details(bonus_id):
    try:
        employee_id = g.employee_id
        
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description=f"Unauthorized bonus details access attempt for bonus {bonus_id} - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, type, description, amount, awarded_date
            FROM bonuses_incentives
            WHERE id = %s AND employee_id = %s
        """, (bonus_id, employee_id))
        row = cursor.fetchone()

        if not row:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to access non-existent or unauthorized bonus {bonus_id}",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Bonus not found'}), 404

        bonus = {
            'id': row[0],
            'type': row[1],
            'description': row[2],
            'amount': float(row[3]) if row[3] else 0,
            'awarded_date': row[4].isoformat() if row[4] else None
        }

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="view_bonus_details",
            details=f"Accessed details for bonus {bonus_id}: {bonus['type']} of ${bonus['amount']:.2f} awarded on {bonus['awarded_date']}"
        )

        cursor.close()
        conn.close()

        return jsonify({'bonus': bonus})

    except Exception as e:
        logging.error(f"Error fetching bonus details: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while fetching bonus {bonus_id} details: {str(e)}",
            severity="High"
        )
        
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        
        return jsonify({'error': 'Internal server error'}), 500

# Route to fetch savings plans for logged-in employee
@employee_bp.route('/my_savings_plans', methods=['GET'])
@employee_jwt_required()
def my_savings_plans():
    employee_id = g.employee_id
    
    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized savings plans access attempt - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    p.plan_id,
                    p.plan_type,
                    p.provider,
                    p.contribution_amount,
                    p.contribution_unit,
                    p.contribution_percent,
                    p.employer_match_amount,
                    p.employer_match_unit,
                    p.employer_match_percent,
                    p.status,
                    p.start_date,
                    p.notes,
                    p.document_path,
                    (SELECT COUNT(*) 
                     FROM savings_plan_requests r 
                     WHERE r.plan_id = p.plan_id AND r.employee_id = p.employee_id) AS request_count
                FROM savings_plans p
                WHERE p.employee_id = %s
            """, (employee_id,))
            
            plans = cursor.fetchall()
            
            if not plans:
                # Log audit for no plans found
                log_employee_audit(
                    employee_id=employee_id,
                    action="view_savings_plans",
                    details="Retrieved savings plans: no plans found"
                )
                return jsonify({'plans': [], 'message': 'No savings plans found'})

            plans_list = []
            total_contribution = 0
            plan_statuses = {}
            plan_types = {}
            
            for p in plans:
                contribution_amount = float(p[3]) if p[3] is not None else 0
                total_contribution += contribution_amount
                
                plan_status = p[9] or 'Unknown'
                plan_statuses[plan_status] = plan_statuses.get(plan_status, 0) + 1
                
                plan_type = p[1] or 'Unknown'
                plan_types[plan_type] = plan_types.get(plan_type, 0) + 1
                
                plans_list.append({
                    'plan_id': p[0],
                    'plan_type': plan_type,
                    'provider': p[2],
                    'contribution_amount': contribution_amount,
                    'contribution_unit': p[4],
                    'contribution_percent': float(p[5]) if p[5] is not None else None,
                    'employer_match_amount': float(p[6]) if p[6] is not None else None,
                    'employer_match_unit': p[7],
                    'employer_match_percent': float(p[8]) if p[8] is not None else None,
                    'status': plan_status,
                    'start_date': p[10].strftime('%Y-%m-%d') if p[10] else None,
                    'notes': p[11],
                    'document_path': p[12],
                    'request_count': p[13]
                })

            # Log successful audit trail
            status_summary = ', '.join([f"{count} {status}" for status, count in plan_statuses.items()])
            type_summary = ', '.join([f"{count} {ptype}" for ptype, count in plan_types.items()])
            log_employee_audit(
                employee_id=employee_id,
                action="view_savings_plans",
                details=f"Retrieved {len(plans_list)} savings plans with ${total_contribution:.2f} total contribution: {type_summary} | Status: {status_summary}"
            )

            return jsonify({'plans': plans_list})

    except Exception as e:
        logging.error(f"Error fetching savings plans: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error while fetching savings plans: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

#route for viewing response to the request change
@employee_bp.route('/employee/plan_responses/<int:plan_id>', methods=['GET'])
@employee_jwt_required()
@csrf.exempt
def get_plan_responses(plan_id):
    employee_id = g.employee_id
    
    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description=f"Unauthorized savings plan responses access attempt for plan {plan_id} - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized', 'response_count': 0}), 401
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # First verify the plan belongs to this employee
            cur.execute("""
                SELECT plan_type, provider, status
                FROM savings_plans
                WHERE plan_id = %s AND employee_id = %s
            """, (plan_id, employee_id))
            
            plan_info = cur.fetchone()
            if not plan_info:
                log_employee_incident(
                    employee_id=employee_id,
                    description=f"Employee attempted to access responses for non-existent or unauthorized savings plan {plan_id}",
                    severity="High"
                )
                return jsonify({'error': 'Savings plan not found', 'response_count': 0}), 404
            
            plan_type, provider, plan_status = plan_info
            
            cur.execute("""
                SELECT 
                    r.request_id,
                    r.message,
                    r.response,
                    r.status,
                    r.submitted_at,
                    r.reviewed_at,
                    r.reviewed_by,
                    p.plan_type,
                    COUNT(*) OVER() AS total_count
                FROM savings_plan_requests r
                JOIN savings_plans p ON r.plan_id = p.plan_id
                WHERE r.plan_id = %s AND r.employee_id = %s
                ORDER BY r.submitted_at DESC
            """, (plan_id, employee_id))
            
            rows = cur.fetchall()
            if not rows:
                # Log audit for no responses found
                log_employee_audit(
                    employee_id=employee_id,
                    action="view_plan_responses",
                    details=f"Accessed responses for savings plan {plan_id} ({plan_type} with {provider}): no responses found"
                )
                return jsonify({'error': 'No responses found', 'response_count': 0}), 404

            columns = [desc[0] for desc in cur.description]
            responses = [dict(zip(columns, row)) for row in rows]

            # Analyze response patterns for logging
            status_counts = {}
            for response in responses:
                status = response.get('status', 'Unknown')
                status_counts[status] = status_counts.get(status, 0) + 1

            # Log successful audit trail
            status_summary = ', '.join([f"{count} {status}" for status, count in status_counts.items()])
            log_employee_audit(
                employee_id=employee_id,
                action="view_plan_responses",
                details=f"Retrieved {len(responses)} responses for savings plan {plan_id} ({plan_type} with {provider}): {status_summary}"
            )

            return jsonify({
                'responses': responses,
                'response_count': responses[0]['total_count']
            })
            
    except Exception as e:
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error while fetching responses for savings plan {plan_id}: {str(e)}",
            severity="High"
        )
        return jsonify({'error': str(e), 'response_count': 0}), 500
    
#route for fetching saving plan details to view
@employee_bp.route('/savings_plan_details/<int:plan_id>')
@employee_jwt_required()
@csrf.exempt
def get_savings_plan_details(plan_id):
    employee_id = g.employee_id
    
    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description=f"Unauthorized savings plan details access attempt for plan {plan_id} - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT plan_id, plan_type, provider, contribution_percent, start_date, status, notes, document_path
        FROM savings_plans
        WHERE plan_id = %s AND employee_id = %s
    """

    try:
        cursor.execute(query, (plan_id, employee_id))
        result = cursor.fetchone()

        if not result:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to access details for non-existent or unauthorized savings plan {plan_id}",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'Savings plan not found'}), 404

        plan = {
            'plan_id': result[0],
            'plan_type': result[1],
            'provider': result[2],
            'contribution_percent': result[3],
            'start_date': result[4],
            'status': result[5],
            'notes': result[6] or '-',
            'document_url': result[7] or ''
        }

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="view_savings_plan_details",
            details=f"Accessed details for savings plan {plan_id}: {plan['plan_type']} with {plan['provider']}, status: {plan['status']}, contribution: {plan['contribution_percent']}%"
        )

        cursor.close()
        conn.close()
        return jsonify(plan)
        
    except Exception as e:
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error while fetching savings plan {plan_id} details: {str(e)}",
            severity="High"
        )
        
        cursor.close()
        conn.close()
        return jsonify({'error': str(e)}), 500

#route for submitting saving plans
@employee_bp.route('/submit_savings_change_request', methods=['POST'])
@employee_jwt_required()
@csrf.exempt
def submit_savings_change_request():
    print("Received request to /submit_savings_change_request")

    employee_id = g.employee_id  # ✅ use g from decorator
    
    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description="Unauthorized savings plan change request submission - no employee_id in session",
            severity="Medium"
        )
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    data = request.get_json()
    print(f"Received data: {data}")

    plan_id = data.get('plan_id')
    request_type = data.get('request_type')
    message = data.get('message')

    if not all([employee_id, plan_id, request_type, message]):
        missing_fields = []
        if not plan_id: missing_fields.append('plan_id')
        if not request_type: missing_fields.append('request_type')
        if not message: missing_fields.append('message')
        
        log_employee_incident(
            employee_id=employee_id,
            description=f"Savings plan change request attempted with missing fields: {', '.join(missing_fields)}",
            severity="Low"
        )
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    try:
        # First verify the plan belongs to this employee and get details for logging
        cursor.execute("""
            SELECT plan_type, provider, status
            FROM savings_plans
            WHERE plan_id = %s AND employee_id = %s
        """, (plan_id, employee_id))
        
        plan_info = cursor.fetchone()
        if not plan_info:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to submit change request for non-existent or unauthorized savings plan {plan_id}",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Savings plan not found or access denied'}), 404
        
        plan_type, provider, plan_status = plan_info
        
        # Check if there are too many pending requests for this plan
        cursor.execute("""
            SELECT COUNT(*) FROM savings_plan_requests
            WHERE plan_id = %s AND employee_id = %s AND status = 'Pending'
        """, (plan_id, employee_id))
        
        pending_count = cursor.fetchone()[0]
        if pending_count >= 5:  # Configurable limit
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to submit savings plan change request for plan {plan_id} but already has {pending_count} pending requests",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Too many pending requests for this plan'}), 429

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO savings_plan_requests (employee_id, plan_id, message, status, submitted_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING request_id
            """, (employee_id, plan_id, message, 'Pending', datetime.utcnow()))
            
            request_id = cur.fetchone()[0] if cur.rowcount > 0 else None
        
        conn.commit()
        
        # Log successful audit trail
        message_preview = message[:100] + "..." if len(message) > 100 else message
        log_employee_audit(
            employee_id=employee_id,
            action="submit_savings_change_request",
            details=f"Successfully submitted change request (ID: {request_id}) for savings plan {plan_id} ({plan_type} with {provider}), type: {request_type}, message: '{message_preview}'"
        )
        
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Request submitted successfully.'}), 200
        
    except Exception as e:
        conn.rollback()
        
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error during savings plan change request submission: {str(e)}",
            severity="High"
        )
        
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500