"""SOFEM MES v8.0 — Operation Types (catalog)"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin

router = APIRouter(prefix="/api/operation-types", tags=["operation-types"])


class OpTypeCreate(BaseModel):
    nom: str
    description: Optional[str] = None
    ordre: int = 0

class OpTypeUpdate(BaseModel):
    nom: Optional[str] = None
    description: Optional[str] = None
    ordre: Optional[int] = None
    actif: Optional[bool] = None


@router.get("", dependencies=[Depends(require_any_role)])
def list_op_types(db=Depends(get_db)):
    return serialize(q(db, """
        SELECT * FROM operation_types
        WHERE actif = TRUE
        ORDER BY ordre, nom
    """))


@router.get("/all", dependencies=[Depends(require_manager_or_admin)])
def list_all_op_types(db=Depends(get_db)):
    return serialize(q(db, "SELECT * FROM operation_types ORDER BY ordre, nom"))


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_op_type(data: OpTypeCreate, db=Depends(get_db)):
    existing = q(db, "SELECT id FROM operation_types WHERE nom=%s", (data.nom,), one=True)
    if existing:
        raise HTTPException(400, f"Opération '{data.nom}' existe déjà")
    oid = exe(db, """
        INSERT INTO operation_types (nom, description, ordre)
        VALUES (%s, %s, %s)
    """, (data.nom, data.description, data.ordre))
    return {"id": oid, "message": f"Opération '{data.nom}' créée"}


@router.put("/{oid}", dependencies=[Depends(require_manager_or_admin)])
def update_op_type(oid: int, data: OpTypeUpdate, db=Depends(get_db)):
    fields, vals = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s"); vals.append(v)
    if not fields: raise HTTPException(400, "Aucune donnée")
    vals.append(oid)
    exe(db, f"UPDATE operation_types SET {','.join(fields)} WHERE id=%s", vals)
    return {"message": "Opération mise à jour"}


@router.delete("/{oid}", dependencies=[Depends(require_manager_or_admin)])
def delete_op_type(oid: int, db=Depends(get_db)):
    # Soft delete — check if used in any OF
    in_use = q(db, """
        SELECT COUNT(*) n FROM of_operations
        WHERE operation_nom = (SELECT nom FROM operation_types WHERE id=%s)
    """, (oid,), one=True)["n"]
    if in_use > 0:
        # Just deactivate instead of hard delete
        exe(db, "UPDATE operation_types SET actif=FALSE WHERE id=%s", (oid,))
        return {"message": f"Opération désactivée ({in_use} OF(s) liés)"}
    exe(db, "DELETE FROM operation_types WHERE id=%s", (oid,))
    return {"message": "Opération supprimée"}
