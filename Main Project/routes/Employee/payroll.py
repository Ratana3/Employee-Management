import logging
import os
from flask import current_app, g, jsonify, render_template, request, send_file, send_from_directory, url_for
import psycopg2
from routes.Auth.token import employee_jwt_required,verify_employee_token
from routes.Auth.two_authentication import require_employee_2fa
from routes.Auth.utils import get_db_connection
from . import employee_bp
from extensions import csrf
import pandas as pd
import io
import openpyxl
from flask import g
from routes.Auth.decorator import generate_pdf
from routes.Auth.audit import log_employee_audit,log_employee_incident

@employee_bp.route('/payroll')
def payroll_page_shell():
    return render_template('Employee/Payroll.html')

@employee_bp.route('/download/payslip/<int:payroll_id>')
@employee_jwt_required()
@require_employee_2fa
def download_payslip(payroll_id):
    # Locate and send the payslip PDF (implement this as per your logic)
    file_path = f"static/payslips/payslip_{payroll_id}.pdf"
    return send_file(file_path, as_attachment=True)
 
@employee_bp.route('/employee/TaxDocuments/<filename>')
@employee_jwt_required()
def download_tax_document(filename):
    # The decorator sets g.employee_id so you can use it for authorization if desired
    employee_id = g.employee_id
    
    if not employee_id:
        log_employee_incident(
            employee_id=None,
            description=f"Unauthorized tax document download attempt for file '{filename}' - no employee_id in session",
            severity="High"
        )
        return "Unauthorized", 401

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if the file exists and belongs to the employee
        cursor.execute("""
            SELECT file_path, document_type, tax_year, employee_id 
            FROM tax_documents 
            WHERE file_path = %s
        """, (filename,))
        result = cursor.fetchone()
        
        if not result:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to download non-existent tax document: '{filename}'",
                severity="Medium"
            )
            cursor.close()
            conn.close()
            return "File not found", 404
        
        file_path, document_type, tax_year, document_employee_id = result
        
        # Verify the document belongs to the requesting employee
        if document_employee_id != employee_id:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to download unauthorized tax document '{filename}' belonging to employee {document_employee_id}",
                severity="High"
            )
            cursor.close()
            conn.close()
            return "Access denied", 403

        cursor.close()
        conn.close()

        tax_docs_dir = os.path.join(current_app.root_path, "TaxDocuments")
        try:
            # Log successful audit trail
            log_employee_audit(
                employee_id=employee_id,
                action="download_tax_document",
                details=f"Successfully downloaded tax document '{filename}': {document_type} for tax year {tax_year}"
            )
            
            return send_from_directory(tax_docs_dir, filename, as_attachment=True)
        except FileNotFoundError:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Tax document '{filename}' exists in database but file not found on server filesystem",
                severity="High"
            )
            return "File not found on server", 404
            
    except Exception as e:
        # Log incident for system error
        log_employee_incident(
            employee_id=employee_id,
            description=f"System error during tax document download for '{filename}': {str(e)}",
            severity="High"
        )
        
        cursor.close()
        conn.close()
        return "Internal server error", 500

# Route to fetch tax documents for an employee
@employee_bp.route('/get-tax-documents', methods=['GET'])
@employee_jwt_required()
def get_tax_documents():
    try:
        employee_id = g.employee_id  # Get the logged-in employee ID from the decorator
        
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized tax documents access attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT document_id, tax_year, document_type, file_path, created_at 
            FROM tax_documents 
            WHERE employee_id = %s 
            ORDER BY tax_year DESC, created_at DESC
        """, (employee_id,))
        documents = cursor.fetchall()

        cursor.close()
        conn.close()

        tax_docs = []
        years = set()
        document_types = {}
        
        for doc in documents:
            document_id, tax_year, document_type, file_path, created_at = doc
            years.add(tax_year)
            document_types[document_type] = document_types.get(document_type, 0) + 1
            
            tax_docs.append({
                'document_id': document_id,
                'tax_year': tax_year,
                'document_type': document_type,
                'file_path': file_path
            })

        # Log successful audit trail
        year_range = f"{min(years)}-{max(years)}" if len(years) > 1 else str(list(years)[0]) if years else "none"
        type_summary = ', '.join([f"{count} {dtype}" for dtype, count in document_types.items()]) if document_types else "none"
        
        log_employee_audit(
            employee_id=employee_id,
            action="view_tax_documents",
            details=f"Retrieved {len(tax_docs)} tax documents for years {year_range}: {type_summary}"
        )

        return jsonify({'status': 'success', 'data': tax_docs}), 200

    except Exception as e:
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while fetching tax documents: {str(e)}",
            severity="High"
        )
        
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@employee_bp.route('/api/payroll', methods=['GET'])
@employee_jwt_required()
def api_payroll_info():
    try:
        user_id = g.employee_id
        
        if not user_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized payroll information access attempt - no employee_id in session",
                severity="High"
            )
            return jsonify({'error': 'Unauthorized'}), 401
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Fetch employee info
        cursor.execute("""
            SELECT employee_id, first_name, last_name, email, phone_number,
                   department, date_hired, address1, address2
            FROM employees WHERE employee_id = %s
        """, (user_id,))
        user = cursor.fetchone()

        if not user:
            log_employee_incident(
                employee_id=user_id,
                description=f"Payroll access attempted but employee {user_id} not found in database",
                severity="High"
            )
            cursor.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 404

        # Fetch bank details
        cursor.execute("""
            SELECT bd.bank_name, bd.bank_account_number, e.email, bd.account_name,e.employee_id
            FROM bank_details bd
            JOIN employees e ON e.employee_id = bd.employee_id
            WHERE e.employee_id = %s
        """, (user_id,))
        bank = cursor.fetchone()

        # Latest payroll
        cursor.execute("""
            SELECT * FROM payroll
            WHERE employee_id = %s
            ORDER BY payment_date DESC LIMIT 1
        """, (user_id,))
        latest_payroll = cursor.fetchone()

        # Tax documents
        cursor.execute("""
            SELECT * FROM tax_documents
            WHERE employee_id = %s
            ORDER BY tax_year DESC
        """, (user_id,))
        tax_docs = cursor.fetchall()

        # Latest tax summary
        cursor.execute("""
            SELECT * FROM tax_records
            WHERE employee_id = %s
            ORDER BY created_at DESC LIMIT 1
        """, (user_id,))
        tax_summary = cursor.fetchone()

        # Payment history
        cursor.execute("""
            SELECT month, net_salary FROM payroll
            WHERE employee_id = %s AND payment_status = 'Paid'
            ORDER BY payment_date DESC LIMIT 5
        """, (user_id,))
        payment_history = cursor.fetchall()

        profile_picture_url = url_for('employee_bp.profile_picture', user_id=user_id)

        # Analyze data for logging
        latest_payment = float(latest_payroll['net_salary']) if latest_payroll and latest_payroll['net_salary'] else 0
        total_payments = sum(float(row['net_salary']) for row in payment_history if row['net_salary'])
        has_bank_details = bank is not None
        tax_doc_count = len(tax_docs)
        has_tax_summary = tax_summary is not None
        
        # Log successful audit trail
        bank_info = f"with {bank['bank_name']}" if has_bank_details else "no bank details"
        payment_info = f"latest: ${latest_payment:.2f}, total (last 5): ${total_payments:.2f}" if latest_payment > 0 else "no payments"
        tax_info = f"{tax_doc_count} tax documents" + (", with tax summary" if has_tax_summary else ", no tax summary")
        
        log_employee_audit(
            employee_id=user_id,
            action="view_payroll_info",
            details=f"Accessed comprehensive payroll information for {user['first_name']} {user['last_name']} in {user['department']}: {bank_info}, {payment_info}, {tax_info}"
        )

        cursor.close()
        conn.close()

        return jsonify({
            'user': dict(user),
            'bank': dict(bank) if bank else None,
            'latest_payroll': dict(latest_payroll) if latest_payroll else None,
            'tax_docs': [dict(doc) for doc in tax_docs],
            'tax_summary': dict(tax_summary) if tax_summary else None,
            'payment_history': [{'month': row['month'], 'net_salary': row['net_salary']} for row in payment_history],
            'profile_picture_url': profile_picture_url
        })

    except Exception as e:
        logging.error(f"Error in /api/payroll: {e}", exc_info=True)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error while accessing payroll information: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@employee_bp.route('/export-timesheet', methods=['GET'])
@employee_jwt_required()
def export_timesheet():
    try:
        # Get logged-in employee from decorator
        employee_id = g.employee_id
        
        if not employee_id:
            log_employee_incident(
                employee_id=None,
                description="Unauthorized timesheet export attempt - no employee_id in session",
                severity="Medium"
            )
            return jsonify({'error': 'Unauthorized'}), 401
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Query logged-in employee's timesheet
        sql = """
        SELECT 
            e.first_name,
            e.last_name,
            e.email,
            a.date,
            a.clock_in_time,
            a.clock_out_time,
            a.hours_worked,
            a.overtime_hours,
            a.status,
            a.remarks
        FROM 
            employees e
        INNER JOIN 
            attendance_logs a ON e.employee_id = a.employee_id
        WHERE 
            e.employee_id = %s
        ORDER BY a.date DESC
        """

        cur.execute(sql, (employee_id,))
        rows = cur.fetchall()

        if not rows:
            log_employee_incident(
                employee_id=employee_id,
                description="Employee attempted to export timesheet but no attendance records found",
                severity="Low"
            )
            cur.close()
            conn.close()
            return jsonify({'error': 'No timesheet records found'}), 404

        timesheet_list = []
        total_hours = 0
        total_overtime = 0
        status_counts = {}
        date_range = {'start': None, 'end': None}
        
        for row in rows:
            # Analyze data for logging
            hours_worked = float(row['hours_worked']) if row['hours_worked'] else 0
            overtime_hours = float(row['overtime_hours']) if row['overtime_hours'] else 0
            total_hours += hours_worked
            total_overtime += overtime_hours
            
            status = row['status'] or 'Unknown'
            status_counts[status] = status_counts.get(status, 0) + 1
            
            row_date = row['date']
            if row_date:
                if not date_range['start'] or row_date < date_range['start']:
                    date_range['start'] = row_date
                if not date_range['end'] or row_date > date_range['end']:
                    date_range['end'] = row_date
            
            timesheet_list.append({
                "First Name": row['first_name'],
                "Last Name": row['last_name'],
                "Email": row['email'],
                "Date": row['date'].strftime('%Y-%m-%d') if row['date'] else '',
                "Clock In": row['clock_in_time'].strftime('%H:%M') if row['clock_in_time'] else '',
                "Clock Out": row['clock_out_time'].strftime('%H:%M') if row['clock_out_time'] else '',
                "Hours Worked": row['hours_worked'],
                "Overtime Hours": row['overtime_hours'],
                "Status": row['status'],
                "Remarks": row['remarks'] or ''
            })

        df = pd.DataFrame(timesheet_list)
        format_type = request.args.get('format', 'excel')  # Default to 'excel'

        # Log successful audit trail
        status_summary = ', '.join([f"{count} {status}" for status, count in status_counts.items()]) if status_counts else "no records"
        date_range_str = f"from {date_range['start']} to {date_range['end']}" if date_range['start'] and date_range['end'] else "unknown date range"
        
        log_employee_audit(
            employee_id=employee_id,
            action="export_timesheet",
            details=f"Exported {len(timesheet_list)} timesheet records as {format_type} {date_range_str}: {total_hours:.1f}h regular, {total_overtime:.1f}h overtime | Status: {status_summary}"
        )

        if format_type == 'pdf':
            # Generate PDF for Timesheet
            return generate_pdf(df, 'Timesheet')

        # Default to Excel export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Timesheet')

        output.seek(0)
        cur.close()
        conn.close()

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='timesheet_export.xlsx'
        )

    except Exception as e:
        print(f"Error exporting timesheet: {str(e)}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during timesheet export: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500

    finally:
        if 'conn' in locals():
            conn.close()

@employee_bp.route('/export-payroll', methods=['GET'])
@employee_jwt_required()
@require_employee_2fa
def export_payroll():
    import logging
    import io
    import pandas as pd
    from flask import g, request, jsonify, send_file

    conn = None
    try:
        logging.debug("Starting export_payroll route")
        
        # Get logged-in employee from g (set by decorator)
        employee_id = getattr(g, "employee_id", None)
        logging.debug(f"employee_id from g: {employee_id}")

        if not employee_id:
            logging.error("No employee_id found in g")
            log_employee_incident(
                employee_id=None,
                description="Unauthorized payroll export attempt with 2FA - no employee_id in session",
                severity="High"
            )
            return jsonify({'error': 'Unauthorized: No employee_id'}), 401

        conn = get_db_connection()
        logging.debug("Database connection established")

        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Query logged-in employee's payroll
        sql = """
        SELECT 
            e.first_name,
            e.last_name,
            e.email,
            p.month,
            p.base_salary,
            p.hours_worked,
            p.overtime_hours,
            p.overtime_pay,
            p.bonuses,
            p.tax_rate,
            p.tax,
            p.deductions,
            p.net_salary,
            p.payment_status,
            p.payment_date
        FROM 
            employees e
        INNER JOIN 
            payroll p ON e.employee_id = p.employee_id
        WHERE 
            e.employee_id = %s
        ORDER BY p.payment_date DESC, p.month DESC
        """

        logging.debug(f"Executing payroll query for employee_id={employee_id}")
        cur.execute(sql, (employee_id,))
        rows = cur.fetchall()
        logging.debug(f"Payroll rows fetched: {len(rows)}")

        if not rows:
            logging.warning("No payroll records found for employee")
            log_employee_incident(
                employee_id=employee_id,
                description="Employee attempted to export payroll but no payroll records found",
                severity="Low"
            )
            cur.close()
            conn.close()
            return jsonify({'error': 'No payroll records found'}), 404

        payroll_list = []
        total_net_salary = 0
        total_hours = 0
        total_overtime = 0
        total_bonuses = 0
        total_deductions = 0
        payment_statuses = {}
        months_covered = set()
        
        for i, row in enumerate(rows):
            logging.debug(f"Processing row {i}: {row}")
            
            # Analyze data for logging
            net_salary = float(row['net_salary']) if row['net_salary'] else 0
            hours_worked = float(row['hours_worked']) if row['hours_worked'] else 0
            overtime_hours = float(row['overtime_hours']) if row['overtime_hours'] else 0
            bonuses = float(row['bonuses']) if row['bonuses'] else 0
            deductions = float(row['deductions']) if row['deductions'] else 0
            payment_status = row['payment_status'] or 'Unknown'
            month = row['month']
            
            total_net_salary += net_salary
            total_hours += hours_worked
            total_overtime += overtime_hours
            total_bonuses += bonuses
            total_deductions += deductions
            payment_statuses[payment_status] = payment_statuses.get(payment_status, 0) + 1
            if month:
                months_covered.add(month)
            
            payroll_list.append({
                "First Name": row['first_name'],
                "Last Name": row['last_name'],
                "Email": row['email'],
                "Month": month,
                "Base Salary": row['base_salary'],
                "Hours Worked": row['hours_worked'],
                "Overtime Hours": row['overtime_hours'],
                "Overtime Pay": row['overtime_pay'],
                "Bonuses": row['bonuses'],
                "Tax Rate (%)": row['tax_rate'],
                "Tax Amount": row['tax'],
                "Deductions": row['deductions'],
                "Net Salary": row['net_salary'],
                "Payment Status": payment_status,
                "Payment Date": row['payment_date'].strftime('%Y-%m-%d') if row['payment_date'] else ''
            })

        logging.debug(f"Total payroll entries processed: {len(payroll_list)}")
        df = pd.DataFrame(payroll_list)
        logging.debug(f"DataFrame created with shape: {df.shape}")

        format_type = request.args.get('format', 'excel')  # Default to 'excel'
        logging.debug(f"Requested export format: {format_type}")

        # Log successful audit trail
        status_summary = ', '.join([f"{count} {status}" for status, count in payment_statuses.items()]) if payment_statuses else "no payments"
        months_range = f"{min(months_covered)} to {max(months_covered)}" if len(months_covered) > 1 else list(months_covered)[0] if months_covered else "unknown"
        
        log_employee_audit(
            employee_id=employee_id,
            action="export_payroll",
            details=f"Exported {len(payroll_list)} payroll records as {format_type} for months {months_range}: ${total_net_salary:.2f} total net, {total_hours:.1f}h regular, {total_overtime:.1f}h overtime, ${total_bonuses:.2f} bonuses, ${total_deductions:.2f} deductions | Status: {status_summary}"
        )

        if format_type == 'pdf':
            logging.debug("Generating PDF for payroll")
            return generate_pdf(df, 'Payroll')

        # Default to Excel export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Payroll')
        output.seek(0)
        logging.debug("Excel file written to buffer")

        cur.close()
        conn.close()

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='payroll_export.xlsx'
        )

    except Exception as e:
        logging.exception(f"Error exporting payroll: {str(e)}")
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during secure payroll export: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Internal server error'}), 500

    finally:
        if conn:
            logging.debug("Closing database connection")
            conn.close()
                              
@employee_bp.route('/update_bank_details', methods=['POST'])
@employee_jwt_required()
@require_employee_2fa
@csrf.exempt
def update_bank_details():
    import sys
    import traceback

    print("\n[DEBUG][update_bank_details] Route hit", file=sys.stderr)
    try:
        # Fetch employee_id from Flask's g context (set by @employee_jwt_required)
        employee_id = getattr(g, 'employee_id', None)
        print(f"[DEBUG][update_bank_details] employee_id: {employee_id}", file=sys.stderr)

        if not employee_id:
            print("[DEBUG][update_bank_details] Missing employee_id. Unauthorized.", file=sys.stderr)
            log_employee_incident(
                employee_id=None,
                description="Unauthorized bank details update attempt with 2FA - no employee_id in session",
                severity="High"
            )
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

        data = request.get_json()
        print(f"[DEBUG][update_bank_details] Received data: {data}", file=sys.stderr)

        if not data:
            log_employee_incident(
                employee_id=employee_id,
                description="Bank details update attempted with no data provided",
                severity="Low"
            )
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400

        bank_name = data.get('bank_name', '').strip()
        account_number = data.get('account_number', '').strip()
        account_name = data.get('account_name', '').strip()

        print(f"[DEBUG][update_bank_details] bank_name: {bank_name}, account_number: {account_number}, account_name: {account_name}", file=sys.stderr)

        # Validate required fields
        if not all([bank_name, account_number, account_name]):
            missing_fields = []
            if not bank_name: missing_fields.append('bank_name')
            if not account_number: missing_fields.append('account_number')
            if not account_name: missing_fields.append('account_name')
            
            log_employee_incident(
                employee_id=employee_id,
                description=f"Bank details update attempted with missing fields: {', '.join(missing_fields)}",
                severity="Low"
            )
            return jsonify({'status': 'error', 'message': f'Missing required fields: {", ".join(missing_fields)}'}), 400

        # Validate account number (basic validation)
        if len(account_number) < 8 or not account_number.replace('-', '').replace(' ', '').isdigit():
            log_employee_incident(
                employee_id=employee_id,
                description=f"Bank details update attempted with invalid account number format",
                severity="Medium"
            )
            return jsonify({'status': 'error', 'message': 'Invalid account number format'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if bank details exist and get current details for logging
        cursor.execute("""
            SELECT bank_id, bank_name, bank_account_number, account_name 
            FROM bank_details 
            WHERE employee_id = %s
        """, (employee_id,))
        existing = cursor.fetchone()
        print(f"[DEBUG][update_bank_details] Existing bank record: {existing}", file=sys.stderr)

        # Mask account numbers for logging (show only last 4 digits)
        def mask_account_number(acc_num):
            if not acc_num or len(acc_num) < 4:
                return "****"
            return "****" + acc_num[-4:]

        if existing:
            # Update existing
            bank_id, old_bank_name, old_account_number, old_account_name = existing
            
            # Check if any changes were made
            changes = []
            if old_bank_name != bank_name:
                changes.append(f"bank: {old_bank_name} → {bank_name}")
            if old_account_number != account_number:
                changes.append(f"account: {mask_account_number(old_account_number)} → {mask_account_number(account_number)}")
            if old_account_name != account_name:
                changes.append(f"name: {old_account_name} → {account_name}")
            
            if not changes:
                log_employee_audit(
                    employee_id=employee_id,
                    action="update_bank_details",
                    details=f"Attempted bank details update with no changes: {bank_name}, {mask_account_number(account_number)}, {account_name}"
                )
                cursor.close()
                conn.close()
                return jsonify({'status': 'success', 'message': 'No changes detected'})
            
            print(f"[DEBUG][update_bank_details] Updating bank details for employee_id={employee_id}", file=sys.stderr)
            cursor.execute("""
                UPDATE bank_details 
                SET bank_name = %s, bank_account_number = %s, account_name = %s
                WHERE employee_id = %s
            """, (bank_name, account_number, account_name, employee_id))
            print(f"[DEBUG][update_bank_details] Rows affected (update): {cursor.rowcount}", file=sys.stderr)
            
            # Log successful update
            changes_summary = ', '.join(changes)
            log_employee_audit(
                employee_id=employee_id,
                action="update_bank_details",
                details=f"Successfully updated existing bank details: {changes_summary}"
            )
            
        else:
            # Insert new
            print(f"[DEBUG][update_bank_details] Inserting new bank details for employee_id={employee_id}", file=sys.stderr)
            cursor.execute("""
                INSERT INTO bank_details (employee_id, bank_name, bank_account_number, account_name, created_at) 
                VALUES (%s, %s, %s, %s, NOW())
                RETURNING bank_id
            """, (employee_id, bank_name, account_number, account_name))
            
            bank_id = cursor.fetchone()[0] if cursor.rowcount > 0 else None
            print(f"[DEBUG][update_bank_details] Rows affected (insert): {cursor.rowcount}", file=sys.stderr)
            
            # Log successful creation
            log_employee_audit(
                employee_id=employee_id,
                action="update_bank_details",
                details=f"Successfully created new bank details (bank_id: {bank_id}): {bank_name}, {mask_account_number(account_number)}, {account_name}"
            )

        conn.commit()
        print("[DEBUG][update_bank_details] Commit successful", file=sys.stderr)
        cursor.close()
        conn.close()
        print("[DEBUG][update_bank_details] Connection closed", file=sys.stderr)

        return jsonify({'status': 'success'})

    except Exception as e:
        print("[ERROR][update_bank_details] Exception occurred:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=getattr(g, 'employee_id', None),
            description=f"System error during secure bank details update: {str(e)}",
            severity="High"
        )
        
        return jsonify({'status': 'error', 'message': str(e)}), 500