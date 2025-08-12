import os
import psycopg2
from werkzeug.utils import secure_filename


# ======================== Setup the database first ========================

# Get database connection
def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    return psycopg2.connect(
        host='localhost',
        database='YourDatabaseName', # Change this to your database name
        user='YourUsername', # Change this to your server username
        password='123', # Change this to your database password
    )


# Get the role name string from a role_id
def get_role_name(role_id):
    """Fetch the role name from the database based on role ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role_name FROM roles WHERE role_id = %s", (role_id,))
    role_name = cursor.fetchone()
    cursor.close()
    conn.close()
    return role_name[0] if role_name else None

# Save an uploaded file securely to the given folder if extension allowed
def safe_save_file(file, upload_folder, allowed_extensions={'pdf', 'docx'}):
    """Securely save an uploaded file and return its path."""
    filename = secure_filename(file.filename)
    if not ('.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        raise ValueError("Invalid file type")
    
    os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)
    return filepath

# Delete a file if it exists
def safe_delete_file(filepath):
    """Delete a file if it exists."""
    if os.path.exists(filepath):
        os.remove(filepath)
