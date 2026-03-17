-- ============================================================
-- SOFEM MES v6.0 — Schema
-- Compatible with MySQL 5.7+
-- Run after schema_v3_additions.sql + schema_v4_additions.sql
-- SMARTMOVE · Mahmoud Njeh
-- ============================================================

USE railway;

SET FOREIGN_KEY_CHECKS = 0;

-- ── DROP OLD TABLES (children first) ──────────────────────
DROP TABLE IF EXISTS etape_operateurs;
DROP TABLE IF EXISTS op_operateurs;
DROP TABLE IF EXISTS of_operateurs;
DROP TABLE IF EXISTS of_bom;
DROP TABLE IF EXISTS etapes_production;

SET FOREIGN_KEY_CHECKS = 1;

-- ── CLIENTS ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clients (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    code             VARCHAR(30) UNIQUE NOT NULL,
    nom              VARCHAR(200) NOT NULL,
    matricule_fiscal VARCHAR(50),
    adresse          TEXT,
    ville            VARCHAR(100),
    telephone        VARCHAR(50),
    email            VARCHAR(200),
    notes            TEXT,
    actif            BOOLEAN DEFAULT TRUE,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ── OPERATOR RATES (safe for MySQL 5.7 — ignore duplicate errors) ──
ALTER TABLE operateurs ADD COLUMN taux_horaire DECIMAL(10,3) DEFAULT 0;
ALTER TABLE operateurs ADD COLUMN taux_piece   DECIMAL(10,3) DEFAULT 0;
ALTER TABLE operateurs ADD COLUMN type_taux    ENUM('HORAIRE','PIECE','BOTH') DEFAULT 'HORAIRE';

-- ── OF: new columns ───────────────────────────────────────
ALTER TABLE ordres_fabrication ADD COLUMN client_id          INT NULL;
ALTER TABLE ordres_fabrication ADD COLUMN plan_numero        VARCHAR(100) NULL;
ALTER TABLE ordres_fabrication ADD COLUMN chef_projet_id     INT NULL;
ALTER TABLE ordres_fabrication ADD COLUMN sous_traitant      VARCHAR(200) NULL;
ALTER TABLE ordres_fabrication ADD COLUMN sous_traitant_op   VARCHAR(200) NULL;
ALTER TABLE ordres_fabrication ADD COLUMN sous_traitant_cout DECIMAL(10,3) DEFAULT 0;

-- Foreign keys for OF (ignore if already exist)
ALTER TABLE ordres_fabrication
  ADD CONSTRAINT fk_of_client FOREIGN KEY (client_id)      REFERENCES clients(id)    ON DELETE SET NULL;
ALTER TABLE ordres_fabrication
  ADD CONSTRAINT fk_of_chef   FOREIGN KEY (chef_projet_id) REFERENCES operateurs(id) ON DELETE SET NULL;

-- ── DYNAMIC OPERATIONS ────────────────────────────────────
CREATE TABLE IF NOT EXISTS of_operations (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    of_id         INT NOT NULL,
    ordre         INT DEFAULT 1,
    operation_nom VARCHAR(100) NOT NULL,
    machine_id    INT NULL,
    statut        ENUM('PENDING','IN_PROGRESS','COMPLETED') DEFAULT 'PENDING',
    debut         DATETIME NULL,
    fin           DATETIME NULL,
    duree_reelle  INT NULL,
    notes         TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (of_id)      REFERENCES ordres_fabrication(id) ON DELETE CASCADE,
    FOREIGN KEY (machine_id) REFERENCES machines(id)           ON DELETE SET NULL
);

-- ── OPERATORS PER OPERATION ───────────────────────────────
CREATE TABLE IF NOT EXISTS op_operateurs (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    operation_id INT NOT NULL,
    operateur_id INT NOT NULL,
    FOREIGN KEY (operation_id) REFERENCES of_operations(id) ON DELETE CASCADE,
    FOREIGN KEY (operateur_id) REFERENCES operateurs(id)    ON DELETE CASCADE,
    UNIQUE KEY uq_op_oper (operation_id, operateur_id)
);

-- ── OF BOM ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS of_bom (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    of_id            INT NOT NULL,
    materiau_id      INT NOT NULL,
    quantite_requise DECIMAL(10,3) NOT NULL,
    FOREIGN KEY (of_id)       REFERENCES ordres_fabrication(id) ON DELETE CASCADE,
    FOREIGN KEY (materiau_id) REFERENCES materiaux(id),
    UNIQUE KEY uq_of_mat (of_id, materiau_id)
);

-- ── DA new columns ────────────────────────────────────────
ALTER TABLE demandes_achat ADD COLUMN of_id INT NULL;
ALTER TABLE demandes_achat ADD COLUMN objet TEXT NULL;
ALTER TABLE demandes_achat
  ADD CONSTRAINT fk_da_of FOREIGN KEY (of_id) REFERENCES ordres_fabrication(id) ON DELETE SET NULL;

-- ── BL delivery columns ───────────────────────────────────
ALTER TABLE bons_livraison ADD COLUMN date_livraison_reelle DATE NULL;
ALTER TABLE bons_livraison ADD COLUMN destinataire_final    VARCHAR(200) NULL;
ALTER TABLE bons_livraison ADD COLUMN adresse_finale        VARCHAR(300) NULL;

SELECT 'Schema v6.0 OK' AS STATUS;
