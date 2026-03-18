"""SOFEM MES v6.0 — OF Core (CRUD)"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import OFCreate, OFUpdate

router = APIRouter(prefix="/api/of", tags=["of"])


def get_of_full(db, of_id):
    of = q(db, """
        SELECT o.*,
               p.nom produit_nom, p.code produit_code,
               CONCAT(cp.prenom,' ',cp.nom) chef_projet_nom,
               c.nom client_nom, c.matricule_fiscal client_mf,
               c.adresse client_adresse, c.ville client_ville,
               c.telephone client_tel
        FROM ordres_fabrication o
        JOIN produits p ON o.produit_id = p.id
        LEFT JOIN operateurs cp ON cp.id = o.chef_projet_id
        LEFT JOIN clients c ON c.id = o.client_id
        WHERE o.id = %s
    """, (of_id,), one=True)
    if not of: return None
    of["operations"] = q(db, """
        SELECT op.*, m.nom machine_nom, m.code machine_code,
               GROUP_CONCAT(CONCAT(o2.prenom,' ',o2.nom) SEPARATOR ', ') operateurs_noms
        FROM of_operations op
        LEFT JOIN machines m ON m.id = op.machine_id
        LEFT JOIN op_operateurs oo ON oo.operation_id = op.id
        LEFT JOIN operateurs o2 ON o2.id = oo.operateur_id
        WHERE op.of_id = %s
        GROUP BY op.id ORDER BY op.ordre, op.id
    """, (of_id,))
    of["bom"] = q(db, """
        SELECT ob.*, m.nom materiau_nom, m.code materiau_code,
               m.unite, m.stock_actuel
        FROM of_bom ob JOIN materiaux m ON m.id = ob.materiau_id
        WHERE ob.of_id = %s ORDER BY m.nom
    """, (of_id,))
    return of


def auto_create_das(db, of_id, produit_id, quantite, bom_overrides):
    """Always reads from of_bom table — must be called AFTER of_bom is saved."""
    das = []
    # Read actual quantities from of_bom (already saved with correct totals)
    saved = q(db, """
        SELECT ob.materiau_id, ob.quantite_requise
        FROM of_bom ob WHERE ob.of_id = %s
    """, (of_id,))
    if saved:
        lines = [{"materiau_id": r["materiau_id"],
                  "quantite_requise": float(r["quantite_requise"])} for r in saved]
    else:
        # Fallback: product BOM × quantite
        raw = q(db, """
            SELECT materiau_id, quantite_par_unite * %s AS quantite_requise
            FROM bom WHERE produit_id = %s
        """, (quantite, produit_id))
        lines = [{"materiau_id": r["materiau_id"],
                  "quantite_requise": float(r["quantite_requise"])} for r in raw]

    year = datetime.now().year
    for line in lines:
        mat = q(db, "SELECT * FROM materiaux WHERE id=%s", (line["materiau_id"],), one=True)
        if not mat: continue
        needed = float(line["quantite_requise"])
        stock  = float(mat["stock_actuel"])
        minimum = float(mat["stock_minimum"])
        if stock >= needed: continue
        shortfall = needed - stock
        da_qty = round(shortfall * 1.2 + minimum, 3)
        last = q(db, "SELECT da_numero FROM demandes_achat ORDER BY id DESC LIMIT 1", one=True)
        try: n = int(last["da_numero"].split("-")[-1]) + 1 if last else 1
        except: n = 1
        da_num = f"DA-{year}-{str(n).zfill(3)}"
        exe(db, """
            INSERT INTO demandes_achat
              (da_numero,of_id,materiau_id,description,quantite,unite,urgence,statut,notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'PENDING',%s)
        """, (da_num, of_id, mat["id"],
              f"Auto — {mat['nom']} pour OF #{of_id}", da_qty, mat["unite"],
              "URGENT" if shortfall > stock * 0.5 else "NORMAL",
              f"Stock:{stock} | Requis:{needed} | Manque:{shortfall}"))
        das.append({"da_numero": da_num, "materiau": mat["nom"], "quantite": da_qty})
    return das


@router.get("")
def list_of(statut: Optional[str]=None, priorite: Optional[str]=None,
            limit: int=500, user=Depends(require_any_role), db=Depends(get_db)):
    sql = """
        SELECT o.*, p.nom produit_nom, p.code produit_code,
               CONCAT(cp.prenom,' ',cp.nom) chef_projet_nom,
               c.nom client_nom, c.matricule_fiscal client_mf,
               bl.bl_numero, bl.statut bl_statut, bl.id bl_id
        FROM ordres_fabrication o
        JOIN produits p ON o.produit_id = p.id
        LEFT JOIN operateurs cp ON cp.id = o.chef_projet_id
        LEFT JOIN clients c ON c.id = o.client_id
        LEFT JOIN bons_livraison bl ON bl.of_id = o.id
        WHERE 1=1
    """
    params = []
    if statut:   sql += " AND o.statut=%s";   params.append(statut)
    if priorite: sql += " AND o.priorite=%s"; params.append(priorite)
    sql += f" ORDER BY o.created_at DESC LIMIT {int(limit)}"
    ofs = q(db, sql, params)
    for of in ofs:
        try:
            of["operations"] = q(db, """
                SELECT op.id, op.ordre, op.operation_nom, op.statut,
                       op.debut, op.fin, op.duree_reelle, op.machine_id,
                       m.nom machine_nom,
                       COALESCE(GROUP_CONCAT(
                           DISTINCT CONCAT(o2.prenom,' ',o2.nom)
                           ORDER BY o2.nom SEPARATOR ', '
                       ),'') operateurs_noms
                FROM of_operations op
                LEFT JOIN machines m ON m.id = op.machine_id
                LEFT JOIN op_operateurs oo ON oo.operation_id = op.id
                LEFT JOIN operateurs o2 ON o2.id = oo.operateur_id
                WHERE op.of_id = %s
                GROUP BY op.id, op.ordre, op.operation_nom, op.statut,
                         op.debut, op.fin, op.duree_reelle, op.machine_id, m.nom
                ORDER BY op.ordre, op.id
            """, (of["id"],))
        except Exception:
            of["operations"] = []
    return serialize(ofs)


@router.get("/{of_id}")
def get_of(of_id: int, user=Depends(require_any_role), db=Depends(get_db)):
    of = get_of_full(db, of_id)
    if not of: raise HTTPException(404, "OF non trouvé")
    return serialize(of)


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_of(data: OFCreate, db=Depends(get_db)):
    year = datetime.now().year
    last = q(db, "SELECT numero FROM ordres_fabrication ORDER BY id DESC LIMIT 1", one=True)
    try: num = int(last["numero"].split("-")[-1]) + 1 if last else 1
    except: num = 1
    numero = f"OF-{year}-{str(num).zfill(3)}"

    of_id = exe(db, """
        INSERT INTO ordres_fabrication
          (numero,produit_id,quantite,priorite,statut,
           chef_projet_id,client_id,plan_numero,
           atelier,date_echeance,notes,
           sous_traitant,sous_traitant_op,sous_traitant_cout)
        VALUES (%s,%s,%s,%s,'DRAFT',%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (numero, data.produit_id, data.quantite, data.priorite,
          data.chef_projet_id, data.client_id, data.plan_numero,
          data.atelier, data.date_echeance, data.notes,
          data.sous_traitant, data.sous_traitant_op, data.sous_traitant_cout))

    # Dynamic operations
    for i, op in enumerate(data.operations):
        op_id = exe(db, """
            INSERT INTO of_operations (of_id,ordre,operation_nom,machine_id,statut)
            VALUES (%s,%s,%s,%s,'PENDING')
        """, (of_id, op.ordre if op.ordre else i+1, op.operation_nom, op.machine_id))
        for oper_id in op.operateur_ids:
            exe(db, "INSERT IGNORE INTO op_operateurs (operation_id,operateur_id) VALUES (%s,%s)",
                (op_id, oper_id))

    # BOM
    bom_src = data.bom_overrides
    if not bom_src:
        raw = q(db, "SELECT materiau_id, quantite_par_unite*%s qr FROM bom WHERE produit_id=%s",
                (data.quantite, data.produit_id))
        from models import BOMOverride
        bom_src = [BOMOverride(materiau_id=r["materiau_id"],
                               quantite_requise=float(r["qr"])) for r in raw]
    else:
        from models import BOMOverride
        bom_src = [BOMOverride(materiau_id=b.materiau_id,
                               quantite_requise=b.quantite_requise*data.quantite)
                   for b in bom_src]
    for b in bom_src:
        exe(db, """
            INSERT INTO of_bom (of_id,materiau_id,quantite_requise) VALUES (%s,%s,%s)
            ON DUPLICATE KEY UPDATE quantite_requise=VALUES(quantite_requise)
        """, (of_id, b.materiau_id, b.quantite_requise))

    # Auto BL
    bl_numero = None
    try:
        last_bl = q(db, "SELECT bl_numero FROM bons_livraison ORDER BY id DESC LIMIT 1", one=True)
        try: bn = int(last_bl["bl_numero"].split("-")[-1]) + 1 if last_bl else 1
        except: bn = 1
        bl_numero = f"BL-{year}-{str(bn).zfill(3)}"
        dest, addr = "SOFEM", "Route Sidi Salem 2.5KM, Sfax"
        if data.client_id:
            cl = q(db, "SELECT nom,adresse FROM clients WHERE id=%s", (data.client_id,), one=True)
            if cl: dest = cl["nom"]; addr = cl["adresse"] or addr
        exe(db, """
            INSERT INTO bons_livraison (bl_numero,of_id,destinataire,adresse,statut)
            VALUES (%s,%s,%s,%s,'DRAFT')
        """, (bl_numero, of_id, dest, addr))
    except: bl_numero = None

    das = auto_create_das(db, of_id, data.produit_id, data.quantite, data.bom_overrides)

    return {"id": of_id, "numero": numero, "bl_numero": bl_numero,
            "das_crees": das,
            "message": f"OF {numero} créé" + (f" — {len(das)} DA(s)" if das else "")}


@router.put("/{of_id}")
def update_of(of_id: int, data: OFUpdate,
              user=Depends(require_any_role), db=Depends(get_db)):
    of = q(db, "SELECT id,statut,quantite,produit_id FROM ordres_fabrication WHERE id=%s",
           (of_id,), one=True)
    if not of: raise HTTPException(404, "OF non trouvé")

    # Block advancing to IN_PROGRESS if stock insufficient
    if data.statut == "IN_PROGRESS" and of["statut"] in ("DRAFT","APPROVED"):
        shortfalls = []
        bom = q(db, """
            SELECT ob.quantite_requise, m.nom, m.unite,
                   m.stock_actuel, m.stock_minimum, m.id materiau_id
            FROM of_bom ob JOIN materiaux m ON m.id = ob.materiau_id
            WHERE ob.of_id = %s
        """, (of_id,))
        for b in bom:
            needed = float(b["quantite_requise"])
            stock  = float(b["stock_actuel"])
            if stock < needed:
                shortfalls.append({
                    "materiau": b["nom"],
                    "unite": b["unite"],
                    "stock": stock,
                    "requis": needed,
                    "manque": round(needed - stock, 3)
                })
        if shortfalls:
            # Auto-create DAs for missing materials
            das = auto_create_das(db, of_id, of["produit_id"], of["quantite"], [])
            raise HTTPException(409, {
                "message": "Stock insuffisant — production bloquée",
                "shortfalls": shortfalls,
                "das_crees": das
            })

    fields, params = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s"); params.append(v)
    if fields:
        params.append(of_id)
        exe(db, f"UPDATE ordres_fabrication SET {','.join(fields)} WHERE id=%s", params)
    return {"message": "OF mis à jour"}


@router.delete("/{of_id}", dependencies=[Depends(require_manager_or_admin)])
def delete_of(of_id: int, db=Depends(get_db)):
    of = q(db, "SELECT statut FROM ordres_fabrication WHERE id=%s", (of_id,), one=True)
    if not of: raise HTTPException(404, "OF non trouvé")
    if of["statut"] in ("COMPLETED", "CANCELLED"):
        raise HTTPException(400, f"Impossible de supprimer un OF {of['statut']}")
    # Cascade delete: of_operations, op_operateurs, of_bom, bons_livraison handled by FK
    exe(db, "DELETE FROM ordres_fabrication WHERE id=%s", (of_id,))
    return {"message": "OF supprimé"}


@router.put("/{of_id}/full")
def update_of_full(of_id: int, data: OFCreate,
                   user=Depends(require_manager_or_admin), db=Depends(get_db)):
    """Full edit of an OF — header + operations + BOM."""
    of = q(db, "SELECT id,statut FROM ordres_fabrication WHERE id=%s", (of_id,), one=True)
    if not of: raise HTTPException(404, "OF non trouvé")
    if of["statut"] == "COMPLETED":
        raise HTTPException(400, "Impossible de modifier un OF terminé")

    # Update header fields
    exe(db, """
        UPDATE ordres_fabrication SET
          produit_id=%s, quantite=%s, priorite=%s,
          chef_projet_id=%s, client_id=%s, plan_numero=%s,
          atelier=%s, date_echeance=%s, notes=%s,
          sous_traitant=%s, sous_traitant_op=%s, sous_traitant_cout=%s
        WHERE id=%s
    """, (data.produit_id, data.quantite, data.priorite,
          data.chef_projet_id, data.client_id, data.plan_numero,
          data.atelier, data.date_echeance, data.notes,
          data.sous_traitant, data.sous_traitant_op, data.sous_traitant_cout,
          of_id))

    # Replace operations
    exe(db, "DELETE FROM of_operations WHERE of_id=%s", (of_id,))
    for i, op in enumerate(data.operations):
        op_id = exe(db, """
            INSERT INTO of_operations (of_id,ordre,operation_nom,machine_id,statut)
            VALUES (%s,%s,%s,%s,'PENDING')
        """, (of_id, op.ordre if op.ordre else i+1, op.operation_nom, op.machine_id))
        for oper_id in op.operateur_ids:
            exe(db, "INSERT IGNORE INTO op_operateurs (operation_id,operateur_id) VALUES (%s,%s)",
                (op_id, oper_id))

    # Replace BOM
    exe(db, "DELETE FROM of_bom WHERE of_id=%s", (of_id,))
    bom_src = data.bom_overrides if data.bom_overrides else []
    if not bom_src:
        raw = q(db, "SELECT materiau_id, quantite_par_unite*%s qr FROM bom WHERE produit_id=%s",
                (data.quantite, data.produit_id))
        from models import BOMOverride
        bom_src = [BOMOverride(materiau_id=r["materiau_id"],
                               quantite_requise=float(r["qr"])) for r in raw]
    for b in bom_src:
        exe(db, """
            INSERT INTO of_bom (of_id,materiau_id,quantite_requise) VALUES (%s,%s,%s)
        """, (of_id, b.materiau_id, b.quantite_requise))

    return {"message": "OF mis à jour complet"}