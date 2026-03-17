"""SOFEM MES v6.0 — Factures Achat"""

from fastapi import APIRouter, Depends, HTTPException
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import FACreate
from datetime import datetime

router = APIRouter(prefix="/api/achats/fa", tags=["achats-fa"])
TVA_RATE = 19.0


def gen_num(db):
    last = q(db, "SELECT fa_numero FROM factures_achat ORDER BY id DESC LIMIT 1", one=True)
    year = datetime.now().year
    try: n = int(last["fa_numero"].split("-")[-1]) + 1 if last else 1
    except: n = 1
    return f"FA-{year}-{str(n).zfill(3)}"


@router.get("", dependencies=[Depends(require_any_role)])
def list_fa(db=Depends(get_db)):
    return serialize(q(db, """
        SELECT fa.*, bc.bc_numero
        FROM factures_achat fa
        JOIN bons_commande bc ON fa.bc_id = bc.id
        ORDER BY fa.created_at DESC
    """))


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_fa(data: FACreate, db=Depends(get_db)):
    numero = gen_num(db)
    bc = q(db, "SELECT id FROM bons_commande WHERE id=%s", (data.bc_id,), one=True)
    if not bc: raise HTTPException(404, "BC non trouvé")
    lignes = q(db, "SELECT quantite,prix_unitaire FROM bc_lignes WHERE bc_id=%s", (data.bc_id,))
    ht  = sum(float(l["quantite"])*float(l["prix_unitaire"]) for l in lignes)
    tva = round(ht*TVA_RATE/100, 3)
    ttc = round(ht+tva, 3)
    fa_id = exe(db, """
        INSERT INTO factures_achat
          (fa_numero,bc_id,fournisseur,date_facture,montant_ht,tva,montant_ttc,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (numero, data.bc_id, data.fournisseur, data.date_facture, ht, tva, ttc, data.notes))
    return {"id": fa_id, "fa_numero": numero, "montant_ttc": ttc, "message": "Facture créée"}


@router.put("/{fa_id}/payer", dependencies=[Depends(require_manager_or_admin)])
def payer_fa(fa_id: int, db=Depends(get_db)):
    exe(db, "UPDATE factures_achat SET statut='PAYEE' WHERE id=%s", (fa_id,))
    return {"message": "Facture payée"}
