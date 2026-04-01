-- ============================================================
-- SOFEM MES v7.0 — Frozen Pricing & Cost Calculation
-- Historical price snapshots for immutable invoices
-- Run AFTER all previous schema versions
-- SMARTMOVE · Mahmoud Njeh
-- ============================================================

USE sofem_mes;

-- ── PRODUITS: Add price column (required for price snapshots) ────
ALTER TABLE produits ADD COLUMN IF NOT EXISTS prix_vente_ht DECIMAL(10,3) DEFAULT 0 COMMENT 'Selling price ex-tax';

-- ── PRICE HISTORY (Audit trail of all price changes) ─────
CREATE TABLE IF NOT EXISTS prix_historique (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    entity_type     ENUM('MATERIAU','PRODUIT') NOT NULL,
    entity_id       INT NOT NULL,
    prix_ancien     DECIMAL(10,3) NOT NULL,
    prix_nouveau    DECIMAL(10,3) NOT NULL,
    date_changement DATE NOT NULL,
    change_reason   VARCHAR(500),
    changed_by      INT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_entity (entity_type, entity_id),
    INDEX idx_date (date_changement),
    FOREIGN KEY (changed_by)   REFERENCES users(id) ON DELETE SET NULL
);

-- ── BR_LIGNES: Add frozen price snapshot ───────────────
-- Stores actual price paid at reception (may differ from BC)
-- ALREADY APPLIED - Column exists, skipping
-- ALTER TABLE br_lignes ADD COLUMN prix_unitaire_snapshot DECIMAL(10,3) COMMENT 'Frozen price at reception time';

-- ── FACTURES_ACHAT: Add cost fields ────────────────────
-- Track total costs and variance for invoice freeze
-- ALREADY APPLIED - Columns exist, skipping
-- ALTER TABLE factures_achat ADD COLUMN montant_ht DECIMAL(10,2) DEFAULT 0 COMMENT 'Total ex-tax (HT)';
-- ALTER TABLE factures_achat ADD COLUMN tva DECIMAL(10,2) DEFAULT 0 COMMENT 'VAT amount';
-- ALTER TABLE factures_achat ADD COLUMN montant_ttc DECIMAL(10,2) DEFAULT 0 COMMENT 'Total inc-tax (TTC)';
-- ALTER TABLE factures_achat ADD COLUMN cost_locked_at TIMESTAMP NULL COMMENT 'When prices were frozen';
-- ALTER TABLE factures_achat ADD COLUMN cost_locked_by INT NULL;
-- ALTER TABLE factures_achat ADD FOREIGN KEY (cost_locked_by) REFERENCES users(id) ON DELETE SET NULL;

-- ── FA_LIGNES: Immutable invoice lines with frozen prices ─
-- Each line stores the price that was paid at that moment
-- Never changes even if material price updates later
CREATE TABLE IF NOT EXISTS fa_lignes (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    fa_id                   INT NOT NULL,
    bc_ligne_id             INT,
    description             VARCHAR(500),
    quantite                DECIMAL(10,2) NOT NULL,
    unite                   VARCHAR(20),
    prix_unitaire_snapshot  DECIMAL(10,3) NOT NULL COMMENT 'Frozen price at invoice creation',
    montant                 DECIMAL(10,2) NOT NULL COMMENT 'qty × frozen price',
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_fa (fa_id),
    INDEX idx_bc_ligne (bc_ligne_id),
    FOREIGN KEY (fa_id)        REFERENCES factures_achat(id) ON DELETE CASCADE,
    FOREIGN KEY (bc_ligne_id)  REFERENCES bc_lignes(id) ON DELETE SET NULL
);

-- ── OF COST TRACKING ───────────────────────────────────
-- Store estimated vs actual costs for profitability analysis
CREATE TABLE IF NOT EXISTS of_costs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    of_id           INT NOT NULL,
    cost_type       ENUM('MATERIAL','LABOR','OVERHEAD') NOT NULL,
    amount          DECIMAL(10,2) NOT NULL,
    detail          TEXT COMMENT 'e.g., "Operation: Welding, 2.5h × 25/h", "Material waste"',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_of (of_id),
    FOREIGN KEY (of_id) REFERENCES ordres_fabrication(id) ON DELETE CASCADE
);

-- ── SNAPSHOT: Immutable backup when OF is TERMINATED ────
-- Captures product, materials, operations, and costs at OF completion
-- ONE snapshot per OF (PRIMARY KEY = order_id)
-- Automatically populated when OF status changes to TERMINATED
CREATE TABLE IF NOT EXISTS of_invoice_snapshot (
    order_id            INT PRIMARY KEY,
    of_numero           VARCHAR(50) NOT NULL,
    snapshot_json       LONGTEXT NOT NULL COMMENT 'Complete snapshot: product + materials + operations + costs',
    total_cost          DECIMAL(10,2) NOT NULL COMMENT 'Sum of all costs (product + materials + operations)',
    created_by          INT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_created_at (created_at),
    FOREIGN KEY (order_id) REFERENCES ordres_fabrication(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

-- ── ORDRES_FABRICATION: Add cost fields ────────────────
-- Store estimated and actual costs when OF is completed
-- REQUIRED - produit_prix_snapshot needed for frozen pricing
ALTER TABLE ordres_fabrication ADD COLUMN IF NOT EXISTS produit_prix_snapshot DECIMAL(10,3) DEFAULT 0 COMMENT 'Product price frozen at OF creation';
-- Other cost fields to be applied later if needed
-- ALTER TABLE ordres_fabrication ADD COLUMN cost_estimated_materials DECIMAL(10,2) DEFAULT 0;
-- ALTER TABLE ordres_fabrication ADD COLUMN cost_estimated_labor DECIMAL(10,2) DEFAULT 0;
-- ALTER TABLE ordres_fabrication ADD COLUMN cost_estimated_overhead DECIMAL(10,2) DEFAULT 0;
-- ALTER TABLE ordres_fabrication ADD COLUMN cost_estimated_total DECIMAL(10,2) DEFAULT 0;
-- ALTER TABLE ordres_fabrication ADD COLUMN cost_actual_total DECIMAL(10,2) DEFAULT 0 COMMENT 'Frozen when OF completes';
-- ALTER TABLE ordres_fabrication ADD COLUMN cost_variance DECIMAL(10,2) DEFAULT 0 COMMENT 'actual - estimated';
-- ALTER TABLE ordres_fabrication ADD COLUMN cost_locked_at TIMESTAMP NULL COMMENT 'When cost was frozen';
-- ALTER TABLE ordres_fabrication ADD COLUMN cost_locked_by INT NULL;
-- ALTER TABLE ordres_fabrication ADD FOREIGN KEY (cost_locked_by) REFERENCES users(id) ON DELETE SET NULL;

-- ── INDEXES for performance ──────────────────────────────
CREATE INDEX idx_fa_lignes_fa ON fa_lignes(fa_id);
CREATE INDEX idx_of_costs_of ON of_costs(of_id);
CREATE INDEX idx_prix_hist_entity ON prix_historique(entity_type, entity_id);
