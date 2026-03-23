"""SOFEM MES v6.0 — OF BOM (per-OF material quantities)"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import BOMOverride

router = APIRouter(prefix="/api/of/{of_id}/bom", tags=["of-bom"])


@router.get("")
def get_of_bom(of_id: int, user=Depends(require_any_role), db=Depends(get_db)):
    return serialize(q(db, """
        SELECT ob.*, m.nom materiau_nom, m.code materiau_code,
               m.unite, m.stock_actuel, m.stock_minimum
        FROM of_bom ob JOIN materiaux m ON m.id = ob.materiau_id
        WHERE ob.of_id = %s ORDER BY m.nom
    """, (of_id,)))


@router.put("")
def replace_of_bom(of_id: int, lines: List[BOMOverride],
                   user=Depends(require_manager_or_admin), db=Depends(get_db)):
    exe(db, "DELETE FROM of_bom WHERE of_id=%s", (of_id,))
    for b in lines:
        exe(db, """
            INSERT INTO of_bom (of_id,materiau_id,quantite_requise) VALUES (%s,%s,%s)
        """, (of_id, b.materiau_id, b.quantite_requise))
    return {"message": f"BOM mis à jour — {len(lines)} ligne(s)"}


@router.post("", status_code=201)
def add_of_bom_line(of_id: int, data: BOMOverride,
                    user=Depends(require_manager_or_admin), db=Depends(get_db)):
    exe(db, """
        INSERT INTO of_bom (of_id,materiau_id,quantite_requise) VALUES (%s,%s,%s)
        ON DUPLICATE KEY UPDATE quantite_requise=VALUES(quantite_requise)
    """, (of_id, data.materiau_id, data.quantite_requise))
    return {"message": "Ligne BOM ajoutée"}


@router.delete("/{mat_id}", dependencies=[Depends(require_manager_or_admin)])
def delete_of_bom_line(of_id: int, mat_id: int, db=Depends(get_db)):
    exe(db, "DELETE FROM of_bom WHERE of_id=%s AND materiau_id=%s", (of_id, mat_id))
    return {"message": "Ligne supprimée"}
