// ── operators.js ─────────────────────────────────────────
async function loadOperators() {
  try {
    const ops = await api('/api/operateurs') || [];
    $('operators-tb').innerHTML = ops.length === 0 ? empty(8) : ops.map(o => `<tr>
      <td><strong>${o.prenom} ${o.nom}</strong></td>
      <td><span class="badge b-draft">${o.specialite}</span></td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${o.telephone||'—'}</td>
      <td style="font-size:11px">${o.email||'—'}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${o.type_taux||'HORAIRE'}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">
        ${o.type_taux==='PIECE'?'—':o.taux_horaire+' TND/h'}
      </td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">
        ${o.type_taux==='HORAIRE'?'—':o.taux_piece+' TND/pcs'}
      </td>
      <td><button class="fbtn" onclick="openEditOperateur(${JSON.stringify(o).replace(/"/g,'&quot;')})">✎</button>
          <button class="fbtn" style="color:var(--red)" onclick="deleteOperateur(${o.id})">✕</button></td>
    </tr>`).join('');
  } catch(e) { toast('Erreur opérateurs: ' + e.message, 'err'); }
}

function openNewOperateur() {
  $('op-edit-id').value = '';
  ['op-prenom','op-nom','op-tel','op-email'].forEach(id => $(id).value='');
  $('op-spec').value = 'Ponçage';
  $('op-taux-type').value = 'HORAIRE';
  $('op-taux-h').value = '0'; $('op-taux-p').value = '0';
  onTauxTypeChange();
  openModal('m-op');
}

function openEditOperateur(o) {
  $('op-edit-id').value  = o.id;
  $('op-prenom').value   = o.prenom;
  $('op-nom').value      = o.nom;
  $('op-spec').value     = o.specialite;
  $('op-tel').value      = o.telephone||'';
  $('op-email').value    = o.email||'';
  $('op-taux-type').value = o.type_taux||'HORAIRE';
  $('op-taux-h').value   = o.taux_horaire||0;
  $('op-taux-p').value   = o.taux_piece||0;
  onTauxTypeChange();
  openModal('m-op');
}

function onTauxTypeChange() {
  const t = $('op-taux-type').value;
  $('taux-h-row').style.display = t==='PIECE' ? 'none' : '';
  $('taux-p-row').style.display = t==='HORAIRE' ? 'none' : '';
}

async function saveOperateur() {
  const id = $('op-edit-id').value;
  if (!$('op-prenom').value||!$('op-nom').value) { toast('Prénom et Nom requis','err'); return; }
  const data = {
    prenom: $('op-prenom').value, nom: $('op-nom').value,
    specialite: $('op-spec').value,
    telephone: $('op-tel').value||null, email: $('op-email').value||null,
    type_taux: $('op-taux-type').value,
    taux_horaire: parseFloat($('op-taux-h').value)||0,
    taux_piece:   parseFloat($('op-taux-p').value)||0,
  };
  try {
    if (id) { await api(`/api/operateurs/${id}`,'PUT',data); toast('Opérateur mis à jour ✓'); }
    else    { await api('/api/operateurs','POST',data); toast('Opérateur créé ✓'); }
    closeModal('m-op'); loadOperators();
  } catch(e) { toast(e.message,'err'); }
}

async function deleteOperateur(id) {
  if (!confirm('Désactiver cet opérateur ?')) return;
  try { await api(`/api/operateurs/${id}`,'DELETE'); toast('Opérateur désactivé'); loadOperators(); }
  catch(e) { toast(e.message,'err'); }
}
