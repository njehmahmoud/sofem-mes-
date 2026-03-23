"""SOFEM MES v6.0 — Clients"""

from fastapi import APIRouter, Depends, HTTPException
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import ClientCreate, ClientUpdate

router = APIRouter(prefix="/api/clients", tags=["clients"])


def next_code(db) -> str:
    rows = q(db, "SELECT code FROM clients WHERE code LIKE 'CLT-%' ORDER BY id DESC LIMIT 1")
    last = 0
    if rows:
        try: last = int(rows[0]["code"].split("-")[-1])
        except: pass
    return f"CLT-{str(last+1).zfill(3)}"


@router.get("", dependencies=[Depends(require_any_role)])
def list_clients(db=Depends(get_db)):
    return serialize(q(db, "SELECT * FROM clients WHERE actif=TRUE ORDER BY nom"))


@router.get("/{cid}", dependencies=[Depends(require_any_role)])
def get_client(cid: int, db=Depends(get_db)):
    c = q(db, "SELECT * FROM clients WHERE id=%s", (cid,), one=True)
    if not c: raise HTTPException(404, "Client introuvable")
    c["ofs"] = q(db, """
        SELECT o.numero, o.statut, o.created_at, p.nom produit_nom
        FROM ordres_fabrication o JOIN produits p ON p.id=o.produit_id
        WHERE o.client_id=%s ORDER BY o.created_at DESC LIMIT 10
    """, (cid,))
    return serialize(c)


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_client(data: ClientCreate, db=Depends(get_db)):
    code = next_code(db)
    cid = exe(db, """
        INSERT INTO clients (code,nom,matricule_fiscal,adresse,ville,telephone,email,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (code, data.nom, data.matricule_fiscal, data.adresse,
          data.ville, data.telephone, data.email, data.notes))
    return {"id": cid, "code": code, "message": f"Client créé — {code}"}


@router.put("/{cid}", dependencies=[Depends(require_manager_or_admin)])
def update_client(cid: int, data: ClientUpdate, db=Depends(get_db)):
    fields, vals = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s"); vals.append(v)
    if not fields: raise HTTPException(400, "Aucune donnée")
    vals.append(cid)
    exe(db, f"UPDATE clients SET {','.join(fields)} WHERE id=%s", vals)
    return {"message": "Client mis à jour"}


@router.delete("/{cid}", dependencies=[Depends(require_manager_or_admin)])
def delete_client(cid: int, db=Depends(get_db)):
    if q(db, "SELECT id FROM ordres_fabrication WHERE client_id=%s LIMIT 1", (cid,), one=True):
        raise HTTPException(400, "Client utilisé dans des OFs")
    exe(db, "DELETE FROM clients WHERE id=%s", (cid,))
    return {"message": "Client supprimé"}
