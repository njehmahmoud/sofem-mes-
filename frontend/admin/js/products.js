// ── products.js ──────────────────────────────────────────
let _allMats = [];
let _bomEditorProdId = null;
let _bomLines = [];

async function loadProducts() {
  try {
    const [prods, mats] = await Promise.all([api('/api/produits'), api('/api/materiaux')]);
    _allMats = mats || [];
    const list = prods || [];
    // Update next-code preview
    const sofem = list.filter(p=>p.code.startsWith('SOFEM-')).sort((a,b)=>b.code.localeCompare(a.code));
    const nextNum = sofem.length ? parseInt(sofem[0].code.split('-')[1]||0)+1 : 1;
    if ($('prod-code-preview')) $('prod-code-preview').textContent = `SOFEM-${String(nextNum).padStart(3,'0')}`;

    $('prods-tb').innerHTML = list.length===0 ? empty(5) : list.map(p => {
      const bomPills = (p.bom||[]).map(b =>
        `<span style="font-size:9px;font-family:'IBM Plex Mono',monospace;background:var(--bg3);border:1px solid var(--border);border-radius:3px;padding:1px 5px;margin-right:3px">${b.materiau_nom} × ${b.quantite_par_unite}</span>`
      ).join('');
      return `<tr>
        <td><span class="of-num">${p.code}</span></td>
        <td><strong>${p.nom}</strong></td>
        <td style="color:var(--muted);font-size:10px">${p.description||'—'}</td>
        <td style="color:var(--muted)">${p.unite}</td>
        <td>${bomPills||'<span style="font-size:10px;color:var(--muted)">— Aucun —</span>'}
          <button class="fbtn" style="color:var(--accent);margin-left:4px" onclick="openBOMEditor(${p.id},'${p.nom.replace(/'/g,"\\'")}')">✎ BOM</button></td>
      </tr>`;
    }).join('');
  } catch(e) { toast('Erreur produits: ' + e.message,'err'); }
}

async function saveProduit() {
  if (!$('prod-nom').value) { toast('Nom requis','err'); return; }
  try {
    const res = await api('/api/produits','POST',{
      nom: $('prod-nom').value,
      description: $('prod-desc').value||null,
      unite: $('prod-unite').value||'pcs'
    });
    toast(`${res.code} créé ✓`); closeModal('m-prod'); loadProducts();
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