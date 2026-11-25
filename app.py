import streamlit as st

# Hospital dashboard. Login and patient pages come in the next steps.
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

st.markdown(
    '<div class="top-bar"><h1>Community Hospital</h1>'
    "<p>Patient records, with privacy built in</p></div>",
    unsafe_allow_html=True,
)
st.write("")

st.markdown(
    '<div class="card">This dashboard keeps patient data private. '
    "Only the right role can see the right data, and every action is logged.</div>",
    unsafe_allow_html=True,
)
st.write("")

st.info("Login page is next. After that, patients, anonymization and logs will show up here.")

st.write("")
st.markdown(
    '<p class="footer">Community Hospital — GDPR mini system, IS Assignment 4</p>',
    unsafe_allow_html=True,
)
