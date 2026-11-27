import csv
import hashlib
import io
import sqlite3
from datetime import datetime
from pathlib import Path

from crypto_utils import encrypt_text, make_anon_name, mask_contact

DB_PATH = Path(__file__).parent / "hospital.db"


def hash_password(password):
    # Store a hash, never the plain password.
    return hashlib.sha256(password.encode()).hexdigest()


def get_connection():
    return sqlite3.connect(DB_PATH)


def _add_encrypted_columns(cur):
    # Extra columns for encrypted names and contacts. They are added
    # only if they are not there yet, so old databases still work.
    for column in ("encrypted_name TEXT", "encrypted_contact TEXT"):
        try:
            cur.execute(f"ALTER TABLE patients ADD COLUMN {column}")
        except sqlite3.OperationalError:
            pass


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'doctor', 'receptionist'))
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS patients (
            patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT NOT NULL,
            diagnosis TEXT NOT NULL,
            anonymized_name TEXT,
            anonymized_contact TEXT,
            date_added TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            action TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            details TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )

    _add_encrypted_columns(cur)

    # Add the demo users only the first time, so running this again
    # does not make copies.
    if cur.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        users = [
            ("admin", "admin123", "admin"),
            ("Dr. Bob", "doc123", "doctor"),
            ("Alice_recep", "rec123", "receptionist"),
        ]
        for username, password, role in users:
            cur.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, hash_password(password), role),
            )

    seeded = False
    if cur.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0:
        seeded = True
        patients = [
            ("Ahmed Khan", "0300-1234567", "Flu", "2026-11-20"),
            ("Sara Ahmed", "0321-7654321", "Diabetes", "2026-11-21"),
            ("Bilal Hussain", "0333-4567890", "Fracture", "2026-11-22"),
            ("Ayesha Malik", "0345-9876543", "Asthma", "2026-11-23"),
            ("Usman Ali", "0301-2345678", "Fever", "2026-11-24"),
            ("Fatima Noor", "0322-3456789", "Migraine", "2026-11-25"),
        ]
        for name, contact, diagnosis, date_added in patients:
            cur.execute(
                "INSERT INTO patients (name, contact, diagnosis, date_added)"
                " VALUES (?, ?, ?, ?)",
                (name, contact, diagnosis, date_added),
            )

    conn.commit()
    if seeded:
        # The sample patients are anonymized from the start, so the
        # Doctor sees ANON ids even before anyone presses the button.
        anonymize_all()
    conn.close()


def get_setting(key, default=""):
    conn = get_connection()
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ).fetchone()
    conn.close()
    return row[0] if row else default


def set_setting(key, value):
    conn = get_connection()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def is_anonymized():
    # True when the Admin pressed Anonymize Data and has not
    # pressed Decrypt Data since. Kept in the database, so it
    # stays on for every login, not just this browser.
    return get_setting("anonymized", "0") == "1"


def set_anonymized(on):
    set_setting("anonymized", "1" if on else "0")


def get_all_patients():
    conn = get_connection()
    rows = conn.execute(
        "SELECT patient_id, name, contact, diagnosis,"
        " anonymized_name, anonymized_contact, date_added"
        " FROM patients ORDER BY patient_id"
    ).fetchall()
    conn.close()
    return rows


def add_patient(name, contact, diagnosis, date_added):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO patients (name, contact, diagnosis, date_added)"
        " VALUES (?, ?, ?, ?)",
        (name, contact, diagnosis, date_added),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    # A new patient is anonymized straight away, so no one
    # ever sees a blank ANON id for them.
    anonymize_patient(new_id)
    return new_id


def patient_exists(name, contact, exclude_id=None):
    # Same name and contact as a patient who is already there.
    digits = "".join(ch for ch in contact if ch.isdigit())
    conn = get_connection()
    rows = conn.execute(
        "SELECT patient_id, name, contact FROM patients"
    ).fetchall()
    conn.close()
    for pid, pname, pcontact in rows:
        if exclude_id is not None and pid == exclude_id:
            continue
        p_digits = "".join(ch for ch in pcontact if ch.isdigit())
        if pname.strip().lower() == name.strip().lower() and p_digits == digits:
            return True
    return False


def update_patient(patient_id, name, contact, diagnosis):
    conn = get_connection()
    conn.execute(
        "UPDATE patients SET name = ?, contact = ?, diagnosis = ?"
        " WHERE patient_id = ?",
        (name, contact, diagnosis, patient_id),
    )
    conn.commit()
    conn.close()


def anonymize_patient(patient_id):
    # Fills in the anonymized name and contact for one patient,
    # and keeps the real values encrypted so Admin can read them back.
    conn = get_connection()
    _add_encrypted_columns(conn.cursor())
    row = conn.execute(
        "SELECT name, contact FROM patients WHERE patient_id = ?",
        (patient_id,),
    ).fetchone()
    if row is None:
        conn.close()
        return
    name, contact = row
    conn.execute(
        "UPDATE patients SET anonymized_name = ?, anonymized_contact = ?,"
        " encrypted_name = ?, encrypted_contact = ? WHERE patient_id = ?",
        (
            make_anon_name(name, patient_id),
            mask_contact(contact),
            encrypt_text(name),
            encrypt_text(contact),
            patient_id,
        ),
    )
    conn.commit()
    conn.close()


def anonymize_all():
    # Fills in the anonymized name and contact for every patient,
    # and keeps the real values encrypted so Admin can read them back.
    conn = get_connection()
    rows = conn.execute("SELECT patient_id FROM patients").fetchall()
    conn.close()
    for (patient_id,) in rows:
        anonymize_patient(patient_id)
    return len(rows)


def get_encrypted_sample():
    conn = get_connection()
    row = conn.execute(
        "SELECT name, encrypted_name FROM patients"
        " WHERE encrypted_name IS NOT NULL ORDER BY patient_id LIMIT 1"
    ).fetchone()
    conn.close()
    return row


def log_action(user_id, role, action, details):
    # Every important action is written here, with who did it and when.
    conn = get_connection()
    conn.execute(
        "INSERT INTO logs (user_id, role, action, timestamp, details)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, role, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), details),
    )
    conn.commit()
    conn.close()


def get_all_logs():
    conn = get_connection()
    rows = conn.execute(
        "SELECT log_id, user_id, role, action, timestamp, details"
        " FROM logs ORDER BY log_id DESC"
    ).fetchall()
    conn.close()
    return rows


def export_patients_csv(anonymized=False):
    # CSV backup of the patients table, for the Admin to download.
    # When the data is anonymized, the backup has the ANON ids
    # instead of the real names, like the screen does.
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["patient_id", "name", "contact", "diagnosis",
         "anonymized_name", "anonymized_contact", "date_added"]
    )
    for row in get_all_patients():
        if anonymized:
            row = (
                row[0],
                row[4] or "***",
                row[5] or "XXX-XXX-",
                row[3],
                row[4],
                row[5],
                row[6],
            )
        writer.writerow(row)
    return out.getvalue()


def export_logs_csv():
    # CSV backup of the audit logs.
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["log_id", "user_id", "role", "action", "timestamp", "details"])
    for row in get_all_logs():
        writer.writerow(row)
    return out.getvalue()


def get_actions_per_day():
    # How many actions happened on each day, for the activity graph.
    conn = get_connection()
    rows = conn.execute(
        "SELECT date(timestamp), action, COUNT(*)"
        " FROM logs GROUP BY date(timestamp), action"
        " ORDER BY date(timestamp)"
    ).fetchall()
    conn.close()
    return rows


if __name__ == "__main__":
    init_db()
    print("Database ready.")
