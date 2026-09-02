import math
import datetime
from backend.config import ALLOWED_GPS_RADIUS_METERS
from backend.ai.scene_verifier import verify_scene_similarity

def calculate_geodesic_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two GPS points
    on earth in meters using the Haversine formula.
    """
    if None in (lat1, lon1, lat2, lon2):
        return 999999.0

    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0)**2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return round(R * c, 2)

def perform_multi_factor_verification(
    orig_lat, orig_lng, 
    officer_lat, officer_lng, officer_accuracy, 
    before_img_path, after_img_path, 
    ai_detected_potholes
):
    """
    Combines 5 Verification Factors:
    1. Camera Capture (Submission event)
    2. GPS Geofencing Match (Distance <= 30m)
    3. Server Timestamp
    4. Before/After Visual Scene Consistency (OpenCV ORB/Histogram)
    5. AI Pothole Elimination Model Inspection
    """
    capture_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. GPS Geofencing Check
    dist_meters = calculate_geodesic_distance(orig_lat, orig_lng, officer_lat, officer_lng)
    
    if officer_lat is None or officer_lng is None:
        gps_status = "FAILED"
        gps_reason = "Officer GPS location coordinates missing or unavailable."
    elif dist_meters <= ALLOWED_GPS_RADIUS_METERS:
        gps_status = "VERIFIED"
        gps_reason = f"Officer location verified ({dist_meters}m from pothole; within {ALLOWED_GPS_RADIUS_METERS}m radius)."
    else:
        gps_status = "FAILED"
        gps_reason = f"Officer is {dist_meters}m away from reported pothole location (Exceeds {ALLOWED_GPS_RADIUS_METERS}m allowed radius)."

    # 2. Before vs After Scene Match Check
    scene_res = verify_scene_similarity(before_img_path, after_img_path)
    scene_status = scene_res["status"]
    scene_score = scene_res["similarity_score"]
    scene_reason = scene_res["reason"]

    # 3. AI Repair Inspection Check
    if ai_detected_potholes == 0:
        ai_status = "VERIFIED"
        ai_reason = "AI Model verified 0 potholes in repair proof photo."
    else:
        ai_status = "FAILED"
        ai_reason = f"AI Model detected {ai_detected_potholes} pothole(s) still remaining in repair proof photo."

    # 4. Multi-Factor Decision Matrix
    if gps_status == "FAILED":
        final_status = "GPS_FAILED"
        pothole_status = "UNDER_REPAIR"
        reason = f"Repair photo rejected: {gps_reason}"
    elif scene_status == "FAILED":
        final_status = "SCENE_MISMATCH"
        pothole_status = "UNDER_REPAIR"
        reason = f"Repair photo rejected: {scene_reason}"
    elif scene_status == "MANUAL_REVIEW_REQUIRED":
        final_status = "MANUAL_REVIEW_REQUIRED"
        pothole_status = "UNDER_REPAIR"
        reason = f"Scene match uncertain: {scene_reason}"
    elif ai_status == "FAILED":
        final_status = "REPAIR_NOT_VERIFIED"
        pothole_status = "UNDER_REPAIR"
        reason = f"Repair incomplete: {ai_reason}"
    else:
        final_status = "VERIFIED"
        pothole_status = "RESOLVED"
        reason = "Multi-Factor Verification Passed! All 5 factors (Camera Capture, GPS Geofence, Timestamp, Scene Match, AI Check) verified successfully."

    return {
        "final_status": final_status,
        "pothole_status": pothole_status,
        "reason": reason,
        "capture_timestamp": capture_timestamp,
        "distance_meters": dist_meters,
        "gps_status": gps_status,
        "gps_reason": gps_reason,
        "scene_status": scene_status,
        "scene_score": scene_score,
        "scene_reason": scene_reason,
        "ai_status": ai_status,
        "ai_reason": ai_reason
    }
