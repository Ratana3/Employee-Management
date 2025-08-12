from flask import Blueprint

admin_bp = Blueprint('admin_bp', __name__, url_prefix='/')

# Import routes so they're registered with this blueprint
from . import attendanceandtimetracking,dashboard,employeeEngagement,employeemanagement,importdata,notificationsandcommunication,payrollandfinancialmanagement
from . import performancemanagement,profile,reportandanalytics,securityandcompliance,systemadministration,traininganddevelopment,verification,workflowmanagement