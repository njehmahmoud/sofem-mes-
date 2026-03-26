"""SOFEM MES v6.0 — Machines (Commit 01 — ISO 9001 soft delete)"""

from fastapi import APIRouter, Depends, HTTPException, Request
from database import get_db, q, exe, serialize, soft_delete, log_activity, cancel_document
from auth import require_any_role, require_manager_or_admin, get_current_user
from models import MachineCreate, MachineUpdate, DeactivateRequest

router = APIRouter(prefix="/api/machines", tags=["machines"])


@router.get("")
def list_machines(show_inactive: bool = False,
                  conn=Depends(get_db), user=Depends(require_any_role)):
    base = "" if show_inactive else "WHERE actif=TRUE OR actif IS NULL"
    rows = q(conn, f"SELECT * FROM machines {base} ORDER BY atelier, nom")
    return serialize(rows)


@router.get("/{mid}")
def get_machine(mid: int, conn=Depends(get_db), user=Depends(require_any_role)):
    row = q(conn, "SELECT * FROM machines WHERE id=%s", (mid,), one=True)
    if not row: raise HTTPException(404, "Machine introuvable")
    hist = q(conn, """
        SELECT om.*, o.nom as technicien_nom, o.prenom as technicien_prenom
        FROM ordres_maintenance om
        LEFT JOIN operateurs o ON o.id = om.technicien_id
        WHERE om.machine_id=%s ORDER BY om.created_at DESC LIMIT 10
    """, (mid,))
    row["historique_maintenance"] = hist
    return serialize(row)


@router.post("", status_code=201)
def create_machine(data: MachineCreate, request: Request,
                   conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    if not data.code:
        count = q(conn, "SELECT COUNT(*) as c FROM machines", one=True)["c"]
        data.code = f"MCH-{count+1:04d}"
    mid = exe(conn, """
        INSERT INTO machines
            (code,nom,type,marque,modele,numero_serie,atelier,statut,date_acquisition,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (data.code, data.nom, data.type, data.marque, data.modele,
          data.numero_serie, data.atelier, data.statut, data.date_acquisition, data.notes))

    log_activity(conn, "CREATE", "MACHINE", mid, data.code,
                 user.get("id"), f"{user.get('prenom','')} {user.get('nom','')}".strip(),
                 new_value=data.dict(), detail=f"Machine {data.code} — {data.nom} créée",
                 ip_address=request.client.host if request.client else None)
    return {"id": mid, "message": "Machine créée"}


@router.put("/{mid}")
def update_machine(mid: int, data: MachineUpdate, request: Request,
                   conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    old = q(conn, "SELECT * FROM machines WHERE id=%s", (mid,), one=True)
    if not old: raise HTTPException(404, "Machine introuvable")

    fields, vals = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s"); vals.append(v)
    if not fields: raise HTTPException(400, "Aucune donnée")
    vals.append(mid)
    exe(conn, f"UPDATE machines SET {','.join(fields)} WHERE id=%s", vals)

    log_activity(conn, "UPDATE", "MACHINE", mid, old.get("code"),
                 user.get("id"), f"{user.get('prenom','')} {user.get('nom','')}".strip(),
                 old_value={f: old.get(f) for f in data.dict(exclude_none=True).keys()},
                 new_value=data.dict(exclude_none=True),
                 detail=f"Machine {old.get('code')} mise à jour",
                 ip_address=request.client.host if request.client else None)
    return {"message": "Machine mise à jour"}


@router.delete("/{mid}")
def deactivate_machine(mid: int, data: DeactivateRequest,
                       request: Request,
                       conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    """
    ISO 9001 — machines are never physically deleted.
    Machine with active maintenance orders cannot be deactivated.
    """
    machine = q(conn, "SELECT * FROM machines WHERE id=%s", (mid,), one=True)
    if not machine: raise HTTPException(404, "Machine introuvable")

    active_om = q(conn, """
        SELECT COUNT(*) n FROM ordres_maintenance
        WHERE machine_id=%s AND statut IN ('PLANIFIE','EN_COURS')
    """, (mid,), one=True)
    if active_om and active_om["n"] > 0:
        raise HTTPException(400,
            f"Machine liée à {active_om['n']} ordre(s) de maintenance actif(s)")

    soft_delete(conn, "machines", mid,
                user.get("id"),
                f"{user.get('prenom','')} {user.get('nom','')}".strip(),
                data.reason, "MACHINE", machine.get("code"))
    return {"message": f"Machine {machine.get('code')} désactivée"}


@router.get("/stats/overview")
def machines_stats(conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    total      = q(conn, "SELECT COUNT(*) as c FROM machines WHERE actif=TRUE OR actif IS NULL", one=True)["c"]
    by_status  = q(conn, "SELECT statut, COUNT(*) as c FROM machines WHERE actif=TRUE OR actif IS NULL GROUP BY statut")
    en_maint   = q(conn, "SELECT COUNT(*) as c FROM ordres_maintenance WHERE statut IN ('PLANIFIE','EN_COURS')", one=True)["c"]
    return serialize({"total": total, "by_status": by_status, "en_maintenance": en_maint})