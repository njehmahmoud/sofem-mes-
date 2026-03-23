"""SOFEM MES v6.0 — Analytics Routes (patched)
Fix: correlated subquery in production cost (O(n×m)) replaced with a
     derived-table LEFT JOIN — one scan instead of one per product row.
"""

import logging
from fastapi import APIRouter, Depends
from database import get_db, q, serialize
from auth import require_any_role

logger = logging.getLogger("sofem-analytics")

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/production", dependencies=[Depends(require_any_role)])
def analytics_production(db=Depends(get_db)):
    # OF par mois (12 derniers mois)
    par_mois = q(db, """
        SELECT DATE_FORMAT(created_at,'%Y-%m') mois,
               DATE_FORMAT(MIN(created_at),'%b %Y') mois_label,
               COUNT(*) total,
               SUM(statut='COMPLETED') completes,
               SUM(statut='CANCELLED') annules,
               SUM(priorite='URGENT') urgents
        FROM ordres_fabrication
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
        GROUP BY DATE_FORMAT(created_at,'%Y-%m')
        ORDER BY mois
    """)

    # Statuts actuels
    statuts = q(db, """
        SELECT statut, COUNT(*) n FROM ordres_fabrication
        GROUP BY statut
    """)

    # OFs en retard
    retards = q(db, """
        SELECT o.id, o.numero, o.date_echeance, o.statut, o.priorite,
               p.nom produit_nom, c.nom client_nom,
               DATEDIFF(CURDATE(), o.date_echeance) jours_retard
        FROM ordres_fabrication o
        JOIN produits p ON p.id = o.produit_id
        LEFT JOIN clients c ON c.id = o.client_id
        WHERE o.date_echeance < CURDATE()
          AND o.statut NOT IN ('COMPLETED','CANCELLED')
        ORDER BY jours_retard DESC
        LIMIT 10
    """)

    # ── Coût matières moyen par produit — FIXED: derived-table JOIN (was correlated subquery) ──
    # Old O(n×m): AVG( (SELECT SUM(...) WHERE of_id = o.id) ) — runs one subquery per OF row.
    # New O(n+m): pre-aggregate all of_bom costs once, then JOIN — single pass.
    try:
        couts = q(db, """
            SELECT p.nom produit_nom,
                   COUNT(o.id) nb_ofs,
                   ROUND(AVG(COALESCE(mat_cost.cout, 0)), 2) cout_mat_moyen
            FROM ordres_fabrication o
            JOIN produits p ON p.id = o.produit_id
            LEFT JOIN (
                SELECT ob.of_id,
                       SUM(ob.quantite_requise * m.prix_unitaire) AS cout
                FROM of_bom ob
                JOIN materiaux m ON m.id = ob.materiau_id
                GROUP BY ob.of_id
            ) mat_cost ON mat_cost.of_id = o.id
            WHERE o.statut = 'COMPLETED'
            GROUP BY p.id
            ORDER BY nb_ofs DESC
            LIMIT 5
        """)
    except Exception as e:
        logger.warning(f"Product cost analytics failed: {e}")
        couts = []

    # OF actifs par atelier
    ateliers = q(db, """
        SELECT atelier, COUNT(*) n, SUM(statut='IN_PROGRESS') en_cours
        FROM ordres_fabrication
        WHERE statut NOT IN ('COMPLETED','CANCELLED')
        GROUP BY atelier ORDER BY n DESC
    """)

    return serialize({
        "par_mois":       par_mois,
        "statuts":        statuts,
        "retards":        retards,
        "couts_produits": couts,
        "ateliers":       ateliers,
    })


@router.get("/achats", dependencies=[Depends(require_any_role)])
def analytics_achats(db=Depends(get_db)):
    stock = q(db, """
        SELECT nom, code, unite,
               stock_actuel, stock_minimum,
               ROUND(CASE WHEN stock_minimum>0
                     THEN stock_actuel/stock_minimum*100 ELSE 100 END, 0) pct,
               prix_unitaire,
               ROUND(stock_actuel * prix_unitaire, 2) valeur_stock
        FROM materiaux
        ORDER BY
          CASE WHEN stock_minimum > 0
               THEN stock_actuel/stock_minimum ELSE 99 END ASC
    """)

    val_totale = q(db, """
        SELECT ROUND(SUM(stock_actuel * prix_unitaire), 2) total
        FROM materiaux
    """, one=True)

    da_statuts = q(db, """
        SELECT statut, COUNT(*) n FROM demandes_achat GROUP BY statut
    """)

    mouvements = q(db, """
        SELECT ms.type, ms.quantite, ms.stock_avant, ms.stock_apres,
               ms.motif, ms.created_at,
               m.nom materiau_nom, m.unite,
               o.numero of_numero
        FROM mouvements_stock ms
        JOIN materiaux m ON m.id = ms.materiau_id
        LEFT JOIN ordres_fabrication o ON o.id = ms.of_id
        ORDER BY ms.created_at DESC LIMIT 15
    """)

    fournisseurs = q(db, """
        SELECT bc.fournisseur,
               COUNT(*) nb_bc,
               SUM(bcl.quantite * bcl.prix_unitaire) montant_total
        FROM bons_commande bc
        JOIN bc_lignes bcl ON bcl.bc_id = bc.id
        GROUP BY bc.fournisseur
        ORDER BY montant_total DESC LIMIT 5
    """)

    try:
        brs_attente = q(db, """
            SELECT br.br_numero, br.created_at,
                   bc.bc_numero, bc.fournisseur,
                   da.da_numero
            FROM bons_reception br
            JOIN bons_commande bc ON bc.id = br.bc_id
            LEFT JOIN demandes_achat da ON da.id = bc.da_id
            WHERE br.statut = 'EN_ATTENTE'
            ORDER BY br.created_at DESC
        """)
    except Exception as e:
        logger.warning(f"BRs en attente query failed: {e}")
        brs_attente = []

    return serialize({
        "stock":                stock,
        "valeur_totale_stock":  val_totale["total"] if val_totale else 0,
        "da_statuts":           da_statuts,
        "mouvements":           mouvements,
        "top_fournisseurs":     fournisseurs,
        "brs_attente":          brs_attente,
    })


@router.get("/operateurs", dependencies=[Depends(require_any_role)])
def analytics_operateurs(db=Depends(get_db)):
    try:
        perf = q(db, """
            SELECT o.id, o.nom, o.prenom, o.specialite,
                   COALESCE(o.role,'OPERATEUR') role,
                   o.taux_horaire, o.taux_piece, o.type_taux,
                   COUNT(DISTINCT oo.operation_id) total_ops,
                   SUM(op.statut='COMPLETED') ops_terminees,
                   SUM(op.duree_reelle) duree_totale_min,
                   COUNT(DISTINCT of2.id) ofs_impliques
            FROM operateurs o
            LEFT JOIN op_operateurs oo ON oo.operateur_id = o.id
            LEFT JOIN of_operations op ON op.id = oo.operation_id
            LEFT JOIN ordres_fabrication of2 ON of2.id = op.of_id
            WHERE o.actif = TRUE
            GROUP BY o.id ORDER BY ops_terminees DESC
        """)
    except Exception as e:
        logger.warning(f"Operator performance query failed: {e}")
        perf = q(db, """
            SELECT o.id, o.nom, o.prenom, o.specialite,
                   'OPERATEUR' role,
                   o.taux_horaire, o.taux_piece, o.type_taux,
                   0 total_ops, 0 ops_terminees,
                   0 duree_totale_min, 0 ofs_impliques
            FROM operateurs o WHERE o.actif = TRUE ORDER BY o.nom
        """)

    specialites = q(db, """
        SELECT specialite, COUNT(*) n FROM operateurs
        WHERE actif = TRUE GROUP BY specialite ORDER BY n DESC
    """)

    try:
        cout_ops = q(db, """
            SELECT op.operation_nom,
                   COUNT(*) nb,
                   ROUND(AVG(op.duree_reelle), 0) duree_moy_min,
                   ROUND(SUM(
                     CASE o2.type_taux
                       WHEN 'HORAIRE' THEN (op.duree_reelle/60) * o2.taux_horaire
                       WHEN 'PIECE'   THEN o2.taux_piece
                       ELSE (op.duree_reelle/60)*o2.taux_horaire + o2.taux_piece
                     END
                   ), 2) cout_total
            FROM of_operations op
            JOIN op_operateurs oo ON oo.operation_id = op.id
            JOIN operateurs o2 ON o2.id = oo.operateur_id
            WHERE op.statut = 'COMPLETED' AND op.duree_reelle > 0
            GROUP BY op.operation_nom ORDER BY cout_total DESC LIMIT 8
        """)
    except Exception as e:
        logger.warning(f"Operation cost analytics failed: {e}")
        cout_ops = []

    return serialize({
        "performance":         perf,
        "specialites":         specialites,
        "cout_par_operation":  cout_ops,
    })


@router.get("/qualite", dependencies=[Depends(require_any_role)])
def analytics_qualite(db=Depends(get_db)):
    try:
        par_mois = q(db, """
            SELECT DATE_FORMAT(date_controle,'%Y-%m') mois,
                   DATE_FORMAT(MIN(date_controle),'%b %Y') mois_label,
                   COUNT(*) total,
                   SUM(statut='CONFORME') conformes,
                   SUM(quantite_rebut) total_rebut,
                   SUM(quantite_controlee) total_controlees,
                   ROUND(SUM(statut='CONFORME')/COUNT(*)*100, 1) taux
            FROM controles_qualite
            WHERE date_controle >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
            GROUP BY DATE_FORMAT(date_controle,'%Y-%m')
            ORDER BY mois
        """)

        nc_stats = q(db, """
            SELECT gravite, statut, COUNT(*) n
            FROM non_conformites GROUP BY gravite, statut
        """)

        nc_ouvertes = q(db, """
            SELECT nc.*, of2.numero of_numero, p.nom produit_nom,
                   o.nom resp_nom, o.prenom resp_prenom,
                   DATEDIFF(CURDATE(), nc.created_at) age_jours
            FROM non_conformites nc
            LEFT JOIN ordres_fabrication of2 ON of2.id = nc.of_id
            LEFT JOIN produits p ON p.id = of2.produit_id
            LEFT JOIN operateurs o ON o.id = nc.responsable_id
            WHERE nc.statut = 'OUVERTE'
            ORDER BY
              CASE nc.gravite WHEN 'CRITIQUE' THEN 1
                WHEN 'MAJEURE' THEN 2 ELSE 3 END,
              nc.created_at
        """)

        defauts = q(db, """
            SELECT type_defaut, COUNT(*) n
            FROM non_conformites GROUP BY type_defaut ORDER BY n DESC LIMIT 8
        """)

        kpis = q(db, """
            SELECT
              COUNT(*) total_cq,
              SUM(statut='CONFORME') conformes,
              ROUND(SUM(statut='CONFORME')/NULLIF(COUNT(*),0)*100, 1) taux_global,
              SUM(quantite_rebut) total_rebut,
              SUM(quantite_controlee) total_controlees
            FROM controles_qualite
        """, one=True)

        nc_kpis = q(db, """
            SELECT
              COUNT(*) total_nc,
              SUM(statut='OUVERTE') ouvertes,
              SUM(gravite='CRITIQUE' AND statut!='CLOTUREE') critiques
            FROM non_conformites
        """, one=True)

    except Exception as e:
        logger.warning(f"Quality analytics failed: {e}")
        return {"error": str(e), "par_mois": [], "nc_stats": [],
                "nc_ouvertes": [], "defauts": [], "kpis": {}, "nc_kpis": {}}

    return serialize({
        "par_mois":   par_mois,
        "nc_stats":   nc_stats,
        "nc_ouvertes": nc_ouvertes,
        "defauts":    defauts,
        "kpis":       kpis,
        "nc_kpis":    nc_kpis,
    })
