-- ============================================================
-- SOFEM MES v3.0 — Schema additions
-- Run AFTER existing schema_v2.sql
-- SMARTMOVE · Mahmoud Njeh
-- ============================================================

USE railway;

-- ── BON DE LIVRAISON ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS bons_livraison (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    bl_numero     VARCHAR(30) UNIQUE NOT NULL,
    of_id         INT NOT NULL,
    date_livraison DATE,
    destinataire  VARCHAR(200) DEFAULT 'SOFEM',
    adresse       VARCHAR(300) DEFAULT 'Route Sidi Salem 2.5KM, Sfax',
    statut        ENUM('DRAFT','EMIS','LIVRE') DEFAULT 'DRAFT',
    notes         TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (of_id) REFERENCES ordres_fabrication(id) ON DELETE CASCADE
);

-- ── ETAPES OPERATEURS (multi-operator per stage) ──────────
-- Replace single operateur_id in etapes_production with dedicated table
CREATE TABLE IF NOT EXISTS etape_operateurs (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    etape_id     INT NOT NULL,
    operateur_id INT NOT NULL,
    role         VARCHAR(50) DEFAULT 'PRINCIPAL',
    FOREIGN KEY (etape_id)     REFERENCES etapes_production(id) ON DELETE CASCADE,
    FOREIGN KEY (operateur_id) REFERENCES operateurs(id),
    UNIQUE KEY unique_etape_op (etape_id, operateur_id)
);

-- ── MODULE ACHATS ─────────────────────────────────────────

-- Demande d'achat
CREATE TABLE IF NOT EXISTS demandes_achat (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    da_numero     VARCHAR(30) UNIQUE NOT NULL,
    materiau_id   INT,
    description   VARCHAR(300) NOT NULL,
    quantite      DECIMAL(10,2) NOT NULL,
    unite         VARCHAR(20) DEFAULT 'pcs',
    urgence       ENUM('NORMAL','URGENT') DEFAULT 'NORMAL',
    statut        ENUM('PENDING','APPROVED','REJECTED','ORDERED') DEFAULT 'PENDING',
    demandeur_id  INT,
    valideur_id   INT,
    notes         TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (materiau_id)  REFERENCES materiaux(id),
    FOREIGN KEY (demandeur_id) REFERENCES operateurs(id),
    FOREIGN KEY (valideur_id)  REFERENCES operateurs(id)
);

-- Bon de commande
CREATE TABLE IF NOT EXISTS bons_commande (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    bc_numero     VARCHAR(30) UNIQUE NOT NULL,
    fournisseur   VARCHAR(200) NOT NULL,
    statut        ENUM('DRAFT','ENVOYE','RECU_PARTIEL','RECU','ANNULE') DEFAULT 'DRAFT',
    tva_rate      DECIMAL(5,2) DEFAULT 19.00,
    notes         TEXT,
    da_id         INT,
    created_by    INT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (da_id)      REFERENCES demandes_achat(id),
    FOREIGN KEY (created_by) REFERENCES operateurs(id)
);

-- Lignes du bon de commande
CREATE TABLE IF NOT EXISTS bc_lignes (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    bc_id         INT NOT NULL,
    materiau_id   INT,
    description   VARCHAR(300) NOT NULL,
    quantite      DECIMAL(10,2) NOT NULL,
    unite         VARCHAR(20) DEFAULT 'pcs',
    prix_unitaire DECIMAL(10,3) DEFAULT 0,
    FOREIGN KEY (bc_id)       REFERENCES bons_commande(id) ON DELETE CASCADE,
    FOREIGN KEY (materiau_id) REFERENCES materiaux(id)
);

-- Bon de réception
CREATE TABLE IF NOT EXISTS bons_reception (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    br_numero     VARCHAR(30) UNIQUE NOT NULL,
    bc_id         INT NOT NULL,
    date_reception DATE NOT NULL,
    statut        ENUM('PARTIEL','COMPLET') DEFAULT 'COMPLET',
    notes         TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bc_id) REFERENCES bons_commande(id)
);

-- Lignes du bon de réception
CREATE TABLE IF NOT EXISTS br_lignes (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    br_id         INT NOT NULL,
    bc_ligne_id   INT NOT NULL,
    quantite_recue DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (br_id)       REFERENCES bons_reception(id) ON DELETE CASCADE,
    FOREIGN KEY (bc_ligne_id) REFERENCES bc_lignes(id)
);

-- Facture d'achat
CREATE TABLE IF NOT EXISTS factures_achat (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    fa_numero     VARCHAR(30) UNIQUE NOT NULL,
    bc_id         INT NOT NULL,
    fournisseur   VARCHAR(200) NOT NULL,
    date_facture  DATE NOT NULL,
    montant_ht    DECIMAL(12,3) DEFAULT 0,
    tva           DECIMAL(12,3) DEFAULT 0,
    montant_ttc   DECIMAL(12,3) DEFAULT 0,
    statut        ENUM('PENDING','PAYEE','ANNULEE') DEFAULT 'PENDING',
    notes         TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bc_id) REFERENCES bons_commande(id)
);

SELECT 'Schema v3.0 additions installed!' as STATUS;
