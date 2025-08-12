from datetime import datetime, timedelta
import logging
import os
import bcrypt
from flask import Blueprint, Response, render_template, jsonify, request, send_file, url_for
import psycopg2
from routes.Auth.audit import log_audit, log_incident
from routes.Auth.token import token_required_with_roles, token_required_with_roles_and_2fa
from routes.Auth.utils import get_db_connection
from . import admin_bp
from extensions import csrf
from PIL import Image
import io

# Shell route — HTML only
@admin_bp.route('/reportingandanalytics', methods=['GET'])
def reporting_and_analytics_page():
    return render_template('Admin/ReportingAndAnalytics.html')

# route for displaying datas such as log audits for admins
@csrf.exempt
@admin_bp.route('/reportingandanalytics_data', methods=['GET', 'POST'])
@token_required_with_roles_and_2fa(required_actions=["reporting_and_analytics_data"])
def reporting_and_analytics_data(admin_id, role, role_id):
    logging.debug("\n=== REPORTING & ANALYTICS DATA REQUEST ===")
    logging.debug(f"Authenticated as {role} ID {admin_id}")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Get total number of employees
        cursor.execute("SELECT COUNT(*) FROM employees;")
        total_employees = cursor.fetchone()[0]

        # Handle audit trail data
        selected_date = None
        if request.method == 'POST':
            data = request.get_json()
            selected_date = data.get('selected_date')

        if selected_date:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
            start_date = date_obj.strftime('%Y-%m-%d 00:00:00')
            end_date = date_obj.strftime('%Y-%m-%d 23:59:59')
            cursor.execute("""
                SELECT 
                    at.audit_id, 
                    at.action, 
                    at.details, 
                    at.timestamp, 
                    at.category,
                    at.compliance_status,
                    at.role_id,
                    r.role_name
                FROM audit_trail_admin at
                LEFT JOIN roles r ON r.role_id = at.role_id
                WHERE at.timestamp BETWEEN %s AND %s
                ORDER BY at.timestamp DESC
            """, (start_date, end_date))
        else:
            cursor.execute("""
                SELECT 
                    at.audit_id, 
                    at.action, 
                    at.details, 
                    at.timestamp, 
                    at.category,
                    at.compliance_status,
                    at.role_id,
                    r.role_name
                FROM audit_trail_admin at
                LEFT JOIN roles r ON r.role_id = at.role_id
                ORDER BY at.timestamp DESC
                LIMIT 50
            """)

        rows = cursor.fetchall()
        audit_entries = []
        for row in rows:
            entry = {
                "audit_id": row["audit_id"],
                "action": row["action"],
                "details": row["details"],
                "timestamp": row["timestamp"].strftime('%Y-%m-%d %H:%M:%S') if row["timestamp"] else None,
                "category": row["category"],
                "compliance_status": row["compliance_status"],
                "role_id": row["role_id"],
                "role_name": row["role_name"]
            }
            audit_entries.append(entry)

        cursor.close()
        conn.close()

        # Audit: log reporting and analytics data access
        log_audit(admin_id, role, "reporting_and_analytics_data", "Viewed reporting and analytics dashboard data")
        return jsonify({
            "total_employees": total_employees,
            "audit_entries": audit_entries,
            "admin_id": admin_id,
            "admin_role": role
        })

    except Exception as e:
        logging.error(f"Error fetching reporting data: {e}", exc_info=True)
        if conn:
            conn.close()
        log_incident(admin_id, role, f"Error fetching reporting and analytics data: {e}", severity="High")
        return jsonify({"error": "Internal Server Error"}), 500
   
    
#route for logging exporting reports
@csrf.exempt
@admin_bp.route('/api/log_export', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["log_export_action"])
def log_export_action(admin_id, role, role_id):
    try:
        print(f"[DEBUG] log_export_action called by Admin ID: {admin_id}, Role: {role}")
        data = request.json
        print(f"[DEBUG] Received data: {data}")
        export_type = data.get('export_type')
        report_type = data.get('report_type')

        log_audit(admin_id, role, f"export_{export_type}", f"Exported {report_type} report as {export_type}")
        print("[DEBUG] Audit log recorded successfully.")
        return jsonify({'success': True})
    
    except Exception as e:
        print(f"[ERROR] Export Audit Log Error: {e}")
        log_incident(admin_id, role, f"Error logging export action: {e}", severity="High")
        return jsonify({'error': str(e)}), 500

# API to get all the reports 
@csrf.exempt
@admin_bp.route('/generate_reports', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["generate_reports"])
def generate_reports(admin_id, role, role_id):
    try:
        report_type = request.args.get('report_type', 'all')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        print(f"[DEBUG] generate_reports called")
        print(f"[DEBUG] Params - Admin ID: {admin_id}, Role: {role}, Report Type: {report_type}, Start: {start_date}, End: {end_date}")
        
        if not start_date or not end_date:
            return jsonify({"error": "Missing start_date or end_date parameters"}), 400
        
        reports = {}
        
        conn = get_db_connection()
        print("[DEBUG] DB connection established.")

        # Attendance Report
        if report_type in ["attendance", "all"]:
            try:
                cursor = conn.cursor()
                print("[DEBUG] Running attendance query...")
                cursor.execute("""
                    SELECT date, AVG(hours_worked) 
                    FROM attendance_logs
                    WHERE date BETWEEN %s AND %s
                    GROUP BY date ORDER BY date
                """, (start_date, end_date))
                data = cursor.fetchall()
                cursor.close()
                print(f"[DEBUG] Attendance Data: {data}")
                reports["attendance"] = {
                    "labels": [str(row[0]) for row in data],
                    "data": [float(row[1]) for row in data]
                }
                print("[DEBUG] Attendance report parsed successfully.")
            except Exception as e:
                print(f"[ERROR] Attendance report error: {e}")
                log_incident(admin_id, role, f"Error generating attendance report: {e}", severity="High")
                return jsonify({'error': f"Attendance report error: {str(e)}"}), 500

        # Payroll Report
        if report_type in ["payroll", "all"]:
            try:
                cursor = conn.cursor()
                print("[DEBUG] Running payroll query...")
                cursor.execute("SELECT employee_id, net_salary, created_at FROM payroll WHERE created_at BETWEEN %s AND %s", (start_date, end_date))
                data = cursor.fetchall()
                cursor.close()
                print(f"[DEBUG] Payroll Raw Data: {data}")

                # Example processing - sum by employee
                from collections import defaultdict
                payroll_summary = defaultdict(float)
                for emp_id, amount, created_at in data:
                    payroll_summary[emp_id] += float(amount)
                
                reports["payroll"] = {
                    "labels": list(map(str, payroll_summary.keys())),
                    "data": list(payroll_summary.values())
                }
                print("[DEBUG] Payroll report parsed successfully.")
            except Exception as e:
                print(f"[ERROR] Payroll report error: {e}")
                log_incident(admin_id, role, f"Error generating payroll report: {e}", severity="High")
                return jsonify({'error': f"Payroll report error: {str(e)}"}), 500

        # Performance Report
        if report_type in ["performance", "all"]:
            try:
                cursor = conn.cursor()
                print("[DEBUG] Running performance query...")
                cursor.execute("""
                    SELECT EXTRACT(MONTH FROM gp.updated_at), AVG(gpp.progress_percentage)
                    FROM goal_progress gp
                    JOIN goal_progress_percentage gpp
                      ON gp.progress_percentage_id = gpp.progress_percentage_id
                    WHERE gp.updated_at BETWEEN %s AND %s
                    GROUP BY EXTRACT(MONTH FROM gp.updated_at)
                    ORDER BY EXTRACT(MONTH FROM gp.updated_at)
                """, (start_date, end_date))
                data = cursor.fetchall()
                cursor.close()
                print(f"[DEBUG] Performance Data: {data}")

                reports["performance"] = {
                    "labels": [f"Month {int(row[0])}" for row in data],
                    "data": [float(row[1]) for row in data]
                }
                print("[DEBUG] Performance report parsed successfully.")
            except Exception as e:
                print(f"[ERROR] Performance report error: {e}")
                log_incident(admin_id, role, f"Error generating performance report: {e}", severity="High")
                return jsonify({'error': f"Performance report error: {str(e)}"}), 500

        # Productivity Report
        if report_type in ["productivity", "all"]:
            try:
                cursor = conn.cursor()
                print("[DEBUG] Running productivity query...")
                cursor.execute("""
                    SELECT e.department, COUNT(task_id)
                    FROM tasks t
                    LEFT JOIN employees e ON e.employee_id = t.employee_id
                    WHERE due_date BETWEEN %s AND %s
                    GROUP BY e.department
                """, (start_date, end_date))
                data = cursor.fetchall()
                cursor.close()
                print(f"[DEBUG] Productivity Data: {data}")

                reports["productivity"] = {
                    "labels": [row[0] if row[0] else "Unknown Department" for row in data],
                    "data": [int(row[1]) for row in data]
                }
                print("[DEBUG] Productivity report parsed successfully.")
            except Exception as e:
                print(f"[ERROR] Productivity report error: {e}")
                log_incident(admin_id, role, f"Error generating productivity report: {e}", severity="High")
                return jsonify({'error': f"Productivity report error: {str(e)}"}), 500

        # Finalize
        conn.close()
        print("[DEBUG] DB connection closed.")

        log_audit(admin_id, role, "generate_reports", f"Generated {report_type} reports from {start_date} to {end_date}")
        print("[DEBUG] Audit log recorded.")

        return jsonify(reports)

    except Exception as e:
        print(f"[ERROR] generate_reports general error: {e}")
        log_incident(admin_id, role, f"Error generating reports: {e}", severity="High")
        return jsonify({'error': str(e)}), 500

# API to get attendance data
@admin_bp.route('/api/attendance_report', methods=['GET','POST'])
@token_required_with_roles_and_2fa(required_actions=["get_attendance_report"])
def get_attendance_report(admin_id, role,role_id):
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        print(f"[DEBUG] get_attendance_report from {start_date} to {end_date} by Admin ID: {admin_id}")

        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT date, AVG(hours_worked) 
            FROM attendance_logs
            WHERE date BETWEEN %s AND %s
            GROUP BY date ORDER BY date
        """
        cursor.execute(query, (start_date, end_date))
        data = cursor.fetchall()
        cursor.close()
        conn.close()

        response = {"labels": [row[0] for row in data], "data": [row[1] for row in data]}
        log_audit(admin_id, role, "get_attendance_report", f"Viewed attendance data from {start_date} to {end_date}")
        print("[DEBUG] Attendance report data prepared and audit logged.")
        return jsonify(response)
    
    except Exception as e:
        print(f"[ERROR] get_attendance_report Error: {e}")
        log_incident(admin_id, role, f"Error fetching attendance report: {e}", severity="High")
        return jsonify({'error': str(e)}), 500

# API for payroll data
@admin_bp.route("/api/payroll_report", methods=["GET","POST"])
@token_required_with_roles_and_2fa(required_actions=["payroll_report"])
def payroll_report(admin_id, role, role_id):
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        print(f"[DEBUG] payroll_report from {start_date} to {end_date} by Admin ID: {admin_id}")

        if not start_date or not end_date:
            print("[WARN] Missing start_date or end_date")
            return jsonify({"error": "Missing start_date or end_date"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT payroll_id, employee_id, month, base_salary, hours_worked, overtime_hours, overtime_pay, bonuses,
                   tax_rate, tax, net_salary, created_at, deductions, payment_status, payment_date
            FROM payroll
            WHERE created_at BETWEEN %s AND %s
        """
        cursor.execute(query, (start_date, end_date))
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        data = [dict(zip(columns, row)) for row in results]
        cursor.close()
        conn.close()

        log_audit(admin_id, role, "payroll_report", f"Viewed payroll data from {start_date} to {end_date}")
        print("[DEBUG] Payroll report data fetched and audit logged.")
        return jsonify(data)

    except Exception as e:
        print(f"[ERROR] Payroll API Error: {e}")
        log_incident(admin_id, role, f"Error fetching payroll report: {e}", severity="High")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500
    
# API for performance data
@admin_bp.route('/api/performance_report', methods=['GET',"POST"])
@token_required_with_roles_and_2fa(required_actions=["get_performance_report"])
def get_performance_report(admin_id, role,role_id):
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        print(f"[DEBUG] get_performance_report from {start_date} to {end_date} by Admin ID: {admin_id}")

        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT EXTRACT(MONTH FROM gp.updated_at), AVG(gpp.progress_percentage)
            FROM goal_progress gp
            JOIN goal_progress_percentage gpp
            ON gp.progress_percentage_id = gpp.progress_percentage_id
            WHERE gp.updated_at BETWEEN %s AND %s
            GROUP BY EXTRACT(MONTH FROM gp.updated_at)
            ORDER BY EXTRACT(MONTH FROM gp.updated_at)
        """
        cursor.execute(query, (start_date, end_date))
        data = cursor.fetchall()
        cursor.close()
        conn.close()

        response = {"labels": [f"Month {int(row[0])}" for row in data], "data": [row[1] for row in data]}
        log_audit(admin_id, role, "get_performance_report", f"Viewed performance data from {start_date} to {end_date}")
        print("[DEBUG] Performance report fetched and audit logged.")
        return jsonify(response)
    
    except Exception as e:
        print(f"[ERROR] get_performance_report Error: {e}")
        log_incident(admin_id, role, f"Error fetching performance report: {e}", severity="High")
        return jsonify({'error': str(e)}), 500

# API for productivity data
@admin_bp.route('/api/productivity_report', methods=['GET',"POST"])
@token_required_with_roles_and_2fa(required_actions=["get_productivity_report"])
def get_productivity_report(admin_id, role,role_id):
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        print(f"[DEBUG] get_productivity_report from {start_date} to {end_date} by Admin ID: {admin_id}")

        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT e.department, COUNT(task_id)
            FROM tasks t
            LEFT JOIN employees e ON e.employee_id = t.employee_id
            WHERE due_date BETWEEN %s AND %s
            GROUP BY e.department
        """
        cursor.execute(query, (start_date, end_date))
        data = cursor.fetchall()
        cursor.close()
        conn.close()

        response = {
            "labels": [row[0] if row[0] is not None else "Unknown Department" for row in data],
            "data": [row[1] for row in data]
        }

        log_audit(admin_id, role, "get_productivity_report", f"Viewed productivity data from {start_date} to {end_date}")
        print("[DEBUG] Productivity report fetched and audit logged.")
        return jsonify(response)

    except Exception as e:
        print(f"[ERROR] get_productivity_report Error: {e}")
        log_incident(admin_id, role, f"Error fetching productivity report: {e}", severity="High")
        return jsonify({'error': str(e)}), 500
