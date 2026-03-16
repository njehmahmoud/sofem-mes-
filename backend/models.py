"""
SOFEM MES v2.0 — Models / Schemas
SMARTMOVE · Mahmoud Njeh
"""

from pydantic import BaseModel
from typing import Optional
from datetime import date

# ── AUTH ──────────────────────────────────
class PINLogin(BaseModel):
    pin: str

class UserCreate(BaseModel):
    nom: str
    prenom: str
    role: str           # ADMIN, MANAGER, OPERATOR
    pin: str
    operateur_id: Optional[int] = None  # link to operateur if OPERATOR role
    actif: bool = True

class UserUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    role: Optional[str] = None
    pin: Optional[str] = None
    actif: Optional[bool] = None

# ── ORDRES DE FABRICATION ─────────────────
class OFCreate(BaseModel):
    produit_id: int
    quantite: int
    priorite: str = "NORMAL"
    operateur_id: Optional[int] = None
    atelier: str = "Atelier A"
    date_echeance: date
    notes: Optional[str] = None

class OFUpdate(BaseModel):
    statut: Optional[str] = None
    priorite: Optional[str] = None
    operateur_id: Optional[int] = None
    atelier: Optional[str] = None
    notes: Optional[str] = None

# ── ETAPES ────────────────────────────────
class EtapeUpdate(BaseModel):
    statut: str
    operateur_id: Optional[int] = None
    notes: Optional[str] = None

# ── MATERIAUX ─────────────────────────────
class MateriauCreate(BaseModel):
    code: str
    nom: str
    unite: str
    stock_actuel: float = 0
    stock_minimum: float = 0
    fournisseur: Optional[str] = None

class MouvementCreate(BaseModel):
    materiau_id: int
    of_id: Optional[int] = None
    type: str
    quantite: float
    motif: Optional[str] = None

# ── OPERATEURS ────────────────────────────
class OperateurCreate(BaseModel):
    nom: str
    prenom: str
    specialite: str
    telephone: Optional[str] = None
    email: Optional[str] = None

class OperateurUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    specialite: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    actif: Optional[bool] = None

# ── PRODUITS ──────────────────────────────
class ProduitCreate(BaseModel):
    code: str
    nom: str
    description: Optional[str] = None
    unite: str = "pcs"
