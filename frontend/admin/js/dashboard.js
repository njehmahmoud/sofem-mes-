// ── dashboard.js v6 ──────────────────────────────────────
async function loadDashboard() {
  try {
    const [dash, ofs, mats] = await Promise.all([
      api('/api/dashboard'),
      api('/api/of?limit=10'),
      api('/api/materiaux')
    ]);
    if (!dash) return;

    // KPIs
    if ($('kpi-ofs'))        $('kpi-ofs').textContent        = dash.ordres_actifs  ?? 0;
    if ($('kpi-inprogress')) $('kpi-inprogress').textContent = dash.urgents        ?? 0;
    if ($('kpi-completed'))  $('kpi-completed').textContent  = dash.completed_today ?? dash.taux_completion ?? 0;
    if ($('kpi-alerts'))     $('kpi-alerts').textContent     = dash.alertes_stock  ?? 0;

    // Pipeline — dynamic: collect all unique operation names across active OFs
    if (ofs) {
      const activeOfs = ofs.filter(o => o.statut === 'IN_PROGRESS');
      // Collect all unique operation names
      const opNames = [...new Set(
        activeOfs.flatMap(o => (o.operations||[]).map(op => op.operation_nom))
      )];

      // Count statuses per operation name
      const pipeline = opNames.map(name => {
        const all  = activeOfs.flatMap(o => (o.operations||[]).filter(op => op.operation_nom === name));
        const inp  = all.filter(op => op.statut === 'IN_PROGRESS').length;
        const done = all.filter(op => op.statut === 'COMPLETED').length;
        return { name, inp, done };
      });

      const pipeEl = document.querySelector('.pipeline-steps') || document.getElementById('pipeline');
      if (pipeEl && pipeline.length > 0) {
        pipeEl.innerHTML = pipeline.map((p, i) => `
          <div class="ps">
            <div class="ps-circle ${p.inp > 0 ? 'active' : p.done > 0 ? 'done' : 'pending'}">
              <span>${p.inp > 0 ? p.inp : p.done > 0 ? '✓' : '○'}</span>
            </div>
            <div class="ps-label">${p.name}</div>
          </div>
          ${i < pipeline.length-1 ? '<div class="ps-arrow">→</div>' : ''}
        `).join('');
      } else if (pipeEl) {
        pipeEl.innerHTML = '<div style="color:var(--muted);font-size:11px;padding:1rem">Aucun ordre en cours</div>';
      }
    }

    // Recent OFs table
    if (ofs && $('dash-ofs')) {
      $('dash-ofs').innerHTML = ofs.length === 0 ? empty(7) : ofs.slice(0, 6).map(of => `
        <tr>
          <td><span class="of-num">${of.numero}</span></td>
          <td>${of.produit_nom}</td>
          <td style="font-size:11px;color:var(--muted)">${of.client_nom||'—'}</td>
          <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${of.quantite}</td>
          <td>${pBadge(of.priorite)}</td>
          <td>${sBadge(of.statut)}</td>
          <td>${dots(of.operations)}</td>
        </tr>`
      ).join('');
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
            </div>`
          ).join('');
    }

    // Chart (OF par mois)
    if (dash.graphique && $('rep-chart')) {
      const data = dash.graphique;
      const max = Math.max(...data.map(d => d.total), 1);
      $('rep-chart').innerHTML = data.map((d, i) =>
        `<div class="bc">
          <div style="position:relative;width:100%;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;flex:1">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:7px;color:var(--text);margin-bottom:2px">${d.total}</span>
            <div class="bf${i===data.length-1?' cur':''}" style="width:100%;height:${Math.round(d.total/max*80)}%"></div>
          </div>
          <div class="bl">${(d.mois||'').slice(0,3)}</div>
        </div>`
      ).join('');
    }

  } catch(e) { toast('Erreur dashboard: ' + e.message, 'err'); }
}
