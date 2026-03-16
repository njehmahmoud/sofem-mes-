"""SOFEM MES v2.0 — Produits Routes"""

from fastapi import APIRouter, Depends
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import ProduitCreate

router = APIRouter(prefix="/api/produits", tags=["produits"])

@router.get("", dependencies=[Depends(require_any_role)])
def list_produits(db=Depends(get_db)):
    return serialize(q(db, "SELECT * FROM produits ORDER BY nom"))

@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_produit(data: ProduitCreate, db=Depends(get_db)):
    pid = exe(db, "INSERT INTO produits (code,nom,description,unite) VALUES (%s,%s,%s,%s)",
              (data.code, data.nom, data.description, data.unite))
    return {"id": pid, "message": "Produit créé"}
