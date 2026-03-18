// ── achats.js ────────────────────────────────────────────

// ── DA ────────────────────────────────────────────────────
async function loadDA() {
  try {
    const [das, mats, ofs, ops] = await Promise.all([
      api('/api/achats/da'), api('/api/materiaux'),
      api('/api/of?limit=500'), api('/api/operateurs')
    ]);
    // Populate modal selects
    if (mats) $('da-mat').innerHTML = '<option value="">— Aucun —</option>' +
      mats.map(m => `<option value="${m.id}">${m.nom} (stock: ${m.stock_actuel} ${m.unite})</option>`).join('');
    if (ofs) {
      const daOfEl = $('da-of');
      if (daOfEl) daOfEl.innerHTML = '<option value="">— Aucun —</option>' +
        ofs.map(o => `<option value="${o.id}">${o.numero} — ${o.produit_nom}</option>`).join('');
    }
    // Populate demandeur from operateurs
    const opsList = await api('/api/operateurs') || [];
    const demEl = $('da-demandeur');
    if (demEl) demEl.innerHTML = '<option value="">— Aucun —</option>' +
      opsList.map(o => `<option value="${o.id}">${o.prenom} ${o.nom}</option>`).join('');
    if (ops) $('da-demandeur').innerHTML = '<option value="">— Aucun —</option>' +
      ops.map(o => `<option value="${o.id}">${o.prenom} ${o.nom}</option>`).join('');

    $('da-tb').innerHTML = (das||[]).length===0 ? empty(9) : das.map(da => {
      const badge = {PENDING:'b-draft',APPROVED:'b-approved',REJECTED:'b-cancelled',ORDERED:'b-inprogress'}[da.statut]||'b-draft';
      return `<tr>
        <td><span class="of-num">${da.da_numero}</span></td>
        <td style="font-size:11px;max-width:180px">${da.description}</td>
        <td style="font-size:11px">${da.materiau_nom||'—'}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${da.quantite} ${da.unite}</td>
        <td><span class="badge ${da.urgence==='URGENT'?'b-urgent':'b-normal'}">${da.urgence}</span></td>
        <td><span class="badge ${badge}">${da.statut}</span></td>
        <td style="font-size:10px;color:var(--muted)">${(da.created_at||'').slice(0,10)}</td>
        <td style="font-size:11px">${da.of_numero||'—'}</td>
        <td style="display:flex;gap:3px">
          <button class="btn btn-ghost btn-sm" onclick="window.open('${API}/api/achats/da/${da.id}/ba','_blank')" title="Besoins & Achats PDF">📋 BA</button>
          ${da.statut==='PENDING'
            ? `<button class="fbtn" style="color:var(--green)" onclick="updateDA(${da.id},'APPROVED')">✓</button>
               <button class="fbtn" style="color:var(--red)"   onclick="updateDA(${da.id},'REJECTED')">✕</button>`
            : ''}
        </td>
      </tr>`;
    }).join('');
  } catch(e) { toast('Erreur DA: '+e.message,'err'); }
}

async function saveDA() {
  if (!$('da-desc')?.value) { toast('Description requise','err'); return; }
  try {
    const res = await api('/api/achats/da','POST',{
      materiau_id:  $('da-mat')?.value       ? parseInt($('da-mat').value)       : null,
      of_id:        $('da-of')?.value         ? parseInt($('da-of').value)         : null,
      description:  $('da-desc').value,
      objet:        $('da-objet')?.value      || null,
      quantite:     parseFloat($('da-qte')?.value)||1,
      unite:        $('da-unite')?.value      || 'pcs',
      urgence:      $('da-urgence')?.value    || 'NORMAL',
      notes:        $('da-notes')?.value      || null,
      demandeur_id: $('da-demandeur')?.value  ? parseInt($('da-demandeur').value) : null
    });
    toast(`${res.da_numero} créée ✓`); closeModal('m-da'); loadDA();
  } catch(e) { toast(e.message,'err'); }
}

async function updateDA(id, statut) {
  try { await api(`/api/achats/da/${id}`,'PUT',{statut}); toast(`DA → ${statut} ✓`); loadDA(); }
  catch(e) { toast(e.message,'err'); }
}

// ── BC ────────────────────────────────────────────────────
async function loadBC() {
  try {
    const [bcs, das] = await Promise.all([api('/api/achats/bc'), api('/api/achats/da')]);
    if (das) $('bc-da').innerHTML = '<option value="">— DA liée —</option>' +
      das.filter(d=>d.statut==='APPROVED').map(d=>`<option value="${d.id}">${d.da_numero} — ${d.description.slice(0,30)}</option>`).join('');

    $('bc-tb').innerHTML = (bcs||[]).length===0 ? empty(7) : bcs.map(bc => {
      const badge={DRAFT:'b-draft',ENVOYE:'b-approved',RECU:'b-completed',ANNULE:'b-cancelled',RECU_PARTIEL:'b-inprogress'}[bc.statut]||'b-draft';
      return `<tr>
        <td><span class="of-num">${bc.bc_numero}</span></td>
        <td>${bc.fournisseur}</td>
        <td style="font-size:10px;color:var(--muted)">${bc.da_numero||'—'}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${bc.montant_ht||0} TND HT</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${bc.montant_ttc||0} TND TTC</td>
        <td><span class="badge ${badge}">${bc.statut}</span></td>
        <td style="display:flex;gap:3px">
          <button class="btn btn-ghost btn-sm" onclick="window.open('${API}/api/achats/bc/${bc.id}/pdf','_blank')">🖨️</button>
          <select class="fbtn" onchange="updateBC(${bc.id},this.value)" style="font-size:9px">
            <option value="">Statut</option>
            <option value="ENVOYE">Envoyé</option>
            <option value="RECU_PARTIEL">Reçu partiel</option>
            <option value="RECU">Reçu</option>
            <option value="ANNULE">Annulé</option>
          </select>
        </td>
      </tr>`;
    }).join('');
  } catch(e) { toast('Erreur BC: '+e.message,'err'); }
}

let bcLines = [];
function addBCLine() {
  bcLines.push({ description:'', quantite:1, unite:'pcs', prix_unitaire:0, materiau_id:null });
  renderBCLines();
}
function renderBCLines() {
  $('bc-lines').innerHTML = bcLines.map((l,i)=>`
    <div style="display:flex;gap:4px;margin-bottom:4px;align-items:center">
      <input placeholder="Désignation" value="${l.description}"
        style="flex:2;background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:3px 6px;color:var(--text);font-size:11px"
        onchange="bcLines[${i}].description=this.value">
      <input type="number" placeholder="Qté" value="${l.quantite}" min="0"
        style="width:55px;background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:3px 5px;color:var(--text);font-size:11px"
        onchange="bcLines[${i}].quantite=parseFloat(this.value)||0">
      <input placeholder="Unité" value="${l.unite}"
        style="width:45px;background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:3px 5px;color:var(--text);font-size:11px"
        onchange="bcLines[${i}].unite=this.value">
      <input type="number" placeholder="Prix HT" value="${l.prix_unitaire}" min="0" step="0.001"
        style="width:70px;background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:3px 5px;color:var(--text);font-size:11px"
        onchange="bcLines[${i}].prix_unitaire=parseFloat(this.value)||0">
      <button class="fbtn" style="color:var(--red)" onclick="bcLines.splice(${i},1);renderBCLines()">✕</button>
    </div>`).join('');
}

async function saveBC() {
  if (!$('bc-fourn').value) { toast('Fournisseur requis','err'); return; }
  try {
    const res = await api('/api/achats/bc','POST',{
      fournisseur: $('bc-fourn').value,
      da_id: $('bc-da').value ? parseInt($('bc-da').value) : null,
      notes: $('bc-notes').value||null,
      lignes: bcLines
    });
    toast(`${res.bc_numero} créé ✓`); closeModal('m-bc'); bcLines=[]; loadBC();
  } catch(e) { toast(e.message,'err'); }
}

async function updateBC(id, statut) {
  if (!statut) return;
  try { await api(`/api/achats/bc/${id}/statut?statut=${statut}`,'PUT'); toast('BC mis à jour'); loadBC(); }
  catch(e) { toast(e.message,'err'); }
}

// ── BR ────────────────────────────────────────────────────
async function loadBR() {
  try {
    const [brs, bcs] = await Promise.all([api('/api/achats/br'), api('/api/achats/bc')]);
    if (bcs) {
      const received = bcs.filter(b=>['ENVOYE','RECU_PARTIEL'].includes(b.statut));
      $('br-bc').innerHTML = '<option value="">— Sélectionner BC —</option>' +
        received.map(b=>`<option value="${b.id}">${b.bc_numero} — ${b.fournisseur}</option>`).join('');
    }
    $('br-date').value = new Date().toISOString().split('T')[0];
    $('br-tb').innerHTML = (brs||[]).length===0 ? empty(5) : brs.map(br=>
      `<tr><td><span class="of-num">${br.br_numero}</span></td>
       <td>${br.bc_numero}</td><td>${br.fournisseur}</td>
       <td><span class="badge ${br.statut==='COMPLET'?'b-completed':'b-inprogress'}">${br.statut}</span></td>
       <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${br.date_reception||'—'}</td></tr>`
    ).join('');
  } catch(e) { toast('Erreur BR: '+e.message,'err'); }
}

async function loadBCLines() {
  const bcId = parseInt($('br-bc').value); if (!bcId) return;
  const bc = await api('/api/achats/bc');
  const found = (bc||[]).find(b=>b.id===bcId);
  if (!found?.lignes) return;
  $('br-lines').innerHTML = '<div style="font-family:IBM Plex Mono,monospace;font-size:9px;color:var(--muted);margin-bottom:.5rem">QUANTITÉS REÇUES</div>' +
    found.lignes.map(l=>`
      <div style="display:flex;align-items:center;gap:.5rem;padding:4px 0;border-bottom:1px solid var(--border)">
        <span style="flex:1;font-size:11px">${l.materiau_nom||l.description} (commandé: ${l.quantite} ${l.unite})</span>
        <input type="number" id="br-qty-${l.id}" value="${l.quantite}" min="0" step="0.01"
          style="width:80px;background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:3px 6px;color:var(--text);font-family:'IBM Plex Mono',monospace;font-size:11px">
        <span style="font-size:10px;color:var(--muted)">${l.unite}</span>
      </div>`).join('');
  // Store lines for save
  window._brLines = found.lignes;
}

async function saveBR() {
  const bcId = parseInt($('br-bc').value);
  if (!bcId) { toast('Sélectionner un BC','err'); return; }
  const lignes = (window._brLines||[]).map(l=>({
    bc_ligne_id: l.id,
    quantite_recue: parseFloat($(`br-qty-${l.id}`)?.value||0)
  })).filter(l=>l.quantite_recue>0);
  try {
    const res = await api('/api/achats/br','POST',{
      bc_id: bcId, date_reception: $('br-date').value,
      statut: $('br-statut').value, lignes
    });
    toast(`${res.br_numero} créé — stock mis à jour ✓`); closeModal('m-br'); loadBR();
  } catch(e) { toast(e.message,'err'); }
}

// ── FA ────────────────────────────────────────────────────
async function loadFA() {
  try {
    const [fas, bcs] = await Promise.all([api('/api/achats/fa'), api('/api/achats/bc')]);
    if (bcs) {
      const received = bcs.filter(b=>b.statut==='RECU');
      $('fa-bc').innerHTML = '<option value="">— Sélectionner BC —</option>' +
        received.map(b=>`<option value="${b.id}">${b.bc_numero} — ${b.fournisseur}</option>`).join('');
    }
    $('fa-date').value = new Date().toISOString().split('T')[0];
    $('fa-tb').innerHTML = (fas||[]).length===0 ? empty(7) : fas.map(fa=>
      `<tr><td><span class="of-num">${fa.fa_numero}</span></td>
       <td>${fa.fournisseur}</td><td>${fa.bc_numero}</td>
       <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${fa.montant_ht} HT</td>
       <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${fa.montant_ttc} TTC</td>
       <td><span class="badge ${fa.statut==='PAYEE'?'b-completed':'b-draft'}">${fa.statut}</span></td>
       <td>${fa.statut==='PENDING'
         ? `<button class="fbtn" style="color:var(--green)" onclick="payFA(${fa.id})">✓ Payer</button>`
         : '—'}</td></tr>`
    ).join('');
  } catch(e) { toast('Erreur FA: '+e.message,'err'); }
}

async function saveFA() {
  if (!$('fa-bc').value||!$('fa-fourn').value) { toast('BC et fournisseur requis','err'); return; }
  try {
    const res = await api('/api/achats/fa','POST',{
      bc_id: parseInt($('fa-bc').value),
      fournisseur: $('fa-fourn').value,
      date_facture: $('fa-date').value,
      notes: $('fa-notes').value||null
    });
    toast(`${res.fa_numero} créée ✓`); closeModal('m-fa'); loadFA();
  } catch(e) { toast(e.message,'err'); }
}

async function payFA(id) {
  try { await api(`/api/achats/fa/${id}/payer`,'PUT'); toast('Facture payée ✓'); loadFA(); }
  catch(e) { toast(e.message,'err'); }
}