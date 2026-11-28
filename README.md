# Community Hospital Dashboard

A small hospital management system for IS Assignment 4. It keeps patient
data private using the CIA triad and GDPR ideas: login with roles, masked
patient data, and a log of who did what.

## How to run

```
pip install -r requirements.txt
streamlit run app.py
```

The app opens in the browser. The database file is made on the first run.

## Login

These are the demo accounts from the assignment:

- Admin — `admin` / `admin123`
- Doctor — `Dr. Bob` / `doc123`
- Receptionist — `Alice_recep` / `rec123`

Admin sees full data, Doctor sees anonymized data only, Receptionist
adds and edits records but cannot see sensitive data. The receptionist
picks a patient by their anonymized ID and the masked contact. Her
edit form starts empty: she types the new name or contact, and a field
left blank stays as it is, so she never sees the stored name or
contact. The diagnosis stays locked for her.

Admin can press Anonymize Data to hide names and contacts in every
view, and Decrypt Data to see the real data again. Anonymize replaces
the real name and contact in the database with masked values, and the
real values only live in the encrypted columns. A new patient is
anonymized as soon as they are added, so no one ever sees a blank
ANON id for them.

Passwords are stored as salted hashes, never as plain text. Every
login, view, add, update, anonymize, decrypt, erase and export is
written to the audit log, and log entries cannot be changed or deleted
once written. The admin can erase a patient for good, and records
older than the retention limit (365 days to start with) can be erased
too.

Patients must agree before their record is saved, and records older
than 365 days are flagged for review. A future date is not accepted,
and the same patient cannot be added twice. The add form clears after
every save, so no patient data stays on the screen.

The dashboard shows totals for patients, encrypted records, old
records and audit entries, and the demo accounts are listed under the
login box.

## Files

- `app.py` — the dashboard
- `database.py` — tables and sample data
- `auth.py` — login and roles
- `crypto_utils.py` — masking and Fernet encryption
- `Assignment4.ipynb` — the same steps as the app, in a notebook

The encryption key is made on the first run and saved as `secret.key`.
It is not pushed to the repo. If you copy `hospital.db` to another
computer, copy `secret.key` too. Without the key the encrypted names
cannot be read back, and pressing Anonymize Data again will not fix
that — it will stop with an error instead of overwriting anything.
