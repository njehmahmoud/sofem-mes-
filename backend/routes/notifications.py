"""SOFEM MES v6.0 — Notifications & Activity Log Routes"""

from fastapi import APIRouter, Depends
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin, get_current_user
from datetime import datetime

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

@router.get("", dependencies=[Depends(require_any_role)])
def get_notifications(db=Depends(get_db)):
    """Return all active alerts grouped by type"""
    notifs = []

    # Stock alerts
    stock = q(db, """
        SELECT nom, stock_actuel, stock_minimum, unite
        FROM materiaux WHERE stock_actuel < stock_minimum ORDER BY stock_actuel/NULLIF(stock_minimum,1) ASC
    """)
    for s in stock:
        notifs.append({
            "type": "stock",
            "level": "danger",
            "icon": "📦",
            "title": f"Stock critique — {s['nom']}",
            "detail": f"{s['stock_actuel']} / {s['stock_minimum']} {s['unite']}",
        })

    # OFs en retard
    retards = q(db, """
        SELECT o.numero, p.nom produit_nom, DATEDIFF(CURDATE(), o.date_echeance) jours
        FROM ordres_fabrication o JOIN produits p ON p.id=o.produit_id
        WHERE o.date_echeance < CURDATE() AND o.statut NOT IN ('COMPLETED','CANCELLED')
        ORDER BY jours DESC LIMIT 5
    """)
    for r in retards:
        notifs.append({
            "type": "retard",
            "level": "warning",
            "icon": "⏰",
            "title": f"OF en retard — {r['numero']}",
            "detail": f"{r['produit_nom']} · +{r['jours']} jours",
        })

    # OFs urgents actifs
    urgents = q(db, """
        SELECT o.numero, p.nom produit_nom, o.date_echeance
        FROM ordres_fabrication o JOIN produits p ON p.id=o.produit_id
        WHERE o.priorite='URGENT' AND o.statut NOT IN ('COMPLETED','CANCELLED')
        ORDER BY o.date_echeance ASC LIMIT 3
    """)
    for u in urgents:
        notifs.append({
            "type": "urgent",
            "level": "danger",
            "icon": "🚨",
            "title": f"OF urgent — {u['numero']}",
            "detail": f"{u['produit_nom']} · Échéance {str(u['date_echeance'] or '—')[:10]}",
        })

    # DAs en attente d'approbation
    try:
        das = q(db, "SELECT COUNT(*) n FROM demandes_achat WHERE statut='PENDING'", one=True)
        if das and das['n'] > 0:
            notifs.append({
                "type": "da",
                "level": "info",
                "icon": "📝",
                "title": f"{das['n']} demande(s) achat en attente",
                "detail": "À approuver dans Achats → DAs",
            })
    except: pass

    # BRs en attente de réception
    try:
        brs = q(db, "SELECT COUNT(*) n FROM bons_reception WHERE statut='EN_ATTENTE'", one=True)
        if brs and brs['n'] > 0:
            notifs.append({
                "type": "br",
                "level": "info",
                "icon": "📬",
                "title": f"{brs['n']} bon(s) de réception en attente",
                "detail": "Confirmer la réception dans Achats → BRs",
            })
    except: pass

    return {
        "total": len(notifs),
        "danger": sum(1 for n in notifs if n['level'] == 'danger'),
        "warning": sum(1 for n in notifs if n['level'] == 'warning'),
        "info": sum(1 for n in notifs if n['level'] == 'info'),
        "items": notifs
    }


# ── Activity Log ───────────────────────────────────────────
@router.get("/activity", dependencies=[Depends(require_any_role)])
def get_activity(limit: int = 50, db=Depends(get_db)):
    try:
        logs = q(db, """
            SELECT al.*, u.prenom, u.nom
            FROM activity_log al
            LEFT JOIN users u ON u.id = al.user_id
            ORDER BY al.created_at DESC
            LIMIT %s
        """, (limit,))
        return serialize(logs)
    except:
        return []

@router.post("/activity", dependencies=[Depends(require_any_role)])
def log_activity(data: dict, user=Depends(get_current_user), db=Depends(get_db)):
    try:
        exe(db, """
            INSERT INTO activity_log (user_id, action, entity_type, entity_id, detail)
            VALUES (%s, %s, %s, %s, %s)
        """, (user.get('id'), data.get('action'), data.get('entity_type'),
              data.get('entity_id'), data.get('detail')))
    except: pass
    return {"ok": True}