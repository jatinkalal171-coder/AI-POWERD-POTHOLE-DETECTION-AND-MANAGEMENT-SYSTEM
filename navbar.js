document.addEventListener('DOMContentLoaded', () => {
  renderSidebar();
  renderTopbar();
});

function renderSidebar() {
  const sidebarContainer = document.getElementById('sidebar-container');
  if (!sidebarContainer) return;

  const currentPath = window.location.pathname.split('/').pop() || 'index.html';
  const user = getCurrentUser() || { name: 'Guest User', role: 'Citizen' };
  const role = user.role || 'Citizen';

  const allNavItems = [
    { href: 'index.html', label: 'Common Dashboard', icon: '📊', roles: ['Citizen', 'Municipality Officer', 'Field Officer', 'Admin'] },
    { href: 'detect.html', label: 'AI Detection Studio', icon: '🔍', roles: ['Citizen', 'Municipality Officer', 'Admin'] },
    { href: 'live.html', label: 'Live Camera Feed', icon: '📹', roles: ['Citizen', 'Municipality Officer', 'Admin'] },
    { href: 'complaints.html', label: role === 'Citizen' ? 'My Complaints' : 'Citizen Complaints', icon: '📥', roles: ['Citizen', 'Municipality Officer', 'Admin'] },
    { href: 'repairs.html', label: role === 'Field Officer' ? 'Assigned Work Orders' : 'Repair Management', icon: '🛠️', roles: ['Municipality Officer', 'Field Officer', 'Admin'] },
    { href: 'potholes.html', label: 'Pothole Directory', icon: '🛑', roles: ['Municipality Officer', 'Admin'] },
    { href: 'map.html', label: 'GIS Map & Hotspots', icon: '🗺️', roles: ['Citizen', 'Municipality Officer', 'Field Officer', 'Admin'] },
    { href: 'analytics.html', label: 'Road Analytics', icon: '📈', roles: ['Municipality Officer', 'Admin'] },
    { href: 'reports.html', label: 'Export Reports', icon: '📄', roles: ['Municipality Officer', 'Admin'] },
    { href: 'notifications.html', label: 'Notifications', icon: '🔔', roles: ['Citizen', 'Municipality Officer', 'Field Officer', 'Admin'] },
    { href: 'users.html', label: 'User Directory', icon: '👥', roles: ['Municipality Officer', 'Admin'] },
    { href: 'settings.html', label: 'Settings', icon: '⚙️', roles: ['Admin'] }
  ];

  const visibleItems = allNavItems.filter(item => item.roles.includes(role));

  const navHtml = visibleItems.map(item => {
    const isActive = currentPath === item.href || (currentPath === '' && item.href === 'index.html') || (currentPath === 'pothole-details.html' && item.href === 'potholes.html');
    return `
      <a href="${item.href}" class="nav-item ${isActive ? 'active' : ''}">
        <span class="icon">${item.icon}</span> ${item.label}
      </a>
    `;
  }).join('');

  sidebarContainer.innerHTML = `
    <aside class="sidebar">
      <div class="sidebar-header" style="padding:1rem; border-bottom:1px solid var(--border-color); text-align:center; background:rgba(15,23,42,0.6);">
        <img src="images/logo.png" style="max-height:85px; width:auto; max-width:100%; object-fit:contain; filter:drop-shadow(0 4px 10px rgba(0,0,0,0.5));" alt="ROADFIX Logo">
      </div>
      <nav class="sidebar-nav">
        ${navHtml}
      </nav>
      <div class="sidebar-footer" style="flex-direction:column; align-items:stretch;">
        <div style="display:flex; align-items:center; justify-content:space-between; width:100%;">
          <div class="user-badge">
            <div class="user-avatar">${user.name ? user.name.charAt(0) : 'U'}</div>
            <div class="user-info">
              <span class="user-name">${user.name || 'User'}</span>
              <span class="user-role">${user.role || 'Citizen'}</span>
            </div>
          </div>
          <button class="btn-icon" title="Logout" onclick="logout()">🚪</button>
        </div>
        <div style="text-align:center; padding-top:0.6rem; margin-top:0.5rem; border-top:1px solid rgba(255,255,255,0.08); font-size:0.72rem; color:var(--text-muted); font-weight:600; letter-spacing:0.04em;">
          Made with ❤️ by <span style="color:var(--accent-cyan); font-weight:700;">Jatin</span>
        </div>
      </div>
    </aside>
  `;
}

function renderTopbar() {
  const topbarContainer = document.getElementById('topbar-container');
  if (!topbarContainer) return;

  const titleMap = {
    'index.html': { title: 'Executive Road Dashboard', sub: 'Real-time pothole monitoring & municipal health telemetry' },
    'detect.html': { title: 'AI Detection Studio', sub: 'Upload image or video for YOLO pothole detection & severity analysis' },
    'live.html': { title: 'Live Camera Monitor', sub: 'Real-time video feed inference stream' },
    'potholes.html': { title: 'Master Pothole Directory', sub: 'Track, filter, and prioritize detected road defects' },
    'pothole-details.html': { title: 'Pothole Inspection Details', sub: 'Comprehensive lifecycle, detection logs, and explainable AI' },
    'map.html': { title: 'Interactive GIS Map & Hotspots', sub: 'Geospatial risk mapping and pothole spatial density clusters' },
    'complaints.html': { title: 'Citizen Complaint Portal', sub: 'Submit road damage reports with instant AI image verification' },
    'repairs.html': { title: 'Work Orders & AI Verification', sub: 'Assign field officers and verify repairs using before/after AI model' },
    'analytics.html': { title: 'Road Performance Analytics', sub: 'Pothole trend analysis, severity distribution, & repair efficiency' },
    'reports.html': { title: 'Report Generation Center', sub: 'Export municipal inspection PDF and CSV reports' },
    'notifications.html': { title: 'Notifications & Overdue Alerts', sub: 'In-app alert inbox and automatic escalation tracking' },
    'users.html': { title: 'User Management', sub: 'Manage municipality officers, field officers, and citizens' },
    'settings.html': { title: 'System Settings', sub: 'Configure AI thresholds, email alerts, and model weights' }
  };

  const currentPath = window.location.pathname.split('/').pop() || 'index.html';
  const info = titleMap[currentPath] || { title: 'Smart Road Monitoring', sub: 'Municipal AI Portal' };

  topbarContainer.innerHTML = `
    <header class="topbar">
      <div class="page-title-group">
        <h1>${info.title}</h1>
        <p>${info.sub}</p>
      </div>
      <div class="topbar-actions">
        <a href="notifications.html" class="btn-icon" title="Notifications">
          🔔
          <span class="badge-dot" id="notif-badge-dot"></span>
        </a>
      </div>
    </header>
  `;
}
