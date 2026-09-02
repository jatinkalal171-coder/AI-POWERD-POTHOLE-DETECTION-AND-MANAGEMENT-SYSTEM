from backend.database import get_db
from backend.utils.geo_utils import calculate_haversine_distance
from backend.services.priority_service import calculate_road_health_score

def detect_pothole_hotspots(radius_meters=300, min_potholes=2):
    """
    Cluster unresolved potholes within radius_meters to identify Hotspot zones.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT pothole_id, road_name, latitude, longitude, severity_score, risk_level, priority_score, status
    FROM potholes
    WHERE status != 'CLOSED' AND latitude IS NOT NULL AND longitude IS NOT NULL
    ''')
    potholes = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not potholes:
        return []

    visited = set()
    clusters = []

    for i, p1 in enumerate(potholes):
        if p1['pothole_id'] in visited:
            continue

        cluster_items = [p1]
        visited.add(p1['pothole_id'])

        for j, p2 in enumerate(potholes):
            if i == j or p2['pothole_id'] in visited:
                continue

            dist = calculate_haversine_distance(
                p1['latitude'], p1['longitude'],
                p2['latitude'], p2['longitude']
            )

            if dist <= radius_meters:
                cluster_items.append(p2)
                visited.add(p2['pothole_id'])

        if len(cluster_items) >= min_potholes:
            avg_lat = sum(item['latitude'] for item in cluster_items) / len(cluster_items)
            avg_lng = sum(item['longitude'] for item in cluster_items) / len(cluster_items)
            
            health_res = calculate_road_health_score(cluster_items)
            high_risk_count = sum(1 for item in cluster_items if item['risk_level'] in ('HIGH', 'CRITICAL'))

            if len(cluster_items) >= 5 or high_risk_count >= 3:
                prio_label = "VERY HIGH"
            elif len(cluster_items) >= 3:
                prio_label = "HIGH"
            else:
                prio_label = "MEDIUM"

            clusters.append({
                "hotspot_id": f"HOTSPOT-{len(clusters)+1:02d}",
                "road_name": cluster_items[0]['road_name'],
                "latitude": round(avg_lat, 6),
                "longitude": round(avg_lng, 6),
                "total_potholes": len(cluster_items),
                "high_risk_count": high_risk_count,
                "road_health_score": health_res['health_score'],
                "road_condition": health_res['condition'],
                "priority": prio_label,
                "potholes": cluster_items
            })

    # Sort hotspots by highest total potholes
    clusters.sort(key=lambda x: x['total_potholes'], reverse=True)
    return clusters
