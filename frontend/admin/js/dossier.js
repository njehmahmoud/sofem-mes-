// ── dossier.js ────────────────────────────────────────────
// Complete OF document folder viewer — ISO 9001 traceability

// Load dossier view for OF
async function loadDossier(ofId) {
  try {
    const dos = await api(`/api/of/${ofId}/dossier`);
    if (!dos) { toast('Dossier non trouvé', 'err'); return; }

    // Header info
    $('dos-numero').textContent = dos.of?.numero || '—';
    $('dos-info-summary').innerHTML = `
      <span>Produit: <strong style="color:var(--text)">${dos.of?.produit_nom || '—'}</strong></span>
      <span>Qté: <strong style="color:var(--text)">${dos.of?.quantite || 0} ${dos.of?.produit_unite || 'pcs'}</strong></span>
      <span>Statut: <strong style="color:var(--accent)">${dos.of?.statut || '—'}</strong></span>
    `;

    // Render tabs
    renderDossierOps(dos.operations || []);
    renderDossierBOM(dos.bom || []);
    renderDossierAchats(dos.das || [], dos.bcs || [], dos.brs || [], dos.fas || []);
    renderDossierQualite(dos.qc_controlles || [], dos.non_conformites || []);
    renderDossierTrace(dos.activity_log || []);

    openModal('m-dossier');
  } catch (e) { toast('Erreur dossier: ' + e.message, 'err'); }
}

// Tab navigation
function dosTab(tab) {
  // Hide all panes
  document.querySelectorAll('.dos-pane').forEach(p => p.style.display = 'none');
  // Remove active from tabs
  document.querySelectorAll('.dos-tab').forEach(t => t.classList.remove('active'));
  // Show selected pane + mark tab active
  const paneId = `dos-pane-${tab}`;
  const pane = $(paneId);
  if (pane) {
    pane.style.display = 'block';
    event.target.classList.add('active');
  }
}

// Render operations + timeline
function renderDossierOps(ops) {
  if (!ops?.length) {
    $('dos-ops-tb').innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:1rem">— Aucune opération —</td></tr>`;
    return;
  }

  $('dos-ops-tb').innerHTML = ops.map(op => {
    const statusColor = {
      COMPLETED: 'var(--green)',
      IN_PROGRESS: 'var(--accent)',
      PENDING: 'var(--muted)'
    }[op.statut] || 'var(--text)';

    const durée = op.duree_prevue ? `${op.duree_prevue}m` : '—';

    return `<tr style="border-bottom:1px solid var(--border)">
      <td style="padding:4px"><strong>${op.operation_nom || '—'}</strong></td>
      <td style="padding:4px;color:var(--muted)">${op.operateur_nom || '—'}</td>
      <td style="text-align:center;padding:4px"><span style="color:${statusColor};font-weight:600">${op.statut || '—'}</span></td>
      <td style="text-align:center;padding:4px;font-family:'IBM Plex Mono',monospace">${durée}</td>
    </tr>`;
  }).join('');
}

// Render BOM with costs
function renderDossierBOM(bom) {
  if (!bom?.length) {
    $('dos-bom-tb').innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:1rem">— Aucun matériau —</td></tr>`;
    return;
  }

  $('dos-bom-tb').innerHTML = bom.map(ligne => {
    const qte = parseFloat(ligne.quantite || 0);
    const prix = parseFloat(ligne.prix_unitaire || 0);
    const total = qte * prix;

    return `<tr style="border-bottom:1px solid var(--border)">
      <td style="padding:4px"><strong>${ligne.materiau_nom || ligne.description || '—'}</strong></td>
      <td style="text-align:center;padding:4px;font-family:'IBM Plex Mono',monospace">${qte.toFixed(3)}</td>
      <td style="text-align:center;padding:4px">${ligne.unite || 'pcs'}</td>
      <td style="text-align:right;padding:4px;font-family:'IBM Plex Mono',monospace">${prix.toFixed(3)} DT</td>
      <td style="text-align:right;padding:4px;font-family:'IBM Plex Mono',monospace;font-weight:600;color:var(--accent)">${total.toFixed(3)} DT</td>
    </tr>`;
  }).join('');
}

// Render purchase chain (DA → BC → BR → FA)
function renderDossierAchats(das, bcs, brs, fas) {
  // DAs
  $('dos-das-list').innerHTML = das?.length
    ? das.map(da => `<div style="margin-bottom:.3rem">
        <div style="color:var(--accent);font-weight:600">${da.da_numero}</div>
        <div style="color:var(--muted);font-size:8px">${da.description?.slice(0, 30)}</div>
      </div>`).join('')
    : '<span style="color:var(--muted)">—</span>';

  // BCs
  $('dos-bcs-list').innerHTML = bcs?.length
    ? bcs.map(bc => `<div style="margin-bottom:.3rem">
        <div style="color:var(--accent);font-weight:600">${bc.bc_numero}</div>
        <div style="color:var(--muted);font-size:8px">${bc.fournisseur}</div>
      </div>`).join('')
    : '<span style="color:var(--muted)">—</span>';

  // BRs
  $('dos-brs-list').innerHTML = brs?.length
    ? brs.map(br => `<div style="margin-bottom:.3rem">
        <div style="color:var(--green);font-weight:600">${br.br_numero}</div>
        <div style="color:var(--muted);font-size:8px">${br.statut}</div>
      </div>`).join('')
    : '<span style="color:var(--muted)">—</span>';

  // FAs
  $('dos-fas-list').innerHTML = fas?.length
    ? fas.map(fa => `<div style="margin-bottom:.3rem">
        <div style="color:var(--accent);font-weight:600">${fa.fa_numero}</div>
        <div style="color:var(--muted);font-size:8px">${fa.montant_ht} DT HT</div>
      </div>`).join('')
    : '<span style="color:var(--muted)">—</span>';
}

// Render quality controls + non-conformities
function renderDossierQualite(qc, nc) {
  // QC table
  $('dos-qc-tb').innerHTML = qc?.length
    ? qc.map(item => {
        const total = parseFloat(item.quantite_controle || 0);
        const ok = parseFloat(item.quantite_conforme || 0);
        const pct = total > 0 ? ((ok / total) * 100).toFixed(1) : '—';
        const pctColor = pct === '—' ? 'var(--muted)' : pct >= 95 ? 'var(--green)' : pct >= 80 ? 'var(--accent)' : 'var(--red)';

        return `<tr style="border-bottom:1px solid var(--border)">
          <td style="padding:4px">${item.type_controle || '—'}</td>
          <td style="text-align:center;padding:4px;font-family:'IBM Plex Mono',monospace">${total}</td>
          <td style="text-align:center;padding:4px;font-family:'IBM Plex Mono',monospace;color:var(--green)">${ok}</td>
          <td style="text-align:center;padding:4px;font-family:'IBM Plex Mono',monospace">${total - ok}</td>
          <td style="text-align:center;padding:4px;font-family:'IBM Plex Mono',monospace;font-weight:600;color:${pctColor}">${pct}%</td>
        </tr>`;
      }).join('')
    : `<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:.75rem;font-size:9px">— Aucun contrôle —</td></tr>`;

  // NC list
  $('dos-nc-list').innerHTML = nc?.length
    ? nc.map(item => {
        const gravityColor = {
          MINEURE: 'var(--muted)',
          MAJEURE: 'var(--accent)',
          CRITIQUE: 'var(--red)'
        }[item.gravite] || 'var(--text)';

        return `<div style="background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:.5rem;margin-bottom:.5rem">
          <div style="display:flex;align-items:center;gap:.5rem">
            <span style="font-weight:600;color:${gravityColor}">${item.gravite || '—'}</span>
            <span style="color:var(--text);flex:1">${item.defaut}</span>
          </div>
          <div style="color:var(--muted);font-size:9px;margin-top:.25rem">${item.description || '—'}</div>
        </div>`;
      }).join('')
    : '<span style="color:var(--muted);font-size:9px">— Aucune non-conformité —</span>';
}

// Render activity log (ISO 9001 trace)
function renderDossierTrace(logs) {
  if (!logs?.length) {
    $('dos-trace-tb').innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:1rem;font-size:9px">— Aucune activité —</td></tr>`;
    return;
  }

  $('dos-trace-tb').innerHTML = logs.map((log, idx) => {
    const timestamp = log.created_at ? new Date(log.created_at).toLocaleString('fr-FR') : '—';
    const actionColor = {
      CREATE: 'var(--green)',
      UPDATE: 'var(--accent)',
      DELETE: 'var(--red)',
      CANCEL: 'var(--orange)'
    }[log.action] || 'var(--text)';

    return `<tr style="${idx % 2 ? `background:rgba(255,255,255,0.02)` : ''}border-bottom:1px solid var(--border)">
      <td style="padding:4px 6px;font-weight:600;color:${actionColor}">${log.action}</td>
      <td style="padding:4px 6px;font-size:8px;color:var(--muted)">${log.entity_type}</td>
      <td style="padding:4px 6px;color:var(--muted);max-width:150px;overflow:hidden;text-overflow:ellipsis">${log.entity_reference || '—'}</td>
      <td style="padding:4px 6px;color:var(--muted);font-size:8px">${log.user_id || 'Système'}</td>
      <td style="padding:4px 6px;font-size:8px;color:var(--muted)">${timestamp}</td>
    </tr>`;
  }).join('');
}

// Print dossier
function printDossier() {
  const content = $('m-dossier');
  if (!content) return;

  const printWindow = window.open('', '_blank');
  printWindow.document.write('<html><head><title>Dossier OF</title>');
  printWindow.document.write('<style>body { font-family: Arial, sans-serif; font-size: 11px; margin: 1cm; }');
  printWindow.document.write('table { width: 100%; border-collapse: collapse; margin: 1rem 0; }');
  printWindow.document.write('th, td { border: 1px solid #ddd; padding: 4px; text-align: left; }');
  printWindow.document.write('th { background: #f5f5f5; font-weight: bold; }');
  printWindow.document.write('.page-break { page-break-after: always; }');
  printWindow.document.write('</style></head><body>');
  printWindow.document.write(content.innerHTML);
  printWindow.document.write('</body></html>');
  printWindow.document.close();
  printWindow.print();
}

// Utility: pdfUrl helper (if not defined in core.js)
function pdfUrl(path) {
  return window.location.origin + path;
}
