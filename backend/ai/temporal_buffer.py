import time
import numpy as np

def calculate_iou(boxA, boxB):
    """Calculate Intersection over Union (IOU) between two bounding boxes [x1, y1, x2, y2]."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    denominator = float(boxAArea + boxBArea - interArea)
    if denominator <= 0:
        return 0.0
    return interArea / denominator


class TemporalConfirmationBuffer:
    """
    Sliding window temporal confirmation buffer for live camera feeds.
    
    Prevents single-frame false positives by requiring a pothole to be detected 
    consistently across multiple frames (at least 3 hits out of latest 5 frames)
    before marking status as 'CONFIRMED'.
    """
    def __init__(self, window_size=5, min_confirmed_hits=3, iou_threshold=0.30):
        self.window_size = window_size
        self.min_confirmed_hits = min_confirmed_hits
        self.iou_threshold = iou_threshold
        self.tracks = {}  # track_id -> dict
        self.next_track_id = 1

    def reset(self):
        """Reset all tracked candidates."""
        self.tracks = {}
        self.next_track_id = 1

    def process_frame_detections(self, frame_detections):
        """
        Process raw frame detections and return updated detections annotated with 
        temporal status ('SCANNING', 'CANDIDATE', 'CONFIRMED') and track IDs.
        """
        # Mark all existing tracks as missed in current frame initially
        for t_id, track in self.tracks.items():
            track['history'].append(0)  # 0 hit for this frame
            if len(track['history']) > self.window_size:
                track['history'].pop(0)
            track['missed_frames'] += 1

        matched_det_indices = set()
        matched_track_ids = set()

        # Match current detections with active tracks using IOU
        for det_idx, det in enumerate(frame_detections):
            bbox = det['bbox']
            best_iou = 0.0
            best_t_id = None

            for t_id, track in self.tracks.items():
                if t_id in matched_track_ids:
                    continue
                iou = calculate_iou(bbox, track['last_bbox'])
                if iou > best_iou and iou >= self.iou_threshold:
                    best_iou = iou
                    best_t_id = t_id

            if best_t_id is not None:
                # Match found! Update track state
                track = self.tracks[best_t_id]
                track['last_bbox'] = bbox
                track['confidence'] = det['confidence']
                track['history'][-1] = 1  # Change last missed frame (0) to hit (1)
                track['missed_frames'] = 0
                det['track_id'] = best_t_id
                matched_det_indices.add(det_idx)
                matched_track_ids.add(best_t_id)

        # Create new tracks for unmatched detections
        for det_idx, det in enumerate(frame_detections):
            if det_idx not in matched_det_indices:
                t_id = self.next_track_id
                self.next_track_id += 1
                
                self.tracks[t_id] = {
                    'track_id': t_id,
                    'last_bbox': det['bbox'],
                    'confidence': det['confidence'],
                    'history': [1],  # 1 hit in first frame
                    'missed_frames': 0
                }
                det['track_id'] = t_id

        # Purge stale tracks missed for > 3 consecutive frames
        stale_ids = [t_id for t_id, tr in self.tracks.items() if tr['missed_frames'] >= 3]
        for t_id in stale_ids:
            del self.tracks[t_id]

        # Calculate temporal confirmation status for each current detection
        annotated_detections = []
        for det in frame_detections:
            t_id = det.get('track_id')
            if t_id and t_id in self.tracks:
                hits = sum(self.tracks[t_id]['history'])
                total_window = len(self.tracks[t_id]['history'])
                
                if hits >= self.min_confirmed_hits:
                    status = "CONFIRMED"
                elif hits == 2:
                    status = "CANDIDATE"
                else:
                    status = "SCANNING"
                    
                det['confirmation_status'] = status
                det['temporal_hits'] = hits
                det['temporal_window'] = total_window
                det['is_confirmed'] = (status == "CONFIRMED")
                annotated_detections.append(det)

        return annotated_detections
