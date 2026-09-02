document.addEventListener('DOMContentLoaded', () => {
  requireAuth();
  const urlParams = new URLSearchParams(window.location.search);
  const potholeId = urlParams.get('id') || 'PT-2026-0001';
  loadPotholeDetail(potholeId);
});

async function loadPotholeDetail(potholeId) {
  try {
    const data = await apiFetch(`/api/potholes/${potholeId}`);
    if (!data || !data.pothole) return;

    const p = data.pothole;

    // Set Header & Image
    document.getElementById('detail-title').textContent = `Telemetry Metrics: ${p.pothole_id}`;
    document.getElementById('detail-risk-badge').innerHTML = renderRiskBadge(p.risk_level);

    if (p.annotated_image_path) {
      document.getElementById('pothole-img').src = `/uploads/${p.annotated_image_path}`;
    }

    // Set Structured Meta
    document.getElementById('meta-id').textContent = p.pothole_id;
    document.getElementById('meta-dist').textContent = p.estimated_distance_str || (p.estimated_distance ? `${p.estimated_distance} m` : 'Distance estimation requires camera calibration.');
    document.getElementById('meta-road').textContent = p.road_name || 'N/A';
    document.getElementById('meta-conf').textContent = `${p.confidence.toFixed(1)}%`;
    document.getElementById('meta-dim').textContent = `${p.width}px x ${p.height}px`;
    document.getElementById('meta-area').textContent = `${p.area.toLocaleString()} px²`;
    document.getElementById('meta-sev').textContent = `${p.severity_score}/100`;
    document.getElementById('meta-prio').textContent = `${p.priority_score}/100`;
    document.getElementById('meta-count').textContent = `${p.detection_count} time(s)`;
    document.getElementById('meta-first').textContent = formatDate(p.detected_at);
    document.getElementById('meta-status').textContent = p.status;

    // Set Timeline Active Step
    updateLifecycleTimeline(p.status);

    // Render Explainable AI logic
    const ai = p.explainable_ai || {};
    document.getElementById('explain-head').textContent = `Why is this classified as ${p.risk_level} risk?`;
    document.getElementById('explain-reasons-list').innerHTML = (ai.reasons || []).map(r => `<div>${r}</div>`).join('') || 'Standard severity calculation';
    document.getElementById('explain-rec').innerHTML = `<strong>Recommendation:</strong> ${ai.recommendation || 'Periodic monitoring'}`;

    // Render Audit Trail
    const auditBox = document.getElementById('audit-trail-container');
    if (data.audit_logs && data.audit_logs.length > 0) {
      auditBox.innerHTML = data.audit_logs.map(log => `
        <div style="padding:0.6rem 0; border-bottom:1px solid rgba(255,255,255,0.05);">
          <div style="display:flex; justify-content:space-between; font-weight:600; color:var(--text-main);">
            <span>${log.user_name}</span>
            <span style="color:var(--text-muted); font-size:0.75rem;">${formatDate(log.timestamp)}</span>
          </div>
          <div style="color:var(--accent-cyan); font-weight:600; margin-top:0.15rem;">${log.action}</div>
          <div style="color:var(--text-muted); font-size:0.78rem;">${log.details || ''}</div>
        </div>
      `).join('');
    } else {
      auditBox.innerHTML = `<div style="color:var(--text-muted); padding:0.5rem 0;">No audit entries logged yet.</div>`;
    }

  } catch (err) {
    console.error('Error loading detail page:', err);
  }
}

function updateLifecycleTimeline(status) {
  const steps = ['DETECTED', 'VERIFIED', 'REPORTED', 'ASSIGNED', 'UNDER_REPAIR', 'CLOSED'];
  let activeIndex = steps.indexOf(status);
  if (status === 'AI_VERIFIED' || status === 'CLOSED') activeIndex = 5;

  steps.forEach((st, idx) => {
    const el = document.getElementById(`step-${st}`);
    if (el) {
      if (idx <= activeIndex) {
        el.classList.add('completed');
      } else {
        el.classList.remove('completed');
      }
    }
  });
}

function openAssignModal() {
  window.location.href = `repairs.html`;
}
