// ── dashboard.js v6 ──────────────────────────────────────
async function loadDashboard() {
  try {
    const [dash, ofs, mats] = await Promise.all([
      api('/api/dashboard'),
      api('/api/of?limit=10'),
      api('/api/materiaux')
    ]);
    if (!dash) return;

    // KPIs — use correct element IDs from HTML
    if ($('k-actifs'))  $('k-actifs').textContent  = dash.ordres_actifs  ?? 0;
    if ($('k-urgents')) $('k-urgents').textContent = dash.urgents        ?? 0;
    if ($('k-taux'))    $('k-taux').textContent    = (dash.taux_completion ?? 0) + '%';
    if ($('k-stock'))   $('k-stock').textContent   = dash.alertes_stock  ?? 0;
    if ($('k-retard'))  $('k-retard').textContent  = dash.en_retard      ?? 0;

    // Pipeline — dynamic from active OFs
    if (ofs) {
      const activeOfs = ofs.filter(o => o.statut === 'IN_PROGRESS');
      const opNames = [...new Set(
        activeOfs.flatMap(o => (o.operations||[]).map(op => op.operation_nom))
      )];
      const pipeEl = document.querySelector('.pipeline-steps');
      if (pipeEl) {
        if (opNames.length === 0) {
          pipeEl.innerHTML = '<div style="color:var(--muted);font-size:11px;padding:1rem;font-family:\'IBM Plex Mono\',monospace">Aucun ordre en cours</div>';
        } else {
          pipeEl.innerHTML = opNames.map((name, i) => {
            const all  = activeOfs.flatMap(o => (o.operations||[]).filter(op => op.operation_nom === name));
            const inp  = all.filter(op => op.statut === 'IN_PROGRESS').length;
            const done = all.filter(op => op.statut === 'COMPLETED').length;
            const cls  = inp > 0 ? 'active' : done > 0 ? 'done' : 'pending';
            const val  = inp > 0 ? inp : done > 0 ? '✓' : '○';
            return `<div class="ps">
              <div class="ps-circle ${cls}"><span>${val}</span></div>
              <div class="ps-label">${name}</div>
            </div>${i < opNames.length-1 ? '<div class="ps-arrow">→</div>' : ''}`;
          }).join('');
        }
      }
    }

    // Recent OFs table
    if (ofs && $('dash-ofs')) {
      $('dash-ofs').innerHTML = ofs.length === 0 ? empty(7) : ofs.slice(0,6).map(of => `
        <tr>
          <td><span class="of-num">${of.numero}</span></td>
          <td>${of.produit_nom}</td>
          <td style="font-size:11px;color:var(--muted)">${of.client_nom||'—'}</td>
          <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${of.quantite}</td>
          <td>${pBadge(of.priorite)}</td>
          <td>${sBadge(of.statut)}</td>
          <td>${dots(of.operations)}</td>
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
    if (dash.graphique?.length && $('rep-chart')) {
      const max = Math.max(...dash.graphique.map(d => d.total), 1);
      $('rep-chart').innerHTML = dash.graphique.map((d, i, arr) =>
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