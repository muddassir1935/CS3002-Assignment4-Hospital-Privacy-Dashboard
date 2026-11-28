from datetime import date, datetime

import pandas as pd
import streamlit as st

from auth import PERMISSIONS, can_do, check_login
from crypto_utils import mask_diagnosis
from database import (
    add_patient,
    anonymize_all,
    decrypt_all,
    erase_patient_pii,
    export_logs_csv,
    export_patients_csv,
    get_actions_by_role,
    get_actions_per_day,
    get_all_logs,
    get_encrypted_sample,
    get_patients_for_role,
    get_retention_days,
    init_db,
    is_anonymized,
    log_action,
    purge_expired_patients,
    set_retention_days,
    update_patient,
)

st.set_page_config(
    page_title="Community Hospital Privacy Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .top-bar {
        background: linear-gradient(135deg, #0f766e, #0d9488);
        padding: 18px 24px;
        border-radius: 10px;
        margin-bottom: 14px;
    }
    .top-bar h1 { color: white; font-size: 26px; margin: 0; }
    .top-bar p { color: #d7f0ec; margin: 4px 0 0 0; font-size: 14px; }
    .top-bar .top-meta { color: #a7e8e0; font-size: 12px; margin-top: 8px; }
    .pill {
        display: inline-block;
        background: #f59e0b;
        color: #1f2937;
        font-size: 12px;
        font-weight: 600;
        padding: 2px 10px;
        border-radius: 16px;
        margin-left: 10px;
        vertical-align: middle;
    }
    .pill-green {
        background: #d1fae5;
        color: #065f46;
    }
    .role-note {
        background: rgba(15, 118, 110, 0.10);
        border-left: 4px solid #0f766e;
        color: inherit;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 14px;
        font-size: 14px;
    }
    .footer {
        color: #6b7280;
        font-size: 12.5px;
        border-top: 1px solid #e5e7eb;
        padding-top: 10px;
        margin-top: 24px;
    }
    div.stButton > button {
        border-radius: 7px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_server_start_time():
    # Cached once per Streamlit server process so uptime reflects actual server uptime.
    return datetime.now()


@st.cache_resource
def setup_database():
    init_db()
    return True


db_healthy = True
try:
    setup_database()
except Exception:
    db_healthy = False
    st.error("Database initialization failed. Please check hospital.db permissions and reload.")
    st.stop()

# Session defaults
defaults = {
    "logged_in": False,
    "username": "",
    "role": "",
    "user_id": None,
    "view_logged": False,
    "notice": "",
    "last_sync": "",
    "consent_accepted": False,
    "clear_add": False,
    "clear_edit": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

try:
    anonymized = is_anonymized()
    retention_days = get_retention_days()
except Exception:
    db_healthy = False
    anonymized = False
    retention_days = 365


def logout_user():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.user_id = None
    st.session_state.view_logged = False


def valid_contact(contact):
    digits = "".join(ch for ch in (contact or "") if ch.isdigit())
    return len(digits) >= 7


def format_uptime(start_dt):
    elapsed = int((datetime.now() - start_dt).total_seconds())
    hours, rem = divmod(elapsed, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def show_footer():
    server_start = get_server_start_time()
    uptime_str = format_uptime(server_start)
    last_sync = st.session_state.last_sync or "Not synced yet"
    status_text = "Connected (SQLite)" if db_healthy else "Disconnected"
    st.markdown(
        f'<div class="footer">'
        f"<strong>Community Hospital</strong> — GDPR-Compliant Mini Management System (CS-3002 Assignment 4)<br>"
        f"Server Uptime: {uptime_str} (started {server_start.strftime('%H:%M:%S')}) &nbsp;|&nbsp; "
        f"Last Sync: {last_sync} &nbsp;|&nbsp; DB Status: {status_text}"
        f"</div>",
        unsafe_allow_html=True,
    )


# Top header bar
badge = ""
if st.session_state.logged_in:
    if anonymized:
        badge = '<span class="pill">Anonymized Mode (Fernet Encrypted)</span>'
    else:
        badge = '<span class="pill pill-green">Standard Mode</span>'

st.markdown(
    f'<div class="top-bar">'
    f"<h1>Community Hospital Privacy Dashboard{badge}</h1>"
    f"<p>Patient record management implementing the CIA Triad &amp; GDPR privacy principles</p>"
    f'<p class="top-meta">Confidentiality (RBAC + Fernet + Masking) · Integrity (Immutable Audit Logs) · Availability (Error Handling &amp; CSV Backups)</p>'
    f"</div>",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# LOGIN SCREEN + GDPR CONSENT BANNER
# ---------------------------------------------------------------------------
if not st.session_state.logged_in:
    if not st.session_state.consent_accepted:
        st.info(
            "**GDPR Privacy & Data Processing Notice**\n\n"
            "This system processes patient records solely for healthcare treatment under the principles of "
            "**lawful, fair, and transparent processing**, **data minimization**, and **storage limitation** "
            f"(default retention: {retention_days} days). All user actions are recorded in an immutable audit log "
            "for accountability. By continuing, you agree to handle patient data in accordance with hospital privacy policy."
        )
        if st.button("Accept Privacy Notice & Continue", type="primary"):
            st.session_state.consent_accepted = True
            st.rerun()
    else:
        st.success("GDPR Privacy Notice acknowledged for this session.")

    left, middle, right = st.columns([1, 2, 1])
    with middle:
        st.subheader("Staff Login")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button(
                "Login",
                type="primary",
                disabled=not st.session_state.consent_accepted,
            )

        if not st.session_state.consent_accepted:
            st.caption("Please accept the GDPR Privacy Notice above before signing in.")

        if submitted:
            clean_user = username.strip()
            if not clean_user or not password:
                st.error("Please enter both username and password.")
            else:
                try:
                    user = check_login(clean_user, password)
                except Exception:
                    st.error("Database error while verifying credentials. Please try again.")
                else:
                    if user is None:
                        try:
                            log_action(None, "unknown", "login", f"Failed login attempt for '{clean_user}'")
                        except Exception:
                            pass
                        st.error("Invalid username or password.")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.username = user["username"]
                        st.session_state.role = user["role"]
                        st.session_state.user_id = user["user_id"]
                        st.session_state.view_logged = False
                        try:
                            log_action(
                                user["user_id"],
                                user["role"],
                                "login",
                                f"{user['username']} logged in",
                            )
                        except Exception:
                            pass
                        st.rerun()

        st.caption(
            "Demo accounts — **Admin:** `admin` / `admin123` · "
            "**Doctor:** `Dr. Bob` / `doc123` · "
            "**Receptionist:** `Alice_recep` / `rec123`"
        )

    show_footer()
    st.stop()


# ---------------------------------------------------------------------------
# AUTHENTICATED SIDEBAR
# ---------------------------------------------------------------------------
role = st.session_state.role
username = st.session_state.username
user_id = st.session_state.user_id

with st.sidebar:
    st.subheader("Session Info")
    st.write(f"**User:** {username}")
    st.write(f"**Role:** `{role.capitalize()}`")
    st.write(f"**Privacy Mode:** {'Anonymized' if anonymized else 'Standard'}")
    st.write(f"**Retention Policy:** {retention_days} days")

    st.divider()
    st.markdown("**Active RBAC Permissions**")
    for perm in sorted(PERMISSIONS.get(role, set())):
        st.caption(f"- {perm.replace('_', ' ')}")

    st.divider()
    if st.button("Logout", width="stretch"):
        try:
            log_action(user_id, role, "logout", f"{username} logged out")
        except Exception:
            pass
        logout_user()
        st.rerun()


# Role banner & one-time success notifications
role_descriptions = {
    "admin": "Full access to raw and anonymized patient records, Fernet encryption/decryption, GDPR retention controls, Integrity Audit Log, and CSV backups.",
    "doctor": "Read-only access to anonymized patient identities (ANON IDs and masked contacts) alongside clinical diagnoses.",
    "receptionist": "Can register new patients and perform blind updates on contact/name fields. Sensitive patient records and diagnoses remain hidden.",
}
st.markdown(f'<div class="role-note">{role_descriptions[role]}</div>', unsafe_allow_html=True)

if st.session_state.notice:
    st.success(st.session_state.notice)
    st.session_state.notice = ""

# Clear add-patient inputs before widgets render
if st.session_state.clear_add:
    st.session_state.add_name = ""
    st.session_state.add_contact = ""
    st.session_state.add_diagnosis = ""
    st.session_state.add_date = date.today()
    st.session_state.add_consent = False
    st.session_state.clear_add = False


# Fetch role-filtered patient records once per run
try:
    patients = get_patients_for_role(role)
    st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not st.session_state.view_logged:
        try:
            log_action(user_id, role, "view", f"Viewed patient records ({role} scope)")
        except Exception:
            pass
        st.session_state.view_logged = True
except Exception:
    db_healthy = False
    st.error("Unable to load patient records from the database. Please try again.")
    patients = []


# ---------------------------------------------------------------------------
# REUSABLE SECTIONS (ADD PATIENT, EDIT PATIENT)
# ---------------------------------------------------------------------------
def render_add_patient_form():
    st.subheader("Register New Patient")
    st.caption("Patient consent is mandatory before saving personal health data (GDPR Art. 6 & 9).")

    new_name = st.text_input("Full Name", key="add_name", placeholder="e.g. Ali Raza")
    new_contact = st.text_input("Contact Number", key="add_contact", placeholder="e.g. 0300-1234567")
    new_diagnosis = st.text_input("Diagnosis", key="add_diagnosis", placeholder="e.g. Seasonal Flu")
    new_date = st.date_input("Date Added", value=date.today(), key="add_date")
    consent = st.checkbox(
        "Patient has given explicit consent to store and process this record for treatment",
        key="add_consent",
    )

    if st.button("Save Patient", type="primary", key="btn_save_patient"):
        if not new_name.strip() or not new_contact.strip() or not new_diagnosis.strip():
            st.error("Please fill in name, contact, and diagnosis.")
        elif not valid_contact(new_contact):
            st.error("Please enter a valid contact number (at least 7 digits).")
        elif new_date > date.today():
            st.error("Date added cannot be in the future.")
        elif not consent:
            st.error("Patient consent must be confirmed before saving.")
        else:
            try:
                new_id = add_patient(
                    new_name.strip(),
                    new_contact.strip(),
                    new_diagnosis.strip(),
                    str(new_date),
                    consent_given=True,
                    role=role,
                )
                try:
                    log_action(user_id, role, "add", f"Added patient #{new_id} (consent verified)")
                except Exception:
                    pass
                st.session_state.notice = f"Patient #{new_id} added and anonymized automatically."
                st.session_state.clear_add = True
                st.rerun()
            except ValueError as err:
                st.error(str(err))
            except PermissionError as err:
                st.error(str(err))
            except Exception:
                st.error("Could not save patient record due to a database error.")


def render_edit_patient_form():
    st.subheader("Edit Patient Record")
    editable = [p for p in patients if not p.get("is_erased")]
    if not editable:
        st.info("No active patient records available to edit.")
        return

    if role == "admin" and anonymized:
        st.info("Data is currently in Anonymized Mode. Decrypt data first in 'Privacy & GDPR' to edit raw records as Admin.")
        return

    by_id = {p["patient_id"]: p for p in editable}
    if role == "receptionist":
        fmt = lambda pid: f"#{pid} — {by_id[pid]['anonymized_name']} ({by_id[pid]['anonymized_contact']})"
    else:
        fmt = lambda pid: f"#{pid} — {by_id[pid]['name']} ({by_id[pid]['anonymized_name']})"

    picked = st.selectbox("Select Patient", options=list(by_id.keys()), format_func=fmt, key="edit_patient_select")
    current = by_id[picked]

    if role == "receptionist" and st.session_state.clear_edit:
        st.session_state[f"edit_name_{picked}"] = ""
        st.session_state[f"edit_contact_{picked}"] = ""
        st.session_state.clear_edit = False

    if role == "receptionist":
        st.caption(
            "Blind Edit Mode: stored personal details are never displayed. "
            "Type a new Name or Contact to overwrite it, or leave a field blank to keep the existing value."
        )
        edit_name = st.text_input("New Name (optional)", value="", key=f"edit_name_{picked}")
        edit_contact = st.text_input("New Contact (optional)", value="", key=f"edit_contact_{picked}")
        st.text_input("Diagnosis (Restricted)", value=mask_diagnosis(), disabled=True, key=f"edit_diag_{picked}")
        edit_diag = None
    else:
        edit_name = st.text_input("Name", value=current["name"], key=f"edit_name_{picked}")
        edit_contact = st.text_input("Contact", value=current["contact"], key=f"edit_contact_{picked}")
        edit_diag = st.text_input("Diagnosis", value=current["diagnosis"], key=f"edit_diag_{picked}")

    if st.button("Save Changes", type="primary", key="btn_save_edit"):
        if role == "receptionist" and not edit_name.strip() and not edit_contact.strip():
            st.error("Enter a new name or contact to update.")
        elif role == "admin" and (not edit_name.strip() or not edit_contact.strip() or not edit_diag.strip()):
            st.error("All fields are required.")
        elif edit_contact.strip() and not valid_contact(edit_contact):
            st.error("Please enter a valid contact number (at least 7 digits).")
        else:
            try:
                changed = update_patient(
                    picked,
                    name=edit_name,
                    contact=edit_contact,
                    diagnosis=edit_diag,
                    role=role,
                )
                detail = f"Updated patient #{picked}"
                if changed:
                    detail += f" (fields: {', '.join(changed)})"
                else:
                    detail += " (no field values changed)"
                try:
                    log_action(user_id, role, "update", detail)
                except Exception:
                    pass
                st.session_state.notice = f"Patient #{picked} updated (anonymized and encrypted copies synced)."
                if role == "receptionist":
                    st.session_state.clear_edit = True
                st.rerun()
            except (ValueError, PermissionError) as err:
                st.error(str(err))
            except Exception:
                st.error("Database error while updating patient.")


# ---------------------------------------------------------------------------
# ADMIN DASHBOARD
# ---------------------------------------------------------------------------
if role == "admin":
    expired_records = [p for p in patients if not p["is_erased"] and p["days_old"] > retention_days]
    encrypted_count = sum(1 for p in patients if p["encrypted_preview"] != "-")
    try:
        all_logs = get_all_logs(role=role)
    except Exception:
        all_logs = []

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Patients", len(patients))
    m2.metric("Fernet Encrypted", encrypted_count)
    m3.metric(f"Expired (>{retention_days}d)", len(expired_records))
    m4.metric("Audit Log Entries", len(all_logs))

    tab_records, tab_privacy, tab_manage, tab_logs, tab_activity = st.tabs(
        [
            "Patient Records",
            "Privacy & GDPR",
            "Add / Edit Patient",
            "Integrity Audit Log",
            "Activity & Backup",
        ]
    )

    with tab_records:
        st.subheader("Patient Records (Raw & Anonymized View)")
        search = st.text_input("Filter by Diagnosis or Retention Status", placeholder="e.g. Flu, Expired, Active")

        table_rows = []
        for p in patients:
            if search.strip():
                q = search.strip().lower()
                haystack = f"{p['diagnosis']} {p['retention_status']} {p['anonymized_name']}".lower()
                if q not in haystack:
                    continue
            table_rows.append(
                {
                    "ID": p["patient_id"],
                    "Name": p["name"],
                    "Contact": p["contact"],
                    "Diagnosis": p["diagnosis"],
                    "Anon Name": p["anonymized_name"],
                    "Anon Contact": p["anonymized_contact"],
                    "Fernet Token": p["encrypted_preview"],
                    "Date Added": p["date_added"],
                    "Days Old": p["days_old"],
                    "Retention": p["retention_status"],
                    "Consent": "Yes" if p["consent_given"] else "No",
                }
            )

        st.dataframe(table_rows, width="stretch", hide_index=True)
        if expired_records:
            st.warning(
                f"{len(expired_records)} active record(s) exceed the {retention_days}-day GDPR retention window. "
                "Review them in the 'Privacy & GDPR' tab."
            )

    with tab_privacy:
        st.subheader("Reversible Anonymization (Fernet Encryption)")
        st.write(
            "**Anonymize & Encrypt Data** replaces raw names and contacts in SQLite with `ANON_XXXX` IDs and "
            "masked contacts (`XXX-XXX-4567`) while storing reversible Fernet ciphertexts (`secret.key`). "
            "**Decrypt & Restore Data** runs Fernet decryption to recover raw values for Admin view."
        )

        if anonymized:
            st.warning("Current status: **Anonymized Mode** — raw PII in `patients` table is replaced with masked values.")
        else:
            st.success("Current status: **Decrypted (Standard Mode)** — Admin sees raw + anonymized data; Doctor & Receptionist still see masked data only.")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Anonymize & Encrypt Data", type="primary", width="stretch"):
                try:
                    count = anonymize_all(role=role)
                    try:
                        log_action(user_id, role, "anonymization", f"Anonymized & Fernet-encrypted {count} records")
                    except Exception:
                        pass
                    st.session_state.notice = f"Anonymized and encrypted {count} patient records."
                    st.rerun()
                except Exception as err:
                    st.error(f"Anonymization failed: {err}")
        with c2:
            if st.button("Decrypt & Restore Data", width="stretch"):
                try:
                    count = decrypt_all(role=role)
                    try:
                        log_action(user_id, role, "decryption", f"Decrypted {count} records via Fernet")
                    except Exception:
                        pass
                    st.session_state.notice = f"Decrypted {count} patient records back to raw view."
                    st.rerun()
                except Exception as err:
                    st.error(f"Decryption failed: {err}")

        sample = get_encrypted_sample()
        if sample:
            with st.expander("Inspect Live Fernet Encryption Sample (DB Storage Proof)"):
                spid, sname, sanon, smask, senc = sample
                st.write(f"**Patient #{spid}** — Stored `name` column: `{sname}` | `anonymized_name`: `{sanon}` | `anonymized_contact`: `{smask}`")
                st.code(senc, language="text")

        st.divider()
        st.subheader("GDPR Data Retention Timer & Right to Erasure")

        r1, r2 = st.columns([2, 1])
        with r1:
            new_limit = st.number_input(
                "Retention Window (days)",
                min_value=30,
                max_value=3650,
                value=retention_days,
                step=30,
            )
        with r2:
            st.write("")
            st.write("")
            if st.button("Update Retention Policy"):
                try:
                    set_retention_days(int(new_limit), role=role)
                    log_action(user_id, role, "update", f"Updated GDPR retention window to {int(new_limit)} days")
                    st.session_state.notice = f"Retention policy updated to {int(new_limit)} days."
                    st.rerun()
                except Exception as err:
                    st.error(str(err))

        alert_rows = [
            {
                "ID": p["patient_id"],
                "Anon Name": p["anonymized_name"],
                "Date Added": p["date_added"],
                "Days Old": p["days_old"],
                "Status": p["retention_status"],
            }
            for p in patients
            if not p["is_erased"] and p["days_left"] <= 30
        ]
        if alert_rows:
            st.write("**Records Expired or Expiring Within 30 Days**")
            st.dataframe(alert_rows, width="stretch", hide_index=True)
            confirm_purge = st.checkbox("Confirm permanent PII erasure for all expired records")
            if st.button("Purge Expired PII", disabled=not confirm_purge):
                try:
                    erased_ids = purge_expired_patients(role=role, retention_days=retention_days)
                    if erased_ids:
                        log_action(
                            user_id,
                            role,
                            "erasure",
                            f"Retention purge erased PII for patient IDs: {erased_ids}",
                        )
                        st.session_state.notice = f"Purged PII for {len(erased_ids)} expired record(s)."
                    else:
                        st.session_state.notice = "No expired records needed purging."
                    st.rerun()
                except Exception as err:
                    st.error(str(err))
        else:
            st.info("No active records are expired or expiring within 30 days.")

        st.markdown("**Individual Right to Erasure (GDPR Art. 17)**")
        active_for_erasure = [p for p in patients if not p["is_erased"]]
        if active_for_erasure:
            erase_map = {
                p["patient_id"]: f"#{p['patient_id']} — {p['anonymized_name']} ({p['date_added']})"
                for p in active_for_erasure
            }
            erase_pid = st.selectbox("Select Patient for Permanent PII Erasure", options=list(erase_map.keys()), format_func=lambda pid: erase_map[pid], key="erase_patient_select")
            confirm_single = st.checkbox("I confirm this irreversibly scrubs personal identifiers and Fernet keys for this patient")
            if st.button("Erase Patient PII", disabled=not confirm_single):
                try:
                    if erase_patient_pii(erase_pid, role=role):
                        log_action(user_id, role, "erasure", f"GDPR Art. 17 PII erasure completed for patient #{erase_pid}")
                        st.session_state.notice = f"PII permanently erased for patient #{erase_pid}."
                        st.rerun()
                except Exception as err:
                    st.error(str(err))

    with tab_manage:
        col_add, col_edit = st.columns(2)
        with col_add:
            render_add_patient_form()
        with col_edit:
            render_edit_patient_form()

    with tab_logs:
        st.subheader("Integrity Audit Log")
        st.caption(
            "Admin-only accountability trail. Protected at the SQLite layer by append-only triggers "
            "(`prevent_log_update`, `prevent_log_delete`) so entries cannot be altered or erased."
        )

        f1, f2 = st.columns(2)
        with f1:
            action_options = ["All"] + sorted({row[3] for row in all_logs})
            action_filter = st.selectbox("Filter by Action", action_options, key="log_action_filter")
        with f2:
            role_filter = st.selectbox("Filter by Role", ["All", "admin", "doctor", "receptionist", "unknown"], key="log_role_filter")

        log_rows = []
        for log_id, log_uid, log_role, log_act, log_ts, log_det in all_logs:
            if action_filter != "All" and log_act != action_filter:
                continue
            if role_filter != "All" and log_role != role_filter:
                continue
            log_rows.append(
                {
                    "Log ID": log_id,
                    "User ID": str(log_uid) if log_uid is not None else "-",
                    "Role": log_role,
                    "Action": log_act,
                    "Timestamp": log_ts,
                    "Details": log_det,
                }
            )
        st.write(f"Showing **{len(log_rows)}** of {len(all_logs)} entries")
        st.dataframe(log_rows, width="stretch", hide_index=True)

    with tab_activity:
        st.subheader("Real-Time System Activity")
        try:
            per_day = get_actions_per_day(role=role)
            by_role = get_actions_by_role(role=role)
        except Exception:
            per_day, by_role = [], []

        if per_day:
            df_day = pd.DataFrame(per_day, columns=["Day", "Action", "Count"])
            pivoted = df_day.pivot_table(index="Day", columns="Action", values="Count", fill_value=0)
            st.markdown("**User Actions per Day**")
            st.bar_chart(pivoted)

            df_role = pd.DataFrame(by_role, columns=["Role", "Actions"]).set_index("Role")
            st.markdown("**Total Actions by Role**")
            st.bar_chart(df_role)
        else:
            st.info("No audit activity recorded yet.")

        st.divider()
        st.subheader("Backup & Recovery Export (CSV)")
        st.write("Download CSV snapshots of patient records and the Integrity Audit Log for disaster recovery.")

        export_anon = True if anonymized else st.checkbox(
            "Export anonymized CSV (hide raw names & contacts in backup file)", value=True
        )
        b1, b2 = st.columns(2)
        with b1:
            try:
                patients_csv = export_patients_csv(anonymized=export_anon, role=role)
                if st.download_button(
                    "Download Patients CSV Backup",
                    data=patients_csv,
                    file_name="patients_backup.csv",
                    mime="text/csv",
                    width="stretch",
                ):
                    try:
                        mode_tag = "anonymized" if export_anon else "raw"
                        log_action(user_id, role, "export", f"Exported patients CSV ({mode_tag})")
                    except Exception:
                        pass
            except Exception:
                st.error("Failed to generate patients CSV backup.")
        with b2:
            try:
                logs_csv = export_logs_csv(role=role)
                if st.download_button(
                    "Download Audit Logs CSV Backup",
                    data=logs_csv,
                    file_name="integrity_audit_logs.csv",
                    mime="text/csv",
                    width="stretch",
                ):
                    try:
                        log_action(user_id, role, "export", "Exported Integrity Audit Log CSV")
                    except Exception:
                        pass
            except Exception:
                st.error("Failed to generate audit logs CSV backup.")


# ---------------------------------------------------------------------------
# DOCTOR DASHBOARD
# ---------------------------------------------------------------------------
elif role == "doctor":
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Patients", len(patients))
    m2.metric("Active Records", sum(1 for p in patients if not p["is_erased"]))
    m3.metric(f"Retention Alerts (>{retention_days}d)", sum(1 for p in patients if not p["is_erased"] and p["days_old"] > retention_days))

    st.subheader("Anonymized Patient Records")
    st.caption("Patient names and phone numbers are masked to protect identity while allowing clinical review.")
    diag_query = st.text_input("Search by Diagnosis", placeholder="e.g. Diabetes, Asthma")

    doc_rows = []
    for p in patients:
        if diag_query.strip() and diag_query.strip().lower() not in p["diagnosis"].lower():
            continue
        doc_rows.append(
            {
                "ID": p["patient_id"],
                "Anonymized Name": p["anonymized_name"],
                "Masked Contact": p["anonymized_contact"],
                "Diagnosis": p["diagnosis"],
                "Date Added": p["date_added"],
                "Days Old": p["days_old"],
                "Retention": p["retention_status"],
            }
        )
    st.dataframe(doc_rows, width="stretch", hide_index=True)


# ---------------------------------------------------------------------------
# RECEPTIONIST DASHBOARD
# ---------------------------------------------------------------------------
elif role == "receptionist":
    m1, m2 = st.columns(2)
    m1.metric("Registered Patients", len(patients))
    m2.metric("Active Records", sum(1 for p in patients if not p["is_erased"]))

    tab_dir, tab_add, tab_edit = st.tabs(
        ["Patient Directory (Restricted)", "Add Patient", "Edit Patient (Blind Edit)"]
    )

    with tab_dir:
        st.subheader("Restricted Patient Directory")
        st.caption("Sensitive personal identifiers and clinical diagnoses are masked for Receptionist access.")
        rec_rows = [
            {
                "ID": p["patient_id"],
                "Anonymized Name": p["anonymized_name"],
                "Masked Contact": p["anonymized_contact"],
                "Diagnosis": p["diagnosis"],
                "Date Added": p["date_added"],
            }
            for p in patients
        ]
        st.dataframe(rec_rows, width="stretch", hide_index=True)

    with tab_add:
        render_add_patient_form()

    with tab_edit:
        render_edit_patient_form()

show_footer()
