import os
import datetime
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from backend.database import get_db
from backend.ai.detector import get_detector
from backend.config import UPLOADS_DIR, REPAIRS_DIR

from backend.utils.auth_utils import optional_token, token_required, roles_required

repair_bp = Blueprint('repairs', __name__)

@repair_bp.route('', methods=['GET'])
@optional_token
def get_repairs():
    current_user = getattr(request, 'current_user', {}) or {}
    user_role = current_user.get('role')
    user_id = current_user.get('user_id')

    conn = get_db()
    cursor = conn.cursor()

    if user_role == 'Field Officer' and user_id:
        cursor.execute('''
        SELECT r.*, p.priority_score, p.risk_level, p.road_name, p.severity_score
        FROM repairs r
        JOIN potholes p ON r.pothole_id = p.pothole_id
        WHERE r.assigned_officer_id = ? OR r.assigned_officer_id IS NULL OR r.assigned_officer_id = 3
        ORDER BY r.created_at DESC
        ''', (user_id,))
    elif user_role == 'Citizen' and user_id:
        cursor.execute('''
        SELECT r.*, p.priority_score, p.risk_level, p.road_name, p.severity_score
        FROM repairs r
        JOIN potholes p ON r.pothole_id = p.pothole_id
        LEFT JOIN complaints c ON r.complaint_id = c.complaint_id OR r.pothole_id = c.pothole_id
        WHERE c.user_id = ? OR p.user_id = ?
        ORDER BY r.created_at DESC
        ''', (user_id, user_id))
    else:
        cursor.execute('''
        SELECT r.*, p.priority_score, p.risk_level, p.road_name, p.severity_score
        FROM repairs r
        JOIN potholes p ON r.pothole_id = p.pothole_id
        ORDER BY r.created_at DESC
        ''')

    repairs = [dict(row) for row in cursor.fetchall()]

    # If no repairs returned yet, fallback to all repairs
    if not repairs:
        cursor.execute('''
        SELECT r.*, p.priority_score, p.risk_level, p.road_name, p.severity_score
        FROM repairs r
        JOIN potholes p ON r.pothole_id = p.pothole_id
        ORDER BY r.created_at DESC
        ''')
        repairs = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify({"repairs": repairs, "count": len(repairs)})

@repair_bp.route('', methods=['POST'])
@optional_token
def assign_repair():
    current_user = getattr(request, 'current_user', {}) or {}
    user_role = current_user.get('role')

    # Security Check: Only Municipality Officer or Admin can assign repairs
    if user_role and user_role not in ['Municipality Officer', 'Admin']:
        return jsonify({"error": "Access denied. Only Municipality Officers can assign field repair work orders."}), 403

    data = request.get_json() or {}
    pothole_id = data.get('pothole_id')
    assigned_officer_id = data.get('assigned_officer_id', 3)
    assigned_officer_name = data.get('assigned_officer_name', 'Field Officer 07')
    department = data.get('department', 'Road Maintenance Dept')
    deadline = data.get('deadline')

    if not pothole_id:
        return jsonify({"error": "Pothole ID is required"}), 400

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT image_path FROM potholes WHERE pothole_id = ?", (pothole_id,))
    pothole = cursor.fetchone()
    if not pothole:
        conn.close()
        return jsonify({"error": "Pothole not found"}), 404

    cursor.execute("SELECT COUNT(*) FROM repairs")
    next_rep = cursor.fetchone()[0] + 1
    rep_id = f"REP-2026-{next_rep:04d}"

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
    INSERT INTO repairs (
        repair_id, pothole_id, complaint_id, assigned_officer_id, assigned_officer_name, 
        department, deadline, assigned_date, repair_status, before_image_path, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ASSIGNED', ?, ?)
    ''', (rep_id, pothole_id, pothole_id, assigned_officer_id, assigned_officer_name, department, deadline, now_str, pothole['image_path'], now_str))

    # Sync status to ASSIGNED in potholes and complaints table
    cursor.execute("UPDATE potholes SET status = 'ASSIGNED' WHERE pothole_id = ?", (pothole_id,))
    cursor.execute('''
    UPDATE complaints 
    SET status = 'ASSIGNED', assigned_officer_id = ?, assigned_officer_name = ? 
    WHERE pothole_id = ? OR complaint_id = ?
    ''', (assigned_officer_id, assigned_officer_name, pothole_id, pothole_id))

    # Create notification for field officer
    cursor.execute('''
    INSERT INTO notifications (user_id, title, message, type, read_status, created_at)
    VALUES (?, '🛠️ New Repair Work Order Assigned', ?, 'ASSIGNMENT', 0, ?)
    ''', (assigned_officer_id, f"Work Order {rep_id} assigned for Pothole {pothole_id}. Deadline: {deadline}", now_str))

    # Audit log
    cursor.execute('''
    INSERT INTO audit_logs (user_id, user_name, action, pothole_id, details, timestamp)
    VALUES (2, 'Municipality Officer', 'Repair Work Order Assigned', ?, ?, ?)
    ''', (pothole_id, f"Assigned to {assigned_officer_name} under {rep_id}", now_str))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Repair assigned successfully",
        "repair_id": rep_id,
        "pothole_id": pothole_id,
        "assigned_officer": assigned_officer_name,
        "deadline": deadline
    }), 201

from backend.services.verification_service import perform_multi_factor_verification

@repair_bp.route('/<repair_id>/status', methods=['PUT'])
@optional_token
def update_repair_status(repair_id):
    current_user = getattr(request, 'current_user', {}) or {}
    user_role = current_user.get('role')

    if user_role and user_role not in ['Field Officer', 'Municipality Officer', 'Admin']:
        return jsonify({"error": "Access denied. Only Field Officers and Municipality Officers can update repair status."}), 403

    data = request.get_json() or {}
    new_status = (data.get('status') or 'UNDER_REPAIR').upper()

    # Anti-Fraud Security Rule 12: Block direct status change to RESOLVED/CLOSED without multi-factor verification
    if new_status in ['RESOLVED', 'CLOSED', 'VERIFIED_CLOSED'] and user_role != 'Admin':
        return jsonify({
            "error": "Security Error: Direct status change to RESOLVED is blocked. Repair submissions must go through Multi-Factor Verification."
        }), 400

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM repairs WHERE repair_id = ?", (repair_id,))
    repair = cursor.fetchone()
    if not repair:
        conn.close()
        return jsonify({"error": "Repair order not found"}), 404

    pothole_id = repair['pothole_id']
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("UPDATE repairs SET repair_status = ? WHERE repair_id = ?", (new_status, repair_id))
    cursor.execute("UPDATE potholes SET status = ? WHERE pothole_id = ?", (new_status, pothole_id))
    cursor.execute("UPDATE complaints SET status = ? WHERE pothole_id = ? OR complaint_id = ?", (new_status, pothole_id, pothole_id))

    conn.commit()
    conn.close()

    return jsonify({"message": f"Work order {repair_id} updated to {new_status}"})

@repair_bp.route('/<repair_id>/verify', methods=['POST'])
@optional_token
def verify_repair(repair_id):
    current_user = getattr(request, 'current_user', {}) or {}
    user_role = current_user.get('role')

    if user_role and user_role not in ['Field Officer', 'Municipality Officer', 'Admin']:
        return jsonify({"error": "Access denied. Only Field Officers or Officers can submit repair verifications."}), 403

    if 'after_image' not in request.files:
        return jsonify({"error": "Captured repair photo (after_image) is required"}), 400

    file = request.files['after_image']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Officer GPS Telemetry
    lat_val = request.form.get('latitude')
    lng_val = request.form.get('longitude')
    acc_val = request.form.get('accuracy')

    officer_lat = float(lat_val) if lat_val is not None and lat_val != '' else None
    officer_lng = float(lng_val) if lng_val is not None and lng_val != '' else None
    officer_acc = float(acc_val) if acc_val is not None and acc_val != '' else None

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"repair_proof_{stamp}_{secure_filename(file.filename)}"
    raw_path = os.path.join(REPAIRS_DIR, filename)
    file.save(raw_path)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM repairs WHERE repair_id = ?", (repair_id,))
    repair = cursor.fetchone()
    if not repair:
        conn.close()
        return jsonify({"error": "Repair order not found"}), 404

    pothole_id = repair['pothole_id']

    # Fetch Original Pothole Details & BEFORE image
    cursor.execute("SELECT latitude, longitude, image_path, annotated_image_path FROM potholes WHERE pothole_id = ?", (pothole_id,))
    pothole = cursor.fetchone()

    orig_lat = pothole['latitude'] if pothole else None
    orig_lng = pothole['longitude'] if pothole else None

    before_rel_path = pothole['image_path'] or pothole['annotated_image_path'] if pothole else repair['before_image_path']
    before_abs_path = os.path.join(UPLOADS_DIR, before_rel_path.replace('/', os.sep)) if before_rel_path else None

    # 1. AI Model Inference on Repair Proof Image
    detector = get_detector()
    result = detector.detect_image_file(raw_path, save_annotated=True)
    ai_detected_potholes = result['total_potholes']

    rel_after = os.path.relpath(raw_path, UPLOADS_DIR).replace('\\', '/')

    # 2. Multi-Factor Verification Engine Evaluation
    eval_res = perform_multi_factor_verification(
        orig_lat=orig_lat,
        orig_lng=orig_lng,
        officer_lat=officer_lat,
        officer_lng=officer_lng,
        officer_accuracy=officer_acc,
        before_img_path=before_abs_path,
        after_img_path=raw_path,
        ai_detected_potholes=ai_detected_potholes
    )

    final_verification = eval_res['final_status']
    pothole_status = eval_res['pothole_status']
    reason = eval_res['reason']
    capture_time = eval_res['capture_timestamp']
    dist_m = eval_res['distance_meters']

    # Update Database Record
    cursor.execute('''
    UPDATE repairs 
    SET after_image_path = ?, verification_result = ?, repair_status = ?, repair_date = ?, verification_notes = ?,
        repair_latitude = ?, repair_longitude = ?, gps_accuracy = ?, distance_from_pothole = ?, capture_timestamp = ?,
        gps_verification_status = ?, scene_match_status = ?, scene_similarity_score = ?, ai_repair_status = ?, final_verification_status = ?
    WHERE repair_id = ?
    ''', (
        rel_after, final_verification, pothole_status, capture_time, reason,
        officer_lat, officer_lng, officer_acc, dist_m, capture_time,
        eval_res['gps_status'], eval_res['scene_status'], eval_res['scene_score'], eval_res['ai_status'], final_verification,
        repair_id
    ))

    cursor.execute("UPDATE potholes SET status = ? WHERE pothole_id = ?", (pothole_status, pothole_id))
    cursor.execute("UPDATE complaints SET status = ? WHERE pothole_id = ? OR complaint_id = ?", (pothole_status, pothole_id, pothole_id))

    # Notification & Audit Log
    n_title = "✅ Repair Multi-Factor Verified & Resolved" if final_verification == 'VERIFIED' else f"⚠️ Repair Verification: {final_verification}"
    cursor.execute('''
    INSERT INTO notifications (user_id, title, message, type, read_status, created_at)
    VALUES (2, ?, ?, ?, 0, ?)
    ''', (n_title, reason, 'VERIFICATION' if final_verification == 'VERIFIED' else 'CRITICAL', capture_time))

    cursor.execute('''
    INSERT INTO audit_logs (user_id, user_name, action, pothole_id, details, timestamp)
    VALUES (?, ?, 'Multi-Factor Repair Verification', ?, ?, ?)
    ''', (current_user.get('user_id', 3), current_user.get('name', 'Field Officer'), pothole_id, f"Status: {final_verification} | {reason}", capture_time))

    conn.commit()
    conn.close()

    return jsonify({
        "success": final_verification == "VERIFIED",
        "final_verification_status": final_verification,
        "pothole_status": pothole_status,
        "message": reason,
        "telemetry": {
            "complaint_id": pothole_id,
            "original_location": {"latitude": orig_lat, "longitude": orig_lng},
            "officer_location": {"latitude": officer_lat, "longitude": officer_lng, "accuracy": officer_acc},
            "distance_meters": dist_m,
            "capture_timestamp": capture_time,
            "gps_status": eval_res['gps_status'],
            "gps_reason": eval_res['gps_reason'],
            "scene_status": eval_res['scene_status'],
            "scene_score": eval_res['scene_score'],
            "scene_reason": eval_res['scene_reason'],
            "ai_status": eval_res['ai_status'],
            "ai_reason": eval_res['ai_reason'],
            "potholes_detected_in_proof": ai_detected_potholes
        }
    })
