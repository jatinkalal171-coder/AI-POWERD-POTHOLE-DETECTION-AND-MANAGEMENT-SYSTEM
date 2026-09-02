import os
import sys
import sqlite3

# Set workspace directory in path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from backend.config import DATABASE_PATH
from backend.database import init_db

def clear_fake_data():
    print(f"[INFO] Cleaning database at {DATABASE_PATH}...")
    if not os.path.exists(DATABASE_PATH):
        print("[INFO] Database does not exist yet. Initializing clean DB...")
        init_db()
        return

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Clear all pothole, complaint, detection, repair, notification, and audit records
    tables_to_clear = ['potholes', 'complaints', 'detections', 'repairs', 'notifications', 'audit_logs']
    for table in tables_to_clear:
        try:
            cursor.execute(f"DELETE FROM {table}")
            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
            print(f"  [CLEARED] Table '{table}' reset successfully.")
        except Exception as e:
            print(f"  [WARNING] Could not clear table '{table}': {e}")

    conn.commit()
    conn.close()

    print("[SUCCESS] Database wiped clean of all fake/demo data!")
    print("[INFO] Ensuring initial schemas & default system users exist...")
    init_db()
    print("[SUCCESS] Clean database initialized successfully.")

if __name__ == '__main__':
    clear_fake_data()
