import os
import sys
import cv2
import csv
import time
import datetime
import numpy as np


from backend.ai.distance_estimator import estimate_pothole_distance

CONFIDENCE_THRESHOLD = 0.40
NMS_IOU_THRESHOLD = 0.45
TARGET_CLASS_ID = 0           
TARGET_CLASS_KEYWORD = "pothole" 

# Area limits (in pixels)
MIN_POTHOLE_AREA = 1200       
MAX_POTHOLE_AREA = 250000     

# File structure setup
OUTPUT_DIR = "output"
VIDEOS_DIR = os.path.join(OUTPUT_DIR, "videos")
SCREENSHOTS_DIR = os.path.join(OUTPUT_DIR, "screenshots")
REPORTS_DIR = os.path.join(OUTPUT_DIR, "reports")
CSV_PATH = os.path.join(REPORTS_DIR, "report.csv")

for directory in [OUTPUT_DIR, VIDEOS_DIR, SCREENSHOTS_DIR, REPORTS_DIR]:
    os.makedirs(directory, exist_ok=True)


def calculate_risk(conf_percent):
    """Categorize pothole severity based on confidence score."""
    if conf_percent < 50.0:
        return "LOW", (0, 255, 255)       # Yellow
    elif conf_percent <= 75.0:
        return "MEDIUM", (0, 165, 255)    # Orange
    else:
        return "HIGH", (0, 0, 255)        # Red


def draw_hud(frame, fps, road_cond, active_count, unique_total, is_recording):
    """Draw a professional semi-transparent dashboard HUD overlay."""
    h, w = frame.shape[:2]
    
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (320, 160), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    
    cond_color = (0, 255, 0) if road_cond == "GOOD" else (0, 165, 255) if road_cond == "MODERATE" else (0, 0, 255)
    
    cv2.putText(frame, f"FPS: {fps:.1f}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    cv2.putText(frame, f"Road Status: {road_cond}", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cond_color, 2)
    cv2.putText(frame, f"Visible Potholes: {active_count}", (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    cv2.putText(frame, f"Total Unique Tracked: {unique_total}", (20, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    cv2.putText(frame, "[Q] Quit  [S] Save Shot  [R] Rec Toggle", (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

    if is_recording:
        cv2.circle(frame, (w - 30, 30), 8, (0, 0, 255), -1)
        cv2.putText(frame, "REC", (w - 75, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)


# ---------------------------------------------------------
# REPORT GENERATORS (CSV & PDF)
# ---------------------------------------------------------
def generate_csv_report(final_detections):
    """Generate a clean CSV report with ONLY final unique detections including Estimated_Distance_Meters."""
    try:
        with open(CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Complaint_ID", "Confidence Score", 
                "Box X", "Box Y", "Width", "Height", 
                "Estimated_Distance_Meters", "Risk Level"
            ])
            
            for d in final_detections.values():
                dist_str = f"{d['dist_meters']:.1f}" if d.get('dist_meters') is not None else "N/A"
                writer.writerow([
                    f"PT-{d['id']:04d}", 
                    f"{d['conf']:.1f}%", 
                    d['x'], d['y'], d['w'], d['h'], 
                    dist_str,
                    d['risk']
                ])
        return True
    except Exception as e:
        print(f"[ERROR] Failed to write CSV report: {e}")
        return False

def generate_pdf_report(final_detections, final_road_cond, mode_name):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
    except ImportError:
        print("[ERROR] ReportLab module missing. PDF will not be generated.")
        return None

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = os.path.join(REPORTS_DIR, f"Inspection_Report_{stamp}.pdf")
    
    total_unique = len(final_detections)
    risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    highest_conf = 0.0
    avg_conf = 0.0
    
    if total_unique > 0:
        highest_conf = max(d['conf'] for d in final_detections.values())
        avg_conf = sum(d['conf'] for d in final_detections.values()) / total_unique
        for d in final_detections.values():
            risk_counts[d['risk']] += 1

    try:
        doc = SimpleDocTemplate(pdf_path, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph("AI Pothole Inspection Report", styles['Title']))
        elements.append(Spacer(1, 20))

        data = [
            ["Project Title", "Automated Road Damage Assessment"],
            ["Inspection Date & Time", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ["Inspection Mode", mode_name],
            ["Total Unique Potholes", str(total_unique)],
            ["Highest Confidence", f"{highest_conf:.1f}%"],
            ["Average Confidence", f"{avg_conf:.1f}%"],
            ["Overall Road Condition", final_road_cond],
            ["Low Risk Count", str(risk_counts["LOW"])],
            ["Medium Risk Count", str(risk_counts["MEDIUM"])],
            ["High Risk Count", str(risk_counts["HIGH"])],
        ]

        t = Table(data, colWidths=[200, 250])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('GRID', (0, 0), (-1, -1), 1, colors.white),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 25))

        elements.append(Paragraph("Summary", styles['Heading2']))
        summary_text = (f"The automated inspection was conducted in {mode_name} mode. "
                        f"The AI model successfully identified {total_unique} unique potholes during the session. "
                        f"Based on the aggregate severity, the overall road condition is classified as {final_road_cond}.")
        elements.append(Paragraph(summary_text, styles['Normal']))
        elements.append(Spacer(1, 15))

        elements.append(Paragraph("Recommendations", styles['Heading2']))
        if final_road_cond == "GOOD":
            rec = "No immediate major maintenance is required. Routine periodic monitoring is recommended."
        elif final_road_cond == "MODERATE":
            rec = "Schedule targeted maintenance for medium and high-risk potholes to prevent further structural degradation."
        else:
            rec = "Urgent repair required. Immediate intervention is highly advised for all high-risk damage areas to ensure road safety."
        elements.append(Paragraph(rec, styles['Normal']))

        doc.build(elements)
        return pdf_path
    
    except Exception as e:
        print(f"[ERROR] Failed to generate PDF report: {e}")
        return None


# ---------------------------------------------------------
# MAIN PROGRAM PIPELINE
# ---------------------------------------------------------
def main():
    try:
        from ultralytics import YOLO
    except ImportError:
        print("[ERROR] Ultralytics module missing.")
        return

    model_path = "best.pt"
    if not os.path.exists(model_path):
        print(f"[ERROR] Could not locate custom weights file '{model_path}'.")
        return

    print("[INFO] Loading YOLO Neural Network Model...")
    model = YOLO(model_path)
    model_names = model.names if hasattr(model, 'names') else {}

    print("\n" + "="*45)
    print("   AI POTHOLE DETECTION & AUDIT SYSTEM   ")
    print("="*45)
    print("1. Webcam Stream (Live)")
    print("2. Video File Inspection")
    print("3. Single Image Analysis")
    
    choice = input("\nSelect execution mode (1-3): ").strip()
    
    source = None
    mode_name = ""
    is_image = False
    
    if choice == '1':
        source = 0
        mode_name = "Webcam"
    elif choice == '2':
        source = input("Enter video filepath: ").strip('"').strip("'")
        mode_name = "Video"
    elif choice == '3':
        source = input("Enter image filepath: ").strip('"').strip("'")
        mode_name = "Image"
        is_image = True
    else:
        print("[ERROR] Invalid choice selected.")
        return

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print("[ERROR] Cannot connect to video stream or file source.")
        return
    
    final_detections = {}
    
    is_recording = False
    video_writer = None
    last_saved_video = None
    last_saved_screenshot = None
    
    print("\n[INFO] Video stream started.")
    print("[INFO] Ensure the OpenCV window is focused for key controls to work:")
    print("       'Q' or ESC = Exit | 'S' = Take Screenshot | 'R' = Toggle Recording\n")

    prev_time = time.time()
    
    # Used to hold the image frame in memory for Mode 3 so keys work properly
    image_cache = None 

    while True:
        if is_image:
            if image_cache is None:
                ret, frame = cap.read()
                if not ret: break
                image_cache = frame.copy()
            else:
                frame = image_cache.copy()
                ret = True
            
            # Reset ID counter har image loop me taaki duplicate add na ho.
            # Ye ensure karega ki agar 4 pothole hain, toh CSV me exactly 4 rows hi banengi.
            image_pothole_counter = 1
        else:
            ret, frame = cap.read()
            if not ret:
                print("[INFO] Reached end of video feed.")
                break

        frame_h, frame_w = frame.shape[:2]
        
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0.0
        prev_time = curr_time

        results = model.track(frame, persist=True, verbose=False, conf=CONFIDENCE_THRESHOLD, iou=NMS_IOU_THRESHOLD, classes=[TARGET_CLASS_ID])
        active_potholes_in_frame = 0

        if results and len(results[0].boxes) > 0:
            boxes = results[0].boxes
            
            for box in boxes:
                cls_id = int(box.cls[0])
                conf_percent = float(box.conf[0]) * 100
                
                class_name = model_names.get(cls_id, "").lower() if model_names else ""
                if TARGET_CLASS_KEYWORD not in class_name and cls_id != TARGET_CLASS_ID:
                    continue
                
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                width = x2 - x1
                height = y2 - y1
                area = width * height
                
                if area < MIN_POTHOLE_AREA or area > MAX_POTHOLE_AREA:
                    continue

                active_potholes_in_frame += 1
                risk_level, color_bgr = calculate_risk(conf_percent)
                
                # Monocular ground-plane distance estimation
                dist_data = estimate_pothole_distance([x1, y1, x2, y2], frame.shape)
                dist_str = dist_data["distance_str"]
                dist_meters = dist_data["distance_meters"]

                if is_image:
                    uid = image_pothole_counter
                    image_pothole_counter += 1
                else:
                    uid = int(box.id[0]) if box.id is not None else -1
                
                if uid != -1:
                    if uid not in final_detections or conf_percent > final_detections[uid]['conf']:
                        final_detections[uid] = {
                            'id': uid,
                            'conf': conf_percent,
                            'x': x1, 'y': y1,
                            'w': width, 'h': height,
                            'risk': risk_level,
                            'dist_meters': dist_meters,
                            'dist_str': dist_str
                        }

                cv2.rectangle(frame, (x1, y1), (x2, y2), color_bgr, 2)
                
                id_str = f"ID:{uid} | " if uid != -1 else ""
                label = f"{id_str}Pothole {conf_percent:.0f}% | Estimated Distance: {dist_str}"
                
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                cv2.rectangle(frame, (x1, max(y1 - 20, 0)), (x1 + tw + 4, max(y1, 20)), color_bgr, -1)
                cv2.putText(frame, label, (x1 + 2, max(y1 - 5, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)

        unique_total = len(final_detections)
        road_condition = "GOOD" if active_potholes_in_frame == 0 else "MODERATE" if active_potholes_in_frame <= 2 else "DAMAGED"

        draw_hud(frame, fps, road_condition, active_potholes_in_frame, unique_total, is_recording)

        if is_recording and video_writer:
            video_writer.write(frame)

        cv2.imshow("AI Pothole Inspection Engine", frame)

        # ---------------------------------------------------------
        # CROSS-PLATFORM KEYPRESS HANDLING
        # ---------------------------------------------------------
        delay = 0 if is_image else 1
        key = cv2.waitKey(delay) & 0xFF
        
        if key in [ord('q'), ord('Q'), 27]:
            print("\n[INFO] Termination command received. Closing...")
            break
            
        elif key in [ord('s'), ord('S')]:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            last_saved_screenshot = os.path.join(SCREENSHOTS_DIR, f"screenshot_{stamp}.jpg")
            cv2.imwrite(last_saved_screenshot, frame)
            print(f"[SUCCESS] Screenshot saved: {last_saved_screenshot}")
            
        elif key in [ord('r'), ord('R')] and not is_image:
            if is_recording:
                is_recording = False
                if video_writer:
                    video_writer.release()
                    video_writer = None
                print(f"[SUCCESS] Video recording stopped and saved: {last_saved_video}")
            else:
                is_recording = True
                stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                # Changed from .mp4 to .avi (XVID) for 100% OpenCV compatibility without bugs
                last_saved_video = os.path.join(VIDEOS_DIR, f"recording_{stamp}.avi")
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                video_writer = cv2.VideoWriter(last_saved_video, fourcc, 20.0, (frame_w, frame_h))
                print(f"[ACTION] Video recording STARTED...")

    cap.release()
    if video_writer:
        video_writer.release()
    cv2.destroyAllWindows()

    # ---------------------------------------------------------
    # FINAL REPORT COMPILATION & SUMMARY
    # ---------------------------------------------------------
    final_unique = len(final_detections)
    if final_unique == 0:
        final_road_condition = "GOOD"
    elif final_unique <= 3:
        final_road_condition = "MODERATE"
    else:
        final_road_condition = "CRITICAL / DAMAGED"
        
    highest_confidence_session = max((d['conf'] for d in final_detections.values()), default=0.0)

    # Dono reports generate ho rahi hain unhi exact detections se (duplicate proof)
    generate_csv_report(final_detections)
    pdf_report_path = generate_pdf_report(
        final_detections=final_detections,
        final_road_cond=final_road_condition,
        mode_name=mode_name
    )

    print("\n" + "="*40)
    print("    AI POTHOLE INSPECTION COMPLETED")
    print("="*40)
    print(f"Total Unique Potholes : {final_unique}")
    print(f"Highest Confidence    : {highest_confidence_session:.1f}%")
    print(f"Road Condition        : {final_road_condition}")
    print(f"CSV Report Saved      : {CSV_PATH}")
    print(f"PDF Report Saved      : {pdf_report_path if pdf_report_path else 'Failed to create'}")
    print(f"Screenshot Folder     : {SCREENSHOTS_DIR}")
    print(f"Video Folder          : {VIDEOS_DIR}")
    print("="*40 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Session ended manually.")
        cv2.destroyAllWindows()
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Runtime exception: {e}")
        cv2.destroyAllWindows()
        sys.exit(1)