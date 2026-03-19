// ── nc.js v6 ─────────────────────────────────────────────
async function loadNC() {
  try {
    const [ncs, ofs, ops] = await Promise.all([
      api('/api/qualite/nc'),
      api('/api/of?limit=500'),
      api('/api/operateurs')
    ]);
    if (!ncs) return;

    // KPIs
    const open = (ncs||[]).filter(n => n.statut === 'OUVERTE').length;
    const inpr = (ncs||[]).filter(n => n.statut === 'EN_COURS').length;
    const crit = (ncs||[]).filter(n => n.gravite === 'CRITIQUE').length;
    const clos = (ncs||[]).filter(n => n.statut === 'CLOTUREE').length;

    if ($('nc-kpis')) $('nc-kpis').innerHTML = `
      <div class="kpi"><div class="kpi-lbl">Ouvertes</div><div class="kpi-val r">${open}</div></div>
      <div class="kpi"><div class="kpi-lbl">En Cours</div><div class="kpi-val o">${inpr}</div></div>
      <div class="kpi"><div class="kpi-lbl">Critiques</div><div class="kpi-val r">${crit}</div></div>
      <div class="kpi"><div class="kpi-lbl">Clôturées</div><div class="kpi-val g">${clos}</div></div>`;

    // Populate dropdowns
    if (ofs && $('nc-of')) {
      $('nc-of').innerHTML = '<option value="">— Aucun —</option>' +
        (ofs||[]).map(o => `<option value="${o.id}">${o.numero} · ${o.produit_nom}</option>`).join('');
    }
    if (ops && $('nc-resp')) {
      $('nc-resp').innerHTML = '<option value="">— Aucun —</option>' +
        (ops||[]).map(o => `<option value="${o.id}">${o.prenom} ${o.nom} (${o.specialite||''})</option>`).join('');
    }

    // Table
    const gMap = { MINEURE:'b-normal', MAJEURE:'b-inprogress', CRITIQUE:'b-urgent' };
    const gIcon = { MINEURE:'🟡', MAJEURE:'🟠', CRITIQUE:'🔴' };
    const sMap = { OUVERTE:'b-urgent', EN_COURS:'b-inprogress', CLOTUREE:'b-completed' };

    if ($('nc-table')) $('nc-table').innerHTML = (ncs||[]).length === 0 ? empty(8, 'Aucune non-conformité') :
      `<table><thead><tr>
        <th>N° NC</th><th>OF</th><th>Type Défaut</th><th>Gravité</th>
        <th>Action Corrective</th><th>Responsable</th><th>Statut</th><th>Actions</th>
      </tr></thead><tbody>
      ${(ncs||[]).map(n => `<tr>
        <td><span class="of-num" style="font-size:9px">${n.nc_numero}</span></td>
        <td><span class="of-num" style="font-size:9px;color:var(--muted)">${n.of_numero||'—'}</span></td>
        <td><strong style="font-size:11px">${n.type_defaut}</strong>
          ${n.description?`<div style="font-size:10px;color:var(--muted);margin-top:1px">${n.description.slice(0,60)}${n.description.length>60?'...':''}</div>`:''}
        </td>
        <td><span class="badge ${gMap[n.gravite]||'b-normal'}">${gIcon[n.gravite]||''} ${n.gravite}</span></td>
        <td style="font-size:11px;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${n.action_corrective||'—'}</td>
        <td style="font-size:11px">${n.responsable_prenom?n.responsable_prenom+' '+n.responsable_nom:'—'}</td>
        <td><span class="badge ${sMap[n.statut]||'b-draft'}">${n.statut.replace('_',' ')}</span></td>
        <td style="display:flex;gap:3px">
          <select class="fbtn" onchange="updateNCStatus(${n.id},this.value);this.value=''"
            style="font-size:9px;padding:2px 4px;background:var(--bg3);border:1px solid var(--border);border-radius:4px;color:var(--text)">
            <option value="">▾</option>
            <option value="OUVERTE">Ouverte</option>
            <option value="EN_COURS">En Cours</option>
            <option value="CLOTUREE">✓ Clôturée</option>
          </select>
        </td>
      </tr>`).join('')}
      </tbody></table>`;

  } catch(e) { toast('Erreur NC: ' + e.message, 'err'); }
}

async function saveNC() {
  if (!$('nc-defaut')?.value?.trim()) { toast('Type de défaut obligatoire', 'err'); return; }
  try {
    await api('/api/qualite/nc', 'POST', {
      of_id:             $('nc-of')?.value      ? parseInt($('nc-of').value)   : null,
      type_defaut:       $('nc-defaut').value.trim(),
      description:       $('nc-desc')?.value    || null,
      gravite:           $('nc-gravite')?.value || 'MINEURE',
      action_corrective: $('nc-action')?.value  || null,
      responsable_id:    $('nc-resp')?.value     ? parseInt($('nc-resp').value) : null
    });
    toast('NC créée ✓'); closeModal('modal-nc'); loadNC();
  } catch(e) { toast(e.message, 'err'); }
}

async function updateNCStatus(id, statut) {
  if (!statut) return;
  const data = { statut };
  if (statut === 'CLOTUREE') data.date_cloture = new Date().toISOString().split('T')[0];
  try {
    await api(`/api/qualite/nc/${id}`, 'PUT', data);
    toast(`NC → ${statut.replace('_',' ')} ✓`); loadNC();
  } catch(e) { toast(e.message, 'err'); }
}