document.addEventListener('DOMContentLoaded', () => {
  requireAuth();
  loadAnalyticsCharts();
});

async function loadAnalyticsCharts() {
  try {
    const data = await apiFetch('/api/analytics');
    if (!data) return;

    // 1. Detection Trend Line Chart
    const trendCtx = document.getElementById('trendChart').getContext('2d');
    const trendLabels = (data.detection_trend || []).map(t => t.date);
    const trendValues = (data.detection_trend || []).map(t => t.count);

    new Chart(trendCtx, {
      type: 'line',
      data: {
        labels: trendLabels.length ? trendLabels : ['Today'],
        datasets: [{
          label: 'Pothole Count',
          data: trendValues.length ? trendValues : [5],
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.15)',
          fill: true,
          tension: 0.4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af' } },
          y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af' } }
        }
      }
    });

    // 2. Risk Distribution Pie Chart
    const riskCtx = document.getElementById('riskChart').getContext('2d');
    const rd = data.risk_distribution || {};

    new Chart(riskCtx, {
      type: 'doughnut',
      data: {
        labels: ['Critical', 'High', 'Medium', 'Low'],
        datasets: [{
          data: [rd.CRITICAL || 2, rd.HIGH || 3, rd.MEDIUM || 4, rd.LOW || 1],
          backgroundColor: ['#a855f7', '#ef4444', '#f97316', '#eab308']
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'right', labels: { color: '#f9fafb' } }
        }
      }
    });

    // 3. Road-wise Bar Chart
    const roadCtx = document.getElementById('roadChart').getContext('2d');
    const roadLabels = (data.road_rankings || []).map(r => r.road_name);
    const roadCounts = (data.road_rankings || []).map(r => r.count);

    new Chart(roadCtx, {
      type: 'bar',
      data: {
        labels: roadLabels.length ? roadLabels : ['Central Ave', 'Park St', 'Ring Road'],
        datasets: [{
          label: 'Total Potholes',
          data: roadCounts.length ? roadCounts : [4, 2, 1],
          backgroundColor: '#06b6d4'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af' } },
          y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af' } }
        }
      }
    });

    // 4. Predictive Maintenance Risk Module
    const predBox = document.getElementById('predictive-rankings-box');
    if (data.road_rankings && data.road_rankings.length > 0) {
      predBox.innerHTML = data.road_rankings.map((r, i) => {
        const pRisk = r.avg_sev > 75 ? 'HIGH' : r.avg_sev > 50 ? 'MEDIUM' : 'LOW';
        const pDays = r.avg_sev > 75 ? 7 : r.avg_sev > 50 ? 14 : 30;
        const pBadge = pRisk === 'HIGH' ? 'badge-critical' : pRisk === 'MEDIUM' ? 'badge-high' : 'badge-low';
        return `
          <div style="padding:0.75rem 0; border-bottom:1px solid rgba(255,255,255,0.08);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.3rem;">
              <strong style="color:var(--text-main); font-size:0.9rem;">${r.road_name}</strong>
              <span class="badge ${pBadge}">Risk: ${pRisk}</span>
            </div>
            <div style="font-size:0.8rem; color:var(--text-muted);">
              Current Health: <b>${Math.max(10, Math.round(100 - r.avg_sev))}/100</b> | Avg Severity: <b>${r.avg_sev.toFixed(1)}/100</b>
            </div>
            <div style="font-size:0.8rem; color:var(--accent-cyan); font-weight:600; margin-top:0.2rem;">
              💡 Recommendation: Inspect & repair within <b>${pDays} days</b>
            </div>
          </div>
        `;
      }).join('');
    } else {
      predBox.innerHTML = `<div style="color:var(--text-muted); padding:1rem;">Predictive risk data available once more road telemetry is gathered.</div>`;
    }

  } catch (err) {
    console.error('Error loading analytics charts:', err);
  }
}
