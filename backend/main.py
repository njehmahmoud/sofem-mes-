"""SOFEM MES v6.0 — Main Entry Point"""

import os, logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database import init_db

# ── OF module
from routes.of.of         import router as of_router
from routes.of.operations import router as of_ops_router
from routes.of.bom        import router as of_bom_router
from routes.of.fiche      import router as of_fiche_router

# ── Produits module
from routes.produits.produits import router as produits_router
from routes.produits.bom      import router as produits_bom_router

# ── Achats module
from routes.achats.da import router as da_router
from routes.achats.bc import router as bc_router
from routes.achats.br import router as br_router
from routes.achats.fa import router as fa_router

# ── Standalone routes
from routes.clients          import router as clients_router
from routes.operation_types  import router as op_types_router
from routes.settings          import router as settings_router
from routes.facture      import router as facture_router
from routes.operateurs   import router as operateurs_router
from routes.bl           import router as bl_router
from routes.materiaux    import router as materiaux_router
from routes.dashboard    import router as dashboard_router
from routes.rapports     import router as rapports_router
from routes.auth_routes  import router as auth_router
from routes.machines     import router as machines_router
from routes.maintenance  import router as maintenance_router
from routes.planification import router as planification_router
from routes.qualite      import router as qualite_router
from routes.fournisseurs import router as fournisseurs_router
from routes.analytics    import router as analytics_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sofem-mes")

BASE_DIR     = Path(__file__).parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="SOFEM MES API v6.0", version="6.0.0",
              description="Manufacturing Execution System — SOFEM Sfax · SMARTMOVE")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    init_db()
    logger.info(f"✅ Frontend: {FRONTEND_DIR}")

# ── Register all routers ──────────────────────────────────
app.include_router(auth_router)
app.include_router(dashboard_router)

# OF module
app.include_router(of_router)
app.include_router(of_ops_router)
app.include_router(of_bom_router)
app.include_router(of_fiche_router)

# Produits module
app.include_router(produits_router)
app.include_router(produits_bom_router)

# Achats module
app.include_router(da_router)
app.include_router(bc_router)
app.include_router(br_router)
app.include_router(fa_router)

# Standalone
app.include_router(clients_router)
app.include_router(op_types_router)
app.include_router(settings_router)
app.include_router(facture_router)
app.include_router(operateurs_router)
app.include_router(bl_router)
app.include_router(materiaux_router)
app.include_router(rapports_router)
app.include_router(machines_router)
app.include_router(maintenance_router)
app.include_router(planification_router)
app.include_router(qualite_router)
app.include_router(fournisseurs_router)
app.include_router(analytics_router)

# ── Health ───────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "version": "6.0.0"}

# ── Frontend ─────────────────────────────────────────────
@app.get("/admin",    include_in_schema=False)
@app.get("/admin/",   include_in_schema=False)
def admin():
    return FileResponse(str(FRONTEND_DIR / "admin" / "index.html"))

@app.get("/operator",  include_in_schema=False)
@app.get("/operator/", include_in_schema=False)
def operator():
    return FileResponse(str(FRONTEND_DIR / "operator" / "index.html"))

@app.get("/", include_in_schema=False)
def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))

assets_dir = FRONTEND_DIR / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

# Serve admin JS files
admin_js = FRONTEND_DIR / "admin" / "js"
if admin_js.exists():
    app.mount("/admin/js", StaticFiles(directory=str(admin_js)), name="admin-js")
    app.mount("/js",       StaticFiles(directory=str(admin_js)), name="js-root")

admin_css = FRONTEND_DIR / "admin" / "css"
if admin_css.exists():
    app.mount("/admin/css", StaticFiles(directory=str(admin_css)), name="admin-css")
    app.mount("/css",       StaticFiles(directory=str(admin_css)), name="css-root")