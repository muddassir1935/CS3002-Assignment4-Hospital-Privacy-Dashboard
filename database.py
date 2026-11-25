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

    if cur.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0:
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
    conn.close()


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
    return new_id


def update_patient(patient_id, name, contact, diagnosis):
    conn = get_connection()
    conn.execute(
        "UPDATE patients SET name = ?, contact = ?, diagnosis = ?"
        " WHERE patient_id = ?",
        (name, contact, diagnosis, patient_id),
    )
    conn.commit()
    conn.close()


def anonymize_all():
    # Fills in the anonymized name and contact for every patient,
    # and keeps the real values encrypted so Admin can read them back.
    conn = get_connection()
    _add_encrypted_columns(conn.cursor())
    rows = conn.execute(
        "SELECT patient_id, name, contact FROM patients"
    ).fetchall()
    for patient_id, name, contact in rows:
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


def export_patients_csv():
    # CSV backup of the patients table, for the Admin to download.
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["patient_id", "name", "contact", "diagnosis",
         "anonymized_name", "anonymized_contact", "date_added"]
    )
    for row in get_all_patients():
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


if __name__ == "__main__":
    init_db()
    print("Database ready.")
