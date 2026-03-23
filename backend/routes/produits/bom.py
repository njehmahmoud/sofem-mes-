"""SOFEM MES v6.0 — Produits BOM (recipe per product)"""

from fastapi import APIRouter, Depends
from typing import List
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import BOMLine

router = APIRouter(prefix="/api/produits/{pid}/bom", tags=["produits-bom"])


@router.get("", dependencies=[Depends(require_any_role)])
def get_bom(pid: int, db=Depends(get_db)):
    return serialize(q(db, """
        SELECT b.*, m.nom materiau_nom, m.code materiau_code,
               m.unite, m.stock_actuel, m.stock_minimum
        FROM bom b JOIN materiaux m ON m.id = b.materiau_id
        WHERE b.produit_id = %s ORDER BY m.nom
    """, (pid,)))


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def add_line(pid: int, data: BOMLine, db=Depends(get_db)):
    existing = q(db, "SELECT id FROM bom WHERE produit_id=%s AND materiau_id=%s",
                 (pid, data.materiau_id), one=True)
    if existing:
        exe(db, "UPDATE bom SET quantite_par_unite=%s WHERE produit_id=%s AND materiau_id=%s",
            (data.quantite_par_unite, pid, data.materiau_id))
        return {"message": "Quantité mise à jour"}
    exe(db, "INSERT INTO bom (produit_id,materiau_id,quantite_par_unite) VALUES (%s,%s,%s)",
        (pid, data.materiau_id, data.quantite_par_unite))
    return {"message": "Matériau ajouté au BOM"}


@router.put("", dependencies=[Depends(require_manager_or_admin)])
def replace_bom(pid: int, lines: List[BOMLine], db=Depends(get_db)):
    exe(db, "DELETE FROM bom WHERE produit_id=%s", (pid,))
    for l in lines:
        exe(db, "INSERT INTO bom (produit_id,materiau_id,quantite_par_unite) VALUES (%s,%s,%s)",
            (pid, l.materiau_id, l.quantite_par_unite))
    return {"message": f"BOM mis à jour — {len(lines)} ligne(s)"}


@router.delete("/{mid}", dependencies=[Depends(require_manager_or_admin)])
def remove_line(pid: int, mid: int, db=Depends(get_db)):
    exe(db, "DELETE FROM bom WHERE produit_id=%s AND materiau_id=%s", (pid, mid))
    return {"message": "Ligne supprimée"}
