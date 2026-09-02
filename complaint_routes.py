import os
import datetime
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from backend.database import get_db
from backend.ai.detector import get_detector
from backend.services.priority_service import calculate_priority_score
from backend.config import UPLOADS_DIR, COMPLAINTS_DIR

from backend.utils.auth_utils import optional_token, token_required, roles_required

complaint_bp = Blueprint('complaints', __name__)

@complaint_bp.route('', methods=['POST'])
@optional_token
def submit_complaint():
    if 'image' not in request.files:
        return jsonify({"error": "Pothole photo image is required"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "No image file selected"}), 400

    description = request.form.get('description', 'Citizen Pothole Complaint')
    location_name = request.form.get('location_name', 'Unknown Location')
    
    current_user = getattr(request, 'current_user', {}) or {}
    user_id = current_user.get('user_id')
    user_name = request.form.get('user_name') or current_user.get('name') or 'Citizen Reporter'
    user_email = request.form.get('user_email') or current_user.get('email') or 'citizen@gmail.com'
    
    lat_val = request.form.get('latitude')
    lng_val = request.form.get('longitude')
    if not lat_val or not lng_val:
        return jsonify({"error": "Location coordinates are required. Please use 'USE MY CURRENT LOCATION' or click on the map."}), 400
    
    try:
        lat = float(lat_val)
        lng = float(lng_val)
    except ValueError:
        return jsonify({"error": "Invalid location coordinates provided."}), 400

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"complaint_{stamp}_{secure_filename(file.filename)}"
    raw_path = os.path.join(COMPLAINTS_DIR, filename)
    file.save(raw_path)

    # Automatic AI Analysis of uploaded complaint photo
    detector = get_detector()
    result = detector.detect_image_file(raw_path, save_annotated=True)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM complaints")
    next_cmp = cursor.fetchone()[0] + 1
    # Unified Complaint ID: PTH-XXXX (Matches pothole_id 1:1)
    cmp_id = f"PTH-2026-{next_cmp:04d}"
    pothole_id = cmp_id

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    severity_score = 0
    risk_level = "LOW"

    rel_ann_path = None
    if result['annotated_image_path']:
        rel_ann_path = os.path.relpath(result['annotated_image_path'], UPLOADS_DIR).replace('\\', '/')
    rel_comp_img = os.path.relpath(raw_path, UPLOADS_DIR).replace('\\', '/')

    if result['total_potholes'] > 0:
        det = result['detections'][0]
        severity_score = det['severity_score']
        risk_level = det['risk_level']

        prio_res = calculate_priority_score(
            severity_score=det['severity_score'],
            risk_level=det['risk_level'],
            road_importance="MEDIUM"
        )

        cursor.execute('''
        INSERT INTO potholes (
            pothole_id, confidence, width, height, area, severity_score, 
            risk_level, priority_score, road_name, latitude, longitude, 
            image_path, annotated_image_path, detected_at, last_detected_at, 
            detection_count, status, road_importance, user_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'SUBMITTED', 'MEDIUM', ?)
        ''', (
            pothole_id, det['confidence'], det['width'], det['height'], det['area'],
            det['severity_score'], det['risk_level'], prio_res['priority_score'],
            location_name, lat, lng,
            rel_comp_img, rel_ann_path or rel_comp_img, now_str, now_str, user_id
        ))
    else:
        # Save pothole record with default AI parameters if no boxes detected
        cursor.execute('''
        INSERT INTO potholes (
            pothole_id, confidence, width, height, area, severity_score, 
            risk_level, priority_score, road_name, latitude, longitude, 
            image_path, annotated_image_path, detected_at, last_detected_at, 
            detection_count, status, road_importance, user_id
        ) VALUES (?, 60.0, 100, 100, 10000, 45, 'MEDIUM', 50, ?, ?, ?, ?, ?, ?, ?, 1, 'SUBMITTED', 'MEDIUM', ?)
        ''', (
            pothole_id, location_name, lat, lng, rel_comp_img, rel_comp_img, now_str, now_str, user_id
        ))

    cursor.execute('''
    INSERT INTO complaints (
        complaint_id, pothole_id, user_id, user_name, user_email, description, 
        location_name, latitude, longitude, image_path, status, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SUBMITTED', ?)
    ''', (cmp_id, pothole_id, user_id, user_name, user_email, description, location_name, lat, lng, rel_comp_img, now_str))

    # Auto-create repair record so complaint ID is immediately available for Repair Verification
    cursor.execute("SELECT COUNT(*) FROM repairs")
    next_rep = cursor.fetchone()[0] + 1
    rep_id = f"REP-2026-{next_rep:04d}"

    cursor.execute('''
    INSERT INTO repairs (
        repair_id, pothole_id, complaint_id, assigned_officer_id, assigned_officer_name,
        department, assigned_date, repair_status, before_image_path, created_at
    ) VALUES (?, ?, ?, 3, 'Field Officer 07', 'Municipal Road Maintenance Dept', ?, 'ASSIGNED', ?, ?)
    ''', (rep_id, pothole_id, cmp_id, now_str, rel_comp_img, now_str))

    cursor.execute('''
    INSERT INTO notifications (user_id, title, message, type, read_status, created_at)
    VALUES (2, '📥 New Citizen Complaint Submitted', ?, 'ALERT', 0, ?)
    ''', (f"Complaint {cmp_id} submitted for {location_name}", now_str))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "complaint_id": cmp_id,
        "pothole_id": pothole_id,
        "risk_level": risk_level,
        "severity_score": severity_score,
        "status": "SUBMITTED",
        "message": "Complaint submitted and AI verified successfully!"
    }), 201

@complaint_bp.route('', methods=['GET'])
@optional_token
def get_complaints():
    current_user = getattr(request, 'current_user', {}) or {}
    user_role = current_user.get('role')
    user_id = current_user.get('user_id')
    user_email = current_user.get('email')

    conn = get_db()
    cursor = conn.cursor()

    if user_role == 'Citizen' and user_email:
        cursor.execute("SELECT * FROM complaints WHERE user_email = ? OR user_id = ? ORDER BY created_at DESC", (user_email, user_id))
    elif user_role == 'Field Officer' and user_id:
        cursor.execute("SELECT * FROM complaints WHERE assigned_officer_id = ? ORDER BY created_at DESC", (user_id,))
    else:
        cursor.execute("SELECT * FROM complaints ORDER BY created_at DESC")

    complaints = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"complaints": complaints, "count": len(complaints)})
