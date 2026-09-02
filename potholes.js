document.addEventListener('DOMContentLoaded', () => {
  requireAuth();
  loadPotholesList();
});

async function loadPotholesList() {
  const search = document.getElementById('search-input').value;
  const risk = document.getElementById('filter-risk').value;
  const status = document.getElementById('filter-status').value;
  const sort = document.getElementById('sort-by').value;

  const queryParams = new URLSearchParams({ search, risk, status, sort }).toString();

  try {
    const data = await apiFetch(`/api/potholes?${queryParams}`);
    if (!data) return;

    const tbody = document.getElementById('potholes-table-body');
    if (data.count === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:2rem;">No matching pothole records found.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.potholes.map(p => `
      <tr>
        <td>
          <a href="pothole-details.html?id=${p.pothole_id}" style="color:var(--accent-cyan); font-weight:700;">${p.pothole_id}</a>
        </td>
        <td>${p.road_name || 'N/A'}</td>
        <td>${p.confidence.toFixed(1)}%</td>
        <td><strong style="color:var(--accent-cyan);">${p.severity_score}/100</strong></td>
        <td><strong style="color:var(--status-high);">${p.priority_score}/100</strong></td>
        <td>${renderRiskBadge(p.risk_level)}</td>
        <td><span style="font-weight:700;">${p.detection_count || 1}x</span></td>
        <td><span class="badge" style="background:rgba(255,255,255,0.08);">${p.status}</span></td>
        <td>
          <a href="pothole-details.html?id=${p.pothole_id}" class="btn btn-secondary" style="padding:0.35rem 0.75rem; font-size:0.75rem;">Inspect 🔍</a>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load potholes list:', err);
  }
}
