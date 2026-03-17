"""SOFEM MES v2.0 — Operateurs Routes"""

from fastapi import APIRouter, Depends
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import OperateurCreate, OperateurUpdate

router = APIRouter(prefix="/api/operateurs", tags=["operateurs"])

@router.get("", dependencies=[Depends(require_any_role)])
def list_operateurs(db=Depends(get_db)):
    ops = q(db, """SELECT o.*,
        COUNT(DISTINCT of2.id) total_ofs,
        SUM(of2.statut='COMPLETED') ofs_completes
        FROM operateurs o
        LEFT JOIN ordres_fabrication of2 ON o.id=of2.operateur_id
        WHERE o.actif=TRUE GROUP BY o.id ORDER BY o.nom""")
    for op in ops:
        t = op["total_ofs"] or 0
        op["performance"] = round((op["ofs_completes"] or 0) / t * 100, 1) if t > 0 else 0
    return serialize(ops)

@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_operateur(data: OperateurCreate, db=Depends(get_db)):
    oid = exe(db, "INSERT INTO operateurs (nom,prenom,specialite,telephone,email) VALUES (%s,%s,%s,%s,%s)",
              (data.nom, data.prenom, data.specialite, data.telephone, data.email))
    return {"id": oid, "message": "Opérateur créé"}

@router.put("/{op_id}", dependencies=[Depends(require_manager_or_admin)])
def update_operateur(op_id: int, data: OperateurUpdate, db=Depends(get_db)):
    fields, params = [], []
    if data.nom        is not None: fields.append("nom=%s");        params.append(data.nom)
    if data.prenom     is not None: fields.append("prenom=%s");     params.append(data.prenom)
    if data.specialite is not None: fields.append("specialite=%s"); params.append(data.specialite)
    if data.telephone  is not None: fields.append("telephone=%s");  params.append(data.telephone)
    if data.email      is not None: fields.append("email=%s");      params.append(data.email)
    if data.actif      is not None: fields.append("actif=%s");      params.append(data.actif)
    if fields:
        params.append(op_id)
        exe(db, f"UPDATE operateurs SET {','.join(fields)} WHERE id=%s", params)
    return {"message": "Opérateur mis à jour"}

@router.delete("/{op_id}", dependencies=[Depends(require_manager_or_admin)])
def delete_operateur(op_id: int, db=Depends(get_db)):
    # Check if operator has active OFs
    active = q(db, "SELECT COUNT(*) n FROM ordres_fabrication WHERE operateur_id=%s AND statut IN ('DRAFT','APPROVED','IN_PROGRESS')", (op_id,), one=True)["n"]
    if active > 0:
        from fastapi import HTTPException
        raise HTTPException(400, f"Impossible de supprimer: {active} ordre(s) actif(s) assigné(s)")
    exe(db, "DELETE FROM operateurs WHERE id=%s", (op_id,))
    return {"message": "Opérateur supprimé"}
