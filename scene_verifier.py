import os
import cv2
import numpy as np
from backend.config import SCENE_MATCH_THRESHOLD_HIGH, SCENE_MATCH_THRESHOLD_LOW

def verify_scene_similarity(before_img_path, after_img_path):
    """
    Compare BEFORE pothole photo vs AFTER repair proof photo using computer vision
    feature descriptor matching and structural scene consistency checks.
    """
    if not before_img_path or not os.path.exists(before_img_path):
        return {
            "similarity_score": 50.0,
            "status": "MANUAL_REVIEW_REQUIRED",
            "reason": "Original BEFORE image not available for comparison. Flagged for manual review."
        }

    if not after_img_path or not os.path.exists(after_img_path):
        return {
            "similarity_score": 0.0,
            "status": "FAILED",
            "reason": "AFTER repair image missing or unreadable."
        }

    img1 = cv2.imread(before_img_path)
    img2 = cv2.imread(after_img_path)

    if img1 is None or img2 is None:
        return {
            "similarity_score": 0.0,
            "status": "FAILED",
            "reason": "Could not decode before or after image files."
        }

    try:
        # Quick check for identical or near-identical images
        if img1.shape == img2.shape:
            mse = np.mean((img1.astype("float") - img2.astype("float")) ** 2)
            if mse < 5.0:
                similarity_score = round(100.0 - (mse * 2.0), 1)
                return {
                    "similarity_score": similarity_score,
                    "status": "VERIFIED",
                    "reason": f"Scene match verified ({similarity_score}% visual consistency with original location)."
                }

        # 1. Color Histogram Similarity (Global scene color/lighting)
        hsv1 = cv2.cvtColor(img1, cv2.COLOR_BGR2HSV)
        hsv2 = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)

        hist1 = cv2.calcHist([hsv1], [0, 1], None, [50, 60], [0, 180, 0, 256])
        hist2 = cv2.calcHist([hsv2], [0, 1], None, [50, 60], [0, 180, 0, 256])

        cv2.normalize(hist1, hist1, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(hist2, hist2, 0, 1, cv2.NORM_MINMAX)

        hist_corr = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORR)
        hist_score = max(0.0, float(hist_corr)) * 100.0

        # 2. ORB Feature Descriptor Match Score (Road edge & structural keypoints)
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

        orb = cv2.ORB_create(nfeatures=500)
        kp1, des1 = orb.detectAndCompute(gray1, None)
        kp2, des2 = orb.detectAndCompute(gray2, None)

        feature_score = 0.0
        if des1 is not None and des2 is not None and len(des1) > 0 and len(des2) > 0:
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(des1, des2)
            matches = sorted(matches, key=lambda x: x.distance)

            good_matches = [m for m in matches if m.distance < 50]
            max_kp = max(len(kp1), len(kp2))
            feature_score = (len(good_matches) / max_kp) * 100.0 if max_kp > 0 else 0.0
            feature_score = min(100.0, feature_score * 3.5) # Scale to percentage range

        # Weighted Scene Similarity Score
        if des1 is None or des2 is None or len(des1) == 0 or len(des2) == 0:
            similarity_score = round(hist_score, 1)
        else:
            similarity_score = round((0.4 * hist_score) + (0.6 * feature_score), 1)

        if similarity_score >= SCENE_MATCH_THRESHOLD_HIGH:
            status = "VERIFIED"
            reason = f"Scene match verified ({similarity_score}% visual consistency with original location)."
        elif similarity_score >= SCENE_MATCH_THRESHOLD_LOW:
            status = "MANUAL_REVIEW_REQUIRED"
            reason = f"Scene match uncertain ({similarity_score}% consistency). Flagged for Municipal Officer review."
        else:
            status = "FAILED"
            reason = f"Scene mismatch ({similarity_score}% consistency). Photo appears unrelated to original road location."

        return {
            "similarity_score": similarity_score,
            "status": status,
            "reason": reason
        }

    except Exception as e:
        return {
            "similarity_score": 30.0,
            "status": "MANUAL_REVIEW_REQUIRED",
            "reason": f"Scene comparison encountered an exception: {e}. Flagged for review."
        }
