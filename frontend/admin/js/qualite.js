// ── qualite.js v6 ────────────────────────────────────────

async function loadQualite() {
  try {
    const [cqs, ofs, ops] = await Promise.all([
      api('/api/qualite/controles'),
      api('/api/of?limit=200'),
      api('/api/operateurs')
    ]);

    // KPIs
    const total   = (cqs||[]).length;
    const conf    = (cqs||[]).filter(c => c.statut === 'CONFORME').length;
    const nonConf = (cqs||[]).filter(c => c.statut === 'NON_CONFORME').length;
    const taux    = total > 0 ? Math.round(conf / total * 100) : 0;

    $('qualite-kpis').innerHTML = `
      <div class="kpi"><div class="kpi-lbl">Total Contrôles</div><div class="kpi-val">${total}</div></div>
      <div class="kpi"><div class="kpi-lbl">Taux Conformité</div><div class="kpi-val g">${taux}%</div></div>
      <div class="kpi"><div class="kpi-lbl">Non Conformes</div><div class="kpi-val r">${nonConf}</div></div>
      <div class="kpi"><div class="kpi-lbl">En Attente</div><div class="kpi-val o">${total - conf - nonConf}</div></div>`;

    // Populate OF select — only IN_PROGRESS and COMPLETED
    const cqOf = $('cq-of');
    if (cqOf && ofs) {
      const active = (ofs||[]).filter(o => ['IN_PROGRESS','COMPLETED'].includes(o.statut));
      cqOf.innerHTML = '<option value="">— Aucun —</option>' +
        active.map(o => `<option value="${o.id}">${o.numero} · ${o.produit_nom}</option>`).join('');
    }
    // Populate operators
    const cqOp = $('cq-op');
    if (cqOp && ops) {
      cqOp.innerHTML = '<option value="">— Aucun —</option>' +
        (ops||[]).map(o => `<option value="${o.id}">${o.prenom} ${o.nom} (${o.specialite||''})</option>`).join('');
    }
    // Default date = today
    if ($('cq-date') && !$('cq-date').value) {
      $('cq-date').value = new Date().toISOString().split('T')[0];
    }

    // Table
    const sMap = { CONFORME:'b-completed', NON_CONFORME:'b-urgent', EN_ATTENTE:'b-draft', EN_COURS:'b-inprogress' };
    $('qualite-table').innerHTML = (cqs||[]).length === 0 ? empty(10) :
      `<table><thead><tr>
        <th>N° CQ</th><th>OF</th><th>Produit</th><th>Type</th><th>Contrôleur</th>
        <th>Date</th><th>Contrôlé</th><th>✓ Conf.</th><th>✗ Rebut</th><th>Résultat</th><th></th>
      </tr></thead><tbody>
      ${(cqs||[]).map(c => {
        const taux = c.quantite_controlée > 0
          ? Math.round(c.quantite_conforme / c.quantite_controlée * 100) : 0;
        return `<tr>
          <td style="font-family:'IBM Plex Mono',monospace;font-size:9px">${c.cq_numero}</td>
          <td><span class="of-num" style="font-size:9px">${c.of_numero||'—'}</span></td>
          <td style="font-size:11px;color:var(--muted)">${c.produit_nom||'—'}</td>
          <td style="font-size:10px;color:var(--muted)">${c.type_controle}</td>
          <td style="font-size:11px">${c.operateur_nom||'—'}</td>
          <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${(c.date_controle||'').slice(0,10)}</td>
          <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;text-align:center">${c.quantite_controlée||0}</td>
          <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--green);text-align:center">${c.quantite_conforme||0}</td>
          <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--red);text-align:center">${c.quantite_rebut||0}</td>
          <td>
            <span class="badge ${sMap[c.statut]||'b-draft'}">${c.statut.replace('_',' ')}</span>
            <span style="font-size:9px;font-family:'IBM Plex Mono',monospace;color:var(--muted);margin-left:4px">${taux}%</span>
          </td>
          <td style="display:flex;gap:3px">
            <select class="fbtn" onchange="updateCQStatus(${c.id},this.value);this.value=''"
              style="font-size:9px;padding:2px 4px;background:var(--bg3);border:1px solid var(--border);border-radius:4px;color:var(--text)">
              <option value="">▾</option>
              <option value="CONFORME">✓ Conforme</option>
              <option value="NON_CONFORME">✗ Non Conforme</option>
              <option value="EN_ATTENTE">⏳ En Attente</option>
            </select>
            ${c.statut === 'NON_CONFORME'
              ? `<button class="fbtn" style="color:var(--accent);font-size:9px" onclick="createNCFromCQ(${c.id},'${c.of_numero||''}','${c.cq_numero}')">+NC</button>`
              : ''}
          </td>
        </tr>`;
      }).join('')}
      </tbody></table>`;

  } catch(e) { toast('Erreur qualité: ' + e.message, 'err'); }
}

// ── LIVE RÉSULTAT ─────────────────────────────────────────
function updateCQResultat() {
  const total  = parseFloat($('cq-total')?.value) || 0;
  const ok     = parseFloat($('cq-ok')?.value)    || 0;
  const rebut  = parseFloat($('cq-rebut')?.value)  || 0;
  const badge  = $('cq-resultat-badge');
  if (!badge) return;

  if (total === 0) {
    badge.textContent = '— Saisir les quantités —';
    badge.style.color = 'var(--muted)';
    return;
  }
  const taux = Math.round(ok / total * 100);
  if (rebut > 0 || ok < total) {
    badge.innerHTML = `<span style="color:var(--red)">✗ NON CONFORME</span> &nbsp;·&nbsp; ${taux}% conforme &nbsp;·&nbsp; ${rebut} rebut(s)`;
  } else {
    badge.innerHTML = `<span style="color:var(--green)">✓ CONFORME</span> &nbsp;·&nbsp; 100% — Zéro rebut`;
  }
}

function onCQOFChange() {
  // Auto-fill quantite from OF if linked
}

// ── SAVE ──────────────────────────────────────────────────
async function saveControle() {
  if (!$('cq-date')?.value) { toast('Date obligatoire', 'err'); return; }
  const total = parseFloat($('cq-total')?.value) || 0;
  const ok    = parseFloat($('cq-ok')?.value)    || 0;
  const rebut = parseFloat($('cq-rebut')?.value)  || 0;
  const statut = rebut > 0 || ok < total ? 'NON_CONFORME'
               : total > 0              ? 'CONFORME'
               :                          'EN_ATTENTE';
  try {
    await api('/api/qualite/controles', 'POST', {
      of_id:              $('cq-of')?.value   ? parseInt($('cq-of').value) : null,
      type_controle:      $('cq-type')?.value || 'FINAL',
      operateur_id:       $('cq-op')?.value   ? parseInt($('cq-op').value) : null,
      date_controle:      $('cq-date').value,
      statut,
      quantite_controlee: total,
      quantite_conforme:  ok,
      quantite_rebut:     rebut,
      notes:              $('cq-notes')?.value || null
    });
    toast('Contrôle enregistré ✓');
    closeModal('modal-qualite');
    // Reset form
    ['cq-total','cq-ok','cq-rebut'].forEach(id => { if ($(id)) $(id).value = 0; });
    if ($('cq-notes')) $('cq-notes').value = '';
    if ($('cq-resultat-badge')) { $('cq-resultat-badge').textContent = '— Saisir les quantités —'; }
    loadQualite();
  } catch(e) { toast(e.message, 'err'); }
}

async function updateCQStatus(id, statut) {
  if (!statut) return;
  try {
    await api(`/api/qualite/controles/${id}`, 'PUT', { statut });
    toast(`Statut → ${statut.replace('_',' ')} ✓`);
    loadQualite();
  } catch(e) { toast(e.message, 'err'); }
}

// Quick NC creation from non-conforme CQ
function createNCFromCQ(cqId, ofNum, cqNum) {
  // Pre-fill NC modal and open it
  if ($('nc-of')) {
    const ofOpt = [...($('nc-of')?.options||[])].find(o => o.text.includes(ofNum));
    if (ofOpt) $('nc-of').value = ofOpt.value;
  }
  if ($('nc-desc')) $('nc-desc').value = `Non-conformité détectée lors du contrôle ${cqNum}`;
  closeModal('modal-qualite');
  openModal('modal-nc');
  toast('Formulaire NC pré-rempli ✓');
}