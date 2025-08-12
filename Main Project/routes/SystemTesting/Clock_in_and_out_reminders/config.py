from datetime import datetime, timezone, timedelta
import logging
import os
from flask import current_app
from routes.Auth.utils import get_db_connection
from flask_mail import Message
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# System configuration
SYSTEM_SENDER_ID = 1  # Use a designated system user ID
SYSTEM_SENDER_ROLE = "super_admin"  # Use a role that identifies the system

def check_missing_clock_ins(force_test=False):
    """
    Check for employees who haven't clocked in today and send reminders
    Runs after expected clock-in time plus grace period
    
    Parameters:
        force_test (bool): If True, bypasses time and day checks for testing
    """
    if force_test:
        logging.info("[TEST MODE] Running forced missing clock-in check - bypassing all time restrictions")
    else:
        logging.info("[REMINDER] Running standard missing clock-in check")
    
    # Get current date and time in UTC
    now = datetime.now(timezone.utc)
    today = now.date()
    
    # Only run this check during work days (Monday-Friday) unless forced for testing
    if now.weekday() >= 5 and not force_test:  # 5=Saturday, 6=Sunday
        logging.info("[REMINDER] Skipping clock-in check on weekend")
        return
    
    # Only run this check if it's after the grace period (9:30 AM) unless forced for testing
    if not force_test:
        shift_start = datetime.combine(today, datetime.strptime("09:00:00", "%H:%M:%S").time()).replace(tzinfo=timezone.utc)
        reminder_time = shift_start + timedelta(minutes=30)
        
        if now < reminder_time:
            logging.info("[REMINDER] Too early to send clock-in reminders")
            return
    else:
        logging.info("[TEST MODE] Time is now: " + now.strftime("%H:%M:%S") + " - Would normally only run after 09:30 AM UTC")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get all active employees who haven't clocked in today
        query = """
            SELECT e.employee_id, e.role_id, e.email, e.first_name, e.last_name, e.status
            FROM employees e
            WHERE e.account_status = 'Activated'
            AND e.employee_id NOT IN (
                -- Employees who have already clocked in today
                SELECT employee_id FROM attendance_logs 
                WHERE date = %s
            )
        """
        
        # Log the query being executed in test mode
        if force_test:
            logging.info(f"[TEST MODE] Executing query: {query.replace('%s', str(today))}")
            
        cursor.execute(query, (today,))
        
        missing_employees = cursor.fetchall()
        
        if force_test:
            logging.info(f"[TEST MODE] Found {len(missing_employees)} employees who haven't clocked in today")
            
            # If no employees found for testing, log a clear message
            if len(missing_employees) == 0:
                logging.warning("[TEST MODE] No missing clock-ins found! This may be because all employees have clock-in records for today.")
                logging.warning("[TEST MODE] To properly test, use the setup-test-data endpoint first to create test conditions.")
                return
        else:
            logging.info(f"[REMINDER] Found {len(missing_employees)} employees who haven't clocked in today")
        
        reminders_sent = 0
        for employee in missing_employees:
            employee_id, role_id, email, first_name, last_name, status = employee
            full_name = f"{first_name} {last_name}"
            
            # Skip employees on leave or with other valid status
            if status and status.lower() in ('on leave', 'vacation', 'sick leave') and not force_test:
                logging.info(f"[REMINDER] Skipping {full_name} due to status: {status}")
                continue
                
            # Log the missing clock-in
            if force_test:
                logging.info(f"[TEST MODE] Sending reminder to {full_name} (ID: {employee_id}, Email: {email})")
            else:
                logging.info(f"[REMINDER] Employee {full_name} (ID: {employee_id}, Status: {status}) hasn't clocked in today")
            
            # Send notification to the employee
            subject = "Missing Clock-In Reminder"
            message = f"Hi {first_name}, our system shows you haven't clocked in today. Please clock in as soon as possible or contact HR if you're not working today."
            
            # Send through available channels
            send_app_notification(employee_id, role_id, subject, message)
            
            # Also send via email if available
            if email:
                success = send_clock_reminder_email(email, subject, message)
                if force_test:
                    log_status = "SUCCESS" if success else "FAILED"
                    logging.info(f"[TEST MODE] Email to {email}: {log_status}")
            
            reminders_sent += 1
                
        if force_test:
            logging.info(f"[TEST MODE] Clock-in reminder test complete: {reminders_sent} reminders sent")
            
    except Exception as e:
        logging.error(f"[{'TEST MODE' if force_test else 'REMINDER'}] Error checking for missing clock-ins: {e}")
        import traceback
        logging.error(traceback.format_exc())
        raise  # Re-raise in test mode to ensure errors are reported
    finally:
        cursor.close()
        conn.close()

def check_missing_clock_outs(force_test=False):
    """
    Check for employees who clocked in but didn't clock out
    Runs after expected clock-out time plus grace period
    
    Parameters:
        force_test (bool): If True, bypasses time and day checks for testing
    """
    if force_test:
        logging.info("[TEST MODE] Running forced missing clock-out check - bypassing all time restrictions")
    else:
        logging.info("[REMINDER] Running standard missing clock-out check")
    
    # Get current date and time in UTC
    now = datetime.now(timezone.utc)
    today = now.date()
    
    # Only run this check during work days (Monday-Friday) unless forced for testing
    if now.weekday() >= 5 and not force_test:  # 5=Saturday, 6=Sunday
        logging.info("[REMINDER] Skipping clock-out check on weekend")
        return
    
    # Only run this check if it's after the grace period (5:30 PM) unless forced for testing
    if not force_test:
        shift_end = datetime.combine(today, datetime.strptime("17:00:00", "%H:%M:%S").time()).replace(tzinfo=timezone.utc)
        reminder_time = shift_end + timedelta(minutes=30)
        
        if now < reminder_time:
            logging.info("[REMINDER] Too early to send clock-out reminders")
            return
    else:
        logging.info("[TEST MODE] Time is now: " + now.strftime("%H:%M:%S") + " - Would normally only run after 17:30 PM UTC")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get all employees who clocked in today but haven't clocked out
        query = """
            SELECT a.employee_id, e.role_id, e.email, e.first_name, e.last_name, e.status, a.clock_in_time
            FROM attendance_logs a
            JOIN employees e ON a.employee_id = e.employee_id
            WHERE a.date = %s
            AND e.account_status = 'Activated'
            AND a.clock_in_time IS NOT NULL
            AND a.clock_out_time IS NULL
        """
        
        # Log the query being executed in test mode
        if force_test:
            logging.info(f"[TEST MODE] Executing query: {query.replace('%s', str(today))}")
        
        cursor.execute(query, (today,))
        
        missing_clock_outs = cursor.fetchall()
        
        if force_test:
            logging.info(f"[TEST MODE] Found {len(missing_clock_outs)} employees who haven't clocked out today")
            
            # If no employees found for testing, log a clear message
            if len(missing_clock_outs) == 0:
                logging.warning("[TEST MODE] No missing clock-outs found! This may be because all employees who clocked in have already clocked out.")
                logging.warning("[TEST MODE] To properly test, use the setup-test-data endpoint first to create test conditions.")
                return
        else:
            logging.info(f"[REMINDER] Found {len(missing_clock_outs)} employees who haven't clocked out today")
        
        reminders_sent = 0
        for employee in missing_clock_outs:
            employee_id, role_id, email, first_name, last_name, status, clock_in_time = employee
            full_name = f"{first_name} {last_name}"
            
            # Format clock-in time for message
            clock_in_str = clock_in_time.strftime("%I:%M %p") if clock_in_time else "earlier today"
            
            # Log the missing clock-out
            if force_test:
                logging.info(f"[TEST MODE] Sending reminder to {full_name} (ID: {employee_id}, Email: {email})")
            else:
                logging.info(f"[REMINDER] Employee {full_name} (ID: {employee_id}, Status: {status}) hasn't clocked out today")
            
            # Send notification to the employee
            subject = "Missing Clock-Out Reminder"
            message = f"Hi {first_name}, our system shows you clocked in at {clock_in_str} but haven't clocked out. Please remember to clock out before leaving."
            
            # Send through available channels
            send_app_notification(employee_id, role_id, subject, message)
            
            # Also send via email if available
            if email:
                success = send_clock_reminder_email(email, subject, message)
                if force_test:
                    log_status = "SUCCESS" if success else "FAILED"
                    logging.info(f"[TEST MODE] Email to {email}: {log_status}")
            
            reminders_sent += 1
        
        if force_test:
            logging.info(f"[TEST MODE] Clock-out reminder test complete: {reminders_sent} reminders sent")
                
    except Exception as e:
        logging.error(f"[{'TEST MODE' if force_test else 'REMINDER'}] Error checking for missing clock-outs: {e}")
        import traceback
        logging.error(traceback.format_exc())
        if force_test:
            raise  # Re-raise in test mode to ensure errors are reported
    finally:
        cursor.close()
        conn.close()
          
def send_app_notification(employee_id, role_id, subject, message):
    """
    Send in-app notification using the existing messages table
    """
    logging.info(f"[REMINDER] Sending app notification to employee {employee_id}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Insert notification into the messages table using the existing structure
        query = """
            INSERT INTO messages 
            (sender_id, sender_role, receiver_id, receiver_role, subject, body)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        values = (
            SYSTEM_SENDER_ID,       # System sender ID
            SYSTEM_SENDER_ROLE,     # System sender role
            employee_id,            # Receiver ID
            role_id,                # Receiver role
            subject,                # Subject
            message                 # Body
        )
        cursor.execute(query, values)
        conn.commit()
        logging.info(f"[REMINDER] Successfully sent app notification to employee {employee_id}")
        return True
    except Exception as e:
        conn.rollback()
        logging.error(f"[REMINDER] Failed to send app notification: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def send_clock_reminder_email(email, subject, message):
    """
    Send email notification using the exact same logic as 2FA system
    """
    logging.debug(f"[REMINDER EMAIL] Sending email to {email}")

    try:
        from app import mail
        sender_email = os.getenv("EMAIL_USER")
        if not sender_email:
            logging.error("❌ EMAIL_USER not set in .env")
            return False

        logging.debug(f"[REMINDER EMAIL] Preparing to send email: sender={sender_email}, recipient={email}")
        msg = Message(
            subject=subject,
            sender=sender_email,
            recipients=[email]
        )
        msg.body = message

        mail.send(msg)
        logging.info(f"✅ Reminder email sent successfully to {email}")
        return True

    except Exception as e:
        logging.error(f"❌ Email error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False
    
def init_attendance_scheduler(app):
    """Initialize the attendance reminder scheduler"""
    scheduler = BackgroundScheduler()
    
    # Clock-in reminders
    # First reminder at 9:30 AM every weekday
    scheduler.add_job(
        check_missing_clock_ins,
        CronTrigger(day_of_week='mon-fri', hour=9, minute=30),
        id='check_missing_clock_ins_morning',
        max_instances=1,
        replace_existing=True
    )
    
    # Second reminder at 10:30 AM for persistent offenders
    scheduler.add_job(
        check_missing_clock_ins,
        CronTrigger(day_of_week='mon-fri', hour=10, minute=30),
        id='check_missing_clock_ins_late_morning',
        max_instances=1,
        replace_existing=True
    )
    
    # Clock-out reminders
    # First reminder at 5:30 PM every weekday
    scheduler.add_job(
        check_missing_clock_outs,
        CronTrigger(day_of_week='mon-fri', hour=17, minute=30),
        id='check_missing_clock_outs_evening',
        max_instances=1,
        replace_existing=True
    )
    
    # Second reminder at 6:30 PM for persistent offenders
    scheduler.add_job(
        check_missing_clock_outs,
        CronTrigger(day_of_week='mon-fri', hour=18, minute=30),
        id='check_missing_clock_outs_late_evening',
        max_instances=1,
        replace_existing=True
    )
    
    scheduler.start()
    app.scheduler = scheduler  # Store scheduler reference on app
    
    # Make sure scheduler shuts down with the app
    import atexit
    atexit.register(lambda: scheduler.shutdown())