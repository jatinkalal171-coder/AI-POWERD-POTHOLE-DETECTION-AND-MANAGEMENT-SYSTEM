import math
from backend.config import SEVERITY_LOW_MAX, SEVERITY_MEDIUM_MAX, SEVERITY_HIGH_MAX

def calculate_severity_score(box_area, frame_area, confidence_percent, nearby_count=0):
    """
    Calculate an estimated Severity Score (0-100) based on:
    - Box Area relative to total frame area (45% weight)
    - Detection Confidence percentage (35% weight)
    - Pothole Cluster Density / nearby count (20% weight)
    """
    # 1. Area ratio score (logarithmic/linear scaling up to 15% of frame)
    area_ratio = min(box_area / max(frame_area, 1), 0.15)
    area_score = min((area_ratio / 0.08) * 100, 100)

    # 2. Confidence score (direct percentage)
    conf_score = confidence_percent

    # 3. Density / cluster score
    density_score = min(nearby_count * 25, 100)

    # Weighted sum
    total_score = int(round(
        (area_score * 0.45) +
        (conf_score * 0.35) +
        (density_score * 0.20)
    ))

    # Clamp between 0 and 100
    severity_score = max(0, min(100, total_score))
    risk_level, color_bgr, color_hex = get_risk_category(severity_score)

    return {
        "severity_score": severity_score,
        "risk_level": risk_level,
        "color_bgr": color_bgr,
        "color_hex": color_hex,
        "area_score": round(area_score, 1),
        "conf_score": round(conf_score, 1),
        "density_score": round(density_score, 1)
    }

def get_risk_category(score):
    if score <= SEVERITY_LOW_MAX:
        return "LOW", (0, 255, 255), "#f1c40f"         # Yellow
    elif score <= SEVERITY_MEDIUM_MAX:
        return "MEDIUM", (0, 165, 255), "#e67e22"      # Orange
    elif score <= SEVERITY_HIGH_MAX:
        return "HIGH", (0, 0, 255), "#e74c3c"          # Red
    else:
        return "CRITICAL", (128, 0, 128), "#9b59b6"    # Purple/Magenta
