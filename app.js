// Global Application Helpers & API Client

const API_BASE = '/api';

// Toast Notification Handler
function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : type === 'warning' ? '⚠️' : 'ℹ️';
  toast.innerHTML = `<span>${icon}</span> <div>${message}</div>`;
  
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Authentication Helpers
function getAuthToken() {
  return localStorage.getItem('token');
}

function getCurrentUser() {
  const userStr = localStorage.getItem('user');
  if (!userStr) return null;
  try { return JSON.parse(userStr); } catch(e) { return null; }
}

function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  window.location.href = 'login.html';
}

function requireAuth() {
  const token = getAuthToken();
  const currentPath = window.location.pathname.split('/').pop() || 'index.html';
  if (!token && !currentPath.endsWith('login.html')) {
    window.location.href = 'login.html';
    return;
  }
  checkRolePermissions();
}

function redirectUserByRole(role) {
  // All roles are directed to the Common Pothole Dashboard (index.html)
  window.location.href = 'index.html';
}

function checkRolePermissions() {
  const user = getCurrentUser();
  if (!user) return;

  const currentPath = window.location.pathname.split('/').pop() || 'index.html';
  const role = user.role || 'Citizen';

  // Role permissions mapping
  if (role === 'Citizen') {
    const restrictedPages = ['users.html', 'settings.html', 'analytics.html', 'potholes.html'];
    if (restrictedPages.includes(currentPath)) {
      showToast('Access restricted. Redirecting to Common Pothole Dashboard...', 'warning');
      setTimeout(() => window.location.href = 'index.html', 800);
    }
  } else if (role === 'Field Officer') {
    const restrictedPages = ['users.html', 'settings.html', 'analytics.html', 'reports.html'];
    if (restrictedPages.includes(currentPath)) {
      showToast('Access restricted to Field Officers.', 'warning');
      setTimeout(() => window.location.href = 'index.html', 800);
    }
  }
}

// Global API Fetch wrapper with Auth
async function apiFetch(endpoint, options = {}) {
  const token = getAuthToken();
  const headers = options.headers || {};
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  options.headers = headers;

  try {
    const res = await fetch(endpoint, options);
    if (res.status === 401 && !window.location.pathname.endsWith('login.html')) {
      logout();
      return null;
    }
    
    const contentType = res.headers.get('content-type') || '';
    let data = {};
    if (contentType.includes('application/json')) {
      data = await res.json();
    } else {
      const text = await res.text();
      throw new Error(`Server returned status ${res.status}: ${res.statusText || 'Unexpected error'}`);
    }

    if (!res.ok) {
      throw new Error(data.error || `API Request failed (${res.status})`);
    }
    return data;
  } catch (err) {
    console.error(`API Error [${endpoint}]:`, err);
    showToast(err.message || 'Request failed', 'error');
    throw err;
  }
}

// Risk Badge UI Helper
function renderRiskBadge(risk) {
  const r = (risk || 'LOW').toUpperCase();
  const cls = r === 'CRITICAL' ? 'badge-critical' : r === 'HIGH' ? 'badge-high' : r === 'MEDIUM' ? 'badge-medium' : 'badge-low';
  return `<span class="badge ${cls}">${r}</span>`;
}

// Format Date Helper
function formatDate(dateStr) {
  if (!dateStr) return 'N/A';
  try {
    const d = new Date(dateStr);
    return d.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch(e) {
    return dateStr;
  }
}
