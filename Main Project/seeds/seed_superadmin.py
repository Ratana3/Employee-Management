import psycopg2
import bcrypt
import uuid
from datetime import datetime

# Get database connection
def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    return psycopg2.connect(
        host='localhost',
        database='postgres',
        user='postgres',
        password='123',
    )

def seed_superadmin():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Guide : You can edit the details below for your account (Recommendation : just change the email and password since you can update your profile details inside the dashboard)

    email = "superadmin1@gmail.com"
    password = "123"  # Change this!
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    first_name = "super"
    last_name = "admin"
    profile_image = None  # Use None or adjust for binary data
    created_at = datetime.now()
    last_login = None
    status = "Active"
    last_modified = created_at
    role_id = 2
    jti = str(uuid.uuid4())
    phone_number = "12345"
    bio = "Super admin"
    gender = "M"
    date_of_birth = "2025-05-05"  # YYYY-MM-DD format

    # Check if super admin already exists
    cursor.execute("SELECT * FROM super_admins WHERE email = %s", (email,))
    if cursor.fetchone():
        print("Super admin already exists.")
    else:
        cursor.execute("""
            INSERT INTO super_admins (
                email, password_hash, first_name, last_name, profile_image,
                created_at, last_login, status, last_modified, role_id, jti,
                phone_number, bio, gender, date_of_birth
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
        """, (
            email, password_hash, first_name, last_name, profile_image,
            created_at, last_login, status, last_modified, role_id, jti,
            phone_number, bio, gender, date_of_birth
        ))
        conn.commit()
        print("Super admin seeded successfully.")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    seed_superadmin()