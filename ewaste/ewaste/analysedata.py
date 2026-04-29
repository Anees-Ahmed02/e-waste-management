import streamlit as st
import sqlite3
import hashlib
import datetime
import pandas as pd
import os
import numpy as np
from PIL import Image

# ----------------------------
# Page Configuration & Custom CSS
# ----------------------------
st.set_page_config(
    page_title="AI E-Waste Management",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="auto"
)

# Custom CSS (same as before)
st.markdown("""
<style>
    .block-container { max-width: 1200px; padding-top: 2rem; padding-bottom: 2rem; }
    .css-1r6slb0, .css-12oz5g7 {
        background-color: #f8f9fa; border-radius: 10px; padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); margin-bottom: 20px;
    }
    h1, h2, h3 { text-align: center; }
    .css-1xarl3l {
        background-color: #e8f4f8; border-radius: 10px; padding: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stButton button {
        background-color: #4CAF50; color: white; border-radius: 8px;
        padding: 0.5rem 1rem; font-weight: bold; border: none; width: 100%;
    }
    .stButton button:hover { background-color: #45a049; }
    .css-1d391kg { background-color: #f0f2f6; }
    .stTextInput input, .stNumberInput input, .stSelectbox, .stDateInput { border-radius: 8px; }
    .stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Database Setup with Auto-Upgrade
# ----------------------------
def create_tables():
    """Create tables if they don't exist, and add missing columns."""
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()

    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  role TEXT NOT NULL,
                  reward_points INTEGER DEFAULT 0)''')

    # E-waste requests table (create if not exists)
    c.execute('''CREATE TABLE IF NOT EXISTS ewaste_requests
                 (request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  citizen_id INTEGER NOT NULL,
                  item_name TEXT NOT NULL,
                  item_type TEXT,                -- AI classification
                  manual_category TEXT,           -- NEW: user-selected category
                  quantity INTEGER NOT NULL,
                  image_path TEXT,
                  AI_classification TEXT,
                  reward_points INTEGER DEFAULT 0,
                  status TEXT DEFAULT 'pending',
                  recycler_id INTEGER,
                  request_date TIMESTAMP,
                  verified_date TIMESTAMP,
                  FOREIGN KEY(citizen_id) REFERENCES users(user_id),
                  FOREIGN KEY(recycler_id) REFERENCES users(user_id))''')

    # Rewards table
    c.execute('''CREATE TABLE IF NOT EXISTS rewards
                 (reward_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  citizen_id INTEGER NOT NULL,
                  request_id INTEGER NOT NULL,
                  points INTEGER NOT NULL,
                  date TIMESTAMP,
                  FOREIGN KEY(citizen_id) REFERENCES users(user_id),
                  FOREIGN KEY(request_id) REFERENCES ewaste_requests(request_id))''')

    # ----- Check for missing columns in ewaste_requests -----
    c.execute("PRAGMA table_info(ewaste_requests)")
    existing_columns = [col[1] for col in c.fetchall()]
    
    required_columns = [
        'request_id', 'citizen_id', 'item_name', 'item_type', 'manual_category',
        'quantity', 'image_path', 'AI_classification', 'reward_points',
        'status', 'recycler_id', 'request_date', 'verified_date'
    ]
    
    for col in required_columns:
        if col not in existing_columns:
            try:
                if col == 'verified_date':
                    c.execute("ALTER TABLE ewaste_requests ADD COLUMN verified_date TIMESTAMP")
                elif col == 'recycler_id':
                    c.execute("ALTER TABLE ewaste_requests ADD COLUMN recycler_id INTEGER")
                elif col == 'manual_category':
                    c.execute("ALTER TABLE ewaste_requests ADD COLUMN manual_category TEXT")
                # Add other columns as needed
            except sqlite3.OperationalError:
                pass

    conn.commit()
    conn.close()

def add_default_records():
    """Insert default users and sample requests if DB is empty."""
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()
    
    # Check if users table is empty
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        # Default users (password = 'password' hashed)
        default_users = [
            ('Citizen User', 'citizen@example.com', hash_password('password'), 'citizen', 150),
            ('Recycler User', 'recycler@example.com', hash_password('password'), 'recycler', 0),
            ('Admin User', 'admin@example.com', hash_password('password'), 'admin', 0)
        ]
        for user in default_users:
            c.execute('''INSERT INTO users (name, email, password, role, reward_points)
                         VALUES (?, ?, ?, ?, ?)''', user)
        
        # Get citizen id
        c.execute("SELECT user_id FROM users WHERE email='citizen@example.com'")
        citizen_id = c.fetchone()[0]
        
        # Sample requests
        sample_requests = [
            (citizen_id, 'Old Mobile Phone', 'Mobile', 'Mobile', 2, '', 'Mobile', 100, 'verified', 
             datetime.datetime.now() - datetime.timedelta(days=30), datetime.datetime.now() - datetime.timedelta(days=25)),
            (citizen_id, 'Broken Laptop', 'Laptop', 'Laptop', 1, '', 'Laptop', 100, 'verified',
             datetime.datetime.now() - datetime.timedelta(days=20), datetime.datetime.now() - datetime.timedelta(days=18)),
            (citizen_id, 'Dead Battery', 'Battery', 'Battery', 5, '', 'Battery', 150, 'verified',
             datetime.datetime.now() - datetime.timedelta(days=10), datetime.datetime.now() - datetime.timedelta(days=8)),
            (citizen_id, 'Misc Electronics', 'Other', 'Other', 3, '', 'Other', 60, 'pending',
             datetime.datetime.now() - datetime.timedelta(days=2), None)
        ]
        for req in sample_requests:
            c.execute('''INSERT INTO ewaste_requests
                         (citizen_id, item_name, item_type, manual_category, quantity, image_path,
                          AI_classification, reward_points, status, request_date, verified_date)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', req)
        
        # Update user's reward points based on verified requests
        c.execute('''UPDATE users SET reward_points = reward_points + 
                     (SELECT SUM(reward_points) FROM ewaste_requests 
                      WHERE citizen_id=? AND status='verified')''', (citizen_id,))
        
        conn.commit()
    
    conn.close()

# Initialize/upgrade database
create_tables()
add_default_records()

# Ensure upload directory exists
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ----------------------------
# Helper Functions (updated for new column)
# ----------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(name, email, password, role):
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                  (name, email, hash_password(password), role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(email, password, role):
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()
    c.execute("SELECT user_id, name, password FROM users WHERE email=? AND role=?",
              (email, role))
    user = c.fetchone()
    conn.close()
    if user and user[2] == hash_password(password):
        return {'user_id': user[0], 'name': user[1], 'role': role}
    return None

def get_user_rewards(user_id):
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()
    c.execute("SELECT reward_points FROM users WHERE user_id=?", (user_id,))
    points = c.fetchone()
    conn.close()
    return points[0] if points else 0

def get_user_requests(user_id):
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()
    c.execute('''SELECT request_id, item_name, quantity, AI_classification, 
                        manual_category, reward_points, status, request_date, verified_date
                 FROM ewaste_requests WHERE citizen_id=? ORDER BY request_date DESC''', (user_id,))
    requests = c.fetchall()
    conn.close()
    return requests

def get_pending_requests():
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()
    c.execute('''SELECT r.request_id, u.name, r.item_name, r.quantity, r.AI_classification, 
                        r.manual_category, r.reward_points, r.request_date
                 FROM ewaste_requests r
                 JOIN users u ON r.citizen_id = u.user_id
                 WHERE r.status='pending' ORDER BY r.request_date''')
    requests = c.fetchall()
    conn.close()
    return requests

def get_assigned_requests(recycler_id):
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()
    c.execute('''SELECT request_id, item_name, quantity, AI_classification, status, request_date
                 FROM ewaste_requests WHERE recycler_id=? AND status='assigned' ORDER BY request_date''', (recycler_id,))
    requests = c.fetchall()
    conn.close()
    return requests

def get_collected_requests():
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()
    c.execute('''SELECT r.request_id, u.name, r.item_name, r.quantity, r.AI_classification, 
                        r.reward_points, r.request_date, r.recycler_id
                 FROM ewaste_requests r
                 JOIN users u ON r.citizen_id = u.user_id
                 WHERE r.status='collected' ORDER BY r.request_date''')
    requests = c.fetchall()
    conn.close()
    return requests

def assign_request(request_id, recycler_id):
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()
    c.execute("UPDATE ewaste_requests SET status='assigned', recycler_id=? WHERE request_id=? AND status='pending'",
              (recycler_id, request_id))
    conn.commit()
    conn.close()

def mark_collected(request_id):
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()
    c.execute("UPDATE ewaste_requests SET status='collected' WHERE request_id=? AND status='assigned'", (request_id,))
    conn.commit()
    conn.close()

def verify_request(request_id, admin_id):
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()
    c.execute('''SELECT citizen_id, reward_points FROM ewaste_requests WHERE request_id=? AND status='collected' ''', (request_id,))
    result = c.fetchone()
    if result:
        citizen_id, points = result
        c.execute("UPDATE users SET reward_points = reward_points + ? WHERE user_id = ?", (points, citizen_id))
        c.execute("UPDATE ewaste_requests SET status='verified', verified_date=? WHERE request_id=?",
                  (datetime.datetime.now(), request_id))
        c.execute("INSERT INTO rewards (citizen_id, request_id, points, date) VALUES (?, ?, ?, ?)",
                  (citizen_id, request_id, points, datetime.datetime.now()))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def get_all_users():
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()
    c.execute("SELECT user_id, name, email, role, reward_points FROM users")
    users = c.fetchall()
    conn.close()
    return users

def get_all_requests():
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()
    c.execute('''SELECT r.request_id, u.name, r.item_name, r.quantity, r.AI_classification,
                        r.manual_category, r.reward_points, r.status, r.request_date, r.verified_date
                 FROM ewaste_requests r
                 JOIN users u ON r.citizen_id = u.user_id
                 ORDER BY r.request_date DESC''')
    requests = c.fetchall()
    conn.close()
    return requests

def get_stats():
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM ewaste_requests")
    total_requests = c.fetchone()[0]
    c.execute("SELECT SUM(reward_points) FROM users")
    total_rewards = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM ewaste_requests WHERE status='verified'")
    verified_requests = c.fetchone()[0]
    conn.close()
    return total_users, total_requests, total_rewards, verified_requests

# ----------------------------
# AI Simulation & ML Analysis
# ----------------------------
def predict_image(image_path):
    filename = os.path.basename(image_path).lower()
    if 'mobile' in filename or 'phone' in filename:
        return 'Mobile'
    elif 'laptop' in filename:
        return 'Laptop'
    elif 'battery' in filename:
        return 'Battery'
    else:
        import random
        return random.choice(['Mobile', 'Laptop', 'Battery', 'Other'])

def calculate_reward(item_type, quantity):
    points_map = {
        'Mobile': 50,
        'Laptop': 100,
        'Battery': 30,
        'Other': 20
    }
    return points_map.get(item_type, 20) * quantity

def get_ml_insights():
    """
    Simulate ML analysis on e-waste data.
    Returns a dictionary with insights and predictions.
    """
    conn = sqlite3.connect('ewaste.db')
    
    # Get all verified requests with dates
    df = pd.read_sql_query('''
        SELECT request_date, manual_category, quantity, reward_points
        FROM ewaste_requests
        WHERE status='verified' AND manual_category IS NOT NULL
    ''', conn, parse_dates=['request_date'])
    conn.close()
    
    if df.empty:
        return {
            'total_items': 0,
            'category_dist': {},
            'monthly_trend': {},
            'next_month_prediction': 0,
            'recoverable_value': 0,
            'co2_saved': 0
        }
    
    # Basic stats
    total_items = df['quantity'].sum()
    category_dist = df.groupby('manual_category')['quantity'].sum().to_dict()
    
    # Monthly trend
    df['month'] = df['request_date'].dt.to_period('M')
    monthly = df.groupby('month')['quantity'].sum().sort_index()
    monthly_trend = {str(k): v for k, v in monthly.items()}
    
    # Simple prediction for next month (linear regression simulation)
    # Use last 3 months average if enough data, else simple average
    if len(monthly) >= 3:
        last_3 = list(monthly.values)[-3:]
        next_pred = int(np.mean(last_3))
    elif len(monthly) > 0:
        next_pred = int(np.mean(list(monthly.values)))
    else:
        next_pred = 0
    
    # Simulated recoverable value (e.g., $ per item)
    # Different categories have different values
    value_per_item = {
        'Mobile': 5,
        'Laptop': 15,
        'Battery': 2,
        'Other': 1
    }
    recoverable = sum(df.apply(lambda row: value_per_item.get(row['manual_category'], 1) * row['quantity'], axis=1))
    
    # Simulated CO2 savings (kg per item)
    co2_per_item = {
        'Mobile': 50,
        'Laptop': 200,
        'Battery': 10,
        'Other': 5
    }
    co2_saved = sum(df.apply(lambda row: co2_per_item.get(row['manual_category'], 5) * row['quantity'], axis=1))
    
    return {
        'total_items': total_items,
        'category_dist': category_dist,
        'monthly_trend': monthly_trend,
        'next_month_prediction': next_pred,
        'recoverable_value': round(recoverable, 2),
        'co2_saved': round(co2_saved, 2)
    }

# ----------------------------
# UI Functions (updated for category)
# ----------------------------
def center_form(func):
    def wrapper(*args, **kwargs):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.container():
                st.markdown('<div class="css-1r6slb0">', unsafe_allow_html=True)
                func(*args, **kwargs)
                st.markdown('</div>', unsafe_allow_html=True)
    return wrapper

def main():
    st.markdown("<h1 style='text-align: center;'>♻️ AI Based E-Waste Management System</h1>", unsafe_allow_html=True)
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user = None
    
    if not st.session_state.logged_in:
        with st.sidebar:
            st.markdown("## 🌐 Main Menu")
            menu = st.radio("", ["🔑 Login", "📝 Register"], index=0, label_visibility="collapsed")
            if menu == "🔑 Login":
                show_login()
            else:
                show_register()
    else:
        with st.sidebar:
            user = st.session_state.user
            st.markdown(f"## 👤 Welcome, **{user['name']}**")
            st.markdown(f"**Role:** {user['role'].capitalize()}")
            st.markdown("---")
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.user = None
                st.rerun()
        
        if user['role'] == 'citizen':
            citizen_dashboard()
        elif user['role'] == 'recycler':
            recycler_dashboard()
        elif user['role'] == 'admin':
            admin_dashboard()

@center_form
def show_login():
    st.markdown("### 🔐 Login")
    with st.form("login_form"):
        email = st.text_input("📧 Email", placeholder="Enter your email")
        password = st.text_input("🔒 Password", type="password", placeholder="Enter your password")
        role = st.selectbox("👤 Role", ["citizen", "recycler", "admin"])
        submitted = st.form_submit_button("🚀 Login", use_container_width=True)
        if submitted:
            user = login_user(email, password, role)
            if user:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.success(f"✅ Welcome, {user['name']}!")
                st.rerun()
            else:
                st.error("❌ Invalid credentials or role.")

@center_form
def show_register():
    st.markdown("### 📝 Register New Account")
    with st.form("register_form"):
        name = st.text_input("👤 Full Name", placeholder="Enter your full name")
        email = st.text_input("📧 Email", placeholder="Enter your email")
        password = st.text_input("🔒 Password", type="password", placeholder="Choose a password")
        role = st.selectbox("👤 Role", ["citizen", "recycler", "admin"])
        submitted = st.form_submit_button("✅ Register", use_container_width=True)
        if submitted:
            if register_user(name, email, password, role):
                st.success("🎉 Registration successful! Please log in.")
            else:
                st.error("❌ Email already exists. Try a different one.")

def citizen_dashboard():
    st.markdown("## 🏠 Citizen Dashboard")
    tabs = st.tabs(["📤 Upload E-Waste", "🏆 View Rewards", "📋 Track Requests"])
    
    with tabs[0]:
        st.markdown("### Upload New E-Waste")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("upload_form", clear_on_submit=True):
                item_name = st.text_input("📦 Item Name", placeholder="e.g., Old Mobile Phone")
                # NEW: manual category dropdown
                category_options = ["Mobile", "Laptop", "Battery", "Other"]
                manual_category = st.selectbox("📂 Select Category (optional)", [""] + category_options, 
                                               help="Choose the type of e-waste. If not selected, AI will classify.")
                quantity = st.number_input("🔢 Quantity", min_value=1, step=1, value=1)
                image_file = st.file_uploader("📸 Upload Image", type=['jpg', 'jpeg', 'png'])
                submitted = st.form_submit_button("📤 Submit Request", use_container_width=True)
                
                if submitted and image_file and item_name:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    img_path = os.path.join(UPLOAD_DIR, f"{timestamp}_{image_file.name}")
                    with open(img_path, "wb") as f:
                        f.write(image_file.getbuffer())
                    
                    # AI classification (always runs)
                    ai_class = predict_image(img_path)
                    # Use manual category if provided, otherwise AI class
                    final_category = manual_category if manual_category else ai_class
                    points = calculate_reward(final_category, quantity)
                    
                    conn = sqlite3.connect('ewaste.db')
                    c = conn.cursor()
                    c.execute('''INSERT INTO ewaste_requests
                                 (citizen_id, item_name, item_type, manual_category, quantity, image_path, 
                                  AI_classification, reward_points, status, request_date)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                              (st.session_state.user['user_id'], item_name, final_category, manual_category, quantity,
                               img_path, ai_class, points, 'pending', datetime.datetime.now()))
                    conn.commit()
                    conn.close()
                    
                    st.success(f"✅ Request submitted! Classified as **{final_category}** (AI: {ai_class})")
                    st.info(f"⏳ Status: Pending. You will receive {points} points after admin verification.")
                elif submitted and not image_file:
                    st.warning("⚠️ Please upload an image.")
    
    with tabs[1]:
        st.markdown("### Your Reward Points")
        points = get_user_rewards(st.session_state.user['user_id'])
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.metric("Total Points", points, delta=None, delta_color="normal")
    
    with tabs[2]:
        st.markdown("### Your Requests")
        requests = get_user_requests(st.session_state.user['user_id'])
        if requests:
            df = pd.DataFrame(requests, columns=["ID", "Item", "Qty", "AI Class", "Manual Cat", "Points", "Status", "Date", "Verified Date"])
            df["Date"] = pd.to_datetime(df["Date"]).dt.strftime('%Y-%m-%d %H:%M')
            df["Verified Date"] = df["Verified Date"].apply(lambda x: pd.to_datetime(x).strftime('%Y-%m-%d %H:%M') if x else "")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("📭 No requests found.")

def recycler_dashboard():
    st.markdown("## ♻️ Recycler Dashboard")
    tabs = st.tabs(["📋 Pending Requests", "📌 My Assigned", "✅ Mark Collected"])
    
    with tabs[0]:
        st.markdown("### Pending E-Waste Requests")
        pending = get_pending_requests()
        if pending:
            df = pd.DataFrame(pending, columns=["ID", "Citizen", "Item", "Qty", "AI Class", "Manual Cat", "Points", "Date"])
            df["Date"] = pd.to_datetime(df["Date"]).dt.strftime('%Y-%m-%d %H:%M')
            st.dataframe(df, use_container_width=True)
            
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                with st.form("accept_request"):
                    request_id = st.number_input("Enter Request ID to accept", min_value=1, step=1)
                    if st.form_submit_button("✅ Accept", use_container_width=True):
                        assign_request(request_id, st.session_state.user['user_id'])
                        st.success(f"Request {request_id} assigned to you.")
                        st.rerun()
        else:
            st.info("📭 No pending requests.")
    
    with tabs[1]:
        st.markdown("### My Assigned Requests")
        assigned = get_assigned_requests(st.session_state.user['user_id'])
        if assigned:
            df = pd.DataFrame(assigned, columns=["ID", "Item", "Qty", "Type", "Status", "Date"])
            df["Date"] = pd.to_datetime(df["Date"]).dt.strftime('%Y-%m-%d %H:%M')
            st.dataframe(df, use_container_width=True)
        else:
            st.info("📭 No assigned requests.")
    
    with tabs[2]:
        st.markdown("### Mark Request as Collected")
        assigned = get_assigned_requests(st.session_state.user['user_id'])
        if assigned:
            request_ids = [str(r[0]) for r in assigned]
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                with st.form("collect_request"):
                    request_id = st.selectbox("Select Request ID", request_ids)
                    if st.form_submit_button("📦 Mark Collected", use_container_width=True):
                        mark_collected(int(request_id))
                        st.success(f"Request {request_id} marked as collected. Awaiting admin verification.")
                        st.rerun()
        else:
            st.info("📭 No requests to mark collected.")

def admin_dashboard():
    st.markdown("## 🛡️ Admin Dashboard")
    tabs = st.tabs(["👥 Users", "📋 All Requests", "✅ Verification", "📊 Reports"])
    
    with tabs[0]:
        st.markdown("### All Users")
        users = get_all_users()
        if users:
            df = pd.DataFrame(users, columns=["ID", "Name", "Email", "Role", "Reward Points"])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No users.")
    
    with tabs[1]:
        st.markdown("### All E-Waste Requests")
        requests = get_all_requests()
        if requests:
            df = pd.DataFrame(requests, columns=["ID", "Citizen", "Item", "Qty", "AI Class", "Manual Cat", "Points", "Status", "Date", "Verified Date"])
            df["Date"] = pd.to_datetime(df["Date"]).dt.strftime('%Y-%m-%d %H:%M')
            df["Verified Date"] = df["Verified Date"].apply(lambda x: pd.to_datetime(x).strftime('%Y-%m-%d %H:%M') if x else "")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No requests.")
    
    with tabs[2]:
        st.markdown("### Verify Collected E-Waste")
        collected = get_collected_requests()
        if collected:
            df = pd.DataFrame(collected, columns=["ID", "Citizen", "Item", "Qty", "Type", "Points", "Date", "Recycler ID"])
            df["Date"] = pd.to_datetime(df["Date"]).dt.strftime('%Y-%m-%d %H:%M')
            st.dataframe(df, use_container_width=True)
            
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                with st.form("verify_request"):
                    request_id = st.number_input("Enter Request ID to verify", min_value=1, step=1)
                    if st.form_submit_button("✅ Verify & Grant Points", use_container_width=True):
                        if verify_request(request_id, st.session_state.user['user_id']):
                            st.success(f"Request {request_id} verified! Points awarded.")
                            st.rerun()
                        else:
                            st.error("Verification failed. Request may not be in 'collected' status.")
        else:
            st.info("📭 No requests awaiting verification.")
    
    with tabs[3]:
        st.markdown("### System Reports & ML Insights")
        
        # Basic stats
        total_users, total_requests, total_rewards, verified_requests = get_stats()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 Total Users", total_users)
        with col2:
            st.metric("📋 Total Requests", total_requests)
        with col3:
            st.metric("✅ Verified Requests", verified_requests)
        with col4:
            st.metric("🏆 Total Rewards", total_rewards)
        
        st.markdown("---")
        st.markdown("### 📊 E-Waste Analytics (ML Insights)")
        
        insights = get_ml_insights()
        
        if insights['total_items'] == 0:
            st.info("Not enough data for insights. Upload some e-waste first!")
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Items Recycled", insights['total_items'])
            with col2:
                st.metric("Predicted Next Month", insights['next_month_prediction'])
            with col3:
                st.metric("Est. Recoverable Value ($)", f"${insights['recoverable_value']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("CO₂ Saved (kg)", insights['co2_saved'])
            with col2:
                st.metric("Categories", len(insights['category_dist']))
            
            # Category distribution bar chart
            if insights['category_dist']:
                st.markdown("#### Items by Category")
                cat_df = pd.DataFrame.from_dict(insights['category_dist'], orient='index', columns=['Quantity'])
                st.bar_chart(cat_df)
            
            # Monthly trend line chart
            if insights['monthly_trend']:
                st.markdown("#### Monthly E-Waste Collection Trend")
                trend_df = pd.DataFrame.from_dict(insights['monthly_trend'], orient='index', columns=['Quantity'])
                st.line_chart(trend_df)
            
            # Additional ML insight: next month prediction note
            st.info(f"📈 Based on historical data, we predict **{insights['next_month_prediction']} items** next month. "
                    f"This uses a simple moving average model. Actual results may vary.")

if __name__ == "__main__":
    main()