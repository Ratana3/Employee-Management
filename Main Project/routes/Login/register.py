import logging
import os
from venv import logger
import bcrypt
from flask import jsonify, render_template, request
from routes.Auth.utils import get_db_connection
from . import login_bp




@login_bp.route('/get_roles', methods=['GET'])
def get_roles():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT role_name, role_id FROM roles")  # Fetch role names
        roles = [{"role_name": row[0],"role_id": row[1]} for row in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify({"roles": roles})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# =================== Role Information ===================

# function for inserting the account into employee or admin table based on roles

# these roles will be inserted into employees table when you choose one of the roles below to register an account
ROLES_EMPLOYEES_TABLE = ["employee", "hr", "admin"]  
# these roles will be inserted into admins table when you choose one of the roles below to register an account
ROLES_ADMINS_TABLE = ["admin", "manager", "hr"]

# if the same role appear inside "ROLES_EMPLOYEES_TABLE" and also "ROLES_ADMINS_TABLE" 
# then registering an account with that role will create you an employee account and also an admin account automatically

# =================== Role Information ===================

@login_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        logger.debug('GET request received, rendering registration page')
        return render_template("Login/register.html")

    try:
        data = request.json
        logger.debug(f'POST data received: {data}')
        
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        email = data.get('email')
        role = data.get('role')
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        date_of_birth = data.get('date_of_birth')
        gender = data.get('gender')

        # Check if all fields are provided
        if not all([first_name, last_name, email, role, password, confirm_password, date_of_birth, gender]):
            logger.warning('Missing required fields')
            return jsonify({"error": "All fields are required"}), 400

        # Check if passwords match
        if password != confirm_password:
            logger.warning('Passwords do not match')
            return jsonify({"error": "Passwords do not match"}), 400

        # Ensure role is an integer
        try:
            role = int(role)
        except ValueError:
            logger.warning(f'Invalid role ID format: {role}')
            return jsonify({"error": "Invalid role ID"}), 400

        # Hash the password using bcrypt
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
        logger.debug('Password hashed successfully')

        # Database operations
        conn = get_db_connection()
        cur = conn.cursor()

        # Fetch role name from DB based on role_id
        cur.execute("SELECT role_name FROM roles WHERE role_id = %s", (role,))
        role_row = cur.fetchone()

        if not role_row:
            logger.warning(f'Invalid role ID: {role}')
            return jsonify({"error": "Invalid role selected"}), 400

        role_name = role_row[0].lower()

        # --- ROLE TABLE LOGIC START ---
        ROLES_EMPLOYEES_TABLE = ["employee", "hr", "admin"]
        ROLES_ADMINS_TABLE = ["admin", "manager", "hr"]

        inserted_tables = []

        # Insert into employees table if role is in the list, now with role_id
        if role_name in ROLES_EMPLOYEES_TABLE:
            cur.execute(
                "INSERT INTO employees (first_name, last_name, email, password, role_id, date_of_birth, gender) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (first_name, last_name, email, hashed_password, role, date_of_birth, gender)
            )
            inserted_tables.append('employees')

        # Insert into admins table if role is in the list
        if role_name in ROLES_ADMINS_TABLE:
            cur.execute(
                "INSERT INTO admins (first_name, last_name, email, role_id, password, date_of_birth, gender) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (first_name, last_name, email, role, hashed_password, date_of_birth, gender)
            )
            inserted_tables.append('admins')

        if not inserted_tables:
            logger.warning(f'Invalid role selected (no table matches): {role_name}')
            cur.close()
            conn.close()
            return jsonify({"error": "Invalid role selected"}), 400
        # --- ROLE TABLE LOGIC END ---

        conn.commit()
        cur.close()
        conn.close()

        logger.debug(f'User {first_name} {last_name} registered successfully into: {inserted_tables}')
        return jsonify({"message": "User registered successfully"}), 201

    except Exception as e:
        logger.error(f'Error during registration: {str(e)}', exc_info=True)
        return jsonify({"error": str(e)}), 500