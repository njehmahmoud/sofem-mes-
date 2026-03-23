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

    // Stock — render to dash-mats (correct ID)
    if (mats && $('dash-mats')) {
      const alerts = mats.filter(m => parseFloat(m.stock_actuel) <= parseFloat(m.stock_minimum));
      const low    = mats.filter(m => {
        const pct = m.stock_minimum > 0 ? m.stock_actuel / m.stock_minimum : 1;
        return pct > 1 && pct < 1.5;
      });
      if ($('stock-ct')) $('stock-ct').textContent = alerts.length || '✓';
      if ($('stock-ct')) $('stock-ct').className = alerts.length ? 'badge b-urgent' : 'badge b-completed';

      if (!mats.length) {
        $('dash-mats').innerHTML = '<div style="color:var(--muted);font-size:11px;padding:1rem">Aucun matériau</div>';
      } else {
        // Show all materials with stock bar, alerts first
        const sorted = [...mats].sort((a,b) => {
          const pa = a.stock_minimum > 0 ? a.stock_actuel/a.stock_minimum : 999;
          const pb = b.stock_minimum > 0 ? b.stock_actuel/b.stock_minimum : 999;
          return pa - pb;
        });
        $('dash-mats').innerHTML = sorted.slice(0, 12).map(m => {
          const pct    = m.stock_minimum > 0 ? Math.min(m.stock_actuel / m.stock_minimum, 2) : 1;
          const pctVal = m.stock_minimum > 0 ? Math.round(m.stock_actuel / m.stock_minimum * 100) : 100;
          const cls    = pct <= 1 ? 'd' : pct < 1.5 ? 'w' : 'ok';
          const badge  = pct <= 1
            ? '<span class="badge b-urgent" style="font-size:8px">ALERTE</span>'
            : pct < 1.5
              ? '<span class="badge b-inprogress" style="font-size:8px">BAS</span>'
              : '';
          return \`<div class="mat-item">
            <div style="flex:1;min-width:0">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">
                <span class="mat-name" style="font-size:11px">\${m.nom}</span>
                \${badge}
              </div>
              <div style="display:flex;align-items:center;gap:.5rem">
                <div class="bar-w"><div class="bar-f \${cls}" style="width:\${Math.min(pct*50,100)}%"></div></div>
                <span class="bar-pct \${cls}">\${pctVal}%</span>
                <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--muted)">\${m.stock_actuel} / \${m.stock_minimum} \${m.unite}</span>
              </div>
            </div>
          </div>\`;
        }).join('');
      }
    }

    // OF par mois — improved chart with total count + taux completion
    if ($('dash-chart')) {
      const data = dash.graphique || [];
      if (!data.length) {
        $('dash-chart').innerHTML = '<div style="color:var(--muted);font-size:11px;padding:1rem;text-align:center">Aucune donnée</div>';
      } else {
        const max = Math.max(...data.map(d => d.total), 1);
        if ($('chart-taux')) $('chart-taux').textContent = \`Taux: \${dash.taux_completion ?? 0}%\`;
        $('dash-chart').innerHTML = \`
          <div style="display:flex;align-items:flex-end;gap:6px;height:100%;padding:0 8px">
            \${data.map((d, i, arr) => {
              const isCurrent = i === arr.length - 1;
              const h = Math.max(Math.round(d.total / max * 80), 4);
              return \`<div class="bc" style="position:relative" title="\${d.mois}: \${d.total} OF">
                <div style="position:relative;width:100%;display:flex;flex-direction:column;
                  align-items:center;justify-content:flex-end;flex:1">
                  <span style="font-family:'IBM Plex Mono',monospace;font-size:8px;
                    color:\${isCurrent?'var(--text)':'var(--muted)'};margin-bottom:3px;font-weight:\${isCurrent?700:400}">\${d.total}</span>
                  <div class="bf\${isCurrent?' cur':''}"
                    style="width:100%;height:\${h}%;border-radius:3px 3px 0 0;
                      background:\${isCurrent?'var(--red)':'rgba(212,43,43,0.45)'};
                      transition:height .6s ease"></div>
                </div>
                <div class="bl" style="font-size:8px;color:\${isCurrent?'var(--red)':'var(--muted)'};
                  font-weight:\${isCurrent?700:400};margin-top:4px;white-space:nowrap">
                  \${(d.mois||'').slice(0,6)}
                </div>
              </div>\`;
            }).join('')}
          </div>\`;
      }
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