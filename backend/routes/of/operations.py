"""SOFEM MES v6.0 — OF Operations (dynamic étapes)"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List
from datetime import datetime
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import OperationCreate, OperationUpdate

router = APIRouter(prefix="/api/of/{of_id}/operations", tags=["of-operations"])


def _get_op(db, of_id, op_id):
    op = q(db, "SELECT * FROM of_operations WHERE id=%s AND of_id=%s",
           (op_id, of_id), one=True)
    if not op: raise HTTPException(404, "Opération introuvable")
    return op


@router.get("")
def list_operations(of_id: int, user=Depends(require_any_role), db=Depends(get_db)):
    ops = q(db, """
        SELECT op.*, m.nom machine_nom
        FROM of_operations op
        LEFT JOIN machines m ON m.id = op.machine_id
        WHERE op.of_id = %s ORDER BY op.ordre, op.id
    """, (of_id,))
    for op in ops:
        op["operateurs"] = q(db, """
            SELECT o.id, o.nom, o.prenom, o.specialite,
                   o.taux_horaire, o.taux_piece, o.type_taux
            FROM op_operateurs oo
            JOIN operateurs o ON o.id = oo.operateur_id
            WHERE oo.operation_id = %s
        """, (op["id"],))
    return serialize(ops)


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def add_operation(of_id: int, data: OperationCreate, db=Depends(get_db)):
    # Auto-order: last + 1
    last = q(db, "SELECT MAX(ordre) mo FROM of_operations WHERE of_id=%s", (of_id,), one=True)
    ordre = (last["mo"] or 0) + 1 if data.ordre is None else data.ordre
    op_id = exe(db, """
        INSERT INTO of_operations (of_id,ordre,operation_nom,machine_id,statut)
        VALUES (%s,%s,%s,%s,'PENDING')
    """, (of_id, ordre, data.operation_nom, data.machine_id))
    for oper_id in data.operateur_ids:
        exe(db, "INSERT IGNORE INTO op_operateurs (operation_id,operateur_id) VALUES (%s,%s)",
            (op_id, oper_id))
    return {"id": op_id, "message": "Opération ajoutée"}


@router.put("/{op_id}")
def update_operation(of_id: int, op_id: int, data: OperationUpdate,
                     user=Depends(require_any_role), db=Depends(get_db)):
    op = _get_op(db, of_id, op_id)
    fields, params = [], []

    if data.operation_nom is not None: fields.append("operation_nom=%s"); params.append(data.operation_nom)
    if data.machine_id    is not None: fields.append("machine_id=%s");    params.append(data.machine_id)
    if data.notes         is not None: fields.append("notes=%s");         params.append(data.notes)
    if data.duree_reelle  is not None: fields.append("duree_reelle=%s");  params.append(data.duree_reelle)

    if data.statut is not None:
        fields.append("statut=%s"); params.append(data.statut)
        if data.statut == "IN_PROGRESS":
            fields.append("debut=%s"); params.append(datetime.now())
        elif data.statut == "COMPLETED":
            fields.append("fin=%s"); params.append(datetime.now())
            # Auto-calc duration if not overridden
            if data.duree_reelle is None and op.get("debut"):
                try:
                    dur = int((datetime.now() - op["debut"]).total_seconds() / 60)
                    fields.append("duree_reelle=%s"); params.append(dur)
                except: pass

    if fields:
        params.append(op_id)
        exe(db, f"UPDATE of_operations SET {','.join(fields)} WHERE id=%s", params)

    # Auto-update OF status
    ops = q(db, "SELECT statut FROM of_operations WHERE of_id=%s", (of_id,))
    statuts = [o["statut"] for o in ops]
    if statuts:
        if all(s == "COMPLETED" for s in statuts):
            exe(db, "UPDATE ordres_fabrication SET statut='COMPLETED' WHERE id=%s", (of_id,))
        elif any(s == "IN_PROGRESS" for s in statuts):
            exe(db, "UPDATE ordres_fabrication SET statut='IN_PROGRESS' WHERE id=%s", (of_id,))

    return {"message": f"Opération → {data.statut or 'mis à jour'}"}


@router.delete("/{op_id}", dependencies=[Depends(require_manager_or_admin)])
def delete_operation(of_id: int, op_id: int, db=Depends(get_db)):
    _get_op(db, of_id, op_id)
    exe(db, "DELETE FROM of_operations WHERE id=%s", (op_id,))
    return {"message": "Opération supprimée"}


@router.put("/{op_id}/operateurs")
def set_operateurs(of_id: int, op_id: int, operateur_ids: List[int],
                   user=Depends(require_manager_or_admin), db=Depends(get_db)):
    _get_op(db, of_id, op_id)
    exe(db, "DELETE FROM op_operateurs WHERE operation_id=%s", (op_id,))
    for oid in operateur_ids:
        exe(db, "INSERT IGNORE INTO op_operateurs (operation_id,operateur_id) VALUES (%s,%s)",
            (op_id, oid))
    return {"message": f"{len(operateur_ids)} opérateur(s) assigné(s)"}
