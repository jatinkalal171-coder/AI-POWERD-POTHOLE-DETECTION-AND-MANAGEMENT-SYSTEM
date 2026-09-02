import os
import cv2
import time
import datetime
from flask import Blueprint, request, jsonify, Response, url_for
from werkzeug.utils import secure_filename
from backend.ai.detector import get_detector
from backend.ai.tracking import process_video_stream
from backend.ai.duplicate_detection import find_duplicate_pothole
from backend.services.priority_service import calculate_priority_score
from backend.database import get_db
from backend.config import UPLOADS_DIR, DETECTIONS_DIR, VIDEOS_DIR

from backend.ai.temporal_buffer import TemporalConfirmationBuffer
from backend.ai.distance_estimator import (
    load_calibration,
    update_camera_calibration,
    calculate_distance_test_metrics,
    estimate_pothole_distance
)

detect_bp = Blueprint('detect', __name__)
live_temporal_buffer = TemporalConfirmationBuffer(window_size=5, min_confirmed_hits=3)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

@detect_bp.route('/calibration', methods=['GET', 'POST'])
def camera_calibration_route():
    if request.method == 'GET':
        calib = load_calibration()
        return jsonify({"success": True, "calibration": calib})
    
    req_json = request.get_json() or {}
    updated_calib = update_camera_calibration(
        camera_height=req_json.get('camera_height'),
        known_ref_width=req_json.get('known_ref_width'),
        known_ref_dist=req_json.get('known_ref_dist'),
        pixel_width=req_json.get('pixel_width'),
        camera_pitch=req_json.get('camera_pitch'),
        camera_fovy=req_json.get('camera_fovy')
    )
    return jsonify({
        "success": True, 
        "message": "Camera calibration updated successfully", 
        "calibration": updated_calib
    })

@detect_bp.route('/distance-test', methods=['POST'])
def distance_test_route():
    req_json = request.get_json() or {}
    test_cases = req_json.get('test_cases', [])
    
    # Default benchmark test set if none provided
    if not test_cases:
        test_cases = [
            {"actual": 1.0, "estimated": 1.1},
            {"actual": 2.0, "estimated": 2.0},
            {"actual": 3.0, "estimated": 3.2},
            {"actual": 4.0, "estimated": 4.1},
            {"actual": 5.0, "estimated": 5.4}
        ]

    # Process test cases with bounding box inputs if provided
    processed_cases = []
    for case in test_cases:
        act = case.get("actual")
        est = case.get("estimated")
        
        if est is None and "bbox" in case and "frame_shape" in case:
            dist_res = estimate_pothole_distance(case["bbox"], case["frame_shape"])
            est = dist_res.get("distance_meters")

        processed_cases.append({
            "actual": act,
            "estimated": est
        })

    metrics = calculate_distance_test_metrics(processed_cases)
    return jsonify({
        "success": True,
        "metrics": metrics
    })

def allowed_file(filename, allowed_set):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set

def generate_unique_pothole_id(cursor, prefix="PT-2026"):
    """
    Generate a guaranteed unique pothole_id by checking existing records in database.
    """
    cursor.execute("SELECT id FROM potholes ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    next_seq = (row[0] + 1) if row else 1

    candidate = f"{prefix}-{next_seq:04d}"
    counter = next_seq
    while True:
        cursor.execute("SELECT COUNT(*) FROM potholes WHERE pothole_id = ?", (candidate,))
        if cursor.fetchone()[0] == 0:
            return candidate
        counter += 1
        candidate = f"{prefix}-{counter:04d}"

def generate_unique_sub_id(cursor, base_p_id, idx):
    """
    Generate a guaranteed unique sub-ID for multiple detection boxes within the same image/video frame.
    """
    sub_suffix = chr(65 + (idx % 26)) if idx < 26 else f"-{idx+1}"
    candidate = f"{base_p_id}-{sub_suffix}"
    counter = 1
    while True:
        cursor.execute("SELECT COUNT(*) FROM potholes WHERE pothole_id = ?", (candidate,))
        if cursor.fetchone()[0] == 0:
            return candidate
        candidate = f"{base_p_id}-{sub_suffix}-{counter}"
        counter += 1

from backend.utils.auth_utils import optional_token

@detect_bp.route('/image', methods=['POST'])
@optional_token
def detect_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image file uploaded"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
        return jsonify({"error": "Invalid file format. Please upload JPG, PNG, or WEBP."}), 400

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    raw_filename = f"upload_{stamp}_{secure_filename(file.filename)}"
    raw_path = os.path.join(UPLOADS_DIR, raw_filename)
    file.save(raw_path)

    road_name = request.form.get('road_name', 'Inspection Segment')
    road_importance = request.form.get('road_importance', 'MEDIUM')
    
    current_user = getattr(request, 'current_user', {}) or {}
    user_id = current_user.get('user_id')
    user_name = current_user.get('name') or 'AI Detection System'
    user_email = current_user.get('email') or 'system@city.gov'

    lat_val = request.form.get('latitude')
    lng_val = request.form.get('longitude')
    if not lat_val or not lng_val:
        return jsonify({"error": "Location coordinates are required. Click 'USE MY CURRENT LOCATION' or select a point on the map."}), 400

    try:
        lat = float(lat_val)
        lng = float(lng_val)
    except ValueError:
        return jsonify({"error": "Invalid location coordinates provided."}), 400

    detector = get_detector()
    result = detector.detect_image_file(raw_path, save_annotated=True)

    conn = get_db()
    inserted_potholes = []
    try:
        cursor = conn.cursor()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        total_det_count = len(result['detections'])

        base_p_id = generate_unique_pothole_id(cursor)
        dup_info = find_duplicate_pothole(lat, lng)

        rel_ann_path = os.path.relpath(result['annotated_image_path'], UPLOADS_DIR).replace('\\', '/') if result['annotated_image_path'] else None
        rel_raw_path = os.path.relpath(raw_path, UPLOADS_DIR).replace('\\', '/')

        for idx, det in enumerate(result['detections']):
            prio_res = calculate_priority_score(
                severity_score=det['severity_score'],
                risk_level=det['risk_level'],
                road_importance=road_importance,
                nearby_count=total_det_count - 1
            )

            if dup_info and total_det_count == 1:
                p_id = dup_info['pothole_id']
                cursor.execute('''
                UPDATE potholes 
                SET detection_count = detection_count + 1, last_detected_at = ? 
                WHERE pothole_id = ?
                ''', (now_str, p_id))
            else:
                if total_det_count > 1:
                    base_id_for_sub = dup_info['pothole_id'] if dup_info else base_p_id
                    p_id = generate_unique_sub_id(cursor, base_id_for_sub, idx)
                else:
                    p_id = base_p_id

                cursor.execute('''
                INSERT INTO potholes (
                    pothole_id, confidence, width, height, area, severity_score, 
                    risk_level, priority_score, road_name, latitude, longitude, 
                    image_path, annotated_image_path, detected_at, last_detected_at, 
                    detection_count, status, road_importance, estimated_distance, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'OPEN', ?, ?, ?)
                ''', (
                    p_id, det['confidence'], det['width'], det['height'], det['area'],
                    det['severity_score'], det['risk_level'], prio_res['priority_score'],
                    road_name, lat, lng, rel_raw_path,
                    rel_ann_path, now_str, now_str, road_importance, det.get('estimated_distance'), user_id
                ))

                # Also create corresponding complaint record for unified lifecycle
                cursor.execute('''
                INSERT INTO complaints (
                    complaint_id, pothole_id, user_id, user_name, user_email, description,
                    location_name, latitude, longitude, image_path, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'AI Detection Studio Report', ?, ?, ?, ?, 'OPEN', ?)
                ''', (p_id, p_id, user_id, user_name, user_email, road_name, lat, lng, rel_ann_path or rel_raw_path, now_str))

            cursor.execute('''
            INSERT INTO detections (pothole_id, source_type, confidence, image_path, detected_at)
            VALUES (?, 'IMAGE', ?, ?, ?)
            ''', (p_id, det['confidence'], rel_ann_path or rel_raw_path, now_str))

            det['pothole_id'] = p_id
            det['priority_score'] = prio_res['priority_score']
            det['duplicate_info'] = dup_info
            inserted_potholes.append(det)

        conn.commit()
    finally:
        conn.close()

    annotated_url = None
    if result['annotated_image_path']:
        rel = os.path.relpath(result['annotated_image_path'], UPLOADS_DIR).replace('\\', '/')
        annotated_url = f"/uploads/{rel}"

    return jsonify({
        "success": True,
        "total_detected": result['total_potholes'],
        "annotated_image_url": annotated_url,
        "detections": inserted_potholes
    })

@detect_bp.route('/video', methods=['POST'])
def detect_video():
    if 'video' not in request.files:
        return jsonify({"error": "No video file uploaded"}), 400

    file = request.files['video']
    if file.filename == '':
        return jsonify({"error": "No video selected"}), 400

    if not allowed_file(file.filename, ALLOWED_VIDEO_EXTENSIONS):
        return jsonify({"error": "Invalid video format. Upload MP4, AVI, or MOV."}), 400

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_filename = f"vid_upload_{stamp}_{secure_filename(file.filename)}"
    raw_path = os.path.join(VIDEOS_DIR, raw_filename)
    file.save(raw_path)

    road_name = request.form.get('road_name') or 'Video Inspection Route'
    road_importance = request.form.get('road_importance') or 'MEDIUM'
    lat_val = request.form.get('latitude')
    lng_val = request.form.get('longitude')
    lat = float(lat_val) if lat_val else 20.5937
    lng = float(lng_val) if lng_val else 78.9629

    stats = process_video_stream(raw_path)

    video_url = None
    if stats.get('output_video_path'):
        video_rel = os.path.relpath(stats['output_video_path'], UPLOADS_DIR).replace('\\', '/')
        video_url = f"/uploads/{video_rel}"

    keyframe_url = None
    if stats.get('keyframe_image_path'):
        key_rel = os.path.relpath(stats['keyframe_image_path'], UPLOADS_DIR).replace('\\', '/')
        keyframe_url = f"/uploads/{key_rel}"

    conn = get_db()
    inserted_potholes = []
    unique_dets = stats.get('unique_detections', [])
    total_det_count = len(unique_dets)

    if total_det_count > 0:
        try:
            cursor = conn.cursor()
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            base_p_id = generate_unique_pothole_id(cursor)
            dup_info = find_duplicate_pothole(lat, lng)

            for idx, det in enumerate(unique_dets):
                prio_res = calculate_priority_score(
                    severity_score=det['severity_score'],
                    risk_level=det['risk_level'],
                    road_importance=road_importance,
                    nearby_count=total_det_count - 1
                )

                if dup_info and total_det_count == 1:
                    p_id = dup_info['pothole_id']
                    cursor.execute('''
                    UPDATE potholes 
                    SET detection_count = detection_count + 1, last_detected_at = ? 
                    WHERE pothole_id = ?
                    ''', (now_str, p_id))
                else:
                    if total_det_count > 1:
                        base_id_for_sub = dup_info['pothole_id'] if dup_info else base_p_id
                        p_id = generate_unique_sub_id(cursor, base_id_for_sub, idx)
                    else:
                        p_id = base_p_id

                    rel_img = keyframe_url.replace('/uploads/', '') if keyframe_url else os.path.relpath(raw_path, UPLOADS_DIR).replace('\\', '/')

                    cursor.execute('''
                    INSERT INTO potholes (
                        pothole_id, confidence, width, height, area, severity_score, 
                        risk_level, priority_score, road_name, latitude, longitude, 
                        image_path, annotated_image_path, detected_at, last_detected_at, 
                        detection_count, status, road_importance, estimated_distance
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'OPEN', ?, ?)
                    ''', (
                        p_id, det['confidence'], det['width'], det['height'], det['area'],
                        det['severity_score'], det['risk_level'], prio_res['priority_score'],
                        road_name, lat, lng, os.path.relpath(raw_path, UPLOADS_DIR).replace('\\', '/'),
                        rel_img, now_str, now_str, road_importance, det.get('estimated_distance')
                    ))

                cursor.execute('''
                INSERT INTO detections (pothole_id, source_type, confidence, image_path, detected_at)
                VALUES (?, 'VIDEO', ?, ?, ?)
                ''', (p_id, det['confidence'], rel_img if 'rel_img' in locals() else '', now_str))

                det['pothole_id'] = p_id
                det['priority_score'] = prio_res['priority_score']
                inserted_potholes.append(det)

            conn.commit()
        finally:
            conn.close()

    return jsonify({
        "success": True,
        "total_frames": stats['total_frames_processed'],
        "unique_pothole_count": stats['unique_pothole_count'],
        "average_confidence": stats['average_confidence'],
        "risk_breakdown": stats['risk_breakdown'],
        "processed_video_url": video_url,
        "keyframe_image_url": keyframe_url,
        "detections": inserted_potholes
    })

# MJPEG Stream generator for Live Camera Mode (legacy fallback)
def generate_camera_frames():
    camera = cv2.VideoCapture(0)
    detector = get_detector()

    if not camera.isOpened():
        print("[WARNING] Live camera unavailable.")
        return

    while True:
        success, frame = camera.read()
        if not success:
            break

        annotated_frame, _ = detector.detect_frame(frame, tracking=True)
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@detect_bp.route('/live_feed')
def live_feed():
    return Response(generate_camera_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@detect_bp.route('/frame', methods=['POST'])
def detect_frame_route():
    import base64
    import numpy as np
    detector = get_detector()
    
    frame = None
    req_json = request.is_json and request.json or {}

    if 'frame' in request.files:
        file = request.files['frame']
        img_bytes = file.read()
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    elif 'image_data' in req_json:
        b64data = req_json['image_data']
        if ',' in b64data:
            b64data = b64data.split(',')[1]
        img_bytes = base64.b64decode(b64data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        return jsonify({"error": "No valid frame image provided"}), 400

    annotated_frame, detections = detector.detect_frame(frame, tracking=False, temporal_buffer=live_temporal_buffer)
    _, buffer = cv2.imencode('.jpg', annotated_frame)
    b64_out = base64.b64encode(buffer).decode('utf-8')

    # Only CONFIRMED potholes (multi-frame hits >= 3 in 5 frames) are eligible for DB save
    confirmed_detections = [d for d in detections if d.get('confirmation_status') == 'CONFIRMED']
    candidate_detections = [d for d in detections if d.get('confirmation_status') == 'CANDIDATE']
    scanning_detections = [d for d in detections if d.get('confirmation_status') == 'SCANNING']

    saved_records = []
    save_to_db = req_json.get('save_to_db', False) or request.form.get('save_to_db') == 'true'

    if save_to_db and len(confirmed_detections) > 0:
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"live_frame_{stamp}.jpg"
        live_img_path = os.path.join(DETECTIONS_DIR, filename)
        cv2.imwrite(live_img_path, annotated_frame)

        rel_img_path = os.path.relpath(live_img_path, UPLOADS_DIR).replace('\\', '/')

        lat_val = req_json.get('latitude') or request.form.get('latitude')
        lng_val = req_json.get('longitude') or request.form.get('longitude')
        road_name = req_json.get('road_name') or request.form.get('road_name') or 'Live AI Camera Stream'

        lat = float(lat_val) if lat_val is not None else 20.5937
        lng = float(lng_val) if lng_val is not None else 78.9629

        dup_info = find_duplicate_pothole(lat, lng)

        conn = get_db()
        try:
            cursor = conn.cursor()
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            base_p_id = generate_unique_pothole_id(cursor)
            total_det_count = len(confirmed_detections)

            for idx, det in enumerate(confirmed_detections):
                prio_res = calculate_priority_score(
                    severity_score=det['severity_score'],
                    risk_level=det['risk_level'],
                    road_importance='HIGH',
                    nearby_count=total_det_count - 1
                )

                if dup_info and total_det_count == 1:
                    p_id = dup_info['pothole_id']
                    cursor.execute('''
                    UPDATE potholes 
                    SET detection_count = detection_count + 1, last_detected_at = ? 
                    WHERE pothole_id = ?
                    ''', (now_str, p_id))
                else:
                    if total_det_count > 1:
                        base_id_for_sub = dup_info['pothole_id'] if dup_info else base_p_id
                        p_id = generate_unique_sub_id(cursor, base_id_for_sub, idx)
                    else:
                        p_id = base_p_id

                    cursor.execute('''
                    INSERT INTO potholes (
                        pothole_id, confidence, width, height, area, severity_score, 
                        risk_level, priority_score, road_name, latitude, longitude, 
                        image_path, annotated_image_path, detected_at, last_detected_at, 
                        detection_count, status, road_importance, estimated_distance
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'OPEN', 'HIGH', ?)
                    ''', (
                        p_id, det['confidence'], det['width'], det['height'], det['area'],
                        det['severity_score'], det['risk_level'], prio_res['priority_score'],
                        road_name, lat, lng, rel_img_path, rel_img_path, now_str, now_str, det.get('estimated_distance')
                    ))

                cursor.execute('''
                INSERT INTO detections (pothole_id, source_type, confidence, image_path, detected_at)
                VALUES (?, 'LIVE', ?, ?, ?)
                ''', (p_id, det['confidence'], rel_img_path, now_str))

                saved_records.append(p_id)

            conn.commit()
        finally:
            conn.close()

    return jsonify({
        "success": True,
        "total_detected": len(detections),
        "confirmed_count": len(confirmed_detections),
        "candidate_count": len(candidate_detections),
        "scanning_count": len(scanning_detections),
        "detections": detections,
        "annotated_frame": f"data:image/jpeg;base64,{b64_out}",
        "saved_to_db": len(saved_records) > 0,
        "saved_pothole_ids": saved_records
    })

@detect_bp.route('/compare_frame', methods=['POST'])
def compare_frame_route():
    """
    Debug route: Capture a live camera frame, save it as a static image,
    and run it through BOTH live frame processing and static file inference
    to empirically verify 100% detection consistency.
    """
    import base64
    import numpy as np
    detector = get_detector()

    frame = None
    req_json = request.is_json and request.json or {}

    if 'frame' in request.files:
        file = request.files['frame']
        img_bytes = file.read()
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    elif 'image_data' in req_json:
        b64data = req_json['image_data']
        if ',' in b64data:
            b64data = b64data.split(',')[1]
        img_bytes = base64.b64decode(b64data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        return jsonify({"error": "No valid frame image provided"}), 400

    # 1. Run Live Frame Detection
    ann_live, dets_live = detector.detect_frame(frame.copy(), tracking=False)

    # 2. Save to temporary disk file and run Static File Detection
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    temp_path = os.path.join(UPLOADS_DIR, f"temp_compare_{stamp}.jpg")
    cv2.imwrite(temp_path, frame)

    try:
        static_result = detector.detect_image_file(temp_path, save_annotated=False)
        dets_static = static_result['detections']
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    # 3. Compare Results
    live_count = len(dets_live)
    static_count = len(dets_static)
    is_identical = (live_count == static_count)

    if is_identical and live_count > 0:
        for d1, d2 in zip(dets_live, dets_static):
            bbox_diff = max(abs(c1 - c2) for c1, c2 in zip(d1['bbox'], d2['bbox']))
            if abs(d1['confidence'] - d2['confidence']) > 1.0 or bbox_diff > 2:
                is_identical = False
                break

    _, buffer = cv2.imencode('.jpg', ann_live)
    b64_out = base64.b64encode(buffer).decode('utf-8')

    return jsonify({
        "success": True,
        "is_identical": is_identical,
        "live_count": live_count,
        "static_count": static_count,
        "live_detections": dets_live,
        "static_detections": dets_static,
        "annotated_frame": f"data:image/jpeg;base64,{b64_out}"
    })


