"""SOFEM MES v6.0 — Opérateurs (with taux horaire/pièce)"""

from fastapi import APIRouter, Depends, HTTPException
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import OperateurCreate, OperateurUpdate

router = APIRouter(prefix="/api/operateurs", tags=["operateurs"])


@router.get("", dependencies=[Depends(require_any_role)])
def list_operateurs(db=Depends(get_db)):
    ops = q(db, """
        SELECT o.*,
               COUNT(DISTINCT oo.operation_id) total_operations,
               COUNT(DISTINCT of2.id) total_ofs
        FROM operateurs o
        LEFT JOIN op_operateurs oo ON oo.operateur_id = o.id
        LEFT JOIN of_operations ops2 ON ops2.id = oo.operation_id
        LEFT JOIN ordres_fabrication of2 ON of2.id = ops2.of_id
        WHERE o.actif = TRUE
        GROUP BY o.id ORDER BY o.nom
    """)
    return serialize(ops)


@router.get("/{op_id}", dependencies=[Depends(require_any_role)])
def get_operateur(op_id: int, db=Depends(get_db)):
    op = q(db, "SELECT * FROM operateurs WHERE id=%s", (op_id,), one=True)
    if not op: raise HTTPException(404, "Opérateur introuvable")
    op["operations_recentes"] = q(db, """
        SELECT ops.operation_nom, ops.statut, ops.debut, ops.fin,
               ops.duree_reelle, of2.numero of_numero
        FROM op_operateurs oo
        JOIN of_operations ops ON ops.id = oo.operation_id
        JOIN ordres_fabrication of2 ON of2.id = ops.of_id
        WHERE oo.operateur_id = %s
        ORDER BY ops.created_at DESC LIMIT 10
    """, (op_id,))
    return serialize(op)


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_operateur(data: OperateurCreate, db=Depends(get_db)):
    oid = exe(db, """
        INSERT INTO operateurs (nom,prenom,specialite,telephone,email,
                                taux_horaire,taux_piece,type_taux)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (data.nom, data.prenom, data.specialite, data.telephone, data.email,
          data.taux_horaire, data.taux_piece, data.type_taux))
    return {"id": oid, "message": "Opérateur créé"}


@router.put("/{op_id}", dependencies=[Depends(require_manager_or_admin)])
def update_operateur(op_id: int, data: OperateurUpdate, db=Depends(get_db)):
    fields, params = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s"); params.append(v)
    if not fields: raise HTTPException(400, "Aucune donnée")
    params.append(op_id)
    exe(db, f"UPDATE operateurs SET {','.join(fields)} WHERE id=%s", params)
    return {"message": "Opérateur mis à jour"}


@router.delete("/{op_id}", dependencies=[Depends(require_manager_or_admin)])
def delete_operateur(op_id: int, db=Depends(get_db)):
    exe(db, "UPDATE operateurs SET actif=FALSE WHERE id=%s", (op_id,))
    return {"message": "Opérateur désactivé"}
