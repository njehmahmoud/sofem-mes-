// ── bl.js ────────────────────────────────────────────────
async function loadBL() {
  try {
    const bls = await api('/api/bl') || [];
    // Enrich with OF statut for livrer button
    bls.forEach(bl => { bl.of_statut = bl.of_statut || ''; });
    $('bl-tb').innerHTML = bls.length===0 ? empty(8) : bls.map(bl => {
      const isLivre = bl.statut==='LIVRE';
      const badge   = isLivre?'b-completed':bl.statut==='EMIS'?'b-approved':'b-draft';
      return `<tr>
        <td><span class="of-num">${bl.bl_numero}</span></td>
        <td><span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--red)">${bl.of_numero}</span></td>
        <td>${bl.produit_nom||'—'}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${bl.quantite||'—'}</td>
        <td>${bl.destinataire||'—'}</td>
        <td><span class="badge ${badge}">${bl.statut}</span></td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted)">${bl.date_livraison_reelle||bl.date_livraison||'—'}</td>
        <td style="display:flex;gap:4px;flex-wrap:wrap">
          <button class="btn btn-ghost btn-sm" onclick="window.open('${API}/api/bl/${bl.id}/pdf','_blank')">🖨️ PDF</button>
          <button class="btn btn-ghost btn-sm" style="color:var(--accent)" onclick="openBLEdit(${bl.id},'${bl.bl_numero}','${(bl.destinataire||'').replace(/'/g,\"\\'\")}')">✎</button>`+
          ${!isLivre
            ? `<button class="btn btn-sm" style="background:var(--green);font-size:9px;padding:3px 8px"
                onclick="openLivrerBL(${bl.id},'${bl.bl_numero}','${(bl.destinataire||'').replace(/'/g,\"\\'\")}')">✓ Livrer</button>`
            : '<span style="font-size:10px;color:var(--green)">✓ Livré</span>'}
        </td>
      </tr>`;
    }).join('');
  } catch(e) { toast('Erreur BL: ' + e.message,'err'); }
}

function openLivrerModal(blId, blNum, dest) {
  $('bl-livrer-id').value     = blId;
  $('bl-livrer-num').textContent = blNum;
  $('bl-dest').value          = dest||'';
  $('bl-adresse').value       = 'Route Sidi Salem 2.5KM, Sfax';
  $('bl-date-liv').value      = new Date().toISOString().split('T')[0];
  $('bl-liv-notes').value     = '';
  openModal('m-bl-livrer');
}

async function confirmLivraison() {
  const id = $('bl-livrer-id').value;
  if (!$('bl-dest').value||!$('bl-date-liv').value) { toast('Destinataire et date requis','err'); return; }
  try {
    await api(`/api/bl/${id}/livrer`,'POST',{
      destinataire:   $('bl-dest').value,
      adresse:        $('bl-adresse').value,
      date_livraison: $('bl-date-liv').value,
      notes:          $('bl-liv-notes').value||null
    });
    toast('BL livré — OF clôturé ✓');
    closeModal('m-bl-livrer');
    window.open(`${API}/api/bl/${id}/pdf`,'_blank');
    loadBL();
  } catch(e) { toast(e.message,'err'); }
}


// ── BL EDIT ───────────────────────────────────────────────
async function openBLEdit(blId, blNum, dest, adresse, notes) {
  $('bl-edit-id').value = blId;
  $('bl-edit-num').textContent = blNum;
  $('bl-edit-dest').value = dest || '';
  $('bl-edit-adresse').value = adresse || '';
  $('bl-edit-notes').value = notes || '';
  // Load version history
  const versions = await api(`/api/bl/${blId}/versions`).catch(()=>[]);
  $('bl-version-history').innerHTML = !versions?.length
    ? '<div style="color:var(--muted);font-size:10px">Aucune modification précédente</div>'
    : versions.map(v => `
        <div style="padding:4px 0;border-bottom:1px solid var(--border);font-size:10px">
          <span style="font-family:'IBM Plex Mono',monospace;color:var(--muted)">v${v.version} · ${(v.created_at||'').slice(0,16)}</span>
          ${v.modifie_par ? `<span style="margin-left:.5rem;color:var(--muted)">${v.modifie_par}</span>` : ''}
          <div style="color:var(--text);margin-top:1px">${v.destinataire||''} — ${v.adresse||''}</div>
        </div>`).join('');
  openModal('m-bl-edit');
}

async function saveBLEdit() {
  const id = $('bl-edit-id').value;
  try {
    await api(`/api/bl/${id}`, 'PUT', {
      notes: $('bl-edit-notes').value || null
    });
    // Update details separately
    const params = new URLSearchParams({
      destinataire: $('bl-edit-dest').value,
      adresse: $('bl-edit-adresse').value,
      notes: $('bl-edit-notes').value || ''
    });
    await fetch(`${API}/api/bl/${id}/details?${params}`, {
      method:'PUT',
      headers:{'Authorization':'Bearer '+localStorage.getItem('token')}
    });
    toast('BL mis à jour ✓'); closeModal('m-bl-edit'); loadBL();
  } catch(e) { toast(e.message,'err'); }
}

// Smart livrer - check OF status first
async function openLivrerBL(blId, blNum, dest, ofStatut) {
  // Check if OF is completed
  if (ofStatut && ofStatut !== 'COMPLETED') {
    $('bl-notready-statut').textContent = `Statut OF actuel : ${ofStatut}`;
    openModal('m-bl-notready');
    return;
  }
  // OF might be completed, proceed with livrer modal
  openLivrerModal(blId, blNum, dest);
}