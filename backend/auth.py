"""
SOFEM MES v2.0 — Authentication
PIN Login + JWT Tokens + Role-based access
SMARTMOVE · Mahmoud Njeh
"""

import os
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

logger = logging.getLogger("sofem-mes")

SECRET_KEY = os.environ.get("SECRET_KEY", "sofem-mes-smartmove-2025-secret")
ALGORITHM  = "HS256"
TOKEN_EXPIRE_HOURS = 12

security = HTTPBearer()

# ── PIN HASHING ───────────────────────────
def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()

def verify_pin(pin: str, hashed: str) -> bool:
    return hash_pin(pin) == hashed

# ── JWT ───────────────────────────────────
def create_token(user_id: int, role: str, nom: str, prenom: str, operateur_id: Optional[int] = None) -> str:
    payload = {
        "sub":          str(user_id),
        "role":         role,
        "nom":          nom,
        "prenom":       prenom,
        "operateur_id": operateur_id,
        "exp":          datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expirée — reconnectez-vous")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token invalide")

# ── DEPENDENCIES ─────────────────────────
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    return decode_token(credentials.credentials)

def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "ADMIN":
        raise HTTPException(403, "Accès réservé aux administrateurs")
    return user

def require_manager_or_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in ("ADMIN", "MANAGER"):
        raise HTTPException(403, "Accès réservé aux managers et administrateurs")
    return user

def require_any_role(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in ("ADMIN", "MANAGER", "OPERATOR"):
        raise HTTPException(403, "Accès non autorisé")
    return user

# Backwards-compatibility aliases
require_role = require_any_role
