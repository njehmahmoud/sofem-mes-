-- ============================================================
-- SOFEM MES v2.0 — Schema MySQL
-- SMARTMOVE · Mahmoud Njeh
-- ============================================================

CREATE DATABASE IF NOT EXISTS sofem_mes CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sofem_mes;

-- ── USERS (Auth) ─────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    nom          VARCHAR(100) NOT NULL,
    prenom       VARCHAR(100) NOT NULL,
    role         ENUM('ADMIN','MANAGER','OPERATOR') NOT NULL,
    pin_hash     VARCHAR(64) NOT NULL,
    operateur_id INT,
    actif        BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── OPERATEURS ────────────────────────────
CREATE TABLE IF NOT EXISTS operateurs (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    nom        VARCHAR(100) NOT NULL,
    prenom     VARCHAR(100) NOT NULL,
    specialite ENUM('AutoCAD','Découpage','Pliage','Soudage','Ponçage') NOT NULL,
    telephone  VARCHAR(20),
    email      VARCHAR(100),
    actif      BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── PRODUITS ──────────────────────────────
CREATE TABLE IF NOT EXISTS produits (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    code        VARCHAR(50) UNIQUE NOT NULL,
    nom         VARCHAR(200) NOT NULL,
    description TEXT,
    unite       VARCHAR(20) DEFAULT 'pcs',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── MATERIAUX ─────────────────────────────
CREATE TABLE IF NOT EXISTS materiaux (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    code          VARCHAR(50) UNIQUE NOT NULL,
    nom           VARCHAR(200) NOT NULL,
    unite         VARCHAR(20) NOT NULL,
    stock_actuel  DECIMAL(10,2) DEFAULT 0,
    stock_minimum DECIMAL(10,2) DEFAULT 0,
    fournisseur   VARCHAR(200),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ── ORDRES DE FABRICATION ─────────────────
CREATE TABLE IF NOT EXISTS ordres_fabrication (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    numero        VARCHAR(20) UNIQUE NOT NULL,
    produit_id    INT NOT NULL,
    quantite      INT NOT NULL,
    priorite      ENUM('LOW','NORMAL','HIGH','URGENT') DEFAULT 'NORMAL',
    statut        ENUM('DRAFT','APPROVED','IN_PROGRESS','COMPLETED','CANCELLED') DEFAULT 'DRAFT',
    operateur_id  INT,
    atelier       VARCHAR(50) DEFAULT 'Atelier A',
    date_echeance DATE NOT NULL,
    notes         TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (produit_id)   REFERENCES produits(id),
    FOREIGN KEY (operateur_id) REFERENCES operateurs(id)
);

-- ── ETAPES DE PRODUCTION ──────────────────
CREATE TABLE IF NOT EXISTS etapes_production (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    of_id        INT NOT NULL,
    etape        ENUM('AutoCAD','Découpage','Pliage','Soudage','Ponçage') NOT NULL,
    statut       ENUM('PENDING','IN_PROGRESS','COMPLETED') DEFAULT 'PENDING',
    operateur_id INT,
    debut        TIMESTAMP NULL,
    fin          TIMESTAMP NULL,
    notes        TEXT,
    FOREIGN KEY (of_id)        REFERENCES ordres_fabrication(id) ON DELETE CASCADE,
    FOREIGN KEY (operateur_id) REFERENCES operateurs(id),
    UNIQUE KEY unique_of_etape (of_id, etape)
);

-- ── MOUVEMENTS STOCK ──────────────────────
CREATE TABLE IF NOT EXISTS mouvements_stock (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    materiau_id INT NOT NULL,
    of_id       INT,
    type        ENUM('ENTREE','SORTIE','AJUSTEMENT') NOT NULL,
    quantite    DECIMAL(10,2) NOT NULL,
    stock_avant DECIMAL(10,2),
    stock_apres DECIMAL(10,2),
    motif       VARCHAR(200),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (materiau_id) REFERENCES materiaux(id),
    FOREIGN KEY (of_id)       REFERENCES ordres_fabrication(id)
);

-- ── DONNEES INITIALES ─────────────────────

INSERT INTO operateurs (nom, prenom, specialite, telephone) VALUES
('Dupont',  'Jean',  'Soudage',   '+216 90 000 001'),
('Robert',  'Marc',  'Pliage',    '+216 90 000 002'),
('Lambert', 'Sofia', 'Découpage', '+216 90 000 003'),
('Benzara', 'Karim', 'Ponçage',   '+216 90 000 004');

INSERT INTO produits (code, nom, description, unite) VALUES
('BA-004', 'Bracket Assembly', 'Support de fixation', 'pcs'),
('SC-001', 'Shaft Coupling',   'Accouplement arbre',  'pcs'),
('GH-002', 'Gear Housing',     'Carter engrenage',    'pcs'),
('FP-003', 'Flange Plate',     'Plaque a brides',     'pcs'),
('CS-005', 'Cam Shaft',        'Arbre a cames',       'pcs');

INSERT INTO materiaux (code, nom, unite, stock_actuel, stock_minimum, fournisseur) VALUES
('MAT-001', 'Tole Acier S235 3mm',     'm2',  3.2,  10.0, 'Aciers du Nord'),
('MAT-002', 'Fil Soudure ER70S',       'kg',  42.0, 50.0, 'SoudeTech'),
('MAT-003', 'Profile Aluminium 40x40', 'm',   25.0,  8.0, 'AlumPro'),
('MAT-004', 'Acier Rond O40',          'm',    4.5,  8.0, 'Aciers du Nord'),
('MAT-005', 'Visserie M8',             'pcs', 850,  200,  'Fixalia');

INSERT INTO ordres_fabrication (numero, produit_id, quantite, priorite, statut, operateur_id, date_echeance) VALUES
('OF-2025-042', 1, 50,  'URGENT', 'IN_PROGRESS', 1, '2025-04-01'),
('OF-2025-041', 2, 120, 'NORMAL', 'IN_PROGRESS', 2, '2025-04-05'),
('OF-2025-040', 3, 30,  'HIGH',   'IN_PROGRESS', 3, '2025-04-10'),
('OF-2025-039', 4, 200, 'LOW',    'COMPLETED',   4, '2025-03-15'),
('OF-2025-038', 5, 75,  'NORMAL', 'DRAFT',       NULL, '2025-04-20');

INSERT INTO etapes_production (of_id, etape, statut) VALUES
(1,'AutoCAD','COMPLETED'),(1,'Découpage','COMPLETED'),(1,'Pliage','IN_PROGRESS'),(1,'Soudage','PENDING'),(1,'Ponçage','PENDING'),
(2,'AutoCAD','COMPLETED'),(2,'Découpage','COMPLETED'),(2,'Pliage','COMPLETED'),  (2,'Soudage','IN_PROGRESS'),(2,'Ponçage','PENDING'),
(3,'AutoCAD','COMPLETED'),(3,'Découpage','IN_PROGRESS'),(3,'Pliage','PENDING'),  (3,'Soudage','PENDING'),(3,'Ponçage','PENDING'),
(4,'AutoCAD','COMPLETED'),(4,'Découpage','COMPLETED'),(4,'Pliage','COMPLETED'),  (4,'Soudage','COMPLETED'),(4,'Ponçage','COMPLETED'),
(5,'AutoCAD','PENDING'),  (5,'Découpage','PENDING'),  (5,'Pliage','PENDING'),    (5,'Soudage','PENDING'),(5,'Ponçage','PENDING');

-- ── DEFAULT USERS ─────────────────────────
-- Admin  PIN : 1234
-- Manager PIN: 5678
-- Jean   PIN : 1111
-- Marc   PIN : 2222
INSERT INTO users (nom, prenom, role, pin_hash, operateur_id) VALUES
('Njeh',   'Mahmoud', 'ADMIN',    '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', NULL),
('Sofem',  'Manager', 'MANAGER',  'f8638b979b2f4f793ddb6dbd197e0ee25a7a6ea32b0ae22f5e3c5d119d839e75', NULL),
('Dupont', 'Jean',    'OPERATOR', '0ffe1abd1a08215353c233d6e009613e95eec4253832a761af28ff37ac5a150c', 1),
('Robert', 'Marc',    'OPERATOR', 'edee29f882543b956620b26d0ee0e7e950399b1c4222f5de05e06425b4c995e9', 2);
