from flask import Flask
from routes.Login import login_bp
from routes.Employee import employee_bp
from routes.Admin import admin_bp
from routes.SystemTesting.Clock_in_and_out_reminders.clock_in_and_out_reminder import test_reminder_bp
from flask_cors import CORS 
from flask_wtf.csrf import CSRFProtect
from extensions import csrf
from dotenv import load_dotenv
import os
from flask_mail import Mail, Message
from routes.SystemTesting.Clock_in_and_out_reminders.config import init_attendance_scheduler

app = Flask(__name__)
app.secret_key = "123456"
app.config['WTF_CSRF_SECRET_KEY'] = 'anothersecretkey'  # Use a different key for CSRF protection
app.config['WTF_CSRF_ENABLED'] = True

init_attendance_scheduler(app)
csrf.init_app(app)
load_dotenv()
print("EMAIL_USER:", os.getenv("EMAIL_USER"))  # Debugging
print("EMAIL_PASSWORD:", os.getenv("EMAIL_PASSWORD"))  # Debugging (DO NOT DO IN PRODUCTION)

app.config['DOCUMENT_REPOSITORY'] = os.path.join(app.root_path, 'static', 'DocumentRepository')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv("EMAIL_USER")
app.config['MAIL_PASSWORD'] = os.getenv("EMAIL_PASSWORD")  # Can be app password or normal password
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("EMAIL_USER")

mail = Mail(app)
# Register blueprints
app.register_blueprint(login_bp, url_prefix='/')
app.register_blueprint(employee_bp, url_prefix='/')
app.register_blueprint(admin_bp, url_prefix='/')
app.register_blueprint(test_reminder_bp, url_prefix='/')

if __name__ == '__main__':
    app.run(debug=False)
