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
      mats.map(m => `<option value="$${m.id}">$${m.nom} (stock: $${m.stock_actuel} $${m.unite})</option>`).join('');
    if (ofs) {
      const daOfEl = $('da-of');
      if (daOfEl) daOfEl.innerHTML = '<option value="">— Aucun —</option>' +
        ofs.map(o => `<option value="$${o.id}">$${o.numero} — ${o.produit_nom}</option>`).join('');
    }
    // Populate demandeur from operateurs
    const demEl = $('da-demandeur');
    if (demEl && ops) { // Use the 'ops' variable from Promise.all
      demEl.innerHTML = '<option value="">— Aucun —</option>' +
        ops.map(o => `<option value="$${o.id}">$${o.prenom} ${o.nom}</option>`).join('');
    }

    $('da-tb').innerHTML = (das||[]).length===0 ? empty(10) : das.map(da => {
      const badge = {PENDING:'b-draft',APPROVED:'b-approved',REJECTED:'b-cancelled',ORDERED:'b-inprogress',RECEIVED:'b-completed'}[da.statut]||'b-draft';
      const statutLabel = {PENDING:'En attente',APPROVED:'Approuvée',REJECTED:'Rejetée',ORDERED:'Commandée',RECEIVED:'Reçue'}[da.statut]||da.statut;
      // BC / BR links
      const bc = da.bc;
      let bcBrCell = '—';
      if (bc) {
        const brBadge = bc.br_statut === 'COMPLET'
          ? '<span class="badge b-completed" style="font-size:8px">BR REÇU</span>'
          : bc.br_statut === 'EN_ATTENTE'
            ? '<span class="badge b-draft" style="font-size:8px">BR EN ATTENTE</span>'
            : bc.br_statut === 'PARTIEL'
              ? '<span class="badge b-inprogress" style="font-size:8px">BR PARTIEL</span>'
              : '';
        bcBrCell = `<div style="display:flex;flex-direction:column;gap:2px">
          <div style="display:flex;align-items:center;gap:3px">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--accent)">${bc.bc_numero}</span>
            <button class="btn btn-ghost btn-sm" style="font-size:8px;padding:1px 5px"
              onclick="window.open(pdfUrl('/api/achats/bc/${bc.id}/pdf'),'_blank')" title="Imprimer BC">🖨️</button>
          </div>
          <div style="display:flex;align-items:center;gap:3px">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--muted)">${bc.br_numero||'—'}</span>
            ${brBadge}
          </div>
        </div>`;
      }
      return `<tr>
        <td><span class="of-num">${da.da_numero}</span></td>
        <td style="font-size:11px;max-width:160px">${da.description}</td>
        <td style="font-size:11px">${da.materiau_nom||'—'}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">$${da.quantite} $${da.unite}</td>
        <td><span class="badge $${da.urgence==='URGENT'?'b-urgent':'b-normal'}">$${da.urgence}</span></td>
        <td><span class="badge $${badge}">$${statutLabel}</span></td>
        <td style="font-size:10px;color:var(--muted)">${da.of_numero||'—'}</td>
        <td>${bcBrCell}</td>
        <td style="display:flex;gap:3px;flex-wrap:wrap">
          <button class="btn btn-ghost btn-sm" onclick="window.open(pdfUrl('/api/achats/da/${da.id}/ba'),'_blank')" title="BA PDF">📋 BA</button>
          ${da.statut==='PENDING'
            ? <button class="fbtn" style="color:var(--green)" onclick="updateDA($${da.id},'APPROVED')" title="Approuver">✓</button>        <button class="fbtn" style="color:var(--red)"   onclick="updateDA($${da.id},'REJECTED')" title="Rejeter">CANCELLED</button>
            : ''}
            ${!['CANCELLED','RECEIVED','ORDERED'].includes(da.statut)
            ? <button class="fbtn" style="color:var(--accent)"          onclick="cancelDA($${da.id},'$${da.da_numero}','$${(da.description||'').replace(/'/g,"\\'")}','$${da.statut}')"          title="Annuler">✕ Annuler</button>
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
      materiau_id:  $$('da-mat')?.value       ? parseInt($$('da-mat').value)       : null,
      of_id:        $$('da-of')?.value         ? parseInt($$('da-of').value)         : null,
      description:  $('da-desc').value,
      objet:        $('da-objet')?.value      || null,
      quantite:     parseFloat($('da-qte')?.value)||1,
      unite:        $('da-unite')?.value      || 'pcs',
      urgence:      $('da-urgence')?.value    || 'NORMAL',
      notes:        $('da-notes')?.value      || null,
      demandeur_id: $$('da-demandeur')?.value  ? parseInt($$('da-demandeur').value) : null
    });
    toast(`${res.da_numero} créée ✓`); closeModal('m-da'); loadDA();
  } catch(e) { toast(e.message,'err'); }
}

async function updateDA(id, statut) {
  try {
    const res = await api(`/api/achats/da/${id}`,'PUT',{statut});
    if (statut === 'APPROVED' && res.bc_numero) {
      toast(`DA approuvée ✓ — $${res.bc_numero} + $${res.br_numero} créés`);
    } else {
      toast(`DA → ${statut} ✓`);
    }
    loadDA(); loadBC(); loadBR();
  } catch(e) { toast(e.message,'err'); }
}

async function confirmerReception(brId, brNumero) {
  // Load BR details to pre-fill modal
  try {
    const brs = await api('/api/achats/br');
    const br  = (brs||[]).find(b => b.id === brId);
    if (!br) { toast('BR introuvable', 'err'); return; }

    // Find the BC line (quantity ordered)
    const bcs = await api('/api/achats/bc');
    const bc  = (bcs||[]).find(b => b.id === br.bc_id);
    const ligne = bc?.lignes?.[0];

    $('br-confirm-id').value      = brId;
    $('br-confirm-num').textContent = brNumero;

    // Info band
    const mat = ligne?.materiau_nom || ligne?.description || '—';
    const unite = ligne?.unite || '';
    $('br-confirm-info').innerHTML = `
      <div style="display:flex;gap:1.5rem;flex-wrap:wrap">
        <span>📦 <strong style="color:var(--text)">${mat}</strong></span>
        <span>🏭 Fournisseur: <strong style="color:var(--text)">${br.fournisseur}</strong></span>
        <span>📋 BC: <strong style="color:var(--accent)">${br.bc_numero}</strong></span>
        <span>Unité: <strong style="color:var(--text)">${unite}</strong></span>
      </div>`;

    const qteCmd = parseFloat(ligne?.quantite || 0);
    $('br-confirm-qte-cmd').value   = qteCmd;
    $('br-confirm-qte-recue').value = qteCmd;  // default = full quantity
    $('br-confirm-prix').value      = parseFloat(ligne?.prix_unitaire || 0);
    $('br-confirm-notes').value     = '';
    $('br-confirm-status').style.display = 'none';
    updateBRTotal();

    openModal('m-br-confirm');
  } catch(e) { toast(e.message, 'err'); }
}

function updateBRTotal() {
  const qte  = parseFloat($('br-confirm-qte-recue')?.value || 0);
  const prix = parseFloat($('br-confirm-prix')?.value || 0);
  const total = Math.round(qte * prix * 1000) / 1000;
  if ($$('br-confirm-total')) $$('br-confirm-total').value = total;

  // Show partial/full indicator
  const qteCmd = parseFloat($('br-confirm-qte-cmd')?.value || 0);
  const statusEl = $('br-confirm-status');
  if (statusEl && qteCmd > 0) {
    if (qte <= 0) {
      statusEl.style.display = 'block';
      statusEl.style.background = 'rgba(212,43,43,0.1)';
      statusEl.style.border = '1px solid var(--red)';
      statusEl.style.color = 'var(--red)';
      statusEl.textContent = '⚠ Quantité reçue doit être > 0';
    } else if (qte < qteCmd) {
      statusEl.style.display = 'block';
      statusEl.style.background = 'rgba(245,158,11,0.1)';
      statusEl.style.border = '1px solid #f59e0b';
      statusEl.style.color = '#f59e0b';
      statusEl.textContent = `⚠ Réception partielle — $${qte} / $${qteCmd} ${''} reçus`;
    } else {
      statusEl.style.display = 'block';
      statusEl.style.background = 'rgba(22,163,74,0.1)';
      statusEl.style.border = '1px solid var(--green)';
      statusEl.style.color = 'var(--green)';
      statusEl.textContent = `✓ Réception complète — $${qte} sur $${qteCmd} commandés`;
    }
  }
}

async function submitConfirmerReception() {
  const brId     = parseInt($('br-confirm-id').value);
  const qteRecue = parseFloat($('br-confirm-qte-recue').value);
  const prix     = parseFloat($('br-confirm-prix').value || 0);
  const notes    = $('br-confirm-notes').value || null;

  if (!qteRecue || qteRecue <= 0) { toast('Quantité reçue requise', 'err'); return; }

  try {
    // Update price on BC line first if provided
    if (prix > 0) {
      await api(`/api/achats/br/$${brId}/quantite?quantite_recue=$${qteRecue}`, 'PUT');
    } else {
      await api(`/api/achats/br/$${brId}/quantite?quantite_recue=$${qteRecue}`, 'PUT');
    }
    // Confirm reception
    const res = await api(`/api/achats/br/${brId}/confirmer`, 'PUT');
    toast(res.message + ' ✓');
    closeModal('m-br-confirm');
    loadDA(); loadBR(); loadBC();
    if (window.pageLoaders?.dashboard) window.pageLoaders.dashboard();
  } catch(e) { toast(e.message, 'err'); }
}

// ── BC ────────────────────────────────────────────────────
async function loadBC() {
  try {
    const [bcs, das, fourns] = await Promise.all([
      api('/api/achats/bc'), api('/api/achats/da'), api('/api/fournisseurs')
    ]);
    // Populate fournisseur dropdown
    if (fourns && $('bc-four')) {
      $('bc-four').innerHTML = '<option value="">— Sélectionner fournisseur —</option>' +
        fourns.map(f => `<option value="$${f.nom}">$${f.nom}${f.ville?' · '+f.ville:''}</option>`).join('');
    }
    // Populate DA — only APPROVED
    if (das && $$('bc-da')) $$('bc-da').innerHTML = '<option value="">— DA liée (optionnel) —</option>' +
      das.filter(d=>d.statut==='APPROVED').map(d=>`<option value="$${d.id}">$${d.da_numero} — $${d.description.slice(0,30)} ($${d.quantite} ${d.unite})</option>`).join('');

    $('bc-tb').innerHTML = (bcs||[]).length===0 ? empty(7) : bcs.map(bc => {
      const badge={DRAFT:'b-draft',ENVOYE:'b-approved',RECU:'b-completed',ANNULE:'b-cancelled',RECU_PARTIEL:'b-inprogress'}[bc.statut]||'b-draft';
      return `<tr>
        <td><span class="of-num">${bc.bc_numero}</span></td>
        <td>${bc.fournisseur}</td>
        <td style="font-size:10px;color:var(--muted)">${bc.da_numero||'—'}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${bc.montant_ht||0} TND HT</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${bc.montant_ttc||0} TND TTC</td>
        <td><span class="badge $${badge}">$${bc.statut}</span></td>
        <td style="display:flex;gap:3px">
          <button class="btn btn-ghost btn-sm" onclick="window.open(pdfUrl('/api/achats/bc/${bc.id}/pdf'),'_blank')">🖨️</button>
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