"""SOFEM MES v2.0 — Rapports Routes"""

from fastapi import APIRouter, Depends
from database import get_db, q, serialize
from auth import require_manager_or_admin

router = APIRouter(prefix="/api/rapports", tags=["rapports"])

@router.get("/production-mensuelle", dependencies=[Depends(require_manager_or_admin)])
def rapport_mensuel(db=Depends(get_db)):
    return serialize(q(db, """SELECT DATE_FORMAT(created_at,'%Y-%m') mois,
        COUNT(*) total, SUM(statut='COMPLETED') completes
        FROM ordres_fabrication
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
        GROUP BY DATE_FORMAT(created_at,'%Y-%m') ORDER BY mois"""))

@router.get("/operateurs", dependencies=[Depends(require_manager_or_admin)])
def rapport_operateurs(db=Depends(get_db)):
    return serialize(q(db, """SELECT CONCAT(o.prenom,' ',o.nom) operateur, o.specialite,
        COUNT(DISTINCT ep.of_id) total_ofs,
        SUM(ep.statut='COMPLETED') etapes_completes,
        ROUND(AVG(TIMESTAMPDIFF(MINUTE,ep.debut,ep.fin)),0) duree_moy_min
        FROM operateurs o
        LEFT JOIN op_operateurs oo ON oo.operateur_id = o.id
        LEFT JOIN of_operations ep ON ep.id = oo.operation_id
        WHERE o.actif=TRUE GROUP BY o.id ORDER BY etapes_completes DESC"""))

@router.get("/stock-alertes", dependencies=[Depends(require_manager_or_admin)])
def rapport_stock(db=Depends(get_db)):
    return serialize(q(db, """SELECT *, ROUND(stock_actuel/stock_minimum*100,0) pct
        FROM materiaux WHERE stock_actuel < stock_minimum
        ORDER BY (stock_actuel/stock_minimum) ASC"""))
