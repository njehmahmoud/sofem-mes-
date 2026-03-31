// ── activity.js — SOFEM MES v6.0 — Historique d'activité ─

async function loadActivity() {
  try {
    const logs = await api('/api/notifications/activity?limit=100') || [];
    const el = $('activity-tb');
    if (!el) return;

    if (!logs.length) {
      el.innerHTML = `<tr><td colspan="6" class="empty">Aucune activité enregistrée<br>
        <span style="font-size:9px;color:var(--muted)">Les actions se loguent automatiquement</span>
      </td></tr>`;
      return;
    }

    const iconMap = {
      CREATE:'✚', UPDATE:'✎', DELETE:'✕', LOGIN:'🔑', LOGOUT:'🚪',
      APPROVE:'✓', REJECT:'✗', PRINT:'🖨', EXPORT:'📤', CONFIRM:'✅'
    };
    const colorMap = {
      CREATE:'var(--green)', UPDATE:'var(--accent)', DELETE:'var(--red)',
      LOGIN:'var(--blue)', LOGOUT:'var(--muted)', APPROVE:'var(--green)',
      REJECT:'var(--red)', PRINT:'var(--muted)', EXPORT:'var(--blue)', CONFIRM:'var(--green)'
    };

    el.innerHTML = logs.map(l => {
      const icon  = iconMap[l.action]  || '·';
      const color = colorMap[l.action] || 'var(--muted)';
      const user  = l.prenom ? `${l.prenom} ${l.nom}` : 'Système';
      const ts    = String(l.created_at||'').replace('T',' ').slice(0,16);
      return `<tr>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted)">${ts}</td>
        <td><span style="font-size:14px;color:${color}">${icon}</span>
          <span class="badge" style="font-size:8px;background:${color}20;color:${color};margin-left:4px">${l.action}</span></td>
        <td style="font-size:11px;font-weight:500">${user}</td>
        <td><span class="badge b-draft" style="font-size:8px">${l.entity_type||'—'}</span></td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted)">${l.entity_id||'—'}</td>
        <td style="font-size:11px;color:var(--muted);max-width:200px;overflow:hidden;
          text-overflow:ellipsis;white-space:nowrap">${l.detail||'—'}</td>
      </tr>`;
    }).join('');
  } catch(e) { toast('Erreur activité: '+e.message,'err'); }
}

// Log an action (called from other modules)
function logActivity(action, entity_type, entity_id, detail) {
  api('/api/notifications/activity', 'POST', { action, entity_type, entity_id, detail })
    .catch(() => {}); // silent fail
}

window.pageLoaders = window.pageLoaders || {};
window.pageLoaders['activity'] = loadActivity;