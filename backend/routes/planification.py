"""
SOFEM MES v4.0 — Planification Production
SMARTMOVE · Mahmoud Njeh
"""

from fastapi import APIRouter, Depends, HTTPException
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import PlanningCreate, PlanningUpdate

router = APIRouter(prefix="/api/planning", tags=["planning"])


@router.get("", dependencies=[Depends(require_any_role)])
def list_planning(conn=Depends(get_db)):
    rows = q(conn, """
        SELECT pp.*,
               of_.numero AS of_numero, p.nom as produit_nom,
               m.nom as machine_nom, m.code as machine_code,
               o.nom as operateur_nom, o.prenom as operateur_prenom
        FROM planning_production pp
        LEFT JOIN ordres_fabrication of_ ON of_.id = pp.of_id
        LEFT JOIN produits p ON p.id = of_.produit_id
        LEFT JOIN machines m ON m.id = pp.machine_id
        LEFT JOIN operateurs o ON o.id = pp.operateur_id
        ORDER BY pp.date_debut ASC
    """)
    return serialize(rows)


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_planning(data: PlanningCreate, conn=Depends(get_db)):
    # Conflict check: same machine, overlapping time
    if data.machine_id:
        conflict = q(conn, """
            SELECT id FROM planning_production
            WHERE machine_id=%s AND statut NOT IN ('TERMINE','ANNULE')
            AND date_debut < %s AND date_fin > %s
        """, (data.machine_id, data.date_fin, data.date_debut), one=True)
        if conflict:
            raise HTTPException(409, "Conflit de planification: machine déjà occupée sur ce créneau")
    pid = exe(conn, """
        INSERT INTO planning_production (of_id,machine_id,operateur_id,date_debut,date_fin,statut,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (data.of_id, data.machine_id, data.operateur_id,
          data.date_debut, data.date_fin, data.statut, data.notes))
    return {"id": pid, "message": "Planification créée"}


@router.put("/{pid}", dependencies=[Depends(require_manager_or_admin)])
def update_planning(pid: int, data: PlanningUpdate, conn=Depends(get_db)):
    fields, vals = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s")
        vals.append(v)
    if not fields:
        raise HTTPException(400, "Aucune donnée")
    vals.append(pid)
    exe(conn, f"UPDATE planning_production SET {','.join(fields)} WHERE id=%s", vals)
    return {"message": "Planning mis à jour"}


@router.delete("/{pid}", dependencies=[Depends(require_manager_or_admin)])
def delete_planning(pid: int, conn=Depends(get_db)):
    exe(conn, "DELETE FROM planning_production WHERE id=%s", (pid,))
    return {"message": "Entrée supprimée"}


@router.get("/gantt", dependencies=[Depends(require_manager_or_admin)])
def gantt_data(conn=Depends(get_db)):
    """Returns data structured for Gantt chart rendering."""
    rows = q(conn, """
        SELECT pp.id, pp.date_debut, pp.date_fin, pp.statut,
               of_.numero AS of_numero, p.nom as produit_nom,
               m.nom as machine_nom,
               o.nom as operateur_nom, o.prenom as operateur_prenom
        FROM planning_production pp
        LEFT JOIN ordres_fabrication of_ ON of_.id = pp.of_id
        LEFT JOIN produits p ON p.id = of_.produit_id
        LEFT JOIN machines m ON m.id = pp.machine_id
        LEFT JOIN operateurs o ON o.id = pp.operateur_id
        WHERE pp.statut NOT IN ('ANNULE')
        ORDER BY pp.date_debut
    """)
    return serialize(rows)