// ── materials.js ─────────────────────────────────────────
async function loadMaterials(){
  try{
    const [mats,mvts]=await Promise.all([api('/api/materiaux'),api('/api/materiaux/mouvements?limit=20')]);
    $('mats-tb').innerHTML=mats.map(m=>{const pct=Math.min(100,Math.round(m.pct_stock||0));const cls=pct<50?'d':pct<90?'w':'ok';return`<tr><td><span class="of-num">${m.code}</span></td><td>${m.nom}</td><td style="font-family:'IBM Plex Mono',monospace">${m.stock_actuel}</td><td style="font-family:'IBM Plex Mono',monospace;color:var(--muted)">${m.stock_minimum}</td><td style="color:var(--muted)">${m.unite}</td><td style="font-size:10px;color:var(--muted)">${m.fournisseur||'—'}</td><td>${m.alerte?'<span class="badge b-urgent">ALERTE</span>':'<span class="badge b-completed">OK</span>'}</td><td style="min-width:80px"><div class="bar-w"><div class="bar-f ${cls}" style="width:${pct}%"></div></div></td></tr>`;}).join('');
    $('mvt-tb').innerHTML=mvts.length===0?empty(8,'Aucun mouvement'):mvts.map(m=>{const col=m.type==='ENTREE'?'var(--green)':m.type==='SORTIE'?'var(--red)':'var(--accent)';return`<tr><td style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--muted)">${(m.created_at||'').slice(0,16)}</td><td>${m.materiau_nom}</td><td><span style="color:${col};font-family:'IBM Plex Mono',monospace;font-size:9px">${m.type}</span></td><td style="font-family:'IBM Plex Mono',monospace">${m.quantite}</td><td style="color:var(--muted);font-family:'IBM Plex Mono',monospace">${m.stock_avant||'—'}</td><td style="font-family:'IBM Plex Mono',monospace">${m.stock_apres||'—'}</td><td><span class="of-num">${m.of_numero||'—'}</span></td><td style="font-size:10px;color:var(--muted)">${m.motif||'—'}</td></tr>`;}).join('');
    $('mv-mat').innerHTML=mats.map(m=>`<option value="${m.id}">${m.nom} (${m.stock_actuel} ${m.unite})</option>`).join('');
  }catch(e){toast('Erreur: '+e.message,'err');}
}

async function saveMouvement(){
  try{const res=await api('/api/materiaux/mouvement',{method:'POST',body:JSON.stringify({materiau_id:parseInt($('mv-mat').value),type:$('mv-type').value,quantite:parseFloat($('mv-qte').value),motif:$('mv-motif').value||null})});toast(`Stock mis à jour ✓`);closeModal('m-mv');loadMaterials();}
  catch(e){toast(e.message,'err');}
}

async function saveMateriau(){
  if(!$('mat-code').value||!$('mat-nom').value){toast('Champs obligatoires manquants','err');return;}
  try{await api('/api/materiaux',{method:'POST',body:JSON.stringify({code:$('mat-code').value,nom:$('mat-nom').value,unite:$('mat-unite').value,stock_actuel:parseFloat($('mat-stock').value)||0,stock_minimum:parseFloat($('mat-min').value)||0,fournisseur:$('mat-four').value||null})});toast('Matériau créé ✓');closeModal('m-mat');loadMaterials();}
  catch(e){toast(e.message,'err');}
}
