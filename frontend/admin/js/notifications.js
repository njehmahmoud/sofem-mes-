// ── notifications.js — SOFEM MES v6.0 ────────────────────
let _notifData  = { total: 0, danger: 0, warning: 0, info: 0, items: [] };
let _notifOpen  = false;
let _notifTimer = null;

// ── Init: inject bell into topbar ────────────────────────
function initNotifications() {
  // Insert bell button before logout
  const logout = document.querySelector('.btn-logout');
  if (!logout || document.getElementById('notif-bell')) return;

  const bell = document.createElement('div');
  bell.id = 'notif-bell';
  bell.style.cssText = 'position:relative;cursor:pointer;display:flex;align-items:center';
  bell.innerHTML = `
    <button id="notif-btn" onclick="toggleNotifPanel()"
      style="background:none;border:1px solid var(--border);border-radius:6px;
        padding:5px 10px;cursor:pointer;color:var(--muted);font-size:14px;
        display:flex;align-items:center;gap:5px;transition:all .15s;position:relative">
      🔔
      <span id="notif-count" style="display:none;position:absolute;top:-5px;right:-5px;
        background:var(--red);color:#fff;border-radius:50%;font-size:8px;
        font-family:'IBM Plex Mono',monospace;font-weight:700;
        min-width:16px;height:16px;display:none;align-items:center;
        justify-content:center;padding:0 3px;line-height:16px">0</span>
    </button>
    <!-- Panel -->
    <div id="notif-panel" style="display:none;position:absolute;top:calc(100% + 8px);right:0;
      width:360px;background:var(--bg2);border:1px solid var(--border);border-radius:10px;
      z-index:500;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,.4)">
      <div style="padding:.75rem 1rem;border-bottom:1px solid var(--border);
        display:flex;align-items:center;justify-content:space-between">
        <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;
          text-transform:uppercase;letter-spacing:2px">Notifications</div>
        <div style="display:flex;gap:.5rem;align-items:center">
          <span id="notif-summary" style="font-size:9px;color:var(--muted);
            font-family:'IBM Plex Mono',monospace"></span>
          <button onclick="refreshNotifications()" style="background:none;border:none;
            color:var(--muted);cursor:pointer;font-size:11px;padding:2px 4px">↺</button>
        </div>
      </div>
      <div id="notif-list" style="max-height:380px;overflow-y:auto"></div>
      <div style="padding:.6rem 1rem;border-top:1px solid var(--border);text-align:center">
        <button onclick="navigate('analytics-production');toggleNotifPanel()"
          style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--muted);
          background:none;border:none;cursor:pointer;letter-spacing:1px">
          VOIR ANALYTIQUES →
        </button>
      </div>
    </div>
  `;
  logout.parentNode.insertBefore(bell, logout);

  // Close on outside click
  document.addEventListener('click', e => {
    if (_notifOpen && !document.getElementById('notif-bell').contains(e.target)) {
      closeNotifPanel();
    }
  });

  // First fetch
  refreshNotifications();
  // Auto-refresh every 60s
  _notifTimer = setInterval(refreshNotifications, 60000);
}

async function refreshNotifications() {
  try {
    const result = await api('/api/notifications');
    if (result) {
      _notifData = result;
      renderNotifBell();
      if (_notifOpen) renderNotifPanel();
    }
  } catch(e) {
    // Silent fail — don't crash the whole app if notifications endpoint is unavailable
  }
}

function renderNotifBell() {
  const count = document.getElementById('notif-count');
  const btn   = document.getElementById('notif-btn');
  if (!count || !btn) return;

  const total   = _notifData.total || 0;
  const dangers = _notifData.danger || 0;

  if (total > 0) {
    count.style.display = 'flex';
    count.textContent   = total > 99 ? '99+' : total;
    count.style.background = dangers > 0 ? 'var(--red)' : 'var(--accent)';
    btn.style.borderColor  = dangers > 0 ? 'var(--red)' : 'var(--accent)';
    btn.style.color        = dangers > 0 ? 'var(--red)' : 'var(--accent)';
    if (dangers > 0) btn.style.animation = 'ring 2s infinite';
  } else {
    count.style.display = 'none';
    btn.style.borderColor = 'var(--border)';
    btn.style.color       = 'var(--muted)';
    btn.style.animation   = 'none';
  }
}

function renderNotifPanel() {
  const list = document.getElementById('notif-list');
  const summ = document.getElementById('notif-summary');
  if (!list) return;

  const parts = [];
  if (_notifData.danger)  parts.push(`${_notifData.danger} critique${_notifData.danger>1?'s':''}`);
  if (_notifData.warning) parts.push(`${_notifData.warning} retard${_notifData.warning>1?'s':''}`);
  if (_notifData.info)    parts.push(`${_notifData.info} info`);
  if (summ) summ.textContent = parts.join(' · ') || 'Tout va bien';

  const levelColors = {
    danger:  { bg:'rgba(212,43,43,.12)',  border:'rgba(212,43,43,.3)',  text:'#F87171' },
    warning: { bg:'rgba(245,166,35,.12)', border:'rgba(245,166,35,.3)', text:'var(--accent)' },
    info:    { bg:'rgba(59,130,246,.1)',  border:'rgba(59,130,246,.25)',text:'#93C5FD' },
  };

  if (!_notifData.items?.length) {
    list.innerHTML = `<div style="padding:2rem;text-align:center">
      <div style="font-size:28px;margin-bottom:.5rem">✅</div>
      <div style="font-size:12px;color:var(--green);font-family:'IBM Plex Mono',monospace">
        Tout est OK — Aucune alerte
      </div>
    </div>`;
    return;
  }

  const navMap = { stock:'materials', retard:'orders', urgent:'orders', da:'da', br:'br' };

  list.innerHTML = _notifData.items.map(n => {
    const c   = levelColors[n.level] || levelColors.info;
    const nav = navMap[n.type] || 'dashboard';
    return `<div onclick="navigate('${nav}');closeNotifPanel()" style="display:flex;align-items:flex-start;
      gap:.75rem;padding:.75rem 1rem;border-bottom:1px solid var(--border);cursor:pointer;
      background:${c.bg};border-left:3px solid ${c.border};transition:filter .15s"
      onmouseover="this.style.filter='brightness(1.2)'" onmouseout="this.style.filter='none'">
      <span style="font-size:18px;flex-shrink:0;margin-top:1px">${n.icon}</span>
      <div style="flex:1;min-width:0">
        <div style="font-size:11px;font-weight:600;color:${c.text};margin-bottom:2px">${n.title}</div>
        <div style="font-size:10px;color:var(--muted);font-family:'IBM Plex Mono',monospace;
          white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${n.detail}</div>
      </div>
      <span style="font-size:9px;color:var(--muted);flex-shrink:0;margin-top:2px">→</span>
    </div>`;
  }).join('');
}

function toggleNotifPanel() {
  _notifOpen ? closeNotifPanel() : openNotifPanel();
}

function openNotifPanel() {
  _notifOpen = true;
  const panel = document.getElementById('notif-panel');
  if (panel) panel.style.display = 'block';
  renderNotifPanel();
}

function closeNotifPanel() {
  _notifOpen = false;
  const panel = document.getElementById('notif-panel');
  if (panel) panel.style.display = 'none';
}

window.addEventListener('DOMContentLoaded', () => {
  // Only init if we have a valid token — avoid 401 redirect on startup
  if (localStorage.getItem('token')) {
    setTimeout(initNotifications, 800);
  }
});