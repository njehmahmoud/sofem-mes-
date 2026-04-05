-- ============================================================
-- SOFEM MES v7 → v8 Combined Deployment Script
-- Frozen Pricing + Complete Invoice Snapshots
-- SMARTMOVE · Mahmoud Njeh · April 1, 2026
-- 
-- Run this script top-to-bottom in MySQL Workbench
-- Estimated time: < 5 seconds
-- ============================================================

USE sofem_mes;

-- ============================================================
-- PART 1: SCHEMA V7 — Frozen Pricing Infrastructure
-- ============================================================
-- Purpose: Add price history tracking and frozen price snapshots
-- Status: Safe to run - all operations are idempotent

-- ──────────────────────────────────────────────────────────
-- Step 1: Add selling price column to products (if not exists)
-- ──────────────────────────────────────────────────────────
ALTER TABLE produits ADD COLUMN IF NOT EXISTS prix_vente_ht DECIMAL(10,3) DEFAULT 0 COMMENT 'Selling price ex-tax';

-- ──────────────────────────────────────────────────────────
-- Step 2: Create price history audit trail (SCHEMA V7)
-- ──────────────────────────────────────────────────────────
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
    FOREIGN KEY (changed_by) REFERENCES users(id) ON DELETE SET NULL
);

-- ──────────────────────────────────────────────────────────
-- Step 3: Create immutable invoice lines table (SCHEMA V7)
-- ──────────────────────────────────────────────────────────
-- Each line stores the frozen price paid at invoice creation time
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
    FOREIGN KEY (fa_id) REFERENCES factures_achat(id) ON DELETE CASCADE,
    FOREIGN KEY (bc_ligne_id) REFERENCES bc_lignes(id) ON DELETE SET NULL
);

-- ──────────────────────────────────────────────────────────
-- Step 4: Create OF cost tracking table (SCHEMA V7)
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS of_costs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    of_id           INT NOT NULL,
    cost_type       ENUM('MATERIAL','LABOR','OVERHEAD') NOT NULL,
    amount          DECIMAL(10,2) NOT NULL,
    detail          TEXT COMMENT 'e.g., "Operation: Welding, 2.5h × 25/h"',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_of (of_id),
    FOREIGN KEY (of_id) REFERENCES ordres_fabrication(id) ON DELETE CASCADE
);

-- ──────────────────────────────────────────────────────────
-- Step 5: Add price snapshot to ordres_fabrication (SCHEMA V7)
-- ──────────────────────────────────────────────────────────
ALTER TABLE ordres_fabrication ADD COLUMN IF NOT EXISTS produit_prix_snapshot DECIMAL(10,3) DEFAULT 0 COMMENT 'Product price frozen at OF creation';

-- ============================================================
-- PART 2: SCHEMA V8 — Complete Invoice Snapshot System
-- ============================================================
-- Purpose: Capture ALL revenue and cost data needed for invoicing
-- Status: Extends v7 - complete immutable record per OF

-- ──────────────────────────────────────────────────────────
-- Step 6: Create OF invoice snapshot table (SCHEMA V8)
-- ──────────────────────────────────────────────────────────
-- This is the single source of truth for all invoice data
-- Populated at OF creation with estimated costs
-- Updated at OF completion with actual costs
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

-- ──────────────────────────────────────────────────────────
-- Step 7: Link factures to OF snapshots (SCHEMA V8)
-- ──────────────────────────────────────────────────────────
-- Enable sales invoices to reference OF instead of BC
-- Values: of_id=123 (sales), bc_id=456 (purchase), or both
ALTER TABLE factures_achat ADD COLUMN IF NOT EXISTS of_id INT NULL;

-- Add foreign key constraint (ignore if already exists)
-- Note: If constraint already exists, this will be skipped by error 1064
ALTER TABLE factures_achat ADD CONSTRAINT fk_fa_of FOREIGN KEY (of_id) REFERENCES ordres_fabrication(id) ON DELETE SET NULL;

-- ──────────────────────────────────────────────────────────
-- Step 8: Create indexes for performance (SCHEMA V8)
-- ──────────────────────────────────────────────────────────
DROP INDEX IF EXISTS idx_of_invoice_of ON of_invoice_snapshot;
DROP INDEX IF EXISTS idx_fa_of ON factures_achat;

CREATE INDEX idx_of_invoice_of ON of_invoice_snapshot(of_id);
CREATE INDEX idx_fa_of ON factures_achat(of_id);

-- ============================================================
-- DEPLOYMENT VERIFICATION
-- ============================================================
-- Run these queries to verify successful deployment

-- Verify v7 tables created
-- SELECT 'V7 Tables' as deployment_check;
-- SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
-- WHERE TABLE_SCHEMA='sofem_mes' AND TABLE_NAME IN (
--   'prix_historique', 'fa_lignes', 'of_costs'
-- );

-- Verify v8 tables created
-- SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
-- WHERE TABLE_SCHEMA='sofem_mes' AND TABLE_NAME='of_invoice_snapshot';

-- Verify columns added
-- SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
-- WHERE TABLE_SCHEMA='sofem_mes' AND TABLE_NAME='factures_achat' 
-- AND COLUMN_NAME='of_id';

-- ============================================================
-- DEPLOYMENT COMPLETE
-- ============================================================
-- ✅ Schema v7: Frozen pricing infrastructure applied
-- ✅ Schema v8: Complete snapshot system applied
-- ✅ Database ready for immutable invoice workflow
-- ✅ Backend code already updated (of.py, operations.py, fa.py)
-- 
-- Next steps:
-- 1. Restart backend: python backend/main.py
-- 2. Create new OF - snapshot auto-captured
-- 3. Complete OF - costs auto-finalized
-- 4. Create sales invoice with of_id - frozen data locked
-- ============================================================
