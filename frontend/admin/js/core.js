// ── SOFEM MES v6.0 — core.js ─────────────────────────────
// Shared utilities: api(), $(), toast(), openModal(), helpers

const API = window.location.origin;

// DOM helper
const $ = id => document.getElementById(id);

// API helper
async function api(path, method = 'GET', body = null) {
  const token = localStorage.getItem('token');
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {}) }
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  if (res.status === 401) {
    // Token expired or invalid — clear and go to login
    // Use a small debounce so multiple simultaneous 401s don't stack
    if (!window._loggingOut) {
      window._loggingOut = true;
      localStorage.clear();
      window.location.replace('/');
    }
    return null;
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Erreur serveur');
  }
  if (res.status === 204) return {};
  return res.json();
}

// Toast
function toast(msg, type = 'ok') {
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.classList.add('show'), 10);
  setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300); }, 3500);
}

// Modal
function openModal(id) { $(id)?.classList.add('open'); }
function closeModal(id) { $(id)?.classList.remove('open'); }

document.addEventListener('click', e => {
  if (e.target.classList.contains('overlay')) e.target.classList.remove('open');
});

// Empty / loading table placeholders
function empty(cols, msg = 'Aucune donnée') {
  return `<tr><td colspan="${cols}" style="text-align:center;color:var(--muted);padding:2rem;font-family:'IBM Plex Mono',monospace;font-size:11px">— ${msg} —</td></tr>`;
}
function loading(cols) {
  return `<tr><td colspan="${cols}" style="text-align:center;color:var(--muted);padding:2rem;font-family:'IBM Plex Mono',monospace;font-size:11px">Chargement...</td></tr>`;
}

// Badge helpers
function pBadge(p) {
  const m = { URGENT:'b-urgent', HIGH:'b-high', NORMAL:'b-normal', LOW:'b-low' };
  const l = { URGENT:'URGENT', HIGH:'HAUTE', NORMAL:'NORMAL', LOW:'BASSE' };
  return `<span class="badge ${m[p]||'b-normal'}">${l[p]||p}</span>`;
}
function sBadge(s) {
  const m = { IN_PROGRESS:'b-inprogress', COMPLETED:'b-completed', DRAFT:'b-draft',
              APPROVED:'b-approved', CANCELLED:'b-cancelled' };
  const l = { IN_PROGRESS:'En Cours', COMPLETED:'Terminé', DRAFT:'Brouillon',
              APPROVED:'Approuvé', CANCELLED:'Annulé' };
  return `<span class="badge ${m[s]||'b-draft'}">${l[s]||s}</span>`;
}
function dateTd(d) {
  if (!d) return '—';
  const diff = (new Date(d) - new Date()) / 86400000;
  const c = diff < 0 ? 'color:var(--red);font-weight:600' : diff < 3 ? 'color:var(--accent)' : 'color:var(--muted)';
  return `<span style="font-family:'IBM Plex Mono',monospace;font-size:10px;${c}">${d}</span>`;
}

// Operations dots (dynamic)
function dots(ops) {
  if (!ops?.length) return '—';
  const cls = { COMPLETED: 'done', IN_PROGRESS: 'in_progress', PENDING: 'pending' };
  return `<div class="sdots">${ops.map(o => {
    const c = cls[o.statut] || 'pending';
    return `<div class="sd ${c}" title="${o.operation_nom} — ${o.statut}"></div>`;
  }).join('')}</div>`;
}

// Clock
function tick() {
  const el = $('clock');
  if (el) el.textContent = new Date().toLocaleString('fr-FR', {
    weekday:'short', day:'2-digit', month:'short',
    hour:'2-digit', minute:'2-digit', second:'2-digit'
  }).toUpperCase();
}
tick(); setInterval(tick, 1000);

// Logout
function logout() {
  localStorage.clear();
  window.location.replace('/');  // replace() prevents back-button loop
}

// User info from token
function getUserInfo() {
  try {
    const token = localStorage.getItem('token');
    if (!token) return {};
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload;
  } catch { return {}; }
}

// Nav router
let currentPage = 'dashboard';
function navigate(page) {
  currentPage = page;
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelector(`.nav-item[data-p="${page}"]`)?.classList.add('active');
  $(`page-${page}`)?.classList.add('active');
  if (window.pageLoaders?.[page]) window.pageLoaders[page]();
  // Persist active page across refreshes
  try { localStorage.setItem('sofem_last_page', page); } catch(e) {}
  location.hash = page;
}

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => navigate(item.dataset.p));
});

// On load: restore last active page from hash or localStorage
window.addEventListener('DOMContentLoaded', () => {
  const hash = location.hash?.replace('#', '');
  const saved = localStorage.getItem('sofem_last_page');
  const restore = hash || saved || 'dashboard';
  // Only restore if the page element exists (valid page)
  if ($(`page-${restore}`)) {
    navigate(restore);
  } else {
    navigate('dashboard');
  }
});

// PDF URL helper — appends token for authenticated PDF endpoints
function pdfUrl(path) {
  const token = localStorage.getItem('token') || '';
  if (!token) {
    alert('No authentication token found. Please log in again.');
    return '#';
  }
  const sep = path.includes('?') ? '&' : '?';
  return `${API}${path}${sep}token=${encodeURIComponent(token)}`;
}

// ── Theme toggle ──────────────────────────────────────────
function quickThemeToggle() {
  try {
    const saved = JSON.parse(localStorage.getItem('sofem_display') || '{}');
    const current = saved.theme || document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    saved.theme = next;
    localStorage.setItem('sofem_display', JSON.stringify(saved));
    document.documentElement.setAttribute('data-theme', next);
    const btn = $('theme-toggle-btn');
    if (btn) btn.textContent = next === 'dark' ? '🌙' : '☀️';
    toast(next === 'dark' ? '🌙 Mode Sombre' : '☀️ Mode Clair');
  } catch(e) {}
}

// ── Sidebar toggle ────────────────────────────────────────
function toggleSidebar() {
  const sidebar = document.querySelector('.sidebar');
  if (!sidebar) return;
  
  const isCollapsed = sidebar.classList.contains('collapsed');
  if (isCollapsed) {
    sidebar.classList.remove('collapsed');
    localStorage.setItem('sofem_sidebar_collapsed', 'false');
  } else {
    sidebar.classList.add('collapsed');
    localStorage.setItem('sofem_sidebar_collapsed', 'true');
  }
}

// Restore sidebar state on page load
window.addEventListener('DOMContentLoaded', () => {
  const wasCollapsed = localStorage.getItem('sofem_sidebar_collapsed') === 'true';
  if (wasCollapsed) {
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) sidebar.classList.add('collapsed');
  }
});

// Apply theme on initial load
(function() {
  try {
    const saved = JSON.parse(localStorage.getItem('sofem_display') || '{}');
    const theme = saved.theme || 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    // Update button icon after DOM loads
    window.addEventListener('DOMContentLoaded', () => {
      const btn = document.getElementById('theme-toggle-btn');
      if (btn) btn.textContent = theme === 'dark' ? '🌙' : '☀️';
    });
  } catch(e) {}
})();