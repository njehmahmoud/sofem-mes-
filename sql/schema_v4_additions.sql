-- ============================================================
-- SOFEM MES v4.0 — Schema additions
-- New modules: Machines, Qualité, Maintenance, Fournisseurs, Planification
-- Run AFTER schema_v3_additions.sql
-- SMARTMOVE · Mahmoud Njeh
-- ============================================================

USE railway;

-- ── MACHINES / ÉQUIPEMENTS ────────────────────────────────
CREATE TABLE IF NOT EXISTS machines (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    code            VARCHAR(30) UNIQUE NOT NULL,
    nom             VARCHAR(200) NOT NULL,
    type            VARCHAR(100),
    marque          VARCHAR(100),
    modele          VARCHAR(100),
    numero_serie    VARCHAR(100),
    atelier         VARCHAR(100) DEFAULT 'Atelier A',
    statut          ENUM('OPERATIONNELLE','EN_MAINTENANCE','EN_PANNE','ARRETEE') DEFAULT 'OPERATIONNELLE',
    date_acquisition DATE,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ── FOURNISSEURS ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fournisseurs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    code            VARCHAR(30) UNIQUE NOT NULL,
    nom             VARCHAR(200) NOT NULL,
    contact         VARCHAR(200),
    telephone       VARCHAR(50),
    email           VARCHAR(200),
    adresse         TEXT,
    ville           VARCHAR(100),
    pays            VARCHAR(100) DEFAULT 'Tunisie',
    matricule_fiscal VARCHAR(50),
    statut          ENUM('ACTIF','INACTIF','BLACKLISTE') DEFAULT 'ACTIF',
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Link materiaux to fournisseurs (replaces fournisseur text field)
CREATE TABLE IF NOT EXISTS materiau_fournisseurs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    materiau_id     INT NOT NULL,
    fournisseur_id  INT NOT NULL,
    prix_unitaire   DECIMAL(10,3) DEFAULT 0,
    delai_jours     INT DEFAULT 7,
    principal       BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (materiau_id)   REFERENCES materiaux(id) ON DELETE CASCADE,
    FOREIGN KEY (fournisseur_id) REFERENCES fournisseurs(id) ON DELETE CASCADE,
    UNIQUE KEY unique_mat_fourn (materiau_id, fournisseur_id)
);

-- ── CONTRÔLE QUALITÉ ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS controles_qualite (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    cq_numero       VARCHAR(30) UNIQUE NOT NULL,
    of_id           INT,
    type_controle   ENUM('RECEPTION','EN_COURS','FINAL') DEFAULT 'FINAL',
    operateur_id    INT,
    date_controle   DATE NOT NULL,
    statut          ENUM('CONFORME','NON_CONFORME','EN_ATTENTE') DEFAULT 'EN_ATTENTE',
    quantite_controlée DECIMAL(10,2) DEFAULT 0,
    quantite_conforme  DECIMAL(10,2) DEFAULT 0,
    quantite_rebut     DECIMAL(10,2) DEFAULT 0,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (of_id)          REFERENCES ordres_fabrication(id) ON DELETE SET NULL,
    FOREIGN KEY (operateur_id)   REFERENCES operateurs(id) ON DELETE SET NULL
);

-- Non-conformités
CREATE TABLE IF NOT EXISTS non_conformites (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    nc_numero       VARCHAR(30) UNIQUE NOT NULL,
    cq_id           INT,
    of_id           INT,
    type_defaut     VARCHAR(200) NOT NULL,
    description     TEXT,
    gravite         ENUM('MINEURE','MAJEURE','CRITIQUE') DEFAULT 'MINEURE',
    statut          ENUM('OUVERTE','EN_COURS','CLOTUREE') DEFAULT 'OUVERTE',
    action_corrective TEXT,
    responsable_id  INT,
    date_cloture    DATE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cq_id)          REFERENCES controles_qualite(id) ON DELETE SET NULL,
    FOREIGN KEY (of_id)          REFERENCES ordres_fabrication(id) ON DELETE SET NULL,
    FOREIGN KEY (responsable_id) REFERENCES operateurs(id) ON DELETE SET NULL
);

-- ── MAINTENANCE ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ordres_maintenance (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    om_numero       VARCHAR(30) UNIQUE NOT NULL,
    machine_id      INT NOT NULL,
    type_maintenance ENUM('PREVENTIVE','CORRECTIVE','URGENCE') DEFAULT 'CORRECTIVE',
    titre           VARCHAR(300) NOT NULL,
    description     TEXT,
    priorite        ENUM('BASSE','NORMAL','HAUTE','URGENT') DEFAULT 'NORMAL',
    statut          ENUM('PLANIFIE','EN_COURS','TERMINE','ANNULE') DEFAULT 'PLANIFIE',
    technicien_id   INT,
    date_planifiee  DATE,
    date_debut      DATETIME,
    date_fin        DATETIME,
    duree_estimee   INT DEFAULT 0,  -- minutes
    cout_estime     DECIMAL(10,3) DEFAULT 0,
    cout_reel       DECIMAL(10,3) DEFAULT 0,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (machine_id)    REFERENCES machines(id) ON DELETE CASCADE,
    FOREIGN KEY (technicien_id) REFERENCES operateurs(id) ON DELETE SET NULL
);

-- ── PLANIFICATION ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS planning_production (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    of_id           INT NOT NULL,
    machine_id      INT,
    operateur_id    INT,
    date_debut      DATETIME NOT NULL,
    date_fin        DATETIME NOT NULL,
    statut          ENUM('PLANIFIE','EN_COURS','TERMINE','ANNULE') DEFAULT 'PLANIFIE',
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (of_id)         REFERENCES ordres_fabrication(id) ON DELETE CASCADE,
    FOREIGN KEY (machine_id)    REFERENCES machines(id) ON DELETE SET NULL,
    FOREIGN KEY (operateur_id)  REFERENCES operateurs(id) ON DELETE SET NULL
);

SELECT 'Schema v4.0 additions installed!' as STATUS;
