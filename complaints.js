let cmpMap = null;
let cmpMarker = null;

document.addEventListener('DOMContentLoaded', () => {
  requireAuth();
  const user = getCurrentUser();
  if (user) {
    const nameInput = document.getElementById('cmp-name');
    const emailInput = document.getElementById('cmp-email');
    if (nameInput && user.name) nameInput.value = user.name;
    if (emailInput && user.email) emailInput.value = user.email;
  }
  initComplaintMap();
  loadComplaintsList();
});

function initComplaintMap() {
  const mapContainer = document.getElementById('cmp-map');
  if (!mapContainer) return;

  // Default view (centered at neutral location)
  cmpMap = L.map('cmp-map').setView([20.5937, 78.9629], 5); // India center view

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(cmpMap);

  // Allow manual clicking on map to set location marker
  cmpMap.on('click', (e) => {
    const lat = parseFloat(e.latlng.lat.toFixed(6));
    const lng = parseFloat(e.latlng.lng.toFixed(6));
    updateLocationOnMap(lat, lng, 'Manual Map Pin Selected');
  });
}

function fetchRealGPSLocation() {
  const statusBox = document.getElementById('gps-status-box');
  const btn = document.getElementById('use-location-btn');

  if (!navigator.geolocation) {
    showGPSError('Geolocation API is not supported by your browser. Please click on the map to set location.');
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
      statusBox.innerHTML = `✅ <strong>Location Acquired via GPS!</strong> (${lat}, ${lng})`;

      updateLocationOnMap(lat, lng, 'Your Current Location');
      showToast('Real GPS location acquired!', 'success');
    },
    (error) => {
      btn.disabled = false;
      btn.textContent = '📍 USE MY CURRENT LOCATION';

      let errorMsg = '⚠️ Location access denied or GPS unavailable.';
      if (error.code === error.PERMISSION_DENIED) {
        errorMsg = '⚠️ <strong>Location Permission Denied:</strong> Please click anywhere on the map below to manually pick your pothole location.';
      } else if (error.code === error.POSITION_UNAVAILABLE) {
        errorMsg = '⚠️ <strong>GPS Signal Unavailable:</strong> Click on the map below to select location manually.';
      } else if (error.code === error.TIMEOUT) {
        errorMsg = '⚠️ <strong>Location Request Timed Out:</strong> Click on the map below to select location manually.';
      }

      showGPSError(errorMsg);
    },
    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0
    }
  );
}

function showGPSError(message) {
  const statusBox = document.getElementById('gps-status-box');
  statusBox.style.display = 'block';
  statusBox.style.background = 'rgba(239, 68, 68, 0.15)';
  statusBox.style.border = '1px solid var(--status-critical)';
  statusBox.style.color = '#fca5a5';
  statusBox.innerHTML = message;
}

function updateLocationOnMap(lat, lng, label) {
  document.getElementById('cmp-lat').value = lat;
  document.getElementById('cmp-lng').value = lng;

  if (cmpMap) {
    cmpMap.setView([lat, lng], 16);

    if (cmpMarker) {
      cmpMarker.setLatLng([lat, lng]);
    } else {
      cmpMarker = L.marker([lat, lng]).addTo(cmpMap);
    }
    cmpMarker.bindPopup(`<b>${label}</b><br>Lat: ${lat}<br>Lng: ${lng}`).openPopup();
  }
}

document.getElementById('complaint-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const fileInput = document.getElementById('cmp-file');
  if (!fileInput.files[0]) {
    showToast('Please select a pothole photo', 'warning');
    return;
  }

  const lat = document.getElementById('cmp-lat').value;
  const lng = document.getElementById('cmp-lng').value;

  if (!lat || !lng) {
    showToast('Please click "USE MY CURRENT LOCATION" or select a point on the map', 'warning');
    return;
  }

  const formData = new FormData();
  formData.append('image', fileInput.files[0]);
  formData.append('user_name', document.getElementById('cmp-name').value);
  formData.append('user_email', document.getElementById('cmp-email').value);
  formData.append('location_name', document.getElementById('cmp-location').value);
  formData.append('description', document.getElementById('cmp-desc').value);
  formData.append('latitude', lat);
  formData.append('longitude', lng);

  const btn = document.getElementById('cmp-btn');
  btn.disabled = true;
  btn.textContent = 'Submitting & Running AI Analysis... ⏳';

  try {
    const res = await apiFetch('/api/complaints', {
      method: 'POST',
      body: formData
    });

    if (res && res.success) {
      showToast('Complaint submitted and verified by AI!', 'success');

      const resBox = document.getElementById('cmp-result-box');
      resBox.style.display = 'block';
      resBox.innerHTML = `
        <div style="font-weight:700; color:var(--status-good); margin-bottom:0.5rem;">🎉 Complaint Successfully Submitted</div>
        <div>Complaint ID: <b>${res.complaint_id}</b></div>
        <div>Associated Pothole: <b>${res.pothole_id || 'N/A'}</b></div>
        <div>Saved GPS: <b>${lat}, ${lng}</b></div>
        <div>AI Estimated Risk: ${renderRiskBadge(res.risk_level)}</div>
        <div>Estimated Severity: <b>${res.severity_score}/100</b></div>
        <div>Current Ticket Status: <span class="badge" style="background:rgba(255,255,255,0.1);">${res.status}</span></div>
      `;

      document.getElementById('complaint-form').reset();
      if (cmpMarker) {
        cmpMap.removeLayer(cmpMarker);
        cmpMarker = null;
      }
      document.getElementById('gps-status-box').style.display = 'none';
      loadComplaintsList();
    }
  } catch (err) {
    console.error('Complaint submission error:', err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Submit & Run AI Verification 🚀';
  }
});

async function loadComplaintsList() {
  try {
    const data = await apiFetch('/api/complaints');
    if (!data) return;

    const tbody = document.getElementById('complaints-tbody');
    if (!data.complaints || data.complaints.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:2rem;">No citizen complaints recorded yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.complaints.map(c => `
      <tr>
        <td><strong style="color:var(--accent-cyan);">${c.complaint_id}</strong></td>
        <td><a href="pothole-details.html?id=${c.pothole_id}" style="color:var(--accent-blue);">${c.pothole_id || 'N/A'}</a></td>
        <td>${c.location_name}</td>
        <td>${c.user_name}</td>
        <td>${formatDate(c.created_at)}</td>
        <td><span class="badge" style="background:rgba(255,255,255,0.1);">${c.status}</span></td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Error loading complaints list:', err);
  }
}
