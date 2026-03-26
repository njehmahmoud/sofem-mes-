"""SOFEM MES v6.0 — Clients (Commit 01 — ISO 9001 soft delete)"""

from fastapi import APIRouter, Depends, HTTPException, Request
from database import get_db, q, exe, serialize, soft_delete, log_activity, cancel_document
from auth import require_any_role, require_manager_or_admin, get_current_user
from models import ClientCreate, ClientUpdate, DeactivateRequest

router = APIRouter(prefix="/api/clients", tags=["clients"])


def next_code(db) -> str:
    rows = q(db, "SELECT code FROM clients WHERE code LIKE 'CLT-%' ORDER BY id DESC LIMIT 1")
    last = 0
    if rows:
        try: last = int(rows[0]["code"].split("-")[-1])
        except: pass
    return f"CLT-{str(last+1).zfill(3)}"


@router.get("", dependencies=[Depends(require_any_role)])
def list_clients(show_inactive: bool = False, db=Depends(get_db)):
    """List clients. By default only active ones. Pass ?show_inactive=true for all."""
    if show_inactive:
        return serialize(q(db, "SELECT * FROM clients ORDER BY actif DESC, nom"))
    return serialize(q(db, "SELECT * FROM clients WHERE actif=TRUE ORDER BY nom"))


@router.get("/{cid}", dependencies=[Depends(require_any_role)])
def get_client(cid: int, db=Depends(get_db)):
    c = q(db, "SELECT * FROM clients WHERE id=%s", (cid,), one=True)
    if not c: raise HTTPException(404, "Client introuvable")
    c["ofs"] = q(db, """
        SELECT o.numero, o.statut, o.created_at, p.nom produit_nom
        FROM ordres_fabrication o JOIN produits p ON p.id=o.produit_id
        WHERE o.client_id=%s ORDER BY o.created_at DESC LIMIT 10
    """, (cid,))
    return serialize(c)


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_client(data: ClientCreate, request: Request,
                  user=Depends(get_current_user), db=Depends(get_db)):
    code = next_code(db)
    cid = exe(db, """
        INSERT INTO clients (code,nom,matricule_fiscal,adresse,ville,telephone,email,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (code, data.nom, data.matricule_fiscal, data.adresse,
          data.ville, data.telephone, data.email, data.notes))

    log_activity(
        db,
        action        = "CREATE",
        entity_type   = "CLIENT",
        entity_id     = cid,
        entity_numero = code,
        user_id       = user.get("id"),
        user_nom      = f"{user.get('prenom','')} {user.get('nom','')}".strip(),
        new_value     = data.dict(),
        detail        = f"Client {code} — {data.nom} créé",
        ip_address    = request.client.host if request.client else None,
    )
    return {"id": cid, "code": code, "message": f"Client créé — {code}"}


@router.put("/{cid}", dependencies=[Depends(require_manager_or_admin)])
def update_client(cid: int, data: ClientUpdate, request: Request,
                  user=Depends(get_current_user), db=Depends(get_db)):
    old = q(db, "SELECT * FROM clients WHERE id=%s", (cid,), one=True)
    if not old: raise HTTPException(404, "Client introuvable")

    fields, vals = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s"); vals.append(v)
    if not fields: raise HTTPException(400, "Aucune donnée")
    vals.append(cid)
    exe(db, f"UPDATE clients SET {','.join(fields)} WHERE id=%s", vals)

    log_activity(
        db,
        action        = "UPDATE",
        entity_type   = "CLIENT",
        entity_id     = cid,
        entity_numero = old.get("code"),
        user_id       = user.get("id"),
        user_nom      = f"{user.get('prenom','')} {user.get('nom','')}".strip(),
        old_value     = {f: old.get(f) for f in data.dict(exclude_none=True).keys()},
        new_value     = data.dict(exclude_none=True),
        detail        = f"Client {old.get('code')} mis à jour",
        ip_address    = request.client.host if request.client else None,
    )
    return {"message": "Client mis à jour"}


@router.delete("/{cid}", dependencies=[Depends(require_manager_or_admin)])
def deactivate_client(cid: int, data: DeactivateRequest,
                      request: Request, user=Depends(get_current_user),
                      db=Depends(get_db)):
    """
    ISO 9001 — clients are never physically deleted.
    They are deactivated with an optional reason.
    Clients linked to OFs cannot be deactivated.
    """
    client = q(db, "SELECT * FROM clients WHERE id=%s", (cid,), one=True)
    if not client: raise HTTPException(404, "Client introuvable")
    if not client.get("actif"): raise HTTPException(400, "Client déjà inactif")

    # Safety check — cannot deactivate if active OFs exist
    active_ofs = q(db, """
        SELECT COUNT(*) n FROM ordres_fabrication
        WHERE client_id=%s AND statut NOT IN ('COMPLETED','CANCELLED')
    """, (cid,), one=True)
    if active_ofs and active_ofs["n"] > 0:
        raise HTTPException(400,
            f"Client lié à {active_ofs['n']} OF(s) actif(s) — impossible de désactiver")

    soft_delete(
        db,
        table         = "clients",
        record_id     = cid,
        user_id       = user.get("id"),
        user_nom      = f"{user.get('prenom','')} {user.get('nom','')}".strip(),
        reason        = data.reason,
        entity_type   = "CLIENT",
        entity_numero = client.get("code"),
    )
    return {"message": f"Client {client.get('code')} désactivé"}