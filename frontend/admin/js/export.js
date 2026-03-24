// ── export.js — SOFEM MES v6.0 ───────────────────────────
// CSV/Excel export for analytics and tables

function exportToCSV(data, filename) {
  if (!data?.length) { toast('Aucune donnée à exporter', 'err'); return; }
  const headers = Object.keys(data[0]);
  const rows = [
    headers.join(';'),
    ...data.map(row => headers.map(h => {
      const v = row[h] ?? '';
      return String(v).includes(';') ? `"${v}"` : v;
    }).join(';'))
  ];
  const blob = new Blob(['\uFEFF' + rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = filename + '_' + new Date().toISOString().slice(0,10) + '.csv';
  a.click(); URL.revokeObjectURL(url);
  toast(`Export ${filename}.csv téléchargé ✓`);
}

async function exportAnalyticsProduction() {
  const d = await api('/api/analytics/production');
  exportToCSV(d?.par_mois || [], 'analytics_production_mois');
}
async function exportAnalyticsAchats() {
  const d = await api('/api/analytics/achats');
  exportToCSV(d?.stock || [], 'analytics_stock_materiaux');
}
async function exportAnalyticsOperateurs() {
  const d = await api('/api/analytics/operateurs');
  exportToCSV((d?.performance||[]).map(o => ({
    prenom: o.prenom, nom: o.nom, specialite: o.specialite, role: o.role,
    ops_terminees: o.ops_terminees, duree_totale_min: o.duree_totale_min,
    ofs_impliques: o.ofs_impliques, taux_horaire: o.taux_horaire,
  })), 'analytics_operateurs');
}
async function exportAnalyticsQualite() {
  const d = await api('/api/analytics/qualite');
  exportToCSV(d?.nc_ouvertes || [], 'analytics_nc_ouvertes');
}

// Generic table export
function exportTable(tableId, filename) {
  const table = document.getElementById(tableId)?.closest('table');
  if (!table) { toast('Table introuvable', 'err'); return; }
  const rows = [];
  const headers = [...table.querySelectorAll('thead th')].map(th => th.textContent.trim());
  rows.push(headers.join(';'));
  table.querySelectorAll('tbody tr').forEach(tr => {
    const cells = [...tr.querySelectorAll('td')].map(td => {
      const v = td.textContent.trim().replace(/\s+/g, ' ');
      return v.includes(';') ? `"${v}"` : v;
    });
    if (cells.length) rows.push(cells.join(';'));
  });
  const blob = new Blob(['\uFEFF' + rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a'); a.href = url;
  a.download = filename + '_' + new Date().toISOString().slice(0,10) + '.csv';
  a.click(); URL.revokeObjectURL(url);
  toast('Export CSV téléchargé ✓');
}