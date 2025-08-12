from .utils import get_db_connection, get_role_name

# Log a security or compliance incident by admin or super admin
def log_incident(admin_id, role, description, severity, status="Open"):
    """Logs a security or compliance incident."""
    try:
        # Validate role before proceeding
        if role not in ["admin", "super_admin"]:
            print("⚠️ Invalid role detected, skipping incident log.")
            return  # Prevent logging invalid roles

        conn = get_db_connection()
        cursor = conn.cursor()

        super_admin_id = None  # Default
        normal_admin_id = None  # Default

        if role == "super_admin":
            # Check if the user exists in super_admins table
            cursor.execute("SELECT super_admin_id FROM super_admins WHERE super_admin_id = %s", (admin_id,))
            super_admin_exists = cursor.fetchone()
            if super_admin_exists:
                super_admin_id = admin_id  # Store in correct column
            else:
                print(f"⚠️ Super Admin ID {admin_id} not found, skipping incident log.")
                return  # Prevent logging

        else:  # role == "admin"
            # Check if the user exists in admins table
            cursor.execute("SELECT admin_id FROM admins WHERE admin_id = %s", (admin_id,))
            admin_exists = cursor.fetchone()
            if admin_exists:
                normal_admin_id = admin_id  # Store in correct column
            else:
                print(f"⚠️ Admin ID {admin_id} not found, skipping incident log.")
                return  # Prevent logging

        # Insert incident log with correct column
        cursor.execute("""
            INSERT INTO incident_logs (admin_id, super_admin_id, role, description, severity, status, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (normal_admin_id, super_admin_id, role, description, severity, status))

        conn.commit()
        print(f"🚨 Incident logged: {description} (Severity: {severity})")

    except Exception as e:
        print(f"❌ Incident Log Error: {e}")

    finally:
        cursor.close()
        conn.close()

# Log an audit trail action by admin or super admin
def log_audit(admin_id,role, action, details):
    """Logs an admin or super_admin action in the audit trail."""
    try:
        # Convert role_id to role_name if role is an integer
        if isinstance(role, int):
            role = get_role_name(role)
            if role is None:
                print(f"⚠️ Invalid role ID {role}, skipping audit log.")
                return  

        role = role.lower().strip()  # Normalize role to lowercase

        valid_roles = ["admin", "super_admin", "manager", "hr"]
        if role not in valid_roles:
            print(f"⚠️ Invalid role detected ({role}), skipping audit log.")
            return  

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT role_id FROM roles WHERE role_name = %s", (role,))
        role_id = cursor.fetchone()
        if not role_id:
            print(f"⚠️ Role {role} not found in roles table, skipping audit log.")
            return  

        cursor.execute("""
            INSERT INTO audit_trail_admin (role_id, action, details, timestamp,compliance_status)
            VALUES (%s, %s, %s, NOW(),'Active')
        """, (role_id[0], action, details))

        conn.commit()
        print(f"📝 Audit log recorded: {action} - {details}")

    except Exception as e:
        print(f"🚨 Audit Log Error: {e}")

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


# Log an audit trail action by employee
def log_employee_audit(employee_id, action, details):
    """Logs an employee action in the audit trail."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify employee exists
        cursor.execute("SELECT employee_id FROM employees WHERE employee_id = %s", (employee_id,))
        employee_exists = cursor.fetchone()
        if not employee_exists:
            print(f"⚠️ Employee ID {employee_id} not found, skipping audit log.")
            return

        cursor.execute("""
            INSERT INTO audit_trail_employee (employee_id, action, details, timestamp, compliance_status)
            VALUES (%s, %s, %s, NOW(), 'Active')
        """, (employee_id, action, details))

        conn.commit()
        print(f"📝 Employee audit log recorded: {action} - {details}")

    except Exception as e:
        print(f"🚨 Employee Audit Log Error: {e}")

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# Log a security or compliance incident by employee
def log_employee_incident(employee_id, description, severity, status="Open"):
    """Logs a security or compliance incident involving an employee."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify employee exists
        cursor.execute("SELECT employee_id FROM employees WHERE employee_id = %s", (employee_id,))
        employee_exists = cursor.fetchone()
        if not employee_exists:
            print(f"⚠️ Employee ID {employee_id} not found, skipping incident log.")
            return

        # Insert incident log
        cursor.execute("""
            INSERT INTO incident_logs_employee (employee_id, incident_type, description, severity_level, status, reported_at, timestamp)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
        """, (employee_id, "system", description, severity, status))

        conn.commit()
        print(f"🚨 Employee incident logged: {description} (Severity: {severity})")

    except Exception as e:
        print(f"❌ Employee Incident Log Error: {e}")

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()