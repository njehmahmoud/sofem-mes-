// ── maintenance.js ─────────────────────────────────────────
async function loadMaintenance(){
  const [oms, stats, machines, ops] = await Promise.all([
    api('/api/maintenance'),
    api('/api/maintenance/stats/overview'),
    api('/api/machines'),
    api('/api/operateurs')
  ]);
  if(!oms||!stats) return;

  $('maintenance-kpis').innerHTML=`
    <div class="kpi-card"><div class="kpi-lbl">Total OMs</div><div class="kpi-val">${stats.total}</div></div>
    <div class="kpi-card"><div class="kpi-lbl">En Cours</div><div class="kpi-val" style="color:var(--accent)">${stats.en_cours}</div></div>
    <div class="kpi-card"><div class="kpi-lbl">Planifiés</div><div class="kpi-val">${stats.planifies}</div></div>
    <div class="kpi-card"><div class="kpi-lbl">Urgences</div><div class="kpi-val" style="color:var(--red)">${stats.urgences}</div></div>
    <div class="kpi-card"><div class="kpi-lbl">Coût Total (TND)</div><div class="kpi-val">${Number(stats.cout_total).toFixed(3)}</div></div>
  `;

  // Populate modal selects
  // Populate machine dropdown
  const omMach = $('om-machine');
  if (omMach && machines) omMach.innerHTML = '<option value="">— Sélectionner machine —</option>' +
    machines.map(m => `<option value="${m.id}">${m.nom} · ${m.atelier} (${m.statut==='OPERATIONNELLE'?'✓':'⚠'} ${m.statut.replace('_',' ')})</option>`).join('');
  // Populate technicien from operateurs
  const omTech = $('om-tech');
  if (omTech && ops) omTech.innerHTML = '<option value="">— Aucun —</option>' +
    ops.map(o => `<option value="${o.id}">${o.prenom} ${o.nom}${o.specialite?' · '+o.specialite:''}</option>`).join('');

  const pMap={BASSE:'b-low',NORMAL:'b-normal',HAUTE:'b-high',URGENT:'b-urgent'};
  const sMap={PLANIFIE:'b-draft',EN_COURS:'b-inprogress',TERMINE:'b-completed',ANNULE:'b-cancelled'};
  const tMap={PREVENTIVE:'🛡️',CORRECTIVE:'🔨',URGENCE:'🚨'};
  $('maintenance-table').innerHTML=`
    <table><thead><tr><th>N°</th><th>Type</th><th>Titre</th><th>Machine</th><th>Technicien</th><th>Date</th><th>Priorité</th><th>Statut</th><th>Actions</th></tr></thead>
    <tbody>${oms.map(o=>`<tr>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${o.om_numero}</td>
      <td>${tMap[o.type_maintenance]||''} <span style="font-size:10px">${o.type_maintenance}</span></td>
      <td>${o.titre}</td>
      <td style="font-size:11px">${o.machine_nom||'—'}</td>
      <td style="font-size:11px">${o.technicien_prenom?o.technicien_prenom+' '+o.technicien_nom:'—'}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${o.date_planifiee||'—'}</td>
      <td><span class="badge ${pMap[o.priorite]||'b-normal'}">${o.priorite}</span></td>
      <td><span class="badge ${sMap[o.statut]||'b-draft'}">${o.statut.replace('_',' ')}</span></td>
      <td style="display:flex;gap:4px;align-items:center">
    <select class="fbtn" onchange="updateOMStatus(${o.id},this.value)">
      <option value="">Changer statut</option>
      <option value="PLANIFIE">Planifié</option>
      <option value="EN_COURS">En Cours</option>
      <option value="TERMINE">Terminé</option>
    </select>
    ${o.statut !== 'TERMINE' && o.statut !== 'ANNULE'
      ? `<button class="fbtn" style="color:var(--accent)"
           onclick="cancelMaintenance(${o.id},'${o.om_numero}','${(o.titre||'').replace(/'/g,"\\'")}','${o.statut}')"
           title="Annuler">✕</button>`
      : ''}
  </td>
      </select></td>
    </tr>`).join('')}</tbody></table>
  `;
}

async function saveMaintenance(){
  const data={
    machine_id:parseInt($('om-machine').value),
    type_maintenance:$('om-type').value,
    titre:$('om-titre').value.trim(),
    description:$('om-desc').value||null,
    priorite:$('om-priorite').value,
    technicien_id:$('om-tech').value?parseInt($('om-tech').value):null,
    date_planifiee:$('om-date').value||null,
    duree_estimee:parseInt($('om-duree').value)||0
  };
  if(!data.titre){alert('Titre obligatoire');return;}
  const r=await api('/api/maintenance','POST',data);
  if(r){closeModal('modal-maintenance');loadMaintenance();}
}

async function updateOMStatus(id,statut){
  if(!statut)return;
  await api(`/api/maintenance/${id}`,'PUT',{statut});
  loadMaintenance();
}