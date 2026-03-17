// ── reports.js ─────────────────────────────────────────
async function loadReports(){
  try{
    const [mois,ops,stock]=await Promise.all([api('/api/rapports/production-mensuelle'),api('/api/rapports/operateurs'),api('/api/rapports/stock-alertes')]);
    const mx=Math.max(...mois.map(m=>m.total),1);
    $('rep-chart').innerHTML=mois.slice(-8).map((m,i,arr)=>`<div class="bc"><div style="position:relative;width:100%;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;flex:1"><span style="font-family:'IBM Plex Mono',monospace;font-size:7px;color:var(--text);margin-bottom:2px">${m.total}</span><div class="bf${i===arr.length-1?' cur':''}" style="width:100%;height:${Math.round(m.total/mx*80)}%"></div></div><div class="bl">${(m.mois||'').slice(5)}</div></div>`).join('');
    $('rep-stock').innerHTML=stock.length===0?'<div class="empty">✓ Tous les stocks OK</div>':stock.map(m=>{const pct=Math.min(100,Math.round(m.pct||0));return`<div class="mat-item"><div style="flex:1"><div class="mat-name">${m.nom}</div><div class="mat-ref">${m.stock_actuel}/${m.stock_minimum} ${m.unite}</div></div><div class="bar-w"><div class="bar-f d" style="width:${pct}%"></div></div><div class="bar-pct d">${pct}%</div></div>`;}).join('');
    $('rep-ops').innerHTML=ops.map(op=>{const init=op.operateur.split(' ').map(n=>n[0]||'').join('');return`<div class="op-item"><div class="op-av">${init}</div><div style="flex:1"><div style="font-size:12px;font-weight:500">${op.operateur}</div><div style="font-size:9px;font-family:'IBM Plex Mono',monospace;color:var(--muted)">${op.specialite} · ${op.total_ofs||0} OFs · ${op.etapes_completes||0} étapes · moy. ${op.duree_moy_min||'—'} min</div></div></div>`;}).join('');
  }catch(e){toast('Erreur: '+e.message,'err');}
}
