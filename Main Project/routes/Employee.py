from functools import wraps
import io
from mailbox import Message
import os
import re
import threading
from turtle import pd
import bcrypt
from flask import Blueprint, g, render_template, request, redirect, send_file, url_for, flash, session, jsonify, Response
from routes.Auth.decorator import employee_jwt_required
from routes.Auth.token import verify_employee_token
from routes.Auth.two_authentication import verify_employee_2fa_code
from routes.Auth.utils import get_db_connection
from routes.Auth.device_tracking import detect_device_info
import sqlite3
import psycopg2
from werkzeug.security import check_password_hash,generate_password_hash
import traceback
import pymysql
import jwt
from datetime import datetime, timedelta
import logging
from flask_wtf.csrf import generate_csrf,CSRFProtect
from werkzeug.utils import secure_filename
import logging
from flask import request, jsonify
from datetime import datetime
import requests
from psycopg2.extras import RealDictCursor
from user_agents import parse
from flask import make_response
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from extensions import csrf


















































    

    






















