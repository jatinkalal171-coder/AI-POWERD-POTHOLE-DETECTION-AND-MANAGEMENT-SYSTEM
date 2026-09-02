import datetime

def calculate_priority_score(severity_score, risk_level, road_importance="MEDIUM", nearby_count=0, age_days=0):
    """
    Calculate Repair Priority Score (0-100) combining:
    - Severity Score (40% weight)
    - Road Importance multiplier (25% weight: CRITICAL=100, HIGH=80, MEDIUM=50, LOW=20)
    - Pothole Cluster Density (20% weight)
    - Age of unresolved issue (15% weight: 5 points per day up to 100)
    """
    imp_map = {"CRITICAL": 100, "HIGH": 80, "MEDIUM": 50, "LOW": 20}
    imp_score = imp_map.get(road_importance.upper(), 50)

    density_score = min(nearby_count * 20, 100)
    age_score = min(age_days * 5, 100)

    total_priority = int(round(
        (severity_score * 0.40) +
        (imp_score * 0.25) +
        (density_score * 0.20) +
        (age_score * 0.15)
    ))

    priority_score = max(0, min(100, total_priority))
    
    if priority_score >= 80:
        prio_label = "CRITICAL"
    elif priority_score >= 60:
        prio_label = "HIGH"
    elif priority_score >= 35:
        prio_label = "MEDIUM"
    else:
        prio_label = "LOW"

    return {
        "priority_score": priority_score,
        "priority_label": prio_label
    }

def calculate_road_health_score(potholes_list):
    """
    Calculate overall Road Health Score (0-100, where 100 is pristine condition).
    Factors:
    - Total pothole count
    - Count of CRITICAL / HIGH risk potholes
    - Average severity score
    """
    if not potholes_list:
        return {
            "health_score": 100,
            "condition": "EXCELLENT",
            "color_hex": "#2ecc71"
        }

    total_count = len(potholes_list)
    critical_high_count = sum(1 for p in potholes_list if p['risk_level'] in ('CRITICAL', 'HIGH'))
    avg_severity = sum(p['severity_score'] for p in potholes_list) / total_count

    # Deductions formula
    deduction = (total_count * 5) + (critical_high_count * 15) + (avg_severity * 0.4)
    health_score = max(0, min(100, int(round(100 - deduction))))

    if health_score >= 80:
        condition = "GOOD"
        color_hex = "#2ecc71"  # Green
    elif health_score >= 60:
        condition = "MODERATE"
        color_hex = "#f39c12"  # Orange
    elif health_score >= 30:
        condition = "POOR"
        color_hex = "#e67e22"  # Dark Orange
    else:
        condition = "CRITICAL"
        color_hex = "#e74c3c"  # Red

    return {
        "health_score": health_score,
        "condition": condition,
        "color_hex": color_hex,
        "total_potholes": total_count,
        "critical_high_potholes": critical_high_count,
        "average_severity": round(avg_severity, 1)
    }
