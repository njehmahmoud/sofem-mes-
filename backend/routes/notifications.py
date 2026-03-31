"""SOFEM MES v6.0 — Notifications & Activity Log Routes
Commit 01 — Now reads from activity_log_v2 with full ISO 9001 audit data
"""

from fastapi import APIRouter, Depends
from database import get_db, q, exe, serialize, log_activity
from auth import require_any_role, require_manager_or_admin, get_current_user
from models import OFCreate, OFUpdate, BOMOverride, CancelRequest
from datetime import datetime

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", dependencies=[Depends(require_any_role)])
def get_notifications(db=Depends(get_db)):
    """Return all active alerts grouped by type"""
    notifs = []

    # Stock alerts
    stock = q(db, """
        SELECT nom, stock_actuel, stock_minimum, unite
        FROM materiaux
        WHERE stock_actuel < stock_minimum
        AND (actif = TRUE OR actif IS NULL)
        ORDER BY stock_actuel/NULLIF(stock_minimum,1) ASC
    """)
    for s in stock:
        notifs.append({
            "type": "stock", "level": "danger", "icon": "📦",
            "title": f"Stock critique — {s['nom']}",
            "detail": f"{s['stock_actuel']} / {s['stock_minimum']} {s['unite']}",
        })

    # OFs en retard
    retards = q(db, """
        SELECT o.numero, p.nom produit_nom, DATEDIFF(CURDATE(), o.date_echeance) jours
        FROM ordres_fabrication o JOIN produits p ON p.id=o.produit_id
        WHERE o.date_echeance < CURDATE()
          AND o.statut NOT IN ('COMPLETED','CANCELLED')
        ORDER BY jours DESC LIMIT 5
    """)
    for r in retards:
        notifs.append({
            "type": "retard", "level": "warning", "icon": "⏰",
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
            "type": "urgent", "level": "danger", "icon": "🚨",
            "title": f"OF urgent — {u['numero']}",
            "detail": f"{u['produit_nom']} · Échéance {str(u['date_echeance'] or '—')[:10]}",
        })

    # DAs en attente d'approbation
    try:
        das = q(db, "SELECT COUNT(*) n FROM demandes_achat WHERE statut='PENDING'", one=True)
        if das and das['n'] > 0:
            notifs.append({
                "type": "da", "level": "info", "icon": "📝",
                "title": f"{das['n']} demande(s) achat en attente",
                "detail": "À approuver dans Achats → DAs",
            })
    except: pass

    # BRs en attente de réception
    try:
        brs = q(db, "SELECT COUNT(*) n FROM bons_reception WHERE statut='EN_ATTENTE'", one=True)
        if brs and brs['n'] > 0:
            notifs.append({
                "type": "br", "level": "info", "icon": "📬",
                "title": f"{brs['n']} bon(s) de réception en attente",
                "detail": "Confirmer la réception dans Achats → BRs",
            })
    except: pass

    return {
        "total":   len(notifs),
        "danger":  sum(1 for n in notifs if n['level'] == 'danger'),
        "warning": sum(1 for n in notifs if n['level'] == 'warning'),
        "info":    sum(1 for n in notifs if n['level'] == 'info'),
        "items":   notifs
    }


# ── Activity Log ───────────────────────────────────────────

@router.get("/activity", dependencies=[Depends(require_any_role)])
def get_activity(
    limit:       int = 100,
    entity_type: str = None,
    entity_id:   int = None,
    action:      str = None,
    user_id:     int = None,
    db=Depends(get_db)
):
    """
    ISO 9001 compliant audit trail.
    Supports filtering by entity_type, entity_id, action, user_id.
    """
    try:
        # Try activity_log_v2 first (new ISO 9001 compliant table)
        where_clauses = []
        params = []

        if entity_type:
            where_clauses.append("entity_type = %s")
            params.append(entity_type.upper())
        if entity_id:
            where_clauses.append("entity_id = %s")
            params.append(entity_id)
        if action:
            where_clauses.append("action = %s")
            params.append(action.upper())
        if user_id:
            where_clauses.append("user_id = %s")
            params.append(user_id)

        where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        params.append(limit)

        logs = q(db, f"""
            SELECT
                al.id, al.created_at, al.user_id, al.user_nom,
                al.action, al.entity_type, al.entity_id,
                al.entity_numero, al.reason, al.detail,
                al.old_value, al.new_value,
                u.prenom, u.nom
            FROM activity_log_v2 al
            LEFT JOIN users u ON u.id = al.user_id
            {where}
            ORDER BY al.created_at DESC
            LIMIT %s
        """, params or (limit,))
        return serialize(logs)

    except Exception:
        # Fallback to old activity_log table
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


@router.get("/activity/entity/{entity_type}/{entity_id}",
            dependencies=[Depends(require_any_role)])
def get_entity_history(entity_type: str, entity_id: int, db=Depends(get_db)):
    """
    Get complete history for a specific document.
    Used to show audit trail directly on an OF, BL, NC, etc.
    """
    try:
        logs = q(db, """
            SELECT
                al.id, al.created_at, al.user_id, al.user_nom,
                al.action, al.entity_numero, al.reason, al.detail,
                al.old_value, al.new_value
            FROM activity_log_v2 al
            WHERE al.entity_type = %s AND al.entity_id = %s
            ORDER BY al.created_at ASC
        """, (entity_type.upper(), entity_id))
        return serialize(logs)
    except:
        return []


@router.post("/activity", dependencies=[Depends(require_any_role)])
def log_activity_endpoint(
    data: dict,
    user=Depends(get_current_user),
    db=Depends(get_db)
):
    """Frontend can log actions (PDF prints, page views, etc.)"""
    try:
        log_activity(
            db,
            action        = data.get('action', 'VIEW'),
            entity_type   = data.get('entity_type', 'UNKNOWN'),
            entity_id     = data.get('entity_id'),
            entity_numero = data.get('entity_numero'),
            user_id       = user.get('id'),
            user_nom      = f"{user.get('prenom','')} {user.get('nom','')}".strip(),
            reason        = data.get('reason'),
            detail        = data.get('detail'),
        )
    except: pass
    return {"ok": True}