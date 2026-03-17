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
      <td><span class="of-num">${of.numero}</span></td>
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
            onclick="window.open('${API}/api/of/${of.id}/fiche','_blank')" title="Fiche Résumé Production">📋 Fiche</button>
          <button class="btn btn-ghost btn-sm" style="font-size:8px"
            onclick="printFacture(${of.id},'client')" title="Facture client">📄 Facture</button>
          <button class="btn btn-ghost btn-sm" style="font-size:8px"
            onclick="printFacture(${of.id},'interne')" title="Rapport interne">🖨️ Interne</button>` : ''}
        ${of.statut!=='COMPLETED'&&of.statut!=='CANCELLED' ? `
          <button class="btn btn-ghost btn-sm" onclick="advanceOF(${of.id},'${of.statut}')">▶</button>` : ''}
        ${of.statut!=='CANCELLED'&&of.statut!=='COMPLETED' ? `
          <button class="btn btn-ghost btn-sm" style="color:var(--red)" onclick="cancelOF(${of.id})">✕</button>` : ''}
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
  try { await api(`/api/of/${id}`, 'PUT', {statut:next}); toast(`OF → ${next} ✓`); loadOrders(); }
  catch(e) { toast(e.message,'err'); }
}

async function cancelOF(id) {
  if (!confirm('Annuler cet OF ?')) return;
  try { await api(`/api/of/${id}`, 'DELETE'); toast('OF annulé'); loadOrders(); }
  catch(e) { toast(e.message,'err'); }
}

function printFacture(ofId, type='interne') {
  window.open(`${API}/api/facture/${ofId}?type=${type}`, '_blank');
}

// ── OF CREATION MODAL ────────────────────────────────────
async function openOFModal() {
  _ofOpsData = [];
  _ofBomData = [];
  const [prods, ops, clients, machines] = await Promise.all([
    api('/api/produits'), api('/api/operateurs'),
    api('/api/clients'),  api('/api/machines')
  ]);

  // Populate selects
  $('of-prod').innerHTML = (prods||[]).map(p =>
    `<option value="${p.id}" data-bom='${JSON.stringify(p.bom||[]).replace(/'/g,"&apos;")}'>${p.code} — ${p.nom}</option>`
  ).join('');
  $('of-client').innerHTML = '<option value="">— Aucun client —</option>' +
    (clients||[]).map(c => `<option value="${c.id}">${c.nom} (${c.code})</option>`).join('');
  $('of-chef').innerHTML = '<option value="">— Non assigné —</option>' +
    (ops||[]).map(o => `<option value="${o.id}">${o.prenom} ${o.nom}</option>`).join('');

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
  const ops  = window._opsCache || [];
  const mach = window._machinesCache || [];
  $('of-ops-list').innerHTML = _ofOpsData.length === 0
    ? '<div style="color:var(--muted);font-size:11px;padding:.5rem">— Aucune opération —</div>'
    : _ofOpsData.map((op, i) => `
      <div style="background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:.6rem;margin-bottom:.4rem">
        <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.4rem">
          <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--red);font-weight:600">${i+1}</span>
          <input value="${op.operation_nom}" placeholder="Nom opération"
            style="flex:1;background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:3px 7px;color:var(--text);font-size:11px"
            onchange="_ofOpsData[${i}].operation_nom=this.value">
          <select onchange="_ofOpsData[${i}].machine_id=this.value?parseInt(this.value):null"
            style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:3px 6px;color:var(--text);font-size:10px">
            <option value="">— Machine —</option>
            ${mach.map(m => `<option value="${m.id}" ${op.machine_id===m.id?'selected':''}>${m.nom}</option>`).join('')}
          </select>
          <button class="fbtn" style="color:var(--red)" onclick="_ofOpsData.splice(${i},1);renderOFOpsBuilder()">✕</button>
        </div>
        <div style="font-size:9px;color:var(--muted);font-family:'IBM Plex Mono',monospace;margin-bottom:3px">OPÉRATEURS</div>
        <div style="display:flex;flex-wrap:wrap;gap:4px">
          ${ops.map(o => {
            const checked = (op.operateur_ids||[]).includes(o.id);
            return `<label style="display:flex;align-items:center;gap:3px;font-size:10px;cursor:pointer;padding:2px 6px;background:${checked?'rgba(212,43,43,0.15)':'var(--bg2)'};border:1px solid ${checked?'var(--red)':'var(--border)'};border-radius:4px">
              <input type="checkbox" ${checked?'checked':''} style="accent-color:var(--red)"
                onchange="toggleOpOnOp(${i},${o.id},this.checked)">
              ${o.prenom} ${o.nom}
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
