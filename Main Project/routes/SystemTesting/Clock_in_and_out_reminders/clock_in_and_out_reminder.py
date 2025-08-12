from flask import Blueprint, jsonify, render_template, request
from datetime import datetime, timezone
from routes.Auth.utils import get_db_connection
from routes.Auth.audit import log_audit
from routes.Auth.token import token_required_with_roles
from extensions import csrf
import logging
import time
from routes.SystemTesting.Clock_in_and_out_reminders.config import check_missing_clock_ins, check_missing_clock_outs

# Create a dedicated blueprint for reminder testing
test_reminder_bp = Blueprint('test_reminder', __name__)

# Dictionary to store last run time for rate limiting
last_run_time = {
    'clock-in': {},
    'clock-out': {},
    'all': {}
}
# Minimum seconds between test runs per admin
MIN_TEST_INTERVAL = 30

def check_rate_limit(admin_id, test_type):
    """Check if admin has run tests too frequently"""
    current_time = time.time()
    if admin_id in last_run_time[test_type]:
        elapsed = current_time - last_run_time[test_type][admin_id]
        if elapsed < MIN_TEST_INTERVAL:
            return False, int(MIN_TEST_INTERVAL - elapsed)
    
    last_run_time[test_type][admin_id] = current_time
    return True, 0

@test_reminder_bp.route('/admin/test-reminders-main')
def test_reminders_main():
    """Serves the main test page (will check auth via JavaScript)"""
    return render_template('SystemTesting/testingreminders.html')

@test_reminder_bp.route('/admin/test-reminders/content')
@csrf.exempt
@token_required_with_roles(allowed_roles=['admin', 'super_admin'])
def test_reminders_content(admin_id, role, role_id, *args, **kwargs):
    """Protected endpoint that returns the page content after authentication"""
    current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    
    # Get admin username based on role
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if role == 'super_admin':
            cursor.execute("SELECT email FROM super_admins WHERE super_admin_id = %s", (admin_id,))
        else:
            cursor.execute("SELECT email FROM admins WHERE admin_id = %s", (admin_id,))
        
        admin = cursor.fetchone()
        username = admin[0] if admin else "Unknown"
        
        # Log access to the testing page using your function
        log_audit(admin_id, role, 'reminder_test_access', 'Accessed reminder testing page')
    except Exception as e:
        logging.error(f"Error in test_reminders_content: {e}")
        username = "Unknown"
    finally:
        cursor.close()
        conn.close()
    
    return jsonify({
        'success': True,
        'username': username,
        'current_time': current_time
    })

@test_reminder_bp.route('/admin/test-reminders/clock-in', methods=['POST'])
@csrf.exempt
@token_required_with_roles(allowed_roles=['admin', 'super_admin'])
def test_clock_in_reminders(admin_id, role, role_id, *args, **kwargs):
    try:
        # Check rate limiting
        allowed, wait_time = check_rate_limit(admin_id, 'clock-in')
        if not allowed:
            log_audit(admin_id, role, 'reminder_test_clock-in', f'Rate limited, must wait {wait_time} seconds')
            return jsonify({
                'success': False,
                'message': f'Please wait {wait_time} seconds before running another test.',
                'rate_limited': True
            }), 429
        
        logging.info(f"[TEST] {role.capitalize()} {admin_id} manually triggering missing clock-in check")
        check_missing_clock_ins(force_test=True)
        
        log_audit(admin_id, role, 'reminder_test_clock-in', 'Successfully ran clock-in reminder test')
        return jsonify({
            'success': True,
            'message': 'Clock-in reminder check completed successfully.',
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        logging.error(f"[TEST] Error testing clock-in reminders: {e}")
        import traceback
        logging.error(traceback.format_exc())
        log_audit(admin_id, role, 'reminder_test_clock-in', f'Error: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        }), 500

@test_reminder_bp.route('/admin/test-reminders/clock-out', methods=['POST'])
@csrf.exempt
@token_required_with_roles(allowed_roles=['admin', 'super_admin'])
def test_clock_out_reminders(admin_id, role, role_id, *args, **kwargs):
    try:
        # Check rate limiting
        allowed, wait_time = check_rate_limit(admin_id, 'clock-out')
        if not allowed:
            log_audit(admin_id, role, 'reminder_test_clock-out', f'Rate limited, must wait {wait_time} seconds')
            return jsonify({
                'success': False,
                'message': f'Please wait {wait_time} seconds before running another test.',
                'rate_limited': True
            }), 429
        
        logging.info(f"[TEST] {role.capitalize()} {admin_id} manually triggering missing clock-out check")
        check_missing_clock_outs(force_test=True)
        
        log_audit(admin_id, role, 'reminder_test_clock-out', 'Successfully ran clock-out reminder test')
        return jsonify({
            'success': True,
            'message': 'Clock-out reminder check completed successfully.',
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        logging.error(f"[TEST] Error testing clock-out reminders: {e}")
        import traceback
        logging.error(traceback.format_exc())
        log_audit(admin_id, role, 'reminder_test_clock-out', f'Error: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        }), 500

@test_reminder_bp.route('/admin/test-reminders/all', methods=['POST'])
@csrf.exempt
@token_required_with_roles(allowed_roles=['admin', 'super_admin'])
def test_all_reminders(admin_id, role, role_id, *args, **kwargs):
    """
    Simplified version that runs both tests sequentially without special data setup.
    Use setup-test-data with appropriate type before running each test.
    """
    try:
        # Check rate limiting
        allowed, wait_time = check_rate_limit(admin_id, 'all')
        if not allowed:
            log_audit(admin_id, role, 'reminder_test_all', f'Rate limited, must wait {wait_time} seconds')
            return jsonify({
                'success': False,
                'message': f'Please wait {wait_time} seconds before running another test.',
                'rate_limited': True
            }), 429
        
        logging.info(f"[TEST] {role.capitalize()} {admin_id} manually triggering all reminder checks")
        
        results = {
            'clock_in': {'status': 'not run'},
            'clock_out': {'status': 'not run'},
            'note': 'For best results, set up test data for each test type separately before running'
        }
        
        # Run both tests sequentially
        try:
            logging.info("[TEST] Running clock-in reminder check...")
            check_missing_clock_ins(force_test=True)
            results['clock_in']['status'] = 'completed'
            
            logging.info("[TEST] Running clock-out reminder check...")
            check_missing_clock_outs(force_test=True)
            results['clock_out']['status'] = 'completed'
            
        except Exception as e:
            logging.error(f"[TEST] Error running reminder checks: {e}")
            raise
        
        log_audit(admin_id, role, 'reminder_test_all', 'Ran all reminder tests sequentially')
        
        return jsonify({
            'success': True,
            'message': 'All reminder checks completed sequentially. For best results, set up test data for each test type separately.',
            'results': results,
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        logging.error(f"[TEST] Error testing reminders: {e}")
        import traceback
        logging.error(traceback.format_exc())
        log_audit(admin_id, role, 'reminder_test_all', f'Error: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        }), 500
     
@test_reminder_bp.route('/admin/test-reminders/setup-test-data', methods=['POST'])
@csrf.exempt
@token_required_with_roles(allowed_roles=['admin', 'super_admin'])
def setup_reminder_test_data(admin_id, role, role_id, *args, **kwargs):
    """Creates test data for clock-in or clock-out reminder testing"""
    try:
        # Parse and validate input
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': 'Missing request body'}), 400
            
            test_type = data.get('type', 'clock-in')  # Default to clock-in
            if test_type not in ['clock-in', 'clock-out']:
                return jsonify({
                    'success': False, 
                    'message': 'Invalid test type. Must be "clock-in" or "clock-out"'
                }), 400
        except Exception as e:
            return jsonify({'success': False, 'message': f'Invalid request: {str(e)}'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        today = datetime.now(timezone.utc).date()
        
        result = {'success': True, 'actions': [], 'employee_used': None}
        
        # Get a single employee for the requested test
        cursor.execute("""
            SELECT employee_id, email, first_name, last_name, role_id 
            FROM employees 
            WHERE account_status = 'Activated' 
            LIMIT 1
        """)
        employee = cursor.fetchone()
        
        if not employee:
            log_audit(admin_id, role, f'setup_reminder_test_{test_type}', 'No active employees found')
            return jsonify({'success': False, 'message': 'No active employees found for testing'})
            
        employee_id, email, first_name, last_name, emp_role_id = employee
        
        # Clock-in test: Remove any attendance records for today
        if test_type == 'clock-in':
            cursor.execute("DELETE FROM attendance_logs WHERE employee_id = %s AND date = %s", 
                       (employee_id, today))
            result['actions'].append(f"Cleared attendance for {first_name} {last_name} ({email})")
            
        # Clock-out test: Create record with clock-in but no clock-out
        if test_type == 'clock-out':
            # First check if record exists
            cursor.execute("""
                SELECT log_id FROM attendance_logs 
                WHERE employee_id = %s AND date = %s
            """, (employee_id, today))
            
            existing_record = cursor.fetchone()
            current_time = datetime.now(timezone.utc).time()
            
            if existing_record:
                # Update existing record
                cursor.execute("""
                    UPDATE attendance_logs 
                    SET clock_in_time = %s, 
                        clock_out_time = NULL, 
                        status = 'Present'
                    WHERE employee_id = %s AND date = %s
                """, (current_time, employee_id, today))
                result['actions'].append(f"Updated existing record for {first_name} {last_name} with clock-in but no clock-out")
            else:
                # Insert new record
                cursor.execute("""
                    INSERT INTO attendance_logs 
                    (employee_id, date, clock_in_time, clock_out_time, status, role_id)
                    VALUES (%s, %s, %s, NULL, 'Present', %s)
                """, (employee_id, today, current_time, emp_role_id or 1))
                result['actions'].append(f"Created new record for {first_name} {last_name} with clock-in but no clock-out")
        
        conn.commit()
        
        # Add helpful debug info to result
        result['message'] = f"Test data created successfully for {test_type} reminder testing"
        result['employee_used'] = {
            'id': employee_id,
            'name': f"{first_name} {last_name}",
            'email': email
        }
        
        # Add verification info for clock-out test
        if test_type == 'clock-out':
            cursor.execute("""
                SELECT clock_in_time, clock_out_time, status 
                FROM attendance_logs 
                WHERE employee_id = %s AND date = %s
            """, (employee_id, today))
            test_record = cursor.fetchone()
            
            if test_record:
                result['verification'] = {
                    'has_clock_in': test_record[0] is not None,
                    'has_clock_out': test_record[1] is not None,
                    'status': test_record[2]
                }
        
        log_audit(
            admin_id, 
            role, 
            f'setup_reminder_test_{test_type}', 
            f"Created test data for {test_type} using employee {employee_id}"
        )
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error setting up test data: {e}")
        import traceback
        logging.error(traceback.format_exc())
        log_audit(admin_id, role, f'setup_reminder_test_{test_type if "test_type" in locals() else "unknown"}', f'Error: {str(e)}')
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()
            
@test_reminder_bp.route('/admin/recent-reminders', methods=['GET'])
@token_required_with_roles(allowed_roles=['admin', 'super_admin'])
def get_recent_reminders(admin_id, role, role_id, *args, **kwargs):
    try:
        limit = min(int(request.args.get('limit', 20)), 100)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First verify table structure
        cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'messages')")
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            return jsonify({
                'success': False,
                'message': 'Messages table does not exist',
                'reminders': []
            }), 404
        
        # Get reminder messages with employee information
        # Using f-string for LIMIT since parameter binding is causing the error
        cursor.execute(f"""
            SELECT m.message_id, m.receiver_id, m.subject, m.body, m.timestamp,
                   e.first_name, e.last_name, e.email
            FROM messages m
            LEFT JOIN employees e ON m.receiver_id = e.employee_id
            WHERE m.sender_role = 'super_admin' 
            AND (m.subject LIKE '%Clock-In Reminder%' OR m.subject LIKE '%Clock-Out Reminder%')
            ORDER BY m.timestamp DESC
            LIMIT {limit}
        """)
        
        results = cursor.fetchall()
        reminders = []
        
        for row in results:
            message_id, employee_id, subject, body, timestamp, first_name, last_name, email = row
            
            # Determine reminder type
            reminder_type = "Clock-In" if "Clock-In Reminder" in subject else "Clock-Out"
            
            # Create employee name (handle missing names)
            employee_name = "Unknown"
            if first_name and last_name:
                employee_name = f"{first_name} {last_name}"
            
            reminders.append({
                'message_id': message_id,
                'employee_id': employee_id,
                'employee_name': employee_name,
                'email': email or "N/A",
                'type': reminder_type,
                'sent_at': timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp else "Unknown",
                'subject': subject,
                'body': body,
                'success': True  # Assuming all messages in the table were sent successfully
            })
        
        log_audit(admin_id, role, 'view_recent_reminders', f'Viewed {len(reminders)} recent reminders')
        
        return jsonify({
            'success': True,
            'reminders': reminders,
            'count': len(reminders)
        })
        
    except Exception as e:
        logging.error(f"[TEST] Error fetching recent reminders: {e}")
        import traceback
        logging.error(traceback.format_exc())
        log_audit(admin_id, role, 'view_recent_reminders', f'Error: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'reminders': []
        }), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()
                      
# Health check for the reminder system
@test_reminder_bp.route('/admin/test-reminders/health', methods=['GET'])
@token_required_with_roles(allowed_roles=['admin', 'super_admin'])
def reminder_health_check(admin_id, role, role_id, *args, **kwargs):
    conn = None
    cursor = None
    health_status = {
        'database': False,
        'employees': False,
        'messages': False,
        'attendance': False,
        'overall': False
    }
    
    try:
        # Check database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        health_status['database'] = True
        
        # Check employees table
        cursor.execute("SELECT COUNT(*) FROM employees WHERE account_status = 'Activated'")
        active_employees = cursor.fetchone()[0]
        health_status['employees'] = True
        
        # Check messages table
        cursor.execute("SELECT COUNT(*) FROM messages WHERE sender_role = 'system'")
        system_messages = cursor.fetchone()[0]
        health_status['messages'] = True
        
        # Check attendance table
        cursor.execute("SELECT COUNT(*) FROM attendance_logs")
        attendance_records = cursor.fetchone()[0]
        health_status['attendance'] = True
        
        # Overall status is good if all components are good
        health_status['overall'] = all(health_status.values())
        
        log_audit(admin_id, role, 'reminder_system_health_check', 'Successfully performed system health check')
        
        return jsonify({
            'success': True,
            'status': health_status,
            'data': {
                'active_employees': active_employees,
                'system_messages': system_messages,
                'attendance_records': attendance_records
            },
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        logging.error(f"[HEALTH] Reminder system health check failed: {e}")
        import traceback
        logging.error(traceback.format_exc())
        
        # Update health status based on what failed
        if not health_status['database']:
            error_component = 'database connection'
        elif not health_status['employees']:
            error_component = 'employees table'
        elif not health_status['messages']:
            error_component = 'messages table'
        elif not health_status['attendance']:
            error_component = 'attendance table'
        else:
            error_component = 'unknown component'
        
        log_audit(admin_id, role, 'reminder_system_health_check', f'Health check failed at {error_component}: {str(e)}')
            
        return jsonify({
            'success': False,
            'status': health_status,
            'message': f'Health check failed at {error_component}: {str(e)}',
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()