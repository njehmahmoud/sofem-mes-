// ── of.js ────────────────────────────────────────────────
let allOFs = [];
let ofFilter = { statut: '', priorite: '' };
let _ofBomData = [];
let _ofOpsData = []; // [{operation_nom, machine_id, operateur_ids:[]}]

async function loadOrders() {
  $('orders-tb').innerHTML = loading(10);
  try {
    let url = '/api/of?limit=500';
    if (ofFilter.statut)   url += `&statut=${ofFilter.statut}`;
    if (ofFilter.priorite) url += `&priorite=${ofFilter.priorite}`;
    allOFs = await api(url) || [];
    renderOrders(allOFs);
  } catch(e) { toast('Erreur OFs: ' + e.message, 'err'); }
}

function renderOrders(ofs) {
  $('search-count').textContent = `${ofs.length} ordre(s)`;
  $('orders-tb').innerHTML = ofs.length === 0 ? empty(12, 'Aucun OF trouvé') : ofs.map(of => {
    const blBadge = of.bl_numero
      ? `<span class="of-num" style="font-size:9px;cursor:pointer" onclick="navigate('bl')" title="Voir BL">${of.bl_numero}</span>`
      : '—';
    const blStatut = of.bl_statut === 'LIVRE'
      ? '<span class="badge b-completed" style="font-size:7px">LIVRÉ</span>'
      : of.bl_statut === 'EMIS'
        ? '<span class="badge b-approved" style="font-size:7px">ÉMIS</span>'
        : '';

    return `<tr>
      <td><input type="checkbox" class="of-chk" value="${of.id}" ${of.statut!=='COMPLETED'?'disabled':''}></td>
      <td><span class="of-num" style="cursor:pointer" onclick="openOFDetail(${of.id})" title="Voir détail">${of.numero}</span></td>
      <td>${blBadge} ${blStatut}</td>
      <td>${of.produit_nom}</td>
      <td style="font-size:11px;color:var(--muted)">${of.client_nom||'—'}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${of.quantite}</td>
      <td>${pBadge(of.priorite)}</td>
      <td>${sBadge(of.statut)}</td>
      <td>${dots(of.operations)}</td>
      <td style="font-size:10px;color:var(--muted)">${of.chef_projet_nom||'—'}</td>
      <td>${dateTd(of.date_echeance)}</td>
      <td><div style="display:flex;gap:3px;flex-wrap:wrap">
        ${of.statut==='COMPLETED' ? `
          <button class="btn btn-ghost btn-sm" style="color:var(--green);font-size:8px"
            onclick="window.open(pdfUrl('/api/of/${of.id}/fiche'),'_blank')" title="Fiche Résumé Production">📋 Fiche</button>
          <button class="btn btn-ghost btn-sm" style="font-size:8px"
            onclick="printFacture(${of.id},'client')" title="Facture client">📄 Facture</button>
          <button class="btn btn-ghost btn-sm" style="font-size:8px"
            onclick="printFacture(${of.id},'interne')" title="Rapport interne">🖨️ Interne</button>` : ''}
        ${of.statut!=='COMPLETED'&&of.statut!=='CANCELLED' ? `
          <button class="btn btn-ghost btn-sm" onclick="advanceOFSafe(${of.id},'${of.statut}')">▶</button>` : ''}
        ${of.statut!=='CANCELLED'&&of.statut!=='COMPLETED' ? `
          <button class="btn btn-ghost btn-sm" style="color:var(--accent)" onclick="openEditOF(${of.id})" title="Modifier">✎</button>` : ''}
        <button class="btn btn-ghost btn-sm" style="color:#f59e0b" onclick="openQuickTime(${of.id},'${of.numero}')" title="Modifier temps opérations">⏱</button>
        <button class="btn btn-ghost btn-sm" style="color:var(--blue)" onclick="duplicateOF(${of.id})" title="Dupliquer">⎘</button>
        ${of.statut!=='COMPLETED'&&of.statut!=='CANCELLED' ? `
          <button class="btn btn-ghost btn-sm" style="color:var(--red)" onclick="deleteOF(${of.id})" title="Supprimer">🗑</button>` : ''}
      </div></td>
    </tr>`;
  }).join('');
}

function searchOF() {
  const txt  = ($('search-of').value||'').toLowerCase();
  const date = $('search-date').value;
  renderOrders(allOFs.filter(of => {
    const matchTxt = !txt ||
      of.numero.toLowerCase().includes(txt) ||
      of.produit_nom.toLowerCase().includes(txt) ||
      (of.client_nom||'').toLowerCase().includes(txt) ||
      (of.chef_projet_nom||'').toLowerCase().includes(txt);
    const matchDate = !date || (of.date_echeance||'').startsWith(date);
    return matchTxt && matchDate;
  }));
}

function filterOF(btn, val, field = '') {
  document.querySelectorAll('#page-orders .fbtn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  ofFilter = { statut:'', priorite:'' };
  if (field==='p') ofFilter.priorite = val; else ofFilter.statut = val;
  $('search-of').value = ''; $('search-date').value = '';
  loadOrders();
}

async function advanceOF(id, current) {
  const next = {DRAFT:'APPROVED', APPROVED:'IN_PROGRESS', IN_PROGRESS:'COMPLETED'}[current];
  if (!next) return;
  try {
    await api(`/api/of/${id}`, 'PUT', {statut: next});
    toast(`OF → ${next} ✓`); loadOrders();
  } catch(e) {
    // Handle stock insufficient (409)
    if (e.message && e.message.includes('Stock insuffisant')) {
      try {
        const detail = JSON.parse(e.message.replace('Stock insuffisant — ','').replace(/.*?(\{.*\}).*/s,'$1'));
      } catch {}
      // Re-fetch the error detail from the response
      showStockWarning(e);
    } else {
      toast(e.message, 'err');
    }
  }
}

async function advanceOFSafe(id, current) {
  const next = {DRAFT:'APPROVED', APPROVED:'IN_PROGRESS', IN_PROGRESS:'COMPLETED'}[current];
  if (!next) return;
  const res = await fetch(`${API}/api/of/${id}`, {
    method:'PUT',
    headers:{'Content-Type':'application/json','Authorization':'Bearer '+localStorage.getItem('token')},
    body: JSON.stringify({statut: next})
  });
  if (res.ok) {
    const labels = {APPROVED:'Approuvé', IN_PROGRESS:'En Cours', COMPLETED:'Terminé'};
    toast(`OF → ${labels[next]||next} ✓`);
    loadOrders();
    return;
  }
  if (res.status === 409) {
    const err = await res.json();
    const detail = err.detail || err;
    if (detail.statut === 'APPROVED') {
      // OF was approved but stock insufficient — show warning and refresh
      loadOrders();
    }
    if (detail.pending_das > 0) {
      // Trying to start but DAs still pending
      showStockWarning([], [], detail.pending_das);
    } else {
      showStockWarning(detail.shortfalls || [], detail.das_crees || []);
    }
  } else {
    const err = await res.json().catch(()=>({detail:'Erreur'}));
    toast(err.detail || 'Erreur', 'err');
  }
}

function showStockWarning(shortfalls, das, pendingDas) {
  if (pendingDas > 0) {
    $('stock-warning-list').innerHTML = `
      <div style="padding:.75rem;background:rgba(245,166,35,0.1);border:1px solid var(--accent);border-radius:6px;font-size:12px">
        ⏳ <strong>${pendingDas} Demande(s) d'Achat</strong> sont en attente de réception.<br>
        <span style="color:var(--muted);font-size:11px">Le démarrage sera possible une fois les matériaux réceptionnés et le stock mis à jour.</span>
      </div>`;
    $('stock-das-created').style.display = 'none';
  } else {
    $('stock-warning-list').innerHTML = (shortfalls||[]).map(s =>
      `<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--border);font-size:11px">
        <span><strong>${s.materiau}</strong></span>
        <span style="font-family:'IBM Plex Mono',monospace;color:var(--red)">
          Stock: ${s.stock} ${s.unite} | Requis: ${s.requis} | Manque: ${s.manque}
        </span>
      </div>`).join('');
    if (das && das.length > 0) {
      $('stock-das-created').style.display = 'block';
      $('stock-das-list').innerHTML = das.map(d =>
        `<div style="font-size:11px;font-family:'IBM Plex Mono',monospace;color:var(--green)">✓ ${d.da_numero} — ${d.materiau} (${d.quantite})</div>`
      ).join('');
    } else {
      $('stock-das-created').style.display = 'none';
    }
  }
  openModal('m-stock-warning');
}

async function cancelOF(id) {
  if (!confirm('Annuler cet OF ?')) return;
  try { await api(`/api/of/${id}`, 'DELETE'); toast('OF annulé'); loadOrders(); }
  catch(e) { toast(e.message,'err'); }
}

function printFacture(ofId, type='interne') {
  window.open(pdfUrl(`/api/facture/${ofId}?type=${type}`), '_blank');
}

// ── OF CREATION MODAL ────────────────────────────────────
async function openOFModal() {
  _ofOpsData = [];
  _ofBomData = [];
  const [prods, ops, chefs, clients, machines, opTypes] = await Promise.all([
    api('/api/produits'), api('/api/operateurs'),
    api('/api/operateurs?role=CHEF_ATELIER'),
    api('/api/clients'),  api('/api/machines'),
    api('/api/operation-types')
  ]);
  window._opTypesCache = opTypes || [];

  // Populate selects
  $('of-prod').innerHTML = (prods||[]).map(p =>
    `<option value="${p.id}" data-bom='${JSON.stringify(p.bom||[]).replace(/'/g,"&apos;")}'>${p.code} — ${p.nom}</option>`
  ).join('');
  $('of-client').innerHTML = '<option value="">— Aucun client —</option>' +
    (clients||[]).map(c => `<option value="${c.id}">${c.nom} (${c.code})</option>`).join('');
  // Chef Atelier = only CHEF_ATELIER role
  $('of-chef').innerHTML = '<option value="">— Non assigné —</option>' +
    (chefs?.length
      ? chefs.map(o => `<option value="${o.id}">${o.prenom} ${o.nom}</option>`).join('')
      : ops.map(o => `<option value="${o.id}" style="color:var(--muted)">${o.prenom} ${o.nom} (aucun chef défini)</option>`).join('')
    );
  if (!chefs?.length) {
    const lbl = $('of-chef').closest?.('.fg')?.querySelector?.('label');
    if (lbl) lbl.innerHTML = 'Chef Atelier <span style="color:var(--accent);font-size:9px">⚠ Définir rôle dans Opérateurs</span>';
  }

  // Store for use in operations builder
  window._opsCache = ops || [];
  window._machinesCache = machines || [];

  renderOFOpsBuilder();
  onOFProductChange();
  openModal('m-of');
}

function onOFProductChange() {
  const sel = $('of-prod');
  if (!sel?.options[sel.selectedIndex]) return;
  try { _ofBomData = JSON.parse(sel.options[sel.selectedIndex].dataset.bom || '[]'); }
  catch { _ofBomData = []; }
  onOFQtyChange();
}

function onOFQtyChange() {
  const qty = parseInt($('of-qte')?.value) || 1;
  if (!_ofBomData.length) {
    $('of-bom-preview').innerHTML = '<span style="color:var(--muted);font-size:11px">— Pas de BOM pour ce produit —</span>';
    $('bom-stock-warn').textContent = '';
    return;
  }
  let shortfalls = 0;
  $('of-bom-preview').innerHTML = _ofBomData.map((b, i) => {
    const needed = (b.quantite_par_unite || 0) * qty;
    const stock  = parseFloat(b.stock_actuel) || 0;
    const ok = stock >= needed;
    if (!ok) shortfalls++;
    return `<div style="display:flex;align-items:center;gap:.5rem;padding:3px 0;border-bottom:1px solid var(--border)">
      <span style="flex:1;font-size:11px">${b.materiau_nom}</span>
      <input type="number" value="${needed.toFixed(3)}" step="0.001" min="0.001"
        style="width:75px;background:var(--bg3);border:1px solid ${ok?'var(--border)':'var(--red)'};border-radius:4px;padding:2px 5px;color:var(--text);font-family:'IBM Plex Mono',monospace;font-size:10px"
        onchange="_ofBomData[${i}].quantite_override=parseFloat(this.value)">
      <span style="font-size:9px;color:var(--muted)">${b.unite}</span>
      <span style="font-size:9px;color:${ok?'var(--green)':'var(--red)'}">${ok?'✓':'⚠'} ${stock}</span>
    </div>`;
  }).join('');
  $('bom-stock-warn').textContent = shortfalls > 0 ? `⚠ ${shortfalls} DA(s) auto` : '✓ Stock OK';
}

// ── DYNAMIC OPERATIONS BUILDER ───────────────────────────
function renderOFOpsBuilder() {
  const ops    = window._opsCache || [];
  const mach   = window._machinesCache || [];
  const types  = window._opTypesCache || [];

  $('of-ops-list').innerHTML = _ofOpsData.length === 0
    ? '<div style="color:var(--muted);font-size:11px;padding:.5rem">— Cliquez + Ajouter pour créer une op&eacute;ration —</div>'
    : _ofOpsData.map((op, i) => `
      <div style="background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:.6rem;margin-bottom:.4rem">
        <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.5rem">
          <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--red);font-weight:600;min-width:16px">${i+1}</span>

          <!-- Operation type dropdown -->
          <select onchange="_ofOpsData[${i}].operation_nom=this.value"
            style="flex:1;background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:4px 8px;color:var(--text);font-size:11px">
            <option value="">— Sélectionner opération —</option>
            ${types.map(t => `<option value="${t.nom}" ${op.operation_nom===t.nom?'selected':''}>${t.nom}</option>`).join('')}
          </select>

          <!-- Machine dropdown -->
          <select onchange="_ofOpsData[${i}].machine_id=this.value?parseInt(this.value):null"
            style="flex:1;background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:4px 8px;color:var(--text);font-size:11px">
            <option value="">— Machine —</option>
            ${mach.map(m => `<option value="${m.id}" ${op.machine_id===m.id?'selected':''}>${m.nom}</option>`).join('')}
          </select>

          <button class="fbtn" style="color:var(--red)" onclick="_ofOpsData.splice(${i},1);renderOFOpsBuilder()">✕</button>
        </div>

        <!-- Operators for this operation -->
        <div style="font-size:8px;color:var(--muted);font-family:'IBM Plex Mono',monospace;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Opérateurs</div>
        <div style="display:flex;flex-wrap:wrap;gap:4px">
          ${ops.map(o => {
            const checked = (op.operateur_ids||[]).includes(o.id);
            return `<label style="display:flex;align-items:center;gap:3px;font-size:10px;cursor:pointer;padding:2px 7px;background:${checked?'rgba(212,43,43,0.12)':'var(--bg2)'};border:1px solid ${checked?'var(--red)':'var(--border)'};border-radius:4px;transition:all .1s">
              <input type="checkbox" ${checked?'checked':''} style="accent-color:var(--red)"
                onchange="toggleOpOnOp(${i},${o.id},this.checked)">
              ${o.prenom} ${o.nom}
              <span style="font-size:8px;color:var(--muted);margin-left:2px">(${o.specialite||''})</span>
            </label>`;
          }).join('')}
        </div>
      </div>`
    ).join('');
}

function addOFOperation() {
  _ofOpsData.push({ operation_nom: '', machine_id: null, operateur_ids: [] });
  renderOFOpsBuilder();
}

function toggleOpOnOp(opIdx, operateurId, checked) {
  if (!_ofOpsData[opIdx]) return;
  const ids = _ofOpsData[opIdx].operateur_ids;
  if (checked && !ids.includes(operateurId)) ids.push(operateurId);
  if (!checked) _ofOpsData[opIdx].operateur_ids = ids.filter(id => id !== operateurId);
}

async function createOF() {
  if (!$('of-prod').value || !$('of-date').value) {
    toast('Produit et date obligatoires', 'err'); return;
  }
  const qty = parseInt($('of-qte').value) || 1;
  const bom_overrides = _ofBomData.map(b => ({
    materiau_id: b.materiau_id,
    quantite_requise: b.quantite_override != null ? b.quantite_override : (b.quantite_par_unite * qty)
  }));
  const payload = {
    produit_id:      parseInt($('of-prod').value),
    quantite:        qty,
    priorite:        $('of-prio').value,
    client_id:       $('of-client').value ? parseInt($('of-client').value) : null,
    chef_projet_id:  $('of-chef').value   ? parseInt($('of-chef').value)   : null,
    plan_numero:     $('of-plan').value   || null,
    atelier:         $('of-atelier').value || 'Atelier A',
    date_echeance:   $('of-date').value,
    notes:           $('of-notes').value  || null,
    sous_traitant:   $('of-st-nom').value || null,
    sous_traitant_op: $('of-st-op').value || null,
    sous_traitant_cout: parseFloat($('of-st-cout').value) || 0,
    operations:      _ofOpsData.filter(o => o.operation_nom.trim()),
    bom_overrides:   bom_overrides.filter(b => b.quantite_requise > 0)
  };
  try {
    const res = await api('/api/of', 'POST', payload);
    let msg = `${res.numero} créé ✓`;
    if (res.bl_numero) msg += ` · BL: ${res.bl_numero}`;
    if (res.das_crees?.length) msg += ` · ${res.das_crees.length} DA(s) auto`;
    toast(msg);
    closeModal('m-of');
    loadOrders();
  } catch(e) { toast(e.message, 'err'); }
}


// ── OF EDIT ───────────────────────────────────────────────
async function openEditOF(ofId) {
  const of = await api(`/api/of/${ofId}`);
  if (!of) return;
  const [prods, ops, chefs, clients, machines, opTypes] = await Promise.all([
    api('/api/produits'), api('/api/operateurs'),
    api('/api/operateurs?role=CHEF_ATELIER'),
    api('/api/clients'),  api('/api/machines'),
    api('/api/operation-types')
  ]);
  window._opTypesCache = opTypes || [];

  // Pre-fill OF modal with existing data
  window._editingOfId = ofId;
  $('of-prod').innerHTML = (prods||[]).map(p =>
    `<option value="${p.id}" data-bom='${JSON.stringify(p.bom||[]).replace(/'/g,"&apos;")}'
     ${p.id===of.produit_id?'selected':''}>${p.code} — ${p.nom}</option>`).join('');
  $('of-client').innerHTML = '<option value="">— Aucun client —</option>' +
    (clients||[]).map(c => `<option value="${c.id}" ${c.id===of.client_id?'selected':''}>${c.nom}</option>`).join('');
  $('of-chef').innerHTML = '<option value="">— Non assigné —</option>' +
    (chefs?.length
      ? chefs.map(o => `<option value="${o.id}" ${o.id===of.chef_projet_id?'selected':''}>${o.prenom} ${o.nom}</option>`).join('')
      : ops.map(o => `<option value="${o.id}" ${o.id===of.chef_projet_id?'selected':''}>${o.prenom} ${o.nom}</option>`).join('')
    );
  $('of-prio').value = of.priorite || 'NORMAL';
  $('of-atelier').value = of.atelier || 'Atelier A';
  $('of-date').value = of.date_echeance || '';
  $('of-plan').value = of.plan_numero || '';
  $('of-notes').value = of.notes || '';
  $('of-st-nom').value = of.sous_traitant || '';
  $('of-st-op').value = of.sous_traitant_op || '';
  $('of-st-cout').value = of.sous_traitant_cout || 0;
  $('of-qte').value = of.quantite || 1;

  // Pre-fill operations
  window._opsCache = ops || [];
  window._machinesCache = machines || [];
  _ofOpsData = (of.operations||[]).map(op => ({
    operation_nom: op.operation_nom,
    machine_id: op.machine_id || null,
    operateur_ids: [] // will be loaded separately
  }));
  renderOFOpsBuilder();

  // Pre-fill BOM
  _ofBomData = (of.bom||[]).map(b => ({...b, quantite_override: null}));
  onOFQtyChange();

  // Change modal button
  const btn = document.querySelector('#m-of .modal-f .btn:last-child');
  if (btn) { btn.textContent = '💾 Enregistrer modifications'; btn.onclick = saveEditOF; }
  const title = document.querySelector('#m-of .modal-title');
  if (title) title.textContent = `MODIFIER OF — ${of.numero}`;

  openModal('m-of');
}

async function saveEditOF() {
  const id = window._editingOfId;
  if (!id) return;
  const qty = parseInt($('of-qte').value) || 1;
  const bom_overrides = _ofBomData.map((b,i) => ({
    materiau_id: b.materiau_id,
    quantite_requise: b.quantite_override != null ? b.quantite_override : (b.quantite_par_unite * qty)
  }));
  const payload = {
    produit_id:     parseInt($('of-prod').value),
    quantite:       qty,
    priorite:       $('of-prio').value,
    client_id:      $('of-client').value ? parseInt($('of-client').value) : null,
    chef_projet_id: $('of-chef').value   ? parseInt($('of-chef').value)   : null,
    plan_numero:    $('of-plan').value   || null,
    atelier:        $('of-atelier').value || 'Atelier A',
    date_echeance:  $('of-date').value,
    notes:          $('of-notes').value  || null,
    sous_traitant:  $('of-st-nom').value || null,
    sous_traitant_op:   $('of-st-op').value   || null,
    sous_traitant_cout: parseFloat($('of-st-cout').value) || 0,
    operations:     _ofOpsData.filter(o => o.operation_nom.trim()),
    bom_overrides:  bom_overrides.filter(b => b.quantite_requise > 0)
  };
  try {
    await api(`/api/of/${id}/full`, 'PUT', payload);
    toast('OF modifié ✓');
    closeModal('m-of');
    // Reset modal to create mode
    window._editingOfId = null;
    const btn = document.querySelector('#m-of .modal-f .btn:last-child');
    if (btn) { btn.textContent = 'Créer OF + BL'; btn.onclick = createOF; }
    const title = document.querySelector('#m-of .modal-title');
    if (title) title.textContent = 'NOUVEL ORDRE DE FABRICATION';
    loadOrders();
  } catch(e) { toast(e.message, 'err'); }
}

async function deleteOF(id) {
  if (!confirm('Supprimer définitivement cet OF et tous ses documents liés ?')) return;
  try {
    await api(`/api/of/${id}`, 'DELETE');
    toast('OF supprimé ✓'); loadOrders();
  } catch(e) { toast(e.message, 'err'); }
}


// ── OF DUPLICATION ────────────────────────────────────────
async function duplicateOF(id) {
  try {
    // Load OF data + dropdowns in parallel
    const [of, clients, ops] = await Promise.all([
      api(`/api/of/${id}`),
      api('/api/clients'),
      api('/api/operateurs')
    ]);
    if (!of) return;

    // Store source ID
    $('dup-src-id').value       = id;
    $('dup-src-num').textContent = of.numero;

    // Pre-fill fields from source OF
    $('dup-qte').value   = of.quantite || 1;
    $('dup-prio').value  = of.priorite || 'NORMAL';
    $('dup-plan').value  = of.plan_numero || '';
    $('dup-notes').value = '';

    // Default new date = today + 30 days
    const d = new Date();
    d.setDate(d.getDate() + 30);
    $('dup-date').value = d.toISOString().split('T')[0];

    // Populate client dropdown
    $('dup-client').innerHTML = '<option value="">— Aucun —</option>' +
      (clients||[]).map(c =>
        `<option value="${c.id}" ${c.id===of.client_id?'selected':''}>${c.nom}</option>`
      ).join('');

    // Populate chef dropdown
    $('dup-chef').innerHTML = '<option value="">— Non assigné —</option>' +
      (ops||[]).map(o =>
        `<option value="${o.id}" ${o.id===of.chef_projet_id?'selected':''}>${o.prenom} ${o.nom}</option>`
      ).join('');

    // Summary of what will be copied
    const opCount  = (of.operations||[]).length;
    const bomCount = (of.bom||[]).length;
    $('dup-summary').innerHTML = `
      <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;text-transform:uppercase;
        letter-spacing:1px;color:var(--muted);margin-bottom:.4rem">Sera copié :</div>
      <div style="display:flex;gap:1.5rem">
        <span>📋 Produit : <strong style="color:var(--text)">${of.produit_nom}</strong></span>
        <span>⚙️ ${opCount} opération${opCount>1?'s':''}</span>
        <span>📦 ${bomCount} matériau${bomCount>1?'x':''} BOM</span>
        ${of.sous_traitant?`<span>🔧 Sous-traitance : ${of.sous_traitant}</span>`:''}
      </div>`;

    openModal('m-of-dup');
  } catch(e) { toast(e.message, 'err'); }
}

async function confirmDuplicateOF() {
  const id  = $('dup-src-id').value;
  const qte = parseInt($('dup-qte').value);
  const date = $('dup-date').value;

  if (!qte || qte < 1) { toast('Quantité invalide', 'err'); return; }
  if (!date) { toast('Date échéance obligatoire', 'err'); return; }

  try {
    const res = await api(`/api/of/${id}/duplicate`, 'POST', {
      quantite:      qte,
      priorite:      $('dup-prio').value,
      date_echeance: date,
      client_id:     $('dup-client').value ? parseInt($('dup-client').value) : null,
      chef_projet_id:$('dup-chef').value   ? parseInt($('dup-chef').value)   : null,
      plan_numero:   $('dup-plan').value   || null,
      notes:         $('dup-notes').value  || null,
    });
    toast(`✓ ${res.numero} créé`);
    closeModal('m-of-dup');
    loadOrders();
  } catch(e) { toast(e.message, 'err'); }
}

// ── OF DETAIL MODAL ──────────────────────────────────────

let _ofdOfId = null;
let _ofdOpsEdits = {};   // { op_id: { duree_reelle, notes } }
let _ofdBomEdits = {};   // { materiau_id: quantite_requise }
let _ofdOf = null;

async function openOFDetail(ofId) {
  _ofdOfId = ofId;
  _ofdOpsEdits = {};
  _ofdBomEdits = {};

  try {
    const of = await api(`/api/of/${ofId}`);
    _ofdOf = of;
    if (!of) return;

    // Header
    $('ofd-numero').textContent = of.numero;
    $('ofd-subtitle').textContent =
      `${of.produit_nom} · ${of.quantite} pcs · ${of.atelier||''}`;

    // Info band
    const cells = [
      ['CLIENT',       of.client_nom  || '—'],
      ['CHEF ATELIER', of.chef_projet_nom || '—'],
      ['ÉCHÉANCE',     of.date_echeance || '—'],
      ['STATUT',       of.statut],
    ];
    $('ofd-info').innerHTML = cells.map(([lbl, val]) => `
      <div class="ofd-info-cell">
        <div class="ofd-info-label">${lbl}</div>
        <div class="ofd-info-value">${val}</div>
      </div>`).join('');

    // Render active tab
    ofdTab('ops');
    openModal('m-of-detail');
  } catch(e) { toast(e.message, 'err'); }
}

function closeOFDetail() {
  closeModal('m-of-detail');
  _ofdOfId = null; _ofdOf = null;
  _ofdOpsEdits = {}; _ofdBomEdits = {};
}

function ofdTab(tab) {
  ['ops','bom','cost'].forEach(t => {
    $(`ofd-tab-${t}`)?.classList.toggle('active', t === tab);
    const pane = $(`ofd-pane-${t}`);
    if (pane) pane.style.display = t === tab ? '' : 'none';
  });
  const saveBtn = $('ofd-save-btn');
  if (saveBtn) {
    saveBtn.style.display = tab === 'cost' ? 'none' : '';
    saveBtn.textContent = tab === 'bom' ? '💾 Enregistrer matériaux' : '💾 Enregistrer opérations';
    saveBtn.onclick = tab === 'bom' ? saveBOMChanges : saveOFDetailOps;
  }
  if (tab === 'ops') renderOFDetailOps();
  if (tab === 'bom') renderOFDetailBOM();
  if (tab === 'cost') renderOFDetailCost();
}

function renderOFDetailOps() {
  const ops = _ofdOf?.operations || [];
  const stCls = { COMPLETED:'b-completed', IN_PROGRESS:'b-inprogress', PENDING:'b-draft' };
  const stLbl = { COMPLETED:'Terminé', IN_PROGRESS:'En cours', PENDING:'En attente' };

  $('ofd-ops-tb').innerHTML = ops.length === 0
    ? `<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:2rem;font-size:11px">— Aucune opération —</td></tr>`
    : ops.map((op, idx) => {
      const dur = _ofdOpsEdits[op.id]?.duree_reelle ?? (op.duree_reelle || '');
      const rowBg = idx % 2 === 0 ? 'background:var(--bg3)' : '';
      const debut = op.debut ? String(op.debut).slice(0,16).replace('T',' ') : '—';
      const fin   = op.fin   ? String(op.fin).slice(0,16).replace('T',' ') : '—';
      return `<tr style="${rowBg}">
        <td style="padding:7px 8px;font-weight:600;color:var(--text)">${op.operation_nom}</td>
        <td style="padding:7px 8px;font-size:10px;color:var(--muted)">${op.operateurs_noms||'—'}</td>
        <td style="padding:7px 8px;font-size:10px;color:var(--muted)">${op.machine_nom||'—'}</td>
        <td style="padding:7px 8px;text-align:center">
          <span class="badge ${stCls[op.statut]||'b-draft'}" style="font-size:8px">${stLbl[op.statut]||op.statut}</span>
        </td>
        <td style="padding:4px 8px;text-align:center">
          <input type="number" min="0" value="${dur}"
            style="width:70px;background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:3px 6px;color:var(--text);font-family:'IBM Plex Mono',monospace;font-size:11px;text-align:center"
            oninput="_ofdOpsEdits[${op.id}] = _ofdOpsEdits[${op.id}]||{}; _ofdOpsEdits[${op.id}].duree_reelle=parseInt(this.value)||0">
        </td>
        <td style="padding:7px 8px;text-align:center;font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--muted)">${debut}</td>
        <td style="padding:7px 8px;text-align:center;font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--muted)">${fin}</td>
      </tr>`;
    }).join('');
}

function renderOFDetailBOM() {
  const bom = _ofdOf?.bom || [];
  $('ofd-bom-tb').innerHTML = bom.length === 0
    ? `<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:2rem;font-size:11px">— Aucun matériau —</td></tr>`
    : bom.map((b, idx) => {
      const qte  = _ofdBomEdits[b.materiau_id] ?? b.quantite_requise;
      const prix = parseFloat(b.prix_unitaire || 0);
      const total = (parseFloat(qte) * prix).toFixed(3);
      const rowBg = idx % 2 === 0 ? 'background:var(--bg3)' : '';
      return `<tr style="${rowBg}">
        <td style="padding:7px 8px;font-weight:600">${b.materiau_nom}</td>
        <td style="padding:7px 8px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted)">${b.materiau_code||'—'}</td>
        <td style="padding:7px 8px;text-align:center;font-family:'IBM Plex Mono',monospace;font-weight:600;color:var(--accent)">${b.quantite_requise}</td>
        <td style="padding:7px 8px;text-align:center;color:var(--muted)">${b.unite}</td>
        <td style="padding:7px 8px;text-align:center;font-family:'IBM Plex Mono',monospace;font-size:10px">${prix.toFixed(3)} DT</td>
        <td style="padding:7px 8px;text-align:center;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--green)">${total} DT</td>
        <td style="padding:4px 8px;text-align:center">
          <input type="number" min="0.001" step="0.001" value="${qte}"
            style="width:80px;background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:3px 6px;color:var(--text);font-family:'IBM Plex Mono',monospace;font-size:11px;text-align:center"
            oninput="_ofdBomEdits[${b.materiau_id}]=parseFloat(this.value)||${b.quantite_requise}; updateBOMRowTotal(this, ${prix})">
        </td>
      </tr>`;
    }).join('');
}

function updateBOMRowTotal(input, prix) {
  const row = input.closest('tr');
  if (!row) return;
  const cells = row.querySelectorAll('td');
  const total = (parseFloat(input.value||0) * prix).toFixed(3);
  cells[5].textContent = total + ' DT';
}

function renderOFDetailCost() {
  const of = _ofdOf;
  if (!of) return;
  const matCost = parseFloat(of.cout_matieres || 0);
  const moCost  = parseFloat(of.cout_main_oeuvre || 0);
  const stCost  = parseFloat(of.cout_sous_traitance || 0);
  const total   = parseFloat(of.cout_revient || 0);
  const pv      = parseFloat(of.prix_vente_ht || 0) * parseInt(of.quantite || 1);
  const marge   = pv > 0 ? (pv - total) : null;

  const row = (lbl, val, highlight=false) =>
    `<div style="display:flex;justify-content:space-between;align-items:center;
      padding:.6rem 1rem;border-bottom:1px solid var(--border);
      ${highlight?'background:var(--bg3);border-radius:4px;':''}">
      <span style="font-size:12px;${highlight?'font-weight:700;color:var(--text)':'color:var(--muted)'}">${lbl}</span>
      <span style="font-family:'IBM Plex Mono',monospace;font-weight:700;
        color:${highlight?'var(--red)':'var(--text)'};font-size:${highlight?'14':'12'}px">${val}</span>
    </div>`;

  $('ofd-cost-content').innerHTML = `
    <div style="max-width:400px;margin:0 auto">
      ${row('Main d\'œuvre',   moCost.toFixed(3)  + ' DT')}
      ${row('Matières',        matCost.toFixed(3) + ' DT')}
      ${row('Sous-traitance',  stCost.toFixed(3)  + ' DT')}
      ${row('COÛT DE REVIENT', total.toFixed(3)   + ' DT', true)}
      ${pv > 0 ? row('Prix Vente HT',  pv.toFixed(3) + ' DT') : ''}
      ${marge !== null ? row('MARGE BRUTE', (marge >= 0 ? '+' : '') + marge.toFixed(3) + ' DT',true) : ''}
    </div>`;
}

async function saveOFDetailOps() {
  if (!_ofdOfId || !Object.keys(_ofdOpsEdits).length) {
    toast('Aucune modification à enregistrer', 'err'); return;
  }
  try {
    const saves = Object.entries(_ofdOpsEdits).map(([opId, edits]) =>
      api(`/api/of/${_ofdOfId}/operations/${opId}`, 'PUT', edits)
    );
    await Promise.all(saves);
    toast(`${saves.length} opération(s) enregistrée(s) ✓`);
    // Refresh OF data
    _ofdOf = await api(`/api/of/${_ofdOfId}`);
    _ofdOpsEdits = {};
    renderOFDetailOps();
    loadOrders();
  } catch(e) { toast(e.message, 'err'); }
}

async function saveBOMChanges() {
  if (!_ofdOfId || !Object.keys(_ofdBomEdits).length) {
    toast('Aucune modification à enregistrer', 'err'); return;
  }
  try {
    const bom = (_ofdOf?.bom || []).map(b => ({
      materiau_id: b.materiau_id,
      quantite_requise: _ofdBomEdits[b.materiau_id] ?? b.quantite_requise
    }));
    await api(`/api/of/${_ofdOfId}/bom`, 'PUT', bom);
    toast('BOM enregistré ✓');
    _ofdOf = await api(`/api/of/${_ofdOfId}`);
    _ofdBomEdits = {};
    renderOFDetailBOM();
  } catch(e) { toast(e.message, 'err'); }
}


// ── QUICK TIME EDIT ───────────────────────────────────────
let _qtOfId = null;

async function openQuickTime(ofId, ofNumero) {
  _qtOfId = ofId;
  try {
    const of = await api(`/api/of/${ofId}`);
    if (!of?.operations?.length) { toast('Aucune opération sur cet OF', 'err'); return; }

    $('qt-numero').textContent = ofNumero;

    $('qt-ops-list').innerHTML = of.operations.map((op, idx) => {
      const dur = op.duree_reelle || 0;
      const h   = Math.floor(dur / 60);
      const m   = dur % 60;
      const stCls = { COMPLETED:'b-completed', IN_PROGRESS:'b-inprogress', PENDING:'b-draft' }[op.statut] || 'b-draft';
      const stLbl = { COMPLETED:'✓', IN_PROGRESS:'⏳', PENDING:'—' }[op.statut] || '—';
      return `
        <div style="display:flex;align-items:center;gap:.75rem;padding:.5rem 0;
          border-bottom:1px solid var(--border);${idx%2===0?'':''}">
          <span style="font-size:9px;color:var(--muted);font-family:'IBM Plex Mono',monospace;min-width:16px">${idx+1}</span>
          <span style="flex:1;font-size:12px;font-weight:600">${op.operation_nom}</span>
          <span style="font-size:10px;color:var(--muted);min-width:80px">${op.operateurs_noms||'—'}</span>
          <span class="badge ${stCls}" style="font-size:8px;min-width:20px;text-align:center">${stLbl}</span>
          <div style="display:flex;align-items:center;gap:4px">
            <div style="display:flex;flex-direction:column;align-items:center">
              <span style="font-size:8px;color:var(--muted);margin-bottom:1px">H</span>
              <input type="number" min="0" max="999" value="${h}"
                id="qt-h-${op.id}"
                style="width:52px;background:var(--bg2);border:1px solid var(--border);border-radius:4px;
                  padding:4px 6px;color:var(--text);font-family:'IBM Plex Mono',monospace;font-size:12px;
                  text-align:center"
                oninput="updateQTTotal(${op.id})">
            </div>
            <span style="color:var(--muted);font-size:14px;margin-top:10px">:</span>
            <div style="display:flex;flex-direction:column;align-items:center">
              <span style="font-size:8px;color:var(--muted);margin-bottom:1px">MIN</span>
              <input type="number" min="0" max="59" value="${m}"
                id="qt-m-${op.id}"
                style="width:52px;background:var(--bg2);border:1px solid var(--border);border-radius:4px;
                  padding:4px 6px;color:var(--text);font-family:'IBM Plex Mono',monospace;font-size:12px;
                  text-align:center"
                oninput="updateQTTotal(${op.id})">
            </div>
            <div style="display:flex;flex-direction:column;align-items:center">
              <span style="font-size:8px;color:var(--muted);margin-bottom:1px">TOTAL</span>
              <span id="qt-total-${op.id}"
                style="width:60px;font-family:'IBM Plex Mono',monospace;font-size:11px;
                  color:var(--accent);text-align:center;padding:4px 0">
                ${dur ? (h > 0 ? `${h}h${m.toString().padStart(2,'0')}` : `${m}min`) : '—'}
              </span>
            </div>
          </div>
        </div>`;
    }).join('');

    // Store op ids for save
    window._qtOps = of.operations.map(o => o.id);
    openModal('m-quick-time');
  } catch(e) { toast(e.message, 'err'); }
}

function updateQTTotal(opId) {
  const h = parseInt($(`qt-h-${opId}`)?.value || 0);
  const m = parseInt($(`qt-m-${opId}`)?.value || 0);
  const total = h * 60 + m;
  const el = $(`qt-total-${opId}`);
  if (el) el.textContent = total > 0
    ? (h > 0 ? `${h}h${m.toString().padStart(2,'0')}` : `${m}min`)
    : '—';
}

async function saveQuickTime() {
  if (!_qtOfId || !window._qtOps?.length) return;
  const saves = window._qtOps.map(opId => {
    const h = parseInt($(`qt-h-${opId}`)?.value || 0);
    const m = parseInt($(`qt-m-${opId}`)?.value || 0);
    const total = h * 60 + m;
    return api(`/api/of/${_qtOfId}/operations/${opId}`, 'PUT', { duree_reelle: total });
  });
  try {
    await Promise.all(saves);
    toast(`Temps enregistrés ✓`);
    closeModal('m-quick-time');
    loadOrders();
    // If detail modal is open, refresh it
    if (_ofdOfId === _qtOfId) {
      _ofdOf = await api(`/api/of/${_qtOfId}`);
      renderOFDetailOps();
    }
  } catch(e) { toast(e.message, 'err'); }
}