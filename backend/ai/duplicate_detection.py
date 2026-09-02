from backend.database import get_db
from backend.utils.geo_utils import calculate_haversine_distance

PROXIMITY_THRESHOLD_METERS = 15.0  # 15 meters

def find_duplicate_pothole(lat, lng, pothole_id=None):
    """
    Search database for an existing unresolved pothole near (lat, lng) within PROXIMITY_THRESHOLD_METERS.
    """
    if lat is None or lng is None:
        return None

    conn = get_db()
    cursor = conn.cursor()
    
    # Query all active/unresolved potholes with valid coordinates
    cursor.execute('''
    SELECT pothole_id, latitude, longitude, detection_count, detected_at, status 
    FROM potholes 
    WHERE status != 'CLOSED' AND latitude IS NOT NULL AND longitude IS NOT NULL
    ''')
    existing = cursor.fetchall()
    conn.close()

    for p in existing:
        if pothole_id and p['pothole_id'] == pothole_id:
            continue
            
        dist = calculate_haversine_distance(lat, lng, p['latitude'], p['longitude'])
        if dist <= PROXIMITY_THRESHOLD_METERS:
            return {
                "pothole_id": p['pothole_id'],
                "distance_meters": round(dist, 2),
                "detection_count": p['detection_count'],
                "first_detected": p['detected_at'],
                "status": p['status']
            }

    return None
