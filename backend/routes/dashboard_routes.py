from flask import Blueprint, jsonify
from backend.database import get_db
from backend.services.priority_service import calculate_road_health_score
from backend.services.hotspot_service import detect_pothole_hotspots
from backend.services.escalation_service import check_and_escalate_overdue_repairs

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/stats', methods=['GET'])
def get_dashboard_stats():
    # Run overdue check on stats load
    check_and_escalate_overdue_repairs()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM potholes")
    potholes = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT COUNT(*) FROM complaints")
    total_reports = cursor.fetchone()[0]

    total_potholes = len(potholes)
    risk_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    status_counts = {"OPEN": 0, "VERIFIED": 0, "SUBMITTED": 0, "ASSIGNED": 0, "UNDER_REPAIR": 0, "RESOLVED": 0, "CLOSED": 0}

    pending_count = 0
    under_repair_count = 0
    resolved_count = 0

    for p in potholes:
        risk_counts[p['risk_level']] = risk_counts.get(p['risk_level'], 0) + 1
        st = p['status'].upper()
        status_counts[st] = status_counts.get(st, 0) + 1
        
        if st in ('OPEN', 'SUBMITTED', 'PENDING'):
            pending_count += 1
        elif st in ('ASSIGNED', 'UNDER_REPAIR'):
            under_repair_count += 1
        elif st in ('RESOLVED', 'CLOSED', 'VERIFIED_CLOSED', 'AI_VERIFIED'):
            resolved_count += 1

    health_info = calculate_road_health_score(potholes)

    # Overdue count
    cursor.execute("SELECT COUNT(*) FROM notifications WHERE type IN ('OVERDUE', 'ESCALATED', 'CRITICAL_DELAY') AND read_status = 0")
    overdue_count = cursor.fetchone()[0]

    # Recent Detections
    cursor.execute("SELECT * FROM potholes ORDER BY detected_at DESC LIMIT 5")
    recent_detections = [dict(row) for row in cursor.fetchall()]

    # Recent Notifications
    cursor.execute("SELECT * FROM notifications ORDER BY created_at DESC LIMIT 5")
    recent_notifications = [dict(row) for row in cursor.fetchall()]

    conn.close()

    high_risk_total = risk_counts.get('HIGH', 0) + risk_counts.get('CRITICAL', 0)
    medium_risk_total = risk_counts.get('MEDIUM', 0)
    low_risk_total = risk_counts.get('LOW', 0)

    return jsonify({
        "total_potholes": total_potholes,
        "total_detected": total_potholes,
        "total_reports": total_reports,
        "high_risk_count": high_risk_total,
        "medium_risk_count": medium_risk_total,
        "low_risk_count": low_risk_total,
        "pending_count": pending_count,
        "under_repair_count": under_repair_count,
        "resolved_count": resolved_count,
        "risk_breakdown": risk_counts,
        "status_breakdown": status_counts,
        "road_health": health_info,
        "overdue_count": overdue_count,
        "recent_detections": recent_detections,
        "recent_notifications": recent_notifications
    })

@dashboard_bp.route('/map/markers', methods=['GET'])
def get_map_markers():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, pothole_id, road_name, latitude, longitude, risk_level, severity_score, priority_score, status, detected_at, annotated_image_path
    FROM potholes
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    ''')
    markers = [dict(row) for row in cursor.fetchall()]
    conn.close()

    for m in markers:
        if m['annotated_image_path']:
            m['image_url'] = f"/uploads/{m['annotated_image_path']}"
        else:
            m['image_url'] = None

    return jsonify({"markers": markers, "count": len(markers)})

@dashboard_bp.route('/map/hotspots', methods=['GET'])
def get_map_hotspots():
    hotspots = detect_pothole_hotspots()
    return jsonify({"hotspots": hotspots, "count": len(hotspots)})

@dashboard_bp.route('/analytics', methods=['GET'])
def get_analytics_data():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT risk_level, COUNT(*) as count FROM potholes GROUP BY risk_level")
    risk_dist = {row['risk_level']: row['count'] for row in cursor.fetchall()}

    cursor.execute("SELECT status, COUNT(*) as count FROM potholes GROUP BY status")
    status_dist = {row['status']: row['count'] for row in cursor.fetchall()}

    cursor.execute("SELECT road_name, COUNT(*) as count, AVG(severity_score) as avg_sev FROM potholes GROUP BY road_name ORDER BY count DESC LIMIT 6")
    road_ranking = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT strftime('%Y-%m-%d', detected_at) as date, COUNT(*) as count FROM potholes GROUP BY date ORDER BY date ASC LIMIT 14")
    trend = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        "risk_distribution": risk_dist,
        "status_distribution": status_dist,
        "road_rankings": road_ranking,
        "detection_trend": trend
    })
