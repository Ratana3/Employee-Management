from datetime import datetime
import logging
import os
import traceback
from flask import current_app, g, jsonify, redirect, render_template, request, send_file, url_for
from extensions import csrf
from routes.Auth.token import employee_jwt_required
from routes.Auth.token import verify_employee_token
from routes.Auth.utils import get_db_connection
from . import employee_bp
from routes.Auth.audit import log_employee_audit,log_employee_incident


#route for administrative tools page
@employee_bp.route('/AdministrativeTools', methods=['GET', 'POST'])
def Administrative_Tools():
    # This just renders the shell/page; no DB queries
    return render_template('Employee/AdministrativeTools.html')

@employee_bp.route("/travel-requests/<int:request_id>", methods=["GET"])
@employee_jwt_required()
@csrf.exempt
def get_travel_request(request_id):
    try:
        employee_id = g.employee_id

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT request_id, destination, purpose, start_date, end_date, estimated_expense, remarks, status
            FROM travel_requests
            WHERE request_id = %s AND employee_id = %s
        """, (request_id, employee_id))

        row = cur.fetchone()

        if row is None:
            # Log incident for unauthorized access attempt
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to access travel request {request_id} that doesn't belong to them or doesn't exist",
                severity="Medium"
            )
            return jsonify({'error': 'Travel request not found'}), 404

        travel_request = {
            'request_id': row[0],
            'destination': row[1],
            'purpose': row[2],
            'start_date': row[3],
            'end_date': row[4],
            'estimated_expense': row[5],
            'remarks': row[6],
            'status': row[7]
        }

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="get_travel_request",
            details=f"Retrieved travel request {request_id} for destination: {row[1]}"
        )

        cur.close()
        conn.close()

        return jsonify(travel_request)

    except Exception as e:
        print("Error fetching travel request:", e)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=g.employee_id if hasattr(g, 'employee_id') else None,
            description=f"System error while fetching travel request {request_id}: {str(e)}",
            severity="High"
        )
        
        return jsonify({'error': 'Failed to fetch travel request'}), 500

@employee_bp.route("/travel-requests/<int:request_id>", methods=["DELETE"])
@employee_jwt_required()
@csrf.exempt
def delete_travel_request(request_id):
    try:
        employee_id = g.employee_id

        conn = get_db_connection()
        cur = conn.cursor()

        # First check if the request exists and get details for logging
        cur.execute("""
            SELECT destination, status
            FROM travel_requests
            WHERE request_id = %s AND employee_id = %s
        """, (request_id, employee_id))
        
        existing_request = cur.fetchone()
        
        if existing_request is None:
            # Log incident for unauthorized deletion attempt
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to delete travel request {request_id} that doesn't belong to them or doesn't exist",
                severity="Medium"
            )
            return jsonify({"error": "Request not found or cannot be deleted."}), 404
        
        # Check if status allows deletion
        if existing_request[1] != 'Pending':
            # Log incident for attempting to delete non-pending request
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to delete travel request {request_id} with status '{existing_request[1]}' (only Pending requests can be deleted)",
                severity="Medium"
            )
            return jsonify({"error": "Request not found or cannot be deleted."}), 404

        # Perform the deletion
        cur.execute("""
            DELETE FROM travel_requests
            WHERE request_id = %s AND employee_id = %s AND status = 'Pending'
        """, (request_id, employee_id))

        conn.commit()

        if cur.rowcount == 0:
            # This shouldn't happen given our checks above, but log it anyway
            log_employee_incident(
                employee_id=employee_id,
                description=f"Unexpected error: Travel request {request_id} deletion failed after validation checks passed",
                severity="High"
            )
            return jsonify({"error": "Request not found or cannot be deleted."}), 404

        # Log successful deletion
        log_employee_audit(
            employee_id=employee_id,
            action="delete_travel_request",
            details=f"Successfully deleted travel request {request_id} for destination: {existing_request[0]}"
        )

        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Travel request deleted successfully"})

    except Exception as e:
        print("Error deleting travel request:", e)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=g.employee_id if hasattr(g, 'employee_id') else None,
            description=f"System error while deleting travel request {request_id}: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": "Failed to delete travel request"}), 500
    
@employee_bp.route("/travel-requests/<int:request_id>", methods=["PUT"])
@employee_jwt_required()
@csrf.exempt
def edit_travel_request(request_id):
    try:
        data = request.get_json()
        destination = data.get("destination")
        purpose = data.get("purpose")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        estimated_expense = data.get("estimated_expense")
        remarks = data.get("remarks")

        employee_id = g.employee_id

        conn = get_db_connection()
        cur = conn.cursor()

        # First check if the request exists and get current details for logging
        cur.execute("""
            SELECT destination, status
            FROM travel_requests
            WHERE request_id = %s AND employee_id = %s
        """, (request_id, employee_id))
        
        existing_request = cur.fetchone()
        
        if existing_request is None:
            # Log incident for unauthorized edit attempt
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to edit travel request {request_id} that doesn't belong to them or doesn't exist",
                severity="Medium"
            )
            return jsonify({"error": "Request not found or cannot be edited."}), 404
        
        # Check if status allows editing
        if existing_request[1] != 'Pending':
            # Log incident for attempting to edit non-pending request
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee attempted to edit travel request {request_id} with status '{existing_request[1]}' (only Pending requests can be edited)",
                severity="Medium"
            )
            return jsonify({"error": "Request not found or cannot be edited."}), 404

        # Perform the update
        cur.execute("""
            UPDATE travel_requests
            SET destination = %s, purpose = %s, start_date = %s, end_date = %s, estimated_expense = %s, remarks = %s, submission_date = NOW()
            WHERE request_id = %s AND employee_id = %s AND status = 'Pending'
        """, (destination, purpose, start_date, end_date, estimated_expense, remarks, request_id, employee_id))

        conn.commit()

        if cur.rowcount == 0:
            # This shouldn't happen given our checks above, but log it anyway
            log_employee_incident(
                employee_id=employee_id,
                description=f"Unexpected error: Travel request {request_id} update failed after validation checks passed",
                severity="High"
            )
            return jsonify({"error": "Request not found or cannot be edited."}), 404

        # Log successful edit
        log_employee_audit(
            employee_id=employee_id,
            action="edit_travel_request",
            details=f"Successfully updated travel request {request_id}: destination changed from '{existing_request[0]}' to '{destination}'"
        )

        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Travel request updated successfully"})

    except Exception as e:
        print("Error editing travel request:", e)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=g.employee_id if hasattr(g, 'employee_id') else None,
            description=f"System error while editing travel request {request_id}: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": "Failed to edit travel request"}), 500

@employee_bp.route("/travel-requests", methods=["GET"])
@employee_jwt_required()
@csrf.exempt
def get_employee_travel_requests():
    try:
        employee_id = g.employee_id
        print(f"[DEBUG] Fetching travel requests for employee_id: {employee_id}")

        conn = get_db_connection()
        cur = conn.cursor()

        query = """
            SELECT request_id, destination, purpose, start_date, end_date, estimated_expense, status, remarks
            FROM travel_requests
            WHERE employee_id = %s
            ORDER BY submission_date DESC;
        """
        print(f"[DEBUG] Executing SQL: {query.strip()} with employee_id: {employee_id}")
        
        cur.execute(query, (employee_id,))
        rows = cur.fetchall()
        print(f"[DEBUG] Number of travel requests fetched: {len(rows)}")

        travel_requests = []
        for row in rows:
            travel_requests.append({
                "request_id": row[0],
                "destination": row[1],
                "purpose": row[2],
                "start_date": row[3].strftime("%Y-%m-%d"),
                "end_date": row[4].strftime("%Y-%m-%d"),
                "estimated_expense": row[5],
                "status": row[6],
                "remarks": row[7],
            })

        # Log successful audit trail
        log_employee_audit(
            employee_id=employee_id,
            action="get_travel_requests",
            details=f"Retrieved {len(rows)} travel requests for employee"
        )

        cur.close()
        conn.close()

        print(f"[DEBUG] Travel requests response: {travel_requests}")
        return jsonify(travel_requests)

    except Exception as e:
        print("[ERROR] Exception occurred while fetching travel requests:")
        traceback.print_exc()
        
        # Log incident for system error
        log_employee_incident(
            employee_id=g.employee_id if hasattr(g, 'employee_id') else None,
            description=f"System error while fetching travel requests: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": "Failed to fetch travel requests"}), 500
    
@employee_bp.route("/travel-requests", methods=["POST"])
@employee_jwt_required()
@csrf.exempt
def submit_travel_request():
    try:
        data = request.get_json()
        destination = data.get("destination")
        purpose = data.get("purpose")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        estimated_expense = data.get("estimated_expense")
        remarks = data.get("remarks")

        employee_id = g.employee_id

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO travel_requests (employee_id, destination, start_date, end_date, purpose, estimated_expense, status, remarks)
            VALUES (%s, %s, %s, %s, %s, %s, 'Pending', %s)
            RETURNING request_id;
        """, (employee_id, destination, start_date, end_date, purpose, estimated_expense, remarks))

        request_id = cur.fetchone()[0]
        conn.commit()

        # Log successful submission
        log_employee_audit(
            employee_id=employee_id,
            action="submit_travel_request",
            details=f"Successfully submitted travel request {request_id} for destination: {destination}, dates: {start_date} to {end_date}, expense: {estimated_expense}"
        )

        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Travel request submitted", "request_id": request_id})

    except Exception as e:
        print("Error submitting travel request:", e)
        
        # Log incident for system error
        log_employee_incident(
            employee_id=g.employee_id if hasattr(g, 'employee_id') else None,
            description=f"System error while submitting travel request: {str(e)}",
            severity="High"
        )
        
        return jsonify({"error": "Failed to submit travel request"}), 500

def is_document_visible_to_employee_role(visibility_role_id, user_role_id, user_role_name):
    """
    Enhanced visibility logic for employee document access
    """
    print(f"[DEBUG] Employee visibility check: doc_visibility={visibility_role_id}, user_role={user_role_id} ({user_role_name})")

    # Super admin employees can see everything
    if user_role_name and user_role_name.lower() == "super_admin":
        print("[DEBUG] Access granted (super admin employee)")
        return True
    
    # Admin employees can see most documents except super_admin exclusive
    if user_role_name and user_role_name.lower() == "admin":
        # Assuming super_admin role_id is 2
        super_admin_role_id = 2
        if visibility_role_id == super_admin_role_id:
            print("[DEBUG] Access denied (admin employee cannot see super_admin docs)")
            return False
        print("[DEBUG] Access granted (admin employee can see this document)")
        return True
    
    # Documents with no specific role requirement (None/0) are visible to all
    if visibility_role_id in (None, 0):
        print("[DEBUG] Access granted (public document)")
        return True
    
    # For other employee roles, exact match required
    result = visibility_role_id == user_role_id
    print(f"[DEBUG] Access {'granted' if result else 'denied'} (role match: {visibility_role_id} == {user_role_id})")
    return result

def get_absolute_file_path_employee(relative_path):
    """Convert relative path to absolute path for employee file operations"""
    if not relative_path:
        return None
    
    # If already absolute, return as-is
    if os.path.isabs(relative_path):
        return relative_path
    
    # Construct absolute path
    doc_dir = current_app.config.get('DOCUMENT_REPOSITORY', 'static/DocumentRepository')
    return os.path.abspath(os.path.join(current_app.root_path, doc_dir, relative_path))

@employee_bp.route("/documents", methods=["GET"])
@employee_jwt_required()
def get_employee_documents():
    """
    Enhanced employee document listing with improved visibility logic
    """
    print(f"📋 Employee documents request from user {g.employee_id} at {datetime.now()}")

    try:
        employee_id = g.employee_id
        employee_role = g.employee_role
        
        conn = get_db_connection()
        cur = conn.cursor()

        # Get employee info for enhanced logging
        cur.execute("SELECT first_name, last_name, email, team_id FROM employees WHERE employee_id = %s", (employee_id,))
        employee_info = cur.fetchone()
        if employee_info:
            employee_name = f"{employee_info[0]} {employee_info[1]}"
            employee_email = employee_info[2]
            employee_team_id = employee_info[3]
        else:
            employee_name = f"Employee {employee_id}"
            employee_email = "unknown@email.com"
            employee_team_id = None

        # Get current user's role_id
        user_role_id = getattr(g, 'role_id', None)
        if not user_role_id:
            cur.execute("SELECT role_id FROM roles WHERE role_name = %s", (employee_role,))
            role_row = cur.fetchone()
            if not role_row:
                log_employee_incident(
                    employee_id=employee_id,
                    description=f"Employee {employee_name} ({employee_email}) role '{employee_role}' not found in roles table during document list fetch",
                    severity="Medium"
                )
                cur.close()
                conn.close()
                return jsonify({"error": "Role not found"}), 403
            user_role_id = role_row[0]

        # Enhanced query to get documents with role information and file status
        query = """
            SELECT d.document_id, d.title, d.description, d.filename, d.file_path,
                   d.category_id, d.upload_date, d.download_count, d.version,
                   d.visibility_by_role_id, d.uploaded_by_role_id,
                   vr.role_name as visibility_role_name,
                   ur.role_name as uploaded_by_role_name,
                   dc.name as category_name
            FROM documents d
            LEFT JOIN roles vr ON d.visibility_by_role_id = vr.role_id
            LEFT JOIN roles ur ON d.uploaded_by_role_id = ur.role_id
            LEFT JOIN document_categories dc ON d.category_id = dc.category_id
            ORDER BY d.upload_date DESC, d.document_id DESC
        """
        
        cur.execute(query)
        all_documents = cur.fetchall()

        # Filter documents based on employee visibility
        visible_documents = []
        file_stats = {"total": 0, "accessible": 0, "missing": 0}

        for doc in all_documents:
            (doc_id, title, description, filename, file_path, category_id, 
             upload_date, download_count, version, visibility_role_id, uploaded_by_role_id,
             visibility_role_name, uploaded_by_role_name, category_name) = doc

            # Check if employee can see this document
            if is_document_visible_to_employee_role(visibility_role_id, user_role_id, employee_role):
                file_stats["total"] += 1
                
                # Check file existence for better user experience
                file_exists = False
                file_size = 0
                if file_path:
                    absolute_path = get_absolute_file_path_employee(file_path)
                    if absolute_path and os.path.exists(absolute_path):
                        try:
                            file_size = os.path.getsize(absolute_path)
                            file_exists = True
                            file_stats["accessible"] += 1
                        except Exception:
                            file_stats["missing"] += 1
                    else:
                        file_stats["missing"] += 1
                else:
                    file_stats["missing"] += 1

                visible_documents.append({
                    "document_id": doc_id,
                    "title": title or "Untitled",
                    "description": description or "",
                    "filename": filename or "",
                    "file_path": file_path or "",
                    "category_id": category_id,
                    "category_name": category_name or "Uncategorized",
                    "upload_date": upload_date.strftime("%Y-%m-%d %H:%M") if upload_date else "Unknown",
                    "upload_date_raw": upload_date.strftime("%Y-%m-%d") if upload_date else "Unknown",
                    "download_count": download_count or 0,
                    "version": version or 1,
                    "visibility_by_role_id": visibility_role_id,
                    "visibility_role_name": visibility_role_name or "Unknown",
                    "uploaded_by_role_id": uploaded_by_role_id,
                    "uploaded_by_role_name": uploaded_by_role_name or "Unknown",
                    "file_exists": file_exists,
                    "file_size": file_size,
                    "file_size_mb": round(file_size / (1024 * 1024), 2) if file_size > 0 else 0
                })

        # Enhanced logging
        log_employee_audit(
            employee_id=employee_id,
            action="get_documents",
            details=f"Employee {employee_name} ({employee_email}, role: {employee_role}) retrieved {len(visible_documents)} documents | Accessible: {file_stats['accessible']} | Missing: {file_stats['missing']} | Total in system: {len(all_documents)}"
        )

        cur.close()
        conn.close()

        print(f"✅ Returning {len(visible_documents)} documents to employee {employee_name}")
        return jsonify({
            "documents": visible_documents,
            "statistics": file_stats,
            "employee_info": {
                "name": employee_name,
                "email": employee_email,
                "role": employee_role,
                "team_id": employee_team_id
            },
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    except Exception as e:
        print(f"❌ Error fetching employee documents: {e}")
        
        log_employee_incident(
            employee_id=g.employee_id if hasattr(g, 'employee_id') else None,
            description=f"System error while fetching employee documents: {str(e)}",
            severity="High"
        )
        
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
            
        return jsonify({
            "error": "Failed to fetch documents",
            "message": "An error occurred while retrieving documents."
        }), 500

@employee_bp.route("/documents/<int:document_id>", methods=["GET"])
@employee_jwt_required()
@csrf.exempt
def download_employee_document(document_id):
    """
    Enhanced employee document download with improved error handling and security
    """
    print(f"📥 Employee download request for document {document_id} at {datetime.now()}")
    
    try:
        employee_id = g.employee_id
        employee_role = g.employee_role
        
        conn = get_db_connection()
        cur = conn.cursor()

        # Get employee info for enhanced logging
        cur.execute("SELECT first_name, last_name, email, team_id FROM employees WHERE employee_id = %s", (employee_id,))
        employee_info = cur.fetchone()
        if employee_info:
            employee_name = f"{employee_info[0]} {employee_info[1]}"
            employee_email = employee_info[2]
            employee_team_id = employee_info[3]
        else:
            employee_name = f"Employee {employee_id}"
            employee_email = "unknown@email.com"
            employee_team_id = None

        # Get current user's role_id
        user_role_id = getattr(g, 'role_id', None)
        if not user_role_id:
            cur.execute("SELECT role_id FROM roles WHERE role_name = %s", (employee_role,))
            role_row = cur.fetchone()
            if not role_row:
                log_employee_incident(
                    employee_id=employee_id,
                    description=f"Employee {employee_name} ({employee_email}) role '{employee_role}' not found in roles table during document download attempt for document {document_id}",
                    severity="Medium"
                )
                cur.close()
                conn.close()
                return jsonify({"error": "Role not found"}), 403
            user_role_id = role_row[0]

        # Enhanced query to get document details with role information
        query = """
            SELECT d.file_path, d.title, d.uploaded_by_role_id, d.upload_date, 
                   d.filename, d.description, d.download_count, d.version,
                   d.category_id, d.visibility_by_role_id,
                   vr.role_name as visibility_role_name,
                   ur.role_name as uploaded_by_role_name,
                   dc.name as category_name
            FROM documents d
            LEFT JOIN roles vr ON d.visibility_by_role_id = vr.role_id
            LEFT JOIN roles ur ON d.uploaded_by_role_id = ur.role_id
            LEFT JOIN document_categories dc ON d.category_id = dc.category_id
            WHERE d.document_id = %s
        """
        cur.execute(query, (document_id,))
        result = cur.fetchone()

        if not result:
            print(f"❌ Document {document_id} not found in database")
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee {employee_name} ({employee_email}) attempted to download non-existent document {document_id}",
                severity="Medium"
            )
            cur.close()
            conn.close()
            return jsonify({"error": "Document not found"}), 404

        # Unpack result with enhanced data
        (file_path, title, uploaded_by_role_id, upload_date, filename, description, 
         download_count, version, category_id, visibility_role_id,
         visibility_role_name, uploaded_by_role_name, category_name) = result

        # Check if employee has permission to access this document
        if not is_document_visible_to_employee_role(visibility_role_id, user_role_id, employee_role):
            log_employee_incident(
                employee_id=employee_id,
                description=f"Employee {employee_name} ({employee_email}, role: {employee_role}) attempted to download document {document_id} ('{title}') requiring role '{visibility_role_name}'",
                severity="High"
            )
            cur.close()
            conn.close()
            return jsonify({
                "error": "Access denied", 
                "message": f"This document requires '{visibility_role_name}' role access"
            }), 403

        # Validate file path
        if not file_path:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Document {document_id} ('{title}') has no file path in database - requested by {employee_name} ({employee_email})",
                severity="High"
            )
            cur.close()
            conn.close()
            return jsonify({"error": "Document file path not found"}), 500

        # Get absolute file path
        full_file_path = get_absolute_file_path_employee(file_path)
        print(f"📂 Checking file path: {full_file_path}")

        # **CRITICAL FILE EXISTENCE CHECK**
        if not os.path.exists(full_file_path):
            print(f"🔍 File not found at: {full_file_path}")
            
            # Try to locate the file in the document repository
            base_filename = os.path.basename(file_path) if file_path else filename
            document_dir = os.path.join(current_app.root_path, 'static', 'DocumentRepository')
            
            print(f"🔍 Searching for: {base_filename} in {document_dir}")
            
            found_file = None
            if base_filename and os.path.exists(document_dir):
                for root, dirs, files in os.walk(document_dir):
                    for file in files:
                        if file == base_filename:
                            found_file = os.path.join(root, file)
                            print(f"✅ Found file at: {found_file}")
                            break
                    if found_file:
                        break

            if found_file and os.path.exists(found_file):
                # Update database with correct path
                relative_path = os.path.relpath(found_file, document_dir)
                cur.execute("""
                    UPDATE documents 
                    SET file_path = %s
                    WHERE document_id = %s
                """, (relative_path, document_id))
                conn.commit()
                
                log_employee_audit(
                    employee_id=employee_id,
                    action="fix_document_path",
                    details=f"Auto-fixed document path for {document_id} ('{title}'): '{file_path}' → '{relative_path}' | Requested by {employee_name} ({employee_email})"
                )
                
                full_file_path = found_file
                print(f"🔧 Path corrected to: {full_file_path}")
            else:
                # File is completely missing
                log_employee_incident(
                    employee_id=employee_id,
                    description=f"Document file permanently missing for document {document_id} ('{title}'): expected at '{full_file_path}', searched in '{document_dir}' | Requested by {employee_name} ({employee_email}) | Original file: {base_filename} | Uploaded by: {uploaded_by_role_name} | Category: {category_name}",
                    severity="High"
                )
                
                cur.close()
                conn.close()
                return jsonify({
                    "error": "Document file not found on server",
                    "message": "The document exists in our records but the file is missing from the server.",
                    "document_title": title,
                    "document_id": document_id,
                    "category": category_name,
                    "support_info": "Please contact IT support to restore this document."
                }), 404

        # Verify file integrity
        try:
            file_stat = os.stat(full_file_path)
            actual_file_size = file_stat.st_size
            
            # Try to read a small portion to verify file integrity
            with open(full_file_path, 'rb') as test_file:
                test_file.read(min(1024, actual_file_size))  # Read first 1KB
                
        except PermissionError:
            log_employee_incident(
                employee_id=employee_id,
                description=f"Permission denied accessing document {document_id} ('{title}') at '{full_file_path}' | Requested by {employee_name} ({employee_email})",
                severity="High"
            )
            cur.close()
            conn.close()
            return jsonify({
                "error": "Document access denied",
                "message": "The document file cannot be accessed due to permission restrictions."
            }), 403
            
        except Exception as file_error:
            log_employee_incident(
                employee_id=employee_id,
                description=f"File corruption or read error for document {document_id} ('{title}') at '{full_file_path}': {str(file_error)} | Requested by {employee_name} ({employee_email})",
                severity="High"
            )
            cur.close()
            conn.close()
            return jsonify({
                "error": "Document file corrupted",
                "message": "The document file appears to be corrupted or unreadable."
            }), 500

        # Prepare download filename
        if filename:
            full_filename = filename
        else:
            # Fallback to creating filename from title
            extension = os.path.splitext(file_path)[1] if file_path else '.pdf'
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_', '.')).strip()
            full_filename = f"{safe_title}{extension}" if safe_title else f"document_{document_id}{extension}"

        # Calculate file size for logging
        file_size_mb = round(actual_file_size / (1024 * 1024), 2)
        
        # Update download statistics
        cur.execute("""
            UPDATE documents 
            SET download_count = COALESCE(download_count, 0) + 1
            WHERE document_id = %s
        """, (document_id,))
        conn.commit()

        # Log successful download
        log_employee_audit(
            employee_id=employee_id,
            action="download_document",
            details=f"Employee {employee_name} ({employee_email}, team: {employee_team_id}) downloaded document {document_id}: '{title}' | File: {filename or os.path.basename(full_file_path)} ({file_size_mb} MB) | Version: {version} | Category: {category_name} | Uploaded by: {uploaded_by_role_name} | Downloads: {download_count + 1}"
        )

        cur.close()
        conn.close()

        print(f"📤 Sending file to employee: {full_file_path} as '{full_filename}'")
        
        # Determine MIME type
        file_extension = os.path.splitext(full_filename)[1].lower()
        mime_types = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.txt': 'text/plain',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.ppt': 'application/vnd.ms-powerpoint',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        }
        
        mimetype = mime_types.get(file_extension, 'application/octet-stream')
        
        # Send file with proper headers
        return send_file(
            full_file_path,
            as_attachment=True,
            download_name=full_filename,
            mimetype=mimetype
        )

    except FileNotFoundError as e:
        print(f"❌ File not found error: {e}")
        
        log_employee_incident(
            employee_id=g.employee_id if hasattr(g, 'employee_id') else None,
            description=f"File not found error while downloading document {document_id}: {str(e)}",
            severity="High"
        )
        
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
            
        return jsonify({
            "error": "Document file not found",
            "message": "The requested document file could not be located on the server.",
            "support_info": f"Please contact IT support with document ID: {document_id}"
        }), 404

    except Exception as e:
        print(f"❌ Error downloading document: {e}")
        
        log_employee_incident(
            employee_id=g.employee_id if hasattr(g, 'employee_id') else None,
            description=f"System error while downloading document {document_id}: {str(e)}",
            severity="High"
        )
        
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
            
        return jsonify({
            "error": "Download failed",
            "message": "An unexpected error occurred while downloading the document.",
            "support_info": f"Error ID: {document_id}"
        }), 500