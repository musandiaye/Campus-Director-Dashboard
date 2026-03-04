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
        df = conn.read(worksheet=sheet_name, ttl=0)
        return df
    except:
        return pd.DataFrame()

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Campus_Report')
    return output.getvalue()

# --- STANDARDIZED OPTIONS ---
TITLES = ["Mr.", "Ms.", "Mrs.", "Dr.", "Prof.", "Eng."]

DEPARTMENTS = [
    "Electrical and Computer Engineering",
    "Mechanical and Metalurgical Engineering",
    "Civil and Mining Engineering",
    "Management & Administration"
]

ARTICLE_TYPES = [
    "Journal Article (Peer Reviewed)", 
    "Conference Paper", 
    "Book Chapter", 
    "Technical Report", 
    "Review Paper"
]

# --- SESSION STATE INITIALIZATION ---
if 'logged_in' not in st.session_state:
    st.session_state.update({
        "logged_in": False, "user": None, "role": None, 
        "name": None, "dept": None, "title": None
    })

# --- AUTHENTICATION & REGISTRATION ---
if not st.session_state.logged_in:
    st.title("UNAM JEDS Engineering")
    st.subheader("Campus Management System")
    
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
            st.info("Registration Key required.")
            c1, c2 = st.columns([1, 3])
            new_title = c1.selectbox("Title", TITLES)
            new_name = c2.text_input("Full Name (Surname First)")
            new_id = st.text_input("Staff ID")
            new_dept = st.selectbox("Department", DEPARTMENTS)
            new_pwd = st.text_input("Set Password", type="password")
            reg_key = st.text_input("Security Key", type="password")
            
            if st.form_submit_button("Register"):
                role = "Academic" if reg_key == "JEDSACA2026" else "Maintenance" if reg_key == "JEDSSUP2026" else None
                if role:
                    users = load_data("staff_registry")
                    new_user = pd.DataFrame([{"staff_id": new_id, "title": new_title, "full_name": new_name, "role": role, "password": hash_password(new_pwd), "department": new_dept}])
                    conn.update(worksheet="staff_registry", data=pd.concat([users, new_user], ignore_index=True))
                    st.success("Account created!")
                else: st.error("Invalid Key.")
    st.stop()

# --- SIDEBAR ---
st.sidebar.title("JEDS Portal")
st.sidebar.write(f"**{st.session_state.title} {st.session_state.name}**")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- DIRECTOR VIEW ---
if st.session_state.role == "Director":
    st.title("🏛️ Director Oversight")
    t1, t2 = st.tabs(["Research Analytics", "Maintenance Audit"])
    
    with t1:
        res_df = load_data("research_status")
        
        # --- NEW METRIC SECTION ---
        st.subheader("Campus Publication KPI")
        col1, col2, col3 = st.columns(3)
        
        published_count = len(res_df[res_df['status'] == "Published"])
        pending_apc = len(res_df[res_df['director_approval'] == "Pending"])
        total_papers = len(res_df)
        
        col1.metric("Total Research Projects", total_papers)
        col2.metric("Successfully Published", published_count, delta="Confirmed")
        col3.metric("Pending APC Approvals", pending_apc, delta_color="inverse")
        st.divider()
        # -------------------------

        search_dept = st.selectbox("Department Filter", ["All"] + DEPARTMENTS)
        display_df = res_df if search_dept == "All" else res_df[res_df['department'] == search_dept]
        st.dataframe(display_df, use_container_width=True)
        
        # Approval Logic
        pending = res_df[res_df['director_approval'] == "Pending"]
        if not pending.empty:
            st.subheader("Pending Funding Actions")
            target = st.selectbox("Select Paper", pending['paper_title'].tolist())
            if st.button("✅ Approve APC Funding"):
                res_df.loc[res_df['paper_title'] == target, 'director_approval'] = "Approved"
                conn.update(worksheet="research_status", data=res_df)
                st.rerun()
        
        st.download_button("📥 Export Research Report", data=to_excel(res_df), file_name="Campus_Research.xlsx")

# --- ACADEMIC VIEW ---
elif st.session_state.role == "Academic":
    st.title("📖 Academic Portal")
    with st.form("research"):
        title = st.text_input("Paper Title")
        atype = st.selectbox("Article Type", ARTICLE_TYPES)
        stat = st.selectbox("Status", ["Draft", "Under Review", "Pending APC", "Published"])
        amt = st.number_input("APC Amount (N$)", min_value=0)
        if st.form_submit_button("Submit"):
            old = load_data("research_status")
            new = pd.DataFrame([{
                "staff_id": st.session_state.user, "full_name": f"{st.session_state.title} {st.session_state.name}",
                "department": st.session_state.dept, "paper_title": title, "article_type": atype,
                "status": stat, "apc_amount": amt, "director_approval": "Pending" if stat == "Pending APC" else "N/A",
                "timestamp": datetime.now().strftime("%Y-%m-%d")
            }])
            conn.update(worksheet="research_status", data=pd.concat([old, new], ignore_index=True))
            st.success("Updated.")

# --- MAINTENANCE VIEW ---
elif st.session_state.role == "Maintenance":
    st.title("🔧 Maintenance Manager")
    m_df = load_data("maintenance_tickets")
    st.dataframe(m_df[m_df['status'] != "Resolved"], use_container_width=True)
    # Status update logic...

# --- FAULT REPORTING ---
st.sidebar.divider()
if st.sidebar.checkbox("Report a Fault"):
    with st.form("fault"):
        loc = st.text_input("Location")
        desc = st.text_area("Fault")
        if st.form_submit_button("Report"):
            m_old = load_data("maintenance_tickets")
            new_t = pd.DataFrame([{"ticket_id": f"JEDS-{datetime.now().strftime('%M%S')}", "reporter": st.session_state.name, "location": loc, "fault_description": desc, "status": "Open", "date_reported": datetime.now().strftime("%Y-%m-%d")}])
            conn.update(worksheet="maintenance_tickets", data=pd.concat([m_old, new_t], ignore_index=True))
            st.success("Reported.")
