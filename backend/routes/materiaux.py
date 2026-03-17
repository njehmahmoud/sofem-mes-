"""SOFEM MES v2.0 — Materiaux Routes"""

from fastapi import APIRouter, Depends, HTTPException
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import MateriauCreate, MouvementCreate

router = APIRouter(prefix="/api/materiaux", tags=["materiaux"])

@router.get("", dependencies=[Depends(require_any_role)])
def list_materiaux(db=Depends(get_db)):
    return serialize(q(db, """SELECT *,
        (stock_actuel < stock_minimum) alerte,
        ROUND(CASE WHEN stock_minimum>0 THEN stock_actuel/stock_minimum*100 ELSE 100 END,0) pct_stock
        FROM materiaux ORDER BY nom"""))

@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_materiau(data: MateriauCreate, db=Depends(get_db)):
    mid = exe(db, "INSERT INTO materiaux (code,nom,unite,stock_actuel,stock_minimum,fournisseur) VALUES (%s,%s,%s,%s,%s,%s)",
              (data.code, data.nom, data.unite, data.stock_actuel, data.stock_minimum, data.fournisseur))
    return {"id": mid, "message": "Matériau créé"}

@router.post("/mouvement", dependencies=[Depends(require_any_role)])
def mouvement_stock(data: MouvementCreate, db=Depends(get_db)):
    mat = q(db, "SELECT stock_actuel FROM materiaux WHERE id=%s", (data.materiau_id,), one=True)
    if not mat: raise HTTPException(404, "Matériau non trouvé")
    avant = float(mat["stock_actuel"])
    apres = avant + data.quantite if data.type=="ENTREE" else avant - data.quantite if data.type=="SORTIE" else data.quantite
    if apres < 0: raise HTTPException(400, f"Stock insuffisant (disponible: {avant})")
    exe(db, "UPDATE materiaux SET stock_actuel=%s WHERE id=%s", (apres, data.materiau_id))
    exe(db, "INSERT INTO mouvements_stock (materiau_id,of_id,type,quantite,stock_avant,stock_apres,motif) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (data.materiau_id, data.of_id, data.type, data.quantite, avant, apres, data.motif))
    return {"message": "Mouvement enregistré", "stock_avant": avant, "stock_apres": apres}

@router.get("/mouvements", dependencies=[Depends(require_any_role)])
def historique(limit: int = 50, db=Depends(get_db)):
    return serialize(q(db, """SELECT ms.*, m.nom materiau_nom, m.unite, o.numero of_numero
        FROM mouvements_stock ms JOIN materiaux m ON ms.materiau_id=m.id
        LEFT JOIN ordres_fabrication o ON ms.of_id=o.id
        ORDER BY ms.created_at DESC LIMIT %s""", (limit,)))
