"""
SOFEM MES v7.0 — Snapshot Capture Function
Captures complete snapshot when OF is COMPLETED
Called automatically when all operations are done
"""

import json
import logging
from datetime import datetime
from database import q, exe

logger = logging.getLogger(__name__)


def capture_of_snapshot(db, of_id, user_id=None):
    """
    Capture immutable snapshot when OF is COMPLETED.
    
    Snapshot contains:
    - OF-id, OF numero
    - Product: id, name, quantity, unit_price, line_total
    - Materials: id, name, quantity, unit, unit_price, line_total (sum)
    - Operations: name, hours_count, hourly_rate, line_total (sum)
    - Costs: total_material_cost, total_operation_cost, total_product_cost, grand_total
    
    Args:
        db: Database connection
        of_id: Manufacturing Order ID
        user_id: User creating snapshot (optional)
    
    Returns:
        dict: Snapshot data or None if failed
    """
    
    try:
        # ─── 1. Get OF and Product Info ────────────────────────────
        of = q(db, """
            SELECT o.id, o.numero, o.quantite, o.produit_id,
                   o.produit_prix_snapshot, o.statut,
                   p.nom produit_nom, p.code produit_code, 
                   p.prix_vente_ht
            FROM ordres_fabrication o
            JOIN produits p ON p.id = o.produit_id
            WHERE o.id = %s
        """, (of_id,), one=True)
        
        if not of:
            logger.error(f"OF not found: {of_id}")
            return None
        
        if of["statut"] != "COMPLETED":
            logger.warning(f"OF {of_id} is not COMPLETED (status: {of['statut']})")
            return None
        
        of_id = of["id"]
        of_numero = of["numero"]
        product_qty = float(of["quantite"])
        product_price = float(of["produit_prix_snapshot"]) or float(of["prix_vente_ht"] or 0)
        product_line_total = product_qty * product_price
        
        # ─── 2. Gather Materials Data ─────────────────────────────
        bom_data = q(db, """
            SELECT ob.materiau_id, m.nom, m.code, ob.quantite_requise,
                   m.unite, m.prix_unitaire,
                   (ob.quantite_requise * m.prix_unitaire) as line_total
            FROM of_bom ob
            JOIN materiaux m ON m.id = ob.materiau_id
            WHERE ob.of_id = %s
            ORDER BY m.nom
        """, (of_id,))
        
        materials = []
        total_material_cost = 0
        
        for mat in bom_data:
            material_record = {
                "material_id": mat["materiau_id"],
                "name": mat["nom"],
                "code": mat["code"],
                "quantity": float(mat["quantite_requise"]),
                "unit": mat["unite"],
                "unit_price": float(mat["prix_unitaire"]),
                "line_total": float(mat["line_total"] or 0)
            }
            materials.append(material_record)
            total_material_cost += material_record["line_total"]
        
        # ─── 3. Gather Operations Data ────────────────────────────
        ops_data = q(db, """
            SELECT o.id, o.operation_nom, o.duree_reelle,
                   GROUP_CONCAT(DISTINCT op.taux_horaire SEPARATOR ',') taux_horaire_list
            FROM of_operations o
            LEFT JOIN op_operateurs oo ON oo.operation_id = o.id
            LEFT JOIN operateurs op ON op.id = oo.operateur_id
            WHERE o.of_id = %s AND o.statut = 'COMPLETED'
            GROUP BY o.id, o.operation_nom, o.duree_reelle
            ORDER BY o.ordre
        """, (of_id,))
        
        operations = []
        total_operation_cost = 0
        
        for op in ops_data:
            hours = float(op["duree_reelle"] or 0) / 60  # Convert minutes to hours
            
            # Get average hourly rate from operateurs assigned to this operation
            operateurs = q(db, """
                SELECT DISTINCT o.taux_horaire, o.nom
                FROM op_operateurs oo
                JOIN operateurs o ON o.id = oo.operateur_id
                WHERE oo.operation_id = %s
            """, (op["id"],))
            
            avg_hourly_rate = 0
            if operateurs:
                rates = [float(o["taux_horaire"] or 0) for o in operateurs]
                avg_hourly_rate = sum(rates) / len(rates) if rates else 0
            
            operation_cost = hours * avg_hourly_rate
            
            operation_record = {
                "operation_id": op["id"],
                "operation_name": op["operation_nom"],
                "hours_count": hours,
                "hourly_rate": avg_hourly_rate,
                "line_total": operation_cost,
                "operateurs_assigned": [o["nom"] for o in operateurs]
            }
            operations.append(operation_record)
            total_operation_cost += operation_cost
        
        # ─── 4. Build Complete Snapshot ───────────────────────────
        snapshot_data = {
            "order_id": of_id,
            "of_numero": of_numero,
            "snapshot_date": datetime.now().isoformat(),
            "product": {
                "id": of["produit_id"],
                "name": of["produit_nom"],
                "code": of["produit_code"],
                "quantity": product_qty,
                "unit_price": product_price,
                "line_total": product_line_total
            },
            "materials": materials,
            "operations": operations,
            "costs": {
                "total_material_cost": round(total_material_cost, 2),
                "total_operation_cost": round(total_operation_cost, 2),
                "total_product_cost": round(product_line_total, 2),
                "grand_total": round(total_material_cost + total_operation_cost + product_line_total, 2)
            },
            "metadata": {
                "created_by": user_id,
                "created_at": datetime.now().isoformat(),
                "status": "locked"
            }
        }
        
        # ─── 5. Store in Database ────────────────────────────────
        snapshot_json = json.dumps(snapshot_data, default=str)
        total_cost = snapshot_data["costs"]["grand_total"]
        
        exe(db, """
            INSERT INTO of_invoice_snapshot 
            (order_id, of_numero, snapshot_json, total_cost, created_by)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                snapshot_json = VALUES(snapshot_json),
                total_cost = VALUES(total_cost),
                created_at = NOW()
        """, (of_id, of_numero, snapshot_json, total_cost, user_id))
        
        logger.info(f"✓ Snapshot captured for OF {of_numero}: "
                   f"Materials={total_material_cost:.2f}, "
                   f"Operations={total_operation_cost:.2f}, "
                   f"Product={product_line_total:.2f}, "
                   f"Total={total_cost:.2f}")
        
        return snapshot_data
        
    except Exception as e:
        logger.error(f"✗ Failed to capture snapshot for OF {of_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
