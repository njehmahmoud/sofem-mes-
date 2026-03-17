// ── bl.js ────────────────────────────────────────────────
async function loadBL() {
  try {
    const bls = await api('/api/bl') || [];
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
          ${!isLivre
            ? `<button class="btn btn-sm" style="background:var(--green);font-size:9px;padding:3px 8px"
                onclick="openLivrerModal(${bl.id},'${bl.bl_numero}','${(bl.destinataire||'').replace(/'/g,"\\'")}')">✓ Livrer</button>`
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
