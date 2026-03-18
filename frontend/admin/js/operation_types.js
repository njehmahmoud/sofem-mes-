// ── operation_types.js ───────────────────────────────────
let _opTypes = [];

async function loadOpTypes() {
  try {
    const types = await api('/api/operation-types/all') || [];
    _opTypes = types.filter(t => t.actif);

    $('op-types-tb').innerHTML = types.length === 0 ? empty(5) : types.map(t => `<tr>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${t.ordre}</td>
      <td><strong>${t.nom}</strong></td>
      <td style="font-size:11px;color:var(--muted)">${t.description||'—'}</td>
      <td><span class="badge ${t.actif?'b-completed':'b-cancelled'}">${t.actif?'ACTIF':'INACTIF'}</span></td>
      <td style="display:flex;gap:4px">
        <button class="fbtn" onclick="editOpType(${t.id},'${t.nom.replace(/'/g,"\\'")}','${(t.description||'').replace(/'/g,"\\'")}',${t.ordre})">✎</button>
        <button class="fbtn" style="color:var(--red)" onclick="deleteOpType(${t.id})">✕</button>
      </td>
    </tr>`).join('');
  } catch(e) { toast('Erreur opérations: ' + e.message, 'err'); }
}

function openNewOpType() {
  $('opt-edit-id').value = '';
  $('opt-nom').value = '';
  $('opt-desc').value = '';
  $('opt-ordre').value = (_opTypes.length + 1);
  document.querySelector('#m-op-type .modal-title').textContent = 'NOUVELLE OPÉRATION';
  openModal('m-op-type');
}

function editOpType(id, nom, desc, ordre) {
  $('opt-edit-id').value = id;
  $('opt-nom').value = nom;
  $('opt-desc').value = desc;
  $('opt-ordre').value = ordre;
  document.querySelector('#m-op-type .modal-title').textContent = 'MODIFIER OPÉRATION';
  openModal('m-op-type');
}

async function saveOpType() {
  const id  = $('opt-edit-id').value;
  const nom = $('opt-nom').value.trim();
  if (!nom) { toast('Nom obligatoire', 'err'); return; }
  const data = {
    nom,
    description: $('opt-desc').value.trim() || null,
    ordre: parseInt($('opt-ordre').value) || 0
  };
  try {
    if (id) {
      await api(`/api/operation-types/${id}`, 'PUT', data);
      toast('Opération mise à jour ✓');
    } else {
      await api('/api/operation-types', 'POST', data);
      toast(`'${nom}' ajoutée ✓`);
    }
    closeModal('m-op-type');
    loadOpTypes();
  } catch(e) { toast(e.message, 'err'); }
}

async function deleteOpType(id) {
  if (!confirm('Supprimer cette opération ?')) return;
  try {
    const res = await api(`/api/operation-types/${id}`, 'DELETE');
    toast(res.message || 'Supprimée');
    loadOpTypes();
  } catch(e) { toast(e.message, 'err'); }
}
