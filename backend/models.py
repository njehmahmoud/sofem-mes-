"""SOFEM MES v6.0 — Pydantic Models (Commit 01 — ISO 9001 soft delete)"""

from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import date

# ── AUTH ──────────────────────────────────────────────────
class PINLogin(BaseModel):
    pin: str

class UserCreate(BaseModel):
    nom: str; prenom: str; role: str; pin: str
    operateur_id: Optional[int] = None; actif: bool = True

class UserUpdate(BaseModel):
    nom: Optional[str]=None; prenom: Optional[str]=None
    role: Optional[str]=None; pin: Optional[str]=None; actif: Optional[bool]=None

# ── ISO 9001 — CANCELLATION & AUDIT ───────────────────────

class CancelRequest(BaseModel):
    """
    Used for every cancellation endpoint.
    Reason is mandatory — ISO 9001 Clause 7.5 requires traceability.
    """
    reason: str

    @validator('reason')
    def reason_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Une raison est obligatoire pour annuler un document')
        if len(v.strip()) < 5:
            raise ValueError('La raison doit contenir au moins 5 caractères')
        return v.strip()


class DeactivateRequest(BaseModel):
    """
    Used for soft-deleting master data records (materiaux, machines, etc.)
    """
    reason: Optional[str] = None


class ActivityLogEntry(BaseModel):
    """Read model for activity log entries."""
    id: int
    created_at: str
    user_id: Optional[int]
    user_nom: Optional[str]
    action: str
    entity_type: str
    entity_id: Optional[int]
    entity_numero: Optional[str]
    reason: Optional[str]
    detail: Optional[str]


# ── CLIENTS ───────────────────────────────────────────────
class ClientCreate(BaseModel):
    nom: str
    matricule_fiscal: Optional[str] = None
    adresse: Optional[str] = None
    ville: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None

class ClientUpdate(BaseModel):
    nom: Optional[str] = None
    matricule_fiscal: Optional[str] = None
    adresse: Optional[str] = None
    ville: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    actif: Optional[bool] = None

# ── OPERATEURS ────────────────────────────────────────────
class OperateurCreate(BaseModel):
    nom: str; prenom: str; specialite: str
    role: str = "OPERATEUR"
    telephone: Optional[str]=None; email: Optional[str]=None
    taux_horaire: float = 0
    taux_piece: float = 0
    type_taux: str = "HORAIRE"

class OperateurUpdate(BaseModel):
    nom: Optional[str]=None; prenom: Optional[str]=None
    specialite: Optional[str]=None; telephone: Optional[str]=None
    email: Optional[str]=None; actif: Optional[bool]=None
    role: Optional[str]=None
    taux_horaire: Optional[float]=None
    taux_piece: Optional[float]=None
    type_taux: Optional[str]=None

# ── OF ────────────────────────────────────────────────────
class OperationIn(BaseModel):
    operation_nom: str
    machine_id: Optional[int] = None
    operateur_ids: List[int] = []
    ordre: Optional[int] = None

class BOMOverride(BaseModel):
    materiau_id: int
    quantite_requise: float

class OFCreate(BaseModel):
    produit_id: int
    quantite: int
    priorite: str = "NORMAL"
    chef_projet_id: Optional[int] = None
    client_id: Optional[int] = None
    plan_numero: Optional[str] = None
    atelier: str = "Atelier A"
    date_echeance: str
    notes: Optional[str] = None
    sous_traitant: Optional[str] = None
    sous_traitant_op: Optional[str] = None
    sous_traitant_cout: float = 0
    operations: List[OperationIn] = []
    bom_overrides: List[BOMOverride] = []

class OFUpdate(BaseModel):
    statut: Optional[str] = None
    priorite: Optional[str] = None
    chef_projet_id: Optional[int] = None
    client_id: Optional[int] = None
    plan_numero: Optional[str] = None
    atelier: Optional[str] = None
    notes: Optional[str] = None
    sous_traitant: Optional[str] = None
    sous_traitant_op: Optional[str] = None
    sous_traitant_cout: Optional[float] = None

class OperationCreate(BaseModel):
    operation_nom: str
    machine_id: Optional[int] = None
    operateur_ids: List[int] = []
    ordre: Optional[int] = None

class OperationUpdate(BaseModel):
    operation_nom: Optional[str] = None
    machine_id: Optional[int] = None
    statut: Optional[str] = None
    duree_reelle: Optional[int] = None
    notes: Optional[str] = None

# ── PRODUITS ──────────────────────────────────────────────
class ProduitCreate(BaseModel):
    nom: str
    description: Optional[str] = None
    unite: str = "pcs"
    prix_vente_ht: float = 0.0

class ProduitUpdate(BaseModel):
    nom: Optional[str] = None
    description: Optional[str] = None
    unite: Optional[str] = None
    prix_vente_ht: Optional[float] = None

class BOMLine(BaseModel):
    materiau_id: int
    quantite_par_unite: float

# ── MATERIAUX ─────────────────────────────────────────────
class MateriauCreate(BaseModel):
    code: str = ""; nom: str; unite: str
    stock_actuel: float=0; stock_minimum: float=0
    fournisseur: Optional[str]=None
    prix_unitaire: float=0.0

class MateriauUpdate(BaseModel):
    nom:           Optional[str]   = None
    unite:         Optional[str]   = None
    stock_minimum: Optional[float] = None
    fournisseur:   Optional[str]   = None
    prix_unitaire: Optional[float] = None

class MouvementCreate(BaseModel):
    materiau_id: int; of_id: Optional[int]=None
    type: str; quantite: float; motif: Optional[str]=None

# ── ACHATS ────────────────────────────────────────────────
class DACreate(BaseModel):
    materiau_id: Optional[int] = None
    of_id: Optional[int] = None
    description: str
    objet: Optional[str] = None
    quantite: float
    unite: str = "pcs"
    urgence: str = "NORMAL"
    notes: Optional[str] = None
    demandeur_id: Optional[int] = None

class DAUpdate(BaseModel):
    statut: Optional[str] = None
    valideur_id: Optional[int] = None
    objet: Optional[str] = None
    notes: Optional[str] = None

class BCLigne(BaseModel):
    materiau_id: Optional[int]=None; description: str
    quantite: float; unite: str="pcs"

class BCCreate(BaseModel):
    fournisseur: str; da_id: Optional[int]=None
    notes: Optional[str]=None; lignes: List[BCLigne]=[]

class BRLigne(BaseModel):
    bc_ligne_id: int; quantite_recue: float; prix_unitaire: Optional[float]=None

class BRCreate(BaseModel):
    bc_id: int; date_reception: date
    statut: str="COMPLET"; notes: Optional[str]=None
    lignes: List[BRLigne]=[]

class FACreate(BaseModel):
    # For purchase invoices (materials)
    bc_id: Optional[int] = None
    # For sales invoices (OF sales)
    of_id: Optional[int] = None
    # Common fields
    fournisseur: Optional[str] = None  # supplier for purchase, or "SOFEM" for sales
    date_facture: date
    notes: Optional[str] = None
    
    class Config:
        validate_assignment = True

# ── BL ────────────────────────────────────────────────────
class BLCreate(BaseModel):
    of_id: int
    date_livraison: Optional[date] = None
    destinataire: str = "SOFEM"
    adresse: str = "Route Sidi Salem 2.5KM, Sfax"
    notes: Optional[str] = None

class BLUpdate(BaseModel):
    statut: Optional[str] = None
    date_livraison: Optional[date] = None
    notes: Optional[str] = None

class BLLivrer(BaseModel):
    destinataire: str
    adresse: str
    date_livraison: date
    notes: Optional[str] = None

# ── MACHINES ──────────────────────────────────────────────
class MachineCreate(BaseModel):
    code: Optional[str]=None; nom: str
    type: Optional[str]=None; marque: Optional[str]=None
    modele: Optional[str]=None; numero_serie: Optional[str]=None
    atelier: str="Atelier A"; statut: str="OPERATIONNELLE"
    date_acquisition: Optional[date]=None; notes: Optional[str]=None

class MachineUpdate(BaseModel):
    nom: Optional[str]=None; type: Optional[str]=None
    marque: Optional[str]=None; modele: Optional[str]=None
    numero_serie: Optional[str]=None; atelier: Optional[str]=None
    statut: Optional[str]=None; date_acquisition: Optional[date]=None
    notes: Optional[str]=None

# ── FOURNISSEURS ──────────────────────────────────────────
class FournisseurCreate(BaseModel):
    code: Optional[str]=None; nom: str
    contact: Optional[str]=None; telephone: Optional[str]=None
    email: Optional[str]=None; adresse: Optional[str]=None
    ville: Optional[str]=None; pays: str="Tunisie"
    matricule_fiscal: Optional[str]=None; statut: str="ACTIF"
    notes: Optional[str]=None

class FournisseurUpdate(BaseModel):
    nom: Optional[str]=None; contact: Optional[str]=None
    telephone: Optional[str]=None; email: Optional[str]=None
    adresse: Optional[str]=None; ville: Optional[str]=None
    pays: Optional[str]=None; matricule_fiscal: Optional[str]=None
    statut: Optional[str]=None; notes: Optional[str]=None

# ── QUALITÉ ───────────────────────────────────────────────
class CQCreate(BaseModel):
    of_id: Optional[int]=None; type_controle: str="FINAL"
    operateur_id: Optional[int]=None; date_controle: date
    statut: str="EN_ATTENTE"; quantite_controlee: float=0
    quantite_conforme: float=0; quantite_rebut: float=0
    notes: Optional[str]=None

class CQUpdate(BaseModel):
    statut: Optional[str]=None; quantite_controlee: Optional[float]=None
    quantite_conforme: Optional[float]=None; quantite_rebut: Optional[float]=None
    notes: Optional[str]=None

class NCCreate(BaseModel):
    cq_id: Optional[int]=None; of_id: Optional[int]=None
    type_defaut: str; description: Optional[str]=None
    gravite: str="MINEURE"; statut: str="OUVERTE"
    action_corrective: Optional[str]=None; responsable_id: Optional[int]=None

class NCUpdate(BaseModel):
    statut: Optional[str]=None; gravite: Optional[str]=None
    action_corrective: Optional[str]=None
    responsable_id: Optional[int]=None; date_cloture: Optional[date]=None

# ── MAINTENANCE ───────────────────────────────────────────
class MaintenanceCreate(BaseModel):
    machine_id: int; type_maintenance: str="CORRECTIVE"
    titre: str; description: Optional[str]=None
    priorite: str="NORMAL"; statut: str="PLANIFIE"
    technicien_id: Optional[int]=None; date_planifiee: Optional[date]=None
    duree_estimee: int=0; cout_estime: float=0; notes: Optional[str]=None

class MaintenanceUpdate(BaseModel):
    type_maintenance: Optional[str]=None; titre: Optional[str]=None
    description: Optional[str]=None; priorite: Optional[str]=None
    statut: Optional[str]=None; technicien_id: Optional[int]=None
    date_planifiee: Optional[date]=None; date_debut: Optional[str]=None
    date_fin: Optional[str]=None; duree_estimee: Optional[int]=None
    cout_estime: Optional[float]=None; cout_reel: Optional[float]=None
    notes: Optional[str]=None

# ── PLANIFICATION ─────────────────────────────────────────
class PlanningCreate(BaseModel):
    of_id: int; machine_id: Optional[int]=None
    operateur_id: Optional[int]=None
    date_debut: str; date_fin: str
    statut: str="PLANIFIE"; notes: Optional[str]=None

class PlanningUpdate(BaseModel):
    machine_id: Optional[int]=None; operateur_id: Optional[int]=None
    date_debut: Optional[str]=None; date_fin: Optional[str]=None
    statut: Optional[str]=None; notes: Optional[str]=None