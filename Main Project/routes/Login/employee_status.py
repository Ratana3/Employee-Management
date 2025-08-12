#route for checking if employee account is terminated and deactivated 
from venv import logger

from flask import g, jsonify
from routes.Auth.token import employee_jwt_required
from routes.Auth.utils import get_db_connection
from . import login_bp

@login_bp.route('/api/employee_status', methods=['GET'])
@employee_jwt_required(check_jti=True)
def check_employee_status():
    employee_id = g.employee_id  # Set by the decorator

    logger.debug(f"Checking status for employee_id: {employee_id}")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        logger.debug("Connected to database, executing status query...")
        cur.execute("SELECT account_status FROM employees WHERE employee_id = %s", (employee_id,))
        row = cur.fetchone()

        cur.close()
        conn.close()
        logger.debug("Database connection closed.")

        if not row:
            logger.warning(f"No status found for employee_id: {employee_id}")
            return jsonify({'status': 'not_found'}), 404

        status = row[0]
        logger.info(f"Status for employee_id {employee_id}: {status}")

        if status in ['Terminated', 'Deactivated']:
            logger.warning(f"Employee {employee_id} is {status}. Returning 403.")
            return jsonify({'status': status}), 403

        logger.debug(f"Employee {employee_id} is active. Returning 200.")
        return jsonify({'status': status}), 200

    except Exception as e:
        logger.exception("Exception occurred while checking employee status.")
        return jsonify({'error': str(e)}), 500
    

@login_bp.route('/validate_token', methods=['GET'])
@employee_jwt_required()
def validate_token():
    return jsonify({"valid": True}), 200

