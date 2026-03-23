// ── monitor.js v6 ────────────────────────────────────────
let _monitorOfs   = [];
let _monitorTimer = null;

async function loadMonitor() {
  try {
    const all = await api('/api/of?limit=500') || [];
    _monitorOfs = all.filter(o => o.statut === 'IN_PROGRESS');

    $('mon-stats').textContent = `${_monitorOfs.length} ORDRES EN COURS`;
    renderMonitorTable();

    // Auto-refresh elapsed times every 30s
    if (_monitorTimer) clearInterval(_monitorTimer);
    _monitorTimer = setInterval(updateElapsedTimes, 30000);

  } catch(e) { toast('Erreur monitoring: ' + e.message, 'err'); }
}

function renderMonitorTable() {
  if (_monitorOfs.length === 0) {
    $('monitor-tb').innerHTML = empty(5, 'Aucun ordre en cours');
    return;
  }

  $('monitor-tb').innerHTML = _monitorOfs.map(of => {
    const ops     = of.operations || [];
    const done    = ops.filter(o => o.statut === 'COMPLETED').length;
    const total   = ops.length;
    const pct     = total > 0 ? Math.round(done / total * 100) : 0;
    const inprog  = ops.find(o => o.statut === 'IN_PROGRESS');

    // Progress bar
    const progressBar = `
      <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.4rem">
        <div style="flex:1;height:4px;background:var(--bg3);border-radius:2px;overflow:hidden">
          <div style="height:100%;width:${pct}%;background:${pct===100?'var(--green)':'var(--red)'};transition:width .3s"></div>
        </div>
        <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--muted);min-width:30px">${pct}%</span>
      </div>`;

    // Operations pipeline
    const pipeline = ops.length === 0
      ? '<span style="color:var(--muted);font-size:10px">— Aucune opération —</span>'
      : `<div style="display:flex;align-items:flex-start;gap:3px;flex-wrap:wrap">
          ${ops.map((op, i) => {
            const st   = op.statut || 'PENDING';
            const nxt  = {PENDING:'IN_PROGRESS', IN_PROGRESS:'COMPLETED'}[st];
            const clr  = st==='COMPLETED'?'var(--green)':st==='IN_PROGRESS'?'var(--red)':'var(--border)';
            const bg   = st==='COMPLETED'?'rgba(34,197,94,0.1)':st==='IN_PROGRESS'?'rgba(212,43,43,0.12)':'var(--bg3)';
            const icon = st==='COMPLETED'?'✓':st==='IN_PROGRESS'?'▶':'○';
            const elapsed = st==='IN_PROGRESS' && op.debut ? getElapsed(op.debut) : '';
            const opLabel = op.operateurs_noms
              ? `<div style="font-size:7px;color:var(--muted);margin-top:1px;max-width:65px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${op.operateurs_noms}</div>`
              : '';
            const timeLabel = elapsed
              ? `<div style="font-size:7px;color:var(--accent);font-family:'IBM Plex Mono',monospace" data-debut="${op.debut}" data-op-time="${op.id}">${elapsed}</div>`
              : '';

            return `<div style="display:flex;flex-direction:column;align-items:center;gap:1px">
              <div style="display:flex;align-items:center;gap:2px;padding:3px 7px;border-radius:5px;
                background:${bg};border:1px solid ${clr};font-size:10px;
                ${nxt?'cursor:pointer':'opacity:0.7'};white-space:nowrap;user-select:none"
                ${nxt?`onclick="advOperation(${of.id},${op.id},'${st}')" title="${st==='PENDING'?'▶ Démarrer':'✓ Terminer'}"`:''}>
                <span style="color:${clr}">${icon}</span>
                <span style="color:var(--text);margin-left:3px">${op.operation_nom}</span>
              </div>
              ${opLabel}${timeLabel}
            </div>
            ${i < ops.length-1 ? '<div style="color:var(--muted);font-size:10px;margin-top:6px">→</div>' : ''}`;
          }).join('')}
        </div>`;

    return `<tr>
      <td>
        <span class="of-num">${of.numero}</span>
        ${of.client_nom?`<div style="font-size:9px;color:var(--muted);margin-top:2px">${of.client_nom}</div>`:''}
      </td>
      <td>
        <div style="font-size:12px"><strong>${of.produit_nom}</strong></div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--muted)">${of.quantite} pcs</div>
      </td>
      <td>
        ${progressBar}
        ${pipeline}
      </td>
      <td>
        ${inprog
          ? `<div style="font-size:10px;font-family:'IBM Plex Mono',monospace;color:var(--red)">▶ ${inprog.operation_nom}</div>
             ${inprog.debut?`<div style="font-size:9px;color:var(--muted);margin-top:2px" data-debut="${inprog.debut}" data-op-time="${inprog.id}">${getElapsed(inprog.debut)}</div>`:''}`
          : done === total && total > 0
            ? '<span style="color:var(--green);font-size:11px">✓ Toutes terminées</span>'
            : '<span style="color:var(--muted);font-size:10px">En attente</span>'
        }
      </td>
    </tr>`;
  }).join('');
}

// ── Elapsed time ──────────────────────────────────────────
function getElapsed(debut) {
  if (!debut) return '';
  try {
    const start = new Date(debut.replace(' ','T'));
    const mins  = Math.floor((Date.now() - start.getTime()) / 60000);
    if (mins < 0)  return '';
    if (mins < 60) return `${mins} min`;
    return `${Math.floor(mins/60)}h ${mins%60}min`;
  } catch { return ''; }
}

function updateElapsedTimes() {
  document.querySelectorAll('[data-debut][data-op-time]').forEach(el => {
    el.textContent = getElapsed(el.dataset.debut);
  });
}

// ── Advance operation ─────────────────────────────────────
async function advOperation(ofId, opId, cur) {
  const next = {PENDING:'IN_PROGRESS', IN_PROGRESS:'COMPLETED'}[cur];
  if (!next) return;
  try {
    await api(`/api/of/${ofId}/operations/${opId}`, 'PUT', { statut: next });
    const label = next === 'IN_PROGRESS' ? '▶ En Cours' : '✓ Terminée';
    toast(`${label} ✓`);
    loadMonitor();
  } catch(e) { toast(e.message, 'err'); }
}