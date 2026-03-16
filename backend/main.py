"""
SOFEM MES — Backend API v1.0 (Cloud Edition)
Hosted on Railway — SMARTMOVE · Mahmoud Njeh
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import mysql.connector
from mysql.connector import pooling, Error
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
import os
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sofem-mes")

# Absolute paths — works regardless of where Railway runs from
BASE_DIR     = Path(__file__).parent.parent  # sofem-cloud/
FRONTEND_DIR = BASE_DIR / "frontend"

# ─────────────────────────────────────────
# DATABASE — reads from Railway env vars
# ─────────────────────────────────────────
DB_CONFIG = {
    "host":     os.environ.get("MYSQLHOST",     "localhost"),
    "port":     int(os.environ.get("MYSQLPORT", "3306")),
    "user":     os.environ.get("MYSQLUSER",     "root"),
    "password": os.environ.get("MYSQLPASSWORD", ""),
    "database": os.environ.get("MYSQLDATABASE", "sofem_mes"),
    "charset":  "utf8mb4",
}

try:
    pool = pooling.MySQLConnectionPool(pool_name="sofem_pool", pool_size=5, **DB_CONFIG)
    logger.info("✅ MySQL connected")
except Error as e:
    logger.error(f"❌ MySQL error: {e}")
    pool = None

# ─────────────────────────────────────────
# APP
# ─────────────────────────────────────────
app = FastAPI(title="SOFEM MES API v1.0", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    logger.info(f"✅ Frontend found at {FRONTEND_DIR}")
else:
    logger.warning(f"⚠️ Frontend not found at {FRONTEND_DIR}")

# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def get_db():
    if not pool:
        raise HTTPException(503, "Database not available")
    conn = pool.get_connection()
    try:
        yield conn
    finally:
        conn.close()

def q(conn, sql, params=None, one=False):
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params or ())
    return cur.fetchone() if one else cur.fetchall()

def exe(conn, sql, params=None):
    cur = conn.cursor()
    cur.execute(sql, params or ())
    conn.commit()
    return cur.lastrowid

def s(obj):
    if isinstance(obj, dict):  return {k: s(v) for k, v in obj.items()}
    if isinstance(obj, list):  return [s(i) for i in obj]
    if isinstance(obj, (datetime, date)): return str(obj)
    return obj

# ─────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────
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

class EtapeUpdate(BaseModel):
    statut: str
    operateur_id: Optional[int] = None
    notes: Optional[str] = None

class MouvementCreate(BaseModel):
    materiau_id: int
    of_id: Optional[int] = None
    type: str
    quantite: float
    motif: Optional[str] = None

class OperateurCreate(BaseModel):
    nom: str
    prenom: str
    specialite: str
    telephone: Optional[str] = None
    email: Optional[str] = None

class MateriauCreate(BaseModel):
    code: str
    nom: str
    unite: str
    stock_actuel: float = 0
    stock_minimum: float = 0
    fournisseur: Optional[str] = None

class ProduitCreate(BaseModel):
    code: str
    nom: str
    description: Optional[str] = None
    unite: str = "pcs"

# ─────────────────────────────────────────
# FRONTEND
# ─────────────────────────────────────────
@app.get("/", include_in_schema=False)
def root():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "SOFEM MES API v1.0 — frontend not found"}

@app.get("/api/health")
def health(db=Depends(get_db)):
    r = q(db, "SELECT COUNT(*) n FROM ordres_fabrication", one=True)
    return {"status": "ok", "version": "1.0.0", "total_ofs": r["n"]}

# ─────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────
@app.get("/api/dashboard")
def dashboard(db=Depends(get_db)):
    actifs   = q(db, "SELECT COUNT(*) n FROM ordres_fabrication WHERE statut IN ('DRAFT','APPROVED','IN_PROGRESS')", one=True)["n"]
    urgents  = q(db, "SELECT COUNT(*) n FROM ordres_fabrication WHERE priorite='URGENT' AND statut NOT IN ('COMPLETED','CANCELLED')", one=True)["n"]
    total_m  = q(db, "SELECT COUNT(*) n FROM ordres_fabrication WHERE MONTH(created_at)=MONTH(NOW()) AND YEAR(created_at)=YEAR(NOW())", one=True)["n"]
    comp_m   = q(db, "SELECT COUNT(*) n FROM ordres_fabrication WHERE statut='COMPLETED' AND MONTH(created_at)=MONTH(NOW()) AND YEAR(created_at)=YEAR(NOW())", one=True)["n"]
    al_stock = q(db, "SELECT COUNT(*) n FROM materiaux WHERE stock_actuel < stock_minimum", one=True)["n"]
    retard   = q(db, "SELECT COUNT(*) n FROM ordres_fabrication WHERE date_echeance < CURDATE() AND statut NOT IN ('COMPLETED','CANCELLED')", one=True)["n"]
    taux     = round(comp_m / total_m * 100, 1) if total_m > 0 else 0
    graphique = q(db, """
        SELECT DATE_FORMAT(created_at,'%b %Y') mois, COUNT(*) total
        FROM ordres_fabrication
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY YEAR(created_at), MONTH(created_at)
        ORDER BY YEAR(created_at), MONTH(created_at)
    """)
    return s({"ordres_actifs": actifs, "urgents": urgents, "taux_completion": taux,
              "alertes_stock": al_stock, "en_retard": retard, "graphique": graphique})

# ─────────────────────────────────────────
# ORDRES DE FABRICATION
# ─────────────────────────────────────────
@app.get("/api/of")
def list_of(statut: Optional[str] = None, priorite: Optional[str] = None, limit: int = 100, db=Depends(get_db)):
    sql = """SELECT o.*, p.nom produit_nom, p.code produit_code,
             CONCAT(op.prenom,' ',op.nom) operateur_nom
             FROM ordres_fabrication o
             JOIN produits p ON o.produit_id=p.id
             LEFT JOIN operateurs op ON o.operateur_id=op.id WHERE 1=1"""
    params = []
    if statut:   sql += " AND o.statut=%s";   params.append(statut)
    if priorite: sql += " AND o.priorite=%s"; params.append(priorite)
    sql += f" ORDER BY o.created_at DESC LIMIT {int(limit)}"
    ofs = q(db, sql, params)
    for of in ofs:
        of["etapes"] = q(db, """SELECT e.*, CONCAT(op.prenom,' ',op.nom) operateur_nom
            FROM etapes_production e LEFT JOIN operateurs op ON e.operateur_id=op.id
            WHERE e.of_id=%s ORDER BY FIELD(e.etape,'AutoCAD','Découpage','Pliage','Soudage','Ponçage')""", (of["id"],))
    return s(ofs)

@app.post("/api/of", status_code=201)
def create_of(data: OFCreate, db=Depends(get_db)):
    last = q(db, "SELECT numero FROM ordres_fabrication ORDER BY id DESC LIMIT 1", one=True)
    year = datetime.now().year
    num = (int(last["numero"].split("-")[-1]) + 1) if last else 1
    numero = f"OF-{year}-{str(num).zfill(3)}"
    of_id = exe(db, """INSERT INTO ordres_fabrication
        (numero,produit_id,quantite,priorite,statut,operateur_id,atelier,date_echeance,notes)
        VALUES (%s,%s,%s,%s,'DRAFT',%s,%s,%s,%s)""",
        (numero, data.produit_id, data.quantite, data.priorite,
         data.operateur_id, data.atelier, data.date_echeance, data.notes))
    for etape in ['AutoCAD','Découpage','Pliage','Soudage','Ponçage']:
        exe(db, "INSERT INTO etapes_production (of_id,etape,statut) VALUES (%s,%s,'PENDING')", (of_id, etape))
    return {"id": of_id, "numero": numero, "message": "OF créé"}

@app.put("/api/of/{of_id}")
def update_of(of_id: int, data: OFUpdate, db=Depends(get_db)):
    fields, params = [], []
    if data.statut      is not None: fields.append("statut=%s");      params.append(data.statut)
    if data.priorite    is not None: fields.append("priorite=%s");    params.append(data.priorite)
    if data.operateur_id is not None: fields.append("operateur_id=%s"); params.append(data.operateur_id)
    if data.atelier     is not None: fields.append("atelier=%s");     params.append(data.atelier)
    if data.notes       is not None: fields.append("notes=%s");       params.append(data.notes)
    if fields:
        params.append(of_id)
        exe(db, f"UPDATE ordres_fabrication SET {','.join(fields)} WHERE id=%s", params)
    return {"message": "OF mis à jour"}

@app.delete("/api/of/{of_id}")
def cancel_of(of_id: int, db=Depends(get_db)):
    exe(db, "UPDATE ordres_fabrication SET statut='CANCELLED' WHERE id=%s", (of_id,))
    return {"message": "OF annulé"}

# ─────────────────────────────────────────
# ETAPES
# ─────────────────────────────────────────
@app.put("/api/of/{of_id}/etape/{etape_nom}")
def update_etape(of_id: int, etape_nom: str, data: EtapeUpdate, db=Depends(get_db)):
    etape = q(db, "SELECT id FROM etapes_production WHERE of_id=%s AND etape=%s", (of_id, etape_nom), one=True)
    if not etape: raise HTTPException(404, "Étape non trouvée")
    exe(db, """UPDATE etapes_production SET statut=%s, operateur_id=%s, notes=%s,
        debut=CASE WHEN statut='PENDING' AND %s='IN_PROGRESS' THEN NOW() ELSE debut END,
        fin=CASE WHEN %s='COMPLETED' THEN NOW() ELSE fin END
        WHERE of_id=%s AND etape=%s""",
        (data.statut, data.operateur_id, data.notes, data.statut, data.statut, of_id, etape_nom))
    etapes = q(db, "SELECT statut FROM etapes_production WHERE of_id=%s", (of_id,))
    statuts = [e["statut"] for e in etapes]
    if all(s == "COMPLETED" for s in statuts):
        exe(db, "UPDATE ordres_fabrication SET statut='COMPLETED' WHERE id=%s", (of_id,))
    elif any(s == "IN_PROGRESS" for s in statuts):
        exe(db, "UPDATE ordres_fabrication SET statut='IN_PROGRESS' WHERE id=%s", (of_id,))
    return {"message": f"{etape_nom} → {data.statut}"}

# ─────────────────────────────────────────
# MATERIAUX
# ─────────────────────────────────────────
@app.get("/api/materiaux")
def list_materiaux(db=Depends(get_db)):
    return s(q(db, """SELECT *, (stock_actuel < stock_minimum) alerte,
        ROUND(CASE WHEN stock_minimum>0 THEN stock_actuel/stock_minimum*100 ELSE 100 END,0) pct_stock
        FROM materiaux ORDER BY nom"""))

@app.post("/api/materiaux", status_code=201)
def create_materiau(data: MateriauCreate, db=Depends(get_db)):
    mid = exe(db, "INSERT INTO materiaux (code,nom,unite,stock_actuel,stock_minimum,fournisseur) VALUES (%s,%s,%s,%s,%s,%s)",
              (data.code, data.nom, data.unite, data.stock_actuel, data.stock_minimum, data.fournisseur))
    return {"id": mid, "message": "Matériau créé"}

@app.post("/api/materiaux/mouvement")
def mouvement_stock(data: MouvementCreate, db=Depends(get_db)):
    mat = q(db, "SELECT stock_actuel FROM materiaux WHERE id=%s", (data.materiau_id,), one=True)
    if not mat: raise HTTPException(404, "Matériau non trouvé")
    avant = float(mat["stock_actuel"])
    apres = avant + data.quantite if data.type=="ENTREE" else avant - data.quantite if data.type=="SORTIE" else data.quantite
    if apres < 0: raise HTTPException(400, f"Stock insuffisant (disponible: {avant})")
    exe(db, "UPDATE materiaux SET stock_actuel=%s WHERE id=%s", (apres, data.materiau_id))
    exe(db, "INSERT INTO mouvements_stock (materiau_id,of_id,type,quantite,stock_avant,stock_apres,motif) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (data.materiau_id, data.of_id, data.type, data.quantite, avant, apres, data.motif))
    return {"message": "Mouvement enregistré", "stock_avant": avant, "stock_apres": apres}

@app.get("/api/materiaux/mouvements")
def historique(limit: int = 50, db=Depends(get_db)):
    return s(q(db, """SELECT ms.*, m.nom materiau_nom, m.unite, o.numero of_numero
        FROM mouvements_stock ms JOIN materiaux m ON ms.materiau_id=m.id
        LEFT JOIN ordres_fabrication o ON ms.of_id=o.id
        ORDER BY ms.created_at DESC LIMIT %s""", (limit,)))

# ─────────────────────────────────────────
# OPERATEURS
# ─────────────────────────────────────────
@app.get("/api/operateurs")
def list_operateurs(db=Depends(get_db)):
    ops = q(db, """SELECT o.*, COUNT(DISTINCT of2.id) total_ofs,
        SUM(of2.statut='COMPLETED') ofs_completes
        FROM operateurs o LEFT JOIN ordres_fabrication of2 ON o.id=of2.operateur_id
        WHERE o.actif=TRUE GROUP BY o.id ORDER BY o.nom""")
    for op in ops:
        t = op["total_ofs"] or 0
        op["performance"] = round((op["ofs_completes"] or 0) / t * 100, 1) if t > 0 else 0
    return s(ops)

@app.post("/api/operateurs", status_code=201)
def create_operateur(data: OperateurCreate, db=Depends(get_db)):
    oid = exe(db, "INSERT INTO operateurs (nom,prenom,specialite,telephone,email) VALUES (%s,%s,%s,%s,%s)",
              (data.nom, data.prenom, data.specialite, data.telephone, data.email))
    return {"id": oid, "message": "Opérateur créé"}

# ─────────────────────────────────────────
# PRODUITS
# ─────────────────────────────────────────
@app.get("/api/produits")
def list_produits(db=Depends(get_db)):
    return s(q(db, "SELECT * FROM produits ORDER BY nom"))

@app.post("/api/produits", status_code=201)
def create_produit(data: ProduitCreate, db=Depends(get_db)):
    pid = exe(db, "INSERT INTO produits (code,nom,description,unite) VALUES (%s,%s,%s,%s)",
              (data.code, data.nom, data.description, data.unite))
    return {"id": pid, "message": "Produit créé"}

# ─────────────────────────────────────────
# RAPPORTS
# ─────────────────────────────────────────
@app.get("/api/rapports/production-mensuelle")
def rapport_mensuel(db=Depends(get_db)):
    return s(q(db, """SELECT DATE_FORMAT(created_at,'%Y-%m') mois, COUNT(*) total,
        SUM(statut='COMPLETED') completes FROM ordres_fabrication
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
        GROUP BY DATE_FORMAT(created_at,'%Y-%m') ORDER BY mois"""))

@app.get("/api/rapports/operateurs")
def rapport_operateurs(db=Depends(get_db)):
    return s(q(db, """SELECT CONCAT(o.prenom,' ',o.nom) operateur, o.specialite,
        COUNT(DISTINCT ep.of_id) total_ofs, SUM(ep.statut='COMPLETED') etapes_completes,
        ROUND(AVG(TIMESTAMPDIFF(MINUTE,ep.debut,ep.fin)),0) duree_moy_min
        FROM operateurs o LEFT JOIN etapes_production ep ON o.id=ep.operateur_id
        WHERE o.actif=TRUE GROUP BY o.id ORDER BY etapes_completes DESC"""))

@app.get("/api/rapports/stock-alertes")
def rapport_stock(db=Depends(get_db)):
    return s(q(db, """SELECT *, ROUND(stock_actuel/stock_minimum*100,0) pct
        FROM materiaux WHERE stock_actuel < stock_minimum
        ORDER BY (stock_actuel/stock_minimum) ASC"""))

# ─────────────────────────────────────────
# START
# ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
