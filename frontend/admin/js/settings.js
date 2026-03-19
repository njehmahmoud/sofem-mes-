// ── settings.js v10 ──────────────────────────────────────
let _settings = {};

const SETTINGS_META = {
  societe: {
    label: '🏢 Informations Société',
    desc:  'Apparaissent sur tous les PDFs (Fiche, Facture, BL, DA, BC)',
    fields: [
      { cle:'societe_nom',       label:'Nom société',         type:'text'   },
      { cle:'societe_tagline',   label:'Tagline / Activité',  type:'text'   },
      { cle:'societe_adresse',   label:'Adresse',             type:'text'   },
      { cle:'societe_ville',     label:'Ville',               type:'text'   },
      { cle:'societe_telephone', label:'Téléphone',           type:'text'   },
      { cle:'societe_email',     label:'Email',               type:'email'  },
      { cle:'societe_website',   label:'Site web',            type:'text'   },
      { cle:'societe_mf',        label:'Matricule Fiscal',    type:'text'   },
      { cle:'societe_rc',        label:'Registre de Commerce',type:'text'   },
    ]
  },
  finance: {
    label: '💰 Paramètres Financiers',
    desc:  'Utilisés dans les calculs de coût et les factures',
    fields: [
      { cle:'tva_rate',            label:'TVA (%)',                    type:'number', step:'0.1' },
      { cle:'devise',              label:'Devise',                     type:'text'   },
      { cle:'overhead_pct',        label:'Frais généraux (%)',         type:'number', step:'0.1' },
      { cle:'prix_horaire_defaut', label:'Prix horaire défaut (TND/h)',type:'number', step:'0.001' },
      { cle:'prix_piece_defaut',   label:'Prix pièce défaut (TND/pcs)',type:'number', step:'0.001' },
    ]
  },
  alertes: {
    label: '🔔 Seuils & Alertes',
    desc:  'Déclencheurs pour les alertes automatiques',
    fields: [
      { cle:'stock_alerte_auto',   label:'Alertes stock automatiques', type:'boolean' },
      { cle:'retard_alerte_jours', label:'Alerte retard OF (jours avant échéance)', type:'number' },
      { cle:'urgent_auto_jours',   label:'Auto-URGENT si retard > X jours (0=désactivé)', type:'number' },
    ]
  },
  workflow: {
    label: '🔄 Workflow Production',
    desc:  'Contrôle le comportement automatique du système',
    fields: [
      { cle:'bl_auto_creation',     label:'Créer BL automatiquement à la création OF', type:'boolean' },
      { cle:'stock_deduction_auto', label:'Déduire stock au démarrage production',      type:'boolean' },
      { cle:'cq_avant_completed',   label:'Exiger contrôle qualité avant OF TERMINÉ',  type:'boolean' },
      { cle:'da_auto_approve_seuil',label:'Auto-approuver DA sous X TND (0=désactivé)',type:'number'  },
      { cle:'of_numero_format',     label:'Format numéro OF',                           type:'text'   },
      { cle:'da_numero_format',     label:'Format numéro DA',                           type:'text'   },
    ]
  },
  pdf: {
    label: '📄 Paramètres PDF',
    desc:  'Personnalisation des documents générés',
    fields: [
      { cle:'pdf_rev',         label:'Révision documents (ENR)',   type:'text' },
      { cle:'pdf_pied_custom', label:'Pied de page PDF',           type:'text' },
      { cle:'pdf_entete_custom',label:'En-tête personnalisé',      type:'textarea' },
    ]
  },
  acces: {
    label: '🔐 Gestion des Accès',
    desc:  'Politiques de sécurité et de rôles',
    fields: [
      { cle:'session_timeout_min', label:'Timeout session (minutes)',           type:'number' },
      { cle:'pin_min_length',      label:'Longueur PIN minimum',                type:'number' },
      { cle:'da_approve_role',     label:'Rôle requis pour approuver DA',       type:'select',
        options:['MANAGER','ADMIN'] },
      { cle:'of_delete_role',      label:'Rôle requis pour supprimer OF',       type:'select',
        options:['MANAGER','ADMIN'] },
    ]
  }
};

async function loadSettings() {
  try {
    const data = await api('/api/settings');
    if (!data) return;

    // Flatten all values
    Object.values(data).forEach(group => {
      group.forEach(s => { _settings[s.cle] = s.valeur_parsed; });
    });

    renderSettings();
  } catch(e) { toast('Erreur settings: ' + e.message, 'err'); }
}

function renderSettings() {
  const container = $('settings-container');
  if (!container) return;

  container.innerHTML = Object.entries(SETTINGS_META).map(([groupe, meta]) => `
    <div class="sec" style="margin-bottom:1.5rem">
      <div class="sec-h">
        <div>
          <div class="sec-title">${meta.label}</div>
          <div style="font-size:10px;color:var(--muted);margin-top:2px">${meta.desc}</div>
        </div>
        <button class="btn btn-ghost" style="font-size:10px" onclick="saveGroup('${groupe}')">💾 Sauvegarder</button>
      </div>
      <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:.75rem;margin-top:.75rem">
        ${meta.fields.map(f => renderField(f)).join('')}
      </div>
    </div>
  `).join('');
}

function renderField(f) {
  const val = _settings[f.cle] ?? '';
  const id  = `stg-${f.cle}`;

  if (f.type === 'boolean') {
    return `<div class="fg" style="display:flex;align-items:center;justify-content:space-between;background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:.5rem .75rem">
      <label style="font-size:11px;color:var(--text);cursor:pointer" for="${id}">${f.label}</label>
      <label style="position:relative;display:inline-block;width:40px;height:22px;flex-shrink:0">
        <input type="checkbox" id="${id}" ${val?'checked':''} style="opacity:0;width:0;height:0"
          onchange="updateSettingLocal('${f.cle}',this.checked)">
        <span style="position:absolute;cursor:pointer;inset:0;background:${val?'var(--red)':'var(--bg2)'};border-radius:22px;transition:.2s;border:1px solid var(--border)">
          <span style="position:absolute;height:16px;width:16px;left:${val?'20':'2'}px;top:2px;background:#fff;border-radius:50%;transition:.2s"></span>
        </span>
      </label>
    </div>`;
  }

  if (f.type === 'select') {
    return `<div class="fg">
      <label style="font-size:10px;color:var(--muted);font-family:'IBM Plex Mono',monospace;text-transform:uppercase;letter-spacing:1px">${f.label}</label>
      <select id="${id}" onchange="updateSettingLocal('${f.cle}',this.value)"
        style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:6px 8px;color:var(--text);font-size:12px;margin-top:4px">
        ${(f.options||[]).map(o => `<option value="${o}" ${val===o?'selected':''}>${o}</option>`).join('')}
      </select>
    </div>`;
  }

  if (f.type === 'textarea') {
    return `<div class="fg" style="grid-column:span 2">
      <label style="font-size:10px;color:var(--muted);font-family:'IBM Plex Mono',monospace;text-transform:uppercase;letter-spacing:1px">${f.label}</label>
      <textarea id="${id}" rows="2" onchange="updateSettingLocal('${f.cle}',this.value)"
        style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:6px 8px;color:var(--text);font-size:12px;margin-top:4px;resize:vertical">${val}</textarea>
    </div>`;
  }

  return `<div class="fg">
    <label style="font-size:10px;color:var(--muted);font-family:'IBM Plex Mono',monospace;text-transform:uppercase;letter-spacing:1px">${f.label}</label>
    <input type="${f.type}" id="${id}" value="${val}" step="${f.step||''}"
      onchange="updateSettingLocal('${f.cle}',this.value)"
      style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:6px 8px;color:var(--text);font-size:12px;margin-top:4px;box-sizing:border-box">
  </div>`;
}

function updateSettingLocal(cle, val) {
  _settings[cle] = val;
}

async function saveGroup(groupe) {
  const meta = SETTINGS_META[groupe];
  if (!meta) return;
  const updates = {};
  meta.fields.forEach(f => {
    const el = $(`stg-${f.cle}`);
    if (!el) return;
    if (f.type === 'boolean') updates[f.cle] = el.checked ? 'true' : 'false';
    else updates[f.cle] = el.value;
  });
  try {
    await api('/api/settings/bulk', 'PUT', { settings: updates });
    toast(`${meta.label} sauvegardé ✓`);
    // Re-render toggles to update colors
    loadSettings();
  } catch(e) { toast(e.message, 'err'); }
}

async function saveAllSettings() {
  const updates = {};
  Object.values(SETTINGS_META).forEach(meta => {
    meta.fields.forEach(f => {
      const el = $(`stg-${f.cle}`);
      if (!el) return;
      if (f.type === 'boolean') updates[f.cle] = el.checked ? 'true' : 'false';
      else updates[f.cle] = el.value;
    });
  });
  try {
    await api('/api/settings/bulk', 'PUT', { settings: updates });
    toast('Tous les paramètres sauvegardés ✓');
  } catch(e) { toast(e.message, 'err'); }
}