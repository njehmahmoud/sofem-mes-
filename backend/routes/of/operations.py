"""SOFEM MES v6.0 — OF Operations (dynamic étapes)"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List
from datetime import datetime, date
import logging
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import OperationCreate, OperationUpdate
from routes.settings import get_all_settings
from routes.of.snapshot_capture import capture_of_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/of/{of_id}/operations", tags=["of-operations"])


def _get_op(db, of_id, op_id):
    op = q(db, "SELECT * FROM of_operations WHERE id=%s AND of_id=%s",
           (op_id, of_id), one=True)
    if not op: raise HTTPException(404, "Opération introuvable")
    return op


@router.get("")
def list_operations(of_id: int, user=Depends(require_any_role), db=Depends(get_db)):
    ops = q(db, """
        SELECT op.*, m.nom machine_nom
        FROM of_operations op
        LEFT JOIN machines m ON m.id = op.machine_id
        WHERE op.of_id = %s ORDER BY op.ordre, op.id
    """, (of_id,))
    for op in ops:
        op["operateurs"] = q(db, """
            SELECT o.id, o.nom, o.prenom, o.specialite,
                   o.taux_horaire, o.taux_piece, o.type_taux
            FROM op_operateurs oo
            JOIN operateurs o ON o.id = oo.operateur_id
            WHERE oo.operation_id = %s
        """, (op["id"],))
    return serialize(ops)


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def add_operation(of_id: int, data: OperationCreate, db=Depends(get_db)):
    # Auto-order: last + 1
    last = q(db, "SELECT MAX(ordre) mo FROM of_operations WHERE of_id=%s", (of_id,), one=True)
    ordre = (last["mo"] or 0) + 1 if data.ordre is None else data.ordre
    op_id = exe(db, """
        INSERT INTO of_operations (of_id,ordre,operation_nom,machine_id,statut)
        VALUES (%s,%s,%s,%s,'PENDING')
    """, (of_id, ordre, data.operation_nom, data.machine_id))
    for oper_id in data.operateur_ids:
        exe(db, "INSERT IGNORE INTO op_operateurs (operation_id,operateur_id) VALUES (%s,%s)",
            (op_id, oper_id))
    return {"id": op_id, "message": "Opération ajoutée"}


@router.put("/{op_id}")
def update_operation(of_id: int, op_id: int, data: OperationUpdate,
                     user=Depends(require_any_role), db=Depends(get_db)):
    op = _get_op(db, of_id, op_id)
    fields, params = [], []

    if data.operation_nom is not None: fields.append("operation_nom=%s"); params.append(data.operation_nom)
    if data.machine_id    is not None: fields.append("machine_id=%s");    params.append(data.machine_id)
    if data.notes         is not None: fields.append("notes=%s");         params.append(data.notes)
    if data.duree_reelle  is not None: fields.append("duree_reelle=%s");  params.append(data.duree_reelle)

    if data.statut is not None:
        fields.append("statut=%s"); params.append(data.statut)
        if data.statut == "IN_PROGRESS":
            fields.append("debut=%s"); params.append(datetime.now())
        elif data.statut == "COMPLETED":
            fields.append("fin=%s"); params.append(datetime.now())
            # Auto-calc duration if not overridden
            if data.duree_reelle is None and op.get("debut"):
                try:
                    dur = int((datetime.now() - op["debut"]).total_seconds() / 60)
                    fields.append("duree_reelle=%s"); params.append(dur)
                except: pass

    if fields:
        params.append(op_id)
        exe(db, f"UPDATE of_operations SET {','.join(fields)} WHERE id=%s", params)

    # Auto-update OF status
    ops = q(db, "SELECT statut FROM of_operations WHERE of_id=%s", (of_id,))
    statuts = [o["statut"] for o in ops]
    if statuts:
        if all(s == "COMPLETED" for s in statuts):
            exe(db, "UPDATE ordres_fabrication SET statut='COMPLETED' WHERE id=%s", (of_id,))
            
            # ─── CAPTURE SNAPSHOT ──────────────────────────────────
            # Create immutable backup with all OF data when completion done
            capture_of_snapshot(db, of_id, user_id=None)
            
            # Finalize invoice snapshot with actual costs (material + labor)
            try:
                # Get actual material cost from BOM (materials consumed)
                bom_cost = q(db, """
                    SELECT COALESCE(SUM(ob.quantite_requise * m.prix_unitaire), 0) as total
                    FROM of_bom ob
                    JOIN materiaux m ON m.id = ob.materiau_id
                    WHERE ob.of_id = %s
                """, (of_id,), one=True)
                actual_material_cost = float(bom_cost.get("total") or 0)
                
                # Get actual labor cost from completed operations
                ops_data = q(db, """
                    SELECT o.operation_nom, o.duree_reelle, GROUP_CONCAT(o.id) as op_ids
                    FROM of_operations o
                    WHERE o.of_id = %s AND o.statut = 'COMPLETED'
                    GROUP BY o.operation_nom, o.duree_reelle
                """, (of_id,))
                
                actual_labor_cost = 0
                of_info = q(db, "SELECT quantite FROM ordres_fabrication WHERE id=%s", (of_id,), one=True)
                qty = float(of_info.get("quantite", 1)) if of_info else 1
                
                for op_rec in ops_data:
                    op_id_list = op_rec.get("op_ids", "").split(",")
                    # Get operateurs for this operation
                    operateurs = q(db, """
                        SELECT DISTINCT o.taux_horaire, o.taux_piece, o.type_taux
                        FROM op_operateurs oo
                        JOIN operateurs o ON o.id = oo.operateur_id
                        WHERE oo.operation_id IN ({})
                    """.format(",".join(op_id_list)), ())
                    
                    for oper in operateurs:
                        if op_rec.get("operation_nom") and "autocad" in str(op_rec.get("operation_nom", "")).lower():
                            # AutoCAD - pay once per operation
                            if oper.get("type_taux") == "PIECE":
                                actual_labor_cost += float(oper.get("taux_piece", 0))
                        else:
                            # Regular operation - pay per quantity or hourly
                            if oper.get("type_taux") == "PIECE":
                                actual_labor_cost += qty * float(oper.get("taux_piece", 0))
                            elif oper.get("type_taux") == "HORAIRE":
                                duration_hours = (float(op_rec.get("duree_reelle", 0)) or 60) / 60
                                actual_labor_cost += duration_hours * float(oper.get("taux_horaire", 0))
                
                # Get snapshot to calculate margins
                snapshot = q(db, """
                    SELECT montant_vente_ht, cost_sous_traitance, cost_main_oeuvre_estime
                    FROM of_invoice_snapshot
                    WHERE of_id = %s
                """, (of_id,), one=True)
                
                montant_ht = float(snapshot.get("montant_vente_ht", 0)) if snapshot else 0
                sous_traitance = float(snapshot.get("cost_sous_traitance", 0)) if snapshot else 0
                
                actual_total_cost = actual_material_cost + actual_labor_cost + sous_traitance
                actual_margin = montant_ht - actual_total_cost
                margin_pct = (actual_margin / montant_ht * 100) if montant_ht > 0 else 0
                
                # Update invoice snapshot with actual costs
                exe(db, """
                    UPDATE of_invoice_snapshot
                    SET cost_materiel_reel = %s,
                        cost_main_oeuvre_reel = %s,
                        cost_total_reel = %s,
                        marge_brute_reel = %s,
                        marge_pourcentage_reel = %s,
                        snapshot_at_completion = NOW(),
                        updated_by = %s
                    WHERE of_id = %s
                """, (actual_material_cost, actual_labor_cost, actual_total_cost, 
                      actual_margin, margin_pct, None, of_id))
                
                logger.info(f"OF {of_id} completed: Material={actual_material_cost}, Labor={actual_labor_cost}, Total={actual_total_cost}, Margin={actual_margin} ({margin_pct:.1f}%)")
            except Exception as e:
                logger.warning(f"Failed to finalize invoice snapshot for OF {of_id}: {e}")
                import traceback
                traceback.print_exc()
            
            # Auto-create quality ticket if setting enabled
            settings = get_all_settings(db)
            if settings.get("cq_auto_creation"):
                of_data = q(db, "SELECT id, numero, quantite, produit_id FROM ordres_fabrication WHERE id=%s", (of_id,), one=True)
                if of_data and not q(db, "SELECT id FROM controles_qualite WHERE of_id=%s", (of_id,), one=True):
                    count = q(db, "SELECT COUNT(*) as c FROM controles_qualite", one=True)["c"]
                    cq_num = f"CQ-{date.today().year}-{count+1:04d}"
                    exe(db, """
                        INSERT INTO controles_qualite
                        (cq_numero, of_id, type_controle, date_controle, statut, quantite_controlée)
                        VALUES (%s, %s, 'FINAL', %s, 'EN_ATTENTE', %s)
                    """, (cq_num, of_id, date.today(), of_data["quantite"]))
        elif any(s == "IN_PROGRESS" for s in statuts):
            exe(db, "UPDATE ordres_fabrication SET statut='IN_PROGRESS' WHERE id=%s", (of_id,))

    return {"message": f"Opération → {data.statut or 'mis à jour'}"}


@router.delete("/{op_id}", dependencies=[Depends(require_manager_or_admin)])
def delete_operation(of_id: int, op_id: int, db=Depends(get_db)):
    _get_op(db, of_id, op_id)
    exe(db, "DELETE FROM of_operations WHERE id=%s", (op_id,))
    return {"message": "Opération supprimée"}


@router.put("/{op_id}/operateurs")
def set_operateurs(of_id: int, op_id: int, operateur_ids: List[int],
                   user=Depends(require_manager_or_admin), db=Depends(get_db)):
    _get_op(db, of_id, op_id)
    exe(db, "DELETE FROM op_operateurs WHERE operation_id=%s", (op_id,))
    for oid in operateur_ids:
        exe(db, "INSERT IGNORE INTO op_operateurs (operation_id,operateur_id) VALUES (%s,%s)",
            (op_id, oid))
    return {"message": f"{len(operateur_ids)} opérateur(s) assigné(s)"}
