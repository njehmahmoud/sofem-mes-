// ── analytics.js — SOFEM MES v6.0 ────────────────────────

// ══════════════════════════════════════════════════════════
// HELPERS — use existing design system classes
// ══════════════════════════════════════════════════════════

function anKpiCard(lbl, val, sub, accent='') {
  const cls = accent ? ` ${accent}` : '';
  return `<div class="kpi${cls}">
    <div class="kpi-lbl">${lbl}</div>
    <div class="kpi-val">${val}</div>
    <div class="kpi-det">${sub}</div>
  </div>`;
}

function anBarRow(label, value, maxVal, color, unit='') {
  const pct = maxVal > 0 ? Math.min(Math.round(value / maxVal * 100), 100) : 0;
  return `<div style="display:flex;align-items:center;gap:.75rem;padding:.55rem 1.25rem;border-bottom:1px solid var(--border)">
    <span style="font-size:11px;width:130px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text)">${label}</span>
    <div style="flex:1;height:5px;background:var(--bg3);border-radius:3px;overflow:hidden">
      <div style="width:${pct}%;height:100%;background:${color};border-radius:3px;transition:width .6s ease"></div>
    </div>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted);width:70px;text-align:right;flex-shrink:0">${value}${unit}</span>
  </div>`;
}

function anChartBar(label, value, maxVal, isCurrent, color, tooltip) {
  const h = maxVal > 0 ? Math.max(Math.round(value / maxVal * 100), 4) : 4;
  const opacity = isCurrent ? '1' : '.45';
  return `<div class="bc" title="${tooltip}">
    <div style="position:relative;width:100%;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;flex:1">
      <span style="font-family:'IBM Plex Mono',monospace;font-size:8px;color:${isCurrent?'var(--text)':'var(--muted)'};margin-bottom:2px;font-weight:${isCurrent?600:400}">${value}</span>
      <div style="width:100%;height:${h}%;background:${color};opacity:${opacity};border-radius:2px 2px 0 0;transition:height .6s ease"></div>
    </div>
    <div class="bl" style="color:${isCurrent?color:'var(--muted)'};font-weight:${isCurrent?600:400}">${label}</div>
  </div>`;
}

function gravBadge(g) {
  if (g === 'CRITIQUE') return '<span class="badge b-urgent">CRITIQUE</span>';
  if (g === 'MAJEURE')  return '<span class="badge b-high">MAJEURE</span>';
  return '<span class="badge b-draft">MINEURE</span>';
}

function typeBadge(type) {
  if (type === 'ENTREE') return '<span class="badge b-completed">↑ ENTRÉE</span>';
  return '<span class="badge b-urgent">↓ SORTIE</span>';
}

// ══════════════════════════════════════════════════════════
// A — ANALYTIQUE PRODUCTION
// ══════════════════════════════════════════════════════════
async function loadAnalyticsProduction() {
  const container = $('anp-kpis');
  if (container) container.innerHTML = '<div class="loading"><div class="spin"></div>CHARGEMENT...</div>';
  try {
    const d = await api('/api/analytics/production');
    if (!d) return;

    const total     = d.par_mois?.reduce((s,m)=>s+parseInt(m.total||0),0)||0;
    const completes = d.par_mois?.reduce((s,m)=>s+parseInt(m.completes||0),0)||0;
    const taux      = total>0?Math.round(completes/total*100):0;
    const retards   = d.retards?.length||0;
    const enCours   = (d.statuts||[]).find(s=>s.statut==='IN_PROGRESS')?.n||0;

    // KPIs
    $('anp-kpis').innerHTML =
      anKpiCard('OFs (12 mois)',   total,    'Total créés') +
      anKpiCard('Terminés',        completes,`${taux}% du total`, 'g') +
      anKpiCard('En cours',        enCours,  'Actifs maintenant', 'b') +
      anKpiCard('En retard',       retards,  'Délai dépassé', retards>0?'':'g') +
      anKpiCard('Taux complétion', taux+'%', 'Cumulé 12 mois', taux>=75?'g':taux>=50?'a':'');

    // Chart par mois
    if ($('anp-chart')) {
      const data = d.par_mois||[];
      if (!data.length) {
        $('anp-chart').innerHTML = '<div class="empty">Aucune donnée</div>';
      } else {
        const maxV = Math.max(...data.map(m=>parseInt(m.total||0)),1);
        $('anp-chart').innerHTML = data.map((m,i,arr)=>{
          const isCur = i===arr.length-1;
          const tooltip = `${m.mois_label}: ${m.total} OFs, ${m.completes} terminés`;
          return anChartBar((m.mois_label||'').slice(0,4), parseInt(m.total||0), maxV, isCur, 'var(--red)', tooltip);
        }).join('');
      }
    }

    // Statuts
    if ($('anp-statuts')) {
      const statuts = d.statuts||[];
      const total_s = statuts.reduce((s,x)=>s+parseInt(x.n||0),0)||1;
      const lbls  = {DRAFT:'Brouillon',APPROVED:'Approuvé',IN_PROGRESS:'En cours',COMPLETED:'Terminé',CANCELLED:'Annulé'};
      const colors= {DRAFT:'var(--muted)',APPROVED:'var(--blue)',IN_PROGRESS:'var(--red)',COMPLETED:'var(--green)',CANCELLED:'#4b5563'};
      if (!statuts.length) {
        $('anp-statuts').innerHTML = '<div class="empty">Aucun OF</div>';
      } else {
        $('anp-statuts').innerHTML = statuts.map(s=>
          anBarRow(lbls[s.statut]||s.statut, parseInt(s.n||0), total_s, colors[s.statut]||'var(--muted)', ' OFs')
        ).join('');
      }
    }

    // OFs en retard
    if ($('anp-retards')) {
      $('anp-retards').innerHTML = !d.retards?.length
        ? `<tr><td colspan="5" class="empty" style="color:var(--green)">✓ Aucun OF en retard</td></tr>`
        : d.retards.map(r=>`<tr>
            <td><span class="of-num">${r.numero}</span></td>
            <td>${r.produit_nom}</td>
            <td style="color:var(--muted)">${r.client_nom||'—'}</td>
            <td><span class="badge b-inprogress">${r.statut}</span></td>
            <td><span style="font-family:'Bebas Neue',sans-serif;font-size:18px;color:var(--red)">+${r.jours_retard}j</span></td>
          </tr>`).join('');
    }

    // Ateliers
    if ($('anp-ateliers')) {
      const ateliers = d.ateliers||[];
      if (!ateliers.length) {
        $('anp-ateliers').innerHTML = '<div class="empty">Aucune donnée</div>';
      } else {
        const maxA = Math.max(...ateliers.map(a=>parseInt(a.n||0)),1);
        $('anp-ateliers').innerHTML = ateliers.map(a=>
          anBarRow(a.atelier, parseInt(a.n||0), maxA, 'var(--blue)', ' OFs')
        ).join('');
      }
    }

  } catch(e) { toast('Erreur analytics production: '+e.message,'err'); }
}

// ══════════════════════════════════════════════════════════
// B — ANALYTIQUE ACHATS & STOCK
// ══════════════════════════════════════════════════════════
async function loadAnalyticsAchats() {
  if ($('ana-kpis')) $('ana-kpis').innerHTML = '<div class="loading"><div class="spin"></div>CHARGEMENT...</div>';
  try {
    const d = await api('/api/analytics/achats');
    if (!d) return;

    const alertes = (d.stock||[]).filter(m=>parseFloat(m.pct||0)<=100).length;
    const bas     = (d.stock||[]).filter(m=>parseFloat(m.pct||0)>100&&parseFloat(m.pct||0)<150).length;
    const valeur  = parseFloat(d.valeur_totale_stock||0);
    const brs_att = d.brs_attente?.length||0;
    const da_pend = (d.da_statuts||[]).find(s=>s.statut==='PENDING')?.n||0;

    $('ana-kpis').innerHTML =
      anKpiCard('Alertes stock',   alertes,           'Sous minimum',        alertes>0?'':'g') +
      anKpiCard('Stock bas',       bas,               '< 150% du minimum',   bas>0?'a':'g') +
      anKpiCard('Valeur stock',    Math.round(valeur)+' DT', 'Inventaire total', 'b') +
      anKpiCard('DAs en attente',  da_pend,           'À approuver',         da_pend>0?'a':'g') +
      anKpiCard('BRs en attente',  brs_att,           'Réceptions pending',  brs_att>0?'a':'g');

    if ($('ana-valeur')) $('ana-valeur').textContent = `Valeur totale: ${valeur.toFixed(2)} DT`;

    // Stock
    if ($('ana-stock')) {
      const items = (d.stock||[]).slice(0,14);
      if (!items.length) {
        $('ana-stock').innerHTML = '<div class="empty">Aucun matériau</div>';
      } else {
        $('ana-stock').innerHTML = items.map(m=>{
          const pct = parseFloat(m.pct||0);
          const color = pct<=100?'var(--red)':pct<150?'var(--accent)':'var(--green)';
          const badge = pct<=100
            ? '<span class="badge b-urgent">ALERTE</span>'
            : pct<150 ? '<span class="badge b-high">BAS</span>' : '';
          return `<div class="mat-item">
            <div style="flex:1;min-width:0">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
                <span class="mat-name">${m.nom}</span>
                <div style="display:flex;align-items:center;gap:6px">${badge}
                  <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:${color};font-weight:600">${pct}%</span>
                </div>
              </div>
              <div style="display:flex;align-items:center;gap:.5rem">
                <div class="bar-w"><div class="bar-f ${pct<=100?'d':pct<150?'w':'ok'}" style="width:${Math.min(pct/2,100)}%"></div></div>
                <span class="mat-ref">${m.stock_actuel} / ${m.stock_minimum} ${m.unite}</span>
              </div>
            </div>
          </div>`;
        }).join('');
      }
    }

    // DA statuts flux
    if ($('ana-da-statuts')) {
      const das = d.da_statuts||[];
      const total = das.reduce((s,x)=>s+parseInt(x.n||0),0)||1;
      const lbls  = {PENDING:'En attente',APPROVED:'Approuvée',REJECTED:'Rejetée',ORDERED:'Commandée',RECEIVED:'Reçue'};
      const colors= {PENDING:'var(--accent)',APPROVED:'var(--green)',REJECTED:'var(--red)',ORDERED:'var(--blue)',RECEIVED:'var(--green)'};
      $('ana-da-statuts').innerHTML = das.length
        ? das.map(s=>anBarRow(lbls[s.statut]||s.statut, parseInt(s.n||0), total, colors[s.statut]||'var(--muted)')).join('')
        : '<div class="empty">Aucune demande</div>';
    }

    // Fournisseurs
    if ($('ana-fournisseurs')) {
      const fourns = d.top_fournisseurs||[];
      if (!fourns.length) {
        $('ana-fournisseurs').innerHTML = '<div class="empty">Aucune donnée</div>';
      } else {
        const maxF = Math.max(...fourns.map(f=>parseFloat(f.montant_total||0)),1);
        $('ana-fournisseurs').innerHTML = fourns.map(f=>
          anBarRow(f.fournisseur||'—', Math.round(parseFloat(f.montant_total||0)), maxF, 'var(--blue)', ' DT')
        ).join('');
      }
    }

    // Mouvements
    if ($('ana-mouvements')) {
      $('ana-mouvements').innerHTML = !d.mouvements?.length
        ? `<tr><td colspan="7" class="empty">Aucun mouvement</td></tr>`
        : d.mouvements.map(mv=>`<tr>
            <td>${typeBadge(mv.type)}</td>
            <td>${mv.materiau_nom}</td>
            <td style="font-family:'IBM Plex Mono',monospace">${mv.quantite} ${mv.unite}</td>
            <td style="font-family:'IBM Plex Mono',monospace;color:var(--muted)">${mv.stock_avant}</td>
            <td style="font-family:'IBM Plex Mono',monospace">${mv.stock_apres}</td>
            <td style="color:var(--muted);max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${mv.motif||'—'}</td>
            <td style="font-family:'IBM Plex Mono',monospace;color:var(--muted)">${String(mv.created_at||'').slice(0,10)}</td>
          </tr>`).join('');
    }

  } catch(e) { toast('Erreur analytics achats: '+e.message,'err'); }
}

// ══════════════════════════════════════════════════════════
// C — ANALYTIQUE OPÉRATEURS
// ══════════════════════════════════════════════════════════
async function loadAnalyticsOperateurs() {
  if ($('ano-kpis')) $('ano-kpis').innerHTML = '<div class="loading"><div class="spin"></div>CHARGEMENT...</div>';
  try {
    const d = await api('/api/analytics/operateurs');
    if (!d) return;

    const total_ops  = d.performance?.reduce((s,o)=>s+parseInt(o.ops_terminees||0),0)||0;
    const chefs      = d.performance?.filter(o=>o.role==='CHEF_ATELIER').length||0;
    const duree_tot  = d.performance?.reduce((s,o)=>s+parseInt(o.duree_totale_min||0),0)||0;
    const heures     = Math.round(duree_tot/60);

    $('ano-kpis').innerHTML =
      anKpiCard('Opérateurs actifs',    d.performance?.length||0, 'En équipe',              'b') +
      anKpiCard('Chefs atelier',        chefs,                    'Avec rôle défini',        'a') +
      anKpiCard('Opérations terminées', total_ops,                'Total cumulé',            'g') +
      anKpiCard('Heures enregistrées',  heures+'h',               'Temps réel saisi (⏱)',    '') +
      anKpiCard('Spécialités',          d.specialites?.length||0, 'Métiers dans l\'équipe',  '');

    // Performance table
    if ($('ano-perf')) {
      const roleLabels = {CHEF_ATELIER:'Chef Atelier',RESPONSABLE:'Responsable',TECHNICIEN:'Technicien',OPERATEUR:'Opérateur'};
      const roleCls    = {CHEF_ATELIER:'b-approved',RESPONSABLE:'b-high',TECHNICIEN:'b-normal',OPERATEUR:'b-draft'};
      $('ano-perf').innerHTML = !d.performance?.length
        ? `<tr><td colspan="7" class="empty">Aucun opérateur</td></tr>`
        : d.performance.map(o=>{
          const dur = parseInt(o.duree_totale_min||0);
          const durStr = dur>0?(dur>=60?Math.floor(dur/60)+'h'+String(dur%60).padStart(2,'0'):dur+'min'):'—';
          const taux = o.type_taux==='PIECE'?`${o.taux_piece} DT/pcs`
                     : o.type_taux==='BOTH' ?`${o.taux_horaire}+${o.taux_piece}`
                     : `${o.taux_horaire} DT/h`;
          const init = (o.prenom[0]||'')+(o.nom[0]||'');
          return `<tr>
            <td><div class="op-item" style="padding:0;border:none">
              <div class="op-av">${init}</div>
              <div><div style="font-size:12px;font-weight:500">${o.prenom} ${o.nom}</div></div>
            </div></td>
            <td><span class="badge ${roleCls[o.role]||'b-draft'}">${roleLabels[o.role]||'Opérateur'}</span></td>
            <td><span class="badge b-draft">${o.specialite||'—'}</span></td>
            <td><span style="font-family:'Bebas Neue',sans-serif;font-size:22px;color:var(--green)">${o.ops_terminees}</span></td>
            <td style="font-family:'IBM Plex Mono',monospace;color:var(--muted)">${durStr}</td>
            <td style="font-family:'IBM Plex Mono',monospace">${o.ofs_impliques}</td>
            <td style="font-family:'IBM Plex Mono',monospace;color:var(--accent)">${taux}</td>
          </tr>`;
        }).join('');
    }

    // Spécialités
    if ($('ano-specialites')) {
      const specs = d.specialites||[];
      if (!specs.length) {
        $('ano-specialites').innerHTML = '<div class="empty">Aucune donnée</div>';
      } else {
        const maxS = Math.max(...specs.map(s=>parseInt(s.n||0)),1);
        $('ano-specialites').innerHTML = specs.map(s=>
          anBarRow(s.specialite||'—', parseInt(s.n||0), maxS, 'var(--blue)', ' op.')
        ).join('');
      }
    }

    // Coût MO par opération
    if ($('ano-cout-ops')) {
      const ops = d.cout_par_operation||[];
      if (!ops.length) {
        $('ano-cout-ops').innerHTML = `<div class="empty" style="padding:1.5rem">
          Aucune donnée — saisir les durées d'opérations avec le bouton <span style="color:var(--accent)">⏱</span> dans les OFs
        </div>`;
      } else {
        const maxC = Math.max(...ops.map(o=>parseFloat(o.cout_total||0)),1);
        $('ano-cout-ops').innerHTML = ops.map(o=>
          anBarRow(o.operation_nom, Math.round(parseFloat(o.cout_total||0)), maxC, 'var(--red)', ' DT')
        ).join('');
      }
    }

  } catch(e) { toast('Erreur analytics opérateurs: '+e.message,'err'); }
}

// ══════════════════════════════════════════════════════════
// D — ANALYTIQUE QUALITÉ
// ══════════════════════════════════════════════════════════
async function loadAnalyticsQualite() {
  if ($('anq-kpis')) $('anq-kpis').innerHTML = '<div class="loading"><div class="spin"></div>CHARGEMENT...</div>';
  try {
    const d = await api('/api/analytics/qualite');
    if (!d) return;

    const kpis    = d.kpis   ||{};
    const nc_kpis = d.nc_kpis||{};
    const taux    = parseFloat(kpis.taux_global||0);

    $('anq-kpis').innerHTML =
      anKpiCard('Taux conformité',  taux+'%',              'Global cumulé',    taux>=95?'g':taux>=85?'a':'') +
      anKpiCard('Total contrôles',  kpis.total_cq||0,      'CQs réalisés',     'b') +
      anKpiCard('NCs ouvertes',     nc_kpis.ouvertes||0,   'À traiter',        (nc_kpis.ouvertes||0)>0?'':'g') +
      anKpiCard('NCs critiques',    nc_kpis.critiques||0,  'Priorité urgente', (nc_kpis.critiques||0)>0?'':'g') +
      anKpiCard('Pièces rebutées',  kpis.total_rebut||0,   'Total cumulé',     (kpis.total_rebut||0)>0?'a':'g');

    // Chart taux conformité par mois
    if ($('anq-chart')) {
      const data = d.par_mois||[];
      if (!data.length) {
        $('anq-chart').innerHTML = '<div class="empty">Aucun contrôle enregistré</div>';
      } else {
        $('anq-chart').innerHTML = data.map((m,i,arr)=>{
          const isCur = i===arr.length-1;
          const t = parseFloat(m.taux||0);
          const color = t>=95?'var(--green)':t>=85?'var(--accent)':'var(--red)';
          return anChartBar((m.mois_label||'').slice(0,4), t, 100, isCur, color, `${m.mois_label}: ${t}% conformité`);
        }).join('');
      }
    }

    // Types défauts
    if ($('anq-defauts')) {
      const defauts = d.defauts||[];
      if (!defauts.length) {
        $('anq-defauts').innerHTML = '<div class="empty">Aucune non-conformité</div>';
      } else {
        const maxD = Math.max(...defauts.map(x=>parseInt(x.n||0)),1);
        $('anq-defauts').innerHTML = defauts.map(x=>
          anBarRow(x.type_defaut||'—', parseInt(x.n||0), maxD, 'var(--red)', ' cas')
        ).join('');
      }
    }

    // NCs ouvertes
    if ($('anq-nc')) {
      $('anq-nc').innerHTML = !d.nc_ouvertes?.length
        ? `<tr><td colspan="8" class="empty" style="color:var(--green)">✓ Aucune non-conformité ouverte</td></tr>`
        : d.nc_ouvertes.map(nc=>`<tr>
            <td><span class="of-num">${nc.nc_numero}</span></td>
            <td style="color:var(--muted)">${nc.of_numero||'—'}</td>
            <td>${nc.produit_nom||'—'}</td>
            <td>${nc.type_defaut||'—'}</td>
            <td>${gravBadge(nc.gravite)}</td>
            <td style="color:var(--muted)">${nc.resp_prenom?nc.resp_prenom+' '+nc.resp_nom:'—'}</td>
            <td><span style="font-family:'Bebas Neue',sans-serif;font-size:18px;color:${parseInt(nc.age_jours||0)>7?'var(--red)':'var(--muted)'}">${nc.age_jours}j</span></td>
            <td style="color:var(--muted);max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${nc.action_corrective||'—'}</td>
          </tr>`).join('');
    }

  } catch(e) { toast('Erreur analytics qualité: '+e.message,'err'); }
}

// ══════════════════════════════════════════════════════════
// PAGE LOADERS
// ══════════════════════════════════════════════════════════
window.pageLoaders = window.pageLoaders || {};
window.pageLoaders['analytics-production'] = loadAnalyticsProduction;
window.pageLoaders['analytics-achats']     = loadAnalyticsAchats;
window.pageLoaders['analytics-operateurs'] = loadAnalyticsOperateurs;
window.pageLoaders['analytics-qualite']    = loadAnalyticsQualite;