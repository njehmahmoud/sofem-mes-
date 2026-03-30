// ── cancel.js — SOFEM MES v6.0 — Commit 01 ───────────────
// ISO 9001 Global cancellation handler
// Replaces all hard DELETE operations with soft CANCEL
// Every cancellation requires a mandatory reason
'use strict';

// ── Global cancel modal ───────────────────────────────────

function openCancelModal({ id, numero, endpoint, info = '', callback = '' }) {
  $('cancel-id').value            = id;
  $('cancel-endpoint').value      = endpoint;
  $('cancel-callback').value      = callback;
  $('cancel-doc-num').textContent = numero || `#${id}`;
  $('cancel-doc-info').innerHTML  = info || `Document ID: ${id}`;
  $('cancel-reason').value        = '';

  const btn = $('cancel-confirm-btn');
  btn.disabled       = true;
  btn.style.opacity  = '.5';
  btn.style.cursor   = 'not-allowed';
  $('cancel-reason-error').style.display = 'none';

  openModal('m-cancel');
  setTimeout(() => $('cancel-reason')?.focus(), 200);
}

function validateCancelReason() {
  const val = $('cancel-reason')?.value?.trim() || '';
  const btn = $('cancel-confirm-btn');
  const err = $('cancel-reason-error');

  if (val.length >= 5) {
    btn.disabled      = false;
    btn.style.opacity = '1';
    btn.style.cursor  = 'pointer';
    if (err) err.style.display = 'none';
  } else {
    btn.disabled      = true;
    btn.style.opacity = '.5';
    btn.style.cursor  = 'not-allowed';
    if (err && val.length > 0) err.style.display = 'block';
  }
}

async function confirmCancel() {
  const id       = $('cancel-id').value;
  const endpoint = $('cancel-endpoint').value;
  const callback = $('cancel-callback').value;
  const reason   = $('cancel-reason')?.value?.trim();

  if (!reason || reason.length < 5) {
    toast('La raison est obligatoire (min. 5 caractères)', 'err');
    return;
  }
  if (!endpoint) {
    toast('Endpoint manquant', 'err');
    return;
  }

  try {
    const res = await api(endpoint, 'PUT', { reason });
    closeModal('m-cancel');

    // Show cascade summary message
    toast(res.message || 'Document annulé ✓');

    // Show warnings if any (BC already sent, goods received, etc.)
    if (res.warnings && res.warnings.length > 0) {
      setTimeout(() => showCancelWarnings(res.warnings), 600);
    }

    // Suggest NC if production had started on the OF
    if (res.suggest_nc) {
      setTimeout(() => {
        if (confirm(
          '⚠ Des opérations avaient déjà démarré sur cet OF.\n\n' +
          'Voulez-vous créer une Non-Conformité pour documenter ' +
          'l\'interruption de production ?\n\n' +
          '(Recommandé pour ISO 9001 Clause 10.2)'
        )) {
          navigate('nc');
          setTimeout(() => openModal('modal-nc'), 300);
        }
      }, 800);
    }

    // Refresh the calling page
    if (callback && window[callback]) window[callback]();

    // Log to activity trail
    logActivity('CANCEL', 'DOCUMENT', id, reason);

  } catch(e) {
    toast(e.message, 'err');
  }
}

// Show cascade warnings in a readable alert
function showCancelWarnings(warnings) {
  const msg = '⚠ Actions manuelles requises:\n\n' + warnings.join('\n\n');
  alert(msg);
}

// ── OF cancellation ───────────────────────────────────────

function cancelOF(ofId, ofNumero, produitNom, statut) {
  if (statut === 'COMPLETED') {
    toast('Un OF terminé ne peut pas être annulé', 'err');
    return;
  }
  openCancelModal({
    id:       ofId,
    numero:   ofNumero,
    endpoint: `/api/of/${ofId}/cancel`,
    callback: 'loadOrders',
    info: `
      <div style="display:flex;gap:1.5rem;flex-wrap:wrap">
        <span>📋 <strong style="color:var(--text)">${ofNumero}</strong></span>
        <span>📦 Produit: <strong style="color:var(--text)">${produitNom}</strong></span>
        <span>📊 Statut: <strong style="color:var(--accent)">${statut}</strong></span>
      </div>
      <div style="margin-top:.5rem;font-size:10px;color:var(--red)">
        ⚠ BL, DAs, BCs liés et stock seront également traités automatiquement.
      </div>`,
  });
}

// ── DA cancellation ───────────────────────────────────────

function cancelDA(daId, daNumero, description, statut) {
  if (statut === 'RECEIVED') {
    toast('Une DA déjà reçue ne peut pas être annulée', 'err');
    return;
  }
  openCancelModal({
    id:       daId,
    numero:   daNumero,
    endpoint: `/api/achats/da/${daId}/cancel`,
    callback: 'loadDA',
    info: `
      <div style="display:flex;gap:1.5rem;flex-wrap:wrap">
        <span>📝 <strong style="color:var(--text)">${daNumero}</strong></span>
        <span>📌 ${description}</span>
        <span>📊 Statut: <strong style="color:var(--accent)">${statut}</strong></span>
      </div>
      ${statut === 'ORDERED'
        ? `<div style="margin-top:.5rem;font-size:10px;color:var(--accent)">
             ⚠ Le BC associé sera également annulé.
           </div>`
        : ''}`,
  });
}

// ── BC cancellation ───────────────────────────────────────

function cancelBC(bcId, bcNumero, fournisseur, statut) {
  if (statut === 'RECU') {
    toast('Un BC entièrement reçu ne peut pas être annulé', 'err');
    return;
  }
  openCancelModal({
    id:       bcId,
    numero:   bcNumero,
    endpoint: `/api/achats/bc/${bcId}/cancel`,
    callback: 'loadBC',
    info: `
      <div style="display:flex;gap:1.5rem;flex-wrap:wrap">
        <span>🛒 <strong style="color:var(--text)">${bcNumero}</strong></span>
        <span>🤝 Fournisseur: <strong style="color:var(--text)">${fournisseur}</strong></span>
        <span>📊 Statut: <strong style="color:var(--accent)">${statut}</strong></span>
      </div>
      <div style="margin-top:.5rem;font-size:10px;color:var(--accent)">
        ⚠ La DA liée repassera en statut APPROUVÉE pour retraitement.
      </div>`,
  });
}

// ── BL cancellation ───────────────────────────────────────

function cancelBL(blId, blNumero, ofNumero, statut) {
  if (statut === 'LIVRE') {
    toast('Un BL déjà livré ne peut pas être annulé', 'err');
    return;
  }
  openCancelModal({
    id:       blId,
    numero:   blNumero,
    endpoint: `/api/bl/${blId}/cancel`,
    callback: 'loadBL',
    info: `
      <div style="display:flex;gap:1.5rem;flex-wrap:wrap">
        <span>🚚 <strong style="color:var(--text)">${blNumero}</strong></span>
        <span>📋 OF lié: <strong style="color:var(--text)">${ofNumero}</strong></span>
        <span>📊 Statut: <strong style="color:var(--accent)">${statut}</strong></span>
      </div>`,
  });
}

// ── Maintenance order cancellation ────────────────────────

function cancelMaintenance(omId, omNumero, titre, statut) {
  if (statut === 'TERMINE') {
    toast('Un ordre de maintenance terminé ne peut pas être annulé', 'err');
    return;
  }
  openCancelModal({
    id:       omId,
    numero:   omNumero,
    endpoint: `/api/maintenance/${omId}/cancel`,
    callback: 'loadMaintenance',
    info: `
      <div style="display:flex;gap:1.5rem;flex-wrap:wrap">
        <span>🔧 <strong style="color:var(--text)">${omNumero}</strong></span>
        <span>📌 ${titre}</span>
        <span>📊 Statut: <strong style="color:var(--accent)">${statut}</strong></span>
      </div>
      ${statut === 'EN_COURS'
        ? `<div style="margin-top:.5rem;font-size:10px;color:var(--accent)">
             ⚠ La machine sera remise en statut OPÉRATIONNELLE.
           </div>`
        : ''}`,
  });
}

// ── Soft deactivations (master data) ─────────────────────

async function deactivateRecord(endpoint, entityName, code, callback) {
  const reason = prompt(
    `Raison de désactivation de "${code}" (optionnel):`
  );
  if (reason === null) return; // user cancelled

  try {
    await api(endpoint, 'DELETE', { reason: reason || 'Désactivation manuelle' });
    toast(`${entityName} désactivé ✓`);
    if (callback && window[callback]) window[callback]();
  } catch(e) {
    toast(e.message, 'err');
  }
}

// Convenience wrappers for master data deactivation
function deactivateMateriau(id, code) {
  deactivateRecord(`/api/materiaux/${id}`, 'Matériau', code, 'loadMaterials');
}
function deactivateMachine(id, code) {
  deactivateRecord(`/api/machines/${id}`, 'Machine', code, 'loadMachines');
}
function deactivateClient(id, code) {
  deactivateRecord(`/api/clients/${id}`, 'Client', code, 'loadClients');
}
function deactivateFournisseur(id, code) {
  deactivateRecord(`/api/fournisseurs/${id}`, 'Fournisseur', code, 'loadFournisseurs');
}
function deactivateOperateur(id, nomPrenom) {
  deactivateRecord(`/api/operateurs/${id}`, 'Opérateur', nomPrenom, 'loadOperators');
}

// ── Activity log helper ───────────────────────────────────

function logActivity(action, entityType, entityId, detail) {
  api('/api/notifications/activity', 'POST', {
    action,
    entity_type: entityType,
    entity_id:   entityId,
    detail
  }).catch(() => {}); // silent fail — never break the main flow
}