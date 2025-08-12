from routes.Auth.utils import get_db_connection

# Check if a user/role has the required permission for a document
def check_permission(user_id, role, document_id, required_permission='view'):
    """Check if a user/role has permission to access a document."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT 1 FROM document_access 
        WHERE document_id = %s AND (user_id = %s OR role = %s)
        AND permission_level = %s
    """
    return cursor.execute(
        query, 
        (document_id, user_id, role, required_permission),
        fetch_one=True
    )
