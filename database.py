import hashlib
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "hospital.db"


def hash_password(password):
    # Store a hash, never the plain password.
    return hashlib.sha256(password.encode()).hexdigest()


def get_connection():
    return sqlite3.connect(DB_PATH)


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


if __name__ == "__main__":
    init_db()
    print("Database ready.")
