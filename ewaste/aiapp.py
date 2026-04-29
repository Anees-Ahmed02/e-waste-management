import streamlit as st
import sqlite3
import hashlib
import datetime
import pandas as pd
import os
os.makedirs("uploads", exist_ok=True)
import numpy as np
import random
from datetime import timedelta
from PIL import Image
from blockchain import Blockchain

# ----------------------------
# Page Configuration & Custom CSS
# ----------------------------
st.set_page_config(
    page_title="AI E-Waste Management",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="auto"
)

# Custom CSS for modern UI
st.markdown("""
<style>

/* 🌟 Sidebar Background */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1f1c2c, #928dab);
    color: white;
    padding: 20px;
}

/* 🧭 Sidebar Title */
section[data-testid="stSidebar"] h2 {
    text-align: center;
    font-size: 22px;
    font-weight: bold;
    margin-bottom: 20px;
    color: #ffffff;
}

/* 🎯 Radio Buttons (Login/Register) */
div[role="radiogroup"] > label {
    background: rgba(255,255,255,0.1);
    padding: 10px;
    margin-bottom: 8px;
    border-radius: 10px;
    transition: 0.3s;
    cursor: pointer;
}

/* Hover Effect */
div[role="radiogroup"] > label:hover {
    background: linear-gradient(90deg, #ff00cc, #3333ff);
    transform: scale(1.03);
}

/* Selected Option */
div[role="radiogroup"] input:checked + div {
    background: linear-gradient(90deg, #8e2de2, #4a00e0);
    color: white;
    border-radius: 10px;
}

/* Remove white box */
div.stRadio > div {
    background: transparent;
}

/* Optional decorative box fix */
.css-1r6slb0 {
    background: rgba(255,255,255,0.08);
    border-radius: 15px;
}

/* Hide extra small text */
small {
    display: none !important;
}
div[data-testid="stForm"] small {
    display: none;
}

div[data-testid="InputInstructions"] {
    display: none;
}

</style>
""", unsafe_allow_html=True)

# ----------------------------
# Database Setup with Auto-Upgrade
# ----------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def calculate_reward(item_type, quantity):
    points_map = {
        'Mobile': 50,
        'Laptop': 100,
        'Battery': 30,
        'Other': 20
    }
    return points_map.get(item_type, 20) * quantity

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

    # E-waste requests table
    c.execute('''CREATE TABLE IF NOT EXISTS ewaste_requests
                 (request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  citizen_id INTEGER NOT NULL,
                  item_name TEXT NOT NULL,
                  item_type TEXT,                -- AI classification
                  manual_category TEXT,           -- user-selected category
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
    """Insert default users and rich sample requests for ML insights."""
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()
    
    # Check if users table is empty
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        # Default users (password = 'password' hashed)
        default_users = [
            ('Citizen User', 'citizen@example.com', hash_password('password'), 'citizen', 0),
            ('Second Citizen', 'citizen2@example.com', hash_password('password'), 'citizen', 0),
            ('Recycler User', 'recycler@example.com', hash_password('password'), 'recycler', 0),
            ('Admin User', 'nishanthi2604@gmail.com', hash_password('123123'), 'admin', 0)
        ]
        for user in default_users:
            c.execute('''INSERT INTO users (name, email, password, role, reward_points)
                         VALUES (?, ?, ?, ?, ?)''', user)
        
        # Get citizen ids
        c.execute("SELECT user_id FROM users WHERE email='citizen@example.com'")
        citizen1 = c.fetchone()[0]
        c.execute("SELECT user_id FROM users WHERE email='citizen2@example.com'")
        citizen2 = c.fetchone()[0]
        
        # Categories and possible quantities
        categories = ['Mobile', 'Laptop', 'Battery', 'Other']
        now = datetime.datetime.now()
        
        # Generate 30 sample requests over the last 6 months
        sample_requests = []
        citizen_ids = [citizen1, citizen2]
        
        for i in range(30):
            citizen = random.choice(citizen_ids)
            item_name = f"Sample {categories[i % 4]} #{i+1}"
            ai_class = categories[i % 4]
            manual = random.choice([ai_class, ''])  # sometimes blank, sometimes set
            quantity = random.randint(1, 5)
            points = calculate_reward(ai_class, quantity)
            
            # Random date within last 180 days
            days_ago = random.randint(0, 180)
            request_date = now - timedelta(days=days_ago)
            
            # 80% are verified, rest pending/assigned/collected
            if random.random() < 0.8:
                status = 'verified'
                verified_date = request_date + timedelta(days=random.randint(1, 10))
            else:
                status = random.choice(['pending', 'assigned', 'collected'])
                verified_date = None
            
            sample_requests.append((
                citizen, item_name, ai_class, manual, quantity,
                '', ai_class, points, status, request_date, verified_date
            ))
        
        for req in sample_requests:
            c.execute('''INSERT INTO ewaste_requests
                         (citizen_id, item_name, item_type, manual_category, quantity, image_path,
                          AI_classification, reward_points, status, request_date, verified_date)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', req)
        
        # Update reward points for citizens based on verified requests
        for cid in citizen_ids:
            c.execute('''UPDATE users SET reward_points = 
                         (SELECT COALESCE(SUM(reward_points), 0) FROM ewaste_requests 
                          WHERE citizen_id=? AND status='verified')
                         WHERE user_id=?''', (cid, cid))
        
        conn.commit()
    
    conn.close()

# Initialize/upgrade database
create_tables()
add_default_records()

# Ensure upload directory exists
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ----------------------------
# Blockchain setup (cached)
# ----------------------------
@st.cache_resource
def get_blockchain():
    return Blockchain()

# ----------------------------
# Helper Functions (database operations)
# ----------------------------
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
    if c.rowcount > 0:
        conn.commit()
        # Blockchain record
        blockchain = get_blockchain()
        block_data = {
            "action": "request_assigned",
            "request_id": request_id,
            "recycler_id": recycler_id,
            "timestamp": str(datetime.datetime.now())
        }
        blockchain.add_block(block_data)
    conn.close()

def mark_collected(request_id):
    conn = sqlite3.connect('ewaste.db')
    c = conn.cursor()
    c.execute("UPDATE ewaste_requests SET status='collected' WHERE request_id=? AND status='assigned'", (request_id,))
    if c.rowcount > 0:
        conn.commit()
        blockchain = get_blockchain()
        block_data = {
            "action": "request_collected",
            "request_id": request_id,
            "timestamp": str(datetime.datetime.now())
        }
        blockchain.add_block(block_data)
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
        # Blockchain record
        blockchain = get_blockchain()
        block_data = {
            "action": "request_verified",
            "request_id": request_id,
            "admin_id": admin_id,
            "points_awarded": points,
            "timestamp": str(datetime.datetime.now())
        }
        blockchain.add_block(block_data)
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
# AI Simulation (image classification)
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
        return random.choice(['Mobile', 'Laptop', 'Battery', 'Other'])

# ----------------------------
# ML Insights for Admin Reports
# ----------------------------
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
    
    # Simple prediction for next month (average of last 3 months)
    if len(monthly) >= 3:
        last_3 = list(monthly.values)[-3:]
        next_pred = int(np.mean(last_3))
    elif len(monthly) > 0:
        next_pred = int(np.mean(list(monthly.values)))
    else:
        next_pred = 0
    
    # Simulated recoverable value ($ per item)
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
# UI Functions with Centering Decorator
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
            st.markdown("""
<h2 style='text-align:center; 
background: linear-gradient(90deg, #ff00cc, #3333ff);
-webkit-background-clip: text;
-webkit-text-fill-color: transparent;'>
Main Menu
</h2>
""", unsafe_allow_html=True)
            menu = st.radio("", [" Login", " Register"], index=0, label_visibility="collapsed")
            if menu == " Login":
                show_login()
            else:
                show_register()
    else:
        with st.sidebar:
            user = st.session_state.user
            st.markdown(f"##  Welcome, **{user['name']}**")
            st.markdown(f"**Role:** {user['role'].capitalize()}")
            st.markdown("---")
            if st.button(" Logout", use_container_width=True):
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
    st.markdown("###  Login")

    email = st.text_input("📧 Email")
    password = st.text_input("🔒 Password", type="password")

    role = st.selectbox("👤 Role", ["citizen", "recycler", "admin"])

    if st.button(" Login", use_container_width=True):

        # ✅ FIXED ADMIN LOGIN (works always)
        if role == "admin":
            if email == "nishanthi2604@gmail.com" and password == "123123":
                st.session_state.logged_in = True
                st.session_state.user = {
                    "user_id": 0,
                    "name": "Admin",
                    "role": "admin"
                }
                st.success("✅ Admin Login Successful")
                st.rerun()
            else:
                st.error("❌ Invalid Admin credentials")
            return  # 🚨 important (stop further checking)

        # 👤 Normal user login
        user = login_user(email, password, role)
        if user:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.success(f"✅ Welcome, {user['name']}!")
            st.rerun()
        else:
            st.error("❌ Invalid credentials or role")

@center_form
def show_register():
    st.markdown("###  Register New Account")

    name = st.text_input("👤 Full Name", placeholder="Enter your full name")
    email = st.text_input("📧 Email", placeholder="Enter your email")
    password = st.text_input("🔒 Password", type="password", placeholder="Choose a password")
    role = st.selectbox("👤 Role", ["citizen", "recycler"])

    if st.button("✅ Register", use_container_width=True):
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
                    
                    ai_class = predict_image(img_path)
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
                    request_id = c.lastrowid  # get the new request ID
                    conn.commit()
                    conn.close()

                    # Blockchain record
                    blockchain = get_blockchain()
                    block_data = {
                        "action": "request_created",
                        "request_id": request_id,
                        "citizen_id": st.session_state.user['user_id'],
                        "item_name": item_name,
                        "category": final_category,
                        "quantity": quantity,
                        "points": points,
                        "timestamp": str(datetime.datetime.now())
                    }
                    blockchain.add_block(block_data)
                    
                    st.success(f" Request submitted! Classified as **{final_category}** (AI: {ai_class})")
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
            if "Verified Date" in df.columns:
                df["Verified Date"] = pd.to_datetime(df["Verified Date"], errors='coerce')
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
    # Added "🔗 Blockchain" tab
    tabs = st.tabs(["👥 Users", "📋 All Requests", "✅ Verification", "📊 Reports", "🔗 Blockchain"])
    
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
            df["Verified Date"] = pd.to_datetime(df["Verified Date"], errors='coerce')
            df["Verified Date"] = df["Verified Date"].dt.strftime('%Y-%m-%d %H:%M')
            df["Verified Date"] = df["Verified Date"].fillna("")
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
            
            # Next month prediction note
            st.info(f"📈 Based on historical data, we predict **{insights['next_month_prediction']} items** next month. "
                    f"This uses a simple moving average model. Actual results may vary.")
    
    # New Blockchain Explorer Tab (with safe timestamp handling)
    with tabs[4]:
        st.markdown("### 🔗 Blockchain Explorer")
        blockchain = get_blockchain()
        
        # Check chain validity
        if blockchain.is_chain_valid():
            st.success("✅ Blockchain integrity verified.")
        else:
            st.error("❌ Blockchain is corrupted!")
        
        # Display blocks
        blocks = blockchain.get_chain_data()
        for block in reversed(blocks):  # show newest first
            # Safely format timestamp
            ts = block['timestamp']
            if isinstance(ts, datetime.datetime):
                ts_str = ts.strftime('%Y-%m-%d %H:%M:%S')
            else:
                ts_str = str(ts)[:19]  # slice string to YYYY-MM-DD HH:MM:SS
            with st.expander(f"Block #{block['block_index']} - {ts_str}"):
                st.json(block)

if __name__ == "__main__":
    main()