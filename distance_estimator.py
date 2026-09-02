import os
import json
import math
import datetime
from backend.config import (
    CAMERA_HEIGHT_METERS,
    CAMERA_PITCH_DEG,
    CAMERA_FOVY_DEG,
    KNOWN_REF_WIDTH_METERS,
    KNOWN_REF_DIST_METERS,
    CALIBRATION_FILE_PATH
)

DEFAULT_CALIBRATION = {
    "is_calibrated": True,
    "camera_height": CAMERA_HEIGHT_METERS,
    "camera_pitch": CAMERA_PITCH_DEG,
    "camera_fovy": CAMERA_FOVY_DEG,
    "known_ref_width": KNOWN_REF_WIDTH_METERS,
    "known_ref_dist": KNOWN_REF_DIST_METERS,
    "focal_length_px": None,
    "calibrated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

def load_calibration():
    """Load calibration parameters from JSON file or return defaults."""
    try:
        if os.path.exists(CALIBRATION_FILE_PATH):
            with open(CALIBRATION_FILE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
    except Exception as e:
        print(f"[WARNING] Could not load camera calibration: {e}")
    
    # Save default initial calibration if file does not exist
    save_calibration(DEFAULT_CALIBRATION)
    return DEFAULT_CALIBRATION

def save_calibration(calibration_data):
    """Save calibration parameters to JSON file."""
    try:
        os.makedirs(os.path.dirname(CALIBRATION_FILE_PATH), exist_ok=True)
        with open(CALIBRATION_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(calibration_data, f, indent=2)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save camera calibration: {e}")
        return False

def update_camera_calibration(camera_height=None, known_ref_width=None, known_ref_dist=None, 
                              pixel_width=None, camera_pitch=None, camera_fovy=None):
    """
    Update calibration parameters and compute focal length if pixel width is provided.
    """
    calib = load_calibration()

    if camera_height is not None:
        calib["camera_height"] = float(camera_height)
    if known_ref_width is not None:
        calib["known_ref_width"] = float(known_ref_width)
    if known_ref_dist is not None:
        calib["known_ref_dist"] = float(known_ref_dist)
    if camera_pitch is not None:
        calib["camera_pitch"] = float(camera_pitch)
    if camera_fovy is not None:
        calib["camera_fovy"] = float(camera_fovy)

    # Compute focal length if pixel width measurement is provided
    if pixel_width is not None and float(pixel_width) > 0 and calib["known_ref_width"] > 0:
        pw = float(pixel_width)
        rw = float(calib["known_ref_width"])
        rd = float(calib["known_ref_dist"])
        calib["focal_length_px"] = round((pw * rd) / rw, 2)

    calib["is_calibrated"] = True
    calib["calibrated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    save_calibration(calib)
    return calib

def estimate_pothole_distance(bbox, frame_shape):
    """
    Defensible Monocular Pinhole Camera Ground-Plane Distance Estimator.
    
    Computes distance Z from camera to pothole based on the bottom-center coordinate 
    of the bounding box (where the pothole rests on the road ground plane).
    
    Parameters:
        bbox (list/tuple): [x1, y1, x2, y2] bounding box coordinates in pixels.
        frame_shape (tuple): (height, width) or (height, width, channels) of the frame.
        
    Returns:
        dict: {
            "distance_meters": float or None,
            "distance_str": str (e.g. "3.4 m" or "Distance estimation requires camera calibration."),
            "reliability": str ("High", "Medium", "Low", or "Calibration Required"),
            "is_valid": bool,
            "warning": str or None
        }
    """
    uncalibrated_res = {
        "distance_meters": None,
        "distance_str": "Distance estimation requires camera calibration.",
        "reliability": "Calibration Required",
        "is_valid": False,
        "warning": "Distance estimation requires camera calibration."
    }

    if not bbox or len(bbox) < 4 or not frame_shape or frame_shape[0] <= 0:
        return uncalibrated_res

    calib = load_calibration()
    if not calib.get("is_calibrated", False):
        return uncalibrated_res

    frame_h = frame_shape[0]
    x1, y1, x2, y2 = bbox[:4]
    box_w = max(x2 - x1, 1)
    
    # Normalized vertical position of pothole bottom (0.0 = top, 1.0 = bottom)
    norm_y = y2 / float(frame_h)
    
    # Horizon / sky check: if bottom edge is near top of frame (norm_y < 0.15), not on road ground plane
    if norm_y < 0.15 or norm_y > 0.99:
        return {
            "distance_meters": None,
            "distance_str": "Distance estimation requires camera calibration.",
            "reliability": "Low / Calibration Required",
            "is_valid": False,
            "warning": "Pothole contact point outside road ground plane boundary."
        }
        
    try:
        h_cam = float(calib.get("camera_height", 1.3))
        pitch_rad = math.radians(float(calib.get("camera_pitch", 15.0)))
        fovy_rad = math.radians(float(calib.get("camera_fovy", 55.0)))
        focal_px = calib.get("focal_length_px")
        
        # Effective focal length in vertical pixels from FOV
        fy = frame_h / (2.0 * math.tan(fovy_rad / 2.0))
        y_center = frame_h / 2.0
        
        # Vertical angle of ray relative to optical center
        angle_off_axis = math.atan((y2 - y_center) / fy)
        
        # Total ray angle relative to ground plane horizon
        total_angle = pitch_rad + angle_off_axis
        
        if total_angle <= 0.02:  # Ray points at or above horizon line
            return uncalibrated_res
            
        # Ground plane distance formula: Z = h_cam / tan(total_angle)
        distance_z = h_cam / math.tan(total_angle)

        # If focal_length_px is calibrated via reference object, blend/refine pinhole estimation
        if focal_px and focal_px > 0 and calib.get("known_ref_width"):
            ref_width = float(calib["known_ref_width"])
            distance_pinhole = (focal_px * ref_width) / float(box_w)
            # Weighted average between ground-plane and reference pinhole
            distance_z = 0.70 * distance_z + 0.30 * distance_pinhole
        
        # Clamp distance bounds (0.5m to 50.0m)
        if distance_z < 0.5 or distance_z > 50.0:
            dist_clamped = round(max(0.5, min(50.0, distance_z)), 1)
            return {
                "distance_meters": dist_clamped,
                "distance_str": f"{dist_clamped} m",
                "reliability": "Low",
                "is_valid": True,
                "warning": "Extreme distance range"
            }
            
        # Determine reliability score
        if 0.40 <= norm_y <= 0.92:
            reliability = "High"
        elif 0.25 <= norm_y < 0.40:
            reliability = "Medium"
        else:
            reliability = "Low"
            
        dist_rounded = round(distance_z, 1)
        
        return {
            "distance_meters": dist_rounded,
            "distance_str": f"{dist_rounded} m",
            "reliability": reliability,
            "is_valid": True,
            "warning": None
        }
        
    except Exception as e:
        print(f"[ERROR] Distance calculation error: {e}")
        return uncalibrated_res

def calculate_distance_test_metrics(test_cases):
    """
    Evaluates actual distance vs estimated distance test cases for demonstration.
    Input test_cases: list of dicts [{"actual": 3.0, "estimated": 3.2}, ...]
    Returns summary dict with per-case metrics and Mean Absolute Error (MAE) and Mean Error %.
    """
    results = []
    total_abs_error = 0.0
    total_error_pct = 0.0
    valid_count = 0

    for item in test_cases:
        actual = float(item.get("actual", 0))
        estimated = float(item.get("estimated", 0)) if item.get("estimated") is not None else None

        if estimated is not None and actual > 0:
            abs_err = round(abs(estimated - actual), 2)
            err_pct = round((abs_err / actual) * 100.0, 2)
            total_abs_error += abs_err
            total_error_pct += err_pct
            valid_count += 1
        else:
            abs_err = None
            err_pct = None

        results.append({
            "actual_m": actual,
            "estimated_m": estimated,
            "error_m": abs_err,
            "error_percent": err_pct,
            "status": "Detected" if estimated is not None else "Not Detected / Uncalibrated"
        })

    mae = round(total_abs_error / valid_count, 2) if valid_count > 0 else 0.0
    mape = round(total_error_pct / valid_count, 2) if valid_count > 0 else 0.0

    return {
        "test_results": results,
        "total_tested": len(test_cases),
        "valid_count": valid_count,
        "mean_absolute_error_m": mae,
        "mean_absolute_percentage_error": mape
    }
