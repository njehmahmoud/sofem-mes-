"""SOFEM MES v6.0 — Factures Achat"""

from fastapi import APIRouter, Depends, HTTPException
from database import get_db, q, exe, serialize, temp_numero, finalize_number, log_activity
from auth import require_any_role, require_manager_or_admin, get_current_user
from models import FACreate
from datetime import datetime
from routes.settings import get_all_settings

router = APIRouter(prefix="/api/achats/fa", tags=["achats-fa"])


@router.get("", dependencies=[Depends(require_any_role)])
def list_fa(db=Depends(get_db)):
    return serialize(q(db, """
        SELECT fa.*, bc.bc_numero
        FROM factures_achat fa
        JOIN bons_commande bc ON fa.bc_id = bc.id
        ORDER BY fa.created_at DESC
    """))


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_fa(data: FACreate, user=Depends(get_current_user), db=Depends(get_db)):

    TVA_RATE = float(get_all_settings(db).get("tva_rate", 19))
    year = datetime.now().year
    tmp = temp_numero()
    bc = q(db, "SELECT id FROM bons_commande WHERE id=%s", (data.bc_id,), one=True)
    if not bc: raise HTTPException(404, "BC non trouvé")
    
    # Read prices from BR lignes (confirmed reception prices)
    # Join on bc_id via bons_reception
    lignes = q(db, """
        SELECT bcl.quantite, COALESCE(brl.prix_unitaire, bcl.prix_unitaire, 0) as prix_unitaire
        FROM bc_lignes bcl
        LEFT JOIN br_lignes brl ON brl.bc_ligne_id = bcl.id
        WHERE bcl.bc_id=%s
    """, (data.bc_id,))
    
    ht  = sum(float(l["quantite"])*float(l["prix_unitaire"]) for l in lignes)
    tva = round(ht*TVA_RATE/100, 3)
    ttc = round(ht+tva, 3)
    
    fa_id = exe(db, """
        INSERT INTO factures_achat
          (fa_numero,bc_id,fournisseur,date_facture,montant_ht,tva,montant_ttc,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (tmp, data.bc_id, data.fournisseur, data.date_facture, ht, tva, ttc, data.notes))
    
    numero = finalize_number(db, "factures_achat", "fa_numero", fa_id, "FA", year)
    
    log_activity(db, "CREATE", "FA", fa_id, numero,
                 user.get("id"), f"{user.get('prenom','')} {user.get('nom','')}".strip(),
                 new_value={"bc_id": data.bc_id, "montant_ttc": ttc},
                 detail=f"FA {numero} créée — Montant TTC: {ttc} TND")
    
    return {"id": fa_id, "fa_numero": numero, "montant_ttc": ttc, "message": "Facture créée"}


@router.put("/{fa_id}/payer", dependencies=[Depends(require_manager_or_admin)])
def payer_fa(fa_id: int, db=Depends(get_db)):
    exe(db, "UPDATE factures_achat SET statut='PAYEE' WHERE id=%s", (fa_id,))
    return {"message": "Facture payée"}