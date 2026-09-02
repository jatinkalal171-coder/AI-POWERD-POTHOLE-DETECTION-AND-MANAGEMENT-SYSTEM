from flask import Blueprint, request, jsonify
from backend.database import get_db
from backend.utils.auth_utils import hash_password, verify_password, generate_token, token_required
import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, password_hash, role FROM users WHERE LOWER(email) = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user or not verify_password(password, user['password_hash']):
        return jsonify({"error": "Invalid email or password"}), 401

    token = generate_token(user['id'], user['email'], user['role'], user['name'])

    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": {
            "id": user['id'],
            "name": user['name'],
            "email": user['email'],
            "role": user['role']
        }
    })

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'Citizen')

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required"}), 400

    if role not in ['Admin', 'Municipality Officer', 'Field Officer', 'Citizen']:
        role = 'Citizen'

    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"error": "Email is already registered"}), 400

    pwd_hash = hash_password(password)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
    INSERT INTO users (name, email, password_hash, role, created_at)
    VALUES (?, ?, ?, ?, ?)
    ''', (name, email, pwd_hash, role, now))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    token = generate_token(user_id, email, role, name)

    return jsonify({
        "message": "User registered successfully",
        "token": token,
        "user": {
            "id": user_id,
            "name": name,
            "email": email,
            "role": role
        }
    }), 201

@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user():
    return jsonify({"user": request.current_user})
