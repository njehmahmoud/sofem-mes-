// ── users.js ─────────────────────────────────────────────
async function loadUsers() {
  try {
    const [users, ops] = await Promise.all([api('/api/auth/users'), api('/api/operateurs')]);
    $('users-tb').innerHTML = (users||[]).length===0 ? empty(6) : users.map(u => {
      const op = (ops||[]).find(o=>o.id===u.operateur_id);
      const rb = {ADMIN:'b-admin',MANAGER:'b-manager',OPERATOR:'b-operator'}[u.role]||'b-draft';
      return `<tr>
        <td style="font-weight:500">${u.nom}</td><td>${u.prenom}</td>
        <td><span class="badge ${rb}">${u.role}</span></td>
        <td style="font-size:10px;color:var(--muted)">${op?`${op.prenom} ${op.nom}`:'—'}</td>
        <td>${u.actif?'<span class="badge b-completed">ACTIF</span>':'<span class="badge b-cancelled">INACTIF</span>'}</td>
        <td><button class="btn btn-ghost btn-sm" style="color:var(--red)" onclick="deactivateUser(${u.id})">Désactiver</button></td>
      </tr>`;
    }).join('');
    $('usr-op').innerHTML = '<option value="">— Aucun —</option>' +
      (ops||[]).map(o=>`<option value="${o.id}">${o.prenom} ${o.nom} (${o.specialite})</option>`).join('');
  } catch(e) { toast('Erreur users: '+e.message,'err'); }
}

async function saveUser() {
  if (!$('usr-prenom').value||!$('usr-nom').value||!$('usr-pin').value) {
    toast('Champs obligatoires manquants','err'); return;
  }
  if ($('usr-pin').value.length !== 4) { toast('PIN doit être 4 chiffres','err'); return; }
  try {
    await api('/api/auth/users','POST',{
      prenom: $('usr-prenom').value, nom: $('usr-nom').value,
      role: $('usr-role').value, pin: $('usr-pin').value,
      operateur_id: $('usr-op').value ? parseInt($('usr-op').value) : null
    });
    toast('Utilisateur créé ✓'); closeModal('m-user'); loadUsers();
  } catch(e) { toast(e.message,'err'); }
}

async function deactivateUser(id) {
  if (!confirm('Désactiver cet utilisateur ?')) return;
  try { await api(`/api/auth/users/${id}`,'PUT',{actif:false}); toast('Désactivé'); loadUsers(); }
  catch(e) { toast(e.message,'err'); }
}
