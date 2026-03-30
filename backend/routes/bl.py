"""SOFEM MES v3.0 — Bon de Livraison Routes (patched)
Fix: race-free BL numbering using insert-first + id-based finalize.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db, q, exe, serialize, temp_numero, finalize_number, cancel_document, log_activity
from auth import require_any_role, get_pdf_user, require_manager_or_admin, get_current_user
from models import BLCreate, BLUpdate, BLLivrer, CancelRequest
from datetime import datetime
import io
from reportlab.lib.utils import ImageReader as _IR
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from routes.settings import get_all_settings

logger = logging.getLogger("sofem-bl")

router = APIRouter(prefix="/api/bl", tags=["bon-livraison"])


@router.get("", dependencies=[Depends(require_any_role)])
def list_bl(db=Depends(get_db)):
    return serialize(q(db, """
        SELECT bl.*, o.numero of_numero, o.statut of_statut,
               p.nom produit_nom, o.quantite,
               c.nom client_nom, c.matricule_fiscal client_mf
        FROM bons_livraison bl
        JOIN ordres_fabrication o ON bl.of_id = o.id
        JOIN produits p ON o.produit_id = p.id
        LEFT JOIN clients c ON c.id = o.client_id
        ORDER BY bl.created_at DESC
    """))


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_bl(data: BLCreate, db=Depends(get_db)):
    of = q(db, "SELECT id FROM ordres_fabrication WHERE id=%s", (data.of_id,), one=True)
    if not of:
        raise HTTPException(404, "OF non trouvé")
    existing = q(db, "SELECT id FROM bons_livraison WHERE of_id=%s", (data.of_id,), one=True)
    if existing:
        raise HTTPException(400, "Un BL existe déjà pour cet OF")

    year = datetime.now().year
    tmp = temp_numero()
    bl_id = exe(db, """
        INSERT INTO bons_livraison (bl_numero, of_id, date_livraison, destinataire, adresse, notes)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (tmp, data.of_id, data.date_livraison, data.destinataire, data.adresse, data.notes))
    numero = finalize_number(db, "bons_livraison", "bl_numero", bl_id, "BL", year)
    return {"id": bl_id, "bl_numero": numero, "message": "BL créé"}


@router.put("/{bl_id}", dependencies=[Depends(require_manager_or_admin)])
def update_bl(bl_id: int, data: BLUpdate, db=Depends(get_db)):
    fields, params = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s")
        params.append(v)
    if fields:
        params.append(bl_id)
        exe(db, f"UPDATE bons_livraison SET {','.join(fields)} WHERE id=%s", params)
    return {"message": "BL mis à jour"}


@router.put("/{bl_id}/livrer", dependencies=[Depends(require_manager_or_admin)])
def livrer_bl(bl_id: int, data: BLLivrer, db=Depends(get_db)):
    exe(db, """
        UPDATE bons_livraison SET
          statut='LIVRÉ',
          date_livraison=%s,
          destinataire_final=%s,
          adresse_finale=%s,
          notes=%s
        WHERE id=%s
    """, (data.date_livraison, data.destinataire, data.adresse, data.notes, bl_id))
    return {"message": "BL marqué livré"}


@router.get("/{bl_id}/pdf")
def print_bl(bl_id: int, token: str = None, user=Depends(get_pdf_user), db=Depends(get_db)):
    bl = q(db, """
        SELECT bl.*, o.numero of_numero, o.quantite, o.atelier, o.date_echeance,
               p.nom produit_nom, p.code produit_code,
               CONCAT(cp.prenom,' ',cp.nom) operateur_nom,
               c.nom client_nom, c.matricule_fiscal client_mf,
               c.adresse client_adresse, c.ville client_ville
        FROM bons_livraison bl
        JOIN ordres_fabrication o ON bl.of_id = o.id
        JOIN produits p ON o.produit_id = p.id
        LEFT JOIN operateurs cp ON o.chef_projet_id = cp.id
        LEFT JOIN clients c ON c.id = o.client_id
        WHERE bl.id = %s
    """, (bl_id,), one=True)
    if not bl:
        raise HTTPException(404, "BL non trouvé")
    bl = serialize(bl)


    cfg = get_all_settings(db)
    S_NOM  = cfg.get("societe_nom",       "SOFEM")
    S_TAG  = cfg.get("societe_tagline",   "Partenaire des Briqueteries")
    S_ADDR = cfg.get("societe_adresse",   "Route Sidi Salem 2.5KM")
    S_VILLE = cfg.get("societe_ville",    "Sfax")
    S_TEL  = cfg.get("societe_telephone", "+216 74 469 181")
    S_MF   = cfg.get("societe_mf",        "000000000/A/M/000")
    S_WEB  = cfg.get("societe_website",   "sofem-tn.com")
    PDF_PIED = cfg.get("pdf_pied_custom", "SOFEM MES v6.0 · SMARTMOVE")


    W, H = A4
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    RED   = colors.HexColor("#D42B2B")
    DARK  = colors.HexColor("#111")
    GRAY  = colors.HexColor("#6B7280")
    LIGHT = colors.HexColor("#F9FAFB")
    WHITE = colors.white
    BORDER = colors.HexColor("#E5E7EB")
    now = datetime.now().strftime("%d / %m / %Y")

    # Header
    c.setFillColor(DARK); c.rect(0, H-38*2.835, W, 38*2.835, fill=1, stroke=0)
    c.setFillColor(RED);  c.rect(0, H-40*2.835, W, 2*2.835, fill=1, stroke=0)
    # ── Company logo ──────────────────────────────────────
    import os as _os
    _logo_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "static", "logo.png")
    if _os.path.exists(_logo_path):
        c.drawImage(_IR(_logo_path), 12*2.835, H-33*2.835, 24*2.835, 24*2.835,
                    preserveAspectRatio=True, mask='auto')
    else:
        c.setFillColor(RED); c.roundRect(15*2.835, H-32*2.835, 22*2.835, 22*2.835, 4, fill=1, stroke=0)
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 18); c.drawCentredString(26*2.835, H-24*2.835, "S")
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 20); c.drawString(42*2.835, H-22*2.835, S_NOM)
    c.setFillColor(RED);   c.setFont("Helvetica", 7);       c.drawString(42*2.835, H-27*2.835, S_TAG)
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 7)
    c.drawString(42*2.835, H-32*2.835, f"{S_ADDR} · {S_VILLE} · {S_TEL}")
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 26); c.drawRightString(W-15*2.835, H-20*2.835, "BON DE LIVRAISON")
    c.setFillColor(RED);   c.setFont("Helvetica-Bold", 13); c.drawRightString(W-15*2.835, H-27*2.835, bl["bl_numero"])
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 8)
    c.drawRightString(W-15*2.835, H-33*2.835, f"Date: {now}")

    # Info band
    y = H - 63*mm
    c.setFillColor(LIGHT); c.rect(0, y, W, 22*mm, fill=1, stroke=0)
    c.setStrokeColor(BORDER); c.setLineWidth(0.5)
    c.line(0, y, W, y); c.line(0, y+22*mm, W, y+22*mm)

    def icol(lbl, val, sub, x):
        c.setFillColor(GRAY); c.setFont("Helvetica-Bold", 7);  c.drawString(x, y+18*mm, lbl.upper())
        c.setFillColor(DARK); c.setFont("Helvetica-Bold", 10); c.drawString(x, y+13*mm, str(val or "—")[:30])
        c.setFillColor(GRAY); c.setFont("Helvetica", 7.5)
        for i, line in enumerate(str(sub).split("\n")):
            c.drawString(x, y+8*mm-i*4*mm, line[:40])

    icol("OF", bl["of_numero"], f"Atelier: {bl.get('atelier','—')}\nÉchéance: {str(bl.get('date_echeance','—'))[:10]}", 15*mm)
    icol("Produit", bl["produit_nom"], f"Code: {bl.get('produit_code','—')}\nQté: {bl.get('quantite','—')}", 75*mm)
    icol("Destinataire", bl.get("destinataire","—"), bl.get("adresse","—"), 145*mm)

    # Items table
    y_cur = y - 15*mm
    c.setFillColor(RED); c.rect(15*mm, y_cur-0.5*mm, 3*mm, 5*mm, fill=1, stroke=0)
    c.setFillColor(DARK); c.setFont("Helvetica-Bold", 9); c.drawString(20*mm, y_cur, "DÉSIGNATION")
    y_cur -= 10*mm
    cols = [15*mm, 100*mm, 145*mm, 175*mm]
    c.setFillColor(DARK); c.rect(15*mm, y_cur-6*mm, W-30*mm, 8*mm, fill=1, stroke=0)
    for i, h in enumerate(["PRODUIT / DÉSIGNATION", "RÉFÉRENCE", "UNITÉ", "QUANTITÉ"]):
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 7); c.drawString(cols[i]+2*mm, y_cur-3*mm, h)
    y_cur -= 14*mm
    c.setFillColor(LIGHT); c.rect(15*mm, y_cur, W-30*mm, 8*mm, fill=1, stroke=0)
    c.setFillColor(DARK);  c.setFont("Helvetica", 8)
    c.drawString(cols[0]+2*mm, y_cur+2.5*mm, bl["produit_nom"][:40])
    c.drawString(cols[1]+2*mm, y_cur+2.5*mm, bl.get("produit_code", "—"))
    c.drawString(cols[2]+2*mm, y_cur+2.5*mm, "pcs")
    c.setFont("Helvetica-Bold", 8)
    c.drawString(cols[3]+2*mm, y_cur+2.5*mm, str(bl.get("quantite", "—")))
    c.setStrokeColor(BORDER); c.setLineWidth(0.3); c.line(15*mm, y_cur, W-15*mm, y_cur)

    # Signature
    y_sig = y_cur - 30*mm
    c.setStrokeColor(BORDER); c.setLineWidth(0.5)
    for label, sx in [("Expéditeur / SOFEM", 15*mm), ("Récepteur", W/2+5*mm)]:
        c.roundRect(sx, y_sig-28*mm, 85*mm, 28*mm, 3, fill=0, stroke=1)
        c.setFillColor(GRAY); c.setFont("Helvetica", 8)
        c.drawCentredString(sx+42.5*mm, y_sig-8*mm, label)
        c.line(sx+5*mm, y_sig-20*mm, sx+80*mm, y_sig-20*mm)

    # Footer
    c.setFillColor(DARK); c.rect(0, 0, W, 14*2.835, fill=1, stroke=0)
    c.setFillColor(RED);  c.rect(0, 14*2.835, W, 0.8*2.835, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 7)
    c.drawString(15*2.835, 9*2.835, f"{S_NOM} · {S_TAG}")
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 7)
    c.drawString(15*2.835, 5*2.835, f"{S_ADDR} · {S_VILLE} · {S_WEB} · MF: {S_MF}")
    c.drawRightString(W-15*2.835, 9*2.835, f"{bl['bl_numero']} · {now}")
    c.drawRightString(W-15*2.835, 5*2.835, PDF_PIED)

    c.save()
    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.read()),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="BL_{bl["bl_numero"]}.pdf"'},
    )


router.put("/{bl_id}/cancel")


def cancel_bl(
        bl_id: int,
        data: CancelRequest,
        user=Depends(get_current_user),
        db=Depends(get_db)
):
    """
    ISO 9001 — Cancel a BL with mandatory reason.
    Delivered BLs (LIVRE) cannot be cancelled.
    """
    bl = q(db, "SELECT * FROM bons_livraison WHERE id=%s", (bl_id,), one=True)
    if not bl:
        raise HTTPException(404, "BL introuvable")
    if bl["statut"] == "CANCELLED":
        raise HTTPException(400, "BL déjà annulé")
    if bl["statut"] == "LIVRE":
        raise HTTPException(400,
                            "Un BL déjà livré ne peut pas être annulé. "
                            "Créer une Non-Conformité si nécessaire.")

    user_id = user.get("id")
    user_nom = f"{user.get('prenom', '')} {user.get('nom', '')}".strip()

    numero = cancel_document(
        db,
        table="bons_livraison",
        id_col="id",
        numero_col="bl_numero",
        record_id=bl_id,
        user_id=user_id,
        user_nom=user_nom,
        reason=data.reason,
        entity_type="BL",
        old_statut=bl["statut"],
    )

    return {"message": f"BL {numero} annulé", "numero": numero}
