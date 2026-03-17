"""
SOFEM MES v4.0 — Fournisseurs
SMARTMOVE · Mahmoud Njeh
"""

from fastapi import APIRouter, Depends, HTTPException
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import FournisseurCreate, FournisseurUpdate

router = APIRouter(prefix="/api/fournisseurs", tags=["fournisseurs"])


@router.get("")
def list_fournisseurs(conn=Depends(get_db), user=Depends(require_any_role)):
    rows = q(conn, "SELECT * FROM fournisseurs ORDER BY nom")
    return serialize(rows)


@router.get("/{fid}")
def get_fournisseur(fid: int, conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    row = q(conn, "SELECT * FROM fournisseurs WHERE id=%s", (fid,), one=True)
    if not row:
        raise HTTPException(404, "Fournisseur introuvable")
    # associated materiaux
    mats = q(conn, """
        SELECT m.code, m.nom, m.unite, mf.prix_unitaire, mf.delai_jours, mf.principal
        FROM materiau_fournisseurs mf
        JOIN materiaux m ON m.id = mf.materiau_id
        WHERE mf.fournisseur_id=%s
    """, (fid,))
    # purchase history
    purchases = q(conn, """
        SELECT bc.bc_numero, bc.statut, bc.created_at,
               SUM(bcl.quantite * bcl.prix_unitaire) as total_ht
        FROM bons_commande bc
        LEFT JOIN bc_lignes bcl ON bcl.bc_id = bc.id
        WHERE bc.fournisseur LIKE CONCAT('%', %s, '%')
        GROUP BY bc.id ORDER BY bc.created_at DESC LIMIT 10
    """, (row["nom"],))
    row["materiaux"] = mats
    row["historique_commandes"] = purchases
    return serialize(row)


@router.post("", status_code=201)
def create_fournisseur(data: FournisseurCreate, conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    if not data.code:
        count = q(conn, "SELECT COUNT(*) as c FROM fournisseurs", one=True)["c"]
        data.code = f"FOURN-{count+1:04d}"
    fid = exe(conn, """
        INSERT INTO fournisseurs (code,nom,contact,telephone,email,adresse,ville,pays,matricule_fiscal,statut,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (data.code, data.nom, data.contact, data.telephone, data.email,
          data.adresse, data.ville, data.pays, data.matricule_fiscal, data.statut, data.notes))
    return {"id": fid, "message": "Fournisseur créé"}


@router.put("/{fid}")
def update_fournisseur(fid: int, data: FournisseurUpdate, conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    fields, vals = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s")
        vals.append(v)
    if not fields:
        raise HTTPException(400, "Aucune donnée")
    vals.append(fid)
    exe(conn, f"UPDATE fournisseurs SET {','.join(fields)} WHERE id=%s", vals)
    return {"message": "Fournisseur mis à jour"}


@router.delete("/{fid}")
def delete_fournisseur(fid: int, conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    exe(conn, "DELETE FROM fournisseurs WHERE id=%s", (fid,))
    return {"message": "Fournisseur supprimé"}
