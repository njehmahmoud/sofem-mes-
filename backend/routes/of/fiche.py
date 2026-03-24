"""SOFEM MES v6.0 — Fiche Résumé Production PDF (ENR-PRD-02)"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db, q, serialize
from auth import require_any_role, get_pdf_user
from datetime import datetime
import io

router = APIRouter(prefix="/api/of", tags=["fiche"])


@router.get("/{of_id}/fiche")
def generate_fiche(of_id: int, token: str=None, user=Depends(get_pdf_user), db=Depends(get_db)):
    of = q(db, """
        SELECT o.*, p.nom produit_nom, p.code produit_code,
               p.prix_vente_ht,
               CONCAT(cp.prenom,' ',cp.nom) chef_projet_nom,
               c.nom client_nom, c.matricule_fiscal client_mf,
               bl.bl_numero
        FROM ordres_fabrication o
        JOIN produits p ON o.produit_id = p.id
        LEFT JOIN operateurs cp ON cp.id = o.chef_projet_id
        LEFT JOIN clients c ON c.id = o.client_id
        LEFT JOIN bons_livraison bl ON bl.of_id = o.id
        WHERE o.id = %s
    """, (of_id,), one=True)
    if not of: raise HTTPException(404, "OF non trouvé")
    if of["statut"] != "COMPLETED":
        raise HTTPException(400, "Fiche disponible uniquement pour les OFs terminés")

    ops = q(db, """
        SELECT op.*, m.nom machine_nom,
               GROUP_CONCAT(DISTINCT CONCAT(o2.prenom,' ',o2.nom) SEPARATOR ', ') operateurs_noms,
               GROUP_CONCAT(DISTINCT o2.taux_horaire SEPARATOR ',') taux_horaires,
               GROUP_CONCAT(DISTINCT o2.taux_piece SEPARATOR ',') taux_pieces,
               GROUP_CONCAT(DISTINCT o2.type_taux SEPARATOR ',') types_taux
        FROM of_operations op
        LEFT JOIN machines m ON m.id = op.machine_id
        LEFT JOIN op_operateurs oo ON oo.operation_id = op.id
        LEFT JOIN operateurs o2 ON o2.id = oo.operateur_id
        WHERE op.of_id = %s
        GROUP BY op.id ORDER BY op.ordre, op.id
    """, (of_id,))

    bom = q(db, """
        SELECT ob.*, m.nom materiau_nom, m.code materiau_code,
               m.unite, m.prix_unitaire
        FROM of_bom ob JOIN materiaux m ON m.id = ob.materiau_id
        WHERE ob.of_id = %s
    """, (of_id,))

    of = serialize(of); ops = serialize(ops); bom = serialize(bom)
    # Load settings
    from routes.settings import get_all_settings
    cfg = get_all_settings(db)
    S_NOM    = cfg.get("societe_nom",       "sofem")
    S_TAG    = cfg.get("societe_tagline",   "Société de Fabrication Électromécanique & de Maintenance")
    S_ADDR   = cfg.get("societe_adresse",   "Route Sidi Salem 2.5KM")
    S_VILLE  = cfg.get("societe_ville",     "Sfax")
    S_TEL    = cfg.get("societe_telephone", "+216 74 469 181")
    S_EMAIL  = cfg.get("societe_email",     "contact@sofem-tn.com")
    S_MF     = cfg.get("societe_mf",        "000000000/A/M/000")
    S_WEB    = cfg.get("societe_website",   "sofem-tn.com")
    TVA_RATE = float(cfg.get("tva_rate",    19)) / 100
    PDF_REV  = cfg.get("pdf_rev",           "00")
    PDF_PIED = cfg.get("pdf_pied_custom",   "PDF_PIED")

    qte = int(of.get("quantite", 1))

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.platypus import Table, TableStyle

    W, H = A4
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)

    RED   = colors.HexColor("#D42B2B")
    DARK  = colors.HexColor("#111111")
    GRAY  = colors.HexColor("#6B7280")
    LIGHT = colors.HexColor("#F5F5F5")
    WHITE = colors.white
    BORDER = colors.HexColor("#CCCCCC")
    now = datetime.now().strftime("%d/%m/%Y")

    # ── HEADER ──────────────────────────────────────────
    c.setFillColor(DARK); c.rect(0, H-35*mm, W, 35*mm, fill=1, stroke=0)
    c.setFillColor(RED);  c.rect(0, H-37*mm, W, 2*mm, fill=1, stroke=0)
    # Logo box
    import os as _os
    _logo_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "static", "logo.png")
    if _os.path.exists(_logo_path):
        from reportlab.lib.utils import ImageReader as _IR
        c.drawImage(_IR(_logo_path), 10*mm, H-31*mm, 22*mm, 22*mm,
                    preserveAspectRatio=True, mask='auto')
    else:
        c.setFillColor(RED); c.roundRect(12*mm, H-30*mm, 20*mm, 20*mm, 3, fill=1, stroke=0)
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(22*mm, H-22*mm, "S")
    # Company name
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 18)
    c.drawString(36*mm, H-20*mm, S_NOM)
    c.setFillColor(RED); c.setFont("Helvetica", 7)
    c.drawString(36*mm, H-25*mm, S_TAG.upper()[:55])
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 6.5)
    c.drawString(36*mm, H-29*mm, f"{S_ADDR} · {S_VILLE} · {S_TEL}")
    # Title right
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 16)
    c.drawRightString(W-12*mm, H-20*mm, "FICHE DE RÉSUMÉ PRODUCTION")
    c.setFillColor(RED); c.setFont("Helvetica-Bold", 10)
    c.drawRightString(W-12*mm, H-26*mm, "ENR-PRD-02")
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 8)
    c.drawRightString(W-12*mm, H-30*mm, f"Rév. {PDF_REV}  ·  Date: {now}  ·  Page 1/1")

    # ── INFO BAND — 2 rows × 4 cols ────────────────────
    ROW_H  = 14*mm
    BAND_H = ROW_H * 2
    BX     = 12*mm
    BW     = W - 24*mm
    y      = H - 40*mm          # top of band

    # Draw band background + outer border
    c.setFillColor(LIGHT)
    c.rect(BX, y - BAND_H, BW, BAND_H, fill=1, stroke=0)
    c.setStrokeColor(BORDER); c.setLineWidth(0.5)
    c.rect(BX, y - BAND_H, BW, BAND_H, fill=0, stroke=1)
    # Horizontal divider between rows
    c.line(BX, y - ROW_H, BX + BW, y - ROW_H)

    col_x = [14*mm, 62*mm, 117*mm, 162*mm]

    def info_cell(label, value, x, row):
        y_lbl = y - row * ROW_H - 3.5*mm
        y_val = y - row * ROW_H - 10*mm
        c.setFillColor(GRAY); c.setFont("Helvetica-Bold", 6)
        c.drawString(x, y_lbl, label.upper())
        c.setFillColor(DARK); c.setFont("Helvetica-Bold", 9)
        c.drawString(x, y_val, str(value or "—")[:28])

    # Row 0 — top
    info_cell("OF N°",       of["numero"],                         col_x[0], 0)
    info_cell("Produit",     of["produit_nom"],                    col_x[1], 0)
    info_cell("Client",      of.get("client_nom") or "—",         col_x[2], 0)
    info_cell("Plan N°",     of.get("plan_numero") or "—",        col_x[3], 0)
    # Row 1 — bottom
    info_cell("Quantité",    str(of["quantite"]),                  col_x[0], 1)
    info_cell("Chef Atelier",of.get("chef_projet_nom") or "—",    col_x[1], 1)
    info_cell("MF Client",   of.get("client_mf") or "—",          col_x[2], 1)
    info_cell("Date Éch.",   str(of.get("date_echeance") or now)[:10], col_x[3], 1)

    # Vertical dividers
    c.setLineWidth(0.3)
    for cx in col_x[1:]:
        c.line(cx - 2*mm, y - BAND_H, cx - 2*mm, y)

    y_cur = y - BAND_H - 8*mm

    # ── OPERATIONS TABLE ────────────────────────────────
    c.setFillColor(DARK); c.setFont("Helvetica-Bold", 9)
    c.drawString(12*mm, y_cur+2*mm, "DÉTAIL DES OPÉRATIONS")

    y_cur -= 6*mm
    # Header row
    cols_x = [12, 42, 82, 112, 137, 157, 182]  # mm
    cols_w = [30, 40, 30, 25,  20,  25,  18]
    headers = ["OPÉRATION","OPÉRATEUR","MACHINE","NB H/PÈC","QTÉ","TOTAL H","COÛT DT"]
    c.setFillColor(DARK); c.rect(12*mm, y_cur-5*mm, W-24*mm, 7*mm, fill=1, stroke=0)
    for i, h in enumerate(headers):
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 7)
        c.drawString(cols_x[i]*mm+1*mm, y_cur-2*mm, h)
    y_cur -= 12*mm

    total_mo_cost = 0  # main d'oeuvre
    for idx, op in enumerate(ops):
        dur = op.get("duree_reelle") or 0  # minutes
        dur_h = dur / 60
        mult = 1 if "autocad" in op["operation_nom"].lower() else qte
        total_h = dur_h * mult
        cost = 0
        try:
            th = float((op.get("taux_horaires") or "0").split(",")[0])
            tp = float((op.get("taux_pieces") or "0").split(",")[0])
            tt = (op.get("types_taux") or "HORAIRE").split(",")[0]
            if tt == "HORAIRE": cost = total_h * th
            elif tt == "PIECE":  cost = mult * tp
            else: cost = total_h * th + mult * tp
        except: pass
        total_mo_cost += cost

        bg = LIGHT if idx % 2 == 0 else WHITE
        c.setFillColor(bg); c.rect(12*mm, y_cur-4*mm, W-24*mm, 6*mm, fill=1, stroke=0)
        c.setStrokeColor(BORDER); c.setLineWidth(0.3)
        c.rect(12*mm, y_cur-4*mm, W-24*mm, 6*mm, fill=0, stroke=1)
        c.setFillColor(DARK); c.setFont("Helvetica", 8)
        vals = [
            op["operation_nom"],
            (op.get("operateurs_noms") or "—")[:28],
            (op.get("machine_nom") or "—")[:20],
            f"{dur}min/p" if dur else "—",
            str(mult),
            f"{total_h:.2f}h" if dur else "—",
            f"{cost:.3f}" if cost else "—"
        ]
        for i, v in enumerate(vals):
            c.drawString(cols_x[i]*mm+1*mm, y_cur-1*mm, str(v))
        y_cur -= 7*mm

        if y_cur < 60*mm:
            c.showPage(); y_cur = H - 20*mm

    # ── BOM / MATIÈRES ──────────────────────────────────
    y_cur -= 4*mm
    c.setFillColor(DARK); c.setFont("Helvetica-Bold", 9)
    c.drawString(12*mm, y_cur+2*mm, "MATIÈRES CONSOMMÉES")
    y_cur -= 6*mm
    mat_headers = ["DÉSIGNATION","CODE","QUANTITÉ","UNITÉ","PRIX UNIT.","TOTAL DT"]
    mat_x = [12, 72, 112, 137, 155, 175]
    c.setFillColor(DARK); c.rect(12*mm, y_cur-5*mm, W-24*mm, 7*mm, fill=1, stroke=0)
    for i, h in enumerate(mat_headers):
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 7)
        c.drawString(mat_x[i]*mm+1*mm, y_cur-2*mm, h)
    y_cur -= 12*mm
    total_mat_cost = 0
    for idx, b in enumerate(bom):
        pu = float(b.get("prix_unitaire") or 0)
        qr = float(b.get("quantite_requise") or 0)
        mat_cost = pu * qr
        total_mat_cost += mat_cost
        bg = LIGHT if idx % 2 == 0 else WHITE
        c.setFillColor(bg); c.rect(12*mm, y_cur-4*mm, W-24*mm, 6*mm, fill=1, stroke=0)
        c.setStrokeColor(BORDER); c.rect(12*mm, y_cur-4*mm, W-24*mm, 6*mm, fill=0, stroke=1)
        c.setFillColor(DARK); c.setFont("Helvetica", 8)
        vals = [b["materiau_nom"], b["materiau_code"],
                str(b["quantite_requise"]), b["unite"],
                f"{pu:.3f}", f"{mat_cost:.3f}"]
        for i, v in enumerate(vals):
            c.drawString(mat_x[i]*mm+1*mm, y_cur-1*mm, str(v))
        y_cur -= 7*mm

    # ── SOUS-TRAITANCE ───────────────────────────────────
    if of.get("sous_traitant"):
        y_cur -= 4*mm
        c.setFillColor(LIGHT); c.rect(12*mm, y_cur-10*mm, W-24*mm, 12*mm, fill=1, stroke=0)
        c.setStrokeColor(BORDER); c.rect(12*mm, y_cur-10*mm, W-24*mm, 12*mm, fill=0, stroke=1)
        c.setFillColor(DARK); c.setFont("Helvetica-Bold", 8)
        c.drawString(14*mm, y_cur-2*mm, "SOUS-TRAITANCE:")
        c.setFont("Helvetica", 8)
        c.drawString(14*mm, y_cur-7*mm,
            f"{of['sous_traitant']} · {of.get('sous_traitant_op','')} · {of.get('sous_traitant_cout',0)} DT")
        y_cur -= 14*mm

    # ── COST SUMMARY ─────────────────────────────────────
    st_cost = float(of.get("sous_traitant_cout") or 0)
    total_cost = total_mo_cost + total_mat_cost + st_cost
    prix_vente = float(of.get("prix_vente_ht") or 0) * qte
    marge = prix_vente - total_cost if prix_vente > 0 else None

    y_cur -= 6*mm
    summary_rows = [
        ("Main d'Œuvre",   f"{total_mo_cost:.3f} DT"),
        ("Matières",       f"{total_mat_cost:.3f} DT"),
        ("Sous-traitance", f"{st_cost:.3f} DT"),
        ("COÛT REVIENT",   f"{total_cost:.3f} DT"),
    ]
    if marge is not None:
        summary_rows.append(("Prix Vente HT", f"{prix_vente:.3f} DT"))
        summary_rows.append(("MARGE BRUTE",   f"{marge:.3f} DT"))

    sx = W - 80*mm
    for i, (lbl, val) in enumerate(summary_rows):
        is_total = lbl in ("COÛT REVIENT", "MARGE BRUTE")
        bg = DARK if is_total else LIGHT
        fg = WHITE if is_total else DARK
        row_h = 7*mm
        c.setFillColor(bg)
        c.rect(sx, y_cur - row_h, 68*mm, row_h, fill=1, stroke=0)
        c.setStrokeColor(BORDER); c.setLineWidth(0.3)
        c.rect(sx, y_cur - row_h, 68*mm, row_h, fill=0, stroke=1)
        c.setFillColor(fg)
        c.setFont("Helvetica-Bold" if is_total else "Helvetica", 8)
        c.drawString(sx + 2*mm, y_cur - 5*mm, lbl)
        c.drawRightString(sx + 66*mm, y_cur - 5*mm, val)
        y_cur -= row_h

    # ── BL REFERENCE ─────────────────────────────────────
    y_cur -= 14*mm
    c.setFillColor(LIGHT); c.rect(12*mm, y_cur-8*mm, 60*mm, 10*mm, fill=1, stroke=0)
    c.setStrokeColor(BORDER); c.rect(12*mm, y_cur-8*mm, 60*mm, 10*mm, fill=0, stroke=1)
    c.setFillColor(GRAY); c.setFont("Helvetica-Bold", 7)
    c.drawString(14*mm, y_cur-2*mm, "BL N°:")
    c.setFillColor(RED); c.setFont("Helvetica-Bold", 9)
    c.drawString(28*mm, y_cur-2*mm, of.get("bl_numero") or "—")

    # ── SIGNATURES ───────────────────────────────────────
    sig_y = max(y_cur - 35*mm, 20*mm)
    for label, sx in [("VISA RESP. PRODUCTION", 12*mm), ("VISA DIRECTION", 110*mm)]:
        c.setStrokeColor(BORDER); c.setLineWidth(0.5)
        c.rect(sx, sig_y, 80*mm, 28*mm, fill=0, stroke=1)
        c.setFillColor(GRAY); c.setFont("Helvetica-Bold", 7)
        c.drawString(sx+2*mm, sig_y+24*mm, label)
        c.setFillColor(LIGHT); c.rect(sx, sig_y, 80*mm, 6*mm, fill=1, stroke=0)

    # ── FOOTER ───────────────────────────────────────────
    c.setFillColor(DARK); c.rect(0, 0, W, 10*mm, fill=1, stroke=0)
    c.setFillColor(RED);  c.rect(0, 10*mm, W, 0.8*mm, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 6.5)
    c.drawString(12*mm, 6*mm, f"{S_NOM} · {S_ADDR} · {S_VILLE} · {S_TEL}")
    c.drawRightString(W-12*mm, 6*mm, f"ENR-PRD-02 · {now} · {PDF_PIED}")

    c.save(); buf.seek(0)
    fname = f"Fiche_{of['numero'].replace('/','-')}.pdf"
    return StreamingResponse(io.BytesIO(buf.read()), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fname}"'})