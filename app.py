import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import hashlib
from io import BytesIO

# --- PAGE CONFIG ---
st.set_page_config(page_title="UNAM JEDS Dashboard", layout="wide", page_icon="🏫")

# --- SCROLL FIX & CUSTOM STYLING ---
st.markdown(
    """
    <style>
    .main .block-container {
        overflow-y: auto;
        height: auto;
        padding-top: 2rem;
    }
    html, body {
        overflow: auto;
    }
    /* Make metrics stand out */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        color: #003366;
    }
    </style>
    """,
    unsafe_allow_html=True
)

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
        df.to_excel(writer, index=False, sheet_name='Report')
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

# --- SIDEBAR LOGO ---
try:
    st.sidebar.image("Logo_UNAM_Namibia.png", use_container_width=True)
except:
    st.sidebar.warning("Logo file not found in repository.")

# --- SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.update({"logged_in": False, "user": None, "role": None, "name": None, "dept": None, "title": None})

# --- AUTHENTICATION ---
if not st.session_state.logged_in:
    st.title("UNAM School of Engineering")
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
            c1, c2 = st.columns([1, 3])
            r_title = c1.selectbox("Title", TITLES)
            r_name = c2.text_input("Full Name (Surname First)")
            r_id = st.text_input("Staff ID")
            r_dept = st.selectbox("Department", DEPARTMENTS)
            r_pwd = st.text_input("Set Password", type="password")
            r_key = st.text_input("Security Key", type="password")
            if st.form_submit_button("Register"):
                role = "Academic" if r_key == "JEDSACA2026" else "Maintenance" if r_key == "JEDSSUP2026" else "Coordinator" if r_key == "JEDSCOR2026" else None
                if role:
                    users = load_data("staff_registry")
                    new_user = pd.DataFrame([{"staff_id": r_id, "title": r_title, "full_name": r_name, "role": role, "password": hash_password(r_pwd), "department": r_dept}])
                    conn.update(worksheet="staff_registry", data=pd.concat([users, new_user], ignore_index=True))
                    st.success(f"Registered as {role}!")
                else: st.error("Invalid Key.")
    st.stop()

# --- SIDEBAR LOGGED IN ---
st.sidebar.write(f"**User:** {st.session_state.title} {st.session_state.name}")
st.sidebar.write(f"**Dept:** {st.session_state.dept}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- MODULE: DIRECTOR & COORDINATOR ---
if st.session_state.role in ["Director", "Coordinator"]:
    st.title(f"📊 {st.session_state.role} Oversight")
    
    if st.session_state.role == "Director":
        tabs = st.tabs(["Research Analytics", "Maintenance Audit"])
        t_res, t_maint = tabs[0], tabs[1]
    else:
        t_res, t_maint = st.tabs(["Research Analytics"])[0], None

    with t_res:
        res_df = load_data("research_status")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Papers", len(res_df))
        m2.metric("Published", len(res_df[res_df['status'] == "Published"]))
        m3.metric("Pending APCs", len(res_df[res_df['director_approval'] == "Pending"]))
        
        dept_filter = st.selectbox("View Department", ["All"] + DEPARTMENTS)
        display_df = res_df if dept_filter == "All" else res_df[res_df['department'] == dept_filter]
        st.dataframe(display_df, use_container_width=True)

    if t_maint:
        with t_maint:
            m_df = load_data("maintenance_tickets")
            st.dataframe(m_df, use_container_width=True)

# --- MODULE: ACADEMIC STAFF ---
elif st.session_state.role == "Academic":
    st.title("📖 Academic Staff Portal")
    
    tab_registry, tab_fault = st.tabs(["Research Registry", "Report Maintenance Fault"])
    
    with tab_registry:
        st.subheader("Register / Update Your Research")
        with st.form("research_reg"):
            p_title = st.text_input("Research/Paper Title")
            p_type = st.selectbox("Article Type", ARTICLE_TYPES)
            p_status = st.selectbox("Current Status", ["Draft", "Under Review", "Pending APC", "Published"])
            p_apc = st.number_input("APC Amount Requested (N$)", min_value=0)
            
            # --- THE FIX FOR THE INDENTATION ERROR IS HERE ---
            if st.form_submit_button("Submit Record"):
                # All code below must be indented further than the 'if' above
                old_data = load_data("research_status")
                
                new_entry = pd.DataFrame([{
                    "staff_id": st.session_state.user, 
                    "full_name": f"{st.session_state.title} {st.session_state.name}",
                    "department": st.session_state.dept, 
                    "paper_title": p_title, 
                    "article_type": p_type, 
                    "status": p_status, 
                    "apc_amount": p_apc, 
                    "director_approval": "Pending" if p_status == "Pending APC" else "N/A",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
                }])
                
                # Combine and Update
                updated_df = pd.concat([old_data, new_entry], ignore_index=True)
                conn.update(worksheet="research_status", data=updated_df)
                
                # Force the app to clear memory and reload
                st.cache_data.clear()
                st.success("Research status successfully recorded!")
                st.rerun() 

        st.divider()
        st.subheader("Your Submission History")
        
        # Reload live data for the history table
        full_res = load_data("research_status")
        
       # --- Updated History Filtering ---
if not full_res.empty:
    # 1. Clean the data: Convert column to string and strip spaces
    full_res['staff_id'] = full_res['staff_id'].astype(str).str.strip()
    
    # 2. Clean the session variable
    current_user = str(st.session_state.user).strip()
    
    # 3. Filter
    my_res = full_res[full_res['staff_id'] == current_user]
    
    if not my_res.empty:
        st.dataframe(my_res, use_container_width=True)
    else:
        # Debugging info (Only shows if no match is found)
        st.info(f"Checking records for ID: '{current_user}'")
        st.warning("No records matched. Please ensure your Staff ID in the 'staff_registry' matches the 'research_status' sheet exactly.")

    with tab_fault:
        # (Rest of your maintenance fault code remains here)
        st.subheader("Report Campus Maintenance Fault")
        with st.form("staff_fault"):
            f_loc = st.text_input("Exact Location (Room/Block)")
            f_desc = st.text_area("Detailed Description of Fault")
            if st.form_submit_button("Submit Fault Report"):
                m_old = load_data("maintenance_tickets")
                new_t = pd.DataFrame([{
                    "ticket_id": f"JEDS-{datetime.now().strftime('%M%S')}", 
                    "reporter": f"{st.session_state.title} {st.session_state.name}", 
                    "location": f_loc, "fault_description": f_desc, "status": "Open", 
                    "manager_remarks": "", "date_reported": datetime.now().strftime("%Y-%m-%d")
                }])
                conn.update(worksheet="maintenance_tickets", data=pd.concat([m_old, new_t], ignore_index=True))
                st.cache_data.clear()
                st.success("Fault report sent!")
                st.rerun()
# --- MODULE: MAINTENANCE MANAGER ---
elif st.session_state.role == "Maintenance":
    st.title("🔧 Maintenance Manager")
    m_df = load_data("maintenance_tickets")
    st.dataframe(m_df[m_df['status'] != "Resolved"], use_container_width=True)
    with st.expander("Update Ticket Status"):
        open_jobs = m_df[m_df['status'] != "Resolved"]
        if not open_jobs.empty:
            t_id = st.selectbox("Select Ticket", open_jobs['ticket_id'].tolist())
            n_s = st.selectbox("New Status", ["In-Progress", "Awaiting Parts", "Resolved"])
            rem = st.text_area("Manager Remarks")
            if st.button("Update"):
                m_df.loc[m_df['ticket_id'] == t_id, 'status'] = n_s
                m_df.loc[m_df['ticket_id'] == t_id, 'manager_remarks'] = rem
                conn.update(worksheet="maintenance_tickets", data=m_df)
                st.rerun()
