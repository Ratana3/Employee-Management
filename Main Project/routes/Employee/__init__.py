from flask import Blueprint

employee_bp = Blueprint('employee_bp', __name__, url_prefix='/')

# Import routes so they're registered with this blueprint
from . import administrativetools,dashboard,feedbackandsupport,financialmanagement,goals,messasge,notifications,payroll,profile,traininganddevelopment,workandproductivity