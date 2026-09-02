from flask import Blueprint, jsonify, request
from backend.database import get_db
from backend.config import MUNICIPALITY_EMAIL, MODEL_PATH, CONFIDENCE_THRESHOLD
from backend.utils.auth_utils import optional_token

user_bp = Blueprint('users', __name__)

@user_bp.route('', methods=['GET'])
@optional_token
def get_users():
    current_user = getattr(request, 'current_user', {}) or {}
    user_role = current_user.get('role')

    if user_role and user_role not in ['Municipality Officer', 'Admin']:
        return jsonify({"error": "Access denied. User directory is restricted to Municipality Officers and Admins."}), 403

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role, created_at FROM users ORDER BY created_at DESC")
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"users": users, "count": len(users)})

@user_bp.route('/settings', methods=['GET'])
def get_settings():
    return jsonify({
        "municipality_email": MUNICIPALITY_EMAIL,
        "model_path": MODEL_PATH,
        "confidence_threshold": CONFIDENCE_THRESHOLD
    })
