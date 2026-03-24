// ── planning.js ─────────────────────────────────────────

let _planningOFs = [];

const STATUS_COLOR = {
  DRAFT:       '#6B7280',
  APPROVED:    '#3B82F6',
  IN_PROGRESS: '#F59E0B',
  COMPLETED:   '#22C55E',
  CANCELLED:   '#EF4444',
};
const STATUS_LABEL = {
  DRAFT:       'Brouillon',
  APPROVED:    'Approuvé',
  IN_PROGRESS: 'En cours',
  COMPLETED:   'Terminé',
  CANCELLED:   'Annulé',
};
const PRIO_LABEL = { LOW:'Basse', NORMAL:'Normale', HIGH:'Haute', URGENT:'URGENT' };

async function loadPlanning(){
  const [rows, ofs, machines, ops] = await Promise.all([
    api('/api/planning'),
    api('/api/of'),
    api('/api/machines'),
    api('/api/operateurs')
  ]);
  if(!rows) return;

  _planningOFs = (ofs||[]).filter(o => !['COMPLETED','CANCELLED'].includes(o.statut));

  if (machines && $('pl-machine')) $('pl-machine').innerHTML = '<option value="">— Aucune —</option>' +
    machines.filter(m=>m.statut==='OPERATIONNELLE').map(m=>`<option value="${m.id}">${m.nom} · ${m.atelier}</option>`).join('');
  if (ops && $('pl-op')) $('pl-op').innerHTML = '<option value="">— Aucun —</option>' +
    ops.map(o=>`<option value="${o.id}">${o.prenom} ${o.nom}${o.specialite?' ('+o.specialite+')':''}</option>`).join('');

  // Gantt
  const ganttHTML = rows.length === 0
    ? '<div style="color:var(--muted);font-size:12px;padding:1rem">Aucun créneau planifié.</div>'
    : (() => {
        const dates = rows.flatMap(r=>[new Date(r.date_debut),new Date(r.date_fin)]);
        const minD = new Date(Math.min(...dates)), maxD = new Date(Math.max(...dates));
        const totalMs = maxD - minD || 1;
        const colors = ['#D42B2B','#3B82F6','#22C55E','#F59E0B','#8B5CF6','#EC4899'];
        return `<div style="font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:1px;color:var(--muted);text-transform:uppercase;margin-bottom:.75rem">Gantt — Planning Production</div>
        <div style="position:relative;min-height:${rows.length*36+20}px">
          ${rows.map((r,i)=>{
            const left  = ((new Date(r.date_debut)-minD)/totalMs*100).toFixed(1);
            const width = Math.max(((new Date(r.date_fin)-new Date(r.date_debut))/totalMs*100).toFixed(1),1);
            const color = colors[i%colors.length];
            return `<div style="position:absolute;top:${i*36}px;left:0;right:0;height:28px">
              <div style="position:absolute;left:${left}%;width:${width}%;height:100%;background:${color}22;border:1px solid ${color};border-radius:4px;display:flex;align-items:center;padding:0 6px;overflow:hidden;cursor:default"
                title="${r.of_numero} | ${r.machine_nom||''} | ${r.date_debut} → ${r.date_fin}">
                <span style="font-size:10px;color:${color};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${r.of_numero}${r.machine_nom?' · '+r.machine_nom:''}</span>
              </div>
            </div>`;
          }).join('')}
        </div>`;
      })();
  $('planning-gantt').innerHTML = `<div style="padding:1rem">${ganttHTML}</div>`;

  const sMap = {PLANIFIE:'b-draft',EN_COURS:'b-inprogress',TERMINE:'b-completed',ANNULE:'b-cancelled'};
  $('planning-table').innerHTML = `
    <table><thead><tr><th>OF</th><th>Produit</th><th>Machine</th><th>Opérateur</th><th>Début</th><th>Fin</th><th>Statut</th><th></th></tr></thead>
    <tbody>${rows.map(r=>`<tr>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${r.of_numero}</td>
      <td style="font-size:11px">${r.produit_nom||'—'}</td>
      <td style="font-size:11px">${r.machine_nom||'—'}</td>
      <td style="font-size:11px">${r.operateur_prenom?r.operateur_prenom+' '+r.operateur_nom:'—'}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${r.date_debut?.replace('T',' ').slice(0,16)||'—'}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:10px">${r.date_fin?.replace('T',' ').slice(0,16)||'—'}</td>
      <td><span class="badge ${sMap[r.statut]||'b-draft'}">${r.statut}</span></td>
      <td><button class="fbtn" style="color:var(--red)" onclick="deletePlanning(${r.id})">✕</button></td>
    </tr>`).join('')}</tbody></table>`;
}

// ── OF Card Picker ────────────────────────────────────────

function openOFPicker(){
  $('of-picker-search').value = '';
  renderOFCards(_planningOFs);
  $('modal-of-picker').classList.add('open');
  setTimeout(()=>$('of-picker-search').focus(), 100);
}

function closeOFPicker(){
  $('modal-of-picker').classList.remove('open');
}

function filterOFPicker(q){
  const s = q.toLowerCase();
  const filtered = _planningOFs.filter(o =>
    (o.numero||'').toLowerCase().includes(s) ||
    (o.produit_nom||'').toLowerCase().includes(s) ||
    (o.client_nom||'').toLowerCase().includes(s) ||
    (o.statut||'').toLowerCase().includes(s) ||
    (o.atelier||'').toLowerCase().includes(s)
  );
  renderOFCards(filtered);
}

function renderOFCards(ofs){
  if(!ofs.length){
    $('of-picker-list').innerHTML = `
      <div style="grid-column:1/-1;text-align:center;padding:2rem;color:var(--muted);font-size:12px">
        Aucun OF correspondant.
      </div>`;
    return;
  }
  $('of-picker-list').innerHTML = ofs.map(o => {
    const color    = STATUS_COLOR[o.statut] || '#6B7280';
    const label    = STATUS_LABEL[o.statut] || o.statut;
    const deadline = o.date_echeance ? String(o.date_echeance).slice(0,10) : '—';
    const progress = o.progression != null ? Math.round(o.progression) : null;
    const cSafe    = (o.client_nom||'').replace(/'/g,"\\'").replace(/"/g,'&quot;');
    const pSafe    = (o.produit_nom||'').replace(/'/g,"\\'").replace(/"/g,'&quot;');
    const prio     = PRIO_LABEL[o.priorite] || o.priorite || '—';
    const qte      = o.quantite || '—';
    return `
    <div onclick="selectOF(${o.id},'${o.numero}','${pSafe}','${cSafe}','${label}','${qte}','${deadline}','${prio}')"
      style="background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:.85rem 1rem;cursor:pointer;
             transition:border-color .15s,transform .1s;position:relative;overflow:hidden"
      onmouseenter="this.style.borderColor='${color}';this.style.transform='translateY(-1px)'"
      onmouseleave="this.style.borderColor='var(--border)';this.style.transform='translateY(0)'">
      <div style="position:absolute;top:0;left:0;width:3px;height:100%;background:${color};border-radius:8px 0 0 8px"></div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem;padding-left:.25rem">
        <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;color:${color}">${o.numero}</span>
        <span style="font-size:9px;font-family:'IBM Plex Mono',monospace;background:${color}22;color:${color};
                     border:1px solid ${color}44;border-radius:4px;padding:1px 6px;letter-spacing:1px">${label}</span>
      </div>
      <div style="font-size:12px;font-weight:600;color:var(--text);margin-bottom:.25rem;padding-left:.25rem;
                  white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${o.produit_nom||'—'}</div>
      <div style="display:flex;gap:.75rem;flex-wrap:wrap;padding-left:.25rem;margin-top:.4rem">
        ${o.client_nom?`<span style="font-size:10px;color:var(--muted)">👤 ${o.client_nom}</span>`:''}
        <span style="font-size:10px;color:var(--muted)">📦 Qté: <b style="color:var(--text)">${qte}</b></span>
        <span style="font-size:10px;color:var(--muted)">📅 ${deadline}</span>
        ${o.atelier?`<span style="font-size:10px;color:var(--muted)">🏭 ${o.atelier}</span>`:''}
        <span style="font-size:10px;color:var(--muted)">⚡ ${prio}</span>
      </div>
      ${progress !== null ? `
      <div style="margin-top:.6rem;padding-left:.25rem">
        <div style="background:var(--border);border-radius:4px;height:4px;overflow:hidden">
          <div style="width:${progress}%;height:100%;background:${color};border-radius:4px"></div>
        </div>
        <div style="font-size:9px;color:var(--muted);margin-top:2px;font-family:'IBM Plex Mono',monospace">${progress}% complété</div>
      </div>` : ''}
    </div>`;
  }).join('');
}

function selectOF(id, numero, produit, client, statut, qte, deadline, prio){
  $('pl-of').value = id;

  // Update picker field label
  const clientPart = client ? ` · ${client}` : '';
  $('pl-of-label').textContent = `${numero} — ${produit}${clientPart}`;
  $('pl-of-label').style.color = 'var(--text)';
  $('pl-of-label').style.fontWeight = '500';

  // Populate info preview
  $('pl-info-produit').textContent  = produit || '—';
  $('pl-info-client').textContent   = client  || '—';
  $('pl-info-qte').textContent      = qte     || '—';
  $('pl-info-deadline').textContent = deadline || '—';
  $('pl-info-prio').textContent     = prio     || '—';
  $('pl-of-info').style.display     = 'block';

  // Pre-fill start date from today if empty
  if (!$('pl-debut').value) {
    const now = new Date();
    now.setMinutes(0, 0, 0);
    $('pl-debut').value = now.toISOString().slice(0,16);
  }

  closeOFPicker();
}

// ── Open / Reset modal ────────────────────────────────────

function openPlanningModal(){
  $('pl-of').value             = '';
  $('pl-of-label').textContent = '— Cliquer pour sélectionner un OF —';
  $('pl-of-label').style.color      = 'var(--muted)';
  $('pl-of-label').style.fontWeight = 'normal';
  $('pl-of-info').style.display     = 'none';
  if($('pl-machine')) $('pl-machine').value = '';
  if($('pl-op'))      $('pl-op').value      = '';
  $('pl-debut').value = '';
  $('pl-fin').value   = '';
  $('pl-notes').value = '';
  openModal('modal-planning');
}

// ── Save ──────────────────────────────────────────────────

async function savePlanning(){
  const ofId = parseInt($('pl-of').value);
  if(!ofId){ alert('Veuillez sélectionner un OF.'); return; }
  if(!$('pl-debut').value){ alert('Date de début obligatoire.'); return; }
  if(!$('pl-fin').value)  { alert('Date de fin obligatoire.');   return; }

  const data = {
    of_id:        ofId,
    machine_id:   $('pl-machine').value ? parseInt($('pl-machine').value) : null,
    operateur_id: $('pl-op').value      ? parseInt($('pl-op').value)      : null,
    date_debut:   $('pl-debut').value.replace('T',' '),
    date_fin:     $('pl-fin').value.replace('T',' '),
    notes:        $('pl-notes').value || null
  };

  const r = await api('/api/planning','POST', data);
  if(r){
    closeModal('modal-planning');
    loadPlanning();
    // Refresh calendar so the new slot appears immediately
    if(typeof loadCalendar === 'function') loadCalendar();
  }
}

// ── Delete ────────────────────────────────────────────────

async function deletePlanning(id){
  if(!confirm('Supprimer ce créneau ?')) return;
  await api(`/api/planning/${id}`,'DELETE');
  loadPlanning();
  if(typeof loadCalendar === 'function') loadCalendar();
}