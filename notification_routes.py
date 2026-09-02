from flask import Blueprint, jsonify, request
from backend.database import get_db

notification_bp = Blueprint('notifications', __name__)

@notification_bp.route('', methods=['GET'])
def get_notifications():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications ORDER BY created_at DESC LIMIT 50")
    notifications = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"notifications": notifications, "count": len(notifications)})

@notification_bp.route('/<int:notif_id>/read', methods=['PUT'])
def mark_read(notif_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET read_status = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Notification marked as read"})

@notification_bp.route('/read_all', methods=['PUT'])
def mark_all_read():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET read_status = 1")
    conn.commit()
    conn.close()
    return jsonify({"message": "All notifications marked as read"})
