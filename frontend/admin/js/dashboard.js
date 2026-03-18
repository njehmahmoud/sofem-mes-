// ── dashboard.js v6 ──────────────────────────────────────
async function loadDashboard() {
  try {
    const [dash, ofs, mats] = await Promise.all([
      api('/api/dashboard'),
      api('/api/of?limit=50'),
      api('/api/materiaux')
    ]);
    if (!dash) return;

    // KPIs
    if ($('k-actifs'))  $('k-actifs').textContent  = dash.ordres_actifs  ?? 0;
    if ($('k-urgents')) $('k-urgents').textContent = dash.urgents        ?? 0;
    if ($('k-taux'))    $('k-taux').textContent    = (dash.taux_completion ?? 0) + '%';
    if ($('k-stock'))   $('k-stock').textContent   = dash.alertes_stock  ?? 0;
    if ($('k-retard'))  $('k-retard').textContent  = dash.en_retard      ?? 0;

    // Pipeline — aggregate all operations across IN_PROGRESS OFs
    const pipeEl = $('dash-pipeline');
    if (pipeEl && ofs) {
      const activeOfs = ofs.filter(o => o.statut === 'IN_PROGRESS');
      // collect unique operation names preserving order
      const opMap = new Map();
      activeOfs.forEach(of => {
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
          const cls = s.inp > 0 ? 'active' : s.done === s.total ? 'done' : 'pending';
          const val = s.inp > 0 ? s.inp : s.done > 0 ? '✓' : '○';
          return `<div class="stage">
            <div class="sb ${cls}">${val}</div>
            <div class="stage-name">${name}</div>
          </div>${i < entries.length-1 ? '<div style="color:var(--muted);margin:0 4px">→</div>' : ''}`;
        }).join('');
      }
    }

    // Recent OFs — 8 cols: N° OF, Produit, Client, Qté, Priorité, Statut, Opérations, Échéance
    if (ofs && $('dash-ofs')) {
      $('dash-ofs').innerHTML = ofs.length === 0 ? empty(8) : ofs.slice(0,6).map(of => `
        <tr>
          <td><span class="of-num">${of.numero}</span></td>
          <td>${of.produit_nom}</td>
          <td style="font-size:11px;color:var(--muted)">${of.client_nom||'—'}</td>
          <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${of.quantite}</td>
          <td>${pBadge(of.priorite)}</td>
          <td>${sBadge(of.statut)}</td>
          <td>${dots(of.operations)}</td>
          <td>${dateTd(of.date_echeance)}</td>
        </tr>`).join('');
    }

    // Stock alerts
    if (mats && $('dash-alerts')) {
      const alerts = mats.filter(m => parseFloat(m.stock_actuel) <= parseFloat(m.stock_minimum));
      $('dash-alerts').innerHTML = alerts.length === 0
        ? '<div style="color:var(--green);font-size:11px;padding:.5rem">✓ Tous les stocks OK</div>'
        : alerts.map(m => `
          <div class="mat-item">
            <div style="flex:1">
              <div class="mat-name">${m.nom}</div>
              <div class="mat-ref">${m.stock_actuel} / ${m.stock_minimum} ${m.unite}</div>
            </div>
            <span class="badge b-urgent">ALERTE</span>
          </div>`).join('');
    }

    // OF par mois chart
    if (dash.graphique?.length && $('dash-chart')) {
      const max = Math.max(...dash.graphique.map(d => d.total), 1);
      $('dash-chart').innerHTML = dash.graphique.map((d, i, arr) =>
        `<div class="bc">
          <div style="position:relative;width:100%;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;flex:1">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:7px;color:var(--text);margin-bottom:2px">${d.total}</span>
            <div class="bf${i===arr.length-1?' cur':''}" style="width:100%;height:${Math.round(d.total/max*80)}%"></div>
          </div>
          <div class="bl">${(d.mois||'').slice(0,3)}</div>
        </div>`).join('');
    }

  } catch(e) { toast('Erreur dashboard: ' + e.message, 'err'); }
}
