// ── cancel.js — SOFEM MES v6.0 — Commit 01 ───────────────
// ISO 9001 Global cancellation handler
// Replaces all hard DELETE operations with soft CANCEL
// Every cancellation requires a mandatory reason

'use strict';

// ── Global cancel modal ───────────────────────────────────

/**
 * Open the cancel modal for any document.
 *
 * @param {object} options
 *   id          - record database ID
 *   numero      - document number (OF-2026-0001, etc.)
 *   endpoint    - API endpoint to call (e.g. '/api/of/5/cancel')
 *   info        - HTML string with document details to show
 *   callback    - function name (string) to call after success
 */
function openCancelModal({ id, numero, endpoint, info = '', callback = '' }) {
  $('cancel-id').value        = id;
  $('cancel-endpoint').value  = endpoint;
  $('cancel-callback').value  = callback;
  $('cancel-doc-num').textContent = numero || `#${id}`;
  $('cancel-doc-info').innerHTML  = info || `Document ID: ${id}`;
  $('cancel-reason').value        = '';

  // Reset button state
  const btn = $('cancel-confirm-btn');
  btn.disabled = true;
  btn.style.opacity = '.5';
  btn.style.cursor  = 'not-allowed';
  $('cancel-reason-error').style.display = 'none';

  openModal('m-cancel');
  setTimeout(() => $('cancel-reason')?.focus(), 200);
}

function validateCancelReason() {
  const val = $('cancel-reason')?.value?.trim() || '';
  const btn = $('cancel-confirm-btn');
  const err = $('cancel-reason-error');

  if (val.length >= 5) {
    btn.disabled       = false;
    btn.style.opacity  = '1';
    btn.style.cursor   = 'pointer';
    if (err) err.style.display = 'none';
  } else {
    btn.disabled       = true;
    btn.style.opacity  = '.5';
    btn.style.cursor   = 'not-allowed';
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

    // Show cascade summary
    toast(res.message || 'Document annulé ✓');

    // Show warnings if any (BC already sent, goods received, etc.)
    if (res.warnings && res.warnings.length > 0) {
      setTimeout(() => {
        showCancelWarnings(res.warnings);
      }, 500);
    }

    // Suggest NC if production had started
    if (res.suggest_nc) {
      setTimeout(() => {
        if (confirm(
          `⚠ Des opérations avaient déjà démarré sur cet OF.\n\n` +
          `Voulez-vous créer une Non-Conformité pour documenter l'interruption de production ?\n\n` +
          `(Recommandé pour ISO 9001)`
        )) {
          navigate('nc');
          openModal('modal-nc');
        }
      }, 800);
    }

    // Refresh the page
    if (callback && window[callback]) window[callback]();
    logActivity('CANCEL', 'DOCUMENT', id, `Annulation confirmée: ${reason}`);

  } catch(e) {
    toast(e.message, 'err');
  }
}

// Show warnings in a readable modal/alert
function showCancelWarnings(warnings) {
  const msg = warnings.join('\n\n');
  alert('⚠ Actions manuelles requises:\n\n' + msg);
}

// ── OF cancellation ───────────────────────────────────────

function cancelOF(ofId, ofNumero, produitNom, statut) {
  // Cannot cancel a completed OF
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
        <span>📊 Statut actuel: <strong style="color:var(--accent)">${statut}</strong></span>
      </div>
      <div style="margin-top:.5rem;font-size:10px;color:var(--red)">
        ⚠ Les opérations liées et le BL associé seront également annulés.
      </div>`,
  });
}

// ── DA cancellation ───────────────────────────────────────

function cancelDA(daId, daNumero, description, statut) {
  if (['RECEIVED','ORDERED'].includes(statut)) {
    toast('Une DA déjà commandée/reçue ne peut pas être annulée', 'err');
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
      </div>`,
  });
}

// ── BC cancellation ───────────────────────────────────────

function cancelBC(bcId, bcNumero, fournisseur, statut) {
  if (['RECU','RECU_PARTIEL'].includes(statut)) {
    toast('Un BC déjà reçu ne peut pas être annulé', 'err');
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
      </div>`,
  });
}

// ── Soft deactivations (master data) ─────────────────────
// These don't need a reason but we ask for one anyway for audit quality

async function deactivateRecord(endpoint, entityName, code, callback) {
  const reason = prompt(
    `Raison de désactivation de "${code}" (optionnel):\n` +
    `(Laisser vide si aucune raison spécifique)`
  );
  if (reason === null) return; // cancelled by user

  try {
    await api(endpoint, 'DELETE', { reason: reason || 'Désactivation manuelle' });
    toast(`${entityName} désactivé ✓`);
    if (callback && window[callback]) window[callback]();
  } catch(e) {
    toast(e.message, 'err');
  }
}

// Convenience wrappers
function deactivateMateriau(id, code)       { deactivateRecord(`/api/materiaux/${id}`,    'Matériau',    code, 'loadMaterials');  }
function deactivateMachine(id, code)        { deactivateRecord(`/api/machines/${id}`,     'Machine',     code, 'loadMachines');   }
function deactivateClient(id, code)         { deactivateRecord(`/api/clients/${id}`,      'Client',      code, 'loadClients');    }
function deactivateFournisseur(id, code)    { deactivateRecord(`/api/fournisseurs/${id}`, 'Fournisseur', code, 'loadFournisseurs'); }
function deactivateOperateur(id, nomPrenom) { deactivateRecord(`/api/operateurs/${id}`,  'Opérateur', nomPrenom, 'loadOperators'); }

// ── Activity log helper ───────────────────────────────────

function logActivity(action, entityType, entityId, detail) {
  api('/api/notifications/activity', 'POST', {
    action, entity_type: entityType, entity_id: entityId, detail
  }).catch(() => {}); // silent fail
}
