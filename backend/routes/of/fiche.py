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
        SELECT ob.*, m.nom materiau_nom, m.code materiau_code, m.unite
        FROM of_bom ob JOIN materiaux m ON m.id = ob.materiau_id
        WHERE ob.of_id = %s
    """, (of_id,))

    of = serialize(of); ops = serialize(ops); bom = serialize(bom)
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
    c.setFillColor(RED); c.roundRect(12*mm, H-30*mm, 20*mm, 20*mm, 3, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(22*mm, H-22*mm, "S")
    # Company name
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 18)
    c.drawString(36*mm, H-20*mm, "SOFEM")
    c.setFillColor(RED); c.setFont("Helvetica", 7)
    c.drawString(36*mm, H-25*mm, "SOCIÉTÉ DE FABRICATION ÉLECTROMÉCANIQUE & DE MAINTENANCE")
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 6.5)
    c.drawString(36*mm, H-29*mm, "Route Sidi Salem 2.5KM · Sfax · +216 74 469 181")
    # Title right
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 16)
    c.drawRightString(W-12*mm, H-20*mm, "FICHE DE RÉSUMÉ PRODUCTION")
    c.setFillColor(RED); c.setFont("Helvetica-Bold", 10)
    c.drawRightString(W-12*mm, H-26*mm, "ENR-PRD-02")
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 8)
    c.drawRightString(W-12*mm, H-30*mm, f"Rév. 00  ·  Date: {now}  ·  Page 1/1")

    # ── INFO BAND ───────────────────────────────────────
    y = H - 55*mm
    c.setFillColor(LIGHT); c.rect(12*mm, y, W-24*mm, 16*mm, fill=1, stroke=0)
    c.setStrokeColor(BORDER); c.setLineWidth(0.5)
    c.rect(12*mm, y, W-24*mm, 16*mm, fill=0, stroke=1)

    def info_cell(label, value, x, y_base):
        c.setFillColor(GRAY); c.setFont("Helvetica-Bold", 6.5)
        c.drawString(x, y_base+11*mm, label.upper())
        c.setFillColor(DARK); c.setFont("Helvetica-Bold", 9)
        c.drawString(x, y_base+6.5*mm, str(value or "—")[:30])

    info_cell("OF N°",         of["numero"],            14*mm, y)
    info_cell("Produit",        of["produit_nom"],       50*mm, y)
    info_cell("Client",         of["client_nom"],        100*mm, y)
    info_cell("Plan N°",        of.get("plan_numero"),   150*mm, y)
    # second row
    info_cell("Quantité",       of["quantite"],          14*mm, y-8*mm)
    info_cell("Chef Atelier",   of.get("chef_projet_nom"), 50*mm, y-8*mm)
    info_cell("MF Client",      of.get("client_mf"),     100*mm, y-8*mm)
    info_cell("Date",           now,                     150*mm, y-8*mm)

    c.setFillColor(LIGHT); c.rect(12*mm, y-10*mm, W-24*mm, 10*mm, fill=1, stroke=0)
    c.rect(12*mm, y-10*mm, W-24*mm, 10*mm, fill=0, stroke=1)

    # ── OPERATIONS TABLE ────────────────────────────────
    y_cur = y - 18*mm
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

    total_cost = 0
    for idx, op in enumerate(ops):
        dur = op.get("duree_reelle") or 0  # minutes
        dur_h = dur / 60
        # AutoCAD × 1, others × quantite
        mult = 1 if "autocad" in op["operation_nom"].lower() else qte
        total_h = dur_h * mult
        # Cost: use first operator's rate
        cost = 0
        try:
            th = float((op.get("taux_horaires") or "0").split(",")[0])
            tp = float((op.get("taux_pieces") or "0").split(",")[0])
            tt = (op.get("types_taux") or "HORAIRE").split(",")[0]
            if tt == "HORAIRE": cost = total_h * th
            elif tt == "PIECE":  cost = mult * tp
            else: cost = total_h * th + mult * tp
        except: pass
        total_cost += cost

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
    mat_headers = ["DÉSIGNATION","CODE","QUANTITÉ","UNITÉ"]
    mat_x = [12, 82, 132, 162]
    c.setFillColor(DARK); c.rect(12*mm, y_cur-5*mm, W-24*mm, 7*mm, fill=1, stroke=0)
    for i, h in enumerate(mat_headers):
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 7)
        c.drawString(mat_x[i]*mm+1*mm, y_cur-2*mm, h)
    y_cur -= 12*mm
    for idx, b in enumerate(bom):
        bg = LIGHT if idx % 2 == 0 else WHITE
        c.setFillColor(bg); c.rect(12*mm, y_cur-4*mm, W-24*mm, 6*mm, fill=1, stroke=0)
        c.setStrokeColor(BORDER); c.rect(12*mm, y_cur-4*mm, W-24*mm, 6*mm, fill=0, stroke=1)
        c.setFillColor(DARK); c.setFont("Helvetica", 8)
        for i, v in enumerate([b["materiau_nom"], b["materiau_code"],
                                str(b["quantite_requise"]), b["unite"]]):
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

    # ── TOTAL COST ───────────────────────────────────────
    y_cur -= 4*mm
    c.setFillColor(DARK); c.rect(130*mm, y_cur-8*mm, W-142*mm, 10*mm, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 9)
    c.drawString(132*mm, y_cur-5*mm, f"COÛT TOTAL: {total_cost:.3f} DT")

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
    c.drawString(12*mm, 6*mm, "SOFEM · Route Sidi Salem 2.5KM · Sfax · +216 74 469 181")
    c.drawRightString(W-12*mm, 6*mm, f"ENR-PRD-02 · {now} · SOFEM MES v6.0")

    c.save(); buf.seek(0)
    fname = f"Fiche_{of['numero'].replace('/','-')}.pdf"
    return StreamingResponse(io.BytesIO(buf.read()), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fname}"'})
