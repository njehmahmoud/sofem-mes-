"""SOFEM MES v6.0 — Dashboard Routes (patched)
Fix: 7 independent serial queries collapsed into 2 queries (one aggregated OF stats, one stock count).
"""

import logging
from fastapi import APIRouter, Depends
from database import get_db, q, serialize
from auth import require_any_role

logger = logging.getLogger("sofem-dashboard")

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", dependencies=[Depends(require_any_role)])
def dashboard(db=Depends(get_db)):
    # ── Single aggregated query replaces 6 separate OF queries ──
    stats = q(db, """
        SELECT
            SUM(statut IN ('DRAFT','APPROVED','IN_PROGRESS'))                                      AS ordres_actifs,
            SUM(priorite='URGENT' AND statut NOT IN ('COMPLETED','CANCELLED'))                     AS urgents,
            SUM(MONTH(created_at)=MONTH(NOW()) AND YEAR(created_at)=YEAR(NOW()))                   AS total_m,
            SUM(statut='COMPLETED'
                AND MONTH(created_at)=MONTH(NOW())
                AND YEAR(created_at)=YEAR(NOW()))                                                  AS comp_m,
            SUM(date_echeance < CURDATE() AND statut NOT IN ('COMPLETED','CANCELLED'))             AS retard
        FROM ordres_fabrication
    """, one=True)

    al_stock = q(db, "SELECT COUNT(*) n FROM materiaux WHERE stock_actuel < stock_minimum", one=True)["n"]

    actifs  = int(stats["ordres_actifs"] or 0)
    urgents = int(stats["urgents"]       or 0)
    total_m = int(stats["total_m"]       or 0)
    comp_m  = int(stats["comp_m"]        or 0)
    retard  = int(stats["retard"]        or 0)
    taux    = round(comp_m / total_m * 100, 1) if total_m > 0 else 0

    graphique = q(db, """
        SELECT DATE_FORMAT(MIN(created_at),'%b %Y') mois, COUNT(*) total
        FROM ordres_fabrication
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY YEAR(created_at), MONTH(created_at)
        ORDER BY YEAR(created_at), MONTH(created_at)
    """)

    return serialize({
        "ordres_actifs":    actifs,
        "urgents":          urgents,
        "taux_completion":  taux,
        "alertes_stock":    al_stock,
        "en_retard":        retard,
        "graphique":        graphique,
        # Aliases used by dashboard.js
        "total_ofs":              actifs,
        "in_progress":            actifs,
        "completed_today":        comp_m,
        "stock_alerts":           al_stock,
        "production_par_semaine": graphique,
    })


@router.get("/operator/{operateur_id}", dependencies=[Depends(require_any_role)])
def dashboard_operator(operateur_id: int, db=Depends(get_db)):
    """Dashboard for a specific operator."""
    # Single aggregated query for operator stats
    row = q(db, """
        SELECT
            SUM(o.statut = 'IN_PROGRESS')              AS mes_ops_actifs,
            SUM(o.statut = 'COMPLETED')                AS termines,
            COUNT(DISTINCT o.id)                       AS total
        FROM op_operateurs oo
        JOIN of_operations op ON op.id = oo.operation_id
        JOIN ordres_fabrication o ON o.id = op.of_id
        WHERE oo.operateur_id = %s
    """, (operateur_id,), one=True)

    total    = int(row["total"]         or 0)
    termines = int(row["termines"]      or 0)
    actifs   = int(row["mes_ops_actifs"] or 0)
    perf     = round(termines / total * 100, 1) if total > 0 else 0

    return {
        "mes_ofs_actifs": actifs,
        "ofs_termines":   termines,
        "performance":    perf,
    }
