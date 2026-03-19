// ── materials.js ─────────────────────────────────────────
async function loadMaterials() {
  try {
    const [mats, mvts] = await Promise.all([
      api('/api/materiaux'),
      api('/api/materiaux/mouvements?limit=20')
    ]);

    // Materials table
    $('mats-tb').innerHTML = (mats||[]).length === 0 ? empty(9) : (mats||[]).map(m => {
      const pct = Math.min(100, Math.round(m.pct_stock||0));
      const cls = pct < 50 ? 'd' : pct < 90 ? 'w' : 'ok';
      const prix = parseFloat(m.prix_unitaire||0);
      return `<tr>
        <td><span class="of-num">${m.code}</span></td>
        <td><strong>${m.nom}</strong></td>
        <td style="font-family:'IBM Plex Mono',monospace">${m.stock_actuel}</td>
        <td style="font-family:'IBM Plex Mono',monospace;color:var(--muted)">${m.stock_minimum}</td>
        <td style="color:var(--muted)">${m.unite}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--accent)">
          ${prix > 0 ? prix.toFixed(3) + ' DT' : '—'}
        </td>
        <td style="font-size:10px;color:var(--muted)">${m.fournisseur||'—'}</td>
        <td>${m.alerte
          ? '<span class="badge b-urgent">ALERTE</span>'
          : '<span class="badge b-completed">OK</span>'}</td>
        <td style="min-width:80px">
          <div class="bar-w"><div class="bar-f ${cls}" style="width:${pct}%"></div></div>
        </td>
        <td style="display:flex;gap:3px">
          <button class="fbtn"
            data-id="${m.id}"
            data-nom="${m.nom.replace(/"/g,'&quot;')}"
            data-unite="${m.unite}"
            data-min="${m.stock_minimum}"
            data-prix="${prix}"
            data-four="${(m.fournisseur||'').replace(/"/g,'&quot;')}"
            onclick="openEditMateriauBtn(this)">✎</button>
          <button class="fbtn" style="color:var(--red)" onclick="deleteMateriau(${m.id},'${m.nom.replace(/'/g,"\\'")}')">🗑</button>
        </td>
      </tr>`;
    }).join('');

    // Mouvements table
    $('mvt-tb').innerHTML = (mvts||[]).length === 0 ? empty(8,'Aucun mouvement') : (mvts||[]).map(m => {
      const col = m.type==='ENTREE' ? 'var(--green)' : m.type==='SORTIE' ? 'var(--red)' : 'var(--accent)';
      return `<tr>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--muted)">${(m.created_at||'').slice(0,16)}</td>
        <td>${m.materiau_nom}</td>
        <td><span style="color:${col};font-family:'IBM Plex Mono',monospace;font-size:9px">${m.type}</span></td>
        <td style="font-family:'IBM Plex Mono',monospace">${m.quantite}</td>
        <td style="color:var(--muted);font-family:'IBM Plex Mono',monospace">${m.stock_avant||'—'}</td>
        <td style="font-family:'IBM Plex Mono',monospace">${m.stock_apres||'—'}</td>
        <td><span class="of-num">${m.of_numero||'—'}</span></td>
        <td style="font-size:10px;color:var(--muted)">${m.motif||'—'}</td>
      </tr>`;
    }).join('');

    // Populate mouvement select
    $('mv-mat').innerHTML = (mats||[]).map(m =>
      `<option value="${m.id}">${m.nom} (${m.stock_actuel} ${m.unite})</option>`).join('');

  } catch(e) { toast('Erreur matériaux: ' + e.message, 'err'); }
}

// ── CREATE ────────────────────────────────────────────────
async function saveMateriau() {
  if (!$('mat-code').value || !$('mat-nom').value) {
    toast('Code et nom obligatoires', 'err'); return;
  }
  try {
    await api('/api/materiaux', 'POST', {
      code:          $('mat-code').value,
      nom:           $('mat-nom').value,
      unite:         $('mat-unite').value,
      stock_actuel:  parseFloat($('mat-stock').value)  || 0,
      stock_minimum: parseFloat($('mat-min').value)    || 0,
      prix_unitaire: parseFloat($('mat-prix')?.value)  || 0,
      fournisseur:   $('mat-four').value               || null
    });
    toast('Matériau créé ✓'); closeModal('m-mat'); loadMaterials();
  } catch(e) { toast(e.message, 'err'); }
}

// ── EDIT ──────────────────────────────────────────────────
function openEditMateriau(id, nom, unite, stockMin, prix, fourn) {
  $('mat-edit-id').value    = id;
  $('mat-edit-nom').value   = nom;
  $('mat-edit-unite').value = unite;
  $('mat-edit-min').value   = stockMin || 0;
  $('mat-edit-prix').value  = prix     || 0;
  $('mat-edit-four').value  = fourn    || '';
  openModal('m-mat-edit');
}

function openEditMateriauBtn(btn) {
  $('mat-edit-id').value    = btn.dataset.id;
  $('mat-edit-nom').value   = btn.dataset.nom;
  $('mat-edit-unite').value = btn.dataset.unite;
  $('mat-edit-min').value   = btn.dataset.min  || 0;
  $('mat-edit-prix').value  = btn.dataset.prix || 0;
  $('mat-edit-four').value  = btn.dataset.four || '';
  openModal('m-mat-edit');
}

async function saveEditMateriau() {
  const id = $('mat-edit-id').value;
  if (!id) return;
  try {
    await api(`/api/materiaux/${id}`, 'PUT', {
      nom:           $('mat-edit-nom').value   || null,
      unite:         $('mat-edit-unite').value || null,
      stock_minimum: parseFloat($('mat-edit-min').value)  || 0,
      prix_unitaire: parseFloat($('mat-edit-prix').value) || 0,
      fournisseur:   $('mat-edit-four').value  || null
    });
    toast('Matériau mis à jour ✓'); closeModal('m-mat-edit'); loadMaterials();
  } catch(e) { toast(e.message, 'err'); }
}

// ── DELETE ────────────────────────────────────────────────
async function deleteMateriau(id, nom) {
  if (!confirm(`Supprimer "${nom}" ?`)) return;
  try {
    await api(`/api/materiaux/${id}`, 'DELETE');
    toast('Matériau supprimé ✓'); loadMaterials();
  } catch(e) { toast(e.message, 'err'); }
}

// ── MOUVEMENT ─────────────────────────────────────────────
async function saveMouvement() {
  try {
    await api('/api/materiaux/mouvement', 'POST', {
      materiau_id: parseInt($('mv-mat').value),
      type:        $('mv-type').value,
      quantite:    parseFloat($('mv-qte').value),
      motif:       $('mv-motif').value || null
    });
    toast('Stock mis à jour ✓'); closeModal('m-mv'); loadMaterials();
  } catch(e) { toast(e.message, 'err'); }
}