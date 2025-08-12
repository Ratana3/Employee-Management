from datetime import datetime, timedelta
import logging
import mimetypes
import os
import bcrypt
from flask import Blueprint, Response, current_app, render_template, jsonify, request, send_file, url_for
import psycopg2
from routes.Auth.audit import log_audit, log_incident
from routes.Auth.token import token_required_with_roles, token_required_with_roles_and_2fa
from routes.Auth.utils import get_db_connection
from . import admin_bp
from extensions import csrf
from PIL import Image
import io
from werkzeug.utils import secure_filename

def is_document_visible_to_role(visibility_role_id, user_role_id, user_role_name):
    """
    Improved visibility logic with proper role hierarchy
    """
    print(f"[DEBUG] Checking visibility: doc_visibility={visibility_role_id}, user_role={user_role_id} ({user_role_name})")

    # Super admin always has access to everything
    if user_role_name.lower() == "super_admin":
        print("[DEBUG] Access granted (super admin override)")
        return True
    
    # Documents with no specific role requirement (None/0) are visible to all
    if visibility_role_id in (None, 0):
        print("[DEBUG] Access granted (public document)")
        return True
    
    # Admin can see most documents except super_admin exclusive ones
    if user_role_name.lower() == "admin":
        # Get super_admin role_id (assuming it's 2 based on your data)
        super_admin_role_id = 2
        if visibility_role_id == super_admin_role_id:
            print("[DEBUG] Access denied (admin cannot see super_admin exclusive docs)")
            return False
        print("[DEBUG] Access granted (admin can see this document)")
        return True
    
    # For other roles, exact match required
    result = visibility_role_id == user_role_id
    print(f"[DEBUG] Access {'granted' if result else 'denied'} (role match: {visibility_role_id} == {user_role_id})")
    return result

def get_relative_file_path(absolute_path):
    """Convert absolute path to relative path for database storage"""
    if not absolute_path:
        return None
    
    # Extract just the filename for relative storage
    filename = os.path.basename(absolute_path)
    return filename

def get_absolute_file_path(relative_path):
    """Convert relative path to absolute path for file operations"""
    if not relative_path:
        return None
    
    # If already absolute, return as-is
    if os.path.isabs(relative_path):
        return relative_path
    
    # Construct absolute path
    doc_dir = current_app.config.get('DOCUMENT_REPOSITORY', 'static/DocumentRepository')
    return os.path.abspath(os.path.join(doc_dir, relative_path))


#function for tracking role to check for visibility
def get_role_id_by_name(role_name):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT role_id FROM roles WHERE LOWER(role_name) = LOWER(%s)", (role_name,))
        result = cur.fetchone()
        return result[0] if result else None
    finally:
        cur.close()
        conn.close()

@csrf.exempt
@admin_bp.route('/api/documents', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["list_documents"])
def list_documents(admin_id, role, role_id):
    print(f"[DEBUG] list_documents called by admin_id={admin_id}, role={role}, role_id={role_id}")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT d.document_id, d.title, d.description, d.filename, d.file_path,
               d.category_id, d.uploaded_by_role_id, d.upload_date, d.version,
               d.download_count, d.visibility_by_role_id, r.role_name
        FROM documents d
        JOIN roles r ON r.role_id = d.visibility_by_role_id
        ORDER BY d.upload_date DESC
    """)
    documents = cur.fetchall()

    visible_docs = []
    for doc in documents:
        (doc_id, title, desc, filename, path, category_id, uploaded_by,
         upload_date, version, download_count, visibility_by_role_id, role_name) = doc

        # Only super_admin sees all documents. Others only see if visibility matches their role_id.
        if role == "super_admin" or str(visibility_by_role_id) == str(role_id):
            visible_docs.append({
                "document_id": doc_id,
                "title": title,
                "description": desc,
                "filename": filename,
                "file_path": path,
                "category_id": category_id,
                "uploaded_by": uploaded_by,
                "upload_date": upload_date.strftime('%Y-%m-%d %H:%M:%S'),
                "version": version,
                "download_count": download_count,
                "visibility_by_role_id": visibility_by_role_id,
                "role_name": role_name
            })
        else:
            print(f"[DEBUG] Document {doc_id} skipped due to visibility role_id '{visibility_by_role_id}' and current role '{role}', role_id '{role_id}'")

    print(f"[DEBUG] Documents returned to client: {len(visible_docs)}")
    cur.close()
    conn.close()

    # Audit: log document listing
    log_audit(admin_id, role, "list_documents", f"Listed {len(visible_docs)} visible documents")
    return jsonify(visible_docs)

@csrf.exempt
@admin_bp.route('/api/categories', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["create_category"])
def create_category(admin_id, role, role_id):
    data = request.get_json()
    name = data.get('name')

    if not name:
        return jsonify({"error": "Category name is required"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Check for duplicate category name (case-insensitive)
        cur.execute("SELECT category_id FROM document_categories WHERE LOWER(name) = LOWER(%s)", (name,))
        existing = cur.fetchone()

        if existing:
            return jsonify({"error": "Category name already exists"}), 400

        # Insert new category
        cur.execute("INSERT INTO document_categories (name) VALUES (%s) RETURNING category_id", (name,))
        new_id = cur.fetchone()[0]
        conn.commit()

        # Audit: log category creation
        log_audit(admin_id, role, "create_category", f"Created document category '{name}' (ID: {new_id})")
    except Exception as e:
        conn.rollback()
        # Incident: log error in category creation
        log_incident(admin_id, role, f"Error creating category '{name}': {e}", severity="High")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

    return jsonify({"message": "Category created", "category_id": new_id}), 201

@csrf.exempt
@admin_bp.route('/api/categories/<int:category_id>', methods=['DELETE'])
@token_required_with_roles_and_2fa(required_actions=["delete_category"])
def delete_category(admin_id, role, role_id, category_id):
    import logging
    import traceback
    from datetime import datetime
    
    # 🔍 DEBUG: Function entry logging
    logging.debug(f"\n{'='*80}")
    logging.debug(f"[DELETE_CATEGORY] Function started at {datetime.utcnow().isoformat()}")
    logging.debug(f"[DELETE_CATEGORY] Admin ID: {admin_id}")
    logging.debug(f"[DELETE_CATEGORY] Role: {role}")
    logging.debug(f"[DELETE_CATEGORY] Role ID: {role_id}")
    logging.debug(f"[DELETE_CATEGORY] Category ID to delete: {category_id}")
    logging.debug(f"[DELETE_CATEGORY] Request method: {request.method}")
    logging.debug(f"[DELETE_CATEGORY] Request headers: {dict(request.headers)}")
    logging.debug(f"{'='*80}")
    
    # 🔍 DEBUG: Validate input parameters
    if not category_id or category_id <= 0:
        logging.error(f"[DELETE_CATEGORY] Invalid category_id provided: {category_id}")
        return jsonify({"error": "Invalid category ID"}), 400
    
    conn = None
    cur = None
    
    try:
        # 🔍 DEBUG: Database connection attempt
        logging.debug(f"[DELETE_CATEGORY] Attempting database connection...")
        conn = get_db_connection()
        logging.debug(f"[DELETE_CATEGORY] Database connection successful")
        
        cur = conn.cursor()
        logging.debug(f"[DELETE_CATEGORY] Database cursor created")

        # 🔍 DEBUG: Step 1 - Check category existence
        logging.debug(f"[DELETE_CATEGORY] Step 1: Checking if category {category_id} exists...")
        category_query = "SELECT * FROM document_categories WHERE category_id = %s"
        logging.debug(f"[DELETE_CATEGORY] Executing query: {category_query} with params: ({category_id},)")
        
        cur.execute(category_query, (category_id,))
        category = cur.fetchone()
        
        logging.debug(f"[DELETE_CATEGORY] Category existence check result: {category}")
        
        if not category:
            logging.warning(f"[DELETE_CATEGORY] Category {category_id} not found in database")
            log_incident(admin_id, role, f"Attempted to delete non-existent category ID {category_id}", severity="Low")
            return jsonify({"error": "Category not found"}), 404
        
        logging.info(f"[DELETE_CATEGORY] Category {category_id} found: {category}")

        # 🔍 DEBUG: Step 2 - Check if category is in use
        logging.debug(f"[DELETE_CATEGORY] Step 2: Checking if category {category_id} is in use...")
        usage_query = "SELECT 1 FROM documents WHERE category_id = %s"
        logging.debug(f"[DELETE_CATEGORY] Executing query: {usage_query} with params: ({category_id},)")
        
        cur.execute(usage_query, (category_id,))
        usage_result = cur.fetchone()
        
        logging.debug(f"[DELETE_CATEGORY] Category usage check result: {usage_result}")
        
        if usage_result:
            logging.warning(f"[DELETE_CATEGORY] Category {category_id} is in use by documents, cannot delete")
            
            # 🔍 DEBUG: Get count of documents using this category
            count_query = "SELECT COUNT(*) FROM documents WHERE category_id = %s"
            cur.execute(count_query, (category_id,))
            document_count = cur.fetchone()[0]
            logging.debug(f"[DELETE_CATEGORY] Number of documents using category {category_id}: {document_count}")
            
            return jsonify({
                "error": "Cannot delete: category is in use by documents",
                "documents_count": document_count
            }), 400
        
        logging.info(f"[DELETE_CATEGORY] Category {category_id} is not in use, safe to delete")

        # 🔍 DEBUG: Step 3 - Delete the category
        logging.debug(f"[DELETE_CATEGORY] Step 3: Deleting category {category_id}...")
        delete_query = "DELETE FROM document_categories WHERE category_id = %s"
        logging.debug(f"[DELETE_CATEGORY] Executing delete query: {delete_query} with params: ({category_id},)")
        
        cur.execute(delete_query, (category_id,))
        rows_affected = cur.rowcount
        logging.debug(f"[DELETE_CATEGORY] Rows affected by delete: {rows_affected}")
        
        if rows_affected == 0:
            logging.error(f"[DELETE_CATEGORY] No rows were deleted - possible race condition")
            conn.rollback()
            return jsonify({"error": "Category could not be deleted - possible race condition"}), 409
        
        # 🔍 DEBUG: Commit transaction
        logging.debug(f"[DELETE_CATEGORY] Committing transaction...")
        conn.commit()
        logging.info(f"[DELETE_CATEGORY] Category {category_id} successfully deleted from database")

        # 🔍 DEBUG: Audit logging
        logging.debug(f"[DELETE_CATEGORY] Recording audit log...")
        log_audit(admin_id, role, "delete_category", f"Deleted document category ID {category_id}")
        logging.debug(f"[DELETE_CATEGORY] Audit log recorded successfully")

    except Exception as e:
        # 🔍 DEBUG: Exception handling with detailed logging
        logging.error(f"[DELETE_CATEGORY] Exception occurred: {type(e).__name__}: {str(e)}")
        logging.error(f"[DELETE_CATEGORY] Exception traceback:\n{traceback.format_exc()}")
        
        # 🔍 DEBUG: Database rollback
        if conn:
            try:
                logging.debug(f"[DELETE_CATEGORY] Attempting database rollback...")
                conn.rollback()
                logging.debug(f"[DELETE_CATEGORY] Database rollback successful")
            except Exception as rollback_error:
                logging.error(f"[DELETE_CATEGORY] Rollback failed: {rollback_error}")
        
        # 🔍 DEBUG: Log incident with detailed error info
        error_details = {
            "exception_type": type(e).__name__,
            "exception_message": str(e),
            "category_id": category_id,
            "admin_id": admin_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logging.debug(f"[DELETE_CATEGORY] Recording incident log with details: {error_details}")
        log_incident(admin_id, role, f"Error deleting category ID {category_id}: {e}", severity="High")
        
        return jsonify({
            "error": str(e),
            "debug_info": {
                "category_id": category_id,
                "error_type": type(e).__name__,
                "timestamp": datetime.utcnow().isoformat()
            }
        }), 500
        
    finally:
        # 🔍 DEBUG: Cleanup with detailed logging
        logging.debug(f"[DELETE_CATEGORY] Entering cleanup phase...")
        
        if cur:
            try:
                logging.debug(f"[DELETE_CATEGORY] Closing database cursor...")
                cur.close()
                logging.debug(f"[DELETE_CATEGORY] Database cursor closed successfully")
            except Exception as cursor_error:
                logging.error(f"[DELETE_CATEGORY] Error closing cursor: {cursor_error}")
                
        if conn:
            try:
                logging.debug(f"[DELETE_CATEGORY] Closing database connection...")
                conn.close()
                logging.debug(f"[DELETE_CATEGORY] Database connection closed successfully")
            except Exception as conn_error:
                logging.error(f"[DELETE_CATEGORY] Error closing connection: {conn_error}")
        
        logging.debug(f"[DELETE_CATEGORY] Cleanup completed")
        logging.debug(f"[DELETE_CATEGORY] Function execution completed at {datetime.utcnow().isoformat()}")
        logging.debug(f"{'='*80}\n")

    # 🔍 DEBUG: Success response
    success_response = {"message": "Category deleted successfully."}
    logging.info(f"[DELETE_CATEGORY] Returning success response: {success_response}")
    
    return jsonify(success_response), 200

#function for handlling file too large
@admin_bp.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large. Maximum size is 500MB'}), 413

@csrf.exempt
@admin_bp.route('/api/documents/upload', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["upload_document"])
def upload_document(admin_id, role, role_id):
    """
    Improved upload function with better file handling and validation
    """
    print(f"[DEBUG] Upload request started by admin_id: {admin_id}, role: {role}")
    
    try:
        # Extract form data
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category_id = request.form.get('category_id')
        visibility_by_role_id = request.form.get('visibility_by_role_id')
        file = request.files.get('file')

        # Enhanced validation
        if not title or len(title) > 200:
            return jsonify({'error': 'Title is required and must be less than 200 characters'}), 400
        
        if len(description) > 1000:
            return jsonify({'error': 'Description must be less than 1000 characters'}), 400
            
        if not category_id:
            return jsonify({'error': 'Category is required'}), 400
            
        if not file or file.filename == '':
            return jsonify({'error': 'No file uploaded'}), 400
            
        if not visibility_by_role_id:
            return jsonify({'error': 'Visibility role is required'}), 400

        # File validation
        original_filename = file.filename
        file_extension = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
        
        ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv', 'txt', 'jpg', 'jpeg', 'png', 'gif', 'ppt', 'pptx'}
        if file_extension not in ALLOWED_EXTENSIONS:
            return jsonify({
                'error': f'File type .{file_extension} not allowed. Allowed types: {", ".join(sorted(ALLOWED_EXTENSIONS))}'
            }), 400

        # Check file size
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)

        MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
        if file_size > MAX_FILE_SIZE:
            return jsonify({
                'error': f'File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB. Your file is {file_size // (1024*1024)}MB'
            }), 400

        # Generate secure filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = secure_filename(original_filename.rsplit('.', 1)[0])
        secure_filename_with_timestamp = f"{base_name}_{timestamp}.{file_extension}"

        # Setup file paths
        upload_dir = current_app.config.get('DOCUMENT_REPOSITORY', 'static/DocumentRepository')
        os.makedirs(upload_dir, exist_ok=True)
        
        absolute_file_path = os.path.abspath(os.path.join(upload_dir, secure_filename_with_timestamp))
        relative_file_path = secure_filename_with_timestamp  # Store only filename

        # Save file
        file.save(absolute_file_path)
        print(f"[DEBUG] File saved to: {absolute_file_path}")

        # Database operations
        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # Validate category exists
            cur.execute("SELECT category_id FROM document_categories WHERE category_id = %s", (int(category_id),))
            if not cur.fetchone():
                os.remove(absolute_file_path)  # Clean up uploaded file
                return jsonify({'error': 'Invalid category'}), 400

            # Get uploader role ID
            uploader_role_id = get_role_id_by_name(role)
            if not uploader_role_id:
                os.remove(absolute_file_path)
                return jsonify({'error': 'Invalid uploader role'}), 400

            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(original_filename)
            if not mime_type:
                mime_type = 'application/octet-stream'

            inserted_documents = []

            # Handle "all" visibility
            if visibility_by_role_id == "all":
                cur.execute("SELECT role_id, role_name FROM roles ORDER BY role_id")
                all_roles = cur.fetchall()
                
                if not all_roles:
                    os.remove(absolute_file_path)
                    return jsonify({'error': 'No roles found in system'}), 400

                for role_row in all_roles:
                    target_role_id, role_name = role_row
                    
                    cur.execute("""
                        INSERT INTO documents (
                            title, description, filename, file_path, category_id, 
                            upload_date, version, download_count, visibility_by_role_id, 
                            uploaded_by_role_id, file_size, mime_type
                        ) VALUES (%s, %s, %s, %s, %s, NOW(), 1, 0, %s, %s, %s, %s)
                        RETURNING document_id
                    """, (
                        title, description, secure_filename_with_timestamp, relative_file_path,
                        int(category_id), target_role_id, uploader_role_id, file_size, mime_type
                    ))
                    
                    doc_id = cur.fetchone()[0]
                    
                    # Add to document history
                    cur.execute("""
                        INSERT INTO document_history 
                        (document_id, version, filename, file_path, updated_at, updated_by)
                        VALUES (%s, 1, %s, %s, NOW(), %s)
                    """, (doc_id, secure_filename_with_timestamp, relative_file_path, f"{role}, ID: {admin_id}"))
                    
                    inserted_documents.append({
                        'document_id': doc_id,
                        'role_id': target_role_id,
                        'role_name': role_name
                    })

            else:
                # Single role visibility
                try:
                    target_role_id = int(visibility_by_role_id)
                    
                    # Validate role exists
                    cur.execute("SELECT role_name FROM roles WHERE role_id = %s", (target_role_id,))
                    role_result = cur.fetchone()
                    if not role_result:
                        os.remove(absolute_file_path)
                        return jsonify({'error': 'Invalid visibility role'}), 400
                    
                    role_name = role_result[0]
                    
                    cur.execute("""
                        INSERT INTO documents (
                            title, description, filename, file_path, category_id,
                            upload_date, version, download_count, visibility_by_role_id,
                            uploaded_by_role_id, file_size, mime_type
                        ) VALUES (%s, %s, %s, %s, %s, NOW(), 1, 0, %s, %s, %s, %s)
                        RETURNING document_id
                    """, (
                        title, description, secure_filename_with_timestamp, relative_file_path,
                        int(category_id), target_role_id, uploader_role_id, file_size, mime_type
                    ))
                    
                    doc_id = cur.fetchone()[0]
                    
                    # Add to document history
                    cur.execute("""
                        INSERT INTO document_history 
                        (document_id, version, filename, file_path, updated_at, updated_by)
                        VALUES (%s, 1, %s, %s, NOW(), %s)
                    """, (doc_id, secure_filename_with_timestamp, relative_file_path, f"{role}, ID: {admin_id}"))
                    
                    inserted_documents.append({
                        'document_id': doc_id,
                        'role_id': target_role_id,
                        'role_name': role_name
                    })
                    
                except ValueError:
                    os.remove(absolute_file_path)
                    return jsonify({'error': 'Invalid visibility role ID'}), 400

            conn.commit()

            # Log successful upload
            role_names = [doc['role_name'] for doc in inserted_documents]
            log_audit(
                admin_id, role, "upload_document",
                f"Uploaded document '{title}' for {len(inserted_documents)} role(s): {', '.join(role_names)} | File: {secure_filename_with_timestamp} ({file_size // 1024}KB)"
            )

            return jsonify({
                'success': True,
                'message': f'Document uploaded successfully for {len(inserted_documents)} role(s)',
                'document_ids': [doc['document_id'] for doc in inserted_documents],
                'filename': secure_filename_with_timestamp,
                'file_size': file_size,
                'roles': role_names
            }), 201

        except Exception as db_error:
            conn.rollback()
            # Clean up file if database operation failed
            if os.path.exists(absolute_file_path):
                os.remove(absolute_file_path)
            raise db_error

        finally:
            cur.close()
            conn.close()

    except Exception as e:
        print(f"[ERROR] Upload failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        log_incident(admin_id, role, f"Document upload failed: {str(e)}", severity="High")
        return jsonify({
            'success': False,
            'error': 'Upload failed',
            'message': 'An error occurred while uploading the document.'
        }), 500
    
@csrf.exempt
@admin_bp.route('/api/documents/<int:document_id>', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["download_document"])
def download_document(admin_id, role, role_id, document_id):
    """
    Improved download function with better error handling and logging
    """
    print(f"[DEBUG] Download request for document {document_id} by {role} (ID: {admin_id})")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get document details with enhanced query
        cur.execute("""
            SELECT d.filename, d.file_path, d.visibility_by_role_id, d.title,
                   d.file_size, d.download_count, r.role_name as visibility_role
            FROM documents d
            LEFT JOIN roles r ON d.visibility_by_role_id = r.role_id
            WHERE d.document_id = %s
        """, (document_id,))
        
        doc = cur.fetchone()

        if not doc:
            print(f"[DEBUG] Document {document_id} not found in database")
            log_incident(admin_id, role, f"Document not found: ID {document_id}", severity="Low")
            return jsonify({'error': 'Document not found'}), 404

        filename, file_path, visibility_role_id, title, file_size, download_count, visibility_role = doc
        
        print(f"[DEBUG] Document found: {title} | Visibility: {visibility_role} (ID: {visibility_role_id})")

        # Check permissions
        if not is_document_visible_to_role(visibility_role_id, role_id, role):
            print(f"[DEBUG] Access denied for role {role} to document with visibility {visibility_role}")
            log_incident(
                admin_id, role, 
                f"Unauthorized document access: ID {document_id} requires {visibility_role} role", 
                severity="Medium"
            )
            return jsonify({
                'error': 'Access denied',
                'message': f'This document requires {visibility_role} role access'
            }), 403

        # Get absolute file path
        absolute_path = get_absolute_file_path(file_path)
        print(f"[DEBUG] Checking file at: {absolute_path}")

        # Verify file exists
        if not os.path.exists(absolute_path):
            print(f"[DEBUG] File not found on disk: {absolute_path}")
            log_incident(
                admin_id, role,
                f"File missing for document {document_id}: {absolute_path}",
                severity="High"
            )
            return jsonify({
                'error': 'File not found',
                'message': 'The document file is missing from the server. Please contact IT support.',
                'document_id': document_id
            }), 404

        # Check file permissions
        if not os.access(absolute_path, os.R_OK):
            print(f"[DEBUG] No read permission for file: {absolute_path}")
            log_incident(
                admin_id, role,
                f"File access denied for document {document_id}: {absolute_path}",
                severity="High"
            )
            return jsonify({'error': 'File access denied'}), 403

        # Update download count
        cur.execute("""
            UPDATE documents 
            SET download_count = COALESCE(download_count, 0) + 1 
            WHERE document_id = %s
        """, (document_id,))
        conn.commit()

        # Log successful download
        actual_file_size = os.path.getsize(absolute_path)
        log_audit(
            admin_id, role, "download_document",
            f"Downloaded '{title}' (ID: {document_id}) | File: {filename} ({actual_file_size // 1024}KB) | Downloads: {(download_count or 0) + 1}"
        )

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type:
            mime_type = 'application/octet-stream'

        print(f"[DEBUG] Sending file: {filename} ({mime_type})")

        # Send file
        return send_file(
            absolute_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mime_type
        )

    except Exception as e:
        print(f"[ERROR] Download failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        log_incident(admin_id, role, f"Download error for document {document_id}: {str(e)}", severity="High")
        return jsonify({
            'error': 'Download failed',
            'message': 'An error occurred while downloading the document.'
        }), 500
    
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@csrf.exempt
@admin_bp.route('/api/documents/<int:document_id>/edit', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["edit_document"])
def edit_document(admin_id, role, role_id, document_id):
    from flask import current_app
    import os

    def safe_int(val, fallback):
        try:
            if val is None:
                return fallback
            if isinstance(val, int):
                return val
            val_str = str(val).strip()
            if val_str in ('', 'undefined', 'null', 'None'):
                return fallback
            return int(val_str)
        except Exception:
            return fallback

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT title, description, category_id, uploaded_by_role_id, 
                   visibility_by_role_id, filename, file_path, upload_date,
                   download_count, version
            FROM documents WHERE document_id = %s
        """, (document_id,))
        current_doc = cur.fetchone()
        if not current_doc:
            log_incident(admin_id, role, f"Document not found for edit: ID {document_id}", severity="Low")
            return jsonify({'error': 'Document not found'}), 404

        current_values = {
            'title': current_doc[0],
            'description': current_doc[1],
            'category_id': current_doc[2],
            'uploaded_by_role_id': current_doc[3],
            'visibility_by_role_id': current_doc[4],
            'filename': current_doc[5],
            'file_path': current_doc[6],
            'upload_date': current_doc[7],
            'download_count': current_doc[8],
            'version': current_doc[9]
        }

        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category_id = request.form.get('category_id', '').strip()
        uploaded_by = request.form.get('uploaded_by', '').strip()
        visibility = request.form.get('visibility', '').strip()
        upload_date = request.form.get('upload_date', '').strip()
        download_count = request.form.get('download_count', '').strip()
        version = request.form.get('version', '').strip()

        # DEBUG
        print(f"DEBUG: role={role} | role_id={role_id} | uploaded_by(raw)={uploaded_by}")

        # Always coerce uploaded_by_role_id to int for DB
        uploaded_by_role_id = safe_int(uploaded_by, current_values['uploaded_by_role_id'])

        final_values = {
            'title': title if title else current_values['title'],
            'description': description if description else current_values['description'],
            'category_id': safe_int(category_id, current_values['category_id']),
            'uploaded_by_role_id': uploaded_by_role_id,
            'visibility_by_role_id': safe_int(visibility, current_values['visibility_by_role_id']),
            'upload_date': upload_date if upload_date else current_values['upload_date'],
            'download_count': safe_int(download_count, current_values['download_count']),
            'version': version if version else current_values['version'],
            'filename': current_values['filename'],
            'file_path': current_values['file_path']
        }

        print(f"DEBUG: final_values={final_values}")

        new_file = request.files.get('editNewFile')
        if new_file and new_file.filename:
            from werkzeug.utils import secure_filename
            safe_filename = secure_filename(new_file.filename)
            save_path = os.path.join(current_app.config['DOCUMENT_REPOSITORY'], safe_filename)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            new_file.save(save_path)
            final_values['filename'] = safe_filename
            final_values['file_path'] = save_path

        # Format updated_by as "role, ID: role_id" for history (this is correct)
        updated_by_value = f"{role}, ID: {role_id}"

        cur.execute("""
            INSERT INTO document_history 
                (document_id, version, filename, file_path, updated_at, updated_by)
            VALUES (%s, %s, %s, %s, NOW(), %s)
        """, (
            document_id,
            current_values['version'],
            current_values['filename'],
            current_values['file_path'],
            updated_by_value
        ))

        if visibility == "all":
            cur.execute("SELECT role_id FROM roles")
            all_roles = cur.fetchall()
            if not all_roles:
                return jsonify({'error': 'No roles found'}), 400

            inserted_ids = []
            for (role_row,) in all_roles:
                cur.execute("""
                    INSERT INTO documents (
                        title, description, filename, file_path,
                        category_id, upload_date,
                        version, download_count, visibility_by_role_id, uploaded_by_role_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING document_id
                """, (
                    final_values['title'],
                    final_values['description'],
                    final_values['filename'],
                    final_values['file_path'],
                    final_values['category_id'],
                    final_values['upload_date'],
                    final_values['version'],
                    final_values['download_count'],
                    role_row,
                    final_values['uploaded_by_role_id']
                ))
                new_document_id = cur.fetchone()[0]
                if not new_document_id:
                    cur.execute("SELECT LAST_INSERT_ID()")  # MySQL fallback
                    new_document_id = cur.fetchone()[0]

                inserted_ids.append(new_document_id)

                # Copy ALL document_history for old document_id to the new one
                cur.execute("""
                    INSERT INTO document_history (document_id, version, filename, file_path, updated_at, updated_by)
                    SELECT %s, version, filename, file_path, updated_at, updated_by
                    FROM document_history
                    WHERE document_id = %s
                """, (new_document_id, document_id))

            # Now you can safely delete the old document and its history (the old history is now copied)
            cur.execute("DELETE FROM document_history WHERE document_id = %s", (document_id,))
            cur.execute("DELETE FROM documents WHERE document_id = %s", (document_id,))

            conn.commit()
            log_audit(
                admin_id, role, "edit_document",
                f"Edited document '{final_values['title']}' for ALL roles (new IDs: {inserted_ids}), deleted original ID {document_id} and its history was copied."
            )
            return jsonify({'message': 'Document updated for all roles.'})

        else:
            cur.execute("""
                UPDATE documents SET 
                    title=%s, description=%s, category_id=%s,
                    uploaded_by_role_id=%s, visibility_by_role_id=%s,
                    filename=%s, file_path=%s, upload_date=%s,
                    download_count=%s, version=%s
                WHERE document_id=%s
            """, (
                final_values['title'],
                final_values['description'],
                final_values['category_id'],
                final_values['uploaded_by_role_id'],
                final_values['visibility_by_role_id'],
                final_values['filename'],
                final_values['file_path'],
                final_values['upload_date'],
                final_values['download_count'],
                final_values['version'],
                document_id
            ))

            conn.commit()
            log_audit(admin_id, role, "edit_document", f"Edited document '{final_values['title']}' (ID: {document_id})")
            return jsonify({'message': 'Document updated successfully'})

    except Exception as e:
        conn.rollback()
        print(f"Error updating document: {e}")
        log_incident(admin_id, role, f"Error editing document ID {document_id}: {e}", severity="High")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
        
@csrf.exempt
@admin_bp.route('/api/documents/<int:document_id>/delete', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["delete_document"])
def delete_document(admin_id, role, role_id, document_id):
    """
    Improved delete function with better file cleanup and validation
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get document details before deletion
        cur.execute("""
            SELECT d.filename, d.file_path, d.title, d.download_count,
                   r.role_name as visibility_role
            FROM documents d
            LEFT JOIN roles r ON d.visibility_by_role_id = r.role_id
            WHERE d.document_id = %s
        """, (document_id,))
        
        doc = cur.fetchone()

        if not doc:
            log_incident(admin_id, role, f"Attempted to delete non-existent document ID {document_id}", severity="Low")
            return jsonify({'error': 'Document not found'}), 404

        filename, file_path, title, download_count, visibility_role = doc

        # Check if other documents use the same file
        cur.execute("SELECT COUNT(*) FROM documents WHERE filename = %s", (filename,))
        file_usage_count = cur.fetchone()[0]

        # Delete document history first (foreign key constraint)
        cur.execute("DELETE FROM document_history WHERE document_id = %s", (document_id,))
        history_deleted = cur.rowcount

        # Delete document record
        cur.execute("DELETE FROM documents WHERE document_id = %s", (document_id,))
        doc_deleted = cur.rowcount

        if doc_deleted == 0:
            conn.rollback()
            return jsonify({'error': 'Failed to delete document from database'}), 500

        # Delete physical file only if no other documents use it
        file_delete_status = "not_attempted"
        if file_usage_count <= 1:  # Only this document used the file
            absolute_path = get_absolute_file_path(file_path)
            
            if absolute_path and os.path.exists(absolute_path):
                try:
                    os.remove(absolute_path)
                    file_delete_status = "deleted"
                    print(f"[DEBUG] Deleted file: {absolute_path}")
                except Exception as e:
                    file_delete_status = f"failed: {str(e)}"
                    print(f"[WARNING] Failed to delete file {absolute_path}: {e}")
            else:
                file_delete_status = "file_not_found"
        else:
            file_delete_status = f"shared_by_{file_usage_count}_documents"

        conn.commit()

        # Log successful deletion
        log_audit(
            admin_id, role, "delete_document",
            f"Deleted document '{title}' (ID: {document_id}) | File: {filename} | Downloads: {download_count or 0} | History records: {history_deleted} | File status: {file_delete_status}"
        )

        return jsonify({
            'success': True,
            'message': 'Document deleted successfully',
            'document_id': document_id,
            'title': title,
            'filename': filename,
            'file_delete_status': file_delete_status,
            'history_records_deleted': history_deleted
        }), 200

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Delete failed: {str(e)}")
        
        log_incident(admin_id, role, f"Error deleting document {document_id}: {str(e)}", severity="High")
        return jsonify({
            'error': 'Delete failed',
            'message': 'An error occurred while deleting the document.'
        }), 500
    
    finally:
        cur.close()
        conn.close()
        
@csrf.exempt
@admin_bp.route('/api/documents/<int:document_id>/history', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_document_history"])
def get_document_history(admin_id, role, role_id, document_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch the visibility for the document
    cur.execute("SELECT visibility_by_role_id FROM documents WHERE document_id = %s", (document_id,))
    result = cur.fetchone()

    if not result:
        # Incident: log document not found
        log_incident(admin_id, role, f"Document not found for history: ID {document_id}", severity="Low")
        return jsonify({'error': 'Document not found'}), 404

    visibility = result[0]

    # FIX: Use role_id instead of admin_id for role-based visibility!
    if not is_document_visible_to_role(visibility, role_id, role):
        # Incident: log unauthorized history access
        log_incident(admin_id, role, f"Unauthorized access to document history: ID {document_id}", severity="Medium")
        return jsonify({'error': 'Unauthorized access to document history'}), 403

    # Fetch the document history if the visibility check passes
    cur.execute("""
        SELECT version, filename, file_path, updated_by, updated_at
        FROM document_history
        WHERE document_id = %s
        ORDER BY version DESC
    """, (document_id,))
    
    history = cur.fetchall()
    cur.close()

    # Audit: log document history access
    log_audit(admin_id, role, "get_document_history", f"Viewed history for document ID {document_id}")

    def to_web_path(file_path):
        # Only keep the filename, and serve from /static/DocumentRepository/
        filename = os.path.basename(file_path)
        return f"/static/DocumentRepository/{filename}"

    return jsonify([
        {
            'version': h[0],
            'filename': h[1],
            'file_path': to_web_path(h[2]),
            'updated_by': h[3],
            'updated_at': h[4].strftime('%Y-%m-%d %H:%M:%S')
        }
        for h in history
    ])

@csrf.exempt
@admin_bp.route('/api/document_categories', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["get_document_categories"])
def get_document_categories(admin_id, role, role_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT category_id, name FROM document_categories ORDER BY name")
    categories = cur.fetchall()
    cur.close()
    conn.close()
    # Audit: log category list access
    log_audit(admin_id, role, "get_document_categories", "Viewed document categories")
    return jsonify([
        {'id': cat[0], 'name': cat[1]} for cat in categories
    ])

@admin_bp.route('/securityandcompliance', methods=['GET', 'POST'])
def securityandcompliance():
    # Fetch employees from the database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT employee_id, email FROM employees")
    employees = cursor.fetchall()
    cursor.close()
    conn.close()

    # Debugging: Ensure that employees are being passed correctly
    print(f"DEBUG: Employees data: {employees}")  # This will print the employee data to the console

    return render_template('Admin/securityandcompliance.html', employees=employees)

# Edit Compliance Record
@csrf.exempt
@admin_bp.route('/edit_compliance', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["edit_compliance"])
def edit_compliance(admin_id, role, role_id):
    try:
        data = request.json
        print("Received compliance update request:", data)

        # Validate required fields
        required_fields = ["status", "timestamp", "role_id", "details", "id"]
        for field in required_fields:
            if field not in data or data[field] == "":
                print(f"Warning: Missing or empty field '{field}'")
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Validate compliance_status (Active or Inactive)
        valid_statuses = ["Active", "Inactive"]
        if data["status"] not in valid_statuses:
            print(f"Error: Invalid compliance status '{data['status']}'")
            return jsonify({"error": "Invalid compliance status. Use 'Active' or 'Inactive'"}), 400

        # Ensure ID is an integer
        try:
            audit_id = int(data["id"])
        except ValueError:
            print(f"Error: Invalid ID format '{data['id']}'")
            return jsonify({"error": "Invalid compliance record ID"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        sql_query = """
            UPDATE audit_trail_admin 
            SET compliance_status = %s, timestamp = %s, role_id = %s, details = %s 
            WHERE audit_id = %s
        """
        query_values = (
            data["status"],   # Now storing "Active" or "Inactive" directly
            data["timestamp"],  
            data["role_id"], 
            data["details"], 
            audit_id
        )
        print("Executing SQL Query:", sql_query)
        print("With Values:", query_values)

        cur.execute(sql_query, query_values)
        conn.commit()

        if cur.rowcount == 0:
            print(f"Warning: No record found with audit_id {audit_id}")
            # Incident: log record not found
            log_incident(admin_id, role, f"No compliance record found with audit_id {audit_id}", severity="Low")
            return jsonify({"error": "No compliance record found with given ID"}), 404

        print(f"Compliance record {audit_id} updated successfully")

        # Audit: log compliance edit
        log_audit(admin_id, role, "edit_compliance", f"Edited compliance record ID {audit_id}")

        cur.close()
        conn.close()

        return jsonify({"message": "Compliance record updated successfully"})

    except Exception as e:
        print(f"Error updating compliance record: {e}")
        # Incident: log error in compliance edit
        log_incident(admin_id, role, f"Error updating compliance record: {e}", severity="High")
        return jsonify({"error": "An error occurred while updating the record"}), 500

# Edit Incident Log
@csrf.exempt
@admin_bp.route('/edit_incident', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["edit_incident"])
def edit_incident(admin_id, role, role_id):
    try:
        data = request.json
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE incident_logs 
            SET incident_type = %s, description = %s,  status = %s, severity_level = %s, reported_at = %s 
            WHERE incident_id = %s
        """, (data['type'], data['description'], data['status'], data['severity'], data['reported_at'], data['id']))
        conn.commit()
        if cur.rowcount == 0:
            # Incident: log record not found
            log_incident(admin_id, role, f"No incident record found with incident_id {data['id']}", severity="Low")
            cur.close()
            conn.close()
            return jsonify({"error": "No incident record found with given ID"}), 404

        # Audit: log incident edit
        log_audit(admin_id, role, "edit_incident", f"Edited incident record ID {data['id']}")
        cur.close()
        conn.close()
        return jsonify({"message": "Incident record updated successfully"})
    except Exception as e:
        print(f"Error updating incident record: {e}")
        # Incident: log error in incident edit
        log_incident(admin_id, role, f"Error updating incident record: {e}", severity="High")
        return jsonify({"error": "An error occurred while updating the record"}), 500

# Delete Compliance Record
@csrf.exempt
@admin_bp.route('/delete_compliance/<int:id>', methods=['DELETE'])
@token_required_with_roles_and_2fa(required_actions=["delete_compliance"])
def delete_compliance(admin_id, role, role_id,id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM audit_trail_admin WHERE audit_id = %s", (id,))
    conn.commit()
    deleted = cur.rowcount
    cur.close()
    conn.close()
    if deleted == 0:
        # Incident: log record not found
        log_incident(admin_id, role, f"Attempted to delete non-existent compliance record ID {id}", severity="Low")
        return jsonify({"error": "Compliance record not found"}), 404
    # Audit: log compliance delete
    log_audit(admin_id, role, "delete_compliance", f"Deleted compliance record ID {id}")
    return jsonify({"message": "Compliance record deleted successfully"})

# Delete Incident Log
@csrf.exempt
@admin_bp.route('/delete_incident/<int:id>', methods=['DELETE'])
@token_required_with_roles_and_2fa(required_actions=["delete_incident"])
def delete_incident(admin_id, role, role_id,id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM incident_logs WHERE incident_id = %s", (id,))
    conn.commit()
    deleted = cur.rowcount
    cur.close()
    conn.close()
    if deleted == 0:
        # Incident: log record not found
        log_incident(admin_id, role, f"Attempted to delete non-existent incident record ID {id}", severity="Low")
        return jsonify({"error": "Incident log not found"}), 404
    # Audit: log incident delete
    log_audit(admin_id, role, "delete_incident", f"Deleted incident log ID {id}")
    return jsonify({"message": "Incident log deleted successfully"})

# View Compliance Record
@csrf.exempt
@admin_bp.route('/view_compliance/<int:id>', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["view_compliance"])
def view_compliance(admin_id, role, role_id,id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch the record
    cur.execute("""
                select at.audit_id,r.role_name, at.action, at.details, at.timestamp, at.compliance_status
                from audit_trail_admin at 
                left join roles r ON r.role_id = at.role_id
                WHERE audit_id = %s
                """, 
                (id,))
    record = cur.fetchone()

    # Get column names
    col_names = [desc[0] for desc in cur.description]

    cur.close()
    conn.close()

    # If record not found, return error
    if not record:
        print(f"Error: Compliance record with ID {id} not found")  # Debugging record not found
        # Incident: log record not found
        log_incident(admin_id, role, f"Compliance record with ID {id} not found", severity="Low")
        return jsonify({"error": "Compliance record not found"}), 404

    # Convert tuple to dictionary by zipping column names with record values
    record_dict = dict(zip(col_names, record))

    print(f"Fetched compliance data: {record_dict}")  # Debugging the fetched data

    # Ensure last_reviewed is formatted as YYYY-MM-DD
    if record_dict.get("timestamp"):
        try:
            # Convert datetime object to string in YYYY-MM-DD format
            record_dict["timestamp"] = record_dict["timestamp"].strftime("%Y-%m-%d")
            print(f"Formatted last_reviewed: {record_dict['timestamp']}")  # Debugging formatted date
        except Exception as e:
            print(f"Error formatting timestamp: {e}")  # Debugging formatting error

    # Audit: log compliance view
    log_audit(admin_id, role, "view_compliance", f"Viewed compliance record ID {id}")

    return jsonify(record_dict)

# View Incident Log
@csrf.exempt
@admin_bp.route('/view_incident/<int:id>', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["view_incident"])
def view_incident(admin_id, role, role_id,id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch column names
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'incident_logs'")
    columns = [col[0] for col in cur.fetchall()]

    # Fetch incident record
    cur.execute("SELECT * FROM incident_logs WHERE incident_id = %s", (id,))
    record = cur.fetchone()
    
    cur.close()
    conn.close()

    if record:
        # Convert to dictionary
        record_dict = dict(zip(columns, record))
        # Audit: log incident view
        log_audit(admin_id, role, "view_incident", f"Viewed incident log ID {id}")
        return jsonify(record_dict)
    else:
        # Incident: log not found
        log_incident(admin_id, role, f"Incident record with ID {id} not found", severity="Low")
        return jsonify({"error": "Incident not found"}), 404

#route for displaying compliance in the table
@csrf.exempt
@admin_bp.route('/compliance', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["display_compliance"])
def display_compliance(admin_id, role, role_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT at.audit_id, at.category, at.compliance_status, at.timestamp, at.details, r.role_name 
        FROM audit_trail_admin at
        left join roles r on r.role_id = at.role_id 
    """)
    records = [
        {"id": row[0], "policy": row[1], "status": row[2], "timestamp": row[3], "details": row[4], "role_name": row[5]} for row in cur.fetchall()
    ]
    cur.close()
    conn.close()
    # Audit: log compliance table view
    log_audit(admin_id, role, "display_compliance", "Viewed compliance table")
    return jsonify(records)

#route for displaying the incident logs in the table
@csrf.exempt
@admin_bp.route('/incidents', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["display_incidents"])
def display_incidents(admin_id, role, role_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT incident_id, incident_type, description, severity_level, status, reported_at FROM incident_logs")
    records = [
        {"id": row[0], "type": row[1], "description": row[2], "severity": row[3], "status": row[4], "reported_at": row[5]} for row in cur.fetchall()
    ]
    cur.close()
    conn.close()
    # Audit: log incident table view
    log_audit(admin_id, role, "display_incidents", "Viewed incidents table")
    return jsonify(records)

#route for reporting new incident
@csrf.exempt
@admin_bp.route('/report-incident', methods=['POST'])
@token_required_with_roles_and_2fa(required_actions=["report_incident"])
def report_incident(admin_id, role, role_id):
    try:
        data = request.json
        logging.debug(f"Received data: {data}")

        # Extract required fields
        incident_type = data.get("incident_type")
        description = data.get("description")
        severity_level = data.get("severity_level")
        status = data.get("status")

        # Validate required fields
        if not all([incident_type, description, severity_level, status]):
            logging.error("Missing required fields in request")
            return jsonify({"error": "All fields (incident_type, description, severity_level, status) are required"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        logging.debug(f"Extracted Admin ID: {admin_id}, Role: {role}")

        # Check if admin exists in the correct table
        super_admin_id = None
        normal_admin_id = None

        if role == "super_admin":
            cur.execute("SELECT super_admin_id FROM super_admins WHERE super_admin_id = %s", (admin_id,))
            if cur.fetchone():
                super_admin_id = admin_id  # Store in the correct column
            else:
                logging.error(f"Super Admin ID {admin_id} not found")
                return jsonify({"error": "Super Admin not found"}), 403
        else:  # role == "admin"
            cur.execute("SELECT admin_id FROM admins WHERE admin_id = %s", (admin_id,))
            if cur.fetchone():
                normal_admin_id = admin_id  # Store in the correct column
            else:
                logging.error(f"Admin ID {admin_id} not found")
                return jsonify({"error": "Admin not found"}), 403

        # Insert into the database with the correct admin column
        cur.execute("""
            INSERT INTO incident_logs (admin_id, super_admin_id, incident_type, description, severity_level, status, reported_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW()) RETURNING incident_id
        """, (normal_admin_id, super_admin_id, incident_type, description, severity_level, status))

        new_id = cur.fetchone()[0]
        conn.commit()

        logging.info(f"Incident reported successfully with ID: {new_id}")

        # Audit: log incident report
        log_audit(admin_id, role, "report_incident", f"Reported incident (ID: {new_id}): {incident_type}, severity {severity_level}")

        return jsonify({"message": "Incident reported successfully", "incident_id": new_id})

    except Exception as e:
        logging.error(f"Error reporting incident: {e}", exc_info=True)
        # Incident: log error reporting incident
        log_incident(admin_id, role, f"Error reporting incident: {e}", severity="High")
        return jsonify({"error": "Internal server error"}), 500

    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

# Utility function to generate date filter SQL and parameters
def get_date_filter_sql_and_params(date_filter, timestamp_column="timestamp"):
    today = datetime.utcnow().date()
    if date_filter == "today":
        return f"AND DATE({timestamp_column}) = %s", [today]
    elif date_filter == "yesterday":
        yesterday = today - timedelta(days=1)
        return f"AND DATE({timestamp_column}) = %s", [yesterday]
    elif date_filter == "last_week":
        # Last 7 days, excluding today
        week_start = today - timedelta(days=7)
        return f"AND DATE({timestamp_column}) >= %s AND DATE({timestamp_column}) < %s", [week_start, today]
    elif date_filter == "last_month":
        # Last 30 days, excluding today
        month_start = today - timedelta(days=30)
        return f"AND DATE({timestamp_column}) >= %s AND DATE({timestamp_column}) < %s", [month_start, today]
    return "", []

@csrf.exempt
@admin_bp.route('/search-compliance', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["search_compliance"])
def search_compliance(admin_id, role, role_id):
    query = request.args.get('query', '').lower()
    date_filter = request.args.get('date_filter', '').strip()
    logging.debug(f"🔍 Received search query: {query} | date_filter: {date_filter}")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Base SQL
        sql_query = """
            SELECT at.audit_id, at.category, CAST(at.compliance_status AS TEXT), at.timestamp, r.role_name, at.details 
            FROM audit_trail_admin at
            JOIN roles r ON r.role_id = at.role_id
            WHERE (LOWER(at.category) LIKE %s 
               OR LOWER(CAST(at.compliance_status AS TEXT)) LIKE %s
               OR LOWER(at.timestamp::TEXT) LIKE %s
               OR LOWER(r.role_name) LIKE %s
               OR LOWER(at.details) LIKE %s)
        """
        search_param = f"%{query}%"
        params = [search_param] * 5

        # Date filter logic
        date_sql, date_params = get_date_filter_sql_and_params(date_filter, "at.timestamp")
        if date_sql:
            sql_query += f" {date_sql}"
            params.extend(date_params)

        logging.debug(f"📌 Executing SQL: {sql_query} with params: {params}")

        cur.execute(sql_query, params)
        fetched_data = cur.fetchall()
        logging.debug(f"📊 Fetched {len(fetched_data)} records from database.")

        filtered_records = [
            {
                "id": row[0],
                "policy": row[1], 
                "status": row[2],
                "timestamp": row[3],
                "role_name": row[4],
                "details": row[5]
            } for row in fetched_data
        ]
        logging.debug(f"✅ Returning {len(filtered_records)} filtered records.")

        log_audit(admin_id, role, "search_compliance", f"Searched compliance with query '{query}' and date_filter '{date_filter}'")

        return jsonify(filtered_records)

    except Exception as e:
        logging.error(f"❌ Error in search_compliance: {e}", exc_info=True)
        log_incident(admin_id, role, f"Error in search_compliance: {e}", severity="High")
        return jsonify({"error": "Internal server error"}), 500

    finally:
        cur.close()
        conn.close()
        logging.debug("🔒 Database connection closed.")

@csrf.exempt
@admin_bp.route('/search-incidents', methods=['GET'])
@token_required_with_roles_and_2fa(required_actions=["search_incidents"])
def search_incidents(admin_id, role, role_id):
    query = request.args.get('query', '').lower()
    date_filter = request.args.get('date_filter', '').strip()
    logging.debug(f"🔍 Received incident search query: {query} | date_filter: {date_filter}")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        sql_query = """
            SELECT incident_id, incident_type, description, severity_level, status, reported_at 
            FROM incident_logs 
            WHERE (LOWER(incident_type) LIKE %s 
               OR LOWER(description) LIKE %s
               OR LOWER(severity_level) LIKE %s
               OR LOWER(status) LIKE %s
               OR LOWER(reported_at::TEXT) LIKE %s)
        """
        search_param = f"%{query}%"
        params = [search_param] * 5

        date_sql, date_params = get_date_filter_sql_and_params(date_filter, "reported_at")
        if date_sql:
            sql_query += f" {date_sql}"
            params.extend(date_params)

        logging.debug(f"📌 Executing SQL: {sql_query} with params: {params}")

        cur.execute(sql_query, params)
        fetched_data = cur.fetchall()
        logging.debug(f"📊 Fetched {len(fetched_data)} records from database.")

        filtered_records = [
            {
                "id": row[0],
                "type": row[1],
                "description": row[2],
                "severity": row[3],
                "status": row[4],
                "reported_at": row[5]
            } for row in fetched_data
        ]
        logging.debug(f"✅ Returning {len(filtered_records)} filtered records.")

        log_audit(admin_id, role, "search_incidents", f"Searched incidents with query '{query}' and date_filter '{date_filter}'")

        return jsonify(filtered_records)

    except Exception as e:
        logging.error(f"❌ Error in search_incidents: {e}", exc_info=True)
        log_incident(admin_id, role, f"Error in search_incidents: {e}", severity="High")
        return jsonify({"error": "Internal server error"}), 500

    finally:
        cur.close()
        conn.close()
        logging.debug("🔒 Database connection closed.")