"""SOFEM MES v6.0 — Bons de Réception"""

from fastapi import APIRouter, Depends
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import BRCreate
from datetime import datetime

router = APIRouter(prefix="/api/achats/br", tags=["achats-br"])


def gen_num(db):
    last = q(db, "SELECT br_numero FROM bons_reception ORDER BY id DESC LIMIT 1", one=True)
    year = datetime.now().year
    try: n = int(last["br_numero"].split("-")[-1]) + 1 if last else 1
    except: n = 1
    return f"BR-{year}-{str(n).zfill(3)}"


@router.get("", dependencies=[Depends(require_any_role)])
def list_br(db=Depends(get_db)):
    brs = serialize(q(db, """
        SELECT br.*, bc.bc_numero, bc.fournisseur
        FROM bons_reception br
        JOIN bons_commande bc ON br.bc_id = bc.id
        ORDER BY br.created_at DESC
    """))
    for br in brs:
        br["lignes"] = serialize(q(db, """
            SELECT brl.*, bcl.description, bcl.unite, m.nom materiau_nom
            FROM br_lignes brl
            JOIN bc_lignes bcl ON brl.bc_ligne_id = bcl.id
            LEFT JOIN materiaux m ON bcl.materiau_id = m.id
            WHERE brl.br_id = %s
        """, (br["id"],)))
    return brs


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_br(data: BRCreate, db=Depends(get_db)):
    numero = gen_num(db)
    br_id = exe(db, """
        INSERT INTO bons_reception (br_numero,bc_id,date_reception,statut,notes)
        VALUES (%s,%s,%s,%s,%s)
    """, (numero, data.bc_id, data.date_reception, data.statut, data.notes))

    for l in data.lignes:
        exe(db, "INSERT INTO br_lignes (br_id,bc_ligne_id,quantite_recue) VALUES (%s,%s,%s)",
            (br_id, l.bc_ligne_id, l.quantite_recue))
        bcl = q(db, "SELECT materiau_id FROM bc_lignes WHERE id=%s", (l.bc_ligne_id,), one=True)
        if bcl and bcl["materiau_id"]:
            mat = q(db, "SELECT stock_actuel FROM materiaux WHERE id=%s",
                    (bcl["materiau_id"],), one=True)
            if mat:
                avant = float(mat["stock_actuel"])
                apres = avant + float(l.quantite_recue)
                exe(db, "UPDATE materiaux SET stock_actuel=%s WHERE id=%s",
                    (apres, bcl["materiau_id"]))
                exe(db, """
                    INSERT INTO mouvements_stock
                      (materiau_id,type,quantite,stock_avant,stock_apres,motif)
                    VALUES (%s,'ENTREE',%s,%s,%s,%s)
                """, (bcl["materiau_id"], l.quantite_recue, avant, apres, f"Réception {numero}"))

    exe(db, "UPDATE bons_commande SET statut=%s WHERE id=%s",
        ("RECU" if data.statut == "COMPLET" else "RECU_PARTIEL", data.bc_id))
    return {"id": br_id, "br_numero": numero, "message": "BR créé — stock mis à jour"}
