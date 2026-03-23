// ── operator_dashboard.js — SOFEM MES v6.0 ───────────────
// Simplified view for operators (mobile-friendly)

async function loadOperatorDashboard() {
  try {
    const user = getUserInfo();
    // Try to find linked operator
    const users = await api('/api/auth/users') || [];
    const me    = users.find(u => u.prenom === user.prenom && u.nom === user.nom);
    const opId  = me?.operateur_id;

    // Load all active OFs and my operations
    const [ofs, myPerf] = await Promise.all([
      api('/api/of?limit=100'),
      opId ? api(`/api/dashboard/operator/${opId}`) : Promise.resolve(null)
    ]);

    renderOperatorDashboard(user, ofs || [], myPerf, opId);
  } catch(e) { toast('Erreur: '+e.message,'err'); }
}

function renderOperatorDashboard(user, ofs, perf, opId) {
  const el = $('opd-container');
  if (!el) return;

  // Filter OFs that have operations for this operator (if linked)
  const myOFs = opId
    ? ofs.filter(of => of.operations?.some(op =>
        op.operateurs_ids?.includes(opId) && op.statut !== 'COMPLETED'
      ))
    : ofs.filter(of => of.statut === 'IN_PROGRESS');

  const urgent = myOFs.filter(o => o.priorite === 'URGENT').length;
  const initials = (user.prenom?.[0]||'') + (user.nom?.[0]||'');

  el.innerHTML = `
    <!-- Greeting -->
    <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem;
      background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:1.25rem">
      <div style="width:52px;height:52px;border-radius:50%;background:var(--red);
        display:flex;align-items:center;justify-content:center;
        font-family:'Bebas Neue',sans-serif;font-size:22px;color:#fff;flex-shrink:0">${initials}</div>
      <div>
        <div style="font-family:'Bebas Neue',sans-serif;font-size:22px;letter-spacing:2px">
          Bonjour, <span style="color:var(--red)">${user.prenom} ${user.nom}</span>
        </div>
        <div style="font-size:10px;color:var(--muted);font-family:'IBM Plex Mono',monospace">
          ${new Date().toLocaleDateString('fr-FR',{weekday:'long',day:'numeric',month:'long'})}
        </div>
      </div>
      ${urgent > 0 ? `<div style="margin-left:auto;background:var(--red-g);border:1px solid var(--red);
        border-radius:6px;padding:.5rem .75rem;text-align:center">
        <div style="font-family:'Bebas Neue',sans-serif;font-size:28px;color:var(--red);line-height:1">${urgent}</div>
        <div style="font-size:8px;color:var(--red);font-family:'IBM Plex Mono',monospace">URGENT</div>
      </div>` : ''}
    </div>

    <!-- My stats -->
    <div class="kpi-grid" style="grid-template-columns:repeat(3,1fr);margin-bottom:1.25rem">
      <div class="kpi"><div class="kpi-lbl">Mes tâches actives</div>
        <div class="kpi-val r">${myOFs.length}</div><div class="kpi-det">À traiter</div></div>
      <div class="kpi g"><div class="kpi-lbl">OFs terminés</div>
        <div class="kpi-val g">${perf?.ofs_termines||0}</div><div class="kpi-det">Total cumulé</div></div>
      <div class="kpi b"><div class="kpi-lbl">Performance</div>
        <div class="kpi-val b">${perf?.performance||0}%</div><div class="kpi-det">Taux complétion</div></div>
    </div>

    <!-- My OFs -->
    <div class="sec">
      <div class="sec-h">
        <div class="sec-title">MES <span class="ac">ORDRES EN COURS</span></div>
        <span style="font-size:9px;color:var(--muted);font-family:'IBM Plex Mono',monospace">
          ${myOFs.length} tâche${myOFs.length>1?'s':''}
        </span>
      </div>
      ${!myOFs.length
        ? `<div class="empty" style="padding:2rem">
            <div style="font-size:28px;margin-bottom:.5rem">✅</div>
            Aucune tâche active pour le moment
          </div>`
        : myOFs.map(of => {
            const ops  = (of.operations||[]).filter(op => op.statut !== 'COMPLETED');
            const done = (of.operations||[]).filter(op => op.statut === 'COMPLETED').length;
            const tot  = (of.operations||[]).length;
            const pct  = tot > 0 ? Math.round(done/tot*100) : 0;
            const col  = of.priorite==='URGENT'?'var(--red)':of.priorite==='HAUTE'?'var(--accent)':'var(--blue)';
            return `<div style="padding:1rem 1.25rem;border-bottom:1px solid var(--border)"
              onclick="openOFDetail(${of.id})" style="cursor:pointer">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem">
                <div>
                  <span class="of-num">${of.numero}</span>
                  <span style="font-size:11px;margin-left:.5rem">${of.produit_nom}</span>
                </div>
                <div style="display:flex;gap:.4rem;align-items:center">
                  ${pBadge(of.priorite)}
                  ${sBadge(of.statut)}
                </div>
              </div>
              <!-- Progress bar -->
              <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.4rem">
                <div style="flex:1;height:6px;background:var(--bg3);border-radius:3px;overflow:hidden">
                  <div style="width:${pct}%;height:100%;background:${col};border-radius:3px;transition:width .5s"></div>
                </div>
                <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted)">${done}/${tot}</span>
              </div>
              <!-- Next operations -->
              ${ops.slice(0,2).map(op => `
                <div style="display:flex;align-items:center;gap:.4rem;padding:3px 0">
                  <div class="sd ${op.statut==='IN_PROGRESS'?'in_progress':'pending'}"></div>
                  <span style="font-size:10px;color:var(--muted)">${op.operation_nom}</span>
                  ${op.operateurs_noms?`<span style="font-size:9px;color:var(--muted);margin-left:auto">${op.operateurs_noms}</span>`:''}
                </div>`).join('')}
            </div>`;
          }).join('')}
    </div>

    <!-- Quick actions -->
    <div class="sec" style="margin-top:1.25rem">
      <div class="sec-h"><div class="sec-title">ACCÈS <span class="ac">RAPIDES</span></div></div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;padding:1rem">
        ${[
          ['📋','Mes OFs','orders'],
          ['✅','Qualité','qualite'],
          ['📊','Analytique','analytics-production'],
          ['📅','Calendrier','calendar'],
          ['📡','Monitoring','monitor'],
          ['⚙️','Paramètres','settings'],
        ].map(([icon,lbl,page]) => `
          <button onclick="navigate('${page}')"
            style="background:var(--bg3);border:1px solid var(--border);border-radius:8px;
              padding:.75rem .5rem;cursor:pointer;text-align:center;transition:all .15s"
            onmouseover="this.style.borderColor='var(--red)'"
            onmouseout="this.style.borderColor='var(--border)'">
            <div style="font-size:20px;margin-bottom:4px">${icon}</div>
            <div style="font-size:9px;font-family:'IBM Plex Mono',monospace;
              color:var(--muted);text-transform:uppercase;letter-spacing:1px">${lbl}</div>
          </button>`).join('')}
      </div>
    </div>
  `;
}

window.pageLoaders = window.pageLoaders || {};
window.pageLoaders['operator-dashboard'] = loadOperatorDashboard;
