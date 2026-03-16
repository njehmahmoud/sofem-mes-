"""
SOFEM MES v2.0 — Main Entry Point
SMARTMOVE · Mahmoud Njeh
"""

import os
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import init_db
from routes.auth_routes import router as auth_router
from routes.dashboard   import router as dashboard_router
from routes.of          import router as of_router
from routes.materiaux   import router as materiaux_router
from routes.operateurs  import router as operateurs_router
from routes.produits    import router as produits_router
from routes.rapports    import router as rapports_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sofem-mes")

BASE_DIR     = Path(__file__).parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

# ── APP ───────────────────────────────────
app = FastAPI(
    title="SOFEM MES API v2.0",
    description="Manufacturing Execution System — SOFEM Sfax · SMARTMOVE",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DATABASE ──────────────────────────────
@app.on_event("startup")
def startup():
    init_db()
    if FRONTEND_DIR.exists():
        logger.info(f"✅ Frontend found at {FRONTEND_DIR}")
    else:
        logger.warning(f"⚠️ Frontend not found at {FRONTEND_DIR}")

# ── ROUTES ────────────────────────────────
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(of_router)
app.include_router(materiaux_router)
app.include_router(operateurs_router)
app.include_router(produits_router)
app.include_router(rapports_router)

# ── HEALTH ────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0.0"}

# ── FRONTEND ──────────────────────────────
@app.get("/admin", include_in_schema=False)
@app.get("/admin/", include_in_schema=False)
def admin():
    return FileResponse(str(FRONTEND_DIR / "admin" / "index.html"))

@app.get("/operator", include_in_schema=False)
@app.get("/operator/", include_in_schema=False)
def operator():
    return FileResponse(str(FRONTEND_DIR / "operator" / "index.html"))

@app.get("/", include_in_schema=False)
def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))

# Serve static assets
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")
