// ── monitor.js ───────────────────────────────────────────
async function loadMonitor() {
  try {
    const all = await api('/api/of?limit=500') || [];
    const active = all.filter(o => o.statut === 'IN_PROGRESS');

    $('mon-stats').textContent = `${active.length} ORDRES EN COURS`;

    if (active.length === 0) {
      $('monitor-tb').innerHTML = empty(6, 'Aucun ordre en cours');
      return;
    }

    $('monitor-tb').innerHTML = active.map(of => {
      const ops = of.operations || [];
      const opCells = ops.map(op => {
        const st  = op.statut || 'PENDING';
        const cls = st === 'COMPLETED' ? 'done' : st === 'IN_PROGRESS' ? 'in_progress' : 'pending';
        const lbl = st === 'COMPLETED' ? `✓ ${op.operation_nom}` :
                    st === 'IN_PROGRESS' ? `⬛ ${op.operation_nom}` : `○ ${op.operation_nom}`;
        const nxt = { PENDING:'IN_PROGRESS', IN_PROGRESS:'COMPLETED' }[st];
        return `<td>${nxt
          ? `<span class="ms ${cls}" onclick="advOperation(${of.id},${op.id},'${st}')">${lbl}</span>
             <div style="font-size:8px;color:var(--muted);margin-top:1px">${op.operateurs_noms||''}</div>`
          : `<span class="ms done">${lbl}</span>`
        }</td>`;
      }).join('');

      return `<tr>
        <td><span class="of-num">${of.numero}</span></td>
        <td>${of.produit_nom}</td>
        <td>${of.client_nom||'—'}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${of.quantite}</td>
        ${opCells}
      </tr>`;
    }).join('');
  } catch(e) { toast('Erreur monitoring: ' + e.message, 'err'); }
}

async function advOperation(ofId, opId, cur) {
  const next = { PENDING:'IN_PROGRESS', IN_PROGRESS:'COMPLETED' }[cur];
  if (!next) return;
  try {
    await api(`/api/of/${ofId}/operations/${opId}`, 'PUT', { statut: next });
    toast(`Opération → ${next} ✓`);
    loadMonitor();
  } catch(e) { toast(e.message, 'err'); }
}
