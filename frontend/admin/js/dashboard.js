// ── dashboard.js ─────────────────────────────────────────
async function loadDashboard() {
  try {
    const [dash, ofs, mats, ops] = await Promise.all([
      api('/api/dashboard'), api('/api/of?limit=500'),
      api('/api/materiaux'), api('/api/operateurs')
    ]);
    if (!dash) return;

    $('kpi-ofs').textContent      = dash.total_ofs ?? 0;
    $('kpi-inprogress').textContent = dash.in_progress ?? 0;
    $('kpi-completed').textContent  = dash.completed_today ?? 0;
    $('kpi-alerts').textContent     = dash.stock_alerts ?? 0;

    // Mini chart
    if (dash.production_par_semaine) {
      const max = Math.max(...dash.production_par_semaine.map(d => d.total), 1);
      $('week-chart').innerHTML = dash.production_par_semaine.map(d =>
        `<div class="bc"><div style="height:${Math.round(d.total/max*60)}px" class="bf"></div>
         <div class="bl">${(d.jour||'').slice(0,3)}</div></div>`
      ).join('');
    }

    // Recent OFs
    if (ofs) {
      $('dash-ofs').innerHTML = ofs.slice(0,6).map(of =>
        `<tr><td><span class="of-num">${of.numero}</span></td>
         <td>${of.produit_nom}</td><td>${of.quantite}</td>
         <td>${pBadge(of.priorite)}</td><td>${sBadge(of.statut)}</td>
         <td>${dots(of.operations)}</td>
         <td>${dateTd(of.date_echeance)}</td></tr>`
      ).join('') || empty(7);
    }

    // Stock alerts
    if (mats) {
      const alerts = mats.filter(m => parseFloat(m.stock_actuel) <= parseFloat(m.stock_minimum));
      $('dash-alerts').innerHTML = alerts.length === 0
        ? '<div style="color:var(--green);font-size:11px;padding:.5rem">✓ Tous les stocks OK</div>'
        : alerts.map(m => `<div class="mat-item">
            <div style="flex:1"><div class="mat-name">${m.nom}</div>
            <div class="mat-ref">${m.stock_actuel}/${m.stock_minimum} ${m.unite}</div></div>
            <span class="badge b-urgent">ALERTE</span></div>`
          ).join('');
    }
  } catch(e) { toast('Erreur dashboard: ' + e.message, 'err'); }
}
