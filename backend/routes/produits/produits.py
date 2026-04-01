"""SOFEM MES v6.0 — Produits CRUD"""

from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime
from database import get_db, q, exe, serialize, log_activity
from auth import require_any_role, require_manager_or_admin, get_current_user
from models import ProduitCreate, ProduitUpdate

router = APIRouter(prefix="/api/produits", tags=["produits"])


def next_code(db) -> str:
    rows = q(db, "SELECT code FROM produits WHERE code LIKE 'SOFEM-%' ORDER BY id DESC LIMIT 1")
    last = 0
    if rows:
        try: last = int(rows[0]["code"].split("-")[-1])
        except: pass
    return f"SOFEM-{str(last+1).zfill(3)}"


@router.get("", dependencies=[Depends(require_any_role)])
def list_produits(db=Depends(get_db)):
    prods = q(db, "SELECT * FROM produits ORDER BY nom")
    for p in prods:
        p["bom"] = q(db, """
            SELECT b.*, m.nom materiau_nom, m.code materiau_code, m.unite
            FROM bom b JOIN materiaux m ON m.id = b.materiau_id
            WHERE b.produit_id = %s ORDER BY m.nom
        """, (p["id"],))
    return serialize(prods)


@router.get("/{pid}", dependencies=[Depends(require_any_role)])
def get_produit(pid: int, db=Depends(get_db)):
    p = q(db, "SELECT * FROM produits WHERE id=%s", (pid,), one=True)
    if not p: raise HTTPException(404, "Produit introuvable")
    p["bom"] = q(db, """
        SELECT b.*, m.nom materiau_nom, m.code materiau_code,
               m.unite, m.stock_actuel, m.stock_minimum
        FROM bom b JOIN materiaux m ON m.id = b.materiau_id
        WHERE b.produit_id = %s ORDER BY m.nom
    """, (pid,))
    return serialize(p)


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_produit(data: ProduitCreate, db=Depends(get_db)):
    code = next_code(db)
    pid = exe(db,
        "INSERT INTO produits (code,nom,description,unite,prix_vente_ht) VALUES (%s,%s,%s,%s,%s)",
        (code, data.nom, data.description, data.unite, data.prix_vente_ht))
    return {"id": pid, "code": code, "message": f"Produit créé — {code}"}


@router.put("/{pid}", dependencies=[Depends(require_manager_or_admin)])
def update_produit(pid: int, data: ProduitUpdate, db=Depends(get_db)):
    fields, vals = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s"); vals.append(v)
    if not fields: raise HTTPException(400, "Aucune donnée")
    vals.append(pid)
    exe(db, f"UPDATE produits SET {','.join(fields)} WHERE id=%s", vals)
    return {"message": "Produit mis à jour"}


@router.delete("/{pid}", dependencies=[Depends(require_manager_or_admin)])
def delete_produit(pid: int, db=Depends(get_db)):
    if q(db, "SELECT id FROM ordres_fabrication WHERE produit_id=%s LIMIT 1", (pid,), one=True):
        raise HTTPException(400, "Produit utilisé dans des OFs")
    exe(db, "DELETE FROM produits WHERE id=%s", (pid,))
    return {"message": "Produit supprimé"}


@router.put("/{pid}/prix", dependencies=[Depends(require_manager_or_admin)])
def update_produit_price(pid: int, new_price: float = 0, reason: str = "",
                         request: Request = None, user=Depends(get_current_user),
                         db=Depends(get_db)):
    """
    Update product selling price and track change in prix_historique.
    Enables traceability of price changes for professional offeringanalysis.
    """
    prod = q(db, "SELECT * FROM produits WHERE id=%s", (pid,), one=True)
    if not prod:
        raise HTTPException(404, "Produit non trouvé")
    
    old_price = float(prod.get("prix_vente_ht", 0))
    new_price = float(new_price)
    
    if old_price == new_price:
        return {"message": "Prix identique — aucune mise à jour"}
    
    # Update product price
    exe(db, "UPDATE produits SET prix_vente_ht=%s WHERE id=%s", (new_price, pid))
    
    # Log price change in prix_historique (immutable audit trail)
    exe(db, """
        INSERT INTO prix_historique 
        (entity_type, entity_id, prix_ancien, prix_nouveau, date_changement, change_reason, changed_by)
        VALUES ('PRODUIT', %s, %s, %s, %s, %s, %s)
    """, (pid, old_price, new_price, datetime.today().date(),
          reason or "Changement de prix", user.get("id")))
    
    # Log to activity log
    log_activity(
        db,
        action        = "UPDATE",
        entity_type   = "PRODUIT_PRICE",
        entity_id     = pid,
        entity_numero = prod.get("code"),
        user_id       = user.get("id"),
        user_nom      = f"{user.get('prenom','')} {user.get('nom','')}".strip(),
        old_value     = {"prix_vente_ht": old_price},
        new_value     = {"prix_vente_ht": new_price},
        detail        = f"Prix {prod.get('code')} → {old_price} → {new_price} ({reason or 'Changement'})",
        ip_address    = request.client.host if request and request.client else None,
    )
    
    return {
        "message": f"Prix mis à jour: {old_price} → {new_price} TND",
        "prix_ancien": old_price,
        "prix_nouveau": new_price
    }


@router.get("/{pid}/prix-historique", dependencies=[Depends(require_any_role)])
def get_prix_historique_produit(pid: int, db=Depends(get_db)):
    """Get price change history for a product."""
    prod = q(db, "SELECT * FROM produits WHERE id=%s", (pid,), one=True)
    if not prod:
        raise HTTPException(404, "Produit non trouvé")
    
    history = serialize(q(db, """
        SELECT ph.*, 
               CONCAT(u.prenom,' ',u.nom) changed_by_nom
        FROM prix_historique ph
        LEFT JOIN users u ON ph.changed_by = u.id
        WHERE ph.entity_type='PRODUIT' AND ph.entity_id = %s
        ORDER BY ph.date_changement DESC, ph.id DESC
    """, (pid,)))
    
    return history