// ── calendar.js — SOFEM MES v6.0 — Vue Calendrier ────────
let _calDate  = new Date();
let _calOFs   = [];
let _calView  = 'month'; // 'month' | 'week'

const MONTH_FR = ['Janvier','Février','Mars','Avril','Mai','Juin',
                  'Juillet','Août','Septembre','Octobre','Novembre','Décembre'];
const DAY_FR   = ['Lun','Mar','Mer','Jeu','Ven','Sam','Dim'];

async function loadCalendar() {
  try {
    _calOFs = await api('/api/of?limit=200') || [];
    renderCalendar();
  } catch(e) { toast('Erreur calendrier: '+e.message,'err'); }
}

function renderCalendar() {
  const el = $('cal-container');
  if (!el) return;

  const y = _calDate.getFullYear();
  const m = _calDate.getMonth();

  // Header
  el.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;
      margin-bottom:1rem;padding:0">
      <div style="display:flex;align-items:center;gap:.75rem">
        <button class="btn btn-ghost btn-sm" onclick="calNav(-1)">‹</button>
        <div style="font-family:'Bebas Neue',sans-serif;font-size:24px;letter-spacing:2px">
          ${MONTH_FR[m]} <span style="color:var(--red)">${y}</span>
        </div>
        <button class="btn btn-ghost btn-sm" onclick="calNav(1)">›</button>
        <button class="btn btn-ghost btn-sm" onclick="calToday()">Aujourd'hui</button>
      </div>
      <div style="display:flex;gap:.4rem">
        <button class="fbtn ${_calView==='month'?'active':''}" onclick="calSetView('month')">Mois</button>
        <button class="fbtn ${_calView==='week'?'active':''}" onclick="calSetView('week')">Semaine</button>
      </div>
    </div>
    <div id="cal-legend" style="display:flex;gap:1rem;margin-bottom:.75rem;flex-wrap:wrap">
      ${[['var(--red)','URGENT'],['var(--accent)','HAUTE'],['var(--blue)','NORMALE'],
         ['var(--muted)','BASSE'],['var(--green)','TERMINÉ']].map(([c,l])=>
        `<div style="display:flex;align-items:center;gap:4px;font-size:9px;
          font-family:'IBM Plex Mono',monospace;color:var(--muted)">
          <div style="width:10px;height:10px;border-radius:2px;background:${c}"></div>${l}
        </div>`).join('')}
    </div>
    <div id="cal-grid"></div>
  `;

  _calView === 'month' ? renderMonthView(y, m) : renderWeekView();
}

function renderMonthView(y, m) {
  const grid = $('cal-grid');
  if (!grid) return;

  const firstDay = new Date(y, m, 1).getDay();
  const offset   = (firstDay + 6) % 7; // Mon=0
  const daysInM  = new Date(y, m+1, 0).getDate();
  const today    = new Date();

  let html = `<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px">`;

  // Day headers
  DAY_FR.forEach(d => {
    html += `<div style="text-align:center;font-family:'IBM Plex Mono',monospace;
      font-size:9px;color:var(--muted);padding:.4rem 0;letter-spacing:1px">${d}</div>`;
  });

  // Empty cells before month start
  for (let i = 0; i < offset; i++) {
    html += `<div style="min-height:80px;background:var(--bg3);border-radius:4px;opacity:.3"></div>`;
  }

  // Day cells
  for (let d = 1; d <= daysInM; d++) {
    const date     = new Date(y, m, d);
    const dateStr  = date.toISOString().slice(0,10);
    const isToday  = date.toDateString() === today.toDateString();
    const dayOFs   = getOFsForDate(dateStr);
    const isWkend  = date.getDay() === 0 || date.getDay() === 6;

    html += `<div style="min-height:80px;background:${isToday?'rgba(212,43,43,.1)':isWkend?'var(--bg3)':'var(--bg2)'};
      border:1px solid ${isToday?'var(--red)':'var(--border)'};border-radius:4px;
      padding:4px;overflow:hidden;cursor:${dayOFs.length?'pointer':'default'}"
      onclick="calDayClick('${dateStr}')">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;
        color:${isToday?'var(--red)':'var(--muted)'};font-weight:${isToday?700:400};
        margin-bottom:3px">${d}</div>
      ${dayOFs.slice(0,3).map(of => `
        <div style="font-size:8px;padding:1px 4px;border-radius:2px;margin-bottom:1px;
          background:${calOFColor(of)}22;color:${calOFColor(of)};
          font-family:'IBM Plex Mono',monospace;white-space:nowrap;overflow:hidden;
          text-overflow:ellipsis;max-width:100%" title="${of.produit_nom}">
          ${of.numero}
        </div>`).join('')}
      ${dayOFs.length > 3 ? `<div style="font-size:8px;color:var(--muted);padding-left:4px">+${dayOFs.length-3} autres</div>` : ''}
    </div>`;
  }

  html += '</div>';
  grid.innerHTML = html;
}

function renderWeekView() {
  const grid = $('cal-grid');
  if (!grid) return;

  // Get Monday of current week
  const day   = _calDate.getDay();
  const diff  = (day + 6) % 7;
  const mon   = new Date(_calDate); mon.setDate(_calDate.getDate() - diff);
  const days  = Array.from({length:7}, (_,i) => {
    const d = new Date(mon); d.setDate(mon.getDate()+i); return d;
  });
  const today = new Date();

  let html = `<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px">`;

  days.forEach((d, i) => {
    const dateStr  = d.toISOString().slice(0,10);
    const isToday  = d.toDateString() === today.toDateString();
    const dayOFs   = getOFsForDate(dateStr);
    const isWkend  = i >= 5;

    html += `<div style="background:${isToday?'rgba(212,43,43,.1)':isWkend?'var(--bg3)':'var(--bg2)'};
      border:1px solid ${isToday?'var(--red)':'var(--border)'};border-radius:6px;
      padding:.6rem;min-height:200px">
      <div style="text-align:center;margin-bottom:.5rem">
        <div style="font-family:'IBM Plex Mono',monospace;font-size:8px;
          color:var(--muted);letter-spacing:1px">${DAY_FR[i]}</div>
        <div style="font-family:'Bebas Neue',sans-serif;font-size:22px;
          color:${isToday?'var(--red)':'var(--text)'}">${d.getDate()}</div>
      </div>
      ${dayOFs.map(of => `
        <div onclick="openOFDetail(${of.id})" style="font-size:9px;padding:3px 6px;
          border-radius:3px;margin-bottom:3px;cursor:pointer;
          background:${calOFColor(of)}22;border-left:2px solid ${calOFColor(of)};
          color:var(--text)" title="${of.produit_nom}">
          <div style="font-family:'IBM Plex Mono',monospace;font-size:8px;
            color:${calOFColor(of)}">${of.numero}</div>
          <div style="font-size:9px;white-space:nowrap;overflow:hidden;
            text-overflow:ellipsis">${of.produit_nom}</div>
        </div>`).join('')}
      ${!dayOFs.length ? `<div style="font-size:8px;color:var(--muted);
        text-align:center;margin-top:1rem;opacity:.5">—</div>` : ''}
    </div>`;
  });

  html += '</div>';
  grid.innerHTML = html;
}

function getOFsForDate(dateStr) {
  return _calOFs.filter(of => {
    if (!of.date_echeance) return false;
    return String(of.date_echeance).slice(0,10) === dateStr;
  });
}

function calOFColor(of) {
  if (of.statut === 'COMPLETED') return 'var(--green)';
  if (of.priorite === 'URGENT')  return 'var(--red)';
  if (of.priorite === 'HAUTE')   return 'var(--accent)';
  if (of.priorite === 'NORMALE') return 'var(--blue)';
  return 'var(--muted)';
}

function calNav(dir) {
  if (_calView === 'month') {
    _calDate.setMonth(_calDate.getMonth() + dir);
  } else {
    _calDate.setDate(_calDate.getDate() + dir * 7);
  }
  _calDate = new Date(_calDate);
  renderCalendar();
}

function calToday() {
  _calDate = new Date();
  renderCalendar();
}

function calSetView(view) {
  _calView = view;
  renderCalendar();
}

function calDayClick(dateStr) {
  const ofs = getOFsForDate(dateStr);
  if (!ofs.length) return;
  if (ofs.length === 1) { navigate('orders'); return; }
  toast(`${ofs.length} OFs le ${dateStr} — voir Ordres de Fab.`);
  navigate('orders');
}

window.pageLoaders = window.pageLoaders || {};
window.pageLoaders['calendar'] = loadCalendar;
