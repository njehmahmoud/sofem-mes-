// ── products.js ──────────────────────────────────────────
let _allMats = [];
let _bomEditorProdId = null;
let _bomLines = [];

async function loadProducts() {
  try {
    const [prods, mats] = await Promise.all([api('/api/produits'), api('/api/materiaux')]);
    _allMats = mats || [];
    const list = prods || [];

    // Next code preview
    const sofem = list.filter(p=>p.code.startsWith('SOFEM-')).sort((a,b)=>b.code.localeCompare(a.code));
    const nextNum = sofem.length ? parseInt(sofem[0].code.split('-')[1]||0)+1 : 1;
    if ($('prod-code-preview')) $('prod-code-preview').textContent = `SOFEM-${String(nextNum).padStart(3,'0')}`;

    $('prods-tb').innerHTML = list.length===0 ? empty(6) : list.map(p => {
      const bomPills = (p.bom||[]).map(b =>
        `<span style="font-size:9px;font-family:'IBM Plex Mono',monospace;background:var(--bg3);border:1px solid var(--border);border-radius:3px;padding:1px 5px;margin-right:3px">${b.materiau_nom} × ${b.quantite_par_unite}</span>`
      ).join('');
      const prix = parseFloat(p.prix_vente_ht||0);
      return `<tr>
        <td><span class="of-num">${p.code}</span></td>
        <td><strong>${p.nom}</strong></td>
        <td style="color:var(--muted);font-size:10px">${p.description||'—'}</td>
        <td style="color:var(--muted)">${p.unite}</td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--accent)">
          ${prix > 0 ? prix.toFixed(3) + ' DT' : '—'}
        </td>
        <td>
          ${bomPills||'<span style="font-size:10px;color:var(--muted)">— Aucun —</span>'}
          <button class="fbtn" style="color:var(--accent);margin-left:4px"
            onclick="openBOMEditor(${p.id},'${p.nom.replace(/'/g,"\\'")}')">✎ BOM</button>
        </td>
        <td>
          <button class="fbtn"
            data-id="${p.id}"
            data-nom="${p.nom.replace(/"/g,'&quot;')}"
            data-unite="${p.unite}"
            data-prix="${prix}"
            data-desc="${(p.description||''). replace(/"/g,'&quot;')}"
            onclick="openEditProduitBtn(this)">✎</button>
        </td>
      </tr>`;
    }).join('');
  } catch(e) { toast('Erreur produits: ' + e.message,'err'); }
}

// ── CREATE ────────────────────────────────────────────────
async function saveProduit() {
  if (!$('prod-nom').value) { toast('Nom requis','err'); return; }
  try {
    const res = await api('/api/produits','POST',{
      nom:          $('prod-nom').value,
      description:  $('prod-desc').value  || null,
      unite:        $('prod-unite').value  || 'pcs',
      prix_vente_ht: parseFloat($('prod-prix')?.value) || 0
    });
    toast(`${res.code} créé ✓`); closeModal('m-prod'); loadProducts();
  } catch(e) { toast(e.message,'err'); }
}

// ── EDIT ──────────────────────────────────────────────────
function openEditProduit(id, nom, unite, prix, desc) {
  $('prod-edit-id').value   = id;
  $('prod-edit-nom').value  = nom;
  $('prod-edit-unite').value = unite;
  $('prod-edit-prix').value  = prix || 0;
  $('prod-edit-desc').value  = desc || '';
  openModal('m-prod-edit');
}

function openEditProduitBtn(btn) {
  $('prod-edit-id').value   = btn.dataset.id;
  $('prod-edit-nom').value  = btn.dataset.nom;
  $('prod-edit-unite').value = btn.dataset.unite;
  $('prod-edit-prix').value  = btn.dataset.prix || 0;
  $('prod-edit-desc').value  = btn.dataset.desc || '';
  openModal('m-prod-edit');
}

async function saveEditProduit() {
  const id = $('prod-edit-id').value;
  if (!id) return;
  try {
    await api(`/api/produits/${id}`, 'PUT', {
      nom:           $('prod-edit-nom').value,
      unite:         $('prod-edit-unite').value   || 'pcs',
      prix_vente_ht: parseFloat($('prod-edit-prix').value) || 0,
      description:   $('prod-edit-desc').value    || null
    });
    toast('Produit mis à jour ✓'); closeModal('m-prod-edit'); loadProducts();
  } catch(e) { toast(e.message,'err'); }
}

// ── BOM EDITOR ────────────────────────────────────────────
async function openBOMEditor(prodId, prodNom) {
  _bomEditorProdId = prodId;
  const bom = await api(`/api/produits/${prodId}/bom`) || [];
  _bomLines = bom.map(b=>({...b}));
  $('bom-prod-title').textContent = prodNom;
  renderBOMEditor();
  openModal('m-bom');
}

function renderBOMEditor() {
  $('bom-lines-body').innerHTML = _bomLines.length === 0
    ? `<tr><td colspan="4" style="color:var(--muted);font-size:11px;text-align:center;padding:1rem">— Cliquez + Ajouter —</td></tr>`
    : _bomLines.map((l, i) => `<tr>
        <td>${l.materiau_nom}</td>
        <td><input type="number" value="${l.quantite_par_unite}" min="0.001" step="0.001"
          style="width:75px;background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:3px 6px;color:var(--text);font-family:'IBM Plex Mono',monospace;font-size:11px"
          onchange="_bomLines[${i}].quantite_par_unite=parseFloat(this.value)||0"></td>
        <td style="font-size:10px;color:var(--muted)">${l.unite}</td>
        <td><button class="fbtn" style="color:var(--red)" onclick="_bomLines.splice(${i},1);renderBOMEditor()">✕</button></td>
      </tr>`).join('');
  $('bom-add-mat').innerHTML = '<option value="">— Ajouter matériau —</option>' +
    _allMats.filter(m => !_bomLines.find(l => l.materiau_id===m.id))
            .map(m => `<option value="${m.id}" data-nom="${m.nom}" data-unite="${m.unite}">${m.nom} (${m.unite})</option>`).join('');
}

function bomAddLine() {
  const sel = $('bom-add-mat');
  const id  = parseInt(sel.value); if (!id) return;
  const opt = sel.options[sel.selectedIndex];
  _bomLines.push({ materiau_id:id, materiau_nom:opt.dataset.nom, unite:opt.dataset.unite, quantite_par_unite:1 });
  renderBOMEditor();
}

async function saveBOM() {
  if (!_bomEditorProdId) return;
  try {
    await api(`/api/produits/${_bomEditorProdId}/bom`,'PUT',
      _bomLines.map(l=>({ materiau_id:l.materiau_id, quantite_par_unite:l.quantite_par_unite })));
    toast('BOM sauvegardé ✓'); closeModal('m-bom'); loadProducts();
  } catch(e) { toast(e.message,'err'); }
}