-- ============================================
-- SOFEM MES — Schema MySQL
-- ============================================

CREATE DATABASE IF NOT EXISTS sofem_mes CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sofem_mes;

-- Opérateurs
CREATE TABLE IF NOT EXISTS operateurs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    specialite ENUM('AutoCAD','Découpage','Pliage','Soudage','Ponçage') NOT NULL,
    actif BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Produits
CREATE TABLE IF NOT EXISTS produits (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    nom VARCHAR(200) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Matériaux
CREATE TABLE IF NOT EXISTS materiaux (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    nom VARCHAR(200) NOT NULL,
    unite VARCHAR(20) NOT NULL,
    stock_actuel DECIMAL(10,2) DEFAULT 0,
    stock_minimum DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Ordres de Fabrication
CREATE TABLE IF NOT EXISTS ordres_fabrication (
    id INT AUTO_INCREMENT PRIMARY KEY,
    numero VARCHAR(20) UNIQUE NOT NULL,
    produit_id INT NOT NULL,
    quantite INT NOT NULL,
    priorite ENUM('LOW','NORMAL','HIGH','URGENT') DEFAULT 'NORMAL',
    statut ENUM('DRAFT','APPROVED','IN_PROGRESS','COMPLETED','CANCELLED') DEFAULT 'DRAFT',
    operateur_id INT,
    atelier VARCHAR(50) DEFAULT 'Workshop A',
    date_echeance DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (produit_id) REFERENCES produits(id),
    FOREIGN KEY (operateur_id) REFERENCES operateurs(id)
);

-- Étapes de production par OF
CREATE TABLE IF NOT EXISTS etapes_production (
    id INT AUTO_INCREMENT PRIMARY KEY,
    of_id INT NOT NULL,
    etape ENUM('AutoCAD','Découpage','Pliage','Soudage','Ponçage') NOT NULL,
    statut ENUM('PENDING','IN_PROGRESS','COMPLETED') DEFAULT 'PENDING',
    operateur_id INT,
    debut TIMESTAMP NULL,
    fin TIMESTAMP NULL,
    notes TEXT,
    FOREIGN KEY (of_id) REFERENCES ordres_fabrication(id) ON DELETE CASCADE,
    FOREIGN KEY (operateur_id) REFERENCES operateurs(id),
    UNIQUE KEY unique_of_etape (of_id, etape)
);

-- BOM — Matériaux requis par produit
CREATE TABLE IF NOT EXISTS bom (
    id INT AUTO_INCREMENT PRIMARY KEY,
    produit_id INT NOT NULL,
    materiau_id INT NOT NULL,
    quantite_par_unite DECIMAL(10,3) NOT NULL,
    FOREIGN KEY (produit_id) REFERENCES produits(id),
    FOREIGN KEY (materiau_id) REFERENCES materiaux(id),
    UNIQUE KEY unique_bom (produit_id, materiau_id)
);

-- Mouvements de stock
CREATE TABLE IF NOT EXISTS mouvements_stock (
    id INT AUTO_INCREMENT PRIMARY KEY,
    materiau_id INT NOT NULL,
    of_id INT,
    type ENUM('ENTREE','SORTIE','AJUSTEMENT') NOT NULL,
    quantite DECIMAL(10,2) NOT NULL,
    motif VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (materiau_id) REFERENCES materiaux(id),
    FOREIGN KEY (of_id) REFERENCES ordres_fabrication(id)
);

-- ============================================
-- DONNÉES INITIALES
-- ============================================

INSERT INTO operateurs (nom, prenom, specialite) VALUES
('Dupont', 'Jean', 'Soudage'),
('Robert', 'Marc', 'Pliage'),
('Lambert', 'Sofia', 'Découpage'),
('Benzara', 'Karim', 'Ponçage');

INSERT INTO produits (code, nom) VALUES
('BA-004', 'Bracket Assembly'),
('SC-001', 'Shaft Coupling'),
('GH-002', 'Gear Housing'),
('FP-003', 'Flange Plate'),
('CS-005', 'Cam Shaft');

INSERT INTO materiaux (code, nom, unite, stock_actuel, stock_minimum) VALUES
('MAT-001', 'Tôle Acier S235 3mm', 'm²', 3.2, 10.0),
('MAT-002', 'Fil Soudure ER70S', 'kg', 42.0, 50.0),
('MAT-003', 'Profilé Aluminium 40x40', 'm', 25.0, 8.0),
('MAT-004', 'Acier Rond Ø40', 'm', 4.5, 8.0),
('MAT-005', 'Visserie M8', 'pcs', 850, 200);

INSERT INTO ordres_fabrication (numero, produit_id, quantite, priorite, statut, operateur_id, date_echeance) VALUES
('OF-2025-042', 1, 50, 'URGENT', 'IN_PROGRESS', 1, '2025-02-28'),
('OF-2025-041', 2, 120, 'NORMAL', 'IN_PROGRESS', 2, '2025-03-05'),
('OF-2025-040', 3, 30, 'HIGH', 'IN_PROGRESS', 3, '2025-03-10'),
('OF-2025-039', 4, 200, 'LOW', 'COMPLETED', 4, '2025-03-15'),
('OF-2025-038', 5, 75, 'NORMAL', 'DRAFT', NULL, '2025-03-20');

INSERT INTO etapes_production (of_id, etape, statut) VALUES
(1,'AutoCAD','COMPLETED'),(1,'Découpage','COMPLETED'),(1,'Pliage','IN_PROGRESS'),(1,'Soudage','PENDING'),(1,'Ponçage','PENDING'),
(2,'AutoCAD','COMPLETED'),(2,'Découpage','COMPLETED'),(2,'Pliage','COMPLETED'),(2,'Soudage','IN_PROGRESS'),(2,'Ponçage','PENDING'),
(3,'AutoCAD','COMPLETED'),(3,'Découpage','IN_PROGRESS'),(3,'Pliage','PENDING'),(3,'Soudage','PENDING'),(3,'Ponçage','PENDING'),
(4,'AutoCAD','COMPLETED'),(4,'Découpage','COMPLETED'),(4,'Pliage','COMPLETED'),(4,'Soudage','COMPLETED'),(4,'Ponçage','COMPLETED'),
(5,'AutoCAD','PENDING'),(5,'Découpage','PENDING'),(5,'Pliage','PENDING'),(5,'Soudage','PENDING'),(5,'Ponçage','PENDING');
