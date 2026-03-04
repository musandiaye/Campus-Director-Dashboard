import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import hashlib
from io import BytesIO

# --- PAGE CONFIG ---
st.set_page_config(page_title="UNAM JEDS Director Dashboard", layout="wide")

# --- CONNECTION ---
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
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# --- SESSION STATE ---
if 'auth' not in st.session_state:
    st.session_state.auth = {"logged_in": False, "user": None, "role": None}

# --- SIDEBAR LOGO & TITLE ---
st.sidebar.title("UNAM JEDS")
st.sidebar.subheader("Campus Management System")

# --- AUTHENTICATION ---
if not st.session_state.auth["logged_in"]:
    with st.container():
        st.header("Login")
        u_id = st.text_input("Staff ID")
        u_pw = st.text_input("Password", type="password")
        
        if st.button("Login"):
            users = load_data("staff_registry")
            # In production, use hash_password(u_pw) comparison
            match = users[(users['staff_id'] == u_id)] 
            if not match.empty:
                st.session_state.auth = {
                    "logged_in": True, 
                    "user": match.iloc[0]['full_name'],
                    "role": match.iloc[0]['role'],
                    "dept": match.iloc[0]['department']
                }
                st.rerun()
            else:
                st.error("Invalid Credentials")
    st.stop()

# --- NAV ---
user_role = st.session_state.auth["role"]
st.sidebar.write(f"Welcome, **{st.session_state.auth['user']}**")
st.sidebar.write(f"Role: {user_role}")
if st.sidebar.button("Sign Out"):
    st.session_state.auth = {"logged_in": False, "user": None, "role": None}
    st.rerun()

# --- MODULES ---

# 1. DIRECTOR DASHBOARD
if user_role == "Director":
    st.title("Director's Oversight Dashboard")
    tab1, tab2 = st.tabs(["Research & APC Approvals", "Maintenance Oversight"])
    
    with tab1:
        st.subheader("Pending APC Requests")
        res_df = load_data("research_status")
        pending_apc = res_df[(res_df['status'] == "Pending APC") & (res_df['director_approval'] == "Pending")]
        
        if not pending_apc.empty:
            st.dataframe(pending_apc)
            approve_id = st.selectbox("Select Paper Title to Approve", pending_apc['paper_title'].tolist())
            if st.button("Approve Funding"):
                res_df.loc[res_df['paper_title'] == approve_id, 'director_approval'] = "Approved"
                conn.update(worksheet="research_status", data=res_df)
                st.success(f"Approved APC for {approve_id}")
                st.rerun()
        else:
            st.info("No pending funding requests.")
            
        st.divider()
        st.subheader("Generate Campus Research Report")
        st.download_button("Download Full Report (Excel)", data=to_excel(res_df), file_name="JEDS_Research_Report.xlsx")

    with tab2:
        st.subheader("Campus Maintenance Status")
        maint_df = load_data("maintenance_tickets")
        st.dataframe(maint_df)
        st.download_button("Download Maintenance Logs", data=to_excel(maint_df), file_name="JEDS_Maintenance_Report.xlsx")

# 2. ACADEMIC STAFF MODULE
elif user_role == "Academic":
    st.title("Research Portal")
    menu = st.radio("Action", ["Update Progress", "My Submissions"], horizontal=True)
    
    if menu == "Update Progress":
        with st.form("research_form"):
            title = st.text_input("Paper/Project Title")
            journal = st.text_input("Target Journal/Conference")
            status = st.selectbox("Status", ["Draft", "Under Review", "Pending APC", "Published"])
            apc_needed = st.number_input("APC Amount (if applicable)", min_value=0.0)
            
            if st.form_submit_button("Submit Update"):
                old_data = load_data("research_status")
                new_entry = pd.DataFrame([{
                    "staff_id": st.session_state.auth['user'],
                    "paper_title": title,
                    "journal": journal,
                    "status": status,
                    "apc_amount": apc_needed,
                    "director_approval": "Pending" if status == "Pending APC" else "N/A",
                    "timestamp": datetime.now().strftime("%Y-%m-%d")
                }])
                conn.update(worksheet="research_status", data=pd.concat([old_data, new_entry], ignore_index=True))
                st.success("Research status updated!")

# 3. MAINTENANCE MANAGER MODULE
elif user_role == "Maintenance":
    st.title("Maintenance Job Cards")
    maint_df = load_data("maintenance_tickets")
    
    st.subheader("Open Tickets")
    open_tickets = maint_df[maint_df['status'] != "Resolved"]
    st.dataframe(open_tickets)
    
    with st.expander("Update Ticket Status"):
        if not open_tickets.empty:
            t_id = st.selectbox("Select Ticket ID", open_tickets['ticket_id'].tolist())
            new_status = st.selectbox("New Status", ["Assigned", "In Progress", "Resolved"])
            remarks = st.text_area("Manager Remarks")
            
            if st.button("Update Job Card"):
                maint_df.loc[maint_df['ticket_id'] == t_id, 'status'] = new_status
                maint_df.loc[maint_df['ticket_id'] == t_id, 'manager_remarks'] = remarks
                conn.update(worksheet="maintenance_tickets", data=maint_df)
                st.success(f"Ticket {t_id} updated to {new_status}")
                st.rerun()

# 4. GENERAL FAULT REPORTING (Available to all)
st.sidebar.divider()
if st.sidebar.checkbox("Report a Campus Fault"):
    st.write("---")
    st.header("Report Maintenance Issue")
    with st.form("fault_form"):
        loc = st.text_input("Location (Building/Room)")
        desc = st.text_area("Description of Fault")
        priority = st.select_slider("Priority", options=["Low", "Medium", "High"])
        
        if st.form_submit_button("Submit Ticket"):
            m_df = load_data("maintenance_tickets")
            new_t = pd.DataFrame([{
                "ticket_id": f"TKT-{datetime.now().strftime('%f')}",
                "reporter": st.session_state.auth['user'],
                "location": loc,
                "fault_description": desc,
                "priority": priority,
                "status": "Open",
                "date_reported": datetime.now().strftime("%Y-%m-%d")
            }])
            conn.update(worksheet="maintenance_tickets", data=pd.concat([m_df, new_t], ignore_index=True))
            st.success("Fault reported. The maintenance manager has been notified.")
