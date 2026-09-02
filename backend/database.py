import sqlite3
import os
import datetime
from werkzeug.security import generate_password_hash
from backend.config import DATABASE_PATH

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('Admin', 'Municipality Officer', 'Field Officer', 'Citizen')),
        created_at TEXT NOT NULL
    )
    ''')

    # 2. Potholes Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS potholes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pothole_id TEXT UNIQUE NOT NULL,
        confidence REAL NOT NULL,
        width REAL NOT NULL,
        height REAL NOT NULL,
        area REAL NOT NULL,
        severity_score INTEGER NOT NULL,
        risk_level TEXT NOT NULL,
        priority_score INTEGER NOT NULL,
        road_name TEXT DEFAULT 'Main Highway Segment A',
        latitude REAL,
        longitude REAL,
        image_path TEXT,
        annotated_image_path TEXT,
        detected_at TEXT NOT NULL,
        last_detected_at TEXT NOT NULL,
        detection_count INTEGER DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'OPEN',
        road_importance TEXT DEFAULT 'MEDIUM',
        estimated_distance REAL
    )
    ''')

    # Migration for estimated_distance column if missing
    cursor.execute("PRAGMA table_info(potholes)")
    p_columns = [row[1] for row in cursor.fetchall()]
    if 'estimated_distance' not in p_columns:
        cursor.execute("ALTER TABLE potholes ADD COLUMN estimated_distance REAL")
    if 'user_id' not in p_columns:
        cursor.execute("ALTER TABLE potholes ADD COLUMN user_id INTEGER")

    # Migration for complaints table
    cursor.execute("PRAGMA table_info(complaints)")
    c_columns = [row[1] for row in cursor.fetchall()]
    if 'assigned_officer_id' not in c_columns:
        cursor.execute("ALTER TABLE complaints ADD COLUMN assigned_officer_id INTEGER")
    if 'assigned_officer_name' not in c_columns:
        cursor.execute("ALTER TABLE complaints ADD COLUMN assigned_officer_name TEXT")

    # Migration for repairs table
    cursor.execute("PRAGMA table_info(repairs)")
    r_columns = [row[1] for row in cursor.fetchall()]
    if 'complaint_id' not in r_columns:
        cursor.execute("ALTER TABLE repairs ADD COLUMN complaint_id TEXT")
    if 'repair_latitude' not in r_columns:
        cursor.execute("ALTER TABLE repairs ADD COLUMN repair_latitude REAL")
    if 'repair_longitude' not in r_columns:
        cursor.execute("ALTER TABLE repairs ADD COLUMN repair_longitude REAL")
    if 'gps_accuracy' not in r_columns:
        cursor.execute("ALTER TABLE repairs ADD COLUMN gps_accuracy REAL")
    if 'distance_from_pothole' not in r_columns:
        cursor.execute("ALTER TABLE repairs ADD COLUMN distance_from_pothole REAL")
    if 'capture_timestamp' not in r_columns:
        cursor.execute("ALTER TABLE repairs ADD COLUMN capture_timestamp TEXT")
    if 'gps_verification_status' not in r_columns:
        cursor.execute("ALTER TABLE repairs ADD COLUMN gps_verification_status TEXT")
    if 'scene_match_status' not in r_columns:
        cursor.execute("ALTER TABLE repairs ADD COLUMN scene_match_status TEXT")
    if 'scene_similarity_score' not in r_columns:
        cursor.execute("ALTER TABLE repairs ADD COLUMN scene_similarity_score REAL")
    if 'ai_repair_status' not in r_columns:
        cursor.execute("ALTER TABLE repairs ADD COLUMN ai_repair_status TEXT")
    if 'final_verification_status' not in r_columns:
        cursor.execute("ALTER TABLE repairs ADD COLUMN final_verification_status TEXT")

    # 3. Detections Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pothole_id TEXT NOT NULL,
        source_type TEXT NOT NULL,
        confidence REAL NOT NULL,
        bbox_json TEXT,
        image_path TEXT,
        detected_at TEXT NOT NULL,
        FOREIGN KEY(pothole_id) REFERENCES potholes(pothole_id)
    )
    ''')

    # 4. Complaints Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id TEXT UNIQUE NOT NULL,
        pothole_id TEXT,
        user_id INTEGER,
        user_name TEXT,
        user_email TEXT,
        description TEXT,
        location_name TEXT,
        latitude REAL,
        longitude REAL,
        image_path TEXT,
        status TEXT NOT NULL DEFAULT 'SUBMITTED',
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    ''')

    # 5. Repairs Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS repairs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repair_id TEXT UNIQUE NOT NULL,
        pothole_id TEXT NOT NULL,
        assigned_officer_id INTEGER,
        assigned_officer_name TEXT,
        department TEXT DEFAULT 'Road Maintenance',
        deadline TEXT,
        assigned_date TEXT NOT NULL,
        repair_date TEXT,
        repair_status TEXT NOT NULL DEFAULT 'ASSIGNED',
        before_image_path TEXT,
        after_image_path TEXT,
        verification_result TEXT DEFAULT 'PENDING',
        verification_notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(pothole_id) REFERENCES potholes(pothole_id),
        FOREIGN KEY(assigned_officer_id) REFERENCES users(id)
    )
    ''')

    # 6. Notifications Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'ALERT',
        read_status INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    ''')

    # 7. Audit Logs Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        user_name TEXT NOT NULL,
        action TEXT NOT NULL,
        pothole_id TEXT,
        details TEXT,
        timestamp TEXT NOT NULL
    )
    ''')

    conn.commit()
    seed_initial_data(conn)
    conn.close()
    print("[INFO] Database initialized successfully.")

def seed_initial_data(conn):
    cursor = conn.cursor()
    
    # Check if admin user exists
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if user_count == 0:
        seed_users = [
            ("System Admin", "admin@city.gov", generate_password_hash("admin123"), "Admin"),
            ("Officer Sarah Jenkins", "officer@city.gov", generate_password_hash("officer123"), "Municipality Officer"),
            ("Field Officer 07", "field07@city.gov", generate_password_hash("field123"), "Field Officer"),
            ("John Citizen", "citizen@gmail.com", generate_password_hash("citizen123"), "Citizen")
        ]
        for name, email, pwd, role in seed_users:
            cursor.execute('''
            INSERT INTO users (name, email, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (name, email, pwd, role, now))
        print("[INFO] Default users seeded successfully.")

    conn.commit()

if __name__ == "__main__":
    init_db()
