"""
SOFEM MES v4.0 — Maintenance
SMARTMOVE · Mahmoud Njeh
"""

from fastapi import APIRouter, Depends, HTTPException
from database import get_db, q, exe, serialize, temp_numero, finalize_number, cancel_document, log_activity, CancelRequest
from auth import require_any_role, require_manager_or_admin, get_current_user
from models import MaintenanceCreate, MaintenanceUpdate
from datetime import date

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


@router.get("")
def list_maintenance(conn=Depends(get_db), user=Depends(require_any_role)):
    rows = q(conn, """
        SELECT om.*,
               m.nom as machine_nom, m.code as machine_code, m.atelier,
               o.nom as technicien_nom, o.prenom as technicien_prenom
        FROM ordres_maintenance om
        LEFT JOIN machines m ON m.id = om.machine_id
        LEFT JOIN operateurs o ON o.id = om.technicien_id
        ORDER BY om.created_at DESC
    """)
    return serialize(rows)


@router.get("/{oid}")
def get_ordre(oid: int, conn=Depends(get_db), user=Depends(require_any_role)):
    row = q(conn, """
        SELECT om.*,
               m.nom as machine_nom, m.code as machine_code,
               o.nom as technicien_nom, o.prenom as technicien_prenom
        FROM ordres_maintenance om
        LEFT JOIN machines m ON m.id = om.machine_id
        LEFT JOIN operateurs o ON o.id = om.technicien_id
        WHERE om.id=%s
    """, (oid,), one=True)
    if not row:
        raise HTTPException(404, "Ordre introuvable")
    return serialize(row)


@router.post("", status_code=201)
def create_maintenance(data: MaintenanceCreate, conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    count = q(conn, "SELECT COUNT(*) as c FROM ordres_maintenance", one=True)["c"]
    om_num = f"OM-{date.today().year}-{count+1:04d}"
    oid = exe(conn, """
        INSERT INTO ordres_maintenance
        (om_numero,machine_id,type_maintenance,titre,description,priorite,statut,
         technicien_id,date_planifiee,duree_estimee,cout_estime,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (om_num, data.machine_id, data.type_maintenance, data.titre, data.description,
          data.priorite, data.statut, data.technicien_id, data.date_planifiee,
          data.duree_estimee, data.cout_estime, data.notes))
    # Update machine status if maintenance starts
    if data.statut in ("EN_COURS",):
        exe(conn, "UPDATE machines SET statut='EN_MAINTENANCE' WHERE id=%s", (data.machine_id,))
    return {"id": oid, "om_numero": om_num, "message": "Ordre de maintenance créé"}


@router.put("/{oid}")
def update_maintenance(oid: int, data: MaintenanceUpdate, conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    fields, vals = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s")
        vals.append(v)
    if not fields:
        raise HTTPException(400, "Aucune donnée")
    vals.append(oid)
    exe(conn, f"UPDATE ordres_maintenance SET {','.join(fields)} WHERE id=%s", vals)
    # Sync machine status
    om = q(conn, "SELECT machine_id, statut FROM ordres_maintenance WHERE id=%s", (oid,), one=True)
    if om:
        if data.statut == "TERMINE":
            exe(conn, "UPDATE machines SET statut='OPERATIONNELLE' WHERE id=%s", (om["machine_id"],))
        elif data.statut == "EN_COURS":
            exe(conn, "UPDATE machines SET statut='EN_MAINTENANCE' WHERE id=%s", (om["machine_id"],))
    return {"message": "Ordre mis à jour"}


@router.delete("/{oid}")
def delete_maintenance(oid: int, conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    exe(conn, "DELETE FROM ordres_maintenance WHERE id=%s", (oid,))
    return {"message": "Ordre supprimé"}


@router.get("/stats/overview")
def maintenance_stats(conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    total = q(conn, "SELECT COUNT(*) as c FROM ordres_maintenance", one=True)["c"]
    en_cours = q(conn, "SELECT COUNT(*) as c FROM ordres_maintenance WHERE statut='EN_COURS'", one=True)["c"]
    planifies = q(conn, "SELECT COUNT(*) as c FROM ordres_maintenance WHERE statut='PLANIFIE'", one=True)["c"]
    urgences = q(conn, "SELECT COUNT(*) as c FROM ordres_maintenance WHERE type_maintenance='URGENCE' AND statut!='TERMINE'", one=True)["c"]
    by_type = q(conn, "SELECT type_maintenance, COUNT(*) as c FROM ordres_maintenance GROUP BY type_maintenance")
    cout_total = q(conn, "SELECT SUM(cout_reel) as total FROM ordres_maintenance WHERE statut='TERMINE'", one=True)["total"] or 0
    return serialize({
        "total": total,
        "en_cours": en_cours,
        "planifies": planifies,
        "urgences": urgences,
        "by_type": by_type,
        "cout_total": cout_total
    })


@router.put("/{oid}/cancel")
def cancel_maintenance(
        oid: int,
        data: CancelRequest,
        user=Depends(get_current_user),
        conn=Depends(get_db)
):
    """
    ISO 9001 — Cancel a maintenance order with mandatory reason.
    TERMINE orders cannot be cancelled.
    When cancelled, machine status is restored to OPERATIONNELLE.
    """
    om = q(conn, """
        SELECT om.*, m.statut machine_statut
        FROM ordres_maintenance om
        LEFT JOIN machines m ON m.id = om.machine_id
        WHERE om.id=%s
    """, (oid,), one=True)

    if not om:
        raise HTTPException(404, "Ordre de maintenance introuvable")
    if om["statut"] == "ANNULE":
        raise HTTPException(400, "Ordre déjà annulé")
    if om["statut"] == "TERMINE":
        raise HTTPException(400,
                            "Un ordre de maintenance terminé ne peut pas être annulé.")

    user_id = user.get("id")
    user_nom = f"{user.get('prenom', '')} {user.get('nom', '')}".strip()

    numero = cancel_document(
        conn,
        table="ordres_maintenance",
        id_col="id",
        numero_col="om_numero",
        record_id=oid,
        user_id=user_id,
        user_nom=user_nom,
        reason=data.reason,
        entity_type="MAINTENANCE",
        old_statut=om["statut"],
    )

    # If machine was in maintenance because of this order,
    # restore it to OPERATIONNELLE
    if om["statut"] == "EN_COURS" and om.get("machine_id"):
        # Check no other active maintenance orders for this machine
        other_active = q(conn, """
            SELECT COUNT(*) n FROM ordres_maintenance
            WHERE machine_id=%s
              AND id != %s
              AND statut = 'EN_COURS'
        """, (om["machine_id"], oid), one=True)

        if not other_active or other_active["n"] == 0:
            exe(conn,
                "UPDATE machines SET statut='OPERATIONNELLE' WHERE id=%s",
                (om["machine_id"],))
            log_activity(
                conn, "UPDATE", "MACHINE", om["machine_id"], None,
                user_id, user_nom,
                old_value={"statut": "EN_MAINTENANCE"},
                new_value={"statut": "OPERATIONNELLE"},
                detail=f"Machine restaurée à OPERATIONNELLE — OM {numero} annulé"
            )

    return {"message": f"Ordre {numero} annulé", "numero": numero}
