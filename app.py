import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import hashlib
from io import BytesIO

# --- PAGE CONFIG ---
st.set_page_config(page_title="UNAM JEDS Director Dashboard", layout="wide", page_icon="🏫")

# --- DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- HELPERS ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def load_data(sheet_name):
    try:
        return conn.read(worksheet=sheet_name, ttl=0)
    except:
        return pd.DataFrame()

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Campus_Report')
    return output.getvalue()

# --- OPTIONS ---
TITLES = ["Mr.", "Ms.", "Mrs.", "Dr.", "Prof.", "Eng."]
DEPARTMENTS = [
    "Electrical and Computer Engineering",
    "Mechanical and Metalurgical Engineering",
    "Civil and Mining Engineering",
    "Management & Administration"
]
ARTICLE_TYPES = ["Journal Article (Peer Reviewed)", "Conference Paper", "Book Chapter", "Technical Report", "Review Paper"]

# --- SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.update({"logged_in": False, "user": None, "role": None, "name": None, "dept": None, "title": None})

# --- AUTHENTICATION & REGISTRATION ---
if not st.session_state.logged_in:
    st.title("UNAM JEDS Engineering")
    auth_mode = st.tabs(["Login", "Staff Registration"])
    
    with auth_mode[0]:
        with st.form("login_form"):
            sid = st.text_input("Staff ID")
            pwd = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                users = load_data("staff_registry")
                user_row = users[users['staff_id'].astype(str) == str(sid)]
                if not user_row.empty and user_row.iloc[0]['password'] == hash_password(pwd):
                    st.session_state.update({
                        "logged_in": True, "user": sid, "name": user_row.iloc[0]['full_name'],
                        "role": user_row.iloc[0]['role'], "dept": user_row.iloc[0].get('department', 'N/A'),
                        "title": user_row.iloc[0].get('title', '')
                    })
                    st.rerun()
                else: st.error("Invalid credentials.")

    with auth_mode[1]:
        with st.form("reg_form"):
            st.info("Registration Key required from the Director's Office.")
            c1, c2 = st.columns([1, 3])
            r_title = c1.selectbox("Title", TITLES)
            r_name = c2.text_input("Full Name (Surname First)")
            r_id = st.text_input("Staff ID")
            r_dept = st.selectbox("Department", DEPARTMENTS)
            r_pwd = st.text_input("Set Password", type="password")
            r_key = st.text_input("Security Key", type="password")
            
            if st.form_submit_button("Register"):
                role = None
                if r_key == "JEDSACA2026": role = "Academic"
                elif r_key == "JEDSSUP2026": role = "Maintenance"
                elif r_key == "JEDSCOR2026": role = "Coordinator" # New Role
                
                if role:
                    users = load_data("staff_registry")
                    new_user = pd.DataFrame([{"staff_id": r_id, "title": r_title, "full_name": r_name, "role": role, "password": hash_password(r_pwd), "department": r_dept}])
                    conn.update(worksheet="staff_registry", data=pd.concat([users, new_user], ignore_index=True))
                    st.success(f"Registered as {role}! You can now login.")
                else: st.error("Invalid Security Key.")
    st.stop()

# --- SIDEBAR ---
st.sidebar.title("JEDS Portal")
st.sidebar.write(f"**{st.session_state.title} {st.session_state.name}**")
st.sidebar.write(f"*Role: {st.session_state.role}*")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- ROLE: DIRECTOR & COORDINATOR SHARED VIEW ---
if st.session_state.role in ["Director", "Coordinator"]:
    st.title(f"🏫 School Research Oversight ({st.session_state.role})")
    
    res_df = load_data("research_status")
    
    # KPI Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total School Papers", len(res_df))
    col2.metric("Published", len(res_df[res_df['status'] == "Published"]))
    col3.metric("Pending APCs", len(res_df[res_df['director_approval'] == "Pending"]))
    
    st.divider()
    
    # Department Filter
    search_dept = st.selectbox("Filter by Department", ["All"] + DEPARTMENTS)
    display_df = res_df if search_dept == "All" else res_df[res_df['department'] == search_dept]
    st.dataframe(display_df, use_container_width=True)
    
    # Exclusive Director Actions (Approvals)
    if st.session_state.role == "Director":
        pending = res_df[res_df['director_approval'] == "Pending"]
        if not pending.empty:
            st.subheader("💳 Financial Approvals (Director Only)")
            target = st.selectbox("Select Paper for APC Approval", pending['paper_title'].tolist())
            if st.button("Approve Funding"):
                res_df.loc[res_df['paper_title'] == target, 'director_approval'] = "Approved"
                conn.update(worksheet="research_status", data=res_df)
                st.rerun()
                
    st.download_button("📥 Download School Research Report", data=to_excel(res_df), file_name="School_Research_Full.xlsx")

# --- ROLE: ACADEMIC STAFF ---
elif st.session_state.role == "Academic":
    st.title("📖 Staff Research Portal")
    with st.form("res"):
        t = st.text_input("Paper Title")
        at = st.selectbox("Article Type", ARTICLE_TYPES)
        s = st.selectbox("Status", ["Draft", "Under Review", "Pending APC", "Published"])
        a = st.number_input("APC Amount (N$)", min_value=0)
        if st.form_submit_button("Submit Record"):
            old = load_data("research_status")
            new = pd.DataFrame([{
                "staff_id": st.session_state.user, "full_name": f"{st.session_state.title} {st.session_state.name}",
                "department": st.session_state.dept, "paper_title": t, "article_type": at,
                "status": s, "apc_amount": a, "director_approval": "Pending" if s == "Pending APC" else "N/A",
                "timestamp": datetime.now().strftime("%Y-%m-%d")
            }])
            conn.update(worksheet="research_status", data=pd.concat([old, new], ignore_index=True))
            st.success("Research status updated.")

# --- ROLE: MAINTENANCE MANAGER ---
elif st.session_state.role == "Maintenance":
    st.title("🔧 Maintenance Management")
    m_df = load_data("maintenance_tickets")
    st.dataframe(m_df[m_df['status'] != "Resolved"], use_container_width=True)
    # Status update logic...

# --- SHARED: FAULT REPORTING ---
st.sidebar.divider()
if st.sidebar.checkbox("Report a Fault"):
    with st.form("f"):
        l = st.text_input("Location")
        d = st.text_area("Fault Detail")
        if st.form_submit_button("Report"):
            m_old = load_data("maintenance_tickets")
            new_t = pd.DataFrame([{"ticket_id": f"JEDS-{datetime.now().strftime('%M%S')}", "reporter": st.session_state.name, "location": l, "fault_description": d, "status": "Open", "date_reported": datetime.now().strftime("%Y-%m-%d")}])
            conn.update(worksheet="maintenance_tickets", data=pd.concat([m_old, new_t], ignore_index=True))
            st.success("Fault Reported.")
