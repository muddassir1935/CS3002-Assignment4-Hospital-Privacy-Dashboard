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
can change a patient's name and contact, but not the diagnosis.

Admin can press Anonymize Data to hide names and contacts in every
view, and Decrypt Data to see the real data again. A new patient is
anonymized as soon as they are added, so no one ever sees a blank
ANON id for them.

Patients must agree before their record is saved, and records older
than 365 days are flagged for review. A future date is not accepted,
and the same patient cannot be added twice.

## Files

- `app.py` — the dashboard
- `database.py` — tables and sample data
- `auth.py` — login and roles
- `crypto_utils.py` — masking and Fernet encryption
- `Assignment4.ipynb` — the same steps as the app, in a notebook

The encryption key is made on the first run and saved as `secret.key`.
It is not pushed to the repo. If you copy `hospital.db` to another
computer, copy `secret.key` too, or press Anonymize Data again to make
new encrypted values.
