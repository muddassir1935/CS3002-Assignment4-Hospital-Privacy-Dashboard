from database import get_connection, hash_password

# What each role is allowed to do. Every page checks this,
# not just hides its button.
PERMISSIONS = {
    "admin": ["view_raw", "view_anon", "add", "edit", "anonymize", "view_logs", "export"],
    "doctor": ["view_anon"],
    "receptionist": ["add", "edit", "view_anon"],
}


def check_login(username, password):
    # Returns the user (id, name, role) if the password matches, else None.
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT user_id, username, role FROM users WHERE username = ? AND password = ?",
        (username, hash_password(password)),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {"user_id": row[0], "username": row[1], "role": row[2]}


def can_do(role, action):
    return action in PERMISSIONS.get(role, [])
