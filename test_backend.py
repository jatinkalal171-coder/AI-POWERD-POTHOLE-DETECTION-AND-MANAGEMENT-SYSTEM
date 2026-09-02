import unittest
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from backend.app import create_app
from backend.database import init_db
from backend.services.priority_service import calculate_priority_score, calculate_road_health_score
from backend.services.hotspot_service import detect_pothole_hotspots

class TestSmartRoadBackend(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_dashboard_stats_api(self):
        res = self.client.get('/api/stats')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('total_potholes', data)
        self.assertIn('road_health', data)

    def test_potholes_list_api(self):
        res = self.client.get('/api/potholes')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('potholes', data)

    def test_map_markers_api(self):
        res = self.client.get('/api/map/markers')
        self.assertEqual(res.status_code, 200)

    def test_hotspots_api(self):
        res = self.client.get('/api/map/hotspots')
        self.assertEqual(res.status_code, 200)

    def test_severity_and_priority_logic(self):
        prio = calculate_priority_score(severity_score=90, risk_level="CRITICAL", road_importance="CRITICAL", nearby_count=4, age_days=8)
        self.assertGreaterEqual(prio['priority_score'], 75)
        self.assertIn(prio['priority_label'], ["CRITICAL", "HIGH"])

    def test_road_health_calculation(self):
        dummy_potholes = [
            {'risk_level': 'CRITICAL', 'severity_score': 90},
            {'risk_level': 'HIGH', 'severity_score': 75}
        ]
        rh = calculate_road_health_score(dummy_potholes)
        self.assertLess(rh['health_score'], 100)

if __name__ == '__main__':
    unittest.main()
