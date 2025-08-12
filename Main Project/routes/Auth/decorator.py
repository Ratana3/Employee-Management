# Decorator for protecting web endpoints with JWT (employee version, redirects on error)
from functools import wraps
import logging
from turtle import color
from flask import g, jsonify, redirect, request, send_file, url_for
from routes.Auth.token import verify_employee_token
from routes.Auth.utils import get_db_connection
from routes.Login import SECRET_KEY
import jwt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import io

def get_token_from_header():
    auth_header = request.headers.get('Authorization', None)
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header.split(' ')[1]
    return None

#function to check if admin is logged in or not before accessing the route 
def login_required(f):
    from routes.Auth.token import get_admin_from_token
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract token from cookie
        token = request.cookies.get('authToken')
        logging.debug(f"Token from cookie: {token}")

        if not token:
            logging.error("No authToken cookie found")
            return redirect(url_for('login.testinglogin'))

        try:
            # Decode and verify the token
            admin_id, role = get_admin_from_token(token)  # You can use the function you already have
            if not admin_id or not role:
                raise ValueError("Invalid token payload")

            logging.debug(f"Authenticated as {role} ID {admin_id}")
        except Exception as e:
            logging.error(f"Token verification failed: {str(e)}")
            return redirect(url_for('login.testinglogin'))

        return f(*args, **kwargs)
    return decorated_function

# Function to generate PDF (you'll need to implement it or use a library like ReportLab)
def generate_pdf(dataframe, title):
    pdf_output = io.BytesIO()
    c = canvas.Canvas(pdf_output, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, height - 50, title)
    y = height - 80

    # For each payroll record, print field:value pairs in a card-like block
    for idx, row in dataframe.iterrows():
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, f"Record {idx + 1}")
        y -= 18
        c.setFont("Helvetica", 10)
        for col, val in zip(dataframe.columns, row):
            # Wrap long values
            text = f"{col}: {val}"
            max_width = width - 80
            if c.stringWidth(text, "Helvetica", 10) < max_width:
                c.drawString(60, y, text)
                y -= 15
            else:
                # Wrap text if it's too long for one line
                from reportlab.platypus import Paragraph
                from reportlab.lib.styles import getSampleStyleSheet
                style = getSampleStyleSheet()['Normal']
                paragraph = Paragraph(text, style)
                paragraph_width, paragraph_height = paragraph.wrap(max_width, y)
                paragraph.drawOn(c, 60, y - paragraph_height + 10)
                y -= paragraph_height

        # Space between records
        y -= 10
        # New page if needed
        if y < 80:
            c.showPage()
            y = height - 50

    c.save()
    pdf_output.seek(0)
    return send_file(
        pdf_output,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"{title.lower()}_export.pdf"
    )

#function to check for document access
def employee_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('user_token')
        if not token:
            logging.warning("No token found in cookies.")
            return jsonify({'success': False, 'message': 'Unauthorized: Token missing'}), 401

        logging.debug(f"Token received: {token}")

        user_id, role = verify_employee_token(token)
        
        if not user_id:
            logging.warning(f"Invalid or expired token. User ID: None, Role: None")
            return jsonify({'success': False, 'message': 'Unauthorized: Invalid or expired token'}), 401

        if role != "Employee":
            logging.warning(f"Unauthorized role access. User ID: {user_id}, Role: {role}")
            return jsonify({'success': False, 'message': 'Unauthorized: Invalid employee role'}), 401

        # Attach user details to the request context for downstream usage
        request.employee_id = user_id
        request.employee_role = role

        # ALSO set on Flask's g context for use in routes
        g.employee_id = user_id
        g.employee_role = role

        # Now fetch role_id from DB and set g.role_id
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT role_id FROM roles WHERE role_name = %s", (role,))
            row = cur.fetchone()
            if row:
                g.role_id = row[0]
            else:
                g.role_id = None
        finally:
            cur.close()
            conn.close()

        return f(*args, **kwargs)
    return decorated_function



