# Community Hospital Privacy Dashboard

A GDPR-compliant mini hospital management dashboard built for **Information Security (CS-3002) — Assignment 4**. It implements the **CIA Triad** (Confidentiality, Integrity, Availability) and core GDPR privacy principles using Python, Streamlit, SQLite, and Fernet encryption.

## How to Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

The SQLite database (`hospital.db`) and Fernet encryption key (`secret.key`) are created automatically on the first run with the demo accounts and sample patient records.

## Demo Accounts

| Role | Username | Password | Access Level |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `admin123` | Full access to raw & anonymized data, Fernet anonymize/decrypt, GDPR retention & erasure, Integrity Audit Log, CSV backups |
| **Doctor** | `Dr. Bob` | `doc123` | Read-only access to anonymized patient identities (`ANON_XXXX`, `XXX-XXX-4567`) and diagnoses |
| **Receptionist** | `Alice_recep` | `rec123` | Register patients (with mandatory consent) and perform blind edits; sensitive fields & diagnoses remain hidden (`***`) |

## Key Features Implemented

### Confidentiality (Privacy & Access Control)
- **Authentication & Salted Hashing:** Passwords are stored using salted PBKDF2-HMAC-SHA256 (`100,000` iterations) and verified with constant-time comparison (`hmac.compare_digest`).
- **Role-Based Access Control (RBAC):** Enforced both in the UI and inside backend database functions (`auth.py` and `database.py`).
- **Data Masking:** Names become deterministic `ANON_XXXX` IDs (SHA-256), contacts become `XXX-XXX-4567`, and diagnoses are masked as `***` for Receptionist access.
- **Reversible Fernet Encryption:** Clicking **Anonymize & Encrypt Data** replaces raw `name` and `contact` values in SQLite with masked values while storing Fernet ciphertexts (`encrypted_name`, `encrypted_contact`). Clicking **Decrypt & Restore Data** runs `Fernet.decrypt()` using `secret.key` to recover raw values for Admin.

### Integrity (Accountability & Validation)
- **Immutable Integrity Audit Log:** Every login, failed login, logout, view, add, update, anonymization, decryption, erasure, and CSV export is timestamped in `logs`.
- **Database-Level Constraints:** SQLite `CHECK` constraints validate non-empty fields, valid roles, and contact length; `FOREIGN KEY` links logs to users; and SQLite triggers (`prevent_log_update`, `prevent_log_delete`) block any modification or deletion of audit logs.
- **Input & Duplicate Validation:** Prevents empty fields, invalid phone numbers, future dates, and duplicate patient entries (even while in anonymized mode).

### Availability (Reliability & Recovery)
- **Exception Handling:** All login, query, encryption, and export operations are wrapped in `try/except` with proper `finally: conn.close()` cleanup to prevent SQLite lockups.
- **CSV Backup Export:** Admin can download CSV snapshots of patient records (raw or anonymized) and audit logs at any time.
- **System Status Footer:** Displays live server uptime, last DB synchronization time, and SQLite health status.

### GDPR Compliance (Bonus Features)
- **User Consent Banner:** Staff must acknowledge the GDPR data-processing notice before logging in, and new patient records require explicit patient consent (stored with timestamp).
- **Data Retention Timer:** Configurable retention window (default `365` days) highlights Active, Expiring Soon, and Expired records, with one-click **Purge Expired PII**.
- **Right to Erasure (Art. 17):** Admin can permanently scrub a patient's personal identifiers and Fernet tokens so they can never be re-identified.
- **Real-Time Activity Graphs:** Admin dashboard visualizes user actions per day and total actions by role.

## Project Structure

- `app.py` — Streamlit dashboard with role-based views and tabs
- `database.py` — SQLite schema, triggers, RBAC-enforced queries, Fernet anonymize/decrypt, GDPR retention & erasure, CSV export
- `auth.py` — Login verification and RBAC permission checks
- `crypto_utils.py` — PBKDF2 password hashing, masking helpers, SHA-256 `ANON_XXXX` generator, and Fernet encryption/decryption
- `Assignment4.ipynb` — Step-by-step walkthrough notebook testing each CIA and GDPR component
- `requirements.txt` — Python dependencies (`streamlit`, `cryptography`, `pandas`)
