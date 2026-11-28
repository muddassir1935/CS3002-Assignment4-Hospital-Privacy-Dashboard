from crypto_utils import verify_password
from database import get_connection

# Role-Based Access Control (RBAC) permissions matrix.
# Checked both in the UI and inside backend database functions.
PERMISSIONS = {
    "admin": {
        "view_raw",
        "view_anon",
        "view_diagnosis",
        "add",
        "edit",
        "delete",
        "anonymize",
        "decrypt",
        "view_logs",
        "export",
        "manage_retention",
    },
    "doctor": {
        "view_anon",
        "view_diagnosis",
    },
    "receptionist": {
        "view_restricted",
        "add",
        "edit",
    },
}


def check_login(username, password):
    """Verify credentials and return user dict if valid, else None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT user_id, username, password, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    user_id, uname, stored_hash, role = row
    if not verify_password(password, stored_hash):
        return None
    return {"user_id": user_id, "username": uname, "role": role}


def can_do(role, action):
    return action in PERMISSIONS.get(role, set())


def require_permission(role, action):
    if not can_do(role, action):
        raise PermissionError(f"Role '{role}' is not authorized to perform '{action}'.")
