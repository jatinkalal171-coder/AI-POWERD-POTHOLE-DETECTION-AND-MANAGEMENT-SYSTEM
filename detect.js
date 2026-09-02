let detectMap = null;
let detectMarker = null;

document.addEventListener('DOMContentLoaded', () => {
  if (typeof requireAuth === 'function') requireAuth();
  initDetectMap();
});

function initDetectMap() {
  const mapContainer = document.getElementById('detect-map');
  if (!mapContainer) return;

  detectMap = L.map('detect-map').setView([20.5937, 78.9629], 5);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(detectMap);

  detectMap.on('click', (e) => {
    const lat = parseFloat(e.latlng.lat.toFixed(6));
    const lng = parseFloat(e.latlng.lng.toFixed(6));
    updateDetectLocation(lat, lng, 'Selected Location Pin');
  });
}

function fetchDetectGPSLocation() {
  const statusBox = document.getElementById('detect-gps-status');
  const btn = document.getElementById('detect-gps-btn');

  if (!navigator.geolocation) {
    showDetectGPSError('Geolocation API is not supported by your browser. Click on the map to set location.');
    return;
  }

  btn.disabled = true;
  btn.textContent = '📍 Acquiring Accurate GPS Coordinates... ⏳';
  statusBox.style.display = 'block';
  statusBox.style.background = 'rgba(59, 130, 246, 0.15)';
  statusBox.style.border = '1px solid var(--accent-blue)';
  statusBox.style.color = 'var(--accent-blue)';
  statusBox.textContent = 'Requesting location permission from browser...';

  navigator.geolocation.getCurrentPosition(
    (position) => {
      btn.disabled = false;
      btn.textContent = '📍 USE MY CURRENT LOCATION';

      const lat = parseFloat(position.coords.latitude.toFixed(6));
      const lng = parseFloat(position.coords.longitude.toFixed(6));

      statusBox.style.background = 'rgba(16, 185, 129, 0.15)';
      statusBox.style.border = '1px solid var(--status-good)';
      statusBox.style.color = 'var(--status-good)';
      statusBox.innerHTML = `✅ <strong>Location Acquired via Device GPS!</strong> (${lat}, ${lng})`;

      updateDetectLocation(lat, lng, 'Your Current GPS Location');
      if (typeof showToast === 'function') showToast('Device GPS location acquired!', 'success');
    },
    (error) => {
      btn.disabled = false;
      btn.textContent = '📍 USE MY CURRENT LOCATION';

      let errorMsg = '⚠️ Location access denied or GPS unavailable.';
      if (error.code === error.PERMISSION_DENIED) {
        errorMsg = '⚠️ <strong>Location Permission Denied:</strong> Please click on the map below to select location manually.';
      } else if (error.code === error.POSITION_UNAVAILABLE) {
        errorMsg = '⚠️ <strong>GPS Signal Unavailable:</strong> Click on the map below to select location manually.';
      } else if (error.code === error.TIMEOUT) {
        errorMsg = '⚠️ <strong>Location Request Timed Out:</strong> Click on the map below to select location manually.';
      }

      showDetectGPSError(errorMsg);
    },
    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0
    }
  );
}

function showDetectGPSError(message) {
  const statusBox = document.getElementById('detect-gps-status');
  if (!statusBox) return;
  statusBox.style.display = 'block';
  statusBox.style.background = 'rgba(239, 68, 68, 0.15)';
  statusBox.style.border = '1px solid var(--status-critical)';
  statusBox.style.color = '#fca5a5';
  statusBox.innerHTML = message;
}

function updateDetectLocation(lat, lng, label) {
  document.getElementById('lat').value = lat;
  document.getElementById('lng').value = lng;

  if (detectMap) {
    detectMap.setView([lat, lng], 16);

    if (detectMarker) {
      detectMarker.setLatLng([lat, lng]);
    } else {
      detectMarker = L.marker([lat, lng]).addTo(detectMap);
    }
    detectMarker.bindPopup(`<b>${label}</b><br>Lat: ${lat}<br>Lng: ${lng}`).openPopup();
  }
}

function switchTab(type) {
  document.getElementById('tab-img-btn').classList.toggle('active', type === 'image');
  document.getElementById('tab-vid-btn').classList.toggle('active', type === 'video');
  document.getElementById('image-upload-form').style.display = type === 'image' ? 'block' : 'none';
  document.getElementById('video-upload-form').style.display = type === 'video' ? 'block' : 'none';
  document.getElementById('form-title').textContent = type === 'image' ? 'Upload Image for AI Inspection' : 'Upload Video for Object Tracking Inspection';
}

function previewSelectedFile(input, targetId) {
  if (input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = (e) => {
      document.getElementById(targetId).src = e.target.result;
      document.getElementById('img-preview-container').style.display = 'block';
    };
    reader.readAsDataURL(input.files[0]);
  }
}

function previewSelectedVideoFile(input) {
  if (input.files && input.files[0]) {
    const videoElem = document.getElementById('vid-preview-tag');
    const container = document.getElementById('vid-preview-container');
    videoElem.src = URL.createObjectURL(input.files[0]);
    container.style.display = 'block';
  }
}

// Single Image Submission Handler
document.getElementById('image-upload-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById('img-file-input');
  if (!fileInput.files[0]) {
    showToast('Please select an image file first', 'warning');
    return;
  }

  const lat = document.getElementById('lat').value;
  const lng = document.getElementById('lng').value;
  if (!lat || !lng) {
    showToast('Please click "USE MY CURRENT LOCATION" or select location on map', 'warning');
    return;
  }

  const formData = new FormData();
  formData.append('image', fileInput.files[0]);
  formData.append('road_name', document.getElementById('road_name').value);
  formData.append('road_importance', document.getElementById('road_importance').value);
  formData.append('latitude', lat);
  formData.append('longitude', lng);

  const btn = document.getElementById('run-btn');
  btn.disabled = true;
  btn.textContent = 'Running YOLO Model... ⏳';

  try {
    const res = await apiFetch('/api/detect/image', {
      method: 'POST',
      body: formData
    });

    if (res && res.success) {
      showToast(`Detected ${res.total_detected} pothole(s)!`, res.total_detected > 0 ? 'success' : 'info');

      const mediaBox = document.getElementById('result-media-box');
      if (res.annotated_image_url) {
        mediaBox.innerHTML = `<img src="${res.annotated_image_url}" alt="Detection Evidence">`;
      }

      const distCardElem = document.getElementById('primary-estimated-distance');
      const distRelElem = document.getElementById('primary-distance-reliability');

      if (res.detections && res.detections.length > 0) {
        const firstDist = res.detections[0].distance_str || (res.detections[0].estimated_distance ? `${res.detections[0].estimated_distance} m` : 'Distance estimation requires camera calibration.');
        const distSummaryList = res.detections.map((d, i) => `Pothole #${i+1} → ${d.distance_str || 'Calibration required'}`).join('<br>');
        
        if (distCardElem) distCardElem.innerHTML = res.detections.length === 1 ? firstDist : `<div style="font-size:1.1rem; line-height:1.5; color:var(--accent-cyan);">${distSummaryList}</div>`;
        if (distRelElem) distRelElem.textContent = res.detections[0].distance_reliability ? `Reliability: ${res.detections[0].distance_reliability}` : 'Estimated Distance';
      } else {
        if (distCardElem) distCardElem.textContent = '--';
        if (distRelElem) distRelElem.textContent = 'No Potholes Detected';
      }

      const panel = document.getElementById('detection-details-panel');
      const content = document.getElementById('det-card-meta-content');
      panel.style.display = 'block';

      if (res.total_detected === 0) {
        content.innerHTML = `<div style="text-align:center; padding:1.5rem; font-size:1.1rem; font-weight:600; color:var(--status-good);">No pothole detected.</div>`;
      } else {
        content.innerHTML = res.detections.map((d, idx) => `
          <div style="margin-bottom:1rem; padding-bottom:0.75rem; border-bottom:1px solid var(--border-color);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
              <strong style="color:var(--accent-cyan); font-size:1rem;">Pothole #${idx + 1} (${d.pothole_id || 'ID:' + d.id})</strong>
              ${renderRiskBadge(d.risk_level)}
            </div>

            <div class="meta-row"><span>Estimated Distance</span><strong style="color:var(--accent-cyan);">${d.distance_str || (d.estimated_distance ? d.estimated_distance + ' m' : 'Distance estimation requires camera calibration.')}</strong></div>
            <div class="meta-row"><span>Detection Confidence</span><strong>${d.confidence}%</strong></div>
            <div class="meta-row"><span>Estimated Dimensions (W x H)</span><strong>${d.width}px x ${d.height}px</strong></div>
            <div class="meta-row"><span>Bounding Box Surface Area</span><strong>${d.area.toLocaleString()} px²</strong></div>
            <div class="meta-row"><span>Estimated Severity Score</span><strong style="color:var(--accent-cyan);">${d.severity_score}/100</strong></div>
            <div class="meta-row"><span>Repair Priority Score</span><strong style="color:var(--status-high);">${d.priority_score || 0}/100</strong></div>

            ${d.duplicate_info ? `
              <div style="margin-top:0.5rem; padding:0.5rem; background:rgba(249,115,22,0.15); border:1px solid var(--status-medium); border-radius:var(--radius-sm); font-size:0.8rem;">
                ⚠️ <strong>DUPLICATE POTHOLE DETECTED:</strong> Matched nearby existing record <b>${d.duplicate_info.pothole_id}</b> (${d.duplicate_info.distance_meters}m away). Detection count updated to <b>${d.duplicate_info.detection_count + 1}</b>.
              </div>
            ` : ''}
          </div>
        `).join('');
      }
    }
  } catch (err) {
    console.error('Image detection error:', err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Run YOLO Pothole AI 🚀';
  }
});

// Video Submission Handler
document.getElementById('video-upload-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById('vid-file-input');
  if (!fileInput.files[0]) {
    showToast('Please select a video file first', 'warning');
    return;
  }

  const formData = new FormData();
  formData.append('video', fileInput.files[0]);

  const lat = document.getElementById('lat').value;
  const lng = document.getElementById('lng').value;
  if (lat && lng) {
    formData.append('latitude', lat);
    formData.append('longitude', lng);
  }

  const roadName = document.getElementById('road_name').value;
  if (roadName) formData.append('road_name', roadName);

  const roadImp = document.getElementById('road_importance').value;
  if (roadImp) formData.append('road_importance', roadImp);

  const btn = document.getElementById('vid-run-btn');
  btn.disabled = true;
  btn.textContent = 'Processing Video Frames & Tracking... ⏳';

  try {
    const res = await apiFetch('/api/detect/video', {
      method: 'POST',
      body: formData
    });

    if (res && res.success) {
      showToast(`Video processed! ${res.unique_pothole_count} unique tracked potholes found.`, 'success');

      const mediaBox = document.getElementById('result-media-box');
      let mediaHtml = '';

      if (res.keyframe_image_url) {
        mediaHtml += `
          <div style="width:100%; text-align:center; padding:0.5rem;">
            <div style="font-size:0.85rem; font-weight:700; color:var(--accent-cyan); margin-bottom:0.4rem;">📸 AI Annotated Keyframe Summary</div>
            <img src="${res.keyframe_image_url}" alt="AI Detection Keyframe" style="width:100%; max-height:350px; border-radius:var(--radius-md); border:1px solid var(--border-accent); object-fit:contain;">
          </div>
        `;
      }

      if (res.processed_video_url) {
        mediaHtml += `
          <div style="width:100%; text-align:center; margin-top:0.5rem;">
            <video controls autoplay loop src="${res.processed_video_url}" style="width:100%; max-height:350px; border-radius:var(--radius-md);"></video>
          </div>
        `;
      }

      if (!mediaHtml) {
        mediaHtml = `<div style="text-align:center; padding:1.5rem; color:var(--text-muted);">Video processing complete.</div>`;
      }

      mediaBox.innerHTML = mediaHtml;

      const panel = document.getElementById('detection-details-panel');
      const content = document.getElementById('det-card-meta-content');
      panel.style.display = 'block';

      let dbDetsHtml = '';
      if (res.detections && res.detections.length > 0) {
        dbDetsHtml = `
          <div style="margin-top:1rem; padding-top:0.75rem; border-top:1px solid var(--border-color);">
            <strong style="color:var(--text-primary); font-size:0.85rem; display:block; margin-bottom:0.5rem;">Tracked Potholes Saved to Database:</strong>
            ${res.detections.map(d => `
              <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.8rem; padding:0.35rem 0.5rem; background:rgba(255,255,255,0.03); border-radius:var(--radius-sm); margin-bottom:0.3rem;">
                <span style="font-weight:700; color:var(--accent-cyan);">${d.pothole_id}</span>
                <span>Conf: <b>${d.confidence}%</b></span>
                <span>Sev: <b>${d.severity_score}/100</b></span>
                ${renderRiskBadge(d.risk_level)}
              </div>
            `).join('')}
          </div>
        `;
      }

      content.innerHTML = `
        <div class="meta-row"><span>Total Frames Processed</span><strong>${res.total_frames}</strong></div>
        <div class="meta-row"><span>Total Unique Tracked Potholes</span><strong style="color:var(--accent-cyan); font-size:1.1rem;">${res.unique_pothole_count}</strong></div>
        <div class="meta-row"><span>Average Model Confidence</span><strong>${res.average_confidence}%</strong></div>
        <div class="meta-row"><span>Critical / High Risk Count</span><strong style="color:var(--status-critical);">${(res.risk_breakdown?.CRITICAL || 0) + (res.risk_breakdown?.HIGH || 0)}</strong></div>
        <div class="meta-row"><span>Medium Risk Count</span><strong style="color:var(--status-medium);">${res.risk_breakdown?.MEDIUM || 0}</strong></div>
        <div class="meta-row"><span>Low Risk Count</span><strong style="color:var(--status-low);">${res.risk_breakdown?.LOW || 0}</strong></div>
        ${dbDetsHtml}
      `;
    }
  } catch (err) {
    console.error('Video detection error:', err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Process Video Stream 🎥';
  }
});

// Modal Calibration Functions
async function openCalibrationModal() {
  const modal = document.getElementById('calibration-modal');
  if (modal) modal.style.display = 'flex';

  try {
    const res = await apiFetch('/api/detect/calibration');
    if (res && res.success && res.calibration) {
      const c = res.calibration;
      if (document.getElementById('calib-height')) document.getElementById('calib-height').value = c.camera_height || 1.3;
      if (document.getElementById('calib-ref-width')) document.getElementById('calib-ref-width').value = c.known_ref_width || 0.50;
      if (document.getElementById('calib-ref-dist')) document.getElementById('calib-ref-dist').value = c.known_ref_dist || 2.00;
      if (document.getElementById('calib-pitch')) document.getElementById('calib-pitch').value = c.camera_pitch || 15;
      if (document.getElementById('calib-fovy')) document.getElementById('calib-fovy').value = c.camera_fovy || 55;
    }
  } catch (err) {
    console.error('Failed to load calibration:', err);
  }
}

function closeCalibrationModal() {
  const modal = document.getElementById('calibration-modal');
  if (modal) modal.style.display = 'none';
}

async function saveModalCalibration(e) {
  e.preventDefault();
  const payload = {
    camera_height: parseFloat(document.getElementById('calib-height').value),
    known_ref_width: parseFloat(document.getElementById('calib-ref-width').value),
    known_ref_dist: parseFloat(document.getElementById('calib-ref-dist').value),
    camera_pitch: parseFloat(document.getElementById('calib-pitch').value),
    camera_fovy: parseFloat(document.getElementById('calib-fovy').value)
  };

  try {
    const res = await apiFetch('/api/detect/calibration', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    if (res && res.success) {
      showToast('Camera calibration saved successfully! 📷', 'success');
      closeCalibrationModal();
    }
  } catch (err) {
    console.error('Failed to save calibration:', err);
  }
}
