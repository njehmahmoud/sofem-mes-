"""
SOFEM MES v6.0 — Authentication (patched)
Fixes:
  - PIN hashing upgraded from SHA-256 to bcrypt (via passlib)
  - Legacy SHA-256 hashes are verified and auto-upgraded on login
  - Raises startup warning if SECRET_KEY is the insecure default
  - is_legacy_hash() exported for auth_routes to trigger re-hashing
SMARTMOVE · Mahmoud Njeh
"""

import os
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Query
from passlib.context import CryptContext
import jwt

logger = logging.getLogger("sofem-mes")

SECRET_KEY = os.environ.get("SECRET_KEY", "")

if not SECRET_KEY:
    error_msg = (
        "❌ FATAL: SECRET_KEY environment variable is not set. "
        "This is required for production security. "
        "Set it in your Railway/deployment environment variables immediately."
    )
    logger.error(error_msg)
    raise ValueError(error_msg)

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 12

security = HTTPBearer()

# ── Bcrypt context ────────────────────────────────────────
_bcrypt = CryptContext(schemes=["bcrypt"], deprecated="auto")


def is_legacy_hash(hashed: str) -> bool:
    """Returns True if the stored hash is SHA-256 (hex string, not a bcrypt hash)."""
    return not (hashed.startswith("$2b$") or hashed.startswith("$2a$"))


def hash_pin(pin: str) -> str:
    """Hash a PIN with bcrypt."""
    return _bcrypt.hash(pin)


def verify_pin(pin: str, hashed: str) -> bool:
    """
    Verify a PIN against a stored hash.
    Supports both bcrypt (new) and SHA-256 (legacy) hashes so existing
    users can still log in while their hash is upgraded on next login.
    """
    if is_legacy_hash(hashed):
        # Legacy SHA-256 path
        return hashlib.sha256(pin.encode()).hexdigest() == hashed
    # Bcrypt path
    try:
        return _bcrypt.verify(pin, hashed)
    except Exception:
        return False


# ── JWT ───────────────────────────────────────────────────

def create_token(user_id: int, role: str, nom: str, prenom: str,
                 operateur_id: Optional[int] = None) -> str:
    payload = {
        "sub":          str(user_id),
        "role":         role,
        "nom":          nom,
        "prenom":       prenom,
        "operateur_id": operateur_id,
        "exp":          datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"DEBUG: Token decoded successfully for user {decoded.get('sub')}")
        return decoded
    except jwt.ExpiredSignatureError:
        print(f"DEBUG: Token expired")
        raise HTTPException(401, "Session expirée — reconnectez-vous")
    except jwt.InvalidTokenError as e:
        print(f"DEBUG: Invalid token: {str(e)}")
        raise HTTPException(401, "Token invalide")


# ── Dependencies ──────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    return decode_token(credentials.credentials)


def get_pdf_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
) -> dict:
    """Accepts token from query param OR Authorization header (for PDF window.open())."""
    token = request.query_params.get("token")
    if token:
        return decode_token(token)
    if credentials:
        return decode_token(credentials.credentials)
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Non authentifié")


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


# Backward-compatibility alias
require_role = require_any_role
