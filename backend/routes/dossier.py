"""SOFEM MES v6.0 — Dossier (Document Folder) - ISO 9001 Traceability
Provides GET /api/of/{of_id}/dossier to gather all related documents for an OF.
Includes: OF, OFs operations, DA, BC, BR, FA, Quality controls, and activity log.
"""

from fastapi import APIRouter, Depends, HTTPException
from database import get_db, q, serialize
from auth import require_any_role
from datetime import datetime

router = APIRouter(prefix="/api/of", tags=["dossier"])


@router.get("/{of_id}/dossier", dependencies=[Depends(require_any_role)])
def get_of_dossier(of_id: int, db=Depends(get_db)):
    """
    Get complete dossier for an OF: documents, operations, QC, activity log.
    ISO 9001 — Full traceability of manufacturing and purchase history.
    """
    
    # ── OF BASE DATA ──────────────────────────────────────
    of = q(db, """
        SELECT o.*, p.nom produit_nom, p.code produit_code,
               c.nom client_nom, c.matricule_fiscal client_mf,
               CONCAT(cp.prenom,' ',cp.nom) chef_projet_nom
        FROM ordres_fabrication o
        LEFT JOIN produits p ON o.produit_id = p.id
        LEFT JOIN clients c ON o.client_id = c.id
        LEFT JOIN operateurs cp ON o.chef_projet_id = cp.id
        WHERE o.id = %s
    """, (of_id,), one=True)
    
    if not of:
        raise HTTPException(404, "OF non trouvée")
    
    of = serialize(of)
    
    # ── OPERATIONS ────────────────────────────────────────
    operations = serialize(q(db, """
        SELECT oo.*, m.nom machine_nom,
               CONCAT(op.prenom,' ',op.nom) operateur_nom
        FROM of_operations oo
        LEFT JOIN machines m ON oo.machine_id = m.id
        LEFT JOIN operateurs op ON oo.operateur_id = op.id
        WHERE oo.of_id = %s
        ORDER BY oo.ordre ASC
    """, (of_id,)))
    
    # ── BOM (Bill of Materials) ───────────────────────────
    bom = serialize(q(db, """
        SELECT m.id, m.code, m.nom, m.unite,
               ob.quantite_requise,
               (ob.quantite_requise * m.prix_unitaire) as montant_estime
        FROM of_bom ob
        JOIN materiaux m ON ob.materiau_id = m.id
        WHERE ob.of_id = %s
        ORDER BY m.nom
    """, (of_id,)))
    
    # ── DEMANDES D'ACHAT (Purchase Requests) ──────────────
    das = serialize(q(db, """
        SELECT da.*, m.nom materiau_nom,
               CONCAT(d.prenom,' ',d.nom) demandeur_nom
        FROM demandes_achat da
        LEFT JOIN materiaux m ON da.materiau_id = m.id
        LEFT JOIN operateurs d ON da.demandeur_id = d.id
        WHERE da.of_id = %s
        ORDER BY da.created_at DESC
    """, (of_id,)))
    
    # Enrich DAs with BC/BR data
    for da in das:
        bc_br = q(db, """
            SELECT bc.id bc_id, bc.bc_numero, bc.statut bc_statut,
                   br.id br_id, br.br_numero, br.statut br_statut
            FROM bons_commande bc
            LEFT JOIN bons_reception br ON br.bc_id = bc.id
            WHERE bc.da_id = %s
            ORDER BY bc.id DESC LIMIT 1
        """, (da["id"],), one=True)
        if bc_br:
            da["bc"] = serialize(bc_br)
    
    # ── BONS DE COMMANDE (Purchase Orders) ────────────────
    bcs = serialize(q(db, """
        SELECT bc.*, da.da_numero,
               GROUP_CONCAT(DISTINCT br.br_numero) br_numeros
        FROM bons_commande bc
        LEFT JOIN demandes_achat da ON bc.da_id = da.id
        LEFT JOIN bons_reception br ON br.bc_id = bc.id
        WHERE bc.da_id IN (SELECT id FROM demandes_achat WHERE of_id = %s)
        GROUP BY bc.id
        ORDER BY bc.created_at DESC
    """, (of_id,)))
    
    for bc in bcs:
        bc["lignes"] = serialize(q(db, """
            SELECT bcl.*, m.nom materiau_nom,
                   (bcl.quantite * bcl.prix_unitaire) as montant_ht
            FROM bc_lignes bcl
            LEFT JOIN materiaux m ON bcl.materiau_id = m.id
            WHERE bcl.bc_id = %s
            ORDER BY bcl.id
        """, (bc["id"],)))
    
    # ── BONS DE RECEPTION (Purchase Receipts) ─────────────
    brs = serialize(q(db, """
        SELECT br.*, bc.bc_numero
        FROM bons_reception br
        JOIN bons_commande bc ON br.bc_id = bc.id
        WHERE bc.da_id IN (SELECT id FROM demandes_achat WHERE of_id = %s)
        ORDER BY br.created_at DESC
    """, (of_id,)))
    
    for br in brs:
        br["lignes"] = serialize(q(db, """
            SELECT brl.*, bcl.description, bcl.unite,
                   m.nom materiau_nom,
                   (brl.quantite_recue * brl.prix_unitaire) as montant_ht
            FROM br_lignes brl
            JOIN bc_lignes bcl ON brl.bc_ligne_id = bcl.id
            LEFT JOIN materiaux m ON bcl.materiau_id = m.id
            WHERE brl.br_id = %s
            ORDER BY brl.id
        """, (br["id"],)))
    
    # ── FACTURES (Invoices) ───────────────────────────────
    fas = serialize(q(db, """
        SELECT fa.*, bc.bc_numero
        FROM factures_achat fa
        JOIN bons_commande bc ON fa.bc_id = bc.id
        WHERE bc.da_id IN (SELECT id FROM demandes_achat WHERE of_id = %s)
        ORDER BY fa.created_at DESC
    """, (of_id,)))
    
    # ── CONTROLES QUALITE (Quality Controls) ──────────────
    qc = serialize(q(db, """
        SELECT cq.*, o.numero of_numero,
               CONCAT(op.prenom,' ',op.nom) operateur_nom
        FROM controles_qualite cq
        LEFT JOIN ordres_fabrication o ON cq.of_id = o.id
        LEFT JOIN operateurs op ON cq.operateur_id = op.id
        WHERE cq.of_id = %s
        ORDER BY cq.created_at DESC
    """, (of_id,)))
    
    # ── NON-CONFORMITES (Non-Conformities) ────────────────
    nc = serialize(q(db, """
        SELECT nc.*, cq.cq_numero,
               CONCAT(r.prenom,' ',r.nom) responsable_nom
        FROM non_conformites nc
        LEFT JOIN controles_qualite cq ON nc.cq_id = cq.id
        LEFT JOIN operateurs r ON nc.responsable_id = r.id
        WHERE nc.of_id = %s
        ORDER BY nc.created_at DESC
    """, (of_id,)))
    
    # ── BONS DE LIVRAISON (Delivery Notes) ────────────────
    bls = serialize(q(db, """
        SELECT bl.*, c.nom client_nom
        FROM bons_livraison bl
        LEFT JOIN clients c ON bl.of_id IS NULL OR c.id = (
            SELECT client_id FROM ordres_fabrication WHERE id = bl.of_id
        )
        WHERE bl.of_id = %s
        ORDER BY bl.created_at DESC
    """, (of_id,)))
    
    # ── ACTIVITY LOG (Audit Trail) ────────────────────────
    activity = serialize(q(db, """
        SELECT al.* FROM activity_log_v2 al
        WHERE (al.entity_type = 'OF' AND al.entity_id = %s)
           OR (al.entity_type IN ('DA','BC','BR','FA','CQ','NC','BL')
               AND al.entity_id IN (
                   SELECT id FROM demandes_achat WHERE of_id = %s
                   UNION
                   SELECT DISTINCT cq.id FROM controles_qualite cq WHERE cq.of_id = %s
                   UNION
                   SELECT DISTINCT nc.id FROM non_conformites nc WHERE nc.of_id = %s
                   UNION
                   SELECT DISTINCT bl.id FROM bons_livraison bl WHERE bl.of_id = %s
               ))
        ORDER BY al.created_at DESC
        LIMIT 200
    """, (of_id, of_id, of_id, of_id, of_id)))
    
    # ── DOCUMENT SUMMARY ──────────────────────────────────
    summary = {
        "of_numero": of["numero"],
        "of_statut": of["statut"],
        "produit_nom": of["produit_nom"],
        "quantite": of["quantite"],
        "client_nom": of.get("client_nom", "—"),
        "total_da": len(das),
        "total_bc": len(bcs),
        "total_br": len(brs),
        "total_fa": len(fas),
        "total_qc": len(qc),
        "total_nc": len(nc),
        "total_bl": len(bls),
        "generated_at": datetime.now().isoformat(),
    }
    
    return {
        "summary": summary,
        "of": of,
        "operations": operations,
        "bom": bom,
        "das": das,
        "bcs": bcs,
        "brs": brs,
        "fas": fas,
        "qc": qc,
        "nc": nc,
        "bls": bls,
        "activity_log": activity,
    }
