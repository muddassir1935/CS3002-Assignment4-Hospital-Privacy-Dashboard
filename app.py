import streamlit as st

from auth import can_do, check_login
from database import init_db

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


def logout():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.user_id = None


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
                try:
                    user = check_login(username.strip(), password)
                except Exception:
                    st.error("Something went wrong. Please try again.")
                    user = None
                if user is None:
                    st.error("Wrong username or password.")
                else:
                    st.session_state.logged_in = True
                    st.session_state.username = user["username"]
                    st.session_state.role = user["role"]
                    st.session_state.user_id = user["user_id"]
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

# The patient list, anonymization and logs come in the next steps.
# can_do is already the check those pages will use.
if can_do(role, "view_raw"):
    st.info("Patient list and anonymization are next.")
elif can_do(role, "view_anon"):
    st.info("Patient list (anonymized) is next.")
else:
    st.info("Patient list is next.")

st.write("")
st.markdown(
    '<p class="footer">Community Hospital — GDPR mini system, IS Assignment 4</p>',
    unsafe_allow_html=True,
)
