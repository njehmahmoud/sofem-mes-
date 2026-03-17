"""SOFEM MES v2.0 — Ordres de Fabrication Routes"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin, get_current_user
from models import OFCreate, OFUpdate, EtapeUpdate

router = APIRouter(prefix="/api/of", tags=["of"])

STAGES = ['AutoCAD','Découpage','Pliage','Soudage','Ponçage']

def get_of_with_etapes(db, of_id):
    of = q(db, """SELECT o.*, p.nom produit_nom, p.code produit_code,
        CONCAT(op.prenom,' ',op.nom) operateur_nom
        FROM ordres_fabrication o
        JOIN produits p ON o.produit_id=p.id
        LEFT JOIN operateurs op ON o.operateur_id=op.id
        WHERE o.id=%s""", (of_id,), one=True)
    if of:
        of["etapes"] = q(db, """SELECT e.*, CONCAT(op.prenom,' ',op.nom) operateur_nom
            FROM etapes_production e LEFT JOIN operateurs op ON e.operateur_id=op.id
            WHERE e.of_id=%s ORDER BY FIELD(e.etape,'AutoCAD','Découpage','Pliage','Soudage','Ponçage')""", (of_id,))
    return of

@router.get("")
def list_of(
    statut: Optional[str] = None,
    priorite: Optional[str] = None,
    operateur_id: Optional[int] = None,
    limit: int = 100,
    user: dict = Depends(require_any_role),
    db=Depends(get_db)
):
    sql = """SELECT o.*, p.nom produit_nom, p.code produit_code,
        CONCAT(op.prenom,' ',op.nom) operateur_nom
        FROM ordres_fabrication o
        JOIN produits p ON o.produit_id=p.id
        LEFT JOIN operateurs op ON o.operateur_id=op.id WHERE 1=1"""
    params = []

    # OPERATOR role — force filter to their own OFs only
    if user["role"] == "OPERATOR" and user.get("operateur_id"):
        sql += " AND o.operateur_id=%s"; params.append(user["operateur_id"])
    elif operateur_id:
        sql += " AND o.operateur_id=%s"; params.append(operateur_id)

    if statut:   sql += " AND o.statut=%s";   params.append(statut)
    if priorite: sql += " AND o.priorite=%s"; params.append(priorite)
    sql += f" ORDER BY o.created_at DESC LIMIT {int(limit)}"

    ofs = q(db, sql, params)
    for of in ofs:
        of["etapes"] = q(db, """SELECT e.*, CONCAT(op.prenom,' ',op.nom) operateur_nom
            FROM etapes_production e LEFT JOIN operateurs op ON e.operateur_id=op.id
            WHERE e.of_id=%s ORDER BY FIELD(e.etape,'AutoCAD','Découpage','Pliage','Soudage','Ponçage')""", (of["id"],))
    return serialize(ofs)

@router.get("/{of_id}")
def get_of(of_id: int, user: dict = Depends(require_any_role), db=Depends(get_db)):
    of = get_of_with_etapes(db, of_id)
    if not of: raise HTTPException(404, "OF non trouvé")
    # Operator can only see their own OFs
    if user["role"] == "OPERATOR" and of.get("operateur_id") != user.get("operateur_id"):
        raise HTTPException(403, "Accès non autorisé")
    return serialize(of)

@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_of(data: OFCreate, db=Depends(get_db)):
    last = q(db, "SELECT numero FROM ordres_fabrication ORDER BY id DESC LIMIT 1", one=True)
    year = datetime.now().year
    num  = (int(last["numero"].split("-")[-1]) + 1) if last else 1
    numero = f"OF-{year}-{str(num).zfill(3)}"
    of_id = exe(db, """INSERT INTO ordres_fabrication
        (numero,produit_id,quantite,priorite,statut,operateur_id,atelier,date_echeance,notes)
        VALUES (%s,%s,%s,%s,'DRAFT',%s,%s,%s,%s)""",
        (numero, data.produit_id, data.quantite, data.priorite,
         data.operateur_id, data.atelier, data.date_echeance, data.notes))
    for etape in STAGES:
        exe(db, "INSERT INTO etapes_production (of_id,etape,statut) VALUES (%s,%s,'PENDING')", (of_id, etape))
    return {"id": of_id, "numero": numero, "message": "OF créé"}

@router.put("/{of_id}")
def update_of(of_id: int, data: OFUpdate, user: dict = Depends(require_any_role), db=Depends(get_db)):
    of = q(db, "SELECT operateur_id,statut FROM ordres_fabrication WHERE id=%s", (of_id,), one=True)
    if not of: raise HTTPException(404, "OF non trouvé")
    # Operators can only update statut on their own OFs
    if user["role"] == "OPERATOR":
        if of["operateur_id"] != user.get("operateur_id"):
            raise HTTPException(403, "Non autorisé")
        if data.statut is None:
            raise HTTPException(403, "Opérateur peut seulement changer le statut")
    fields, params = [], []
    if data.statut       is not None: fields.append("statut=%s");       params.append(data.statut)
    if data.priorite     is not None and user["role"] != "OPERATOR": fields.append("priorite=%s"); params.append(data.priorite)
    if data.operateur_id is not None and user["role"] != "OPERATOR": fields.append("operateur_id=%s"); params.append(data.operateur_id)
    if data.atelier      is not None and user["role"] != "OPERATOR": fields.append("atelier=%s"); params.append(data.atelier)
    if data.notes        is not None: fields.append("notes=%s"); params.append(data.notes)
    if fields:
        params.append(of_id)
        exe(db, f"UPDATE ordres_fabrication SET {','.join(fields)} WHERE id=%s", params)
    return {"message": "OF mis à jour"}

@router.delete("/{of_id}", dependencies=[Depends(require_manager_or_admin)])
def cancel_of(of_id: int, db=Depends(get_db)):
    exe(db, "UPDATE ordres_fabrication SET statut='CANCELLED' WHERE id=%s", (of_id,))
    return {"message": "OF annulé"}

@router.put("/{of_id}/etape/{etape_nom}")
def update_etape(of_id: int, etape_nom: str, data: EtapeUpdate, user: dict = Depends(require_any_role), db=Depends(get_db)):
    of = q(db, "SELECT operateur_id FROM ordres_fabrication WHERE id=%s", (of_id,), one=True)
    if not of: raise HTTPException(404, "OF non trouvé")
    # Operator can only update stages on their own OFs
    if user["role"] == "OPERATOR" and of["operateur_id"] != user.get("operateur_id"):
        raise HTTPException(403, "Non autorisé")
    etape = q(db, "SELECT id FROM etapes_production WHERE of_id=%s AND etape=%s", (of_id, etape_nom), one=True)
    if not etape: raise HTTPException(404, "Étape non trouvée")
    exe(db, """UPDATE etapes_production SET statut=%s, operateur_id=%s, notes=%s,
        debut=CASE WHEN %s='IN_PROGRESS' THEN NOW() ELSE debut END,
        fin=CASE WHEN %s='COMPLETED' THEN NOW() ELSE fin END
        WHERE of_id=%s AND etape=%s""",
        (data.statut, data.operateur_id, data.notes, data.statut, data.statut, of_id, etape_nom))
    etapes  = q(db, "SELECT statut FROM etapes_production WHERE of_id=%s", (of_id,))
    statuts = [e["statut"] for e in etapes]
    if all(s == "COMPLETED" for s in statuts):
        exe(db, "UPDATE ordres_fabrication SET statut='COMPLETED' WHERE id=%s", (of_id,))
    elif any(s == "IN_PROGRESS" for s in statuts):
        exe(db, "UPDATE ordres_fabrication SET statut='IN_PROGRESS' WHERE id=%s", (of_id,))
    return {"message": f"{etape_nom} → {data.statut}"}
