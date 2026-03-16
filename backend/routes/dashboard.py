"""SOFEM MES v2.0 — Dashboard Routes"""

from fastapi import APIRouter, Depends
from database import get_db, q, serialize
from auth import require_any_role

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("", dependencies=[Depends(require_any_role)])
def dashboard(db=Depends(get_db)):
    actifs   = q(db, "SELECT COUNT(*) n FROM ordres_fabrication WHERE statut IN ('DRAFT','APPROVED','IN_PROGRESS')", one=True)["n"]
    urgents  = q(db, "SELECT COUNT(*) n FROM ordres_fabrication WHERE priorite='URGENT' AND statut NOT IN ('COMPLETED','CANCELLED')", one=True)["n"]
    total_m  = q(db, "SELECT COUNT(*) n FROM ordres_fabrication WHERE MONTH(created_at)=MONTH(NOW()) AND YEAR(created_at)=YEAR(NOW())", one=True)["n"]
    comp_m   = q(db, "SELECT COUNT(*) n FROM ordres_fabrication WHERE statut='COMPLETED' AND MONTH(created_at)=MONTH(NOW()) AND YEAR(created_at)=YEAR(NOW())", one=True)["n"]
    al_stock = q(db, "SELECT COUNT(*) n FROM materiaux WHERE stock_actuel < stock_minimum", one=True)["n"]
    retard   = q(db, "SELECT COUNT(*) n FROM ordres_fabrication WHERE date_echeance < CURDATE() AND statut NOT IN ('COMPLETED','CANCELLED')", one=True)["n"]
    taux     = round(comp_m / total_m * 100, 1) if total_m > 0 else 0
    graphique = q(db, """
        SELECT DATE_FORMAT(created_at,'%b %Y') mois, COUNT(*) total
        FROM ordres_fabrication
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY YEAR(created_at), MONTH(created_at)
        ORDER BY YEAR(created_at), MONTH(created_at)
    """)
    return serialize({
        "ordres_actifs": actifs, "urgents": urgents,
        "taux_completion": taux, "alertes_stock": al_stock,
        "en_retard": retard, "graphique": graphique
    })

@router.get("/operator/{operateur_id}", dependencies=[Depends(require_any_role)])
def dashboard_operator(operateur_id: int, db=Depends(get_db)):
    """Dashboard for a specific operator — only their data"""
    mes_ofs  = q(db, "SELECT COUNT(*) n FROM ordres_fabrication WHERE operateur_id=%s AND statut='IN_PROGRESS'", (operateur_id,), one=True)["n"]
    termines = q(db, "SELECT COUNT(*) n FROM ordres_fabrication WHERE operateur_id=%s AND statut='COMPLETED'", (operateur_id,), one=True)["n"]
    total    = q(db, "SELECT COUNT(*) n FROM ordres_fabrication WHERE operateur_id=%s", (operateur_id,), one=True)["n"]
    etapes   = q(db, """
        SELECT COUNT(*) n FROM etapes_production ep
        JOIN ordres_fabrication o ON ep.of_id=o.id
        WHERE o.operateur_id=%s AND ep.statut='IN_PROGRESS'
    """, (operateur_id,), one=True)["n"]
    perf = round(termines / total * 100, 1) if total > 0 else 0
    return {"mes_ofs_actifs": mes_ofs, "ofs_termines": termines, "etapes_en_cours": etapes, "performance": perf}
