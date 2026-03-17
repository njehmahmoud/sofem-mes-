"""SOFEM MES v6.0 — Produits CRUD"""

from fastapi import APIRouter, Depends, HTTPException
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
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
        "INSERT INTO produits (code,nom,description,unite) VALUES (%s,%s,%s,%s)",
        (code, data.nom, data.description, data.unite))
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
