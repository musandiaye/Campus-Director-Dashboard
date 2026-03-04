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
    """Encodes password into a SHA-256 hash."""
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

# --- SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.update({"logged_in": False, "user": None, "role": None, "name": None})

# --- AUTHENTICATION & REGISTRATION ---
if not st.session_state.logged_in:
    st.title("UNAM JEDS Engineering")
    st.subheader("Campus Management System (Secure)")
    
    auth_mode = st.tabs(["Login", "Staff Registration"])
    
    with auth_mode[0]: # Login Tab
        with st.form("login_form"):
            sid = st.text_input("Staff ID")
            pwd = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                users = load_data("staff_registry")
                user_row = users[users['staff_id'].astype(str) == str(sid)]
                
                if not user_row.empty:
                    # Compare the HASH of the input with the STORED HASH
                    if user_row.iloc[0]['password'] == hash_password(pwd):
                        st.session_state.update({
                            "logged_in": True,
                            "user": sid,
                            "name": user_row.iloc[0]['full_name'],
                            "role": user_row.iloc[0]['role']
                        })
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
                else:
                    st.error("Staff ID not found.")

    with auth_mode[1]: # Registration Tab
        with st.form("reg_form"):
            st.info("Registration requires a security key provided by the Director.")
            new_id = st.text_input("Staff ID (Employee Number)")
            new_name = st.text_input("Full Name")
            new_email = st.text_input("Email Address")
            new_pwd = st.text_input("Set Password", type="password")
            reg_key = st.text_input("Security Registration Key", type="password")
            
            if st.form_submit_button("Register Account"):
                role = None
                if reg_key == "JEDSACA2026": role = "Academic"
                elif reg_key == "JEDSSUP2026": role = "Maintenance"
                
                if role:
                    users = load_data("staff_registry")
                    if str(new_id) in users['staff_id'].astype(str).values:
                        st.error("This Staff ID is already registered.")
                    else:
                        # STORE THE HASHED PASSWORD
                        new_user = pd.DataFrame([{
                            "staff_id": new_id, 
                            "full_name": new_name, 
                            "email": new_email,
                            "role": role, 
                            "password": hash_password(new_pwd), 
                            "department": "Engineering"
                        }])
                        updated_users = pd.concat([users, new_user], ignore_index=True)
                        conn.update(worksheet="staff_registry", data=updated_users)
                        st.success(f"Successfully registered as {role}! You can now Login.")
                else:
                    st.error("Invalid Security Key.")
    st.stop()

# --- LOGGED IN UI ---
st.sidebar.title("JEDS Dashboard")
st.sidebar.write(f"**User:** {st.session_state.name}")
st.sidebar.write(f"**Role:** {st.session_state.role}")

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- DIRECTOR MODULE ---
if st.session_state.role == "Director":
    st.title("🏛️ Director Oversight")
    t1, t2 = st.tabs(["Research & APCs", "Maintenance Logs"])
    
    with t1:
        res_df = load_data("research_status")
        st.subheader("Campus Research Status")
        st.dataframe(res_df, use_container_width=True)
        
        pending = res_df[res_df['director_approval'] == "Pending"]
        if not pending.empty:
            target = st.selectbox("Action on APC Request", pending['paper_title'].tolist())
            c1, c2 = st.columns(2)
            if c1.button("✅ Approve"):
                res_df.loc[res_df['paper_title'] == target, 'director_approval'] = "Approved"
                conn.update(worksheet="research_status", data=res_df)
                st.rerun()
            if c2.button("❌ Decline"):
                res_df.loc[res_df['paper_title'] == target, 'director_approval'] = "Declined"
                conn.update(worksheet="research_status", data=res_df)
                st.rerun()
        st.download_button("📥 Download Research Report", data=to_excel(res_df), file_name="JEDS_Research.xlsx")

    with t2:
        m_df = load_data("maintenance_tickets")
        st.subheader("Maintenance Ticket Tracking")
        st.dataframe(m_df, use_container_width=True)
        st.download_button("📥 Download Maintenance Report", data=to_excel(m_df), file_name="JEDS_Maintenance.xlsx")

# --- ACADEMIC MODULE ---
elif st.session_state.role == "Academic":
    st.title("📖 Staff Research Portal")
    with st.form("res_update"):
        title = st.text_input("Project/Paper Title")
        status = st.selectbox("Current Stage", ["Draft", "Under Review", "Pending APC", "Published"])
        apc_amt = st.number_input("APC Amount Requested (N$)", min_value=0)
        if st.form_submit_button("Submit Record"):
            old = load_data("research_status")
            new = pd.DataFrame([{"staff_id": st.session_state.user, "paper_title": title, "status": status, "apc_amount": apc_amt, "director_approval": "Pending" if status == "Pending APC" else "N/A", "timestamp": datetime.now().strftime("%Y-%m-%d")}])
            conn.update(worksheet="research_status", data=pd.concat([old, new]))
            st.success("Record Saved.")

# --- MAINTENANCE MODULE ---
elif st.session_state.role == "Maintenance":
    st.title("🔧 Maintenance Manager Portal")
    m_df = load_data("maintenance_tickets")
    open_jobs = m_df[m_df['status'] != "Resolved"]
    st.dataframe(open_jobs)
    
    if not open_jobs.empty:
        with st.form("update_job"):
            t_id = st.selectbox("Select Ticket", open_jobs['ticket_id'].tolist())
            n_stat = st.selectbox("Update Status", ["In-Progress", "Resolved"])
            rem = st.text_area("Manager Remarks")
            if st.form_submit_button("Update Job Card"):
                m_df.loc[m_df['ticket_id'] == t_id, 'status'] = n_stat
                m_df.loc[m_df['ticket_id'] == t_id, 'manager_remarks'] = rem
                conn.update(worksheet="maintenance_tickets", data=m_df)
                st.rerun()

# --- SHARED FAULT REPORTING ---
st.sidebar.divider()
if st.sidebar.checkbox("Report Maintenance Fault"):
    with st.form("fault"):
        loc = st.text_input("Location")
        desc = st.text_area("Fault Detail")
        if st.form_submit_button("Submit Ticket"):
            old = load_data("maintenance_tickets")
            new = pd.DataFrame([{"ticket_id": f"TKT-{datetime.now().strftime('%M%S')}", "reporter": st.session_state.name, "location": loc, "fault_description": desc, "status": "Open", "date_reported": datetime.now().strftime("%Y-%m-%d")}])
            conn.update(worksheet="maintenance_tickets", data=pd.concat([old, new]))
            st.success("Reported.")
