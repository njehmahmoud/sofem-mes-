"""SOFEM MES v6.0 — Bons de Commande (patched)
Fixes:
  - Race condition in BC numbering: insert-first, id-based numero
  - N+1 in list_bc: bc_lignes batch-fetched in one query
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db, q, exe, serialize, temp_numero, finalize_number, cancel_document, log_activity
from auth import require_any_role, get_pdf_user, require_manager_or_admin, get_current_user
from models import BCCreate,CancelRequest
from datetime import datetime
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from routes.settings import get_all_settings

logger = logging.getLogger("sofem-bc")

router = APIRouter(prefix="/api/achats/bc", tags=["achats-bc"])


@router.get("", dependencies=[Depends(require_any_role)])
def list_bc(db=Depends(get_db)):
    from routes.settings import get_all_settings
    TVA_RATE = float(get_all_settings(db).get("tva_rate", 19))

    bcs = serialize(q(db, """
        SELECT bc.*, da.da_numero
        FROM bons_commande bc
        LEFT JOIN demandes_achat da ON bc.da_id = da.id
        ORDER BY bc.created_at DESC
    """))

    if not bcs:
        return bcs

    # ── Batch-fetch all lignes in ONE query (eliminates N+1) ──
    bc_ids = [bc["id"] for bc in bcs]
    placeholders = ",".join(["%s"] * len(bc_ids))
    all_lignes = serialize(q(db, f"""
        SELECT bcl.*, m.nom materiau_nom
        FROM bc_lignes bcl
        LEFT JOIN materiaux m ON bcl.materiau_id = m.id
        WHERE bcl.bc_id IN ({placeholders})
        ORDER BY bcl.bc_id, bcl.id
    """, bc_ids))

    lignes_by_bc: dict = {}
    for ligne in all_lignes:
        lignes_by_bc.setdefault(ligne["bc_id"], []).append(ligne)

    for bc in bcs:
        bc["lignes"] = lignes_by_bc.get(bc["id"], [])
        ht = sum(float(l["quantite"]) * float(l["prix_unitaire"]) for l in bc["lignes"])
        bc["montant_ht"]  = round(ht, 3)
        bc["montant_tva"] = round(ht * TVA_RATE / 100, 3)
        bc["montant_ttc"] = round(ht * (1 + TVA_RATE / 100), 3)

    return bcs


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_bc(data: BCCreate, db=Depends(get_db), user: dict = Depends(get_current_user)):
    year = datetime.now().year
    tmp = temp_numero()
    bc_id = exe(db, """
        INSERT INTO bons_commande (bc_numero, fournisseur, da_id, notes)
        VALUES (%s,%s,%s,%s)
    """, (tmp, data.fournisseur, data.da_id, data.notes))
    numero = finalize_number(db, "bons_commande", "bc_numero", bc_id, "BC", year)

    for l in data.lignes:
        exe(db, """
            INSERT INTO bc_lignes (bc_id, materiau_id, description, quantite, unite)
            VALUES (%s,%s,%s,%s,%s)
        """, (bc_id, l.materiau_id, l.description, l.quantite, l.unite))

    if data.da_id:
        exe(db, "UPDATE demandes_achat SET statut='ORDERED' WHERE id=%s", (data.da_id,))

    log_activity(db, "CREATE", "BC", bc_id, numero,
                 user.get("id"), f"{user.get('prenom','')} {user.get('nom','')}".strip(),
                 new_value=data.dict(), detail=f"BC {numero} créé")

    return {"id": bc_id, "bc_numero": numero, "message": "BC créé"}


@router.get("/{bc_id}", dependencies=[Depends(require_any_role)])
def get_bc(bc_id: int, db=Depends(get_db)):
    bc = q(db, "SELECT * FROM bons_commande WHERE id=%s", (bc_id,), one=True)
    if not bc:
        raise HTTPException(404, "BC non trouvé")
    bc = serialize(bc)
    bc["lignes"] = serialize(q(db, """
        SELECT bcl.*, m.nom materiau_nom
        FROM bc_lignes bcl LEFT JOIN materiaux m ON bcl.materiau_id = m.id
        WHERE bcl.bc_id = %s
    """, (bc_id,)))
    return bc



@router.put("/{bc_id}/statut", dependencies=[Depends(require_manager_or_admin)])
def update_bc_statut(bc_id: int, statut: str, db=Depends(get_db)):
    valid = ("DRAFT", "ENVOYE", "CONFIRME", "RECU", "ANNULE")
    if statut not in valid:
        raise HTTPException(400, f"Statut invalide. Valeurs: {', '.join(valid)}")
    bc = q(db, "SELECT id FROM bons_commande WHERE id=%s", (bc_id,), one=True)
    if not bc:
        raise HTTPException(404, "BC non trouvé")
    exe(db, "UPDATE bons_commande SET statut=%s WHERE id=%s", (statut, bc_id))
    return {"message": f"BC statut mis à jour → {statut}"}

@router.put("/{bc_id}", dependencies=[Depends(require_manager_or_admin)])
def update_bc(bc_id: int, data: dict, db=Depends(get_db)):
    bc = q(db, "SELECT id FROM bons_commande WHERE id=%s", (bc_id,), one=True)
    if not bc:
        raise HTTPException(404, "BC non trouvé")
    allowed = {"statut", "fournisseur", "notes"}
    fields, params = [], []
    for k, v in data.items():
        if k in allowed:
            fields.append(f"{k}=%s"); params.append(v)
    if not fields:
        raise HTTPException(400, "Aucun champ valide")
    params.append(bc_id)
    exe(db, f"UPDATE bons_commande SET {','.join(fields)} WHERE id=%s", params)
    return {"message": "BC mis à jour"}


@router.get("/{bc_id}/pdf")
def print_bc(bc_id: int, user=Depends(get_pdf_user), db=Depends(get_db)):
    bc = q(db, """
        SELECT bc.*, da.da_numero, da.of_id
        FROM bons_commande bc
        LEFT JOIN demandes_achat da ON bc.da_id = da.id
        WHERE bc.id = %s
    """, (bc_id,), one=True)
    if not bc:
        raise HTTPException(404, "BC non trouvé")
    bc = serialize(bc)
    bc["lignes"] = serialize(q(db, """
        SELECT bcl.*, m.nom materiau_nom, m.code materiau_code
        FROM bc_lignes bcl LEFT JOIN materiaux m ON bcl.materiau_id = m.id
        WHERE bcl.bc_id = %s ORDER BY bcl.id
    """, (bc_id,)))

    cfg = get_all_settings(db)
    S_NOM   = cfg.get("societe_nom",       "SOFEM")
    S_TAG   = cfg.get("societe_tagline",   "Partenaire des Briqueteries")
    S_ADDR  = cfg.get("societe_adresse",   "Route Sidi Salem 2.5KM")
    S_VILLE = cfg.get("societe_ville",     "Sfax")
    S_TEL   = cfg.get("societe_telephone", "+216 74 469 181")
    S_MF    = cfg.get("societe_mf",        "000000000/A/M/000")
    S_WEB   = cfg.get("societe_website",   "sofem-tn.com")
    PDF_PIED = cfg.get("pdf_pied_custom",  "SOFEM MES v6.0 · SMARTMOVE")
    TVA_RATE = float(cfg.get("tva_rate",   19)) / 100



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
    c.setFillColor(RED);  c.roundRect(15*2.835, H-32*2.835, 22*2.835, 22*2.835, 4, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 18); c.drawCentredString(26*2.835, H-24*2.835, "S")
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 20); c.drawString(42*2.835, H-22*2.835, S_NOM)
    c.setFillColor(RED);   c.setFont("Helvetica", 7);       c.drawString(42*2.835, H-27*2.835, S_TAG)
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 7)
    c.drawString(42*2.835, H-32*2.835, f"{S_ADDR} · {S_VILLE} · {S_TEL}")
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 26); c.drawRightString(W-15*2.835, H-20*2.835, "BON DE COMMANDE")
    c.setFillColor(RED);   c.setFont("Helvetica-Bold", 13); c.drawRightString(W-15*2.835, H-27*2.835, bc["bc_numero"])
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 8)
    c.drawRightString(W-15*2.835, H-33*2.835, f"Date: {now}")

    y = H - 63*mm
    c.setFillColor(LIGHT); c.rect(0, y, W, 18*mm, fill=1, stroke=0)
    c.setStrokeColor(BORDER); c.setLineWidth(0.5)
    c.line(0, y, W, y); c.line(0, y+18*mm, W, y+18*mm)
    c.setFillColor(GRAY); c.setFont("Helvetica-Bold", 7);  c.drawString(15*mm, y+14*mm, "FOURNISSEUR")
    c.setFillColor(DARK); c.setFont("Helvetica-Bold", 11); c.drawString(15*mm, y+8*mm, str(bc.get("fournisseur", "—"))[:40])
    c.setFillColor(GRAY); c.setFont("Helvetica", 8);       c.drawString(15*mm, y+3*mm, f"DA réf: {bc.get('da_numero', '—')}")
    c.setFillColor(GRAY); c.setFont("Helvetica-Bold", 7);  c.drawRightString(W-15*mm, y+14*mm, "STATUT")
    c.setFillColor(DARK); c.setFont("Helvetica-Bold", 11); c.drawRightString(W-15*mm, y+8*mm, bc.get("statut", "—"))

    y_cur = y - 14*mm
    cols = [15*mm, 95*mm, 130*mm, 155*mm, 180*mm]
    c.setFillColor(DARK); c.rect(15*mm, y_cur-6*mm, W-30*mm, 8*mm, fill=1, stroke=0)
    for i, h in enumerate(["DÉSIGNATION", "QTÉ", "UNITÉ", "PRIX HT", "TOTAL HT"]):
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 7); c.drawString(cols[i]+2*mm, y_cur-3*mm, h)
    y_cur -= 6*mm
    total_ht = 0
    for idx, l in enumerate(bc["lignes"]):
        rh = 8*mm; y_cur -= rh
        if idx % 2 == 0:
            c.setFillColor(LIGHT); c.rect(15*mm, y_cur, W-30*mm, rh, fill=1, stroke=0)
        ht_ligne = float(l["quantite"]) * float(l["prix_unitaire"])
        total_ht += ht_ligne
        c.setFillColor(DARK); c.setFont("Helvetica", 8)
        c.drawString(cols[0]+2*mm, y_cur+2.5*mm, str(l.get("description", ""))[:35])
        c.drawString(cols[1]+2*mm, y_cur+2.5*mm, str(float(l["quantite"])))
        c.drawString(cols[2]+2*mm, y_cur+2.5*mm, str(l.get("unite", "")))
        #c.drawString(cols[3]+2*mm, y_cur+2.5*mm, f"{float(l['prix_unitaire']):.3f}")
        #c.setFont("Helvetica-Bold", 8)
        #c.drawString(cols[4]+2*mm, y_cur+2.5*mm, f"{ht_ligne:.3f}")
        #c.setStrokeColor(BORDER); c.setLineWidth(0.3); c.line(15*mm, y_cur, W-15*mm, y_cur)

    #tva = round(total_ht * TVA_RATE, 3)
    #ttc = round(total_ht + tva, 3)
    #y_cur -= 12*mm; bx = W - 85*mm
    #for lbl, val, bg, fg in [
     #   ("Total HT", f"{total_ht:.3f} TND", LIGHT, DARK),
      #  (f"TVA ({round(TVA_RATE*100)}%)", f"{tva:.3f} TND", LIGHT, GRAY),
       # ("TOTAL TTC", f"{ttc:.3f} TND", DARK, WHITE),
    #]:
        #rh = 9*mm if lbl != "TOTAL TTC" else 11*mm
        #c.setFillColor(bg); c.rect(bx, y_cur-rh, W-15*mm-bx, rh, fill=1, stroke=0)
        #c.setFillColor(fg); c.setFont("Helvetica-Bold", 9 if lbl != "TOTAL TTC" else 11)
        #c.drawString(bx+3*mm, y_cur-rh+3*mm, lbl)
        #c.drawRightString(W-17*mm, y_cur-rh+3*mm, val)
        #c.setStrokeColor(BORDER); c.setLineWidth(0.4); c.line(bx, y_cur-rh, W-15*mm, y_cur-rh)
        #y_cur -= rh

    y_sig = y_cur - 16*mm
    c.setStrokeColor(BORDER); c.setLineWidth(0.5)
    c.roundRect(W-75*mm, y_sig-22*mm, 60*mm, 22*mm, 3, fill=0, stroke=1)
    c.setFillColor(GRAY); c.setFont("Helvetica", 8)
    c.drawCentredString(W-45*mm, y_sig-6*mm, "Signature & Cachet")
    c.line(W-70*mm, y_sig-18*mm, W-20*mm, y_sig-18*mm)

    c.setFillColor(DARK); c.rect(0, 0, W, 14*2.835, fill=1, stroke=0)
    c.setFillColor(RED);  c.rect(0, 14*2.835, W, 0.8*2.835, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 7)
    c.drawString(15*2.835, 9*2.835, f"{S_NOM} · {S_TAG}")
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 7)
    c.drawString(15*2.835, 5*2.835, f"{S_ADDR} · {S_VILLE} · {S_WEB} · MF: {S_MF}")
    c.drawRightString(W-15*2.835, 9*2.835, f"{bc['bc_numero']} · {now}")
    c.drawRightString(W-15*2.835, 5*2.835, PDF_PIED)

    c.save(); buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.read()),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="BC_{bc["bc_numero"]}.pdf"'},
    )


@router.put("/{bc_id}/cancel")
def cancel_bc(
        bc_id: int,
        data: CancelRequest,
        user=Depends(get_current_user),
        db=Depends(get_db)
):
    """
    ISO 9001 — Cancel a BC with mandatory reason.
    RECU BCs cannot be cancelled (goods already received).
    When BC is cancelled, linked DA goes back to APPROVED status.
    """
    bc = q(db, "SELECT * FROM bons_commande WHERE id=%s", (bc_id,), one=True)
    if not bc:
        raise HTTPException(404, "BC introuvable")
    if bc["statut"] in ("CANCELLED", "ANNULE"):
        raise HTTPException(400, "BC déjà annulé")
    if bc["statut"] == "RECU":
        raise HTTPException(400,
                            "Un BC entièrement reçu ne peut pas être annulé. "
                            "Effectuer un ajustement de stock si nécessaire.")

    user_id = user.get("id")
    user_nom = f"{user.get('prenom', '')} {user.get('nom', '')}".strip()

    warnings = []

    # Warn if already sent to supplier
    if bc["statut"] == "ENVOYE":
        warnings.append(
            f"⚠ Ce BC était déjà envoyé au fournisseur {bc.get('fournisseur', '')} — "
            f"contacter le fournisseur pour annuler la commande physiquement"
        )

    numero = cancel_document(
        db,
        table="bons_commande",
        id_col="id",
        numero_col="bc_numero",
        record_id=bc_id,
        user_id=user_id,
        user_nom=user_nom,
        reason=data.reason,
        entity_type="BC",
        old_statut=bc["statut"],
    )

    # Restore linked DA to APPROVED status so it can be re-ordered
    if bc.get("da_id"):
        da = q(db, "SELECT * FROM demandes_achat WHERE id=%s",
               (bc["da_id"],), one=True)
        if da and da["statut"] == "ORDERED":
            exe(db, """
                UPDATE demandes_achat
                SET statut='APPROVED'
                WHERE id=%s
            """, (bc["da_id"],))
            log_activity(
                db, "UPDATE", "DA", bc["da_id"], da.get("da_numero"),
                user_id, user_nom,
                old_value={"statut": "ORDERED"},
                new_value={"statut": "APPROVED"},
                detail=(f"DA {da.get('da_numero')} remise à APPROVED "
                        f"suite à annulation BC {numero}")
            )

    msg = f"BC {numero} annulé"
    if warnings:
        msg += f" · {len(warnings)} avertissement(s)"

    return {"message": msg, "numero": numero, "warnings": warnings}