from datetime import date

import streamlit as st

from auth import can_do, check_login
from crypto_utils import decrypt_text, mask_diagnosis, show_contact, show_name
from database import (
    add_patient,
    anonymize_all,
    get_all_logs,
    get_all_patients,
    get_encrypted_sample,
    init_db,
    log_action,
    update_patient,
)

st.set_page_config(page_title="Community Hospital Dashboard", layout="wide")

st.markdown(
    """
    <style>
    .top-bar { background: #0f766e; padding: 18px 22px; border-radius: 10px; }
    .top-bar h1 { color: white; font-size: 26px; margin: 0; }
    .top-bar p { color: #d7f0ec; margin: 4px 0 0 0; }
    .card { background: #f1f5f4; padding: 16px 18px; border-radius: 10px; }
    .footer { color: grey; font-size: 13px; }
    </style>
    """,
    unsafe_allow_html=True,
)

try:
    init_db()
except Exception:
    st.error("Something went wrong. Please try again.")
    st.stop()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.user_id = None
    st.session_state.view_logged = False


def logout():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.user_id = None
    st.session_state.view_logged = False


def valid_contact(contact):
    digits = "".join(ch for ch in contact if ch.isdigit())
    return len(digits) >= 7


st.markdown(
    '<div class="top-bar"><h1>Community Hospital</h1>'
    "<p>Patient records, with privacy built in</p></div>",
    unsafe_allow_html=True,
)
st.write("")

if not st.session_state.logged_in:
    left, middle, right = st.columns([1, 2, 1])
    with middle:
        st.subheader("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if not username or not password:
                st.error("Please enter username and password.")
            else:
                db_error = False
                try:
                    user = check_login(username.strip(), password)
                except Exception:
                    st.error("Something went wrong. Please try again.")
                    user = None
                    db_error = True
                if user is None:
                    if not db_error:
                        try:
                            log_action(None, "unknown", "login", f"Failed login for {username.strip()}")
                        except Exception:
                            pass
                    st.error("Wrong username or password.")
                else:
                    st.session_state.logged_in = True
                    st.session_state.username = user["username"]
                    st.session_state.role = user["role"]
                    st.session_state.user_id = user["user_id"]
                    st.session_state.view_logged = False
                    try:
                        log_action(user["user_id"], user["role"], "login", f"{user['username']} logged in")
                    except Exception:
                        pass
                    st.rerun()
    st.write("")
    st.markdown(
        '<p class="footer">Community Hospital — GDPR mini system, IS Assignment 4</p>',
        unsafe_allow_html=True,
    )
    st.stop()

role = st.session_state.role
st.write(f"Logged in as **{st.session_state.username}** ({role})")
if st.button("Logout"):
    try:
        log_action(st.session_state.user_id, role, "logout", f"{st.session_state.username} logged out")
    except Exception:
        pass
    logout()
    st.rerun()

if role == "admin":
    what = "You can see full patient data, anonymize it, and check the logs."
elif role == "doctor":
    what = "You can see anonymized patient data only."
else:
    what = "You can add and edit patient records. Sensitive data stays hidden."

st.markdown(f'<div class="card">{what}</div>', unsafe_allow_html=True)
st.write("")

st.subheader("Patients")
try:
    patients = get_all_patients()
    # Log the view once per login. Streamlit runs this page again on
    # every click, so logging it every time would fill the logs.
    if not st.session_state.get("view_logged"):
        try:
            log_action(st.session_state.user_id, role, "view", "Viewed patient list")
        except Exception:
            pass
        st.session_state.view_logged = True
except Exception:
    st.error("Something went wrong. Please try again.")
    patients = []

can_raw = can_do(role, "view_raw")
rows = []
for p in patients:
    pid, name, contact, diagnosis, anon_name, anon_contact, date_added = p
    rows.append(
        {
            "ID": pid,
            "Name": show_name(name, anon_name, can_raw),
            "Contact": show_contact(contact, anon_contact, can_raw),
            "Diagnosis": diagnosis if role != "receptionist" else mask_diagnosis(),
            "Date Added": date_added,
        }
    )
st.write(f"{len(rows)} patients")
st.dataframe(rows, use_container_width=True)
st.write("")

if can_do(role, "anonymize"):
    st.subheader("Anonymize data")
    st.write(
        "This replaces names with ANON ids and masks contacts. "
        "The real names are kept encrypted, so Admin can still read them back."
    )
    if st.button("Anonymize Data"):
        try:
            count = anonymize_all()
            try:
                log_action(st.session_state.user_id, role, "anonymize", f"Anonymized {count} patients")
            except Exception:
                pass
            st.success("Data anonymized.")
            st.rerun()
        except Exception:
            st.error("Something went wrong. Please try again.")
    anon_rows = [
        {"ID": p[0], "Anonymized Name": p[4], "Anonymized Contact": p[5]}
        for p in patients
        if p[4]
    ]
    if anon_rows:
        st.dataframe(anon_rows, use_container_width=True)
        try:
            sample = get_encrypted_sample()
            if sample:
                st.write("Encrypted name (first patient):")
                st.code(sample[1])
                st.write(f"Decrypted back: {decrypt_text(sample[1])}")
        except Exception:
            st.error("Something went wrong. Please try again.")
    st.write("")

if can_do(role, "add"):
    st.subheader("Add patient")
    new_name = st.text_input("Name", key="add_name")
    new_contact = st.text_input("Contact", key="add_contact")
    new_diagnosis = st.text_input("Diagnosis", key="add_diagnosis")
    new_date = st.date_input("Date added", value=date.today(), key="add_date")
    if st.button("Save patient"):
        if not new_name.strip() or not new_contact.strip() or not new_diagnosis.strip():
            st.error("Please fill in all fields.")
        elif not valid_contact(new_contact):
            st.error("Please enter a valid contact number.")
        else:
            try:
                new_id = add_patient(
                    new_name.strip(),
                    new_contact.strip(),
                    new_diagnosis.strip(),
                    str(new_date),
                )
                try:
                    log_action(st.session_state.user_id, role, "add", f"Added patient {new_name.strip()} (ID {new_id})")
                except Exception:
                    pass
                st.success("Patient added.")
                st.rerun()
            except Exception:
                st.error("Something went wrong. Please try again.")
    st.write("")

if can_do(role, "edit") and patients:
    st.subheader("Edit patient")
    by_id = {p[0]: p for p in patients}
    picked = st.selectbox(
        "Choose a patient",
        options=list(by_id.keys()),
        format_func=lambda pid: f"#{pid} - {show_name(by_id[pid][1], by_id[pid][4], can_raw)}",
    )
    current = by_id[picked]
    edit_name = st.text_input("Name", value=current[1], key="edit_name")
    edit_contact = st.text_input("Contact", value=current[2], key="edit_contact")
    edit_diagnosis = st.text_input("Diagnosis", value=current[3], key="edit_diagnosis")
    if st.button("Save changes"):
        if not edit_name.strip() or not edit_contact.strip() or not edit_diagnosis.strip():
            st.error("Please fill in all fields.")
        elif not valid_contact(edit_contact):
            st.error("Please enter a valid contact number.")
        else:
            try:
                update_patient(
                    picked, edit_name.strip(), edit_contact.strip(), edit_diagnosis.strip()
                )
                try:
                    log_action(st.session_state.user_id, role, "update", f"Updated patient #{picked}")
                except Exception:
                    pass
                st.success("Patient updated.")
                st.rerun()
            except Exception:
                st.error("Something went wrong. Please try again.")

if can_do(role, "view_logs"):
    st.write("")
    st.subheader("Audit Logs")
    try:
        logs = get_all_logs()
    except Exception:
        st.error("Something went wrong. Please try again.")
        logs = []
    left, right = st.columns(2)
    with left:
        action_filter = st.selectbox(
            "Action", ["All", "login", "logout", "view", "add", "update", "anonymize"]
        )
    with right:
        role_filter = st.selectbox(
            "Role", ["All", "admin", "doctor", "receptionist", "unknown"]
        )
    log_rows = []
    for log in logs:
        log_id, log_user, log_role, log_action_name, log_time, log_details = log
        if action_filter != "All" and log_action_name != action_filter:
            continue
        if role_filter != "All" and log_role != role_filter:
            continue
        log_rows.append(
            {
                "ID": log_id,
                "User": log_user if log_user is not None else "-",
                "Role": log_role,
                "Action": log_action_name,
                "Time": log_time,
                "Details": log_details,
            }
        )
    st.write(f"{len(log_rows)} log entries")
    st.dataframe(log_rows, use_container_width=True)

st.write("")
st.markdown(
    '<p class="footer">Community Hospital — GDPR mini system, IS Assignment 4</p>',
    unsafe_allow_html=True,
)
