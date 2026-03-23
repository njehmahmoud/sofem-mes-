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


@router.put("/{br_id}/confirmer", dependencies=[Depends(require_manager_or_admin)])
def confirmer_reception(br_id: int, db=Depends(get_db)):
    """
    Confirm reception of an auto-generated BR (EN_ATTENTE).
    Updates quantite_recue from BC line, updates stock, marks DA as RECEIVED.
    """
    br = q(db, "SELECT * FROM bons_reception WHERE id=%s", (br_id,), one=True)
    if not br: raise HTTPException(404, "BR introuvable")
    if br["statut"] not in ("EN_ATTENTE", "PARTIEL"):
        raise HTTPException(400, f"BR deja traite (statut: {br['statut']})")

    lignes = q(db, """
        SELECT brl.id, brl.bc_ligne_id, brl.quantite_recue,
               bcl.materiau_id, bcl.quantite as quantite_commandee,
               bcl.unite, m.nom materiau_nom, m.stock_actuel
        FROM br_lignes brl
        JOIN bc_lignes bcl ON bcl.id = brl.bc_ligne_id
        LEFT JOIN materiaux m ON m.id = bcl.materiau_id
        WHERE brl.br_id = %s
    """, (br_id,))

    stock_updates = []
    for l in lignes:
        # Use commanded quantity as received if quantite_recue is 0
        qte_recue = float(l["quantite_recue"])
        if qte_recue == 0:
            qte_recue = float(l["quantite_commandee"])
            exe(db, "UPDATE br_lignes SET quantite_recue=%s WHERE id=%s",
                (qte_recue, l["id"]))

        if l["materiau_id"] and qte_recue > 0:
            avant = float(l["stock_actuel"] or 0)
            apres = avant + qte_recue
            exe(db, "UPDATE materiaux SET stock_actuel=%s WHERE id=%s",
                (apres, l["materiau_id"]))
            exe(db, """
                INSERT INTO mouvements_stock
                  (materiau_id, type, quantite, stock_avant, stock_apres, motif)
                VALUES (%s, 'ENTREE', %s, %s, %s, %s)
            """, (l["materiau_id"], qte_recue, avant, apres,
                  f"Reception {br['br_numero']}"))
            stock_updates.append({
                "materiau": l["materiau_nom"],
                "quantite": qte_recue,
                "stock_avant": avant,
                "stock_apres": apres
            })

    # Mark BR as COMPLET + set date
    exe(db, """
        UPDATE bons_reception
        SET statut='COMPLET', date_reception=CURDATE()
        WHERE id=%s
    """, (br_id,))

    # Mark BC as RECU
    exe(db, "UPDATE bons_commande SET statut='RECU' WHERE id=%s", (br["bc_id"],))

    # Mark DA as RECEIVED
    da = q(db, "SELECT id FROM demandes_achat WHERE id=(SELECT da_id FROM bons_commande WHERE id=%s)",
           (br["bc_id"],), one=True)
    if da:
        exe(db, "UPDATE demandes_achat SET statut='RECEIVED' WHERE id=%s", (da["id"],))

    return {
        "message": f"Reception confirmee — {len(stock_updates)} materiau(x) mis a jour",
        "stock_updates": stock_updates
    }


@router.put("/{br_id}/quantite", dependencies=[Depends(require_manager_or_admin)])
def update_br_quantite(br_id: int, quantite_recue: float, db=Depends(get_db)):
    """Update the received quantity before confirming (partial reception)."""
    br = q(db, "SELECT id, statut FROM bons_reception WHERE id=%s", (br_id,), one=True)
    if not br: raise HTTPException(404, "BR introuvable")
    if br["statut"] == "COMPLET":
        raise HTTPException(400, "BR deja complete")
    # Update first line (single-line auto-generated BR)
    exe(db, """
        UPDATE br_lignes SET quantite_recue=%s
        WHERE br_id=%s
        ORDER BY id LIMIT 1
    """, (quantite_recue, br_id))
    if br["statut"] == "EN_ATTENTE":
        exe(db, "UPDATE bons_reception SET statut='PARTIEL' WHERE id=%s", (br_id,))
    return {"message": "Quantite mise a jour"}