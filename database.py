import csv
import io
import sqlite3
from datetime import date, datetime
from pathlib import Path

from crypto_utils import (
    encrypt_text,
    hash_password,
    make_anon_name,
    mask_contact,
    mask_diagnosis,
    safe_decrypt,
)

DB_PATH = Path(__file__).parent / "hospital.db"

# Same permissions as auth.py, so the database can check roles itself.
ROLE_PERMISSIONS = {
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
    "doctor": {"view_anon", "view_diagnosis"},
    "receptionist": {"view_restricted", "add", "edit"},
}


def _check_role(role, action):
    if action not in ROLE_PERMISSIONS.get(role, set()):
        raise PermissionError(f"Role '{role}' is not authorized for '{action}'.")


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_extra_columns(cur):
    # Migrate older hospital.db files cleanly if extra columns are missing.
    extra_cols = [
        ("encrypted_name", "TEXT"),
        ("encrypted_contact", "TEXT"),
        ("consent_given", "INTEGER NOT NULL DEFAULT 1"),
        ("consent_date", "TEXT"),
        ("is_erased", "INTEGER NOT NULL DEFAULT 0"),
    ]
    existing = {row[1] for row in cur.execute("PRAGMA table_info(patients)").fetchall()}
    for col_name, col_def in extra_cols:
        if col_name not in existing:
            cur.execute(f"ALTER TABLE patients ADD COLUMN {col_name} {col_def}")


def init_db():
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL CHECK (length(trim(username)) > 0),
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'doctor', 'receptionist'))
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS patients (
                patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                contact TEXT NOT NULL CHECK (length(trim(contact)) >= 7),
                diagnosis TEXT NOT NULL CHECK (length(trim(diagnosis)) > 0),
                anonymized_name TEXT,
                anonymized_contact TEXT,
                date_added TEXT NOT NULL,
                encrypted_name TEXT,
                encrypted_contact TEXT,
                consent_given INTEGER NOT NULL DEFAULT 1 CHECK (consent_given IN (0, 1)),
                consent_date TEXT,
                is_erased INTEGER NOT NULL DEFAULT 0 CHECK (is_erased IN (0, 1))
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT NOT NULL,
                action TEXT NOT NULL CHECK (length(trim(action)) > 0),
                timestamp TEXT NOT NULL,
                details TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
            )
            """
        )

        # Logs cannot be changed or deleted once written.
        cur.execute(
            """
            CREATE TRIGGER IF NOT EXISTS prevent_log_update
            BEFORE UPDATE ON logs
            BEGIN
                SELECT RAISE(ABORT, 'Audit logs are immutable and cannot be updated');
            END;
            """
        )
        cur.execute(
            """
            CREATE TRIGGER IF NOT EXISTS prevent_log_delete
            BEFORE DELETE ON logs
            BEGIN
                SELECT RAISE(ABORT, 'Audit logs are immutable and cannot be deleted');
            END;
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

        _ensure_extra_columns(cur)

        # Default GDPR retention period (365 days) and anonymization mode (off initially).
        cur.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('anonymized', '0')"
        )
        cur.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('retention_days', '365')"
        )

        # Seed assignment demo accounts once.
        if cur.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            demo_users = [
                ("admin", "admin123", "admin"),
                ("Dr. Bob", "doc123", "doctor"),
                ("Alice_recep", "rec123", "receptionist"),
            ]
            for username, password, role in demo_users:
                cur.execute(
                    "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                    (username, hash_password(password), role),
                )

        # Seed sample patients once (including one approaching retention limit and one expired).
        seeded = False
        if cur.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0:
            seeded = True
            sample_patients = [
                ("Ahmed Khan", "0300-1234567", "Flu", "2026-11-20"),
                ("Sara Ahmed", "0321-7654321", "Diabetes", "2026-11-21"),
                ("Bilal Hussain", "0333-4567890", "Fracture", "2026-11-22"),
                ("Ayesha Malik", "0345-9876543", "Asthma", "2026-11-23"),
                ("Usman Ali", "0301-2345678", "Fever", "2026-11-24"),
                ("Fatima Noor", "0322-3456789", "Migraine", "2026-11-25"),
                ("Hassan Raza", "0312-8877665", "Hypertension", "2025-12-15"),
                ("Zainab Tariq", "0331-5544332", "Seasonal Allergy", "2025-06-10"),
            ]
            for name, contact, diagnosis, date_added in sample_patients:
                cur.execute(
                    """
                    INSERT INTO patients (name, contact, diagnosis, date_added, consent_given, consent_date)
                    VALUES (?, ?, ?, ?, 1, ?)
                    """,
                    (name, contact, diagnosis, date_added, date_added),
                )

        conn.commit()
    finally:
        conn.close()

    if seeded:
        # Fill the anonymized and encrypted columns for the sample patients.
        _populate_privacy_fields_for_all()


def _populate_privacy_fields_for_all():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT patient_id, name, contact FROM patients WHERE is_erased = 0"
        ).fetchall()
        for pid, name, contact in rows:
            conn.execute(
                """
                UPDATE patients
                SET anonymized_name = ?, anonymized_contact = ?,
                    encrypted_name = ?, encrypted_contact = ?
                WHERE patient_id = ?
                """,
                (
                    make_anon_name(name, pid),
                    mask_contact(contact),
                    encrypt_text(name),
                    encrypt_text(contact),
                    pid,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def get_setting(key, default=""):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else default
    finally:
        conn.close()


def set_setting(key, value):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, str(value)),
        )
        conn.commit()
    finally:
        conn.close()


def is_anonymized():
    return get_setting("anonymized", "0") == "1"


def get_retention_days():
    try:
        return max(30, int(get_setting("retention_days", "365")))
    except ValueError:
        return 365


def set_retention_days(days, role="admin"):
    _check_role(role, "manage_retention")
    if days < 30 or days > 3650:
        raise ValueError("Retention period must be between 30 and 3650 days.")
    set_setting("retention_days", str(int(days)))


def _real_values(row):
    name, contact, enc_name, enc_contact, is_erased = row
    if is_erased:
        return name, contact
    if enc_name and name.startswith("ANON_"):
        name = safe_decrypt(enc_name, fallback=name)
    if enc_contact and contact.startswith("XXX-XXX-"):
        contact = safe_decrypt(enc_contact, fallback=contact)
    return name, contact


def get_all_patients():
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT patient_id, name, contact, diagnosis,
                   anonymized_name, anonymized_contact, date_added
            FROM patients
            ORDER BY patient_id
            """
        ).fetchall()
    finally:
        conn.close()


def get_patients_for_role(role):
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT patient_id, name, contact, diagnosis,
                   anonymized_name, anonymized_contact, date_added,
                   encrypted_name, encrypted_contact, consent_given, is_erased
            FROM patients
            ORDER BY patient_id
            """
        ).fetchall()
    finally:
        conn.close()

    retention_days = get_retention_days()
    today = date.today()
    result = []

    for row in rows:
        (
            pid,
            name,
            contact,
            diagnosis,
            anon_name,
            anon_contact,
            date_added,
            enc_name,
            _enc_contact,
            consent_given,
            is_erased,
        ) = row

        try:
            days_old = (today - date.fromisoformat(date_added)).days
        except ValueError:
            days_old = 0

        days_left = retention_days - days_old
        if is_erased:
            retention_status = "Erased (GDPR)"
        elif days_left < 0:
            retention_status = f"Expired ({abs(days_left)}d over)"
        elif days_left <= 30:
            retention_status = f"Expiring Soon ({days_left}d left)"
        else:
            retention_status = f"Active ({days_left}d left)"

        if role == "admin":
            result.append(
                {
                    "patient_id": pid,
                    "name": name,
                    "contact": contact,
                    "diagnosis": diagnosis,
                    "anonymized_name": anon_name or "ANON_----",
                    "anonymized_contact": anon_contact or mask_contact(contact),
                    "encrypted_preview": (enc_name[:22] + "...") if enc_name else "-",
                    "date_added": date_added,
                    "days_old": days_old,
                    "days_left": days_left,
                    "retention_status": retention_status,
                    "consent_given": bool(consent_given),
                    "is_erased": bool(is_erased),
                }
            )
        elif role == "doctor":
            # Doctor never receives raw name or raw contact.
            result.append(
                {
                    "patient_id": pid,
                    "anonymized_name": anon_name or "ANON_----",
                    "anonymized_contact": anon_contact or mask_contact(contact),
                    "diagnosis": diagnosis,
                    "date_added": date_added,
                    "days_old": days_old,
                    "retention_status": retention_status,
                    "is_erased": bool(is_erased),
                }
            )
        elif role == "receptionist":
            # Receptionist never receives raw name, raw contact, or diagnosis.
            result.append(
                {
                    "patient_id": pid,
                    "anonymized_name": anon_name or "ANON_----",
                    "anonymized_contact": anon_contact or mask_contact(contact),
                    "diagnosis": mask_diagnosis(),
                    "date_added": date_added,
                    "days_old": days_old,
                    "is_erased": bool(is_erased),
                }
            )
        else:
            raise PermissionError(f"Unknown role '{role}'.")

    return result


def patient_exists(name, contact, exclude_id=None):
    target_name = name.strip().lower()
    target_digits = "".join(ch for ch in contact if ch.isdigit())

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT patient_id, name, contact, encrypted_name, encrypted_contact, is_erased
            FROM patients
            WHERE is_erased = 0
            """
        ).fetchall()
    finally:
        conn.close()

    for pid, pname, pcontact, enc_name, enc_contact, is_erased in rows:
        if exclude_id is not None and pid == exclude_id:
            continue
        real_name, real_contact = _real_values(
            (pname, pcontact, enc_name, enc_contact, is_erased)
        )
        p_digits = "".join(ch for ch in real_contact if ch.isdigit())
        if real_name.strip().lower() == target_name and p_digits == target_digits:
            return True
    return False


def add_patient(name, contact, diagnosis, date_added, consent_given=True, role="admin"):
    _check_role(role, "add")

    clean_name = name.strip()
    clean_contact = contact.strip()
    clean_diagnosis = diagnosis.strip()
    digits = "".join(ch for ch in clean_contact if ch.isdigit())

    if not clean_name or not clean_contact or not clean_diagnosis:
        raise ValueError("Name, contact, and diagnosis are required.")
    if len(digits) < 7:
        raise ValueError("Contact must contain at least 7 digits.")
    if not consent_given:
        raise ValueError("Patient consent is required under GDPR.")
    if patient_exists(clean_name, clean_contact):
        raise ValueError("A patient with this name and contact already exists.")

    anon_mode = is_anonymized()
    consent_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO patients (name, contact, diagnosis, date_added, consent_given, consent_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (clean_name, clean_contact, clean_diagnosis, str(date_added), 1, consent_ts),
        )
        new_id = cur.lastrowid

        anon_name = make_anon_name(clean_name, new_id)
        anon_contact = mask_contact(clean_contact)
        enc_name = encrypt_text(clean_name)
        enc_contact = encrypt_text(clean_contact)

        # If the data is anonymized right now, store the masked values
        # here too. The real ones stay in the encrypted columns.
        stored_name = anon_name if anon_mode else clean_name
        stored_contact = anon_contact if anon_mode else clean_contact

        cur.execute(
            """
            UPDATE patients
            SET name = ?, contact = ?,
                anonymized_name = ?, anonymized_contact = ?,
                encrypted_name = ?, encrypted_contact = ?
            WHERE patient_id = ?
            """,
            (
                stored_name,
                stored_contact,
                anon_name,
                anon_contact,
                enc_name,
                enc_contact,
                new_id,
            ),
        )
        conn.commit()
        return new_id
    finally:
        conn.close()


def update_patient(patient_id, name=None, contact=None, diagnosis=None, role="admin"):
    # A blank name or contact keeps the old value. The receptionist
    # cannot change the diagnosis.
    _check_role(role, "edit")

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT name, contact, diagnosis, encrypted_name, encrypted_contact, is_erased
            FROM patients
            WHERE patient_id = ?
            """,
            (patient_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Patient #{patient_id} not found.")

        old_name, old_contact, old_diag, enc_name, enc_contact, is_erased = row
        if is_erased:
            raise ValueError("Cannot edit a record that has been erased under GDPR.")

        real_old_name, real_old_contact = _real_values(
            (old_name, old_contact, enc_name, enc_contact, is_erased)
        )

        new_name = (name or "").strip() or real_old_name
        new_contact = (contact or "").strip() or real_old_contact
        if role == "receptionist":
            # The receptionist cannot change the diagnosis.
            new_diagnosis = old_diag
        else:
            new_diagnosis = (diagnosis or "").strip() or old_diag

        digits = "".join(ch for ch in new_contact if ch.isdigit())
        if len(digits) < 7:
            raise ValueError("Contact must contain at least 7 digits.")
        if patient_exists(new_name, new_contact, exclude_id=patient_id):
            raise ValueError("A patient with this name and contact already exists.")

        changed_fields = []
        if new_name != real_old_name:
            changed_fields.append("name")
        if new_contact != real_old_contact:
            changed_fields.append("contact")
        if new_diagnosis != old_diag:
            changed_fields.append("diagnosis")

        # Update the anonymized and encrypted columns too.
        anon_name = make_anon_name(new_name, patient_id)
        anon_contact = mask_contact(new_contact)
        new_enc_name = encrypt_text(new_name)
        new_enc_contact = encrypt_text(new_contact)

        anon_mode = is_anonymized()
        stored_name = anon_name if anon_mode else new_name
        stored_contact = anon_contact if anon_mode else new_contact

        conn.execute(
            """
            UPDATE patients
            SET name = ?, contact = ?, diagnosis = ?,
                anonymized_name = ?, anonymized_contact = ?,
                encrypted_name = ?, encrypted_contact = ?
            WHERE patient_id = ?
            """,
            (
                stored_name,
                stored_contact,
                new_diagnosis,
                anon_name,
                anon_contact,
                new_enc_name,
                new_enc_contact,
                patient_id,
            ),
        )
        conn.commit()
        return changed_fields
    finally:
        conn.close()


def anonymize_all(role="admin"):
    # Anonymize swaps the real name and contact for masked values.
    # The real values only live in the Fernet columns, so secret.key
    # has to match hospital.db.
    _check_role(role, "anonymize")

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT patient_id, name, contact, encrypted_name, encrypted_contact, is_erased
            FROM patients
            WHERE is_erased = 0
            """
        ).fetchall()

        for pid, name, contact, enc_name, enc_contact, is_erased in rows:
            # If this row is already anonymized and the key cannot open
            # its token, the real name is gone from here. Stop instead
            # of saving the ANON value as the real name.
            if enc_name and name.startswith("ANON_") and safe_decrypt(enc_name, fallback=None) is None:
                raise ValueError(
                    f"Could not decrypt patient #{pid}. Check that secret.key matches hospital.db."
                )
            if enc_contact and contact.startswith("XXX-XXX-") and safe_decrypt(enc_contact, fallback=None) is None:
                raise ValueError(
                    f"Could not decrypt patient #{pid}. Check that secret.key matches hospital.db."
                )
            real_name, real_contact = _real_values(
                (name, contact, enc_name, enc_contact, is_erased)
            )
            anon_name = make_anon_name(real_name, pid)
            anon_contact = mask_contact(real_contact)
            fresh_enc_name = encrypt_text(real_name)
            fresh_enc_contact = encrypt_text(real_contact)

            conn.execute(
                """
                UPDATE patients
                SET name = ?, contact = ?,
                    anonymized_name = ?, anonymized_contact = ?,
                    encrypted_name = ?, encrypted_contact = ?
                WHERE patient_id = ?
                """,
                (
                    anon_name,
                    anon_contact,
                    anon_name,
                    anon_contact,
                    fresh_enc_name,
                    fresh_enc_contact,
                    pid,
                ),
            )

        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES ('anonymized', '1')
            ON CONFLICT(key) DO UPDATE SET value = '1'
            """
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def decrypt_all(role="admin"):
    # Decrypt brings the real names and contacts back from the Fernet columns.
    _check_role(role, "decrypt")

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT patient_id, name, contact, encrypted_name, encrypted_contact
            FROM patients
            WHERE is_erased = 0
            """
        ).fetchall()

        restored = 0
        for pid, name, contact, enc_name, enc_contact in rows:
            if not enc_name or not enc_contact:
                # A row with no token but an ANON name is stuck: there
                # is nothing to restore, so do not flip the mode flag.
                if name.startswith("ANON_") or contact.startswith("XXX-XXX-"):
                    raise ValueError(
                        f"Could not decrypt patient #{pid}. Check that secret.key matches hospital.db."
                    )
                continue
            plain_name = safe_decrypt(enc_name, fallback="")
            plain_contact = safe_decrypt(enc_contact, fallback="")
            if not plain_name or not plain_contact:
                raise ValueError(
                    f"Could not decrypt patient #{pid}. Check that secret.key matches hospital.db."
                )
            conn.execute(
                "UPDATE patients SET name = ?, contact = ? WHERE patient_id = ?",
                (plain_name, plain_contact, pid),
            )
            restored += 1

        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES ('anonymized', '0')
            ON CONFLICT(key) DO UPDATE SET value = '0'
            """
        )
        conn.commit()
        return restored
    finally:
        conn.close()


def erase_patient_pii(patient_id, role="admin"):
    # Erase a patient for good. The name and contact go, the diagnosis
    # stays for the stats.
    _check_role(role, "delete")

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT is_erased FROM patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Patient #{patient_id} not found.")
        if row[0] == 1:
            return False

        erased_label = f"ERASED_{patient_id}"
        conn.execute(
            """
            UPDATE patients
            SET name = ?, contact = 'XXX-XXX-0000',
                anonymized_name = ?, anonymized_contact = 'XXX-XXX-0000',
                encrypted_name = NULL, encrypted_contact = NULL,
                is_erased = 1
            WHERE patient_id = ?
            """,
            (erased_label, erased_label, patient_id),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def purge_expired_patients(role="admin", retention_days=None):
    # Erase every patient older than the retention limit.
    _check_role(role, "manage_retention")
    limit_days = retention_days if retention_days is not None else get_retention_days()
    today = date.today()

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT patient_id, date_added FROM patients WHERE is_erased = 0"
        ).fetchall()
    finally:
        conn.close()

    erased_ids = []
    for pid, date_added in rows:
        try:
            age = (today - date.fromisoformat(date_added)).days
        except ValueError:
            age = 0
        if age > limit_days:
            if erase_patient_pii(pid, role=role):
                erased_ids.append(pid)
    return erased_ids


def get_encrypted_sample():
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT patient_id, name, anonymized_name, anonymized_contact, encrypted_name
            FROM patients
            WHERE encrypted_name IS NOT NULL AND is_erased = 0
            ORDER BY patient_id
            LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()


def log_action(user_id, role, action, details):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO logs (user_id, role, action, timestamp, details)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                role or "unknown",
                action,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                details,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_logs(role="admin"):
    _check_role(role, "view_logs")
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT log_id, user_id, role, action, timestamp, details
            FROM logs
            ORDER BY log_id DESC
            """
        ).fetchall()
    finally:
        conn.close()


def export_patients_csv(anonymized=None, role="admin"):
    _check_role(role, "export")
    if anonymized is None:
        anonymized = is_anonymized()

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "patient_id",
            "name",
            "contact",
            "diagnosis",
            "anonymized_name",
            "anonymized_contact",
            "date_added",
        ]
    )
    for row in get_all_patients():
        if anonymized:
            row = (
                row[0],
                row[4] or "***",
                row[5] or "XXX-XXX-XXXX",
                row[3],
                row[4],
                row[5],
                row[6],
            )
        writer.writerow(row)
    return out.getvalue()


def export_logs_csv(role="admin"):
    _check_role(role, "export")
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["log_id", "user_id", "role", "action", "timestamp", "details"])
    for row in get_all_logs(role=role):
        writer.writerow(row)
    return out.getvalue()


def get_actions_per_day(role="admin"):
    _check_role(role, "view_logs")
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT date(timestamp) AS day, action, COUNT(*)
            FROM logs
            GROUP BY date(timestamp), action
            ORDER BY day
            """
        ).fetchall()
    finally:
        conn.close()


def get_actions_by_role(role="admin"):
    _check_role(role, "view_logs")
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT role, COUNT(*)
            FROM logs
            GROUP BY role
            ORDER BY COUNT(*) DESC
            """
        ).fetchall()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Database ready.")
