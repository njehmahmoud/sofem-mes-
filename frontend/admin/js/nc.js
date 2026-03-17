// ── nc.js ─────────────────────────────────────────
async function loadNC(){
  const [ncs, ofs, ops] = await Promise.all([
    api('/api/qualite/nc'),
    api('/api/of'),
    api('/api/operateurs')
  ]);
  if(!ncs) return;

  if(ofs) $('nc-of').innerHTML='<option value="">— Aucun —</option>'+ofs.map(o=>`<option value="${o.id}">${o.of_numero}</option>`).join('');
  if(ops){ $('nc-resp').innerHTML='<option value="">— Aucun —</option>'+ops.map(o=>`<option value="${o.id}">${o.prenom} ${o.nom}</option>`).join(''); }

  const gMap={MINEURE:'b-low',MAJEURE:'b-high',CRITIQUE:'b-urgent'};
  const sMap={OUVERTE:'b-inprogress',EN_COURS:'b-draft',CLOTUREE:'b-completed'};
  $('nc-table').innerHTML=`
    <table><thead><tr><th>N°</th><th>OF</th><th>Défaut</th><th>Gravité</th><th>Action Corrective</th><th>Responsable</th><th>Statut</th><th></th></tr></thead>
    <tbody>${ncs.map(n=>`<tr>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${n.nc_numero}</td>
      <td style="font-size:11px">${n.of_numero||'—'}</td>
      <td>${n.type_defaut}</td>
      <td><span class="badge ${gMap[n.gravite]||'b-normal'}">${n.gravite}</span></td>
      <td style="font-size:11px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${n.action_corrective||'—'}</td>
      <td style="font-size:11px">${n.responsable_prenom?n.responsable_prenom+' '+n.responsable_nom:'—'}</td>
      <td><span class="badge ${sMap[n.statut]||'b-draft'}">${n.statut}</span></td>
      <td><select class="fbtn" onchange="updateNCStatus(${n.id},this.value)">
        <option value="">Changer</option><option value="OUVERTE">Ouverte</option>
        <option value="EN_COURS">En Cours</option><option value="CLOTUREE">Clôturée</option>
      </select></td>
    </tr>`).join('')}</tbody></table>
  `;
}

async function saveNC(){
  const data={
    of_id:$('nc-of').value?parseInt($('nc-of').value):null,
    type_defaut:$('nc-defaut').value.trim(),
    description:$('nc-desc').value||null,
    gravite:$('nc-gravite').value,
    action_corrective:$('nc-action').value||null,
    responsable_id:$('nc-resp').value?parseInt($('nc-resp').value):null
  };
  if(!data.type_defaut){alert('Type de défaut obligatoire');return;}
  const r=await api('/api/qualite/nc','POST',data);
  if(r){closeModal('modal-nc');loadNC();}
}

async function updateNCStatus(id,statut){
  if(!statut)return;
  const data={statut};
  if(statut==='CLOTUREE') data.date_cloture=new Date().toISOString().split('T')[0];
  await api(`/api/qualite/nc/${id}`,'PUT',data);
  loadNC();
}
