# AI-Powered Smart Road & Pothole Monitoring System

A production-grade web application for municipal road maintenance that automates the complete lifecycle:
**Detect → Analyze → Prioritize → Report → Assign → Repair → Verify → Close**

---

## 🌟 Key Features

1. **AI Pothole Detection & Tracking Engine**:
   - Reuses trained YOLO model weights (`best.pt`).
   - Supports Single Image Inspection, Video Stream Frame-by-Frame Object Tracking, and Live Webcam Stream (MJPEG over HTTP).
   - Draws bounding boxes, confidence score, estimated dimensions ($W \times H$), surface area ($px^2$).

2. **Scoring & Telemetry Engines**:
   - **Severity Score ($0\text{--}100$)**: Multi-factor engine considering box surface area ratio, detection confidence, and cluster density.
   - **Repair Priority Score ($0\text{--}100$)**: Evaluates severity, risk level, road importance, spatial density, and unresolved issue age.
   - **Road Health Score ($0\text{--}100$)**: Aggregates telemetry across road segments into `GOOD`, `MODERATE`, `POOR`, or `CRITICAL`.
   - **Duplicate Detection**: Deduplicates repeated detections using GPS proximity threshold ($\le 15$m).

3. **Municipal Work Order & AI Repair Verification**:
   - Assign work orders to field officers with deadlines.
   - Field officer uploads repair proof photos ("After Image").
   - AI Model re-evaluates the repair photo: Marks **REPAIR VERIFIED** if fixed or **VERIFICATION FAILED** if damage persists.

4. **GIS Interactive Mapping & Hotspot Detection**:
   - Interactive Leaflet.js map with color-coded risk markers.
   - Automatic spatial density clustering discovering **Pothole Hotspot Zones**.

5. **Citizen Complaint Portal**:
   - Allows citizens to submit photos and location details with instant AI verification ($CMP\text{-}2026\text{-}00125$).

6. **Professional PDF & CSV Reports**:
   - Generates multi-page ReportLab PDF inspection reports with evidence tables.
   - Structured CSV telemetry data export.

---

## 🛠️ System Architecture

```text
smart-pothole-system/
├── backend/
│   ├── app.py                      # Flask REST App entry point & static file server
│   ├── config.py                   # Environment settings & configurable thresholds
│   ├── database.py                 # SQLite database connection & initial seed data
│   ├── ai/
│   │   ├── detector.py             # YOLO detector (best.pt loader)
│   │   ├── severity.py             # 0-100 severity calculation engine
│   │   ├── tracking.py             # Video object tracking engine
│   │   └── duplicate_detection.py  # Spatial deduplication logic
│   ├── services/
│   │   ├── priority_service.py     # Repair Priority & Road Health algorithms
│   │   ├── hotspot_service.py      # Spatial density clustering
│   │   ├── escalation_service.py   # Overdue alert escalation engine
│   │   └── report_service.py       # PDF & CSV generator
│   └── routes/                     # Modular REST API Blueprints
├── frontend/                       # Vanilla JS + HTML5 + CSS3 Dashboard
├── database/                       # SQLite database file (pothole.db)
├── uploads/                        # Detection evidence images & videos
├── reports/                        # Exported PDF & CSV reports
├── best.pt                         # Trained YOLO model weights
└── requirements.txt
```

---

## 🚀 Quick Setup & Execution

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start Flask Server
```bash
python backend/app.py
```

### 3. Access Web Application
Open your web browser and navigate to:
```text
http://127.0.0.1:5000
```

---

## 🔑 Default Sign-in Credentials

- **Admin**: `admin@city.gov` / `admin123`
- **Municipality Officer**: `officer@city.gov` / `officer123`
- **Field Officer**: `field07@city.gov` / `field123`
- **Citizen**: `citizen@gmail.com` / `citizen123`
