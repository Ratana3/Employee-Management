"""
Seed script for inserting default roles into the 'roles' table.
- Skips roles that already exist (by role_id or role_name).
- Intended for PostgreSQL databases.
- Run with: python seed_roles.py
"""

import psycopg2

ROLES = [
    (1, 'admin'),
    (2, 'super_admin'),
    (3, 'manager'),
    (4, 'hr'),
    (5, 'Employee')
]

# Get database connection
def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    return psycopg2.connect(
        host='localhost',
        database='YourDatabaseName',
        user='Username',
        password='123',
    )


def seed_roles():
    conn = get_db_connection()
    cur = conn.cursor()
    for role_id, role_name in ROLES:
        cur.execute("""
            SELECT 1 FROM roles WHERE role_id = %s OR role_name = %s
        """, (role_id, role_name))
        exists = cur.fetchone()
        if not exists:
            cur.execute("""
                INSERT INTO roles (role_id, role_name) VALUES (%s, %s)
            """, (role_id, role_name))
            print(f"Inserted role: {role_id} - {role_name}")
        else:
            print(f"Skipped (already exists): {role_id} - {role_name}")
    conn.commit()
    cur.close()
    conn.close()
    print("Role seeding complete.")

if __name__ == '__main__':
    seed_roles()