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
    st.title(f"📊 {st.session_state.role} School Oversight")
    
    # Define tabs based on role permissions
    if st.session_state.role == "Director":
        tabs = st.tabs(["Research Analytics", "Maintenance Audit"])
        t_res, t_maint = tabs[0], tabs[1]
    else:
        # Coordinators only see Research
        t_res = st.tabs(["Research Analytics"])[0]
        t_maint = None

    # --- TAB 1: RESEARCH ANALYTICS ---
    with t_res:
        res_df = load_data("research_status")
        
        if not res_df.empty:
            # 1. CLEAN DATA & DROP DUPLICATES FOR ACCURATE COUNTS
            # We sort by timestamp to keep the most recent update for each title
            res_df['timestamp'] = pd.to_datetime(res_df['timestamp'], errors='coerce')
            unique_res = res_df.sort_values('timestamp', ascending=False).drop_duplicates('paper_title')
            
            # 2. RESEARCH KPI METRICS
           c1, c2, c3, c4, c5 = st.columns(5)
            
            count_pub = len(unique_res[unique_res['status'] == "Published"])
            count_acc = len(unique_res[unique_res['status'] == "Accepted"]) # New Status
            count_rev = len(unique_res[unique_res['status'] == "Under Review"])
            count_apc = len(unique_res[unique_res['status'] == "Pending APC"])
            
            c1.metric("✅ Published", count_pub)
            c2.metric("🎉 Accepted", count_acc)
            c3.metric("🔍 Under Review", count_rev)
            c4.metric("💳 Pending APC", count_apc)
            c5.metric("📚 Total Works", len(unique_res))
        
            st.divider()
            
            # 3. DIRECTOR'S APC APPROVAL PANEL
            if st.session_state.role == "Director":
                # Only show papers that are Pending APC and NOT yet approved
                pending_list = res_df[
                    (res_df['status'] == "Pending APC") & 
                    (res_df['director_approval'] != "Approved")
                ].drop_duplicates('paper_title')
                
                if not pending_list.empty:
                    st.subheader("💳 APC Funding Actions Required")
                    st.info(f"You have {len(pending_list)} requests awaiting approval.")
                    
                    # Create clear selection labels
                    pending_options = pending_list.apply(
                        lambda x: f"{x['paper_title']} | {x['full_name']} (N$ {x['apc_amount']})", axis=1
                    ).tolist()
                    
                    selected_option = st.selectbox("Select Paper to Approve:", pending_options)
                    selected_title = selected_option.split(" | ")[0]
                    
                    if st.button("✅ Approve APC Funding", type="primary"):
                        # Update all rows with this title to 'Approved'
                        res_df.loc[res_df['paper_title'] == selected_title, 'director_approval'] = "Approved"
                        # Move status from 'Pending APC' to 'Under Review' (or your preferred next step)
                        res_df.loc[res_df['paper_title'] == selected_title, 'status'] = "Under Review"
                        
                        conn.update(worksheet="research_status", data=res_df)
                        st.cache_data.clear()
                        st.success(f"Funding for '{selected_title}' approved successfully!")
                        st.rerun()
                else:
                    st.write("✨ **No pending APC approvals at this time.**")
                st.divider()

            # 4. DEPARTMENTAL VISUALIZATION
            st.subheader("Research Status by Department")
            chart_df = unique_res.groupby(['department', 'status']).size().unstack(fill_value=0)
            target_metrics = [m for m in ["Published", "Under Review", "Pending APC"] if m in chart_df.columns]
            if target_metrics:
                st.bar_chart(chart_df[target_metrics])
            
            # 5. FULL DATA REGISTRY (For detailed lookup)
            st.subheader("Full Research Registry (All Updates)")
            dept_filt = st.selectbox("Filter Registry by Dept", ["All"] + DEPARTMENTS)
            disp_res = res_df if dept_filt == "All" else res_df[res_df['department'] == dept_filt]
            st.dataframe(disp_res, use_container_width=True)
            
        else:
            st.info("The research registry is currently empty.")

    # --- TAB 2: MAINTENANCE AUDIT (Director Only) ---
    if t_maint:
        with t_maint:
            st.subheader("Campus Maintenance Oversight")
            m_df = load_data("maintenance_tickets")
            
            if not m_df.empty:
                # Maintenance Summary KPIs
                mc1, mc2, mc3 = st.columns(3)
                total_t = len(m_df)
                resolved_t = len(m_df[m_df['status'] == "Resolved"])
                pending_t = total_t - resolved_t
                
                mc1.metric("Total Faults", total_t)
                mc2.metric("Pending Repairs", pending_t, delta_color="inverse")
                mc3.metric("Resolved Issues", resolved_t)
                
                st.divider()
                
                # Full Audit Log
                st.dataframe(m_df, use_container_width=True)
                
                # Audit Export
                st.download_button(
                    label="📥 Export Maintenance Audit (Excel)",
                    data=to_excel(m_df),
                    file_name=f"UNAM_JEDS_Maint_Audit_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("No maintenance tickets have been reported yet.")

# --- MODULE: ACADEMIC STAFF ---
elif st.session_state.role == "Academic":
    st.title("📖 Academic Staff Portal")
    
    tab_registry, tab_fault = st.tabs(["Research Registry", "Report Maintenance Fault"])
    
    # --- TAB 1: RESEARCH ---
    with tab_registry:
        st.subheader("Register / Update Your Research")
        with st.form("research_reg"):
            p_title = st.text_input("Research/Paper Title")
            p_type = st.selectbox("Article Type", ARTICLE_TYPES)
            p_status = st.selectbox("Current Status", ["Draft", "Under Review", "Pending APC", "Published"])
            p_apc = st.number_input("APC Amount Requested (N$)", min_value=0)
            
            if st.form_submit_button("Submit Record"):
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
                conn.update(worksheet="research_status", data=pd.concat([old_data, new_entry], ignore_index=True))
                st.cache_data.clear()
                st.rerun()

        st.divider()
        st.subheader("Your Submission History")
        full_res = load_data("research_status")
        if not full_res.empty:
            full_res['staff_id'] = full_res['staff_id'].astype(str).str.split('.').str[0].str.strip()
            my_res = full_res[full_res['staff_id'] == str(st.session_state.user).strip()]
            st.dataframe(my_res, use_container_width=True)

    # --- TAB 2: MAINTENANCE (FIXED SUBMISSION & HISTORY) ---
    with tab_fault:
        st.subheader("Report Campus Maintenance Fault")
        with st.form("staff_fault"):
            f_loc = st.text_input("Exact Location (e.g., Block B, Room 101)")
            f_desc = st.text_area("Description of the problem")
            
            # The logic MUST be inside this 'if' block
            if st.form_submit_button("Submit Fault Report"):
                m_old = load_data("maintenance_tickets")
                new_ticket = pd.DataFrame([{
                    "ticket_id": f"JEDS-{datetime.now().strftime('%M%S')}", 
                    "reporter": f"{st.session_state.title} {st.session_state.name}",
                    "reporter_id": str(st.session_state.user).strip(), # Added to track history
                    "location": f_loc, 
                    "fault_description": f_desc, 
                    "status": "Open", 
                    "manager_remarks": "", 
                    "date_reported": datetime.now().strftime("%Y-%m-%d")
                }])
                conn.update(worksheet="maintenance_tickets", data=pd.concat([m_old, new_ticket], ignore_index=True))
                st.cache_data.clear()
                st.success("Fault report successfully sent to Maintenance!")
                st.rerun()

        st.divider()
        st.subheader("Your Reported Faults History")
        all_faults = load_data("maintenance_tickets")
        
        if not all_faults.empty:
            # Filter by your staff ID
            if 'reporter_id' in all_faults.columns:
                all_faults['reporter_id'] = all_faults['reporter_id'].astype(str).str.split('.').str[0].str.strip()
                my_faults = all_faults[all_faults['reporter_id'] == str(st.session_state.user).strip()]
                
                if not my_faults.empty:
                    st.dataframe(my_faults, use_container_width=True)
                else:
                    st.info("You haven't reported any faults yet.")
            else:
                st.warning("Note: Older reports may not show ID tracking. New reports will appear here.")
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
