// ── monitor.js v6 ────────────────────────────────────────
async function loadMonitor() {
  try {
    const all = await api('/api/of?limit=500') || [];
    const active = all.filter(o => o.statut === 'IN_PROGRESS');

    $('mon-stats').textContent = `${active.length} ORDRES EN COURS`;

    // Dynamic pipeline — aggregate operation statuses across all active OFs
    const pipeEl = $('mon-pipeline');
    if (pipeEl) {
      const opMap = new Map();
      active.forEach(of => {
        (of.operations||[]).forEach(op => {
          if (!opMap.has(op.operation_nom)) opMap.set(op.operation_nom, {inp:0, done:0, total:0});
          const e = opMap.get(op.operation_nom);
          e.total++;
          if (op.statut === 'IN_PROGRESS') e.inp++;
          if (op.statut === 'COMPLETED')   e.done++;
        });
      });
      if (opMap.size === 0) {
        pipeEl.innerHTML = '<div style="color:var(--muted);font-size:11px;font-family:\'IBM Plex Mono\',monospace;padding:.5rem">Aucun ordre en cours</div>';
      } else {
        const entries = [...opMap.entries()];
        pipeEl.innerHTML = entries.map(([name, s], i) => {
          const cls = s.inp > 0 ? 'active' : s.done === s.total && s.total > 0 ? 'done' : 'pending';
          const val = s.inp > 0 ? s.inp : s.done > 0 ? '✓' : '○';
          return `<div class="stage">
            <div class="sb ${cls}">${val}</div>
            <div class="stage-name">${name}</div>
          </div>${i < entries.length-1 ? '<div style="color:var(--muted);margin:0 4px">→</div>' : ''}`;
        }).join('');
      }
    }

    // Monitor table — one row per active OF, one cell per operation
    if (active.length === 0) {
      $('monitor-tb').innerHTML = empty(5, 'Aucun ordre en cours');
      return;
    }

    $('monitor-tb').innerHTML = active.map(of => {
      const opCells = (of.operations||[]).map(op => {
        const st  = op.statut || 'PENDING';
        const cls = st === 'COMPLETED' ? 'done' : st === 'IN_PROGRESS' ? 'in_progress' : 'pending';
        const lbl = st === 'COMPLETED'   ? `✓ ${op.operation_nom}`
                  : st === 'IN_PROGRESS' ? `⬛ ${op.operation_nom}`
                  :                        `○ ${op.operation_nom}`;
        const nxt = {PENDING:'IN_PROGRESS', IN_PROGRESS:'COMPLETED'}[st];
        const opNames = op.operateurs_noms
          ? `<div style="font-size:8px;color:var(--muted);margin-top:1px">${op.operateurs_noms}</div>`
          : '';
        return `<td>${nxt
          ? `<span class="ms ${cls}" style="cursor:pointer" onclick="advOperation(${of.id},${op.id},'${st}')">${lbl}</span>${opNames}`
          : `<span class="ms done">${lbl}</span>${opNames}`
        }</td>`;
      }).join('');

      return `<tr>
        <td><span class="of-num">${of.numero}</span></td>
        <td>${of.produit_nom}</td>
        <td style="font-size:11px;color:var(--muted)">${of.client_nom||'—'}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${of.quantite}</td>
        ${opCells || '<td style="color:var(--muted);font-size:11px">— Aucune opération —</td>'}
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
