"""SOFEM MES v2.0 — Materiaux Routes"""

from fastapi import APIRouter, Depends, HTTPException
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import MateriauCreate, MateriauUpdate, MouvementCreate

router = APIRouter(prefix="/api/materiaux", tags=["materiaux"])

@router.get("", dependencies=[Depends(require_any_role)])
def list_materiaux(db=Depends(get_db)):
    return serialize(q(db, """SELECT *,
        (stock_actuel < stock_minimum) alerte,
        ROUND(CASE WHEN stock_minimum>0 THEN stock_actuel/stock_minimum*100 ELSE 100 END,0) pct_stock
        FROM materiaux ORDER BY nom"""))

@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_materiau(data: MateriauCreate, db=Depends(get_db)):
    mid = exe(db, "INSERT INTO materiaux (code,nom,unite,stock_actuel,stock_minimum,fournisseur,prix_unitaire) VALUES (%s,%s,%s,%s,%s,%s,%s)",
              (data.code, data.nom, data.unite, data.stock_actuel, data.stock_minimum, data.fournisseur, data.prix_unitaire))
    return {"id": mid, "message": "Matériau créé"}

@router.post("/mouvement", dependencies=[Depends(require_any_role)])
def mouvement_stock(data: MouvementCreate, db=Depends(get_db)):
    mat = q(db, "SELECT stock_actuel FROM materiaux WHERE id=%s", (data.materiau_id,), one=True)
    if not mat: raise HTTPException(404, "Matériau non trouvé")
    avant = float(mat["stock_actuel"])
    apres = avant + data.quantite if data.type=="ENTREE" else avant - data.quantite if data.type=="SORTIE" else data.quantite
    if apres < 0: raise HTTPException(400, f"Stock insuffisant (disponible: {avant})")
    exe(db, "UPDATE materiaux SET stock_actuel=%s WHERE id=%s", (apres, data.materiau_id))
    exe(db, "INSERT INTO mouvements_stock (materiau_id,of_id,type,quantite,stock_avant,stock_apres,motif) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (data.materiau_id, data.of_id, data.type, data.quantite, avant, apres, data.motif))
    return {"message": "Mouvement enregistré", "stock_avant": avant, "stock_apres": apres}

@router.get("/mouvements", dependencies=[Depends(require_any_role)])
def historique(limit: int = 50, db=Depends(get_db)):
    return serialize(q(db, """SELECT ms.*, m.nom materiau_nom, m.unite, o.numero of_numero
        FROM mouvements_stock ms JOIN materiaux m ON ms.materiau_id=m.id
        LEFT JOIN ordres_fabrication o ON ms.of_id=o.id
        ORDER BY ms.created_at DESC LIMIT %s""", (limit,)))


@router.put("/{mat_id}", dependencies=[Depends(require_manager_or_admin)])
def update_materiau(mat_id: int, data: MateriauUpdate, db=Depends(get_db)):
    mat = q(db, "SELECT id FROM materiaux WHERE id=%s", (mat_id,), one=True)
    if not mat: raise HTTPException(404, "Matériau non trouvé")
    fields, vals = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s"); vals.append(v)
    if fields:
        vals.append(mat_id)
        exe(db, f"UPDATE materiaux SET {','.join(fields)} WHERE id=%s", vals)
    return {"message": "Matériau mis à jour"}


@router.delete("/{mat_id}", dependencies=[Depends(require_manager_or_admin)])
def delete_materiau(mat_id: int, db=Depends(get_db)):
    in_use = q(db, "SELECT COUNT(*) n FROM of_bom WHERE materiau_id=%s", (mat_id,), one=True)["n"]
    if in_use > 0:
        raise HTTPException(400, f"Matériau utilisé dans {in_use} OF(s) — suppression impossible")
    in_bom = q(db, "SELECT COUNT(*) n FROM bom WHERE materiau_id=%s", (mat_id,), one=True)["n"]
    if in_bom > 0:
        raise HTTPException(400, f"Matériau utilisé dans {in_bom} BOM(s) produit — suppression impossible")
    exe(db, "DELETE FROM materiaux WHERE id=%s", (mat_id,))
    return {"message": "Matériau supprimé"}