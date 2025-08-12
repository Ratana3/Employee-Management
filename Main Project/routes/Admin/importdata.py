import io
import csv
import logging
import bcrypt
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from flask import render_template, request, jsonify
from routes.Auth.config import get_db_connection
from extensions import csrf
from routes.Auth.token import token_required_with_roles_and_2fa
from . import admin_bp
from routes.Auth.data_imports import ImportFactory, handle_import

# Usage in your routes:

# route for rendering employee management page
@admin_bp.route('/dataimportandexport', methods=['GET'])
def dataimportandexport_page():
    # Just serve the HTML shell; no data fetching here
    return render_template('Admin/DataImportAndExport.html')

# Updated route
@csrf.exempt
@admin_bp.route('/import/<entity_type>', methods=['POST'])
def import_any_entity(entity_type):
    """Single route for all imports"""
    
    # Check if entity is supported
    if not ImportFactory.is_supported(entity_type):
        return jsonify({
            "error": f"Entity type '{entity_type}' not supported",
            "supported": list(ImportFactory.get_supported_entities())
        }), 400
    
    # Get required permissions
    required_permissions = ImportFactory.get_required_permissions(entity_type)
    
    # Apply decorator dynamically
    @token_required_with_roles_and_2fa(required_actions=required_permissions)
    def do_import(admin_id, role, role_id):
        result, status_code = handle_import(entity_type, request.files.get('file'))
        return jsonify(result), status_code
    
    return do_import()