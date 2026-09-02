let localStream = null;
let frameInterval = null;
let isProcessingFrame = false;

let userLat = 20.5937;
let userLng = 78.9629;
let consecutiveDetections = 0;
let lastDBSaveTime = 0;

document.addEventListener('DOMContentLoaded', () => {
  requireAuth();
  updateCamUI('STOPPED');
});

async function startCamera() {
  const errorBox = document.getElementById('camera-error-msg');
  errorBox.style.display = 'none';
  errorBox.textContent = '';

  // Get initial geolocation if browser supports it
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        userLat = pos.coords.latitude;
        userLng = pos.coords.longitude;
      },
      (err) => console.log('Geolocation fallback used: ', err),
      { timeout: 5000 }
    );
  }

  try {
    // Request webcam access from browser
    localStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" }
    });

    const videoElem = document.getElementById('webcam-video');
    videoElem.srcObject = localStream;
    await videoElem.play();

    updateCamUI('RUNNING');

    // Create hidden processing canvas
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    consecutiveDetections = 0;
    lastDBSaveTime = 0;

    // Start continuous frame processing (every 200ms)
    frameInterval = setInterval(async () => {
      if (!localStream || isProcessingFrame) return;

      if (videoElem.videoWidth === 0 || videoElem.videoHeight === 0) return;

      canvas.width = videoElem.videoWidth;
      canvas.height = videoElem.videoHeight;
      ctx.drawImage(videoElem, 0, 0, canvas.width, canvas.height);

      const base64Image = canvas.toDataURL('image/jpeg', 0.92);

      const now = Date.now();
      // Throttle DB save: at least 10 consecutive frame detections (2s) AND at least 10s between saves
      const shouldAttemptSave = (consecutiveDetections >= 10) && (now - lastDBSaveTime >= 10000);

      isProcessingFrame = true;
      try {
        const response = await fetch('/api/detect/frame', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            image_data: base64Image,
            save_to_db: shouldAttemptSave,
            latitude: userLat,
            longitude: userLng,
            road_name: 'Live AI Webcam Feed'
          })
        });

        if (response.ok) {
          const data = await response.json();
          if (data.success && data.annotated_frame) {
            const streamImg = document.getElementById('processed-stream-img');
            streamImg.src = data.annotated_frame;
            streamImg.style.display = 'block';

            if (data.total_detected > 0) {
              consecutiveDetections++;
            } else {
              consecutiveDetections = 0;
            }

            const countBadge = document.getElementById('detected-count-badge');
            if (countBadge) {
              const confCount = data.confirmed_count || 0;
              const candCount = (data.candidate_count || 0) + (data.scanning_count || 0);
              countBadge.innerHTML = `Confirmed: <strong style="color:#2ecc71;">${confCount}</strong> | Candidates: <strong style="color:#f1c40f;">${candCount}</strong>`;
            }

            if (data.saved_to_db && data.saved_pothole_ids && data.saved_pothole_ids.length > 0) {
              lastDBSaveTime = Date.now();
              consecutiveDetections = 0;
              showToast(`💾 Live Detection Saved to DB! (${data.saved_pothole_ids.join(', ')})`, 'success');
            }
          }
        }
      } catch (err) {
        console.error('Frame processing error:', err);
      } finally {
        isProcessingFrame = false;
      }
    }, 200);

    showToast('Live Camera started successfully', 'success');
  } catch (err) {
    console.error('Camera access error:', err);
    updateCamUI('STOPPED');
    
    errorBox.style.display = 'block';
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      errorBox.innerHTML = '⚠️ <strong>Camera Permission Denied:</strong> Please allow camera access in your browser settings to use live AI detection.';
    } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
      errorBox.innerHTML = '⚠️ <strong>No Camera Found:</strong> No webcam or camera device was detected on your system.';
    } else {
      errorBox.innerHTML = `⚠️ <strong>Camera Error:</strong> ${err.message || 'Unable to access camera.'}`;
    }
    showToast('Failed to access camera', 'error');
  }
}

function stopCamera() {
  // 1. Stop all media tracks completely
  if (localStream) {
    localStream.getTracks().forEach(track => {
      track.stop();
    });
    localStream = null;
  }

  // 2. Clear frame processing intervals
  if (frameInterval) {
    clearInterval(frameInterval);
    frameInterval = null;
  }

  isProcessingFrame = false;

  // 3. Clear video state & canvas
  const videoElem = document.getElementById('webcam-video');
  if (videoElem) {
    videoElem.pause();
    videoElem.srcObject = null;
  }

  const streamImg = document.getElementById('processed-stream-img');
  if (streamImg) {
    streamImg.removeAttribute('src');
    streamImg.style.display = 'none';
  }

  const countBadge = document.getElementById('detected-count-badge');
  if (countBadge) {
    countBadge.textContent = 'Camera Offline';
  }

  updateCamUI('STOPPED');
  showToast('Live Camera stopped', 'info');
}

function updateCamUI(status) {
  const startBtn = document.getElementById('start-cam-btn');
  const stopBtn = document.getElementById('stop-cam-btn');
  const compareBtn = document.getElementById('compare-cam-btn');
  const liveIndicator = document.getElementById('live-indicator');
  const placeholderBox = document.getElementById('cam-placeholder-box');
  const streamImg = document.getElementById('processed-stream-img');

  if (status === 'RUNNING') {
    startBtn.disabled = true;
    stopBtn.disabled = false;
    if (compareBtn) compareBtn.disabled = false;
    liveIndicator.style.display = 'flex';
    placeholderBox.style.display = 'none';
  } else {
    startBtn.disabled = false;
    stopBtn.disabled = true;
    if (compareBtn) compareBtn.disabled = true;
    liveIndicator.style.display = 'none';
    placeholderBox.style.display = 'flex';
    if (streamImg) streamImg.style.display = 'none';
  }
}

async function runConsistencyCheck() {
  const videoElem = document.getElementById('webcam-video');
  if (!localStream || videoElem.videoWidth === 0 || videoElem.videoHeight === 0) {
    showToast('Start camera first to test frame consistency', 'warning');
    return;
  }

  const compareBtn = document.getElementById('compare-cam-btn');
  if (compareBtn) compareBtn.disabled = true;

  try {
    const canvas = document.createElement('canvas');
    canvas.width = videoElem.videoWidth;
    canvas.height = videoElem.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoElem, 0, 0, canvas.width, canvas.height);

    const base64Image = canvas.toDataURL('image/jpeg', 0.92);

    const res = await fetch('/api/detect/compare_frame', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_data: base64Image })
    });

    if (res.ok) {
      const data = await res.json();
      if (data.success) {
        if (data.is_identical) {
          showToast(`✅ PERFECT CONSISTENCY! Live (${data.live_count}) == Static (${data.static_count}) detections.`, 'success');
        } else {
          showToast(`⚠️ Discrepancy: Live (${data.live_count}) vs Static (${data.static_count}).`, 'warning');
        }
      }
    }
  } catch (err) {
    console.error('Consistency check failed:', err);
    showToast('Failed to run consistency check', 'error');
  } finally {
    if (compareBtn) compareBtn.disabled = false;
  }
}

