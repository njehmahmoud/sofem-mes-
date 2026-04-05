// ── settings.js v10 ──────────────────────────────────────
let _settings = {};
let _displaySettings = {};
let _activeTab = 'systeme';

// ── Display settings stored in localStorage ───────────────
const DISPLAY_DEFAULTS = {
  date_format:       'DD/MM/YYYY',
  number_format:     'FR',
  currency_position: 'after',
  dash_of_count:     6,
  auto_refresh_sec:  0,
  default_page:      'dashboard',
  accent_color:      '#D42B2B',
  toast_duration:    3,
  show_bl_col:       true,
  show_chef_col:     true,
  show_client_col:   true,
  compact_table:     false,
  theme:             'dark',
};

function loadDisplaySettings() {
  try {
    const saved = JSON.parse(localStorage.getItem('sofem_display') || '{}');
    _displaySettings = { ...DISPLAY_DEFAULTS, ...saved };
  } catch { _displaySettings = { ...DISPLAY_DEFAULTS }; }
}

function saveDisplaySettings() {
  localStorage.setItem('sofem_display', JSON.stringify(_displaySettings));
}

// Expose globally so other modules can use it
window.getDisplaySetting = (key) => _displaySettings[key] ?? DISPLAY_DEFAULTS[key];

// ── System settings config ────────────────────────────────
const SYSTEM_GROUPS = {
  societe: {
    icon: '🏢', label: 'Informations Société',
    desc: 'Apparaissent sur tous les PDFs — Fiche, Facture, BL, DA, BC',
    color: 'var(--blue)',
    fields: [
      { cle:'societe_nom',       label:'Nom société',          type:'text',  full:false },
      { cle:'societe_tagline',   label:'Activité / Tagline',   type:'text',  full:true  },
      { cle:'societe_adresse',   label:'Adresse',              type:'text',  full:false },
      { cle:'societe_ville',     label:'Ville',                type:'text',  full:false },
      { cle:'societe_telephone', label:'Téléphone',            type:'text',  full:false },
      { cle:'societe_email',     label:'Email',                type:'email', full:false },
      { cle:'societe_website',   label:'Site web',             type:'text',  full:false },
      { cle:'societe_mf',        label:'Matricule Fiscal',     type:'text',  full:false },
      { cle:'societe_rc',        label:'Registre de Commerce', type:'text',  full:false },
    ]
  },
  finance: {
    icon: '💰', label: 'Paramètres Financiers',
    desc: 'Utilisés dans les calculs de coût et les factures',
    color: 'var(--green)',
    fields: [
      { cle:'tva_rate',            label:'TVA (%)',                     type:'number', step:'0.1',   full:false },
      { cle:'devise',              label:'Devise',                      type:'text',                 full:false },
      { cle:'overhead_pct',        label:'Frais généraux (%)',          type:'number', step:'0.1',   full:false },
      { cle:'prix_horaire_defaut', label:'Prix horaire défaut (TND/h)', type:'number', step:'0.001', full:false },
      { cle:'prix_piece_defaut',   label:'Prix pièce défaut (TND/pcs)', type:'number', step:'0.001', full:false },
    ]
  },
  workflow: {
    icon: '🔄', label: 'Workflow Production',
    desc: 'Contrôle le comportement automatique du système',
    color: 'var(--accent)',
    fields: [
      { cle:'bl_auto_creation',      label:'Créer BL automatiquement à la création OF',         type:'boolean', full:true  },
      { cle:'stock_deduction_auto',  label:'Déduire stock au démarrage production',            type:'boolean', full:true  },
      { cle:'cq_avant_completed',    label:'Exiger contrôle qualité avant OF TERMINÉ',        type:'boolean', full:true  },
      { cle:'cq_auto_creation',      label:'Créer automatiquement ticket qualité après OF terminé', type:'boolean', full:true  },
      { cle:'da_auto_approve_seuil', label:'Auto-approuver DA sous X TND (0=désactivé)',      type:'number',  full:false },
      { cle:'of_numero_format',      label:'Format numéro OF',                                 type:'text',   full:false },
      { cle:'da_numero_format',      label:'Format numéro DA',                                 type:'text',   full:false },
    ]
  },
  alertes: {
    icon: '🔔', label: 'Seuils & Alertes',
    desc: 'Déclencheurs pour les alertes automatiques',
    color: '#F97316',
    fields: [
      { cle:'stock_alerte_auto',   label:'Alertes stock automatiques',             type:'boolean', full:true  },
      { cle:'retard_alerte_jours', label:'Alerte retard OF (jours avant échéance)',type:'number',  full:false },
      { cle:'urgent_auto_jours',   label:'Auto-URGENT si retard > X jours',        type:'number',  full:false },
    ]
  },
  pdf: {
    icon: '📄', label: 'Documents & PDF',
    desc: 'Personnalisation des documents générés',
    color: '#8B5CF6',
    fields: [
      { cle:'pdf_rev',          label:'Révision documents (ENR)',  type:'text',     full:false },
      { cle:'pdf_pied_custom',  label:'Pied de page PDF',          type:'text',     full:true  },
      { cle:'pdf_entete_custom',label:'En-tête personnalisé',      type:'textarea', full:true  },
    ]
  },
  acces: {
    icon: '🔐', label: 'Gestion des Accès',
    desc: 'Politiques de sécurité et de rôles',
    color: 'var(--red)',
    fields: [
      { cle:'session_timeout_min', label:'Timeout session (minutes)',          type:'number',  full:false },
      { cle:'pin_min_length',      label:'Longueur PIN minimum',               type:'number',  full:false },
      { cle:'da_approve_role',     label:'Rôle requis pour approuver DA',      type:'select',  full:false,
        options:['MANAGER','ADMIN'] },
      { cle:'of_delete_role',      label:'Rôle requis pour supprimer OF',      type:'select',  full:false,
        options:['MANAGER','ADMIN'] },
    ]
  }
};

// ── Main load ─────────────────────────────────────────────
async function loadSettings() {
  loadDisplaySettings();
  try {
    const data = await api('/api/settings');
    if (data) {
      Object.values(data).forEach(group =>
        group.forEach(s => { _settings[s.cle] = s.valeur_parsed; })
      );
    }
  } catch(e) { console.warn('Settings API error:', e.message); }
  renderSettingsPage();
}

// ── Render full page ──────────────────────────────────────
function renderSettingsPage() {
  const container = $('settings-container');
  if (!container) return;

  container.innerHTML = `
    <!-- Tab bar -->
    <div style="display:flex;gap:0;border-bottom:2px solid var(--border);margin-bottom:1.5rem">
      <button class="stab ${_activeTab==='systeme'?'stab-active':''}" onclick="switchSettingsTab('systeme')">
        ⚙️ Système
      </button>
      <button class="stab ${_activeTab==='affichage'?'stab-active':''}" onclick="switchSettingsTab('affichage')">
        🖥️ Affichage
      </button>
      <button class="stab ${_activeTab==='utilisateurs'?'stab-active':''}" onclick="switchSettingsTab('utilisateurs')">
        🔐 Utilisateurs
      </button>
    </div>

    <!-- Tab content -->
    <div id="stab-systeme"  style="display:${_activeTab==='systeme'? 'block':'none'}">
      ${renderSystemeTab()}
    </div>
    <div id="stab-affichage" style="display:${_activeTab==='affichage'?'block':'none'}">
      ${renderAffichageTab()}
    </div>
    <div id="stab-utilisateurs" style="display:${_activeTab==='utilisateurs'?'block':'none'}">
      ${renderUtilisateursTab()}
    </div>
  `;

  // Inject tab CSS if not present
  if (!document.getElementById('stab-css')) {
    const style = document.createElement('style');
    style.id = 'stab-css';
    style.textContent = `
      .stab{background:none;border:none;padding:.6rem 1.4rem;font-family:'IBM Plex Mono',monospace;
        font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);
        cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px;transition:all .15s}
      .stab:hover{color:var(--text)}
      .stab-active{color:var(--red);border-bottom-color:var(--red)}
      .scard{background:var(--bg2);border:1px solid var(--border);border-radius:8px;
        padding:1.25rem;margin-bottom:1rem}
      .scard-head{display:flex;align-items:center;gap:.75rem;margin-bottom:1rem;
        padding-bottom:.75rem;border-bottom:1px solid var(--border)}
      .scard-icon{width:36px;height:36px;border-radius:8px;display:flex;align-items:center;
        justify-content:center;font-size:18px;background:var(--bg3);flex-shrink:0}
      .scard-title{font-family:'IBM Plex Mono',monospace;font-size:11px;text-transform:uppercase;
        letter-spacing:1px;color:var(--text);font-weight:600}
      .scard-desc{font-size:10px;color:var(--muted);margin-top:2px}
      .scard-save{margin-left:auto;font-size:10px;padding:4px 12px}
      .sfgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:.75rem}
      .sfull{grid-column:span 2}
      .stoggle{display:flex;align-items:center;justify-content:space-between;
        background:var(--bg3);border:1px solid var(--border);border-radius:6px;
        padding:.5rem .75rem;cursor:pointer;gap:1rem}
      .stoggle label{font-size:11px;color:var(--text);cursor:pointer;flex:1;min-width:0}
      .toggle-wrap{display:flex;align-items:center;flex-shrink:0}
      .toggle-track{position:relative;display:inline-block;width:44px;height:24px;flex-shrink:0}
      .toggle-track input{opacity:0;width:0;height:0;position:absolute}
      .toggle-thumb{position:absolute;cursor:pointer;inset:0;border-radius:24px;
        background:var(--bg2);border:1px solid var(--border);transition:.2s}
      .toggle-thumb:before{content:'';position:absolute;height:18px;width:18px;
        left:2px;bottom:2px;border-radius:50%;background:var(--muted);transition:.2s}
      input:checked + .toggle-thumb{background:var(--red);border-color:var(--red)}
      input:checked + .toggle-thumb:before{transform:translateX(20px);background:#fff}
      .sfield label{font-size:9px;color:var(--muted);font-family:'IBM Plex Mono',monospace;
        text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:4px}
      .sfield input,.sfield select,.sfield textarea{width:100%;background:var(--bg3);
        border:1px solid var(--border);border-radius:4px;padding:7px 10px;color:var(--text);
        font-size:12px;box-sizing:border-box;transition:border-color .15s}
      .sfield input:focus,.sfield select:focus,.sfield textarea:focus{
        outline:none;border-color:var(--red)}
    `;
    document.head.appendChild(style);
  }
}

// ── Système tab ───────────────────────────────────────────
function renderSystemeTab() {
  return `
    <div style="display:flex;justify-content:flex-end;margin-bottom:1rem">
      <button class="btn" onclick="saveAllSettings()">💾 Tout sauvegarder</button>
    </div>
    ${Object.entries(SYSTEM_GROUPS).map(([groupe, meta]) => `
      <div class="scard">
        <div class="scard-head">
          <div class="scard-icon">${meta.icon}</div>
          <div>
            <div class="scard-title">${meta.label}</div>
            <div class="scard-desc">${meta.desc}</div>
          </div>
          <button class="btn btn-ghost scard-save" onclick="saveGroup('${groupe}')">💾 Sauvegarder</button>
        </div>
        <div class="sfgrid">
          ${meta.fields.map(f => renderSystemField(f)).join('')}
        </div>
      </div>
    `).join('')}
  `;
}

function renderSystemField(f) {
  const val = _settings[f.cle] ?? '';
  const id  = `stg-${f.cle}`;
  const fullClass = f.full ? 'sfull' : '';

  if (f.type === 'boolean') {
    const checked = val === true || val === 'true' || val === 1;
    return `<div class="stoggle ${fullClass}">
      <label for="${id}" style="cursor:pointer">${f.label}</label>
      <div class="toggle-wrap">
        <label class="toggle-track">
          <input type="checkbox" id="${id}" ${checked?'checked':''}
            onchange="updateSettingLocal('${f.cle}',this.checked)">
          <span class="toggle-thumb"></span>
        </label>
      </div>
    </div>`;
  }

  if (f.type === 'select') {
    return `<div class="sfield ${fullClass}">
      <label>${f.label}</label>
      <select id="${id}" onchange="updateSettingLocal('${f.cle}',this.value)">
        ${(f.options||[]).map(o => `<option value="${o}" ${val===o?'selected':''}>${o}</option>`).join('')}
      </select>
    </div>`;
  }

  if (f.type === 'textarea') {
    return `<div class="sfield ${fullClass}">
      <label>${f.label}</label>
      <textarea id="${id}" rows="2" onchange="updateSettingLocal('${f.cle}',this.value)">${val}</textarea>
    </div>`;
  }

  return `<div class="sfield ${fullClass}">
    <label>${f.label}</label>
    <input type="${f.type}" id="${id}" value="${val}" ${f.step?`step="${f.step}"`:''}
      onchange="updateSettingLocal('${f.cle}',this.value)">
  </div>`;
}

// ── Affichage tab ─────────────────────────────────────────
function renderAffichageTab() {
  const d = _displaySettings;
  const pages = [
    {v:'dashboard',    l:'📊 Tableau de Bord'},
    {v:'orders',       l:'📋 Ordres de Fab.'},
    {v:'monitor',      l:'📡 Monitoring'},
    {v:'bl',           l:'🚚 Bons de Livraison'},
  ];
  const accents = [
    {v:'#D42B2B',c:'Rouge SOFEM (défaut)'},
    {v:'#3B82F6',c:'Bleu'},
    {v:'#22C55E',c:'Vert'},
    {v:'#F59E0B',c:'Orange'},
    {v:'#8B5CF6',c:'Violet'},
    {v:'#EC4899',c:'Rose'},
  ];

  return `
    <div style="display:flex;justify-content:flex-end;margin-bottom:1rem">
      <button class="btn" onclick="saveDisplayAll()">💾 Sauvegarder affichage</button>
    </div>

    <!-- Format -->
    <div class="scard">
      <div class="scard-head">
        <div class="scard-icon">🗓️</div>
        <div>
          <div class="scard-title">Format & Localisation</div>
          <div class="scard-desc">Format des dates, nombres et devises</div>
        </div>
      </div>
      <div class="sfgrid">
        <div class="sfield">
          <label>Format de date</label>
          <select id="d-date-format" onchange="_displaySettings.date_format=this.value;updateDatePreview()">
            <option value="DD/MM/YYYY" ${d.date_format==='DD/MM/YYYY'?'selected':''}>DD/MM/YYYY (19/03/2026)</option>
            <option value="YYYY-MM-DD" ${d.date_format==='YYYY-MM-DD'?'selected':''}>YYYY-MM-DD (2026-03-19)</option>
            <option value="DD MMM YYYY" ${d.date_format==='DD MMM YYYY'?'selected':''}>DD MMM YYYY (19 Mars 2026)</option>
          </select>
          <div id="date-preview" style="margin-top:6px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--accent)">
            Aperçu: ${formatDate(new Date(), d.date_format)}
          </div>
        </div>
        <div class="sfield">
          <label>Format des nombres</label>
          <select id="d-number-format" onchange="_displaySettings.number_format=this.value;updateNumberPreview()">
            <option value="FR" ${d.number_format==='FR'?'selected':''}>Français — 1 234,56</option>
            <option value="EN" ${d.number_format==='EN'?'selected':''}>International — 1,234.56</option>
          </select>
          <div id="number-preview" style="margin-top:6px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--accent)">
            Aperçu: ${formatNumber(1234.567, d.number_format)} TND
          </div>
        </div>
        <div class="sfield">
          <label>Position devise</label>
          <select id="d-currency-pos" onchange="_displaySettings.currency_position=this.value">
            <option value="after"  ${d.currency_position==='after'? 'selected':''}>Après — 1 500 TND</option>
            <option value="before" ${d.currency_position==='before'?'selected':''}>Avant — TND 1 500</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Tableau de bord -->
    <div class="scard">
      <div class="scard-head">
        <div class="scard-icon">📊</div>
        <div>
          <div class="scard-title">Tableau de Bord</div>
          <div class="scard-desc">Comportement de la page principale</div>
        </div>
      </div>
      <div class="sfgrid">
        <div class="sfield">
          <label>OFs récents affichés</label>
          <input type="range" id="d-of-count" min="3" max="20" value="${d.dash_of_count}"
            oninput="$('of-count-val').textContent=this.value;_displaySettings.dash_of_count=parseInt(this.value)"
            style="width:100%;accent-color:var(--red);margin-top:8px">
          <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--muted);margin-top:4px">
            <span>3</span><span id="of-count-val" style="color:var(--red);font-weight:600">${d.dash_of_count}</span><span>20</span>
          </div>
        </div>
        <div class="sfield">
          <label>Auto-actualisation monitoring (secondes)</label>
          <input type="range" id="d-refresh" min="0" max="60" step="5" value="${d.auto_refresh_sec}"
            oninput="$('refresh-val').textContent=this.value==0?'Désactivé':this.value+'s';_displaySettings.auto_refresh_sec=parseInt(this.value)"
            style="width:100%;accent-color:var(--red);margin-top:8px">
          <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--muted);margin-top:4px">
            <span>Off</span><span id="refresh-val" style="color:var(--red);font-weight:600">${d.auto_refresh_sec===0?'Désactivé':d.auto_refresh_sec+'s'}</span><span>60s</span>
          </div>
        </div>
        <div class="sfield">
          <label>Page par défaut au login</label>
          <select id="d-default-page" onchange="_displaySettings.default_page=this.value">
            ${pages.map(p => `<option value="${p.v}" ${d.default_page===p.v?'selected':''}>${p.l}</option>`).join('')}
          </select>
        </div>
        <div class="sfield">
          <label>Durée des notifications (secondes)</label>
          <input type="range" id="d-toast" min="1" max="10" value="${d.toast_duration}"
            oninput="$('toast-val').textContent=this.value+'s';_displaySettings.toast_duration=parseInt(this.value)"
            style="width:100%;accent-color:var(--red);margin-top:8px">
          <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--muted);margin-top:4px">
            <span>1s</span><span id="toast-val" style="color:var(--red);font-weight:600">${d.toast_duration}s</span><span>10s</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Colonnes OF -->
    <div class="scard">
      <div class="scard-head">
        <div class="scard-icon">📋</div>
        <div>
          <div class="scard-title">Colonnes — Liste des OFs</div>
          <div class="scard-desc">Choisir les colonnes visibles dans le tableau des ordres de fabrication</div>
        </div>
      </div>
      <div class="sfgrid">
        ${[
          {k:'show_bl_col',     l:'Colonne BL (Bon de Livraison)'},
          {k:'show_chef_col',   l:'Colonne Chef Atelier'},
          {k:'show_client_col', l:'Colonne Client'},
          {k:'compact_table',   l:'Mode compact (lignes réduites)'},
        ].map(item => {
          const checked = d[item.k];
          return `<div class="stoggle">
            <label for="d-${item.k}" style="cursor:pointer">${item.l}</label>
            <div class="toggle-wrap">
              <label class="toggle-track">
                <input type="checkbox" id="d-${item.k}" ${checked?'checked':''}
                  onchange="_displaySettings['${item.k}']=this.checked">
                <span class="toggle-thumb"></span>
              </label>
            </div>
          </div>`;
        }).join('')}
      </div>
    </div>

    <!-- Thème -->
    <div class="scard">
      <div class="scard-head">
        <div class="scard-icon">🌓</div>
        <div>
          <div class="scard-title">Thème de l'Interface</div>
          <div class="scard-desc">Basculer entre le mode sombre et le mode clair</div>
        </div>
      </div>
      <div style="display:flex;gap:1rem;padding:.25rem 0">
        <!-- Dark mode card -->
        <div onclick="setTheme('dark')" style="flex:1;cursor:pointer;border-radius:10px;overflow:hidden;
          border:3px solid ${d.theme==='dark'?'var(--red)':'var(--border)'};transition:all .2s">
          <div style="background:#0E0F11;padding:1rem;display:flex;flex-direction:column;gap:6px">
            <div style="height:8px;border-radius:4px;background:#1C1F25;width:60%"></div>
            <div style="height:8px;border-radius:4px;background:#1C1F25;width:80%"></div>
            <div style="height:8px;border-radius:4px;background:#D42B2B;width:40%"></div>
          </div>
          <div style="background:#14161A;padding:.5rem .75rem;display:flex;align-items:center;
            justify-content:space-between;border-top:1px solid rgba(255,255,255,0.07)">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#E8E9EB">🌙 Mode Sombre</span>
            ${d.theme==='dark'?'<span style="color:var(--red);font-size:14px">✓</span>':''}
          </div>
        </div>
        <!-- Light mode card -->
        <div onclick="setTheme('light')" style="flex:1;cursor:pointer;border-radius:10px;overflow:hidden;
          border:3px solid ${d.theme==='light'?'var(--red)':'var(--border)'};transition:all .2s">
          <div style="background:#F3F4F6;padding:1rem;display:flex;flex-direction:column;gap:6px">
            <div style="height:8px;border-radius:4px;background:#E5E7EB;width:60%"></div>
            <div style="height:8px;border-radius:4px;background:#E5E7EB;width:80%"></div>
            <div style="height:8px;border-radius:4px;background:#D42B2B;width:40%"></div>
          </div>
          <div style="background:#FFFFFF;padding:.5rem .75rem;display:flex;align-items:center;
            justify-content:space-between;border-top:1px solid rgba(0,0,0,0.08)">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#111827">☀️ Mode Clair</span>
            ${d.theme==='light'?'<span style="color:var(--red);font-size:14px">✓</span>':''}
          </div>
        </div>
      </div>
    </div>

    <!-- Couleur accent -->
    <div class="scard">
      <div class="scard-head">
        <div class="scard-icon">🎨</div>
        <div>
          <div class="scard-title">Couleur d'Accentuation</div>
          <div class="scard-desc">Couleur principale de l'interface — nécessite un rechargement</div>
        </div>
      </div>
      <div style="display:flex;gap:.75rem;flex-wrap:wrap;padding:.25rem 0">
        ${accents.map(a => `
          <div onclick="setAccentColor('${a.v}')" title="${a.c}"
            style="width:44px;height:44px;border-radius:10px;background:${a.v};cursor:pointer;
              border:3px solid ${d.accent_color===a.v?'#fff':'transparent'};
              box-shadow:${d.accent_color===a.v?'0 0 0 2px '+a.v:'none'};
              transition:all .15s;display:flex;align-items:center;justify-content:center">
            ${d.accent_color===a.v?'<span style="color:#fff;font-size:18px">✓</span>':''}
          </div>`).join('')}
        <div style="display:flex;align-items:center;gap:.5rem;margin-left:.5rem">
          <input type="color" value="${d.accent_color}"
            oninput="setAccentColor(this.value)"
            style="width:44px;height:44px;border:none;background:none;cursor:pointer;border-radius:8px">
          <span style="font-size:10px;color:var(--muted)">Personnalisé</span>
        </div>
      </div>
      <div style="margin-top:.75rem;padding:.5rem .75rem;background:var(--bg3);border-radius:6px;font-size:11px;color:var(--muted)">
        ℹ️ La couleur s'applique immédiatement. Rechargez la page pour un rendu complet.
      </div>
    </div>
  `;
}

// ── Tab switching ─────────────────────────────────────────
function switchSettingsTab(tab) {
  _activeTab = tab;
  document.querySelectorAll('.stab').forEach(b => b.classList.remove('stab-active'));
  event.target.classList.add('stab-active');
  document.getElementById('stab-systeme').style.display      = tab === 'systeme'      ? 'block' : 'none';
  document.getElementById('stab-affichage').style.display    = tab === 'affichage'    ? 'block' : 'none';
  document.getElementById('stab-utilisateurs').style.display = tab === 'utilisateurs' ? 'block' : 'none';
  if (tab === 'utilisateurs') loadSettingsUsers();
}

// ── Helpers ───────────────────────────────────────────────
function formatDate(d, fmt) {
  const dd   = String(d.getDate()).padStart(2,'0');
  const mm   = String(d.getMonth()+1).padStart(2,'0');
  const yyyy = d.getFullYear();
  const months = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc'];
  if (fmt === 'YYYY-MM-DD')  return `${yyyy}-${mm}-${dd}`;
  if (fmt === 'DD MMM YYYY') return `${dd} ${months[d.getMonth()]} ${yyyy}`;
  return `${dd}/${mm}/${yyyy}`;
}

function formatNumber(n, fmt) {
  if (fmt === 'EN') return n.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:3});
  return n.toLocaleString('fr-FR', {minimumFractionDigits:2, maximumFractionDigits:3});
}

function updateDatePreview() {
  const el = $('date-preview');
  if (el) el.textContent = 'Aperçu: ' + formatDate(new Date(), _displaySettings.date_format);
}

function updateNumberPreview() {
  const el = $('number-preview');
  if (el) el.textContent = 'Aperçu: ' + formatNumber(1234.567, _displaySettings.number_format) + ' TND';
}

function setTheme(theme) {
  _displaySettings.theme = theme;
  document.documentElement.setAttribute('data-theme', theme);
  saveDisplaySettings();
  // Re-render to update card borders
  renderSettingsPage();
  toast(theme === 'dark' ? '🌙 Mode Sombre activé' : '☀️ Mode Clair activé');
}

function setAccentColor(color) {
  _displaySettings.accent_color = color;
  document.documentElement.style.setProperty('--red', color);
  document.documentElement.style.setProperty('--red-d', color);
  renderSettingsPage(); // re-render to update checked state
}

// ── Save functions ────────────────────────────────────────
function updateSettingLocal(cle, val) {
  _settings[cle] = val;
}

async function saveGroup(groupe) {
  const meta = SYSTEM_GROUPS[groupe];
  if (!meta) return;
  const updates = {};
  meta.fields.forEach(f => {
    const el = $(`stg-${f.cle}`);
    if (!el) return;
    updates[f.cle] = f.type === 'boolean' ? (el.checked ? 'true' : 'false') : el.value;
  });
  try {
    await api('/api/settings/bulk', 'PUT', { settings: updates });
    toast(`${meta.icon} ${meta.label} sauvegardé ✓`);
  } catch(e) { toast(e.message, 'err'); }
}

async function saveAllSettings() {
  const updates = {};
  Object.values(SYSTEM_GROUPS).forEach(meta => {
    meta.fields.forEach(f => {
      const el = $(`stg-${f.cle}`);
      if (!el) return;
      updates[f.cle] = f.type === 'boolean' ? (el.checked ? 'true' : 'false') : el.value;
    });
  });
  try {
    await api('/api/settings/bulk', 'PUT', { settings: updates });
    toast('✅ Tous les paramètres système sauvegardés');
  } catch(e) { toast(e.message, 'err'); }
}

function saveDisplayAll() {
  // Collect all display values from DOM
  ['date_format','number_format','currency_position','default_page'].forEach(k => {
    const el = $(`d-${k.replace('_','-')}`);
    if (el) _displaySettings[k] = el.value;
  });
  ['dash_of_count','auto_refresh_sec','toast_duration'].forEach(k => {
    const el = $(`d-${k.replace(/_/g,'-')}`);
    if (el) _displaySettings[k] = parseInt(el.value);
  });
  ['show_bl_col','show_chef_col','show_client_col','compact_table'].forEach(k => {
    const el = $(`d-${k}`);
    if (el) _displaySettings[k] = el.checked;
  });
  saveDisplaySettings();
  toast('🖥️ Paramètres d\'affichage sauvegardés ✓');
  // Apply accent color permanently
  document.documentElement.style.setProperty('--red', _displaySettings.accent_color);
}

// Apply display settings on page load
function applyDisplaySettings() {
  loadDisplaySettings();
  const d = _displaySettings;
  // Apply theme
  document.documentElement.setAttribute('data-theme', d.theme || 'dark');
  if (d.accent_color && d.accent_color !== '#D42B2B') {
    document.documentElement.style.setProperty('--red', d.accent_color);
    document.documentElement.style.setProperty('--red-d', d.accent_color);
  }
}

// Call on init
applyDisplaySettings();
// ── Utilisateurs tab ──────────────────────────────────────
let _settingsUsers = [];
let _settingsOps   = [];

function renderUtilisateursTab() {
  return `
    <div class="scard">
      <div class="scard-head">
        <div class="scard-icon" style="background:rgba(212,43,43,.15)">🔐</div>
        <div>
          <div class="scard-title">Gestion des Utilisateurs</div>
          <div class="scard-desc">Ajouter, modifier le PIN, changer le rôle, activer/désactiver</div>
        </div>
        <button class="btn btn-sm" style="margin-left:auto" onclick="openAddUserInline()">+ Ajouter</button>
      </div>

      <!-- Add user form (hidden by default) -->
      <div id="add-user-form" style="display:none;background:var(--bg3);border:1px solid var(--border);
        border-radius:8px;padding:1rem;margin-bottom:1rem">
        <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--red);
          letter-spacing:2px;text-transform:uppercase;margin-bottom:.75rem">NOUVEL UTILISATEUR</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem;margin-bottom:.75rem">
          <div class="fg"><label>Prénom *</label><input id="su-prenom" type="text" placeholder="Prénom"></div>
          <div class="fg"><label>Nom *</label><input id="su-nom" type="text" placeholder="Nom"></div>
          <div class="fg"><label>Rôle *</label>
            <select id="su-role">
              <option value="OPERATOR">Opérateur</option>
              <option value="MANAGER">Manager</option>
              <option value="ADMIN">Admin</option>
            </select>
          </div>
          <div class="fg"><label>PIN (4 chiffres) *</label>
            <input id="su-pin" type="password" maxlength="4" placeholder="••••"
              style="font-size:20px;letter-spacing:6px;text-align:center"></div>
          <div class="fg" style="grid-column:1/-1"><label>Opérateur lié</label>
            <select id="su-op"><option value="">— Aucun —</option></select>
          </div>
        </div>
        <div style="display:flex;gap:.5rem;justify-content:flex-end">
          <button class="btn btn-ghost btn-sm" onclick="closeAddUserInline()">Annuler</button>
          <button class="btn btn-sm" onclick="saveSettingsUser()">Créer utilisateur</button>
        </div>
      </div>

      <!-- Users table -->
      <div class="tw">
        <table>
          <thead><tr>
            <th>Utilisateur</th><th>Rôle</th><th>Opérateur lié</th><th>Statut</th>
            <th>PIN</th><th>Actions</th>
          </tr></thead>
          <tbody id="su-table"><tr><td colspan="6" class="loading"><div class="spin"></div></td></tr></tbody>
        </table>
      </div>
    </div>

    <!-- Suggestions card -->
    <div class="scard">
      <div class="scard-head">
        <div class="scard-icon" style="background:rgba(59,130,246,.15)">💡</div>
        <div>
          <div class="scard-title">Bonnes Pratiques Sécurité</div>
          <div class="scard-desc">Recommandations pour la gestion des accès</div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem">
        ${[
          ['🔑','PIN unique par utilisateur','Ne pas partager les codes PIN entre collègues'],
          ['👤','Un compte par personne','Éviter les comptes génériques partagés'],
          ['🔒','Désactiver les comptes inactifs','Retirer les accès dès qu\'un employé quitte'],
          ['📋','Rôles minimaux','Donner uniquement les droits nécessaires à chaque rôle'],
          ['🔄','Changer les PINs régulièrement','Recommandé tous les 3 mois'],
          ['👁','Surveiller les connexions','Vérifier les logs d\'accès périodiquement'],
        ].map(([icon,title,desc]) => `
          <div style="display:flex;gap:.6rem;padding:.6rem;background:var(--bg3);border-radius:6px">
            <span style="font-size:16px;flex-shrink:0">${icon}</span>
            <div>
              <div style="font-size:11px;font-weight:600;margin-bottom:2px">${title}</div>
              <div style="font-size:10px;color:var(--muted)">${desc}</div>
            </div>
          </div>`).join('')}
      </div>
    </div>
  `;
}

async function loadSettingsUsers() {
  try {
    const [users, ops] = await Promise.all([api('/api/auth/users'), api('/api/operateurs')]);
    _settingsUsers = users || [];
    _settingsOps   = ops   || [];

    // Populate operator select in add form
    const suOp = $('su-op');
    if (suOp) {
      suOp.innerHTML = '<option value="">— Aucun —</option>' +
        _settingsOps.map(o => `<option value="${o.id}">${o.prenom} ${o.nom} (${o.specialite||'—'})</option>`).join('');
    }

    const roleColors = { ADMIN:'b-admin', MANAGER:'b-manager', OPERATOR:'b-operator' };
    const roleLabels = { ADMIN:'Admin', MANAGER:'Manager', OPERATOR:'Opérateur' };

    const tbody = $('su-table');
    if (!tbody) return;

    tbody.innerHTML = !_settingsUsers.length
      ? `<tr><td colspan="6" class="empty">Aucun utilisateur</td></tr>`
      : _settingsUsers.map(u => {
        const op = _settingsOps.find(o => o.id === u.operateur_id);
        const rc = roleColors[u.role] || 'b-draft';
        const rl = roleLabels[u.role] || u.role;
        const init = (u.prenom?.[0]||'') + (u.nom?.[0]||'');
        return `<tr id="su-row-${u.id}">
          <td>
            <div style="display:flex;align-items:center;gap:.6rem">
              <div style="width:28px;height:28px;border-radius:50%;background:var(--red-g);border:1px solid var(--red);
                display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:600;
                color:var(--red);flex-shrink:0">${init}</div>
              <div>
                <div style="font-size:12px;font-weight:500">${u.prenom} ${u.nom}</div>
              </div>
            </div>
          </td>
          <td>
            <select onchange="changeUserRole(${u.id}, this.value)"
              style="background:var(--bg3);border:1px solid var(--border);border-radius:4px;
                padding:3px 6px;color:var(--text);font-size:10px;font-family:'IBM Plex Mono',monospace">
              <option value="OPERATOR" ${u.role==='OPERATOR'?'selected':''}>Opérateur</option>
              <option value="MANAGER"  ${u.role==='MANAGER' ?'selected':''}>Manager</option>
              <option value="ADMIN"    ${u.role==='ADMIN'   ?'selected':''}>Admin</option>
            </select>
          </td>
          <td style="font-size:11px;color:var(--muted)">${op ? `${op.prenom} ${op.nom}` : '—'}</td>
          <td>${u.actif
            ? '<span class="badge b-completed">ACTIF</span>'
            : '<span class="badge b-draft">INACTIF</span>'}</td>
          <td>
            <button class="fbtn" onclick="changePinInline(${u.id},'${u.prenom} ${u.nom}')"
              title="Modifier PIN" style="color:var(--accent)">🔑 PIN</button>
          </td>
          <td style="display:flex;gap:4px">
            ${u.actif
              ? `<button class="fbtn" style="color:var(--red)" onclick="toggleUserActive(${u.id},false)">Désactiver</button>`
              : `<button class="fbtn" style="color:var(--green)" onclick="toggleUserActive(${u.id},true)">Activer</button>`
            }
          </td>
        </tr>`;
      }).join('');
  } catch(e) { toast('Erreur chargement utilisateurs: '+e.message,'err'); }
}

function openAddUserInline() {
  const f = $('add-user-form');
  if (f) { f.style.display = 'block'; $('su-prenom')?.focus(); }
}

function closeAddUserInline() {
  const f = $('add-user-form');
  if (f) { f.style.display = 'none'; }
  ['su-prenom','su-nom','su-pin'].forEach(id => { const el=$(id); if(el) el.value=''; });
  if ($('su-role')) $('su-role').value = 'OPERATOR';
  if ($('su-op'))   $('su-op').value   = '';
}

async function saveSettingsUser() {
  const prenom = $('su-prenom')?.value?.trim();
  const nom    = $('su-nom')?.value?.trim();
  const pin    = $('su-pin')?.value?.trim();
  const role   = $('su-role')?.value;
  const op_id  = $('su-op')?.value;

  if (!prenom || !nom) { toast('Prénom et nom requis','err'); return; }
  if (!pin || pin.length !== 4 || !/^\d{4}$/.test(pin)) {
    toast('PIN doit être exactement 4 chiffres','err'); return;
  }
  try {
    await api('/api/auth/users','POST',{
      prenom, nom, role, pin,
      operateur_id: op_id ? parseInt(op_id) : null
    });
    toast(`Utilisateur ${prenom} ${nom} créé ✓`);
    closeAddUserInline();
    loadSettingsUsers();
  } catch(e) { toast(e.message,'err'); }
}

async function changeUserRole(userId, newRole) {
  try {
    await api(`/api/auth/users/${userId}`, 'PUT', { role: newRole });
    const labels = { ADMIN:'Admin', MANAGER:'Manager', OPERATOR:'Opérateur' };
    toast(`Rôle mis à jour → ${labels[newRole]||newRole} ✓`);
  } catch(e) {
    toast(e.message,'err');
    loadSettingsUsers(); // revert UI
  }
}

async function toggleUserActive(userId, active) {
  try {
    await api(`/api/auth/users/${userId}`, 'PUT', { actif: active });
    toast(active ? 'Utilisateur activé ✓' : 'Utilisateur désactivé');
    loadSettingsUsers();
  } catch(e) { toast(e.message,'err'); }
}

function changePinInline(userId, userName) {
  const pin = prompt(`Nouveau PIN (4 chiffres) pour ${userName}:`);
  if (pin === null) return; // cancelled
  if (!/^\d{4}$/.test(pin)) {
    toast('PIN invalide — doit être exactement 4 chiffres','err'); return;
  }
  api(`/api/auth/users/${userId}`, 'PUT', { pin })
    .then(() => toast(`PIN de ${userName} modifié ✓`))
    .catch(e => toast(e.message,'err'));
}