from flask import Blueprint, request, jsonify
from backend.database import get_db
from backend.services.priority_service import calculate_priority_score
import datetime

pothole_bp = Blueprint('potholes', __name__)

@pothole_bp.route('', methods=['GET'])
def get_potholes():
    search = request.args.get('search', '').strip()
    risk = request.args.get('risk', '').strip()
    status = request.args.get('status', '').strip()
    sort_by = request.args.get('sort', 'priority').strip()

    query = "SELECT * FROM potholes WHERE 1=1"
    params = []

    if search:
        query += " AND (pothole_id LIKE ? OR road_name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    if risk:
        query += " AND risk_level = ?"
        params.append(risk.upper())

    if status:
        query += " AND status = ?"
        params.append(status.upper())

    if sort_by == 'newest':
        query += " ORDER BY detected_at DESC"
    elif sort_by == 'severity':
        query += " ORDER BY severity_score DESC"
    elif sort_by == 'oldest':
        query += " ORDER BY detected_at ASC"
    else:
        query += " ORDER BY priority_score DESC"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(query, params)
    potholes = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({"potholes": potholes, "count": len(potholes)})

@pothole_bp.route('/<pothole_id>', methods=['GET'])
def get_pothole_detail(pothole_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM potholes WHERE pothole_id = ?", (pothole_id,))
    pothole = cursor.fetchone()

    if not pothole:
        conn.close()
        return jsonify({"error": "Pothole record not found"}), 404

    p_dict = dict(pothole)
    if p_dict.get('estimated_distance') is not None:
        p_dict['estimated_distance_str'] = f"{p_dict['estimated_distance']:.1f} m"
    else:
        p_dict['estimated_distance_str'] = "Distance estimation requires camera calibration."

    # Fetch detection events
    cursor.execute("SELECT * FROM detections WHERE pothole_id = ? ORDER BY detected_at DESC", (pothole_id,))
    detections = [dict(row) for row in cursor.fetchall()]

    # Fetch associated repair work order
    cursor.execute("SELECT * FROM repairs WHERE pothole_id = ?", (pothole_id,))
    repair = cursor.fetchone()

    # Fetch associated complaints
    cursor.execute("SELECT * FROM complaints WHERE pothole_id = ?", (pothole_id,))
    complaints = [dict(row) for row in cursor.fetchall()]

    # Fetch audit logs
    cursor.execute("SELECT * FROM audit_logs WHERE pothole_id = ? ORDER BY timestamp DESC", (pothole_id,))
    logs = [dict(row) for row in cursor.fetchall()]

    conn.close()

    # Generate Explainable AI breakdown
    explanations = []
    if p_dict['area'] > 50000:
        explanations.append("✓ Large detected surface area")
    if p_dict['confidence'] > 85:
        explanations.append("✓ High AI detection confidence score")
    if p_dict['road_importance'] in ('HIGH', 'CRITICAL'):
        explanations.append("✓ High traffic road segment importance")
    if p_dict['detection_count'] > 1:
        explanations.append(f"✓ Repeated detection events ({p_dict['detection_count']} times)")

    p_dict['explainable_ai'] = {
        "reasons": explanations,
        "recommendation": "Immediate field repair inspection" if p_dict['risk_level'] in ('HIGH', 'CRITICAL') else "Scheduled maintenance"
    }

    return jsonify({
        "pothole": p_dict,
        "detections": detections,
        "repair": dict(repair) if repair else None,
        "complaints": complaints,
        "audit_logs": logs
    })

@pothole_bp.route('/<pothole_id>', methods=['PUT'])
def update_pothole(pothole_id):
    data = request.get_json() or {}
    new_status = data.get('status')
    road_name = data.get('road_name')
    road_importance = data.get('road_importance')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM potholes WHERE pothole_id = ?", (pothole_id,))
    pothole = cursor.fetchone()

    if not pothole:
        conn.close()
        return jsonify({"error": "Pothole record not found"}), 404

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if new_status:
        cursor.execute("UPDATE potholes SET status = ?, last_detected_at = ? WHERE pothole_id = ?", (new_status, now_str, pothole_id))

    if road_name or road_importance:
        imp = road_importance or pothole['road_importance']
        r_name = road_name or pothole['road_name']
        
        # Recalculate priority
        prio_res = calculate_priority_score(
            severity_score=pothole['severity_score'],
            risk_level=pothole['risk_level'],
            road_importance=imp
        )
        cursor.execute('''
        UPDATE potholes SET road_name = ?, road_importance = ?, priority_score = ? 
        WHERE pothole_id = ?
        ''', (r_name, imp, prio_res['priority_score'], pothole_id))

    # Log audit entry
    cursor.execute('''
    INSERT INTO audit_logs (user_id, user_name, action, pothole_id, details, timestamp)
    VALUES (1, 'Admin/Officer', 'Pothole Status Updated', ?, ?, ?)
    ''', (pothole_id, f"Updated status: {new_status}", now_str))

    conn.commit()
    conn.close()

    return jsonify({"message": f"Pothole {pothole_id} updated successfully"})
