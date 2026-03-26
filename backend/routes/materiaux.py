"""SOFEM MES v6.0 — Materiaux Routes (Commit 01 — ISO 9001 soft delete)"""

from fastapi import APIRouter, Depends, HTTPException, Request
from database import get_db, q, exe, serialize, soft_delete, log_activity, cancel_document
from auth import require_any_role, require_manager_or_admin, get_current_user
from models import MateriauCreate, MateriauUpdate, MouvementCreate, DeactivateRequest

router = APIRouter(prefix="/api/materiaux", tags=["materiaux"])


@router.get("", dependencies=[Depends(require_any_role)])
def list_materiaux(show_inactive: bool = False, db=Depends(get_db)):
    """List materials. Active only by default. Pass ?show_inactive=true for all."""
    base = "" if show_inactive else "WHERE actif=TRUE OR actif IS NULL"
    return serialize(q(db, f"""
        SELECT *,
            (stock_actuel < stock_minimum) alerte,
            ROUND(CASE WHEN stock_minimum>0 THEN stock_actuel/stock_minimum*100 ELSE 100 END,0) pct_stock
        FROM materiaux
        {base}
        ORDER BY nom
    """))


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_materiau(data: MateriauCreate, request: Request,
                    user=Depends(get_current_user), db=Depends(get_db)):
    # Auto-generate MAT-xxx code if not provided
    if not data.code:
        last = q(db, "SELECT code FROM materiaux WHERE code LIKE 'MAT-%' ORDER BY id DESC LIMIT 1", one=True)
        try:
            n = int(last["code"].split("-")[1]) + 1 if last else 1
        except: n = 1
        data.code = f"MAT-{str(n).zfill(3)}"

    mid = exe(db, """
        INSERT INTO materiaux (code,nom,unite,stock_actuel,stock_minimum,fournisseur,prix_unitaire)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (data.code, data.nom, data.unite, data.stock_actuel,
          data.stock_minimum, data.fournisseur, data.prix_unitaire))

    log_activity(
        db,
        action        = "CREATE",
        entity_type   = "MATERIAU",
        entity_id     = mid,
        entity_numero = data.code,
        user_id       = user.get("id"),
        user_nom      = f"{user.get('prenom','')} {user.get('nom','')}".strip(),
        new_value     = data.dict(),
        detail        = f"Matériau {data.code} — {data.nom} créé",
        ip_address    = request.client.host if request.client else None,
    )
    return {"id": mid, "code": data.code, "message": "Matériau créé"}


@router.post("/mouvement", dependencies=[Depends(require_any_role)])
def mouvement_stock(data: MouvementCreate, request: Request,
                    user=Depends(get_current_user), db=Depends(get_db)):
    mat = q(db, "SELECT stock_actuel, nom, code FROM materiaux WHERE id=%s", (data.materiau_id,), one=True)
    if not mat: raise HTTPException(404, "Matériau non trouvé")
    avant = float(mat["stock_actuel"])
    apres = avant + data.quantite if data.type=="ENTREE" \
        else avant - data.quantite if data.type=="SORTIE" \
        else data.quantite
    if apres < 0:
        raise HTTPException(400, f"Stock insuffisant (disponible: {avant})")

    exe(db, "UPDATE materiaux SET stock_actuel=%s WHERE id=%s", (apres, data.materiau_id))
    exe(db, """
        INSERT INTO mouvements_stock
            (materiau_id,of_id,type,quantite,stock_avant,stock_apres,motif)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (data.materiau_id, data.of_id, data.type, data.quantite, avant, apres, data.motif))

    log_activity(
        db,
        action        = "STOCK_MOVEMENT",
        entity_type   = "MATERIAU",
        entity_id     = data.materiau_id,
        entity_numero = mat.get("code"),
        user_id       = user.get("id"),
        user_nom      = f"{user.get('prenom','')} {user.get('nom','')}".strip(),
        old_value     = {"stock": avant},
        new_value     = {"stock": apres, "type": data.type, "quantite": data.quantite},
        detail        = f"{data.type} {data.quantite} — {mat.get('nom')} ({avant}→{apres})",
        ip_address    = request.client.host if request.client else None,
    )
    return {"message": "Mouvement enregistré", "stock_avant": avant, "stock_apres": apres}


@router.get("/mouvements", dependencies=[Depends(require_any_role)])
def historique(limit: int = 50, db=Depends(get_db)):
    return serialize(q(db, """
        SELECT ms.*, m.nom materiau_nom, m.unite, o.numero of_numero
        FROM mouvements_stock ms
        JOIN materiaux m ON ms.materiau_id=m.id
        LEFT JOIN ordres_fabrication o ON ms.of_id=o.id
        ORDER BY ms.created_at DESC LIMIT %s
    """, (limit,)))


@router.put("/{mat_id}", dependencies=[Depends(require_manager_or_admin)])
def update_materiau(mat_id: int, data: MateriauUpdate, request: Request,
                    user=Depends(get_current_user), db=Depends(get_db)):
    mat = q(db, "SELECT * FROM materiaux WHERE id=%s", (mat_id,), one=True)
    if not mat: raise HTTPException(404, "Matériau non trouvé")

    fields, vals = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s"); vals.append(v)
    if fields:
        vals.append(mat_id)
        exe(db, f"UPDATE materiaux SET {','.join(fields)} WHERE id=%s", vals)

    log_activity(
        db,
        action        = "UPDATE",
        entity_type   = "MATERIAU",
        entity_id     = mat_id,
        entity_numero = mat.get("code"),
        user_id       = user.get("id"),
        user_nom      = f"{user.get('prenom','')} {user.get('nom','')}".strip(),
        old_value     = {f: mat.get(f) for f in data.dict(exclude_none=True).keys()},
        new_value     = data.dict(exclude_none=True),
        detail        = f"Matériau {mat.get('code')} mis à jour",
        ip_address    = request.client.host if request.client else None,
    )
    return {"message": "Matériau mis à jour"}


@router.delete("/{mat_id}", dependencies=[Depends(require_manager_or_admin)])
def deactivate_materiau(mat_id: int, data: DeactivateRequest,
                        request: Request, user=Depends(get_current_user),
                        db=Depends(get_db)):
    """
    ISO 9001 — materiaux are never physically deleted.
    They are deactivated. Materials used in active OFs cannot be deactivated.
    """
    mat = q(db, "SELECT * FROM materiaux WHERE id=%s", (mat_id,), one=True)
    if not mat: raise HTTPException(404, "Matériau non trouvé")

    # Check active OFs
    active = q(db, """
        SELECT COUNT(*) n FROM of_bom ob
        JOIN ordres_fabrication o ON o.id = ob.of_id
        WHERE ob.materiau_id=%s AND o.statut NOT IN ('COMPLETED','CANCELLED')
    """, (mat_id,), one=True)
    if active and active["n"] > 0:
        raise HTTPException(400,
            f"Matériau utilisé dans {active['n']} OF(s) actif(s) — impossible de désactiver")

    soft_delete(
        db,
        table         = "materiaux",
        record_id     = mat_id,
        user_id       = user.get("id"),
        user_nom      = f"{user.get('prenom','')} {user.get('nom','')}".strip(),
        reason        = data.reason,
        entity_type   = "MATERIAU",
        entity_numero = mat.get("code"),
    )
    return {"message": f"Matériau {mat.get('code')} désactivé"}