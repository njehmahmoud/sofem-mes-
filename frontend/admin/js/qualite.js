// ── qualite.js ─────────────────────────────────────────
async function loadQualite(){
  const [cqs, stats, ofs, ops] = await Promise.all([
    api('/api/qualite/controles'),
    api('/api/qualite/stats'),
    api('/api/of'),
    api('/api/operateurs')
  ]);
  if(!cqs||!stats) return;

  $('qualite-kpis').innerHTML=`
    <div class="kpi-card"><div class="kpi-lbl">Total Contrôles</div><div class="kpi-val">${stats.total_controles}</div></div>
    <div class="kpi-card"><div class="kpi-lbl">Taux Conformité</div><div class="kpi-val" style="color:var(--green)">${stats.taux_conformite}%</div></div>
    <div class="kpi-card"><div class="kpi-lbl">NC Ouvertes</div><div class="kpi-val" style="color:var(--accent)">${stats.nc_ouvertes}</div></div>
    <div class="kpi-card"><div class="kpi-lbl">NC Critiques</div><div class="kpi-val" style="color:var(--red)">${stats.nc_critiques}</div></div>
  `;

  if(ofs) $('cq-of').innerHTML='<option value="">— Aucun —</option>'+ofs.map(o=>`<option value="${o.id}">${o.of_numero}</option>`).join('');
  if(ops){ $('cq-op').innerHTML='<option value="">— Aucun —</option>'+ops.map(o=>`<option value="${o.id}">${o.prenom} ${o.nom}</option>`).join(''); }
  const today=new Date().toISOString().split('T')[0]; $('cq-date').value=today;

  const sMap={CONFORME:'b-completed',NON_CONFORME:'b-urgent',EN_ATTENTE:'b-draft'};
  $('qualite-table').innerHTML=`
    <table><thead><tr><th>N°</th><th>OF</th><th>Produit</th><th>Type</th><th>Date</th><th>Contrôlé</th><th>Conforme</th><th>Rebut</th><th>Statut</th><th></th></tr></thead>
    <tbody>${cqs.map(c=>`<tr>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${c.cq_numero}</td>
      <td style="font-size:11px">${c.of_numero||'—'}</td>
      <td style="font-size:11px">${c.produit_nom||'—'}</td>
      <td style="font-size:10px;color:var(--muted)">${c.type_controle}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${c.date_controle}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${c.quantite_controlée||0}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--green)">${c.quantite_conforme||0}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--red)">${c.quantite_rebut||0}</td>
      <td><span class="badge ${sMap[c.statut]||'b-draft'}">${c.statut.replace('_',' ')}</span></td>
      <td><select class="fbtn" onchange="updateCQStatus(${c.id},this.value)">
        <option value="">Changer</option><option value="EN_ATTENTE">En Attente</option>
        <option value="CONFORME">Conforme</option><option value="NON_CONFORME">Non Conforme</option>
      </select></td>
    </tr>`).join('')}</tbody></table>
  `;
}

async function saveControle(){
  const data={
    of_id:$('cq-of').value?parseInt($('cq-of').value):null,
    type_controle:$('cq-type').value,
    operateur_id:$('cq-op').value?parseInt($('cq-op').value):null,
    date_controle:$('cq-date').value,
    statut:'EN_ATTENTE',
    quantite_controlee:parseFloat($('cq-total').value)||0,
    quantite_conforme:parseFloat($('cq-ok').value)||0,
    quantite_rebut:parseFloat($('cq-rebut').value)||0,
    notes:$('cq-notes').value||null
  };
  if(!data.date_controle){alert('Date obligatoire');return;}
  const r=await api('/api/qualite/controles','POST',data);
  if(r){closeModal('modal-qualite');loadQualite();}
}

async function updateCQStatus(id,statut){
  if(!statut)return;
  await api(`/api/qualite/controles/${id}`,'PUT',{statut});
  loadQualite();
}
