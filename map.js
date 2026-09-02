document.addEventListener('DOMContentLoaded', () => {
  if (typeof requireAuth === 'function') requireAuth();
  initGISMap();
  loadHotspotsList();
});

let gisMap = null;

async function initGISMap() {
  const mapElem = document.getElementById('gis-map');
  if (!mapElem) return;

  // Initialize Leaflet map without hardcoded Delhi coordinates
  gisMap = L.map('gis-map');

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(gisMap);

  try {
    const res = await apiFetch('/api/map/markers');
    
    if (res && res.markers && res.markers.length > 0) {
      const bounds = [];
      const markersGroup = typeof L.markerClusterGroup === 'function' ? L.markerClusterGroup({
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true,
        maxClusterRadius: 40
      }) : null;

      res.markers.forEach(m => {
        const color = m.risk_level === 'CRITICAL' ? '#9b59b6' : m.risk_level === 'HIGH' ? '#e74c3c' : m.risk_level === 'MEDIUM' ? '#e67e22' : '#f1c40f';

        const marker = L.circleMarker([m.latitude, m.longitude], {
          radius: 9,
          fillColor: color,
          color: '#ffffff',
          weight: 2,
          opacity: 1,
          fillOpacity: 0.9
        });

        bounds.push([m.latitude, m.longitude]);

        const imgHtml = m.image_url ? `<img src="${m.image_url}" style="width:100%; max-height:120px; border-radius:6px; margin:0.4rem 0;">` : '';

        marker.bindPopup(`
          <div style="font-family:sans-serif; width:200px;">
            <strong style="color:${color}; font-size:1.05rem;">${m.pothole_id}</strong><br>
            <span style="font-size:0.8rem; color:#555;">${m.road_name || 'Road Segment'}</span><br>
            ${imgHtml}
            <div style="font-size:0.8rem; margin-top:0.3rem;">
              Severity: <b>${m.severity_score}/100</b> | Priority: <b>${m.priority_score}/100</b><br>
              Risk: <b>${m.risk_level}</b> | Status: <b>${m.status}</b>
            </div>
            <a href="pothole-details.html?id=${m.pothole_id}" style="display:inline-block; margin-top:0.4rem; font-size:0.8rem; font-weight:bold; color:#2563eb;">View Inspection Details &rarr;</a>
          </div>
        `);

        if (markersGroup) {
          markersGroup.addLayer(marker);
        } else {
          marker.addTo(gisMap);
        }
      });

      if (markersGroup) {
        gisMap.addLayer(markersGroup);
      }

      // Fit map to actual real pothole markers in DB
      if (bounds.length === 1) {
        gisMap.setView(bounds[0], 15);
      } else {
        gisMap.fitBounds(bounds, { padding: [40, 40] });
      }
    } else {
      // No real markers in database - use real device GPS or neutral view
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            gisMap.setView([pos.coords.latitude, pos.coords.longitude], 13);
          },
          () => {
            gisMap.setView([20.5937, 78.9629], 5);
          },
          { enableHighAccuracy: true, timeout: 5000 }
        );
      } else {
        gisMap.setView([20.5937, 78.9629], 5);
      }

      // Add overlay banner on empty map
      const infoControl = L.control({ position: 'topright' });
      infoControl.onAdd = function () {
        const div = L.DomUtil.create('div', 'map-empty-info');
        div.style.background = 'rgba(17, 24, 39, 0.85)';
        div.style.color = 'var(--text-muted)';
        div.style.padding = '0.75rem 1rem';
        div.style.borderRadius = '8px';
        div.style.border = '1px solid var(--border-color)';
        div.style.fontSize = '0.85rem';
        div.innerHTML = '📌 <strong>No pothole reports available for mapping.</strong>';
        return div;
      };
      infoControl.addTo(gisMap);
    }
  } catch (err) {
    console.error('Error loading GIS map markers:', err);
    gisMap.setView([20.5937, 78.9629], 5);
  }
}

async function loadHotspotsList() {
  const container = document.getElementById('hotspot-list-container');
  if (!container) return;

  try {
    const res = await apiFetch('/api/map/hotspots');
    if (!res || !res.hotspots || res.hotspots.length === 0) {
      container.innerHTML = `<div style="text-align:center; padding:2rem; color:var(--text-muted); font-size:0.9rem;">No pothole reports available for mapping.</div>`;
      return;
    }

    container.innerHTML = res.hotspots.map(h => `
      <div class="hotspot-card" onclick="zoomToHotspot(${h.latitude}, ${h.longitude})">
        <div class="hotspot-title">
          <span>${h.hotspot_id}</span>
          <span class="badge badge-critical">${h.priority}</span>
        </div>
        <div style="font-size:0.85rem; font-weight:600; margin-bottom:0.4rem;">${h.road_name}</div>
        <div style="font-size:0.8rem; color:var(--text-muted);">
          <div>Pothole Cluster Count: <b>${h.total_potholes}</b></div>
          <div>High/Critical Risk Potholes: <b style="color:var(--status-high);">${h.high_risk_count}</b></div>
          <div>Road Health Score: <b style="color:${h.road_health_score < 40 ? 'var(--status-critical)' : 'var(--status-medium)'}">${h.road_health_score}/100</b> (${h.road_condition})</div>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Error loading hotspots:', err);
    container.innerHTML = `<div style="text-align:center; padding:2rem; color:var(--text-muted);">No pothole reports available for mapping.</div>`;
  }
}

function zoomToHotspot(lat, lng) {
  if (gisMap) {
    gisMap.flyTo([lat, lng], 16, { duration: 1.5 });
  }
}
