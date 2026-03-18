//  ── dashboard.js v6 ──────────────────────────────────────
let _dashOfs = [];

async function loadDashboard() {
  try {
    const [dash, ofs, mats] = await Promise.all([
      api('/api/dashboard'),
      api('/api/of?limit=100'),
      api('/api/materiaux')
    ]);
    if (!dash) return;
    _dashOfs = ofs || [];

    // KPIs
    if ($('k-actifs'))  $('k-actifs').textContent  = dash.ordres_actifs  ?? 0;
    if ($('k-urgents')) $('k-urgents').textContent = dash.urgents        ?? 0;
    if ($('k-taux'))    $('k-taux').textContent    = (dash.taux_completion ?? 0) + '%';
    if ($('k-stock'))   $('k-stock').textContent   = dash.alertes_stock  ?? 0;
    if ($('k-retard'))  $('k-retard').textContent  = dash.en_retard      ?? 0;

    // Populate OF selector - show active OFs first
    const sel = $('pipeline-of-select');
    if (sel && ofs) {
      const sorted = [...ofs].sort((a,b) => {
        const order = {IN_PROGRESS:0, APPROVED:1, DRAFT:2, COMPLETED:3, CANCELLED:4};
        return (order[a.statut]??9) - (order[b.statut]??9);
      });
      sel.innerHTML = '<option value="">— Sélectionner un OF —</option>' +
        sorted.map(o =>
          `<option value="${o.id}">${o.numero} · ${o.produit_nom} · ${sBadgeText(o.statut)}</option>`
        ).join('');
      // Auto-select first IN_PROGRESS
      const first = sorted.find(o => o.statut === 'IN_PROGRESS');
      if (first) { sel.value = first.id; renderDashPipeline(); }
    }

    // Recent OFs table
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

// Render pipeline for the selected OF
function renderDashPipeline() {
  const sel = $('pipeline-of-select');
  const pipeEl = $('dash-pipeline');
  if (!sel || !pipeEl) return;

  const ofId = parseInt(sel.value);
  if (!ofId) {
    pipeEl.innerHTML = '<div style="color:var(--muted);font-size:11px;font-family:\'IBM Plex Mono\',monospace">Sélectionnez un OF pour voir ses opérations</div>';
    return;
  }

  const of = _dashOfs.find(o => o.id === ofId);
  if (!of) return;

  const ops = of.operations || [];
  if (ops.length === 0) {
    pipeEl.innerHTML = '<div style="color:var(--muted);font-size:11px;font-family:\'IBM Plex Mono\',monospace">Aucune opération définie pour cet OF</div>';
    return;
  }

  pipeEl.innerHTML = ops.map((op, i) => {
    const st  = op.statut || 'PENDING';
    const cls = st === 'COMPLETED' ? 'done' : st === 'IN_PROGRESS' ? 'active' : 'pending';
    const val = st === 'COMPLETED' ? '✓' : st === 'IN_PROGRESS' ? '▶' : '○';
    const opNom = op.operateurs_noms
      ? `<div style="font-size:8px;color:var(--muted);margin-top:2px;text-align:center;max-width:70px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${op.operateurs_noms}</div>`
      : '';
    return `<div class="stage" style="align-items:center">
      <div class="sb ${cls}" title="${st}">${val}</div>
      <div class="stage-name">${op.operation_nom}</div>
      ${opNom}
    </div>${i < ops.length-1 ? '<div style="color:var(--muted);margin:0 4px;font-size:14px">→</div>' : ''}`;
  }).join('');
}

function sBadgeText(s) {
  return {IN_PROGRESS:'En Cours', COMPLETED:'Terminé', DRAFT:'Brouillon', APPROVED:'Approuvé', CANCELLED:'Annulé'}[s] || s;
}
