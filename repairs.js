document.addEventListener('DOMContentLoaded', () => {
  requireAuth();
  adjustUIForRole();
  loadRepairsList();
  loadOpenPotholesDropdown();
  loadFieldOfficersDropdown();
});

function adjustUIForRole() {
  const user = getCurrentUser();
  if (!user) return;
  const role = user.role || 'Citizen';

  // Hide Assign Form for Field Officers
  if (role === 'Field Officer') {
    const assignFormCard = document.getElementById('assign-repair-form')?.closest('.card');
    if (assignFormCard) {
      assignFormCard.style.display = 'none';
    }
  }
}

async function loadFieldOfficersDropdown() {
  const selectElem = document.getElementById('assign-officer');
  if (!selectElem) return;

  try {
    const data = await apiFetch('/api/users');
    if (data && data.users) {
      const fieldOfficers = data.users.filter(u => u.role === 'Field Officer' || u.role === 'Admin');
      if (fieldOfficers.length > 0) {
        selectElem.innerHTML = fieldOfficers.map(u => `
          <option value="${u.id}|${u.name}">${u.name} (${u.role})</option>
        `).join('');
      }
    }
  } catch (err) {
    // Keep default options if restricted
  }
}

async function loadOpenPotholesDropdown() {
  try {
    const data = await apiFetch('/api/potholes?status=OPEN');
    const selectElem = document.getElementById('assign-pothole-id');
    if (!selectElem) return;

    let potholes = data?.potholes || [];
    if (potholes.length === 0) {
      const subData = await apiFetch('/api/potholes?status=SUBMITTED');
      if (subData?.potholes) potholes = subData.potholes;
    }

    if (potholes.length === 0) {
      selectElem.innerHTML = '<option value="">No Pending/OPEN Potholes Available</option>';
      return;
    }

    selectElem.innerHTML = '<option value="">Select Pending Pothole...</option>' + potholes.map(p => `
      <option value="${p.pothole_id}">${p.pothole_id} - ${p.road_name || 'Road Segment'} (Risk: ${p.risk_level}, Priority: ${p.priority_score})</option>
    `).join('');
  } catch (err) {
    console.error('Error loading OPEN potholes dropdown:', err);
  }
}

// Issue Work Order Handler
document.getElementById('assign-repair-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const potholeId = document.getElementById('assign-pothole-id').value.trim();
  if (!potholeId) {
    showToast('Please select a valid OPEN Pothole ID', 'warning');
    return;
  }

  const officerVal = document.getElementById('assign-officer').value.split('|');
  const payload = {
    pothole_id: potholeId,
    assigned_officer_id: parseInt(officerVal[0]),
    assigned_officer_name: officerVal[1],
    department: document.getElementById('assign-dept').value,
    deadline: document.getElementById('assign-deadline').value
  };

  const btn = document.getElementById('assign-btn');
  btn.disabled = true;
  btn.textContent = 'Issuing Work Order... ⏳';

  try {
    const res = await apiFetch('/api/repairs', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    if (res && res.repair_id) {
      showToast(`Work order ${res.repair_id} assigned successfully!`, 'success');
      loadRepairsList();
      loadOpenPotholesDropdown();
    }
  } catch (err) {
    console.error('Work order assign error:', err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Issue Work Order 🛠️';
  }
});

// Run AI Repair Verification Handler
document.getElementById('verify-repair-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const repairId = document.getElementById('verify-repair-id').value;
  const fileInput = document.getElementById('verify-after-image');

  if (!repairId || !fileInput.files[0]) {
    showToast('Please select a work order and upload repair proof photo', 'warning');
    return;
  }

  const formData = new FormData();
  formData.append('after_image', fileInput.files[0]);

  const btn = document.getElementById('verify-btn');
  btn.disabled = true;
  btn.textContent = 'Running AI Verification Model... ⏳';

  try {
    const res = await apiFetch(`/api/repairs/${repairId}/verify`, {
      method: 'POST',
      body: formData
    });

    if (res && res.success) {
      const resBox = document.getElementById('verify-result-box');
      resBox.style.display = 'block';

      if (res.verification_result === 'VERIFIED') {
        resBox.style.background = 'rgba(16, 185, 129, 0.15)';
        resBox.style.border = '1px solid var(--status-good)';
        resBox.innerHTML = `
          <div style="font-weight:800; font-size:1.05rem; color:var(--status-good); margin-bottom:0.4rem;">✅ REPAIR VERIFIED BY AI</div>
          <div>${res.message}</div>
          <div style="margin-top:0.4rem; font-size:0.8rem; color:var(--text-muted);">Potholes detected in proof image: <b>0</b> | Ticket Status: <b>CLOSED</b></div>
        `;
        showToast('Repair AI Verified & Ticket Closed!', 'success');
      } else {
        resBox.style.background = 'rgba(239, 68, 68, 0.15)';
        resBox.style.border = '1px solid var(--status-high)';
        resBox.innerHTML = `
          <div style="font-weight:800; font-size:1.05rem; color:var(--status-high); margin-bottom:0.4rem;">❌ REPAIR VERIFICATION FAILED</div>
          <div>${res.message}</div>
          <div style="margin-top:0.4rem; font-size:0.8rem; color:var(--text-muted);">Potholes still detected in proof image: <b>${res.potholes_detected_in_proof}</b> | Ticket Status: <b>UNDER REPAIR / ESCALATED</b></div>
        `;
        showToast('Verification Failed! Pothole still detected.', 'error');
      }

      loadRepairsList();
      loadOpenPotholesDropdown();
    }
  } catch (err) {
    console.error('Repair verification error:', err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Run AI Verification Inspection 🔬';
  }
});

let activeCameraStream = null;
let officerGPS = { latitude: null, longitude: null, accuracy: null };
let capturedImageFile = null;
let currentRepairsData = [];

async function loadRepairsList() {
  try {
    const data = await apiFetch('/api/repairs');
    if (!data) return;

    currentRepairsData = data.repairs || [];
    const tbody = document.getElementById('repairs-tbody');
    const selectElem = document.getElementById('verify-repair-id');

    if (currentRepairsData.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:2rem;">No repair work orders created yet.</td></tr>`;
      selectElem.innerHTML = `<option value="">No Active Work Orders</option>`;
      return;
    }

    // Populate Table
    tbody.innerHTML = currentRepairsData.map(r => {
      const vColor = r.final_verification_status === 'VERIFIED' || r.verification_result === 'VERIFIED' ? 'var(--status-good)' : (r.final_verification_status || '').includes('FAILED') ? 'var(--status-high)' : 'var(--text-muted)';
      const statusDisp = r.final_verification_status || r.verification_result || 'PENDING';
      return `
        <tr>
          <td><strong style="color:var(--accent-cyan);">${r.repair_id}</strong></td>
          <td><a href="pothole-details.html?id=${r.pothole_id}" style="color:var(--accent-blue);">${r.pothole_id}</a></td>
          <td>${r.assigned_officer_name}</td>
          <td>${r.deadline || 'N/A'}</td>
          <td><span class="badge" style="background:rgba(255,255,255,0.1);">${r.repair_status}</span></td>
          <td><strong style="color:${vColor}">${statusDisp}</strong></td>
        </tr>
      `;
    }).join('');

    // Populate Select Options for Verification Form
    selectElem.innerHTML = '<option value="">Select Work Order / Complaint ID...</option>' + currentRepairsData.map(r => `
      <option value="${r.repair_id}">Complaint ${r.pothole_id} (${r.repair_id}) - ${r.repair_status}</option>
    `).join('');

  } catch (err) {
    console.error('Error loading repairs list:', err);
  }
}

function handleWorkOrderChange() {
  const repairId = document.getElementById('verify-repair-id').value;
  const telemetryBox = document.getElementById('telemetry-box');
  const origText = document.getElementById('orig-loc-text');

  if (!repairId) {
    telemetryBox.style.display = 'none';
    return;
  }

  const selectedRepair = currentRepairsData.find(r => r.repair_id === repairId);
  telemetryBox.style.display = 'block';

  acquireOfficerGPS(selectedRepair);
}

function acquireOfficerGPS(selectedRepair) {
  const officerText = document.getElementById('officer-loc-text');
  const distText = document.getElementById('distance-text');
  const origText = document.getElementById('orig-loc-text');

  if (navigator.geolocation) {
    officerText.innerHTML = 'Acquiring GPS location... ⏳';
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        officerGPS.latitude = parseFloat(pos.coords.latitude.toFixed(6));
        officerGPS.longitude = parseFloat(pos.coords.longitude.toFixed(6));
        officerGPS.accuracy = parseFloat(pos.coords.accuracy.toFixed(1));

        officerText.innerHTML = `(${officerGPS.latitude}, ${officerGPS.longitude}) ± ${officerGPS.accuracy}m`;

        // If pothole coordinates exist, calculate distance preview
        if (selectedRepair) {
          fetchPotholeCoords(selectedRepair.pothole_id, (lat, lng) => {
            origText.innerHTML = `(${lat}, ${lng})`;
            const dist = calculateHaversine(lat, lng, officerGPS.latitude, officerGPS.longitude);
            const distColor = dist <= 30.0 ? 'var(--status-good)' : 'var(--status-critical)';
            distText.innerHTML = `<span style="color:${distColor}; font-weight:700;">${dist} m</span>`;
          });
        }
      },
      (err) => {
        officerText.innerHTML = '⚠️ GPS Permission Denied / Signal Unavailable';
        distText.innerHTML = '--';
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  } else {
    officerText.innerHTML = '⚠️ Geolocation not supported by browser';
  }
}

function fetchPotholeCoords(potholeId, callback) {
  apiFetch(`/api/potholes/${potholeId}`).then(data => {
    if (data && data.pothole && data.pothole.latitude) {
      callback(data.pothole.latitude, data.pothole.longitude);
    }
  }).catch(() => {});
}

function calculateHaversine(lat1, lon1, lat2, lon2) {
  const R = 6371000.0;
  const dLat = (lat2 - lat1) * Math.PI / 180.0;
  const dLon = (lon2 - lon1) * Math.PI / 180.0;
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180.0) * Math.cos(lat2 * Math.PI / 180.0) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return parseFloat((R * c).toFixed(1));
}

// Camera Capture Flow
function openCameraCapture() {
  const container = document.getElementById('camera-container');
  const video = document.getElementById('webcam-feed');
  const fileInput = document.getElementById('verify-after-image');

  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    container.style.display = 'block';
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
      .then(stream => {
        activeCameraStream = stream;
        video.srcObject = stream;
      })
      .catch(() => {
        container.style.display = 'none';
        fileInput.click();
      });
  } else {
    fileInput.click();
  }
}

function snapCameraFrame() {
  const video = document.getElementById('webcam-feed');
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;

  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  canvas.toBlob(blob => {
    capturedImageFile = new File([blob], `camera_capture_${Date.now()}.jpg`, { type: 'image/jpeg' });
    
    // Set preview
    const preview = document.getElementById('captured-preview');
    preview.src = URL.createObjectURL(blob);
    document.getElementById('captured-preview-container').style.display = 'block';

    // Enable verify button
    document.getElementById('verify-btn').disabled = false;

    // Stop camera stream
    if (activeCameraStream) {
      activeCameraStream.getTracks().forEach(track => track.stop());
      activeCameraStream = null;
    }
    document.getElementById('camera-container').style.display = 'none';
    showToast('Photo captured live from camera!', 'success');
  }, 'image/jpeg');
}

// File input fallback change listener
document.getElementById('verify-after-image').addEventListener('change', (e) => {
  if (e.target.files && e.target.files[0]) {
    capturedImageFile = e.target.files[0];
    const preview = document.getElementById('captured-preview');
    preview.src = URL.createObjectURL(capturedImageFile);
    document.getElementById('captured-preview-container').style.display = 'block';
    document.getElementById('verify-btn').disabled = false;
  }
});

// Run Multi-Factor Verification Submit Handler
document.getElementById('verify-repair-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const repairId = document.getElementById('verify-repair-id').value;
  if (!repairId || !capturedImageFile) {
    showToast('Please select a work order and capture a repair photo', 'warning');
    return;
  }

  const formData = new FormData();
  formData.append('after_image', capturedImageFile);
  if (officerGPS.latitude !== null) {
    formData.append('latitude', officerGPS.latitude);
    formData.append('longitude', officerGPS.longitude);
    formData.append('accuracy', officerGPS.accuracy);
  }

  const btn = document.getElementById('verify-btn');
  btn.disabled = true;
  btn.textContent = 'Evaluating Multi-Factor Verification... ⏳';

  try {
    const res = await apiFetch(`/api/repairs/${repairId}/verify`, {
      method: 'POST',
      body: formData
    });

    if (res) {
      const resBox = document.getElementById('verify-result-box');
      resBox.style.display = 'block';
      const t = res.telemetry || {};

      const isVerified = res.final_verification_status === 'VERIFIED';
      const bg = isVerified ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)';
      const border = isVerified ? '1px solid var(--status-good)' : '1px solid var(--status-high)';
      const titleColor = isVerified ? 'var(--status-good)' : 'var(--status-high)';
      const titleIcon = isVerified ? '✅ MULTI-FACTOR VERIFIED' : '❌ VERIFICATION FAILED';

      resBox.style.background = bg;
      resBox.style.border = border;

      resBox.innerHTML = `
        <div style="font-weight:800; font-size:1.1rem; color:${titleColor}; margin-bottom:0.6rem;">${titleIcon}</div>
        <div style="margin-bottom:0.75rem; font-size:0.9rem;">${res.message}</div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.5rem; background:rgba(0,0,0,0.3); padding:0.75rem; border-radius:var(--radius-sm); font-size:0.8rem; margin-bottom:0.75rem;">
          <div>📷 <b>Camera Capture:</b> Verified Live</div>
          <div>⏳ <b>Timestamp:</b> ${t.capture_timestamp || 'Server Recorded'}</div>
          <div>📍 <b>GPS Geofence (30m):</b> ${t.gps_status === 'VERIFIED' ? '✅' : '❌'} (${t.distance_meters}m)</div>
          <div>🖼️ <b>Scene Match:</b> ${t.scene_status === 'VERIFIED' ? '✅' : '⚠️'} (${t.scene_score}%)</div>
          <div style="grid-column: span 2;">🔬 <b>AI Defect Check:</b> ${t.ai_status === 'VERIFIED' ? '✅ 0 Potholes Found' : '❌ Defects Detected'}</div>
        </div>

        <div style="text-align:right;">
          <button type="button" class="btn btn-secondary" style="font-size:0.75rem;" onclick="openCameraCapture()">🔄 Retake Photo</button>
        </div>
      `;

      if (isVerified) {
        showToast('Repair Multi-Factor Verified & Ticket Resolved!', 'success');
      } else {
        showToast(`Verification Failed: ${res.final_verification_status}`, 'error');
      }

      loadRepairsList();
      loadOpenPotholesDropdown();
    }
  } catch (err) {
    console.error('Repair verification error:', err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Run Multi-Factor Verification 🔬';
  }
});
