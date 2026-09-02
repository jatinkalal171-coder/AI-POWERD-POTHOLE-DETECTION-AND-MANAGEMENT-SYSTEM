import os
import cv2
import time
import datetime
import numpy as np
from ultralytics import YOLO
from backend.config import MODEL_PATH, CONFIDENCE_THRESHOLD, NMS_IOU_THRESHOLD, MIN_POTHOLE_AREA, MAX_POTHOLE_AREA, MAX_POTHOLE_FRAME_RATIO, DETECTIONS_DIR
from backend.ai.severity import calculate_severity_score
from backend.ai.distance_estimator import estimate_pothole_distance

class PotholeDetector:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PotholeDetector, cls).__new__(cls)
            cls._instance.model = None
            cls._instance._load_model()
        return cls._instance

    def _load_model(self):
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"YOLO Model file not found at path: {MODEL_PATH}")
        print(f"[INFO] Loading YOLO Model from {MODEL_PATH}...")
        self.model = YOLO(MODEL_PATH)
        self.model_names = self.model.names if hasattr(self.model, 'names') else {}
        
        # Identify pothole class indices strictly
        self.pothole_class_ids = []
        if self.model_names:
            for c_id, name in self.model_names.items():
                if "pothole" in str(name).lower():
                    self.pothole_class_ids.append(int(c_id))
        if not self.pothole_class_ids:
            self.pothole_class_ids = [0]

    def reset_tracker(self):
        """Reset internal Ultralytics tracker state if initialized."""
        try:
            if hasattr(self.model, 'predictor') and self.model.predictor is not None:
                if hasattr(self.model.predictor, 'trackers'):
                    self.model.predictor.trackers = []
        except Exception:
            pass

    def detect_frame(self, frame, tracking=False, temporal_buffer=None):
        """
        Run inference on a single OpenCV BGR image frame with strict class filtering (>= 0.70 conf), 
        distance estimation, and temporal confirmation buffer.
        """
        frame_h, frame_w = frame.shape[:2]
        frame_area = frame_h * frame_w

        if tracking:
            results = self.model.track(
                frame, 
                persist=True, 
                verbose=False, 
                conf=CONFIDENCE_THRESHOLD, 
                iou=NMS_IOU_THRESHOLD,
                classes=self.pothole_class_ids
            )
        else:
            results = self.model(
                frame, 
                verbose=False, 
                conf=CONFIDENCE_THRESHOLD, 
                iou=NMS_IOU_THRESHOLD,
                classes=self.pothole_class_ids
            )

        detections = []
        annotated_frame = frame.copy()
        
        if not results or len(results[0].boxes) == 0:
            if temporal_buffer:
                temporal_buffer.process_frame_detections([])
            return annotated_frame, detections

        boxes = results[0].boxes
        box_count = len(boxes)

        for i, box in enumerate(boxes):
            cls_id = int(box.cls[0])
            conf_percent = float(box.conf[0]) * 100
            class_name = self.model_names.get(cls_id, "").lower() if self.model_names else ""
            
            # Enforce 70.0% minimum confidence & strict class filtering
            if conf_percent < 70.0:
                continue
            if cls_id not in self.pothole_class_ids and "pothole" not in class_name:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            width = x2 - x1
            height = y2 - y1
            area = width * height

            if area < MIN_POTHOLE_AREA or area > MAX_POTHOLE_AREA or (frame_area > 0 and (area / frame_area) > MAX_POTHOLE_FRAME_RATIO):
                continue

            # Calculate severity score & risk
            sev_data = calculate_severity_score(
                box_area=area,
                frame_area=frame_area,
                confidence_percent=conf_percent,
                nearby_count=box_count - 1
            )

            # Monocular perspective ground-plane distance estimation
            dist_data = estimate_pothole_distance([x1, y1, x2, y2], frame.shape)

            track_id = int(box.id[0]) if (box.id is not None) else (i + 1)

            det_info = {
                "id": track_id,
                "confidence": round(conf_percent, 1),
                "bbox": [x1, y1, x2, y2],
                "width": width,
                "height": height,
                "area": area,
                "severity_score": sev_data["severity_score"],
                "risk_level": sev_data["risk_level"],
                "color_hex": sev_data["color_hex"],
                "color_bgr": sev_data["color_bgr"],
                "estimated_distance": dist_data["distance_meters"],
                "distance_meters": dist_data["distance_meters"],
                "distance_str": dist_data["distance_str"],
                "distance_reliability": dist_data["reliability"],
                "distance_warning": dist_data.get("warning"),
                "confirmation_status": "CONFIRMED"
            }
            detections.append(det_info)

        # Process temporal confirmation buffer if provided
        if temporal_buffer:
            detections = temporal_buffer.process_frame_detections(detections)

        # Draw annotated bounding boxes with real-time status overlay
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            conf = det["confidence"]
            status = det.get("confirmation_status", "CONFIRMED")
            dist_str = det.get("distance_str", "N/A")
            rel = det.get("distance_reliability", "Medium")

            # Color coding: Yellow for CANDIDATE / SCANNING, Severity color for CONFIRMED
            if status in ["SCANNING", "CANDIDATE"]:
                box_color = (0, 255, 255)  # Bright Yellow BGR
            else:
                box_color = det["color_bgr"]

            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), box_color, 3)

            # Overlay labels: Explicitly label "Estimated Distance" as requested
            if det.get("estimated_distance") is not None:
                line1 = f"Pothole {conf:.0f}% | Estimated Distance: {dist_str}"
            else:
                line1 = f"Pothole {conf:.0f}% | {dist_str}"
                
            line2 = f"[{status}] Sev:{det['severity_score']} ({rel})"
            
            (tw1, th1), _ = cv2.getTextSize(line1, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            (tw2, th2), _ = cv2.getTextSize(line2, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            bg_w = max(tw1, tw2) + 8
            bg_h = th1 + th2 + 10

            bg_y1 = max(y1 - bg_h - 4, 0)
            cv2.rectangle(annotated_frame, (x1, bg_y1), (x1 + bg_w, bg_y1 + bg_h), box_color, -1)
            
            # Text lines inside label box
            cv2.putText(annotated_frame, line1, (x1 + 4, bg_y1 + th1 + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
            cv2.putText(annotated_frame, line2, (x1 + 4, bg_y1 + th1 + th2 + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

        return annotated_frame, detections

    def detect_image_file(self, image_path, save_annotated=True):
        """
        Process an image file from disk and return detection results & saved evidence path.
        """
        frame = cv2.imread(image_path)
        if frame is None:
            raise ValueError(f"Could not read image at path: {image_path}")

        annotated_frame, detections = self.detect_frame(frame, tracking=False)

        annotated_path = None
        if save_annotated:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"detection_{stamp}.jpg"
            annotated_path = os.path.join(DETECTIONS_DIR, filename)
            cv2.imwrite(annotated_path, annotated_frame)

        return {
            "total_potholes": len(detections),
            "detections": detections,
            "annotated_image_path": annotated_path,
            "original_image_path": image_path
        }

# Global singleton helper
def get_detector():
    return PotholeDetector()
