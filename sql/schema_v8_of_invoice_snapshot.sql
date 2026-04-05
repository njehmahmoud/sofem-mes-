-- ============================================================
-- SOFEM MES v8.0 — OF Invoice Snapshot (Immutable Invoice Data)
-- Stores all data needed for invoicing at OF creation/completion time
-- Run AFTER schema_v7_frozen_pricing.sql
-- SMARTMOVE · Mahmoud Njeh
-- ============================================================

USE sofem_mes;

-- ── OF_INVOICE_SNAPSHOT: Immutable invoice data for each OF ────────
-- Populated at OF creation, updated at completion
-- All factures/invoices reference this, never recalculated
CREATE TABLE IF NOT EXISTS of_invoice_snapshot (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    of_id                   INT NOT NULL UNIQUE,
    
    -- Product data (frozen at OF creation)
    produit_id              INT NOT NULL,
    produit_nom             VARCHAR(200),
    produit_code            VARCHAR(50),
    produit_prix_unitaire   DECIMAL(10,3) NOT NULL COMMENT 'Product price at OF creation',
    
    -- Quantity
    quantite_of             DECIMAL(10,2) NOT NULL,
    
    -- REVENUE (frozen at OF creation)
    montant_vente_ht        DECIMAL(10,2) COMMENT 'qty × product price',
    
    -- MATERIALS COST (estimated at creation, actual at completion)
    cost_materiel_estime    DECIMAL(10,2) DEFAULT 0 COMMENT 'Material cost at OF creation',
    cost_materiel_reel      DECIMAL(10,2) DEFAULT 0 COMMENT 'Actual material cost at OF completion',
    
    -- LABOR COST (estimated at creation, actual at completion)
    cost_main_oeuvre_estime DECIMAL(10,2) DEFAULT 0 COMMENT 'Labor cost at OF creation',
    cost_main_oeuvre_reel   DECIMAL(10,2) DEFAULT 0 COMMENT 'Actual labor cost at OF completion',
    
    -- SUBCONTRACTING (frozen at OF creation)
    cost_sous_traitance     DECIMAL(10,2) DEFAULT 0 COMMENT 'Subcontracting cost',
    
    -- OVERHEAD (future)
    cost_overhead           DECIMAL(10,2) DEFAULT 0,
    
    -- TOTAL COSTS & MARGIN
    cost_total_estime       DECIMAL(10,2) DEFAULT 0 COMMENT 'Estimated total at creation',
    cost_total_reel         DECIMAL(10,2) DEFAULT 0 COMMENT 'Actual total at completion',
    marge_brute_estime      DECIMAL(10,2) COMMENT 'montant_vente_ht - cost_total_estime',
    marge_brute_reel        DECIMAL(10,2) COMMENT 'montant_vente_ht - cost_total_reel',
    marge_pourcentage       DECIMAL(5,2) COMMENT 'Estimated margin %',
    marge_pourcentage_reel  DECIMAL(5,2) COMMENT 'Actual margin %',
    
    -- TIMESTAMPS
    snapshot_at_creation    TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'When OF was created',
    snapshot_at_completion  TIMESTAMP NULL COMMENT 'When OF was completed (costs finalized)',
    
    created_by              INT,
    updated_by              INT,
    
    FOREIGN KEY (of_id) REFERENCES ordres_fabrication(id) ON DELETE CASCADE,
    FOREIGN KEY (produit_id) REFERENCES produits(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_of (of_id),
    INDEX idx_created (snapshot_at_creation)
);

-- ── FA_REFERENCE_OF: Link factures to OF snapshots for immutability ────
-- Instead of recalculating from OF, factures reference this snapshot
ALTER TABLE factures_achat ADD COLUMN IF NOT EXISTS of_id INT NULL;

-- Add foreign key constraint (ignore if already exists)
ALTER TABLE factures_achat ADD CONSTRAINT fk_fa_of FOREIGN KEY (of_id) REFERENCES ordres_fabrication(id) ON DELETE SET NULL;

-- ── INDEXES ──────────────────────────────────────────────
DROP INDEX IF EXISTS idx_of_invoice_of ON of_invoice_snapshot;
DROP INDEX IF EXISTS idx_fa_of ON factures_achat;

CREATE INDEX idx_of_invoice_of ON of_invoice_snapshot(of_id);
CREATE INDEX idx_fa_of ON factures_achat(of_id);
