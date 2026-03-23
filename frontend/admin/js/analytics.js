// ── analytics.js — SOFEM MES v6.0 ────────────────────────

// ══════════════════════════════════════════════════════════
// HELPERS
// ══════════════════════════════════════════════════════════
function anKpi(lbl, val, sub, color='var(--text)') {
  return `<div class="kpi">
    <div class="kpi-lbl">${lbl}</div>
    <div class="kpi-val" style="color:${color}">${val}</div>
    <div class="kpi-det">${sub}</div>
  </div>`;
}

function anBar(label, val, max, color='var(--red)', unit='') {
  const pct = max > 0 ? Math.min(Math.round(val / max * 100), 100) : 0;
  return `<div style="display:flex;align-items:center;gap:.5rem;padding:5px 0;border-bottom:1px solid var(--border)">
    <span style="font-size:11px;width:110px;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${label}</span>
    <div style="flex:1;height:6px;background:var(--bg3);border-radius:3px;overflow:hidden">
      <div style="width:${pct}%;height:100%;background:${color};border-radius:3px;transition:width .5s"></div>
    </div>
    <span style="font-size:10px;font-family:'IBM Plex Mono',monospace;color:var(--muted);width:60px;text-align:right">${val}${unit}</span>
  </div>`;
}

function anBadge(txt, cls) {
  return `<span class="badge ${cls}" style="font-size:9px">${txt}</span>`;
}

// ══════════════════════════════════════════════════════════
// A — PRODUCTION
// ══════════════════════════════════════════════════════════
async function loadAnalyticsProduction() {
  try {
    const d = await api('/api/analytics/production');
    if (!d) return;

    // KPIs
    const total     = d.par_mois?.reduce((s, m) => s + parseInt(m.total||0), 0) || 0;
    const completes = d.par_mois?.reduce((s, m) => s + parseInt(m.completes||0), 0) || 0;
    const taux      = total > 0 ? Math.round(completes / total * 100) : 0;
    const retards   = d.retards?.length || 0;
    const urgents   = d.par_mois?.reduce((s, m) => s + parseInt(m.urgents||0), 0) || 0;

    $('anp-kpis').innerHTML =
      anKpi('Total OFs (12 mois)', total, 'Créés', 'var(--text)') +
      anKpi('Terminés', completes, `Taux ${taux}%`, 'var(--green)') +
      anKpi('Taux complétion', taux + '%', 'Ce cumul', taux >= 75 ? 'var(--green)' : 'var(--accent)') +
      anKpi('En retard', retards, 'Délai dépassé', retards > 0 ? 'var(--red)' : 'var(--green)') +
      anKpi('Urgents', urgents, '12 derniers mois', urgents > 3 ? 'var(--accent)' : 'var(--muted)');

    // Chart par mois
    const chartData = d.par_mois || [];
    if (chartData.length && $('anp-chart')) {
      const maxVal = Math.max(...chartData.map(m => parseInt(m.total||0)), 1);
      $('anp-chart').innerHTML = chartData.map((m, i, arr) => {
        const isCur = i === arr.length - 1;
        const h = Math.max(Math.round(parseInt(m.total||0) / maxVal * 90), 4);
        const tPct = m.total > 0 ? Math.round(m.completes / m.total * 100) : 0;
        return `<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:3px;height:100%">
          <span style="font-size:8px;color:${isCur?'var(--text)':'var(--muted)'};font-family:'IBM Plex Mono',monospace">${m.total}</span>
          <div style="width:100%;height:${h}%;background:${isCur?'var(--red)':'rgba(212,43,43,.4)'};border-radius:2px 2px 0 0"
            title="${m.mois_label}: ${m.total} OFs, ${m.completes} terminés (${tPct}%)"></div>
          <span style="font-size:8px;color:${isCur?'var(--red)':'var(--muted)'};font-weight:${isCur?700:400}">${(m.mois_label||'').slice(0,4)}</span>
        </div>`;
      }).join('');
    }

    // Statuts
    if ($('anp-statuts')) {
      const statuts = d.statuts || [];
      const total_s = statuts.reduce((s, x) => s + parseInt(x.n||0), 0);
      const lbls = {DRAFT:'Brouillon',APPROVED:'Approuvé',IN_PROGRESS:'En cours',COMPLETED:'Terminé',CANCELLED:'Annulé'};
      const cols = {DRAFT:'var(--muted)',APPROVED:'var(--blue)',IN_PROGRESS:'var(--red)',COMPLETED:'var(--green)',CANCELLED:'#6b7280'};
      $('anp-statuts').innerHTML = statuts.map(s =>
        anBar(lbls[s.statut]||s.statut, s.n, total_s, cols[s.statut]||'var(--muted)')
      ).join('');
    }

    // Retards
    if ($('anp-retards')) {
      $('anp-retards').innerHTML = !d.retards?.length
        ? `<tr><td colspan="5" style="text-align:center;color:var(--green);padding:1rem">✓ Aucun OF en retard</td></tr>`
        : d.retards.map(r => `<tr>
            <td><span class="of-num">${r.numero}</span></td>
            <td style="font-size:11px">${r.produit_nom}</td>
            <td style="font-size:11px;color:var(--muted)">${r.client_nom||'—'}</td>
            <td>${anBadge(r.statut, 'b-inprogress')}</td>
            <td style="font-family:'IBM Plex Mono',monospace;color:var(--red);font-weight:600">+${r.jours_retard}j</td>
          </tr>`).join('');
    }

    // Ateliers
    if ($('anp-ateliers') && d.ateliers?.length) {
      const maxA = Math.max(...d.ateliers.map(a => parseInt(a.n||0)), 1);
      $('anp-ateliers').innerHTML = d.ateliers.map(a =>
        anBar(a.atelier, a.n, maxA, 'var(--blue)', ' OFs')
      ).join('');
    }

  } catch(e) { toast('Erreur analytics production: ' + e.message, 'err'); }
}

// ══════════════════════════════════════════════════════════
// B — ACHATS & STOCK
// ══════════════════════════════════════════════════════════
async function loadAnalyticsAchats() {
  try {
    const d = await api('/api/analytics/achats');
    if (!d) return;

    const alertes = (d.stock||[]).filter(m => parseFloat(m.pct||0) <= 100).length;
    const bas     = (d.stock||[]).filter(m => parseFloat(m.pct||0) > 100 && parseFloat(m.pct||0) < 150).length;
    const brs_att = d.brs_attente?.length || 0;

    $('ana-kpis').innerHTML =
      anKpi('Alertes stock', alertes, 'Sous minimum', alertes > 0 ? 'var(--red)' : 'var(--green)') +
      anKpi('Stock bas', bas, '< 150% du min', bas > 0 ? 'var(--accent)' : 'var(--green)') +
      anKpi('Valeur stock', (parseFloat(d.valeur_totale_stock||0)).toFixed(0) + ' DT', 'Total inventaire', 'var(--blue)') +
      anKpi('BRs en attente', brs_att, 'Réceptions pending', brs_att > 0 ? 'var(--accent)' : 'var(--green)') +
      anKpi('Matériaux total', d.stock?.length || 0, 'Références actives', 'var(--muted)');

    if ($('ana-valeur')) $('ana-valeur').textContent = `Valeur totale: ${parseFloat(d.valeur_totale_stock||0).toFixed(2)} DT`;

    // Stock bars
    if ($('ana-stock')) {
      const items = (d.stock||[]).slice(0, 15);
      $('ana-stock').innerHTML = items.map(m => {
        const pct = parseFloat(m.pct||0);
        const col = pct <= 100 ? 'var(--red)' : pct < 150 ? 'var(--accent)' : 'var(--green)';
        const badge = pct <= 100
          ? '<span class="badge b-urgent" style="font-size:8px;margin-left:4px">ALERTE</span>'
          : pct < 150 ? '<span class="badge b-inprogress" style="font-size:8px;margin-left:4px">BAS</span>' : '';
        return `<div style="display:flex;align-items:center;gap:.5rem;padding:5px 0;border-bottom:1px solid var(--border)">
          <div style="flex:1;min-width:0">
            <div style="display:flex;align-items:center;margin-bottom:2px">
              <span style="font-size:11px;font-weight:500">${m.nom}</span>${badge}
            </div>
            <div style="display:flex;align-items:center;gap:.5rem">
              <div style="flex:1;height:5px;background:var(--bg3);border-radius:3px;overflow:hidden">
                <div style="width:${Math.min(pct/2,100)}%;height:100%;background:${col};border-radius:3px"></div>
              </div>
              <span style="font-size:9px;font-family:'IBM Plex Mono',monospace;color:${col};width:34px;text-align:right">${pct}%</span>
              <span style="font-size:9px;color:var(--muted);font-family:'IBM Plex Mono',monospace">${m.stock_actuel}/${m.stock_minimum} ${m.unite}</span>
            </div>
          </div>
        </div>`;
      }).join('');
    }

    // DA statuts
    if ($('ana-da-statuts') && d.da_statuts?.length) {
      const total = d.da_statuts.reduce((s, x) => s + parseInt(x.n||0), 0);
      const lbls = {PENDING:'En attente',APPROVED:'Approuvée',REJECTED:'Rejetée',ORDERED:'Commandée',RECEIVED:'Reçue'};
      const cols = {PENDING:'var(--muted)',APPROVED:'var(--green)',REJECTED:'var(--red)',ORDERED:'var(--blue)',RECEIVED:'var(--green)'};
      $('ana-da-statuts').innerHTML = `<div style="font-size:9px;color:var(--muted);font-family:'IBM Plex Mono',monospace;margin-bottom:.4rem">DEMANDES D'ACHAT</div>` +
        d.da_statuts.map(s => anBar(lbls[s.statut]||s.statut, s.n, total, cols[s.statut]||'var(--muted)')).join('');
    }

    // Fournisseurs
    if ($('ana-fournisseurs') && d.top_fournisseurs?.length) {
      const maxF = Math.max(...d.top_fournisseurs.map(f => parseFloat(f.montant_total||0)), 1);
      $('ana-fournisseurs').innerHTML = `<div style="font-size:9px;color:var(--muted);font-family:'IBM Plex Mono',monospace;margin-bottom:.4rem">TOP FOURNISSEURS (MONTANT)</div>` +
        d.top_fournisseurs.map(f =>
          anBar(f.fournisseur||'—', Math.round(parseFloat(f.montant_total||0)), maxF, 'var(--blue)', ' DT')
        ).join('');
    }

    // Mouvements
    if ($('ana-mouvements')) {
      $('ana-mouvements').innerHTML = !(d.mouvements?.length)
        ? `<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:1rem">Aucun mouvement</td></tr>`
        : d.mouvements.map(mv => `<tr>
            <td>${mv.type === 'ENTREE'
              ? '<span class="badge b-completed" style="font-size:8px">ENTRÉE</span>'
              : '<span class="badge b-cancelled" style="font-size:8px">SORTIE</span>'}</td>
            <td style="font-size:11px">${mv.materiau_nom}</td>
            <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${mv.quantite} ${mv.unite}</td>
            <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted)">${mv.stock_avant}</td>
            <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${mv.stock_apres}</td>
            <td style="font-size:10px;color:var(--muted);max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${mv.motif||'—'}</td>
            <td style="font-size:10px;color:var(--muted)">${String(mv.created_at||'').slice(0,10)}</td>
          </tr>`).join('');
    }

  } catch(e) { toast('Erreur analytics achats: ' + e.message, 'err'); }
}

// ══════════════════════════════════════════════════════════
// C — OPÉRATEURS
// ══════════════════════════════════════════════════════════
async function loadAnalyticsOperateurs() {
  try {
    const d = await api('/api/analytics/operateurs');
    if (!d) return;

    const total_ops = d.performance?.reduce((s, o) => s + parseInt(o.ops_terminees||0), 0) || 0;
    const chefs     = d.performance?.filter(o => o.role === 'CHEF_ATELIER').length || 0;
    const duree_tot = d.performance?.reduce((s, o) => s + parseInt(o.duree_totale_min||0), 0) || 0;
    const heures    = Math.round(duree_tot / 60);

    $('ano-kpis').innerHTML =
      anKpi('Opérateurs actifs', d.performance?.length || 0, 'En équipe', 'var(--blue)') +
      anKpi('Chefs atelier', chefs, 'Responsables', 'var(--accent)') +
      anKpi('Opérations terminées', total_ops, 'Total cumulé', 'var(--green)') +
      anKpi('Heures production', heures + 'h', 'Temps réel enregistré', 'var(--text)') +
      anKpi('Spécialités', d.specialites?.length || 0, 'Métiers représentés', 'var(--muted)');

    // Performance table
    if ($('ano-perf')) {
      const roleLabels = {CHEF_ATELIER:'Chef Atelier',RESPONSABLE:'Responsable',TECHNICIEN:'Technicien',OPERATEUR:'Opérateur'};
      const roleCls   = {CHEF_ATELIER:'b-approved',RESPONSABLE:'b-inprogress',TECHNICIEN:'b-draft',OPERATEUR:'b-normal'};
      $('ano-perf').innerHTML = !(d.performance?.length)
        ? `<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:1rem">Aucune donnée</td></tr>`
        : d.performance.map(o => {
          const dur = parseInt(o.duree_totale_min||0);
          const durStr = dur > 0 ? (dur >= 60 ? Math.floor(dur/60)+'h'+String(dur%60).padStart(2,'0') : dur+'min') : '—';
          const tauxStr = o.type_taux==='PIECE' ? `${o.taux_piece} DT/pcs`
                        : o.type_taux==='BOTH'  ? `${o.taux_horaire}+${o.taux_piece}`
                        : `${o.taux_horaire} DT/h`;
          return `<tr>
            <td><div style="display:flex;align-items:center;gap:.5rem">
              <div style="width:26px;height:26px;border-radius:50%;background:var(--red-g);display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:600;color:var(--red);flex-shrink:0">${(o.prenom[0]||'')}${(o.nom[0]||'')}</div>
              <span>${o.prenom} ${o.nom}</span>
            </div></td>
            <td>${anBadge(roleLabels[o.role]||'Opérateur', roleCls[o.role]||'b-draft')}</td>
            <td><span class="badge b-draft" style="font-size:9px">${o.specialite||'—'}</span></td>
            <td style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--green);font-weight:600">${o.ops_terminees}</td>
            <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted)">${durStr}</td>
            <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${o.ofs_impliques}</td>
            <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--accent)">${tauxStr}</td>
          </tr>`;
        }).join('');
    }

    // Spécialités
    if ($('ano-specialites') && d.specialites?.length) {
      const maxS = Math.max(...d.specialites.map(s => parseInt(s.n||0)), 1);
      $('ano-specialites').innerHTML = d.specialites.map(s =>
        anBar(s.specialite||'—', s.n, maxS, 'var(--blue)', ' op.')
      ).join('');
    }

    // Coûts par opération
    if ($('ano-cout-ops') && d.cout_par_operation?.length) {
      const maxC = Math.max(...d.cout_par_operation.map(o => parseFloat(o.cout_total||0)), 1);
      $('ano-cout-ops').innerHTML = d.cout_par_operation.map(o =>
        anBar(o.operation_nom, Math.round(parseFloat(o.cout_total||0)), maxC, 'var(--red)', ' DT')
      ).join('');
    } else if ($('ano-cout-ops')) {
      $('ano-cout-ops').innerHTML = '<div style="color:var(--muted);font-size:11px;padding:.75rem">Aucune donnée — saisir les durées d\'opérations (bouton ⏱)</div>';
    }

  } catch(e) { toast('Erreur analytics opérateurs: ' + e.message, 'err'); }
}

// ══════════════════════════════════════════════════════════
// D — QUALITÉ
// ══════════════════════════════════════════════════════════
async function loadAnalyticsQualite() {
  try {
    const d = await api('/api/analytics/qualite');
    if (!d) return;

    const kpis    = d.kpis    || {};
    const nc_kpis = d.nc_kpis || {};
    const taux    = parseFloat(kpis.taux_global||0);

    $('anq-kpis').innerHTML =
      anKpi('Taux conformité', (taux||0) + '%', 'Global cumulé', taux >= 95 ? 'var(--green)' : taux >= 85 ? 'var(--accent)' : 'var(--red)') +
      anKpi('Total contrôles', kpis.total_cq||0, 'CQs réalisés', 'var(--blue)') +
      anKpi('NCs ouvertes', nc_kpis.ouvertes||0, 'À traiter', (nc_kpis.ouvertes||0) > 0 ? 'var(--red)' : 'var(--green)') +
      anKpi('NCs critiques', nc_kpis.critiques||0, 'Priorité urgente', (nc_kpis.critiques||0) > 0 ? 'var(--red)' : 'var(--green)') +
      anKpi('Pièces rebutées', kpis.total_rebut||0, 'Total cumulé', (kpis.total_rebut||0) > 0 ? 'var(--accent)' : 'var(--green)');

    // Chart taux par mois
    if ($('anq-chart') && d.par_mois?.length) {
      const max = 100;
      $('anq-chart').innerHTML = d.par_mois.map((m, i, arr) => {
        const isCur = i === arr.length - 1;
        const taux_m = parseFloat(m.taux||0);
        const h = Math.max(Math.round(taux_m / max * 90), 4);
        const col = taux_m >= 95 ? '#16a34a' : taux_m >= 85 ? '#d97706' : '#D42B2B';
        return `<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:3px;height:100%">
          <span style="font-size:8px;color:${isCur?col:'var(--muted)'};font-family:'IBM Plex Mono',monospace">${taux_m}%</span>
          <div style="width:100%;height:${h}%;background:${isCur?col:col+'88'};border-radius:2px 2px 0 0"
            title="${m.mois_label}: ${taux_m}% conformité"></div>
          <span style="font-size:8px;color:${isCur?col:'var(--muted)'};font-weight:${isCur?700:400}">${(m.mois_label||'').slice(0,4)}</span>
        </div>`;
      }).join('');
    } else if ($('anq-chart')) {
      $('anq-chart').innerHTML = '<div style="color:var(--muted);font-size:11px;padding:1rem;text-align:center">Aucune donnée de contrôle</div>';
    }

    // Types défauts
    if ($('anq-defauts') && d.defauts?.length) {
      const maxD = Math.max(...d.defauts.map(x => parseInt(x.n||0)), 1);
      $('anq-defauts').innerHTML = d.defauts.map(x =>
        anBar(x.type_defaut||'—', x.n, maxD, 'var(--red)', ' cas')
      ).join('');
    } else if ($('anq-defauts')) {
      $('anq-defauts').innerHTML = '<div style="color:var(--muted);font-size:11px;padding:.75rem">Aucune non-conformité enregistrée</div>';
    }

    // NCs ouvertes
    if ($('anq-nc')) {
      const gravBadge = g => g === 'CRITIQUE'
        ? '<span class="badge b-urgent" style="font-size:8px">CRITIQUE</span>'
        : g === 'MAJEURE'
          ? '<span class="badge b-inprogress" style="font-size:8px">MAJEURE</span>'
          : '<span class="badge b-draft" style="font-size:8px">MINEURE</span>';
      $('anq-nc').innerHTML = !(d.nc_ouvertes?.length)
        ? `<tr><td colspan="8" style="text-align:center;color:var(--green);padding:1rem">✓ Aucune non-conformité ouverte</td></tr>`
        : d.nc_ouvertes.map(nc => `<tr>
            <td><span class="of-num" style="font-size:10px">${nc.nc_numero}</span></td>
            <td style="font-size:10px;color:var(--muted)">${nc.of_numero||'—'}</td>
            <td style="font-size:11px">${nc.produit_nom||'—'}</td>
            <td style="font-size:11px">${nc.type_defaut||'—'}</td>
            <td>${gravBadge(nc.gravite)}</td>
            <td style="font-size:11px;color:var(--muted)">${nc.resp_prenom ? nc.resp_prenom+' '+nc.resp_nom : '—'}</td>
            <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:${parseInt(nc.age_jours||0)>7?'var(--red)':'var(--muted)'}">${nc.age_jours}j</td>
            <td style="font-size:10px;color:var(--muted);max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${nc.action_corrective||'—'}</td>
          </tr>`).join('');
    }

  } catch(e) { toast('Erreur analytics qualité: ' + e.message, 'err'); }
}

// ══════════════════════════════════════════════════════════
// PAGE LOADERS (called by navigate())
// ══════════════════════════════════════════════════════════
window.pageLoaders = window.pageLoaders || {};
window.pageLoaders['analytics-production'] = loadAnalyticsProduction;
window.pageLoaders['analytics-achats']     = loadAnalyticsAchats;
window.pageLoaders['analytics-operateurs'] = loadAnalyticsOperateurs;
window.pageLoaders['analytics-qualite']    = loadAnalyticsQualite;
