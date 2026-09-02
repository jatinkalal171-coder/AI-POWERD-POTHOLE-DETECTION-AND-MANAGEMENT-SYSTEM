import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# File Storage Paths
MODEL_PATH = os.environ.get("MODEL_PATH", os.path.join(BASE_DIR, "best.pt"))
DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "database", "pothole.db"))

UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
DETECTIONS_DIR = os.path.join(UPLOADS_DIR, "detections")
COMPLAINTS_DIR = os.path.join(UPLOADS_DIR, "complaints")
REPAIRS_DIR = os.path.join(UPLOADS_DIR, "repairs")
VIDEOS_DIR = os.path.join(UPLOADS_DIR, "videos")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# Security
SECRET_KEY = os.environ.get("SECRET_KEY", "smart-pothole-monitoring-secret-key-2026")
JWT_EXPIRATION_HOURS = 24

# AI Config Thresholds
CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", 0.70))
NMS_IOU_THRESHOLD = float(os.environ.get("NMS_IOU_THRESHOLD", 0.45))
MIN_POTHOLE_AREA = int(os.environ.get("MIN_POTHOLE_AREA", 100))
MAX_POTHOLE_AREA = int(os.environ.get("MAX_POTHOLE_AREA", 10000000))
MAX_POTHOLE_FRAME_RATIO = float(os.environ.get("MAX_POTHOLE_FRAME_RATIO", 0.35))

# Camera Geometry & Monocular Distance Estimation Calibration
CAMERA_HEIGHT_METERS = float(os.environ.get("CAMERA_HEIGHT_METERS", 1.3))
CAMERA_PITCH_DEG = float(os.environ.get("CAMERA_PITCH_DEG", 15.0))
CAMERA_FOVY_DEG = float(os.environ.get("CAMERA_FOVY_DEG", 55.0))
KNOWN_REF_WIDTH_METERS = float(os.environ.get("KNOWN_REF_WIDTH_METERS", 0.50))
KNOWN_REF_DIST_METERS = float(os.environ.get("KNOWN_REF_DIST_METERS", 2.00))
CALIBRATION_FILE_PATH = os.path.join(BASE_DIR, "backend", "camera_calibration.json")

# Severity Engine Thresholds (0-100)
SEVERITY_LOW_MAX = 30
SEVERITY_MEDIUM_MAX = 60
SEVERITY_HIGH_MAX = 80

# Priority Engine Weights
WEIGHT_SEVERITY = 0.40
WEIGHT_ROAD_IMPORTANCE = 0.25
WEIGHT_DENSITY = 0.20
WEIGHT_AGE = 0.15

# Escalation Config (Days)
REMINDER_DAYS = 2
PENDING_ALERT_DAYS = 5
ESCALATED_DAYS = 7
CRITICAL_DELAY_DAYS = 10

# Multi-Factor Repair Verification Config
ALLOWED_GPS_RADIUS_METERS = float(os.environ.get("ALLOWED_GPS_RADIUS_METERS", 30.0))
SCENE_MATCH_THRESHOLD_HIGH = float(os.environ.get("SCENE_MATCH_THRESHOLD_HIGH", 40.0))
SCENE_MATCH_THRESHOLD_LOW = float(os.environ.get("SCENE_MATCH_THRESHOLD_LOW", 20.0))

# Email Config (Configurable via UI/env)
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
MUNICIPALITY_EMAIL = os.environ.get("MUNICIPALITY_EMAIL", "road-maintenance@cityportal.gov")

# Ensure required directories exist
for directory in [UPLOADS_DIR, DETECTIONS_DIR, COMPLAINTS_DIR, REPAIRS_DIR, VIDEOS_DIR, REPORTS_DIR, os.path.dirname(DATABASE_PATH)]:
    os.makedirs(directory, exist_ok=True)
