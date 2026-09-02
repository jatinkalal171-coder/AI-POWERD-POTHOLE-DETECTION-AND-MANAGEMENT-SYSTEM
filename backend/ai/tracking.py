import os
import cv2
import datetime
from backend.ai.detector import get_detector
from backend.config import VIDEOS_DIR, DETECTIONS_DIR

def process_video_stream(video_path, progress_callback=None):
    """
    Process an input video file, run frame tracking, count unique potholes,
    generate annotated video & keyframe snapshot, and return aggregate statistics.
    """
    detector = get_detector()
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        raise ValueError(f"Unable to open video file at: {video_path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    if fps <= 0 or fps > 120:
        fps = 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Read first frame if dimensions missing
    if width <= 0 or height <= 0:
        ret, test_frame = cap.read()
        if ret and test_frame is not None:
            height, width = test_frame.shape[:2]
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        else:
            width, height = 1280, 720

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_filename = f"processed_{stamp}.mp4"
    out_path = os.path.join(VIDEOS_DIR, out_filename)
    keyframe_filename = f"keyframe_{stamp}.jpg"
    keyframe_path = os.path.join(DETECTIONS_DIR, keyframe_filename)

    # Attempt VideoWriter codecs gracefully
    out = None
    for codec in ['mp4v', 'avc1', 'XVID', 'MJPG']:
        try:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            test_out = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
            if test_out.isOpened():
                out = test_out
                break
        except Exception:
            continue

    unique_detections = {}
    frame_count = 0
    best_keyframe = None
    max_dets_in_frame = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        frame_count += 1
        annotated_frame, frame_dets = detector.detect_frame(frame, tracking=True)

        if len(frame_dets) > max_dets_in_frame or (best_keyframe is None and frame_count == 1):
            max_dets_in_frame = len(frame_dets)
            best_keyframe = annotated_frame.copy()

        for d in frame_dets:
            uid = d['id']
            if uid not in unique_detections or d['confidence'] > unique_detections[uid]['confidence']:
                unique_detections[uid] = d

        if out and out.isOpened():
            try:
                out.write(annotated_frame)
            except Exception:
                pass

        if progress_callback and total_frames > 0 and frame_count % 10 == 0:
            pct = int((frame_count / total_frames) * 100)
            progress_callback(pct, frame_count, total_frames)

    cap.release()
    if out:
        out.release()

    # Save keyframe image for HTML5 frontend fallback
    if best_keyframe is not None:
        cv2.imwrite(keyframe_path, best_keyframe)
    else:
        keyframe_path = None

    total_unique = len(unique_detections)
    risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    total_conf = 0.0

    for d in unique_detections.values():
        risk_counts[d['risk_level']] = risk_counts.get(d['risk_level'], 0) + 1
        total_conf += d['confidence']

    avg_conf = (total_conf / total_unique) if total_unique > 0 else 0.0

    return {
        "total_frames_processed": frame_count,
        "unique_pothole_count": total_unique,
        "average_confidence": round(avg_conf, 1),
        "risk_breakdown": risk_counts,
        "unique_detections": list(unique_detections.values()),
        "output_video_path": out_path if (out and os.path.exists(out_path) and os.path.getsize(out_path) > 0) else None,
        "keyframe_image_path": keyframe_path
    }
