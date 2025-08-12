from flask import Blueprint

login_bp = Blueprint('login_bp', __name__, template_folder='../templates/Login')
# Your secret key for signing the JWT token
SECRET_KEY = '123456'
# Import all route modules so routes are registered!
from . import two_authentication,audit,config,decorator,device_tracking,permissions,token,utils
