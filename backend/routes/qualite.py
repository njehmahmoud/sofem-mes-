"""
SOFEM MES v4.0 — Contrôle Qualité & Non-Conformités
SMARTMOVE · Mahmoud Njeh
"""

from fastapi import APIRouter, Depends, HTTPException
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from models import CQCreate, CQUpdate, NCCreate, NCUpdate
from datetime import date

router = APIRouter(prefix="/api/qualite", tags=["qualite"])


# ── CONTRÔLES QUALITÉ ─────────────────────────────────────

@router.get("/controles")
def list_controles(conn=Depends(get_db), user=Depends(require_any_role)):
    rows = q(conn, """
        SELECT cq.*,
               of_.numero AS of_numero, of_.produit_id,
               p.nom as produit_nom,
               o.nom as operateur_nom, o.prenom as operateur_prenom
        FROM controles_qualite cq
        LEFT JOIN ordres_fabrication of_ ON of_.id = cq.of_id
        LEFT JOIN produits p ON p.id = of_.produit_id
        LEFT JOIN operateurs o ON o.id = cq.operateur_id
        ORDER BY cq.created_at DESC
    """)
    return serialize(rows)


@router.post("/controles", status_code=201)
def create_controle(data: CQCreate, conn=Depends(get_db), user=Depends(require_any_role)):
    count = q(conn, "SELECT COUNT(*) as c FROM controles_qualite", one=True)["c"]
    cq_num = f"CQ-{date.today().year}-{count+1:04d}"
    cid = exe(conn, """
        INSERT INTO controles_qualite
        (cq_numero,of_id,type_controle,operateur_id,date_controle,statut,
         quantite_controlée,quantite_conforme,quantite_rebut,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (cq_num, data.of_id, data.type_controle, data.operateur_id,
          data.date_controle, data.statut, data.quantite_controlee,
          data.quantite_conforme, data.quantite_rebut, data.notes))
    return {"id": cid, "cq_numero": cq_num, "message": "Contrôle créé"}


@router.put("/controles/{cid}")
def update_controle(cid: int, data: CQUpdate, conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    # Map Pydantic field names to actual DB column names (accent in DB column)
    FIELD_MAP = {"quantite_controlee": "quantite_controlée"}
    fields, vals = [], []
    for f, v in data.dict(exclude_none=True).items():
        db_col = FIELD_MAP.get(f, f)
        fields.append(f"{db_col}=%s")
        vals.append(v)
    if not fields:
        raise HTTPException(400, "Aucune donnée")
    vals.append(cid)
    exe(conn, f"UPDATE controles_qualite SET {','.join(fields)} WHERE id=%s", vals)
    return {"message": "Contrôle mis à jour"}


# ── NON-CONFORMITÉS ───────────────────────────────────────

@router.get("/nc")
def list_nc(conn=Depends(get_db), user=Depends(require_any_role)):
    rows = q(conn, """
        SELECT nc.*,
               cq.cq_numero,
               of_.numero AS of_numero,
               o.nom as responsable_nom, o.prenom as responsable_prenom
        FROM non_conformites nc
        LEFT JOIN controles_qualite cq ON cq.id = nc.cq_id
        LEFT JOIN ordres_fabrication of_ ON of_.id = nc.of_id
        LEFT JOIN operateurs o ON o.id = nc.responsable_id
        ORDER BY nc.created_at DESC
    """)
    return serialize(rows)


@router.post("/nc", status_code=201)
def create_nc(data: NCCreate, conn=Depends(get_db), user=Depends(require_any_role)):
    count = q(conn, "SELECT COUNT(*) as c FROM non_conformites", one=True)["c"]
    nc_num = f"NC-{date.today().year}-{count+1:04d}"
    nid = exe(conn, """
        INSERT INTO non_conformites
        (nc_numero,cq_id,of_id,type_defaut,description,gravite,statut,action_corrective,responsable_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (nc_num, data.cq_id, data.of_id, data.type_defaut, data.description,
          data.gravite, data.statut, data.action_corrective, data.responsable_id))
    return {"id": nid, "nc_numero": nc_num, "message": "Non-conformité créée"}


@router.put("/nc/{nid}")
def update_nc(nid: int, data: NCUpdate, conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    fields, vals = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s")
        vals.append(v)
    if not fields:
        raise HTTPException(400, "Aucune donnée")
    vals.append(nid)
    exe(conn, f"UPDATE non_conformites SET {','.join(fields)} WHERE id=%s", vals)
    return {"message": "NC mise à jour"}


# ── STATS QUALITÉ ─────────────────────────────────────────

@router.get("/stats")
def qualite_stats(conn=Depends(get_db), user=Depends(require_manager_or_admin)):
    total_cq = q(conn, "SELECT COUNT(*) as c FROM controles_qualite", one=True)["c"]
    conformes = q(conn, "SELECT COUNT(*) as c FROM controles_qualite WHERE statut='CONFORME'", one=True)["c"]
    nc_ouvertes = q(conn, "SELECT COUNT(*) as c FROM non_conformites WHERE statut='OUVERTE'", one=True)["c"]
    nc_critiques = q(conn, "SELECT COUNT(*) as c FROM non_conformites WHERE gravite='CRITIQUE' AND statut!='CLOTUREE'", one=True)["c"]
    taux_conformite = round((conformes / total_cq * 100), 1) if total_cq else 0
    nc_by_gravite = q(conn, "SELECT gravite, COUNT(*) as c FROM non_conformites GROUP BY gravite")
    return serialize({
        "total_controles": total_cq,
        "conformes": conformes,
        "taux_conformite": taux_conformite,
        "nc_ouvertes": nc_ouvertes,
        "nc_critiques": nc_critiques,
        "nc_by_gravite": nc_by_gravite
    })