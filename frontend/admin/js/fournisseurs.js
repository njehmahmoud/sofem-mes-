// ── fournisseurs.js ─────────────────────────────────────────
async function loadFournisseurs(){
  const fournisseurs=await api('/api/fournisseurs');
  if(!fournisseurs) return;

  const sMap={ACTIF:'b-completed',INACTIF:'b-draft',BLACKLISTE:'b-urgent'};
  $('fournisseurs-table').innerHTML=`
    <table><thead><tr><th>Code</th><th>Nom</th><th>Contact</th><th>Téléphone</th><th>Email</th><th>Ville</th><th>Matricule Fiscal</th><th>Statut</th><th></th></tr></thead>
    <tbody>${fournisseurs.map(f=>`<tr>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${f.code}</td>
      <td><strong>${f.nom}</strong></td>
      <td style="font-size:11px">${f.contact||'—'}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${f.telephone||'—'}</td>
      <td style="font-size:11px">${f.email||'—'}</td>
      <td style="font-size:11px">${f.ville||'—'}, ${f.pays||''}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${f.matricule_fiscal||'—'}</td>
      <td><span class="badge ${sMap[f.statut]||'b-draft'}">${f.statut}</span></td>
      <td><select class="fbtn" onchange="updateFournisseurStatut(${f.id},this.value)">
        <option value="">Statut</option><option value="ACTIF">Actif</option>
        <option value="INACTIF">Inactif</option><option value="BLACKLISTE">Blacklisté</option>
      </select></td>
    </tr>`).join('')}</tbody></table>
  `;
}

async function saveFournisseur(){
  const data={
    nom:$('f-nom').value.trim(), code:$('f-code').value.trim()||null,
    contact:$('f-contact').value.trim()||null, telephone:$('f-tel').value.trim()||null,
    email:$('f-email').value.trim()||null, ville:$('f-ville').value.trim()||null,
    pays:$('f-pays').value.trim()||'Tunisie', matricule_fiscal:$('f-mf').value.trim()||null,
    adresse:$('f-adresse').value.trim()||null
  };
  if(!data.nom){alert('Nom obligatoire');return;}
  const r=await api('/api/fournisseurs','POST',data);
  if(r){closeModal('modal-fournisseur');loadFournisseurs();}
}

async function updateFournisseurStatut(id,statut){
  if(!statut)return;
  await api(`/api/fournisseurs/${id}`,'PUT',{statut});
  loadFournisseurs();
}
