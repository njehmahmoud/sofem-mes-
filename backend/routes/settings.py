"""SOFEM MES v10.0 — Settings"""

from fastapi import APIRouter, Depends
from typing import Optional, Dict, Any
from pydantic import BaseModel
from database import get_db, q, exe, serialize
from auth import require_any_role, require_admin

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    valeur: Optional[str] = None


class SettingsBulkUpdate(BaseModel):
    settings: Dict[str, Any]


def get_all_settings(db) -> dict:
    """Returns all settings as a flat key→value dict."""
    rows = q(db, "SELECT cle, valeur, type FROM settings")
    result = {}
    for r in rows:
        v = r["valeur"]
        if r["type"] == "boolean":
            v = v in ("true", "1", "yes")
        elif r["type"] == "number":
            try: v = float(v) if "." in str(v) else int(v)
            except: v = 0
        result[r["cle"]] = v
    return result


@router.get("", dependencies=[Depends(require_any_role)])
def list_settings(db=Depends(get_db)):
    """Get all settings grouped."""
    rows = q(db, "SELECT * FROM settings ORDER BY groupe, id")
    grouped = {}
    for r in serialize(rows):
        g = r["groupe"]
        if g not in grouped: grouped[g] = []
        # Parse value
        v = r["valeur"]
        if r["type"] == "boolean": v = v in ("true","1","yes")
        elif r["type"] == "number":
            try: v = float(v) if "." in str(v) else int(v)
            except: v = 0
        r["valeur_parsed"] = v
        grouped[g].append(r)
    return grouped


@router.get("/flat", dependencies=[Depends(require_any_role)])
def get_flat_settings(db=Depends(get_db)):
    """Flat key→value dict — used by PDFs and frontend."""
    return get_all_settings(db)


@router.put("/bulk", dependencies=[Depends(require_admin)])
def update_settings_bulk(data: SettingsBulkUpdate, db=Depends(get_db)):
    """Update multiple settings at once."""
    for cle, valeur in data.settings.items():
        str_val = str(valeur).lower() if isinstance(valeur, bool) else str(valeur)
        exe(db, """
            INSERT INTO settings (cle, valeur)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE valeur = %s, updated_at = CURRENT_TIMESTAMP
        """, (cle, str_val, str_val))
    return {"message": f"{len(data.settings)} paramètre(s) mis à jour"}


@router.put("/{cle}", dependencies=[Depends(require_admin)])
def update_setting(cle: str, data: SettingUpdate, db=Depends(get_db)):
    exe(db, """
        INSERT INTO settings (cle, valeur)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE valeur = %s, updated_at = CURRENT_TIMESTAMP
    """, (cle, data.valeur, data.valeur))
    return {"message": "Paramètre mis à jour"}