/* ═══════════════════════════════════════════════════════════════
   app.js — Cloud Dashboard Frontend Logic
   
   All communication with Flask APIs uses fetch().
   No frameworks — plain vanilla JavaScript.
   
   Sections:
     1. API helpers
     2. Toast notifications
     3. Auth (login / register / logout)
     4. Dashboard panel navigation
     5. Dashboard overview (stats)
     6. File manager (upload, list, search, delete, download)
     7. Monitoring (metrics polling)
     8. Global init
═══════════════════════════════════════════════════════════════ */

'use strict';

/* ══════════════════════════════════════════════════════════════
   1. API HELPERS
══════════════════════════════════════════════════════════════ */

/**
 * Wrapper around fetch() that always sets Content-Type for JSON
 * and returns parsed JSON (or throws a structured error).
 */
async function apiJSON(url, options = {}) {
  const defaults = {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',   // send session cookie
  };
  const response = await fetch(url, { ...defaults, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new APIError(data.error || 'Request failed', response.status, data);
  }
  return data;
}

/**
 * Wrapper for multipart file uploads (no Content-Type header —
 * the browser sets it with the correct boundary automatically).
 */
async function apiUpload(url, formData) {
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    body: formData,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new APIError(data.error || 'Upload failed', response.status, data);
  }
  return data;
}

/** Custom error class so we can read status codes in catch blocks. */
class APIError extends Error {
  constructor(message, status, data = {}) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.data   = data;
  }
}

/* ══════════════════════════════════════════════════════════════
   2. TOAST NOTIFICATIONS
══════════════════════════════════════════════════════════════ */

const ICONS = { success: '✓', error: '✕', info: 'ℹ', warning: '⚠' };

/**
 * Show a toast notification.
 * @param {string} message  - Text to display
 * @param {'success'|'error'|'info'|'warning'} type
 * @param {number} duration - Auto-dismiss ms (0 = never)
 */
function showToast(message, type = 'info', duration = 4000) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${ICONS[type] || 'ℹ'}</span>
    <span class="toast-msg">${message}</span>
  `;

  container.appendChild(toast);

  function dismiss() {
    toast.classList.add('toast-leaving');
    setTimeout(() => toast.remove(), 300);
  }

  if (duration > 0) setTimeout(dismiss, duration);
  toast.addEventListener('click', dismiss);
}

/* ══════════════════════════════════════════════════════════════
   3. AUTH — LOGIN PAGE
══════════════════════════════════════════════════════════════ */

function initLoginPage() {
  const form    = document.getElementById('login-form');
  const btnText = document.getElementById('login-btn-text');
  const spinner = document.getElementById('login-spinner');
  const errBox  = document.getElementById('login-error');

  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errBox.classList.add('hidden');

    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    const remember = document.getElementById('login-remember')?.checked ?? false;

    if (!username || !password) {
      showFieldError(errBox, 'Please fill in all fields.');
      return;
    }

    setLoading(btnText, spinner, true, 'Signing in…');

    try {
      await apiJSON('/api/login', {
        method: 'POST',
        body: JSON.stringify({ username, password, remember }),
      });
      showToast('Welcome back!', 'success', 1500);
      setTimeout(() => (window.location.href = '/dashboard'), 600);
    } catch (err) {
      showFieldError(errBox, err.message || 'Invalid username or password.');
    } finally {
      setLoading(btnText, spinner, false, 'Sign In');
    }
  });

  // Toggle password visibility
  setupPasswordToggle('login-password', 'toggle-login-pw');
}

/* ── AUTH — REGISTER PAGE ────────────────────────────────────── */

function initRegisterPage() {
  const form    = document.getElementById('register-form');
  const btnText = document.getElementById('register-btn-text');
  const spinner = document.getElementById('register-spinner');
  const errBox  = document.getElementById('register-error');
  const pwInput = document.getElementById('reg-password');

  if (!form) return;

  // Live password strength meter
  if (pwInput) {
    pwInput.addEventListener('input', () => updatePasswordStrength(pwInput.value));
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errBox.classList.add('hidden');

    const username = document.getElementById('reg-username').value.trim();
    const email    = document.getElementById('reg-email').value.trim();
    const password = pwInput?.value ?? '';
    const confirm  = document.getElementById('reg-confirm').value;

    // Client-side validation
    if (password !== confirm) {
      showFieldError(errBox, 'Passwords do not match.');
      return;
    }

    setLoading(btnText, spinner, true, 'Creating account…');

    try {
      await apiJSON('/api/register', {
        method: 'POST',
        body: JSON.stringify({ username, email, password }),
      });
      showToast('Account created! Redirecting…', 'success', 1500);
      setTimeout(() => (window.location.href = '/dashboard'), 800);
    } catch (err) {
      const details = err.data?.details;
      const msg = details ? details.join('<br>') : (err.message || 'Registration failed.');
      showFieldError(errBox, msg);
    } finally {
      setLoading(btnText, spinner, false, 'Create Account');
    }
  });

  setupPasswordToggle('reg-password', 'toggle-reg-pw');
  setupPasswordToggle('reg-confirm', 'toggle-reg-confirm');
}

function updatePasswordStrength(password) {
  const bar  = document.getElementById('pw-strength-fill');
  const text = document.getElementById('pw-strength-text');
  if (!bar) return;

  let score = 0;
  if (password.length >= 8)             score++;
  if (password.length >= 12)            score++;
  if (/[A-Z]/.test(password))          score++;
  if (/[0-9]/.test(password))          score++;
  if (/[^A-Za-z0-9]/.test(password))  score++;

  const levels = [
    { w: '0%',   color: 'transparent', label: '' },
    { w: '20%',  color: '#ef4444',     label: 'Very weak' },
    { w: '40%',  color: '#f59e0b',     label: 'Weak' },
    { w: '60%',  color: '#f59e0b',     label: 'Fair' },
    { w: '80%',  color: '#10b981',     label: 'Strong' },
    { w: '100%', color: '#00d4ff',     label: 'Very strong' },
  ];

  const level = levels[score] || levels[0];
  bar.style.width = level.w;
  bar.style.background = level.color;
  if (text) { text.textContent = level.label; text.style.color = level.color; }
}

/* ══════════════════════════════════════════════════════════════
   4. DASHBOARD — PANEL NAVIGATION
══════════════════════════════════════════════════════════════ */

let activePanel = 'panel-overview';

function initNavigation() {
  const navItems = document.querySelectorAll('.nav-item[data-panel]');
  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const panelId = item.dataset.panel;
      switchPanel(panelId, item);
    });
  });
}

function switchPanel(panelId, clickedItem = null) {
  // Hide all panels
  document.querySelectorAll('.content-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  // Show target panel
  const panel = document.getElementById(panelId);
  if (panel) panel.classList.add('active');

  // Activate nav item
  if (clickedItem) {
    clickedItem.classList.add('active');
  } else {
    // Find by data-panel
    const navItem = document.querySelector(`.nav-item[data-panel="${panelId}"]`);
    if (navItem) navItem.classList.add('active');
  }

  // Update navbar title
  const titleEl = document.getElementById('navbar-page-title');
  if (titleEl && clickedItem) {
    titleEl.textContent = clickedItem.querySelector('.nav-label')?.textContent || 'Dashboard';
  }

  activePanel = panelId;

  // Lazy-load panel data
  if (panelId === 'panel-overview') loadOverviewStats();
  if (panelId === 'panel-files')    loadFiles();
  if (panelId === 'panel-monitor')  loadMetrics();

  // Close mobile sidebar
  closeSidebar();
}

/* ══════════════════════════════════════════════════════════════
   5. DASHBOARD — OVERVIEW STATS
══════════════════════════════════════════════════════════════ */

async function loadOverviewStats() {
  try {
    // Load files list for counts
    const filesData   = await apiJSON('/api/files');
    const metricsData = await apiJSON('/api/metrics');

    // Update stat cards
    setEl('stat-total-files',   filesData.total ?? 0);
    setEl('stat-storage-used',  formatBytes(filesData.storage_used ?? 0));
    setEl('stat-uploads-today', metricsData.database?.recent_uploads ?? 0);
    setEl('stat-server-status', metricsData.server?.status === 'ok' ? 'Online' : 'Degraded');
    renderS3Status(metricsData.aws ?? {});

    // Recent files table
    renderRecentFiles(filesData.files?.slice(0, 6) ?? []);

    // Status tiles
    updateStatusTile('status-server',   metricsData.server?.status === 'ok');
    updateStatusTile('status-database', metricsData.database?.status === 'connected');
    updateStatusTile('status-s3',       metricsData.aws?.s3_status === 'connected');

    setEl('status-uptime', metricsData.application?.uptime_human ?? '—');

  } catch (err) {
    console.error('Overview load error:', err);
  }
}

function renderRecentFiles(files) {
  const tbody = document.getElementById('recent-files-tbody');
  if (!tbody) return;

  if (!files.length) {
    tbody.innerHTML = `
      <tr><td colspan="5">
        <div class="empty-state">
          <span class="empty-state-icon">📂</span>
          <div class="empty-state-title">No files yet</div>
          <div class="empty-state-sub">Upload your first file from the Files tab</div>
        </div>
      </td></tr>`;
    return;
  }

  tbody.innerHTML = files.map(f => `
    <tr>
      <td>
        <div class="td-filename">
          <div class="file-icon ${getFileIconClass(f.file_extension)}">${getFileIconEmoji(f.file_extension)}</div>
          <span class="truncate" title="${esc(f.original_filename)}">${esc(f.original_filename)}</span>
        </div>
      </td>
      <td>${esc(f.file_extension?.toUpperCase() || '—')}</td>
      <td>${esc(f.file_size_human)}</td>
      <td>${formatDate(f.uploaded_at)}</td>
      <td>
        <span class="badge ${f.storage_backend === 's3' ? 'badge-info' : 'badge-purple'}">
          ${f.storage_backend === 's3' ? '☁ S3' : '💾 Local'}
        </span>
      </td>
    </tr>`).join('');
}

function updateStatusTile(id, isOnline) {
  const tile = document.getElementById(id);
  if (!tile) return;
  const dot   = tile.querySelector('.status-dot');
  const value = tile.querySelector('.status-item-value');
  if (dot)   { dot.className = `status-dot ${isOnline ? 'online' : 'offline'}`; }
  if (value) { value.textContent = isOnline ? 'Connected' : 'Disconnected'; }
}

/* ══════════════════════════════════════════════════════════════
   6. FILE MANAGER
══════════════════════════════════════════════════════════════ */

let filesCache = [];
let searchDebounce = null;

function initFileManager() {
  const zone      = document.getElementById('upload-zone');
  const fileInput = document.getElementById('file-input');
  const browseBtn = document.getElementById('browse-btn');
  const searchBox = document.getElementById('file-search');

  if (!zone) return;

  // Drag and drop
  zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', ()  => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    handleFiles(Array.from(e.dataTransfer.files));
  });

  // Click to browse
  browseBtn?.addEventListener('click', () => fileInput.click());
  zone.addEventListener('click', (e) => {
    if (e.target === zone || zone.contains(e.target)) fileInput.click();
  });

  fileInput?.addEventListener('change', () => handleFiles(Array.from(fileInput.files)));

  // Search with debounce
  searchBox?.addEventListener('input', () => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => loadFiles(searchBox.value.trim()), 350);
  });
}

async function handleFiles(files) {
  if (!files.length) return;

  const list = document.getElementById('upload-list');
  const storageBackend = document.getElementById('storage-destination')?.value || 'local';

  for (const file of files) {
    // Check file size (50 MB)
    if (file.size > 50 * 1024 * 1024) {
      showToast(`${file.name} is too large (max 50 MB).`, 'error');
      continue;
    }

    // Create progress item
    const itemId = `upload-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const item = document.createElement('div');
    item.className = 'upload-progress-item';
    item.id = itemId;
    item.innerHTML = `
      <span>${getFileIconEmoji(file.name.split('.').pop())}</span>
      <div style="flex:1; min-width:0;">
        <div class="upload-file-name truncate">${esc(file.name)}</div>
        <div class="progress-bar mt-1"><div class="progress-fill cyan" style="width:0%" id="bar-${itemId}"></div></div>
      </div>
      <span class="upload-file-size">${formatBytes(file.size)}</span>
      <span id="status-${itemId}" class="text-muted text-sm">Uploading…</span>`;
    list?.prepend(item);

    // Animate bar indeterminate
    const bar = document.getElementById(`bar-${itemId}`);
    if (bar) bar.style.width = '60%';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('storage_backend', storageBackend);

    try {
      const result = await apiUpload('/api/upload', formData);
      if (bar) bar.style.width = '100%';
      const statusEl = document.getElementById(`status-${itemId}`);
      if (statusEl) { statusEl.textContent = '✓ Done'; statusEl.className = 'text-green text-sm font-semibold'; }
      const destination = result.file?.storage_backend === 's3' ? 'Amazon S3' : 'Local storage';
      showToast(`${file.name} uploaded to ${destination}.`, 'success');
      // Refresh file list & stats
      setTimeout(() => { loadFiles(); loadOverviewStats(); }, 800);
    } catch (err) {
      const statusEl = document.getElementById(`status-${itemId}`);
      if (statusEl) { statusEl.textContent = '✕ Failed'; statusEl.className = 'text-red text-sm font-semibold'; }
      if (bar) { bar.style.width = '100%'; bar.className = 'progress-fill red'; }
      showToast(`Upload failed: ${err.message}`, 'error');
    }

    // Remove item after 4s
    setTimeout(() => item.remove(), 4000);
  }

  // Reset input so same file can be re-uploaded
  const fi = document.getElementById('file-input');
  if (fi) fi.value = '';
}

async function loadFiles(search = '') {
  const tbody    = document.getElementById('files-tbody');
  const countEl  = document.getElementById('files-count');
  const storageEl = document.getElementById('files-storage');

  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="6"><div class="loading-overlay"><div class="spinner"></div> Loading files…</div></td></tr>`;

  try {
    const params = new URLSearchParams({ limit: 200 });
    if (search) params.set('search', search);

    const data = await apiJSON(`/api/files?${params}`);
    filesCache = data.files ?? [];

    if (countEl)   countEl.textContent  = `${data.total ?? 0} file${data.total !== 1 ? 's' : ''}`;
    if (storageEl) storageEl.textContent = formatBytes(data.storage_used ?? 0);

    renderFilesTable(filesCache);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><span class="empty-state-icon">⚠</span><div class="empty-state-title">Error loading files</div><div class="empty-state-sub">${esc(err.message)}</div></div></td></tr>`;
  }
}

function renderFilesTable(files) {
  const tbody = document.getElementById('files-tbody');
  if (!tbody) return;

  if (!files.length) {
    tbody.innerHTML = `
      <tr><td colspan="6">
        <div class="empty-state">
          <span class="empty-state-icon">📂</span>
          <div class="empty-state-title">No files found</div>
          <div class="empty-state-sub">Upload files using the area above or change your search</div>
        </div>
      </td></tr>`;
    return;
  }

  tbody.innerHTML = files.map(f => `
    <tr>
      <td>
        <div class="td-filename">
          <div class="file-icon ${getFileIconClass(f.file_extension)}">${getFileIconEmoji(f.file_extension)}</div>
          <div>
            <div class="truncate" title="${esc(f.original_filename)}" style="max-width:220px">${esc(f.original_filename)}</div>
            <div class="text-xs text-muted" style="margin-top:1px">${f.storage_backend === 's3' ? '☁ S3' : '💾 Local'}</div>
          </div>
        </div>
      </td>
      <td><span class="badge badge-info">${esc(f.file_extension?.toUpperCase() || 'FILE')}</span></td>
      <td class="font-mono text-sm">${esc(f.file_size_human)}</td>
      <td class="text-sm">${formatDate(f.uploaded_at)}</td>
      <td>
        <span class="badge ${f.storage_backend === 's3' ? 'badge-success' : 'badge-purple'}">
          ${f.storage_backend === 's3' ? '☁ AWS S3' : '💾 Local'}
        </span>
      </td>
      <td>
        <div class="flex gap-1">
          <button class="btn btn-ghost btn-sm btn-icon" onclick="downloadFile(${f.id})" data-tooltip="Download" title="Download">⬇</button>
          <button class="btn btn-danger btn-sm btn-icon" onclick="deleteFile(${f.id}, '${esc(f.original_filename)}')" data-tooltip="Delete" title="Delete">🗑</button>
        </div>
      </td>
    </tr>`).join('');
}

async function downloadFile(fileId) {
  // Open download in new tab (follows redirect to S3 pre-signed URL or local file)
  window.open(`/api/files/${fileId}/download`, '_blank');
}

async function deleteFile(fileId, filename) {
  if (!confirm(`Delete "${filename}"? This cannot be undone.`)) return;

  try {
    await apiJSON(`/api/files/${fileId}`, { method: 'DELETE' });
    showToast(`"${filename}" deleted.`, 'success');
    loadFiles(document.getElementById('file-search')?.value || '');
    loadOverviewStats();
  } catch (err) {
    showToast(`Delete failed: ${err.message}`, 'error');
  }
}

/* ══════════════════════════════════════════════════════════════
   7. MONITORING
══════════════════════════════════════════════════════════════ */

let metricsInterval = null;

async function loadMetrics() {
  // Clear old interval if any
  if (metricsInterval) clearInterval(metricsInterval);

  await fetchAndRenderMetrics();

  // Auto-refresh every 5 seconds
  metricsInterval = setInterval(fetchAndRenderMetrics, 5000);
}

async function fetchAndRenderMetrics() {
  try {
    const data = await apiJSON('/api/metrics');
    renderServerMetrics(data.server ?? {});
    renderAppMetrics(data.application ?? {}, data.database ?? {}, data.aws ?? {});
  } catch (err) {
    console.error('Metrics load error:', err);
  }
}

function renderServerMetrics(server) {
  // CPU
  setMetric('metric-cpu-val',  `${server.cpu_percent ?? 0}%`);
  setProgress('progress-cpu',   server.cpu_percent ?? 0, getUsageClass(server.cpu_percent));

  // Memory
  setMetric('metric-mem-val',  `${server.memory_percent ?? 0}%`);
  setMetric('metric-mem-sub',  `${server.memory_used_mb ?? 0} MB / ${server.memory_total_mb ?? 0} MB`);
  setProgress('progress-mem',   server.memory_percent ?? 0, getUsageClass(server.memory_percent));

  // Disk
  setMetric('metric-disk-val', `${server.disk_percent ?? 0}%`);
  setMetric('metric-disk-sub', `${server.disk_used_gb ?? 0} GB / ${server.disk_total_gb ?? 0} GB`);
  setProgress('progress-disk',  server.disk_percent ?? 0, getUsageClass(server.disk_percent));

  // Uptime
  setMetric('metric-uptime-val', server.uptime_human ?? '—');
  setMetric('metric-processes',  server.process_count ?? '—');
  setMetric('metric-platform',   `${server.platform ?? '—'} / Python ${server.python_version ?? '—'}`);

  // Network
  setMetric('metric-net-sent', formatBytes(server.net_bytes_sent ?? 0));
  setMetric('metric-net-recv', formatBytes(server.net_bytes_recv ?? 0));
}

function renderAppMetrics(app, db, aws) {
  // App uptime
  setMetric('metric-app-uptime', app.uptime_human ?? '—');
  setMetric('metric-environment', app.environment ?? '—');

  // Database
  setMetric('metric-db-status',  db.status === 'connected' ? '✓ Connected' : '✕ Error');
  setMetric('metric-db-users',   db.total_users ?? 0);
  setMetric('metric-db-files',   db.total_files ?? 0);
  setMetric('metric-db-storage', db.storage_human ?? '0 B');
  setMetric('metric-db-recent',  db.recent_uploads ?? 0);

  renderS3Status(aws);
}

function renderS3Status(aws) {
  // AWS
  const s3Connected = aws.s3_status === 'connected';
  const s3Configured = aws.s3_configured;
  setMetric(
    'metric-s3-status',
    s3Connected ? `✓ ${aws.s3_bucket}` : (s3Configured ? '✕ Connection failed' : '— Not configured')
  );
  setMetric('metric-s3-region',  aws.region ?? '—');
  const s3StatusEl = document.getElementById('s3-status-badge');
  if (s3StatusEl) {
    s3StatusEl.className = `badge ${s3Connected ? 'badge-success' : 'badge-warning'}`;
    s3StatusEl.textContent = s3Connected
      ? '☁ S3 Connected'
      : (s3Configured ? '⚠ S3 Connection Failed' : '⚠ S3 Not Configured');
    s3StatusEl.title = aws.s3_error || '';
  }
}

function getUsageClass(pct) {
  if (pct >= 90) return 'red';
  if (pct >= 70) return 'orange';
  if (pct >= 50) return 'cyan';
  return 'green';
}

/* ══════════════════════════════════════════════════════════════
   8. GLOBAL INIT
══════════════════════════════════════════════════════════════ */

/** Called on every page load. Routes to page-specific init. */
function initApp() {
  const page = document.body.dataset.page;

  if (page === 'login')     initLoginPage();
  if (page === 'register')  initRegisterPage();
  if (page === 'dashboard') initDashboard();
}

function initDashboard() {
  initNavigation();
  initFileManager();
  initSidebar();
  initLogout();

  // Load default panel
  switchPanel('panel-overview');
}

function initLogout() {
  const logoutBtn = document.getElementById('logout-btn');
  logoutBtn?.addEventListener('click', async () => {
    try {
      await apiJSON('/api/logout', { method: 'POST' });
      window.location.href = '/';
    } catch {
      window.location.href = '/';
    }
  });
}

function initSidebar() {
  const toggle  = document.getElementById('sidebar-toggle');
  const overlay = document.getElementById('sidebar-overlay');
  const sidebar = document.getElementById('sidebar');

  toggle?.addEventListener('click', () => {
    sidebar?.classList.toggle('open');
    overlay?.classList.toggle('open');
  });
  overlay?.addEventListener('click', closeSidebar);
}

function closeSidebar() {
  document.getElementById('sidebar')?.classList.remove('open');
  document.getElementById('sidebar-overlay')?.classList.remove('open');
}

/* ══════════════════════════════════════════════════════════════
   UTILITY FUNCTIONS
══════════════════════════════════════════════════════════════ */

/** Safely set element text content. */
function setEl(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

/** Set a metric value element. */
function setMetric(id, value) { setEl(id, value); }

/** Update a progress bar width and color. */
function setProgress(id, percent, colorClass) {
  const bar = document.getElementById(id);
  if (!bar) return;
  bar.style.width = `${Math.min(100, Math.max(0, percent))}%`;
  bar.className   = `progress-fill ${colorClass}`;
}

/** Format bytes to human-readable string. */
function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = bytes;
  for (const unit of units) {
    if (size < 1024) return `${size.toFixed(size < 10 ? 1 : 0)} ${unit}`;
    size /= 1024;
  }
  return `${size.toFixed(1)} PB`;
}

/** Format ISO date string to readable form. */
function formatDate(isoString) {
  if (!isoString) return '—';
  try {
    return new Date(isoString).toLocaleDateString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  } catch { return isoString; }
}

/** Escape HTML to prevent XSS. */
function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** Return CSS class for file icon based on extension. */
function getFileIconClass(ext) {
  const e = (ext || '').toLowerCase();
  if (['png','jpg','jpeg','gif','webp','svg'].includes(e)) return 'img';
  if (['pdf','doc','docx','txt','md','csv','xlsx','pptx'].includes(e)) return 'doc';
  if (['zip','tar','gz','rar','7z'].includes(e)) return 'zip';
  if (['py','js','html','css','json','xml','sh','ts'].includes(e)) return 'code';
  return 'other';
}

/** Return emoji for file icon. */
function getFileIconEmoji(ext) {
  const e = (ext || '').toLowerCase();
  if (['png','jpg','jpeg','gif','webp','svg'].includes(e)) return '🖼';
  if (['pdf'].includes(e)) return '📄';
  if (['doc','docx','txt','md'].includes(e)) return '📝';
  if (['csv','xlsx'].includes(e)) return '📊';
  if (['zip','tar','gz','rar','7z'].includes(e)) return '📦';
  if (['py'].includes(e)) return '🐍';
  if (['js','ts'].includes(e)) return '⚡';
  if (['html','css'].includes(e)) return '🌐';
  if (['json','xml'].includes(e)) return '🔧';
  return '📎';
}

/** Show an error box with HTML message. */
function showFieldError(el, msg) {
  if (!el) return;
  el.innerHTML = msg;
  el.classList.remove('hidden');
}

/** Toggle button loading state. */
function setLoading(textEl, spinnerEl, isLoading, text) {
  if (textEl)   textEl.textContent = isLoading ? text : text;
  if (spinnerEl) spinnerEl.classList.toggle('hidden', !isLoading);
  const btn = textEl?.closest('button');
  if (btn) btn.disabled = isLoading;
}

/** Set up password show/hide toggle. */
function setupPasswordToggle(inputId, toggleId) {
  const input  = document.getElementById(inputId);
  const toggle = document.getElementById(toggleId);
  if (!input || !toggle) return;
  toggle.addEventListener('click', () => {
    const isText = input.type === 'text';
    input.type   = isText ? 'password' : 'text';
    toggle.textContent = isText ? '👁' : '🙈';
  });
}

// Clean up monitoring interval when navigating away from monitor panel
document.addEventListener('visibilitychange', () => {
  if (document.hidden && metricsInterval) {
    clearInterval(metricsInterval);
    metricsInterval = null;
  } else if (!document.hidden && activePanel === 'panel-monitor') {
    loadMetrics();
  }
});

// Bootstrap
document.addEventListener('DOMContentLoaded', initApp);
