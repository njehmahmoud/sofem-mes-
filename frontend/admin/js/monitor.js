// ── monitor.js v6 ────────────────────────────────────────
async function loadMonitor() {
  try {
    const all = await api('/api/of?limit=500') || [];
    const active = all.filter(o => o.statut === 'IN_PROGRESS');

    $('mon-stats').textContent = `${active.length} ORDRES EN COURS`;


    if (active.length === 0) {
      $('monitor-tb').innerHTML = empty(5, 'Aucun ordre en cours');
      return;
    }

    // Per-OF rows with inline pipeline
    $('monitor-tb').innerHTML = active.map(of => {
      const ops = of.operations || [];

      // Inline pipeline for this OF
      const pipeline = ops.length === 0
        ? '<span style="color:var(--muted);font-size:10px">— Aucune opération —</span>'
        : `<div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap">
            ${ops.map((op, i) => {
              const st  = op.statut || 'PENDING';
              const cls = st === 'COMPLETED' ? 'done' : st === 'IN_PROGRESS' ? 'in_progress' : 'pending';
              const nxt = {PENDING:'IN_PROGRESS', IN_PROGRESS:'COMPLETED'}[st];
              const icon = st === 'COMPLETED' ? '✓' : st === 'IN_PROGRESS' ? '▶' : '○';
              const opInfo = op.operateurs_noms
                ? `<div style="font-size:7px;color:var(--muted);max-width:60px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${op.operateurs_noms}</div>`
                : '';
              return `<div style="display:flex;flex-direction:column;align-items:center;gap:1px">
                <span class="ms ${cls}" ${nxt?`onclick="advOperation(${of.id},${op.id},'${st}')" style="cursor:pointer" title="Cliquer pour avancer"`:''}>${icon} ${op.operation_nom}</span>
                ${opInfo}
              </div>${i < ops.length-1 ? '<div style="color:var(--muted);font-size:10px">→</div>' : ''}`;
            }).join('')}
          </div>`;

      return `<tr>
        <td><span class="of-num">${of.numero}</span></td>
        <td>${of.produit_nom}</td>
        <td style="font-size:11px;color:var(--muted)">${of.client_nom||'—'}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${of.quantite}</td>
        <td>${pipeline}</td>
      </tr>`;
    }).join('');

  } catch(e) { toast('Erreur monitoring: ' + e.message, 'err'); }
}

async function advOperation(ofId, opId, cur) {
  const next = {PENDING:'IN_PROGRESS', IN_PROGRESS:'COMPLETED'}[cur];
  if (!next) return;
  try {
    await api(`/api/of/${ofId}/operations/${opId}`, 'PUT', { statut: next });
    toast(`Opération → ${next === 'IN_PROGRESS' ? 'En Cours' : 'Terminée'} ✓`);
    loadMonitor();
  } catch(e) { toast(e.message, 'err'); }
}