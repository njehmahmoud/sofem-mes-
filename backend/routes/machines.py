"""
SOFEM MES v4.0 — Machines / Équipements
SMARTMOVE · Mahmoud Njeh
"""

from fastapi import APIRouter, Depends, HTTPException
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import MachineCreate, MachineUpdate

router = APIRouter(prefix="/api/machines", tags=["machines"])


@router.get("")
def list_machines(conn=Depends(get_db), user=Depends(require_any_role)):
    rows = q(conn, "SELECT * FROM machines ORDER BY atelier, nom")
    return serialize(rows)


@router.get("/{mid}")
def get_machine(mid: int, conn=Depends(get_db), user=Depends(require_any_role)):
    row = q(conn, "SELECT * FROM machines WHERE id=%s", (mid,), one=True)
    if not row:
        raise HTTPException(404, "Machine introuvable")
    # maintenance history
    hist = q(conn, """
        SELECT om.*, o.nom as technicien_nom, o.prenom as technicien_prenom
        FROM ordres_maintenance om
        LEFT JOIN operateurs o ON o.id = om.technicien_id
        WHERE om.machine_id=%s ORDER BY om.created_at DESC LIMIT 10
    """, (mid,))
    row["historique_maintenance"] = hist
    return serialize(row)


@router.post("", status_code=201)
def create_machine(data: MachineCreate, conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    # auto-generate code if not provided
    if not data.code:
        count = q(conn, "SELECT COUNT(*) as c FROM machines", one=True)["c"]
        data.code = f"MCH-{count+1:04d}"
    mid = exe(conn, """
        INSERT INTO machines (code,nom,type,marque,modele,numero_serie,atelier,statut,date_acquisition,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (data.code, data.nom, data.type, data.marque, data.modele,
          data.numero_serie, data.atelier, data.statut, data.date_acquisition, data.notes))
    return {"id": mid, "message": "Machine créée"}


@router.put("/{mid}")
def update_machine(mid: int, data: MachineUpdate, conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    fields, vals = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s")
        vals.append(v)
    if not fields:
        raise HTTPException(400, "Aucune donnée")
    vals.append(mid)
    exe(conn, f"UPDATE machines SET {','.join(fields)} WHERE id=%s", vals)
    return {"message": "Machine mise à jour"}


@router.delete("/{mid}")
def delete_machine(mid: int, conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    exe(conn, "DELETE FROM machines WHERE id=%s", (mid,))
    return {"message": "Machine supprimée"}


@router.get("/stats/overview")
def machines_stats(conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    total = q(conn, "SELECT COUNT(*) as c FROM machines", one=True)["c"]
    by_status = q(conn, "SELECT statut, COUNT(*) as c FROM machines GROUP BY statut")
    en_maintenance = q(conn, "SELECT COUNT(*) as c FROM ordres_maintenance WHERE statut IN ('PLANIFIE','EN_COURS')", one=True)["c"]
    return serialize({"total": total, "by_status": by_status, "en_maintenance": en_maintenance})
