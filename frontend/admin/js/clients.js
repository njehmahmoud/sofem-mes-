// ── clients.js ───────────────────────────────────────────
async function loadClients() {
  try {
    const clients = await api('/api/clients') || [];
    $('clients-tb').innerHTML = clients.length === 0 ? empty(7) : clients.map(c => `<tr>
      <td><span class="of-num">${c.code}</span></td>
      <td><strong>${c.nom}</strong></td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${c.matricule_fiscal||'—'}</td>
      <td style="font-size:11px">${c.telephone||'—'}</td>
      <td style="font-size:11px">${c.email||'—'}</td>
      <td style="font-size:11px">${[c.ville,c.adresse].filter(Boolean).join(' — ')||'—'}</td>
      <td><button class="fbtn" onclick="editClient(${c.id},'${c.nom.replace(/'/g,"\\'")}','${c.matricule_fiscal||''}','${c.telephone||''}','${c.email||''}','${c.ville||''}')">✎</button>
          <button class="fbtn" style="color:var(--red)" onclick="deleteClient(${c.id})">✕</button></td>
    </tr>`).join('');
  } catch(e) { toast('Erreur clients: ' + e.message, 'err'); }
}

async function saveClient() {
  const id   = $('client-edit-id').value;
  const data = {
    nom:              $('client-nom').value.trim(),
    matricule_fiscal: $('client-mf').value.trim()  || null,
    telephone:        $('client-tel').value.trim()  || null,
    email:            $('client-email').value.trim()|| null,
    ville:            $('client-ville').value.trim()|| null,
    adresse:          $('client-adresse').value.trim()|| null,
    notes:            $('client-notes').value.trim()|| null,
  };
  if (!data.nom) { toast('Nom obligatoire', 'err'); return; }
  try {
    if (id) {
      await api(`/api/clients/${id}`, 'PUT', data);
      toast('Client mis à jour ✓');
    } else {
      const res = await api('/api/clients', 'POST', data);
      toast(`${res.code} créé ✓`);
    }
    closeModal('m-client'); loadClients();
  } catch(e) { toast(e.message,'err'); }
}

function editClient(id, nom, mf, tel, email, ville) {
  $('client-edit-id').value = id;
  $('client-nom').value   = nom;
  $('client-mf').value    = mf;
  $('client-tel').value   = tel;
  $('client-email').value = email;
  $('client-ville').value = ville;
  openModal('m-client');
}

function newClient() {
  $('client-edit-id').value = '';
  ['client-nom','client-mf','client-tel','client-email','client-ville','client-adresse','client-notes']
    .forEach(id => $(id).value = '');
  openModal('m-client');
}

async function deleteClient(id) {
  if (!confirm('Supprimer ce client ?')) return;
  try { await api(`/api/clients/${id}`, 'DELETE'); toast('Client supprimé'); loadClients(); }
  catch(e) { toast(e.message,'err'); }
}
