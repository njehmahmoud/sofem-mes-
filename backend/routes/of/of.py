"""SOFEM MES v6.0 — OF Core (patched)"""

import logging
_logger = logging.getLogger("sofem-of")
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database import get_db, q, exe, exe_raw, begin, commit, rollback, serialize, temp_numero, finalize_number, cancel_document, log_activity
from auth import require_any_role, require_manager_or_admin, get_current_user
from models import OFCreate, OFUpdate, BOMOverride, CancelRequest
from routes.settings import get_all_settings

logger = logging.getLogger("sofem-of")

router = APIRouter(prefix="/api/of", tags=["of"])


# ── Full OF fetch ─────────────────────────────────────────

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
    if not of:
        return None
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


# ── Auto-create DAs for material shortfalls ───────────────

def auto_create_das(db, of_id, produit_id, quantite, bom_overrides):
    """Always reads from of_bom table — must be called AFTER of_bom is saved."""
    year = datetime.now().year
    das = []
    saved = q(db, """
        SELECT ob.materiau_id, ob.quantite_requise
        FROM of_bom ob WHERE ob.of_id = %s
    """, (of_id,))
    if saved:
        lines = [{"materiau_id": r["materiau_id"],
                  "quantite_requise": float(r["quantite_requise"])} for r in saved]
    else:
        raw = q(db, """
            SELECT materiau_id, quantite_par_unite * %s AS quantite_requise
            FROM bom WHERE produit_id = %s
        """, (quantite, produit_id))
        lines = [{"materiau_id": r["materiau_id"],
                  "quantite_requise": float(r["quantite_requise"])} for r in raw]

    for line in lines:
        mat = q(db, "SELECT * FROM materiaux WHERE id=%s", (line["materiau_id"],), one=True)
        if not mat:
            continue
        needed  = float(line["quantite_requise"])
        stock   = float(mat["stock_actuel"])
        minimum = float(mat["stock_minimum"])
        if stock >= needed:
            continue
        shortfall = needed - stock
        da_qty = round(shortfall * 1.2 + minimum, 3)
        urgence = "URGENT" if shortfall > stock * 0.5 else "NORMAL"

        # Race-free DA numbering: insert with temp, finalize with id
        tmp = temp_numero()
        da_id = exe(db, """
            INSERT INTO demandes_achat
              (da_numero, of_id, materiau_id, description, quantite, unite, urgence, statut, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDING', %s)
        """, (tmp, of_id, mat["id"],
              f"Auto — {mat['nom']} pour OF #{of_id}",
              da_qty, mat["unite"], urgence,
              f"Stock:{stock} | Requis:{needed} | Manque:{shortfall}"))
        da_num = finalize_number(db, "demandes_achat", "da_numero", da_id, "DA", year)
        das.append({"da_numero": da_num, "materiau": mat["nom"], "quantite": da_qty})
    return das


# ── LIST OF ───────────────────────────────────────────────

@router.get("")
def list_of(statut: Optional[str] = None, priorite: Optional[str] = None,
            limit: int = 100, offset: int = 0,
            user=Depends(require_any_role), db=Depends(get_db)):
    """
    Returns a paginated list of OFs.
    Default limit reduced to 100 (was 500). Use offset for pagination.
    Operations are fetched in ONE batched query — not one per OF.
    """
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
    sql += f" ORDER BY o.created_at DESC LIMIT {int(limit)} OFFSET {int(offset)}"
    ofs = q(db, sql, params)

    if not ofs:
        return serialize(ofs)

    # ── Batch-fetch all operations in ONE query (eliminates N+1) ──
    of_ids = [of["id"] for of in ofs]
    placeholders = ",".join(["%s"] * len(of_ids))
    all_ops = q(db, f"""
        SELECT op.id, op.of_id, op.ordre, op.operation_nom, op.statut,
               op.debut, op.fin, op.duree_reelle, op.machine_id,
               m.nom machine_nom,
               COALESCE(
                   GROUP_CONCAT(
                       DISTINCT CONCAT(o2.prenom,' ',o2.nom)
                       ORDER BY o2.nom SEPARATOR ', '
                   ), ''
               ) operateurs_noms
        FROM of_operations op
        LEFT JOIN machines m ON m.id = op.machine_id
        LEFT JOIN op_operateurs oo ON oo.operation_id = op.id
        LEFT JOIN operateurs o2 ON o2.id = oo.operateur_id
        WHERE op.of_id IN ({placeholders})
        GROUP BY op.id, op.of_id, op.ordre, op.operation_nom, op.statut,
                 op.debut, op.fin, op.duree_reelle, op.machine_id, m.nom
        ORDER BY op.of_id, op.ordre, op.id
    """, of_ids)

    # Group by of_id in Python — O(n) single pass
    ops_by_of: dict = {}
    for op in all_ops:
        ops_by_of.setdefault(op["of_id"], []).append(op)

    for of in ofs:
        of["operations"] = ops_by_of.get(of["id"], [])

    return serialize(ofs)


# ── GET single OF ─────────────────────────────────────────

@router.get("/{of_id}")
def get_of(of_id: int, user=Depends(require_any_role), db=Depends(get_db)):
    of = get_of_full(db, of_id)
    if not of:
        raise HTTPException(404, "OF non trouvé")

    # Cost summary
    try:
        bom = q(db, """
            SELECT ob.quantite_requise, m.prix_unitaire
            FROM of_bom ob JOIN materiaux m ON m.id = ob.materiau_id
            WHERE ob.of_id = %s
        """, (of_id,))
        total_mat = sum(float(b["quantite_requise"]) * float(b["prix_unitaire"] or 0) for b in bom)

        ops = q(db, """
            SELECT op.duree_reelle, op.operation_nom,
                   GROUP_CONCAT(o2.taux_horaire SEPARATOR ',') taux_h,
                   GROUP_CONCAT(o2.taux_piece   SEPARATOR ',') taux_p,
                   GROUP_CONCAT(o2.type_taux    SEPARATOR ',') type_t
            FROM of_operations op
            LEFT JOIN op_operateurs oo ON oo.operation_id = op.id
            LEFT JOIN operateurs o2 ON o2.id = oo.operateur_id
            WHERE op.of_id = %s GROUP BY op.id
        """, (of_id,))
        qte = int(of.get("quantite", 1))
        total_mo = 0
        for op in ops:
            dur = float(op.get("duree_reelle") or 0) / 60
            mult = 1 if "autocad" in str(op.get("operation_nom", "")).lower() else qte
            try:
                th = float((op.get("taux_h") or "0").split(",")[0])
                tp = float((op.get("taux_p") or "0").split(",")[0])
                tt = (op.get("type_t") or "HORAIRE").split(",")[0]
                if tt == "HORAIRE":   total_mo += dur * mult * th
                elif tt == "PIECE":   total_mo += mult * tp
                else:                 total_mo += dur * mult * th + mult * tp
            except Exception as e:
                logger.warning(f"Cost calc error for op in OF {of_id}: {e}")

        st_cost = float(of.get("sous_traitant_cout") or 0)
        of["cout_matieres"]       = round(total_mat, 3)
        of["cout_main_oeuvre"]    = round(total_mo, 3)
        of["cout_sous_traitance"] = round(st_cost, 3)
        of["cout_revient"]        = round(total_mat + total_mo + st_cost, 3)
    except Exception as e:
        logger.warning(f"Cost summary failed for OF {of_id}: {e}")

    return serialize(of)


# ── CREATE OF ─────────────────────────────────────────────

@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_of(data: OFCreate, db=Depends(get_db)):
    year = datetime.now().year

    # ── Race-free OF numbering: insert placeholder, use auto-increment id ──
    tmp = temp_numero()
    of_id = exe(db, """
        INSERT INTO ordres_fabrication
          (numero, produit_id, quantite, priorite, statut,
           chef_projet_id, client_id, plan_numero,
           atelier, date_echeance, notes,
           sous_traitant, sous_traitant_op, sous_traitant_cout)
        VALUES (%s,%s,%s,%s,'DRAFT',%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (tmp, data.produit_id, data.quantite, data.priorite,
          data.chef_projet_id, data.client_id, data.plan_numero,
          data.atelier, data.date_echeance, data.notes,
          data.sous_traitant, data.sous_traitant_op, data.sous_traitant_cout))
    numero = finalize_number(db, "ordres_fabrication", "numero", of_id, "OF", year)

    # Dynamic operations
    for i, op in enumerate(data.operations):
        op_id = exe(db, """
            INSERT INTO of_operations (of_id, ordre, operation_nom, machine_id, statut)
            VALUES (%s,%s,%s,%s,'PENDING')
        """, (of_id, op.ordre if op.ordre else i + 1, op.operation_nom, op.machine_id))
        for oper_id in op.operateur_ids:
            exe(db, "INSERT IGNORE INTO op_operateurs (operation_id, operateur_id) VALUES (%s,%s)",
                (op_id, oper_id))

    # BOM
    bom_src = data.bom_overrides if data.bom_overrides else []
    if not bom_src:
        raw = q(db, "SELECT materiau_id, quantite_par_unite*%s qr FROM bom WHERE produit_id=%s",
                (data.quantite, data.produit_id))
        bom_src = [BOMOverride(materiau_id=r["materiau_id"],
                               quantite_requise=float(r["qr"])) for r in raw]
    for b in bom_src:
        exe(db, """
            INSERT INTO of_bom (of_id, materiau_id, quantite_requise) VALUES (%s,%s,%s)
            ON DUPLICATE KEY UPDATE quantite_requise=VALUES(quantite_requise)
        """, (of_id, b.materiau_id, b.quantite_requise))

    # Auto BL — race-free numbering
    bl_numero = None
    try:
        tmp_bl = temp_numero()
        dest, addr = "SOFEM", "Route Sidi Salem 2.5KM, Sfax"
        if data.client_id:
            cl = q(db, "SELECT nom,adresse FROM clients WHERE id=%s", (data.client_id,), one=True)
            if cl:
                dest = cl["nom"]
                addr = cl["adresse"] or addr
        bl_id = exe(db, """
            INSERT INTO bons_livraison (bl_numero, of_id, destinataire, adresse, statut)
            VALUES (%s,%s,%s,%s,'DRAFT')
        """, (tmp_bl, of_id, dest, addr))
        bl_numero = finalize_number(db, "bons_livraison", "bl_numero", bl_id, "BL", year)
    except Exception as e:
        logger.warning(f"Auto BL creation failed for OF {of_id}: {e}")

    das = auto_create_das(db, of_id, data.produit_id, data.quantite, data.bom_overrides)

    return {
        "id": of_id,
        "numero": numero,
        "bl_numero": bl_numero,
        "das_crees": das,
        "message": f"OF {numero} créé" + (f" — {len(das)} DA(s)" if das else ""),
    }


# ── UPDATE OF ─────────────────────────────────────────────

@router.put("/{of_id}")
def update_of(of_id: int, data: OFUpdate,
              user=Depends(require_any_role), db=Depends(get_db)):
    of = q(db, "SELECT id,statut,quantite,produit_id FROM ordres_fabrication WHERE id=%s",
           (of_id,), one=True)
    if not of:
        raise HTTPException(404, "OF non trouvé")

    # DRAFT → APPROVED: check stock, create DAs, warn on shortfall
    if data.statut == "APPROVED" and of["statut"] == "DRAFT":
        bom = q(db, """
            SELECT ob.quantite_requise, m.nom, m.unite,
                   m.stock_actuel, m.stock_minimum, m.id materiau_id
            FROM of_bom ob JOIN materiaux m ON m.id = ob.materiau_id
            WHERE ob.of_id = %s
        """, (of_id,))
        shortfalls = []
        for b in bom:
            needed = float(b["quantite_requise"])
            stock  = float(b["stock_actuel"])
            if stock < needed:
                shortfalls.append({
                    "materiau": b["nom"], "unite": b["unite"],
                    "stock": stock, "requis": needed,
                    "manque": round(needed - stock, 3),
                })
        if shortfalls:
            das = auto_create_das(db, of_id, of["produit_id"], of["quantite"], [])
            exe(db, "UPDATE ordres_fabrication SET statut='APPROVED' WHERE id=%s", (of_id,))
            raise HTTPException(409, {
                "message": "OF approuvé — stock insuffisant, DAs créées. Démarrage bloqué jusqu'à réception.",
                "shortfalls": shortfalls,
                "das_crees": das,
                "statut": "APPROVED",
            })

    # APPROVED → IN_PROGRESS: block if pending DAs exist
    if data.statut == "IN_PROGRESS" and of["statut"] == "APPROVED":
        pending_das = q(db, """
            SELECT COUNT(*) n FROM demandes_achat
            WHERE of_id = %s AND statut IN ('PENDING', 'ORDERED')
        """, (of_id,), one=True)["n"]
        if pending_das > 0:
            raise HTTPException(409, {
                "message": f"Démarrage bloqué — {pending_das} DA(s) en attente de réception",
                "pending_das": pending_das,
                "statut": "APPROVED",
            })

    # ── Build the field update list ──────────────────────────
    fields, params = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s")
        params.append(v)

    deduct_stock = (
        data.statut == "IN_PROGRESS"
        and of["statut"] == "APPROVED"
        and get_all_settings(db).get("stock_deduction_auto", True)
    )

    if deduct_stock:
        # Read BOM BEFORE opening the transaction (reads are fine outside)
        bom = q(db, """
            SELECT ob.materiau_id, ob.quantite_requise,
                   m.nom, m.unite, m.stock_actuel
            FROM of_bom ob JOIN materiaux m ON m.id = ob.materiau_id
            WHERE ob.of_id = %s
        """, (of_id,))

    # ── Single transaction: status update + stock deduction ──
    try:
        begin(db)

        # 1. Update OF fields
        if fields:
            update_params = params + [of_id]
            exe_raw(db, "UPDATE ordres_fabrication SET " + ",".join(fields) + " WHERE id=%s", update_params)

        # 2. Deduct stock atomically with the status change
        if deduct_stock:
            for b in bom:
                avant  = float(b["stock_actuel"])
                deduct = float(b["quantite_requise"])
                apres  = max(0.0, avant - deduct)
                exe_raw(db, "UPDATE materiaux SET stock_actuel=%s WHERE id=%s",
                        (apres, b["materiau_id"]))
                exe_raw(db, """
                    INSERT INTO mouvements_stock
                      (materiau_id, of_id, type, quantite, stock_avant, stock_apres, motif)
                    VALUES (%s, %s, 'SORTIE', %s, %s, %s, %s)
                """, (b["materiau_id"], of_id, deduct, avant, apres,
                      f"Consommation production OF #{of_id}"))

        commit(db)
    except Exception as e:
        rollback(db)
        logger.error(f"update_of transaction failed for OF {of_id}: {e}")
        raise HTTPException(500, f"Error lors de la mise à jour automatic de stock: {e}")

    return {"message": "OF mis à jour"}


# ── DUPLICATE OF ──────────────────────────────────────────

class DuplicateOverride(BaseModel):
    quantite:       Optional[int]   = None
    priorite:       Optional[str]   = None
    date_echeance:  Optional[str]   = None
    client_id:      Optional[int]   = None
    chef_projet_id: Optional[int]   = None
    plan_numero:    Optional[str]   = None
    notes:          Optional[str]   = None


@router.post("/{of_id}/duplicate", dependencies=[Depends(require_manager_or_admin)])
def duplicate_of(of_id: int, data: DuplicateOverride = DuplicateOverride(), db=Depends(get_db)):
    src = q(db, "SELECT * FROM ordres_fabrication WHERE id=%s", (of_id,), one=True)
    if not src:
        raise HTTPException(404, "OF non trouvé")

    year = datetime.now().year
    tmp = temp_numero()
    new_id = exe(db, """
        INSERT INTO ordres_fabrication
          (numero, produit_id, quantite, priorite, statut,
           chef_projet_id, client_id, plan_numero, atelier,
           date_echeance, notes, sous_traitant, sous_traitant_op, sous_traitant_cout)
        VALUES (%s,%s,%s,%s,'DRAFT',%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (tmp,
          src["produit_id"],
          data.quantite       or src["quantite"],
          data.priorite       or src["priorite"],
          data.chef_projet_id if data.chef_projet_id is not None else src["chef_projet_id"],
          data.client_id      if data.client_id      is not None else src["client_id"],
          data.plan_numero    if data.plan_numero    is not None else src["plan_numero"],
          src["atelier"],
          data.date_echeance  or src["date_echeance"],
          data.notes          if data.notes          is not None else src["notes"],
          src["sous_traitant"], src["sous_traitant_op"], src["sous_traitant_cout"]))
    numero = finalize_number(db, "ordres_fabrication", "numero", new_id, "OF", year)

    # Copy operations + operator assignments
    ops = q(db, "SELECT * FROM of_operations WHERE of_id=%s ORDER BY ordre", (of_id,))
    for op in ops:
        op_id = exe(db, """
            INSERT INTO of_operations (of_id, ordre, operation_nom, machine_id, statut)
            VALUES (%s,%s,%s,%s,'PENDING')
        """, (new_id, op["ordre"], op["operation_nom"], op["machine_id"]))
        for o in q(db, "SELECT operateur_id FROM op_operateurs WHERE operation_id=%s", (op["id"],)):
            exe(db, "INSERT IGNORE INTO op_operateurs (operation_id, operateur_id) VALUES (%s,%s)",
                (op_id, o["operateur_id"]))

    # Copy BOM
    for b in q(db, "SELECT * FROM of_bom WHERE of_id=%s", (of_id,)):
        exe(db, "INSERT INTO of_bom (of_id, materiau_id, quantite_requise) VALUES (%s,%s,%s)",
            (new_id, b["materiau_id"], b["quantite_requise"]))

    # Auto BL — race-free
    try:
        tmp_bl = temp_numero()
        bl_id = exe(db, """
            INSERT INTO bons_livraison (bl_numero, of_id, destinataire, adresse, statut)
            VALUES (%s,%s,%s,%s,'DRAFT')
        """, (tmp_bl, new_id, "SOFEM", "Route Sidi Salem 2.5KM, Sfax"))
        finalize_number(db, "bons_livraison", "bl_numero", bl_id, "BL", year)
    except Exception as e:
        logger.warning(f"Auto BL creation failed for duplicated OF {new_id}: {e}")

    return {"id": new_id, "numero": numero, "message": f"OF dupliqué → {numero}"}


# ── Cancel OF ─────────────────────────────────────────────


@router.delete("/{of_id}", dependencies=[Depends(require_manager_or_admin)])
#
#    from models import CancelRequest
#    from database import cancel_document, log_activity, q, exe
#
# 2. Replace the existing delete_of function with everything below
# ──────────────────────────────────────────────────────────────────────────


def _cancel_of_cascade(db, of_id: int, numero: str,
                        user_id: int, user_nom: str, reason: str) -> dict:
    """
    Full ISO 9001 cascade cancellation for an OF.
    Returns a summary dict of everything that was cancelled / warned.

    Rules:
      BL              → CANCELLED (if not LIVRE)
      Planning slots  → ANNULE
      DA PENDING      → CANCELLED
      DA APPROVED     → CANCELLED
      DA ORDERED      → CANCELLED + warn (BC already sent)
      BC DRAFT        → ANNULE
      BC ENVOYE       → ANNULE + warn manager
      BC RECU_PARTIEL → warn only
      Stock SORTIE    → reversed (ENTREE created)
      NC suggestion   → if any operation was started
    """
    summary = {
        "bl_cancelled":       [],
        "planning_cancelled": [],
        "da_cancelled":       [],
        "bc_cancelled":       [],
        "stock_reversed":     [],
        "warnings":           [],
        "suggest_nc":         False,
    }
    cancel_reason = f"OF {numero} annulé — {reason}"

    # ── 1. Cancel BL ─────────────────────────────────────
    bls = q(db, """
        SELECT id, bl_numero, statut FROM bons_livraison
        WHERE of_id = %s AND statut NOT IN ('LIVRE','CANCELLED')
    """, (of_id,))

    for bl in bls:
        exe(db, """
            UPDATE bons_livraison
            SET statut='CANCELLED', cancel_reason=%s,
                cancelled_by=%s, cancelled_at=NOW()
            WHERE id=%s
        """, (cancel_reason, user_id, bl["id"]))
        log_activity(db, "CANCEL", "BL", bl["id"], bl["bl_numero"],
                     user_id, user_nom, reason=cancel_reason,
                     detail=f"BL {bl['bl_numero']} annulé — OF {numero} annulé")
        summary["bl_cancelled"].append(bl["bl_numero"])

    # ── 2. Cancel Planning slots ──────────────────────────
    plans = q(db, """
        SELECT id FROM planning_production
        WHERE of_id = %s
          AND statut NOT IN ('TERMINE','ANNULE','CANCELLED')
    """, (of_id,))

    for pl in plans:
        exe(db, """
            UPDATE planning_production
            SET statut='ANNULE', cancel_reason=%s,
                cancelled_by=%s, cancelled_at=NOW()
            WHERE id=%s
        """, (cancel_reason, user_id, pl["id"]))
        log_activity(db, "CANCEL", "PLANNING", pl["id"], numero,
                     user_id, user_nom, reason=cancel_reason,
                     detail=f"Créneau planning annulé — OF {numero} annulé")
        summary["planning_cancelled"].append(pl["id"])

    # ── 3. Handle DAs linked to this OF ──────────────────
    das = q(db, """
        SELECT id, da_numero, statut FROM demandes_achat
        WHERE of_id = %s
          AND statut NOT IN ('CANCELLED','RECEIVED')
    """, (of_id,))

    for da in das:
        # Always cancel the DA regardless of status
        exe(db, """
            UPDATE demandes_achat
            SET statut='CANCELLED', cancel_reason=%s,
                cancelled_by=%s, cancelled_at=NOW()
            WHERE id=%s
        """, (cancel_reason, user_id, da["id"]))
        log_activity(db, "CANCEL", "DA", da["id"], da["da_numero"],
                     user_id, user_nom, reason=cancel_reason,
                     detail=f"DA {da['da_numero']} annulée — OF {numero} annulé")
        summary["da_cancelled"].append(da["da_numero"])

        # If DA was ORDERED, a BC exists — handle it
        if da["statut"] == "ORDERED":
            bcs = q(db, """
                SELECT id, bc_numero, statut, fournisseur
                FROM bons_commande
                WHERE da_id = %s
                  AND statut NOT IN ('CANCELLED','ANNULE')
            """, (da["id"],))

            for bc in bcs:
                bc_statut = bc["statut"]

                if bc_statut in ("DRAFT", "ENVOYE"):
                    # Cancel the BC
                    exe(db, """
                        UPDATE bons_commande
                        SET statut='ANNULE', cancel_reason=%s,
                            cancelled_by=%s, cancelled_at=NOW()
                        WHERE id=%s
                    """, (cancel_reason, user_id, bc["id"]))
                    log_activity(db, "CANCEL", "BC", bc["id"], bc["bc_numero"],
                                 user_id, user_nom, reason=cancel_reason,
                                 detail=f"BC {bc['bc_numero']} annulé — OF {numero} annulé")
                    summary["bc_cancelled"].append(bc["bc_numero"])

                    # Extra warning if already sent to supplier
                    if bc_statut == "ENVOYE":
                        summary["warnings"].append(
                            f"⚠ BC {bc['bc_numero']} ({bc['fournisseur']}) était déjà "
                            f"envoyé au fournisseur — contacter le fournisseur "
                            f"pour annuler la commande physiquement"
                        )

                elif bc_statut in ("RECU_PARTIEL", "RECU"):
                    # Goods already received — warn only, do not cancel
                    summary["warnings"].append(
                        f"⚠ BC {bc['bc_numero']} déjà reçu (statut: {bc_statut}) — "
                        f"vérifier le stock et effectuer un ajustement si nécessaire"
                    )

    # ── 4. Reverse stock SORTIE movements for this OF ────
    sorties = q(db, """
        SELECT ms.id, ms.materiau_id, ms.quantite,
               m.nom  materiau_nom,
               m.code materiau_code,
               m.stock_actuel
        FROM mouvements_stock ms
        JOIN materiaux m ON m.id = ms.materiau_id
        WHERE ms.of_id = %s AND ms.type = 'SORTIE'
    """, (of_id,))

    for mv in sorties:
        stock_avant = float(mv["stock_actuel"])
        stock_apres = round(stock_avant + float(mv["quantite"]), 6)

        # Restore the stock
        exe(db, "UPDATE materiaux SET stock_actuel=%s WHERE id=%s",
            (stock_apres, mv["materiau_id"]))

        # Record the reversal as ENTREE
        exe(db, """
            INSERT INTO mouvements_stock
                (materiau_id, of_id, type, quantite,
                 stock_avant, stock_apres, motif)
            VALUES (%s, %s, 'ENTREE', %s, %s, %s, %s)
        """, (
            mv["materiau_id"], of_id, mv["quantite"],
            stock_avant, stock_apres,
            f"Retour stock automatique — OF {numero} annulé"
        ))

        log_activity(
            db, "STOCK_REVERSAL", "MATERIAU",
            mv["materiau_id"], mv["materiau_code"],
            user_id, user_nom,
            old_value={"stock": stock_avant},
            new_value={"stock": stock_apres},
            detail=(f"Stock {mv['materiau_nom']} restauré "
                    f"({stock_avant} → {stock_apres}) — OF {numero} annulé")
        )

        summary["stock_reversed"].append({
            "materiau":    mv["materiau_nom"],
            "code":        mv["materiau_code"],
            "quantite":    float(mv["quantite"]),
            "stock_avant": stock_avant,
            "stock_apres": stock_apres,
        })

    # ── 5. Suggest NC if production had started ───────────
    ops_started = q(db, """
        SELECT COUNT(*) n FROM of_operations
        WHERE of_id = %s
          AND statut IN ('IN_PROGRESS','COMPLETED')
    """, (of_id,), one=True)

    if ops_started and ops_started["n"] > 0:
        summary["suggest_nc"] = True

    return summary


# ── CANCEL ENDPOINTS ──────────────────────────────────────

@router.put("/{of_id}/cancel")
def cancel_of_put(
    of_id: int,
    data:  CancelRequest,
    user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    ISO 9001 — Cancel an OF with full cascade.
    PUT /api/of/{of_id}/cancel  ← called by frontend cancel modal
    """
    of = q(db, """
        SELECT o.*, p.nom produit_nom
        FROM ordres_fabrication o
        JOIN produits p ON p.id = o.produit_id
        WHERE o.id = %s
    """, (of_id,), one=True)

    if not of:
        raise HTTPException(404, "OF introuvable")
    if of["statut"] == "CANCELLED":
        raise HTTPException(400, "OF déjà annulé")
    if of["statut"] == "COMPLETED":
        raise HTTPException(400,
            "Un OF terminé ne peut pas être annulé. "
            "Créer une Non-Conformité si nécessaire.")

    user_id  = user.get("id")
    user_nom = f"{user.get('prenom','')} {user.get('nom','')}".strip()

    # Cancel the OF itself first
    numero = cancel_document(
        db,
        table      = "ordres_fabrication",
        id_col     = "id",
        numero_col = "numero",
        record_id  = of_id,
        user_id    = user_id,
        user_nom   = user_nom,
        reason     = data.reason,
        entity_type= "OF",
        old_statut = of["statut"],
    )

    # Run full cascade
    summary = _cancel_of_cascade(
        db, of_id, numero, user_id, user_nom, data.reason
    )

    # Build human-readable message
    msg_parts = [f"OF {numero} annulé"]
    if summary["bl_cancelled"]:
        msg_parts.append(f"BL: {', '.join(summary['bl_cancelled'])}")
    if summary["da_cancelled"]:
        msg_parts.append(f"DAs: {', '.join(summary['da_cancelled'])}")
    if summary["bc_cancelled"]:
        msg_parts.append(f"BCs: {', '.join(summary['bc_cancelled'])}")
    if summary["stock_reversed"]:
        msg_parts.append(
            f"{len(summary['stock_reversed'])} retour(s) stock"
        )
    if summary["warnings"]:
        msg_parts.append(f"{len(summary['warnings'])} avertissement(s)")

    return {
        "message":    " · ".join(msg_parts),
        "numero":     numero,
        "summary":    summary,
        "suggest_nc": summary["suggest_nc"],
        "warnings":   summary["warnings"],
    }


@router.delete("/{of_id}")
def cancel_of_delete(
    of_id: int,
    data:  CancelRequest,
    user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    DELETE method also triggers cancel — never a physical delete.
    The DB trigger is the final safety net.
    """
    return cancel_of_put(of_id, data, user, db)

# The frontend uses PUT not DELETE for the cancel modal

@router.put("/{of_id}/cancel")
def cancel_of_put(
        of_id: int,
        data: CancelRequest,
        user=Depends(get_current_user),
        db=Depends(get_db)
):
    """
    PUT version of cancel — called by the frontend cancel modal.
    Delegates to the same logic.
    """
    return cancel_of(of_id, data, user, db)


# ── FULL EDIT ─────────────────────────────────────────────

@router.put("/{of_id}/full")
def update_of_full(of_id: int, data: OFCreate,
                   user=Depends(require_manager_or_admin), db=Depends(get_db)):
    """Full edit of an OF — header + operations + BOM."""
    of = q(db, "SELECT id,statut FROM ordres_fabrication WHERE id=%s", (of_id,), one=True)
    if not of:
        raise HTTPException(404, "OF non trouvé")
    if of["statut"] == "COMPLETED":
        raise HTTPException(400, "Impossible de modifier un OF terminé")

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

    exe(db, "DELETE FROM of_operations WHERE of_id=%s", (of_id,))
    for i, op in enumerate(data.operations):
        op_id = exe(db, """
            INSERT INTO of_operations (of_id, ordre, operation_nom, machine_id, statut)
            VALUES (%s,%s,%s,%s,'PENDING')
        """, (of_id, op.ordre if op.ordre else i + 1, op.operation_nom, op.machine_id))
        for oper_id in op.operateur_ids:
            exe(db, "INSERT IGNORE INTO op_operateurs (operation_id, operateur_id) VALUES (%s,%s)",
                (op_id, oper_id))

    exe(db, "DELETE FROM of_bom WHERE of_id=%s", (of_id,))
    bom_src = data.bom_overrides if data.bom_overrides else []
    if not bom_src:
        raw = q(db, "SELECT materiau_id, quantite_par_unite*%s qr FROM bom WHERE produit_id=%s",
                (data.quantite, data.produit_id))
        bom_src = [BOMOverride(materiau_id=r["materiau_id"],
                               quantite_requise=float(r["qr"])) for r in raw]
    for b in bom_src:
        exe(db, """
            INSERT INTO of_bom (of_id, materiau_id, quantite_requise) VALUES (%s,%s,%s)
        """, (of_id, b.materiau_id, b.quantite_requise))

    return {"message": "OF mis à jour complet"}
# ── cancel OF ──────────────────────────────────────────
@router.put("/{of_id}/cancel")
def cancel_of(of_id: int, data: CancelRequest,
              user=Depends(get_current_user), db=Depends(get_db)):
    numero = cancel_document(
        db, "ordres_fabrication", "id", "numero",
        of_id, user["id"],
        f"{user.get('prenom','')} {user.get('nom','')}",
        data.reason, "OF"
    )
    # Also cancel associated BL
    exe(db, """
        UPDATE bons_livraison
        SET statut='CANCELLED', cancel_reason=%s, cancelled_by=%s, cancelled_at=NOW()
        WHERE of_id=%s AND statut != 'LIVRE'
    """, (f"OF {numero} annulé: {data.reason}", user["id"], of_id))
    return {"message": f"OF {numero} annulé", "numero": numero}