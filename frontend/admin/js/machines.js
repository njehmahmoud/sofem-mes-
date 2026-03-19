// ── machines.js v6 ───────────────────────────────────────
const MACHINE_STATUS = {
  OPERATIONNELLE: { label: 'Opérationnelle', cls: 'b-completed',  color: 'var(--green)' },
  EN_MAINTENANCE: { label: 'En Maintenance',  cls: 'b-inprogress', color: 'var(--accent)' },
  EN_PANNE:       { label: 'En Panne',        cls: 'b-urgent',     color: 'var(--red)'    },
  ARRETEE:        { label: 'Arrêtée',         cls: 'b-draft',      color: 'var(--muted)'  }
};

async function loadMachines() {
  try {
    const [machines, stats] = await Promise.all([
      api('/api/machines'),
      api('/api/machines/stats/overview').catch(() => null)
    ]);
    if (!machines) return;

    // KPIs
    const total = machines.length;
    const oper  = machines.filter(m => m.statut === 'OPERATIONNELLE').length;
    const maint = machines.filter(m => m.statut === 'EN_MAINTENANCE').length;
    const panne = machines.filter(m => m.statut === 'EN_PANNE').length;

    $('machines-kpis').innerHTML = `
      <div class="kpi"><div class="kpi-lbl">Total</div><div class="kpi-val">${total}</div></div>
      <div class="kpi"><div class="kpi-lbl">Opérationnelles</div><div class="kpi-val g">${oper}</div></div>
      <div class="kpi"><div class="kpi-lbl">En Maintenance</div><div class="kpi-val o">${maint}</div></div>
      <div class="kpi"><div class="kpi-lbl">En Panne</div><div class="kpi-val r">${panne}</div></div>`;

    // Table
    $('machines-table').innerHTML = machines.length === 0 ? empty(7) :
      `<table><thead><tr>
        <th>Code</th><th>Nom</th><th>Type</th><th>Atelier</th>
        <th>Marque / Modèle</th><th>Statut</th><th>Actions</th>
      </tr></thead><tbody>
      ${machines.map(m => {
        const st = MACHINE_STATUS[m.statut] || MACHINE_STATUS.ARRETEE;
        return `<tr>
          <td><span class="of-num" style="font-size:9px">${m.code||'—'}</span></td>
          <td><strong>${m.nom}</strong></td>
          <td style="color:var(--muted);font-size:11px">${m.type||'—'}</td>
          <td style="color:var(--muted);font-size:11px">${m.atelier||'—'}</td>
          <td style="font-size:11px">${[m.marque,m.modele].filter(Boolean).join(' / ')||'—'}</td>
          <td><span class="badge ${st.cls}">${st.label}</span></td>
          <td style="display:flex;gap:4px">
            <select class="fbtn" onchange="changeMachineStatus(${m.id},this.value);this.value=''"
              style="font-size:10px;padding:2px 4px;background:var(--bg3);border:1px solid var(--border);border-radius:4px;color:var(--text)">
              <option value="">Statut ▾</option>
              ${Object.entries(MACHINE_STATUS).map(([k,v]) =>
                `<option value="${k}" ${m.statut===k?'disabled':''}>${v.label}</option>`
              ).join('')}
            </select>
            <button class="fbtn" onclick="openEditMachine(${m.id})" title="Modifier">✎</button>
            <button class="fbtn" style="color:var(--red)" onclick="deleteMachine(${m.id},'${m.nom.replace(/'/g,"\\'")}')">🗑</button>
          </td>
        </tr>`;
      }).join('')}
      </tbody></table>`;

    // Update code preview
    const codes = machines.filter(m=>(m.code||'').startsWith('MCH-')).sort((a,b)=>b.code.localeCompare(a.code));
    const nextN = codes.length ? parseInt(codes[0].code.split('-')[1]||0)+1 : 1;
    if ($('m-code-preview')) $('m-code-preview').textContent = `MCH-${String(nextN).padStart(3,'0')}`;

    // Populate machine select in maintenance modal
    const mSel = $('om-machine');
    if (mSel) mSel.innerHTML = '<option value="">— Machine —</option>' +
      machines.map(m => `<option value="${m.id}">${m.nom} (${m.atelier})</option>`).join('');

  } catch(e) { toast('Erreur machines: ' + e.message, 'err'); }
}

// ── CREATE / SAVE ─────────────────────────────────────────
async function saveMachine() {
  const editId = $('m-edit-id')?.value;
  if (!$('m-nom').value.trim()) { toast('Nom obligatoire', 'err'); return; }
  const data = {
    nom:              $('m-nom').value.trim(),
    type:             $('m-type').value.trim()  || null,
    atelier:          $('m-atelier').value,
    marque:           $('m-marque').value.trim()|| null,
    modele:           $('m-modele').value.trim()|| null,
    numero_serie:     $('m-serie').value.trim() || null,
    date_acquisition: $('m-date').value         || null,
    notes:            $('m-notes').value        || null
  };
  try {
    if (editId) {
      await api(`/api/machines/${editId}`, 'PUT', data);
      toast('Machine mise à jour ✓');
    } else {
      await api('/api/machines', 'POST', data);
      toast('Machine créée ✓');
    }
    closeModal('modal-machine');
    resetMachineModal();
    loadMachines();
  } catch(e) { toast(e.message, 'err'); }
}

function resetMachineModal() {
  if ($('m-edit-id')) $('m-edit-id').value = '';
  ['m-nom','m-type','m-marque','m-modele','m-serie','m-notes'].forEach(id => {
    if ($(id)) $(id).value = '';
  });
  if ($('m-date')) $('m-date').value = '';
  const title = document.querySelector('#modal-machine .modal-title');
  if (title) title.textContent = 'NOUVELLE MACHINE';
  const btn = document.querySelector('#modal-machine .modal-f .btn:last-child');
  if (btn) btn.textContent = 'Enregistrer';
}

function openEditMachine(id) {
  api(`/api/machines/${id}`).then(m => {
    if (!m) return;
    $('m-edit-id').value   = m.id;
    $('m-nom').value       = m.nom        || '';
    $('m-type').value      = m.type       || '';
    $('m-atelier').value   = m.atelier    || 'Atelier A';
    $('m-marque').value    = m.marque     || '';
    $('m-modele').value    = m.modele     || '';
    $('m-serie').value     = m.numero_serie || '';
    $('m-date').value      = m.date_acquisition || '';
    $('m-notes').value     = m.notes      || '';
    const title = document.querySelector('#modal-machine .modal-title');
    if (title) title.textContent = `MODIFIER — ${m.nom}`;
    openModal('modal-machine');
  });
}

async function changeMachineStatus(id, statut) {
  if (!statut) return;
  try {
    await api(`/api/machines/${id}`, 'PUT', { statut });
    toast(`Statut → ${MACHINE_STATUS[statut]?.label || statut} ✓`);
    loadMachines();
  } catch(e) { toast(e.message, 'err'); }
}

async function deleteMachine(id, nom) {
  if (!confirm(`Supprimer "${nom}" ?`)) return;
  try {
    await api(`/api/machines/${id}`, 'DELETE');
    toast('Machine supprimée ✓'); loadMachines();
  } catch(e) { toast(e.message, 'err'); }
}