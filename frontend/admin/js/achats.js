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
    const demEl = $('da-demandeur');
    if (demEl && ops) {
      demEl.innerHTML = '<option value="">— Aucun —</option>' +
        ops.map(o => `<option value="${o.id}">${o.prenom} ${o.nom}</option>`).join('');
    }

    $('da-tb').innerHTML = (das || []).length === 0 ? empty(10) : das.map(da => {
      const badge = {
        PENDING: 'b-draft',
        APPROVED: 'b-approved',
        REJECTED: 'b-cancelled',
        ORDERED: 'b-inprogress',
        RECEIVED: 'b-completed'
      }[da.statut] || 'b-draft';

      const statutLabel = {
        PENDING: 'En attente',
        APPROVED: 'Approuvée',
        REJECTED: 'Rejetée',
        ORDERED: 'Commandée',
        RECEIVED: 'Reçue'
      }[da.statut] || da.statut;

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
            <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--muted)">${bc.br_numero || '—'}</span>
            ${brBadge}
          </div>
        </div>`;
      }

      return `<tr>
        <td><span class="of-num">${da.da_numero}</span></td>
        <td style="font-size:11px;max-width:160px">${da.description}</td>
        <td style="font-size:11px">${da.materiau_nom || '—'}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${da.quantite} ${da.unite}</td>
        <td><span class="badge ${da.urgence === 'URGENT' ? 'b-urgent' : 'b-normal'}">${da.urgence}</span></td>
        <td><span class="badge ${badge}">${statutLabel}</span></td>
        <td style="font-size:10px;color:var(--muted)">${da.of_numero || '—'}</td>
        <td>${bcBrCell}</td>
        <td style="display:flex;gap:3px;flex-wrap:wrap">
          <button class="btn btn-ghost btn-sm" onclick="window.open(pdfUrl('/api/achats/da/${da.id}/ba'),'_blank')" title="BA PDF">📋 BA</button>
          ${da.statut === 'PENDING'
            ? `<button class="fbtn" style="color:var(--green)" onclick="updateDA(${da.id},'APPROVED')" title="Approuver">✓</button>
               <button class="fbtn" style="color:var(--red)" onclick="updateDA(${da.id},'REJECTED')" title="Rejeter">✕</button>`
            : ''}
          ${!['CANCELLED', 'RECEIVED', 'ORDERED'].includes(da.statut)
            ? `<button class="fbtn" style="color:var(--accent)" onclick="cancelDA(${da.id},'${da.da_numero}','${(da.description || '').replace(/'/g, "\\'")}','${da.statut}')" title="Annuler">✕ Annuler</button>`
            : ''}
        </td>
      </tr>`;
    }).join('');

  } catch (e) { toast('Erreur DA: ' + e.message, 'err'); }
}

async function saveDA() {
  if (!$('da-desc')?.value) { toast('Description requise', 'err'); return; }
  try {
    const res = await api('/api/achats/da', 'POST', {
      materiau_id:  $('da-mat')?.value       ? parseInt($('da-mat').value)       : null,
      of_id:        $('da-of')?.value         ? parseInt($('da-of').value)         : null,
      description:  $('da-desc').value,
      objet:        $('da-objet')?.value      || null,
      quantite:     parseFloat($('da-qte')?.value) || 1,
      unite:        $('da-unite')?.value      || 'pcs',
      urgence:      $('da-urgence')?.value    || 'NORMAL',
      notes:        $('da-notes')?.value      || null,
      demandeur_id: $('da-demandeur')?.value  ? parseInt($('da-demandeur').value) : null
    });
    toast(`${res.da_numero} créée ✓`); closeModal('m-da'); loadDA();
  } catch (e) { toast(e.message, 'err'); }
}

async function updateDA(id, statut) {
  try {
    const res = await api(`/api/achats/da/${id}`, 'PUT', { statut });
    if (statut === 'APPROVED' && res.bc_numero) {
      toast(`DA approuvée ✓ — ${res.bc_numero} + ${res.br_numero} créés`);
    } else {
      toast(`DA → ${statut} ✓`);
    }
    loadDA(); loadBC(); loadBR();
  } catch (e) { toast(e.message, 'err'); }
}

async function cancelDA(id, numero, description, statut) {
  const reason = prompt(`Annuler DA ${numero}?\n\nMotif d'annulation (obligatoire):`);
  if (!reason || reason.trim().length < 5) {
    toast('Motif requis (min. 5 caractères)', 'err');
    return;
  }

  try {
    const res = await api(`/api/achats/da/${id}/cancel`, 'PUT', { reason });
    toast(`${numero} annulée ✓`);
    loadDA(); loadBC(); loadBR();
  } catch (e) { toast(e.message, 'err'); }
}

async function confirmerReception(brId, brNumero) {
  try {
    const brs = await api('/api/achats/br');
    const br  = (brs || []).find(b => b.id === brId);
    if (!br) { toast('BR introuvable', 'err'); return; }

    const bcs = await api('/api/achats/bc');
    const bc  = (bcs || []).find(b => b.id === br.bc_id);
    const ligne = bc?.lignes?.[0];

    $('br-confirm-id').value        = brId;
    $('br-confirm-num').textContent = brNumero;

    const mat   = ligne?.materiau_nom || ligne?.description || '—';
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
    $('br-confirm-qte-recue').value = qteCmd;
    $('br-confirm-prix').value      = parseFloat(ligne?.prix_unitaire || 0);
    $('br-confirm-notes').value     = '';
    $('br-confirm-status').style.display = 'none';
    updateBRTotal();

    openModal('m-br-confirm');
  } catch (e) { toast(e.message, 'err'); }
}

function updateBRTotal() {
  const qte   = parseFloat($('br-confirm-qte-recue')?.value || 0);
  const prix  = parseFloat($('br-confirm-prix')?.value || 0);
  const total = Math.round(qte * prix * 1000) / 1000;
  const totalEl = $('br-confirm-total');
  if (totalEl) totalEl.value = total;

  const qteCmd  = parseFloat($('br-confirm-qte-cmd')?.value || 0);
  const statusEl = $('br-confirm-status');
  if (statusEl && qteCmd > 0) {
    if (qte <= 0) {
      statusEl.style.display    = 'block';
      statusEl.style.background = 'rgba(212,43,43,0.1)';
      statusEl.style.border     = '1px solid var(--red)';
      statusEl.style.color      = 'var(--red)';
      statusEl.textContent      = '⚠ Quantité reçue doit être > 0';
    } else if (qte < qteCmd) {
      statusEl.style.display    = 'block';
      statusEl.style.background = 'rgba(245,158,11,0.1)';
      statusEl.style.border     = '1px solid #f59e0b';
      statusEl.style.color      = '#f59e0b';
      statusEl.textContent      = `⚠ Réception partielle — ${qte} / ${qteCmd} reçus`;
    } else {
      statusEl.style.display    = 'block';
      statusEl.style.background = 'rgba(22,163,74,0.1)';
      statusEl.style.border     = '1px solid var(--green)';
      statusEl.style.color      = 'var(--green)';
      statusEl.textContent      = `✓ Réception complète — ${qte} sur ${qteCmd} commandés`;
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
    // Update quantite_recue
    await api(`/api/achats/br/${brId}/quantite?quantite_recue=${qteRecue}`, 'PUT');

    // Note: Price will be synchronized on confirmer via br_lignes.prix_unitaire → bc_lignes.prix_unitaire
    // The price is already stored in br_lignes from BR creation

    const res = await api(`/api/achats/br/${brId}/confirmer`, 'PUT');
    toast(res.message + ' ✓');
    closeModal('m-br-confirm');
    loadDA(); loadBR(); loadBC();
    if (window.pageLoaders?.dashboard) window.pageLoaders.dashboard();
  } catch (e) { toast(e.message, 'err'); }
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
        fourns.map(f => `<option value="${f.nom}">${f.nom}${f.ville ? ' · ' + f.ville : ''}</option>`).join('');
    }

    // Populate DA — only APPROVED
    if (das && $('bc-da')) {
      $('bc-da').innerHTML = '<option value="">— DA liée (optionnel) —</option>' +
        das.filter(d => d.statut === 'APPROVED')
           .map(d => `<option value="${d.id}">${d.da_numero} — ${d.description.slice(0, 30)} (${d.quantite} ${d.unite})</option>`)
           .join('');
    }

    $('bc-tb').innerHTML = (bcs || []).length === 0 ? empty(7) : bcs.map(bc => {
      const badge = {
        DRAFT: 'b-draft',
        ENVOYE: 'b-approved',
        RECU: 'b-completed',
        ANNULE: 'b-cancelled',
        RECU_PARTIEL: 'b-inprogress'
      }[bc.statut] || 'b-draft';

      return `<tr>
        <td><span class="of-num">${bc.bc_numero}</span></td>
        <td>${bc.fournisseur}</td>
        <td style="font-size:10px;color:var(--muted)">${bc.da_numero || '—'}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${bc.montant_ht || 0} TND HT</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${bc.montant_ttc || 0} TND TTC</td>
        <td><span class="badge ${badge}">${bc.statut}</span></td>
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

  } catch (e) { toast('Erreur BC: ' + e.message, 'err'); }
}

// BC line management
function addBCLine() {
  const container = $('bc-lines');
  if (!container) return;
  const lineId = Date.now();
  const html = `
    <div class="bc-line-row" id="bcline-${lineId}" style="display:flex;gap:.5rem;margin-bottom:.5rem;align-items:flex-start;background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:.5rem">
      <div style="flex:1">
        <select class="bc-materiau-sel" data-lineid="${lineId}" style="width:100%;background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:4px 6px;font-size:11px;color:var(--text)">
          <option value="">— Sélectionner matériau —</option>
        </select>
      </div>
      <div style="width:80px">
        <input type="text" class="bc-desc" placeholder="Description" style="width:100%;background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:4px 6px;font-size:11px;color:var(--text)">
      </div>
      <div style="width:70px">
        <input type="number" class="bc-qty" placeholder="Qté" min="0.001" step="0.001" value="1" style="width:100%;background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:4px 6px;font-size:11px;color:var(--text)">
      </div>
      <div style="width:60px">
        <input type="text" class="bc-unite" placeholder="Unité" value="pcs" style="width:100%;background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:4px 6px;font-size:11px;color:var(--text)">
      </div>
      <button class="fbtn" style="color:var(--red);min-width:30px" onclick="removeBCLine('bcline-${lineId}')">✕</button>
    </div>`;
  container.insertAdjacentHTML('beforeend', html);
  
  // Load matériaux into the new select
  api('/api/materiaux').then(mats => {
    const sel = document.querySelector(`#bcline-${lineId} .bc-materiau-sel`);
    if (sel && mats) {
      sel.innerHTML = '<option value="">— Sélectionner matériau —</option>' +
        mats.map(m => `<option value="${m.id}|${m.nom}|${m.unite}">${m.nom} (${m.unite})</option>`).join('');
      sel.addEventListener('change', function() {
        if (this.value) {
          const [id, nom, unite] = this.value.split('|');
          const row = document.getElementById(`bcline-${lineId}`);
          if (!row.querySelector('.bc-desc').value) {
            row.querySelector('.bc-desc').value = nom;
          }
          row.querySelector('.bc-unite').value = unite;
        }
      });
    }
  });
}

function removeBCLine(lineId) {
  const el = document.getElementById(lineId);
  if (el) el.remove();
}

async function saveBC() {
  const four = $('bc-four')?.value;
  if (!four) { toast('Fournisseur requis', 'err'); return; }

  // Collect lines
  const lines = [];
  document.querySelectorAll('#bc-lines .bc-line-row').forEach(row => {
    const matSel = row.querySelector('.bc-materiau-sel').value;
    const desc = row.querySelector('.bc-desc').value;
    const qty = parseFloat(row.querySelector('.bc-qty').value);
    const unite = row.querySelector('.bc-unite').value;
    
    if (!matSel && !desc) return; // Skip empty lines
    const [matId] = matSel ? matSel.split('|') : [null];
    
    lines.push({
      materiau_id: matId ? parseInt(matId) : null,
      description: desc || null,
      quantite: qty || 0,
      unite: unite || 'pcs'
    });
  });

  if (lines.length === 0) { toast('Ajouter au moins une ligne', 'err'); return; }

  try {
    const res = await api('/api/achats/bc', 'POST', {
      fournisseur: four,
      da_id:       $('bc-da')?.value   ? parseInt($('bc-da').value)   : null,
      notes:       $('bc-notes')?.value || null,
      lignes:      lines
    });
    toast(`${res.bc_numero} créé ✓`); closeModal('m-bc'); loadBC();
  } catch (e) { toast(e.message, 'err'); }
}

async function updateBC(id, statut) {
  if (!statut) return;
  try {
    await api(`/api/achats/bc/${id}`, 'PUT', { statut });
    toast(`BC → ${statut} ✓`);
    loadBC(); loadDA(); loadBR();
  } catch (e) { toast(e.message, 'err'); }
}

// ── BR ────────────────────────────────────────────────────
async function loadBR() {
  try {
    const brs = await api('/api/achats/br');

    $('br-tb').innerHTML = (brs || []).length === 0 ? empty(7) : brs.map(br => {
      const badge = {
        EN_ATTENTE: 'b-draft',
        PARTIEL:    'b-inprogress',
        COMPLET:    'b-completed',
        ANNULE:     'b-cancelled'
      }[br.statut] || 'b-draft';

      const statutLabel = {
        EN_ATTENTE: 'En attente',
        PARTIEL:    'Partiel',
        COMPLET:    'Complet',
        ANNULE:     'Annulé'
      }[br.statut] || br.statut;

      return `<tr>
        <td><span class="of-num">${br.br_numero}</span></td>
        <td style="font-size:10px;color:var(--accent)">${br.bc_numero || '—'}</td>
        <td>${br.fournisseur || '—'}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${br.quantite_recue || 0} / ${br.quantite_commandee || 0} ${br.unite || ''}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${br.montant_total || 0} TND</td>
        <td><span class="badge ${badge}">${statutLabel}</span></td>
        <td style="display:flex;gap:3px">
          ${br.statut !== 'COMPLET' && br.statut !== 'ANNULE'
            ? `<button class="btn btn-ghost btn-sm" onclick="confirmerReception(${br.id},'${br.br_numero}')" title="Confirmer réception">✓ Réceptionner</button>`
            : ''}
          <button class="btn btn-ghost btn-sm" onclick="window.open(pdfUrl('/api/achats/br/${br.id}/pdf'),'_blank')" title="Imprimer BR">🖨️</button>
        </td>
      </tr>`;
    }).join('');

  } catch (e) { toast('Erreur BR: ' + e.message, 'err'); }
}

function loadBCLines() {
  const bcId = parseInt($('br-bc')?.value);
  if (!bcId) {
    $('br-lines').innerHTML = '';
    return;
  }

  api('/api/achats/bc').then(bcs => {
    const bc = (bcs || []).find(b => b.id === bcId);
    if (!bc || !bc.lignes) {
      $('br-lines').innerHTML = '<span style="color:var(--muted);font-size:11px">— Aucune ligne disponible —</span>';
      return;
    }

    const html = `<div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--muted);margin-bottom:.5rem;text-transform:uppercase;letter-spacing:1px">Lignes du BC — ${bc.bc_numero}</div>
      <div style="background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:.5rem">
        ${bc.lignes.map((ligne, idx) => `
          <div class="br-line-item" data-ligne-idx="${idx}" style="display:flex;gap:.5rem;margin-bottom:.5rem;align-items:flex-start;background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:.5rem">
            <div style="flex:1">
              <div style="font-size:10px;color:var(--muted);margin-bottom:2px">Matériau / Description</div>
              <div style="font-size:11px;color:var(--text);font-weight:600">${ligne.materiau_nom || ligne.description || '—'}</div>
            </div>
            <div style="width:80px">
              <div style="font-size:10px;color:var(--muted);margin-bottom:2px">Qté cmd</div>
              <input type="number" class="br-qte-cmd" value="${ligne.quantite}" disabled style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:4px 6px;font-size:10px;color:var(--text);font-family:'IBM Plex Mono',monospace;opacity:.6">
            </div>
            <div style="width:90px">
              <div style="font-size:10px;color:var(--muted);margin-bottom:2px">Qté reçue</div>
              <input type="number" class="br-qte-recue" value="${ligne.quantite}" min="0" step="0.001" style="width:100%;background:var(--bg2);border:1px solid var(--green);border-radius:4px;padding:4px 6px;font-size:10px;color:var(--text);font-family:'IBM Plex Mono',monospace;font-weight:600">
            </div>
            <div style="width:100px">
              <div style="font-size:10px;color:var(--muted);margin-bottom:2px">Prix unit. HT</div>
              <input type="number" class="br-prix" min="0" step="0.001" value="${ligne.prix_unitaire || 0}" style="width:100%;background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:4px 6px;font-size:10px;color:var(--text);font-family:'IBM Plex Mono',monospace">
            </div>
            <div style="width:80px">
              <div style="font-size:10px;color:var(--muted);margin-bottom:2px">Total HT</div>
              <input type="number" disabled value="${(parseFloat(ligne.quantite || 0) * (parseFloat(ligne.prix_unitaire || 0))).toFixed(3)}" style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:4px 6px;font-size:10px;color:var(--accent);font-family:'IBM Plex Mono',monospace;opacity:.7;font-weight:600">
            </div>
          </div>
        `).join('')}
      </div>`;
    $('br-lines').innerHTML = html;
  });
}

async function saveBR() {
  const bcId = parseInt($('br-bc')?.value);
  const date = $('br-date')?.value;
  const statut = $('br-statut')?.value || 'COMPLET';
  const notes = $('br-notes')?.value || null;

  if (!bcId || !date) { toast('BC et Date requis', 'err'); return; }

  // Collect line items with prices
  const lignes = [];
  document.querySelectorAll('#br-lines .br-line-item').forEach(item => {
    const qteRecue = parseFloat(item.querySelector('.br-qte-recue').value);
    const prix = parseFloat(item.querySelector('.br-prix').value || 0);
    lignes.push({
      quantite_recue: qteRecue || 0,
      prix_unitaire: prix || 0
    });
  });

  try {
    const res = await api('/api/achats/br', 'POST', {
      bc_id:  bcId,
      date_reception: date,
      statut: statut,
      notes:  notes,
      lignes: lignes
    });
    toast(`${res.br_numero} créé ✓`); closeModal('m-br'); loadBR();
  } catch (e) { toast(e.message, 'err'); }
}

async function loadFA() {
  try {
    const [fas, bcs] = await Promise.all([
      api('/api/achats/fa'), api('/api/achats/bc')
    ]);

    // Populate BC select  
    if (bcs && $('fa-bc')) {
      $('fa-bc').innerHTML = '<option value="">— Sélectionner BC —</option>' +
        bcs.map(b => `<option value="${b.id}">${b.bc_numero} — ${b.fournisseur} (${b.statut})</option>`).join('');
    }

    $('fa-tb').innerHTML = (fas || []).length === 0 ? empty(5) : fas.map(fa => {
      return `<tr>
        <td><span class="of-num">${fa.fa_numero}</span></td>
        <td>${fa.fournisseur || '—'}</td>
        <td style="font-size:10px;color:var(--accent)">${fa.bc_numero}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${fa.montant_ht} TND HT</td>
        <td style="font-size:9px;color:var(--muted)">${fa.notes || '—'}</td>
        <td>
          <button class="btn btn-ghost btn-sm" onclick="window.open(pdfUrl('/api/achats/fa/${fa.id}/pdf'),'_blank')">🖨️ PDF</button>
        </td>
      </tr>`;
    }).join('');
  } catch (e) { toast('Erreur FA: ' + e.message, 'err'); }
}

async function saveFA() {
  const bcId = parseInt($('fa-bc')?.value);
  const four = $('fa-four')?.value;
  const date = $('fa-date')?.value;
  const notes = $('fa-notes')?.value || null;

  if (!bcId || !four || !date) { toast('BC, Fournisseur et Date requis', 'err'); return; }

  try {
    const res = await api('/api/achats/fa', 'POST', {
      bc_id: bcId,
      fournisseur: four,
      date_facture: date,
      notes: notes
    });
    toast(`${res.fa_numero} créé ✓`); closeModal('m-fa'); loadFA();
  } catch (e) { toast(e.message, 'err'); }
}