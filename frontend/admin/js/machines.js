// ── machines.js ─────────────────────────────────────────
async function loadMachines(){
  const [machines, stats] = await Promise.all([
    api('/api/machines'),
    api('/api/machines/stats/overview')
  ]);
  if(!machines||!stats) return;

  $('machines-kpis').innerHTML=`
    <div class="kpi-card"><div class="kpi-lbl">Total Machines</div><div class="kpi-val">${stats.total}</div></div>
    <div class="kpi-card"><div class="kpi-lbl">Opérationnelles</div><div class="kpi-val" style="color:var(--green)">${(stats.by_status.find(s=>s.statut==='OPERATIONNELLE')||{c:0}).c}</div></div>
    <div class="kpi-card"><div class="kpi-lbl">En Maintenance</div><div class="kpi-val" style="color:var(--accent)">${(stats.by_status.find(s=>s.statut==='EN_MAINTENANCE')||{c:0}).c}</div></div>
    <div class="kpi-card"><div class="kpi-lbl">En Panne</div><div class="kpi-val" style="color:var(--red)">${(stats.by_status.find(s=>s.statut==='EN_PANNE')||{c:0}).c}</div></div>
  `;

  const stMap={OPERATIONNELLE:'b-completed',EN_MAINTENANCE:'b-inprogress',EN_PANNE:'b-urgent',ARRETEE:'b-draft'};
  const stLbl={OPERATIONNELLE:'Opérationnelle',EN_MAINTENANCE:'En Maintenance',EN_PANNE:'En Panne',ARRETEE:'Arrêtée'};
  $('machines-table').innerHTML=`
    <table><thead><tr><th>Code</th><th>Nom</th><th>Type</th><th>Atelier</th><th>Marque/Modèle</th><th>Statut</th><th>Actions</th></tr></thead>
    <tbody>${machines.map(m=>`<tr>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${m.code}</td>
      <td>${m.nom}</td>
      <td style="color:var(--muted);font-size:11px">${m.type||'—'}</td>
      <td style="color:var(--muted);font-size:11px">${m.atelier}</td>
      <td style="font-size:11px">${[m.marque,m.modele].filter(Boolean).join(' / ')||'—'}</td>
      <td><span class="badge ${stMap[m.statut]||'b-draft'}">${stLbl[m.statut]||m.statut}</span></td>
      <td><button class="fbtn" onclick="changeMachineStatus(${m.id},'${m.statut}')">Statut</button></td>
    </tr>`).join('')}</tbody></table>
  `;
}

async function saveMachine(){
  const data={
    nom:$('m-nom').value.trim(), code:$('m-code').value.trim()||null,
    type:$('m-type').value.trim()||null, atelier:$('m-atelier').value,
    marque:$('m-marque').value.trim()||null, modele:$('m-modele').value.trim()||null,
    numero_serie:$('m-serie').value.trim()||null,
    date_acquisition:$('m-date').value||null, notes:$('m-notes').value||null
  };
  if(!data.nom){alert('Nom obligatoire');return;}
  const r=await api('/api/machines','POST',data);
  if(r){closeModal('modal-machine');loadMachines();}
}

async function changeMachineStatus(id, current){
  const opts={OPERATIONNELLE:'Opérationnelle',EN_MAINTENANCE:'En Maintenance',EN_PANNE:'En Panne',ARRETEE:'Arrêtée'};
  const next = prompt(`Nouveau statut pour cette machine:\n${Object.entries(opts).map(([k,v])=>`${k}`).join('\n')}\nActuel: ${current}`);
  if(!next) return;
  await api(`/api/machines/${id}`,'PUT',{statut:next.trim()});
  loadMachines();
}
