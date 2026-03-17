-- ============================================================
-- SOFEM MES v6.0 — SAFE Migration Script
-- Run this — ignores duplicate columns automatically
-- ============================================================

USE railway;

SET FOREIGN_KEY_CHECKS = 0;

-- ── DROP OLD TABLES ───────────────────────────────────────
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

-- ── OPERATOR RATES (safe - ignore if exists) ──────────────
SET @dbname = DATABASE();
SET @tablename = 'operateurs';

-- taux_horaire
SET @col = 'taux_horaire';
SET @sql = IF(
    NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=@dbname AND TABLE_NAME=@tablename AND COLUMN_NAME=@col),
    CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @col, ' DECIMAL(10,3) DEFAULT 0'),
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- taux_piece
SET @col = 'taux_piece';
SET @sql = IF(
    NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=@dbname AND TABLE_NAME=@tablename AND COLUMN_NAME=@col),
    CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @col, ' DECIMAL(10,3) DEFAULT 0'),
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- type_taux
SET @col = 'type_taux';
SET @sql = IF(
    NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=@dbname AND TABLE_NAME=@tablename AND COLUMN_NAME=@col),
    CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @col, ' ENUM(''HORAIRE'',''PIECE'',''BOTH'') DEFAULT ''HORAIRE'''),
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── OF NEW COLUMNS (safe) ─────────────────────────────────
SET @tablename = 'ordres_fabrication';

SET @col = 'client_id';
SET @sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@dbname AND TABLE_NAME=@tablename AND COLUMN_NAME=@col),CONCAT('ALTER TABLE ',@tablename,' ADD COLUMN ',@col,' INT NULL'),'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col = 'plan_numero';
SET @sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@dbname AND TABLE_NAME=@tablename AND COLUMN_NAME=@col),CONCAT('ALTER TABLE ',@tablename,' ADD COLUMN ',@col,' VARCHAR(100) NULL'),'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col = 'chef_projet_id';
SET @sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@dbname AND TABLE_NAME=@tablename AND COLUMN_NAME=@col),CONCAT('ALTER TABLE ',@tablename,' ADD COLUMN ',@col,' INT NULL'),'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col = 'sous_traitant';
SET @sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@dbname AND TABLE_NAME=@tablename AND COLUMN_NAME=@col),CONCAT('ALTER TABLE ',@tablename,' ADD COLUMN ',@col,' VARCHAR(200) NULL'),'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col = 'sous_traitant_op';
SET @sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@dbname AND TABLE_NAME=@tablename AND COLUMN_NAME=@col),CONCAT('ALTER TABLE ',@tablename,' ADD COLUMN ',@col,' VARCHAR(200) NULL'),'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col = 'sous_traitant_cout';
SET @sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@dbname AND TABLE_NAME=@tablename AND COLUMN_NAME=@col),CONCAT('ALTER TABLE ',@tablename,' ADD COLUMN ',@col,' DECIMAL(10,3) DEFAULT 0'),'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── FOREIGN KEYS (safe - ignore if exists) ────────────────
SET FOREIGN_KEY_CHECKS = 0;

ALTER TABLE ordres_fabrication
  DROP FOREIGN KEY IF EXISTS fk_of_client,
  DROP FOREIGN KEY IF EXISTS fk_of_chef;

ALTER TABLE ordres_fabrication
  ADD CONSTRAINT fk_of_client FOREIGN KEY (client_id)      REFERENCES clients(id)    ON DELETE SET NULL,
  ADD CONSTRAINT fk_of_chef   FOREIGN KEY (chef_projet_id) REFERENCES operateurs(id) ON DELETE SET NULL;

SET FOREIGN_KEY_CHECKS = 1;

-- ── DA NEW COLUMNS (safe) ─────────────────────────────────
SET @tablename = 'demandes_achat';

SET @col = 'of_id';
SET @sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@dbname AND TABLE_NAME=@tablename AND COLUMN_NAME=@col),CONCAT('ALTER TABLE ',@tablename,' ADD COLUMN ',@col,' INT NULL'),'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col = 'objet';
SET @sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@dbname AND TABLE_NAME=@tablename AND COLUMN_NAME=@col),CONCAT('ALTER TABLE ',@tablename,' ADD COLUMN ',@col,' TEXT NULL'),'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET FOREIGN_KEY_CHECKS = 0;
ALTER TABLE demandes_achat DROP FOREIGN KEY IF EXISTS fk_da_of;
ALTER TABLE demandes_achat ADD CONSTRAINT fk_da_of FOREIGN KEY (of_id) REFERENCES ordres_fabrication(id) ON DELETE SET NULL;
SET FOREIGN_KEY_CHECKS = 1;

-- ── BL NEW COLUMNS (safe) ─────────────────────────────────
SET @tablename = 'bons_livraison';

SET @col = 'date_livraison_reelle';
SET @sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@dbname AND TABLE_NAME=@tablename AND COLUMN_NAME=@col),CONCAT('ALTER TABLE ',@tablename,' ADD COLUMN ',@col,' DATE NULL'),'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col = 'destinataire_final';
SET @sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@dbname AND TABLE_NAME=@tablename AND COLUMN_NAME=@col),CONCAT('ALTER TABLE ',@tablename,' ADD COLUMN ',@col,' VARCHAR(200) NULL'),'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col = 'adresse_finale';
SET @sql = IF(NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@dbname AND TABLE_NAME=@tablename AND COLUMN_NAME=@col),CONCAT('ALTER TABLE ',@tablename,' ADD COLUMN ',@col,' VARCHAR(300) NULL'),'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── NEW TABLES ────────────────────────────────────────────
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
    FOREIGN KEY (machine_id) REFERENCES machines(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS op_operateurs (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    operation_id INT NOT NULL,
    operateur_id INT NOT NULL,
    FOREIGN KEY (operation_id) REFERENCES of_operations(id) ON DELETE CASCADE,
    FOREIGN KEY (operateur_id) REFERENCES operateurs(id) ON DELETE CASCADE,
    UNIQUE KEY uq_op_oper (operation_id, operateur_id)
);

CREATE TABLE IF NOT EXISTS of_bom (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    of_id            INT NOT NULL,
    materiau_id      INT NOT NULL,
    quantite_requise DECIMAL(10,3) NOT NULL,
    FOREIGN KEY (of_id)       REFERENCES ordres_fabrication(id) ON DELETE CASCADE,
    FOREIGN KEY (materiau_id) REFERENCES materiaux(id),
    UNIQUE KEY uq_of_mat (of_id, materiau_id)
);

SELECT 'Schema v6.0 SAFE migration complete!' AS STATUS;
