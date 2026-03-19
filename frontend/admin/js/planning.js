// ── planning.js ─────────────────────────────────────────
async function loadPlanning(){
  const [rows, ofs, machines, ops] = await Promise.all([
    api('/api/planning'),
    api('/api/of'),
    api('/api/machines'),
    api('/api/operateurs')
  ]);
  if(!rows) return;

  // Populate modal selects
  // OF dropdown — active OFs only (DRAFT, APPROVED, IN_PROGRESS)
  if (ofs && $('pl-of')) {
    const active = (ofs||[]).filter(o => !['COMPLETED','CANCELLED'].includes(o.statut));
    $('pl-of').innerHTML = '<option value="">— Sélectionner un OF —</option>' +
      active.map(o => `<option value="${o.id}">${o.numero} · ${o.produit_nom} (${o.statut.replace('_',' ')})</option>`).join('');
  }
  if (machines && $('pl-machine')) $('pl-machine').innerHTML = '<option value="">— Aucune —</option>' +
    machines.filter(m=>m.statut==='OPERATIONNELLE').map(m=>`<option value="${m.id}">${m.nom} · ${m.atelier}</option>`).join('');
  if (ops && $('pl-op')) $('pl-op').innerHTML = '<option value="">— Aucun —</option>' +
    ops.map(o=>`<option value="${o.id}">${o.prenom} ${o.nom}${o.specialite?' ('+o.specialite+')':''}</option>`).join('');

  // Simple Gantt-style visual
  const ganttHTML = rows.length === 0 ? '<div style="color:var(--muted);font-size:12px;padding:1rem">Aucun créneau planifié.</div>' : (() => {
    const dates = rows.flatMap(r=>[new Date(r.date_debut),new Date(r.date_fin)]);
    const minD = new Date(Math.min(...dates)), maxD = new Date(Math.max(...dates));
    const totalMs = maxD-minD || 1;
    const colors=['#D42B2B','#3B82F6','#22C55E','#F59E0B','#8B5CF6','#EC4899'];
    return `<div style="font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:1px;color:var(--muted);text-transform:uppercase;margin-bottom:.75rem">Gantt — Planning Production</div>
    <div style="position:relative;min-height:${rows.length*36+20}px">
      ${rows.map((r,i)=>{
        const left=((new Date(r.date_debut)-minD)/totalMs*100).toFixed(1);
        const width=Math.max(((new Date(r.date_fin)-new Date(r.date_debut))/totalMs*100).toFixed(1),1);
        const color=colors[i%colors.length];
        return `<div style="position:absolute;top:${i*36}px;left:0;right:0;height:28px">
          <div style="position:absolute;left:${left}%;width:${width}%;height:100%;background:${color}22;border:1px solid ${color};border-radius:4px;display:flex;align-items:center;padding:0 6px;overflow:hidden;cursor:default" title="${r.of_numero} | ${r.machine_nom||''} | ${r.date_debut} → ${r.date_fin}">
            <span style="font-size:10px;color:${color};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${r.of_numero}${r.machine_nom?' · '+r.machine_nom:''}</span>
          </div>
        </div>`;
      }).join('')}
    </div>`;
  })();
  $('planning-gantt').innerHTML=`<div style="padding:1rem">${ganttHTML}</div>`;

  const sMap={PLANIFIE:'b-draft',EN_COURS:'b-inprogress',TERMINE:'b-completed',ANNULE:'b-cancelled'};
  $('planning-table').innerHTML=`
    <table><thead><tr><th>OF</th><th>Produit</th><th>Machine</th><th>Opérateur</th><th>Début</th><th>Fin</th><th>Statut</th><th></th></tr></thead>
    <tbody>${rows.map(r=>`<tr>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${r.of_numero}</td>
      <td style="font-size:11px">${r.produit_nom||'—'}</td>
      <td style="font-size:11px">${r.machine_nom||'—'}</td>
      <td style="font-size:11px">${r.operateur_prenom?r.operateur_prenom+' '+r.operateur_nom:'—'}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${r.date_debut?.replace('T',' ').slice(0,16)||'—'}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${r.date_fin?.replace('T',' ').slice(0,16)||'—'}</td>
      <td><span class="badge ${sMap[r.statut]||'b-draft'}">${r.statut}</span></td>
      <td><button class="fbtn" style="color:var(--red)" onclick="deletePlanning(${r.id})">✕</button></td>
    </tr>`).join('')}</tbody></table>
  `;
}

async function savePlanning(){
  const data={
    of_id:parseInt($('pl-of').value),
    machine_id:$('pl-machine').value?parseInt($('pl-machine').value):null,
    operateur_id:$('pl-op').value?parseInt($('pl-op').value):null,
    date_debut:$('pl-debut').value.replace('T',' '),
    date_fin:$('pl-fin').value.replace('T',' '),
    notes:$('pl-notes').value||null
  };
  if(!data.date_debut||!data.date_fin){alert('Dates obligatoires');return;}
  const r=await api('/api/planning','POST',data);
  if(r){closeModal('modal-planning');loadPlanning();}
}

async function deletePlanning(id){
  if(!confirm('Supprimer ce créneau ?'))return;
  await api(`/api/planning/${id}`,'DELETE');
  loadPlanning();
}