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
adds and edits records but cannot see sensitive data.

## Files

- `app.py` — the dashboard
- `database.py` — tables and sample data (next step)
- `auth.py` — login and roles (next step)
- `crypto_utils.py` — masking and encryption (next step)
