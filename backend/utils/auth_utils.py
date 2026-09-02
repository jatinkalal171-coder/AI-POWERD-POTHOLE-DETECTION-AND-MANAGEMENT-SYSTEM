import datetime
import json
import base64
import hmac
import hashlib
from functools import wraps
from flask import request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from backend.config import SECRET_KEY, JWT_EXPIRATION_HOURS

try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False

def hash_password(password):
    return generate_password_hash(password)

def verify_password(password, password_hash):
    return check_password_hash(password_hash, password)

def generate_token(user_id, email, role, name):
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "name": name,
        "exp": (datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRATION_HOURS)).timestamp()
    }

    if HAS_JWT:
        return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    
    # Custom HMAC-SHA256 Token fallback
    data_str = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(SECRET_KEY.encode(), data_str.encode(), hashlib.sha256).hexdigest()
    return f"{data_str}.{sig}"

def decode_token(token):
    if not token:
        return None

    if HAS_JWT:
        try:
            return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except Exception:
            return None

    # Custom decode fallback
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        data_str, sig = parts[0], parts[1]
        expected_sig = hmac.new(SECRET_KEY.encode(), data_str.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(data_str.encode()).decode())
        if datetime.datetime.utcnow().timestamp() > payload.get("exp", 0):
            return None
        return payload
    except Exception:
        return None

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"error": "Authorization token is missing"}), 401

        user_data = decode_token(token)
        if not user_data:
            return jsonify({"error": "Token is invalid or expired"}), 401

        request.current_user = user_data
        return f(*args, **kwargs)
    return decorated

def optional_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        request.current_user = decode_token(token) if token else None
        return f(*args, **kwargs)
    return decorated

def roles_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        @token_required
        def decorated(*args, **kwargs):
            user_role = getattr(request, 'current_user', {}).get('role')
            if user_role not in allowed_roles:
                return jsonify({"error": f"Access denied. Requires one of roles: {list(allowed_roles)}"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
