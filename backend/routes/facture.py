"""
SOFEM MES v2.0 — Facture / Invoice Route
Generates PDF invoice for completed OFs
SMARTMOVE · Mahmoud Njeh
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db, q, serialize
from auth import require_any_role
from datetime import datetime
import io

router = APIRouter(prefix="/api/facture", tags=["facture"])


def generate_pdf(of: dict, etapes: list, materiaux: list, type: str = "interne") -> bytes:
    """
    type = 'interne' → full report with stages + materials + costs
    type = 'client'  → clean client invoice without internal details
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet

    W, H = A4
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # Colors
    RED    = colors.HexColor("#D42B2B")
    DARK   = colors.HexColor("#111111")
    GRAY   = colors.HexColor("#6B7280")
    LIGHT  = colors.HexColor("#F9FAFB")
    GREEN  = colors.HexColor("#16a34a")
    WHITE  = colors.white
    BORDER = colors.HexColor("#E5E7EB")

    TVA_RATE   = 0.19
    PRIX_UNIT  = 85.0
    now        = datetime.now()
    date_str   = now.strftime("%d / %m / %Y")
    fac_num    = f"FAC-{of['numero'].replace('OF-', '')}"

    # ── HEADER BAR ────────────────────────────────
    c.setFillColor(DARK)
    c.rect(0, H - 38*mm, W, 38*mm, fill=1, stroke=0)
    c.setFillColor(RED)
    c.rect(0, H - 40*mm, W, 2*mm, fill=1, stroke=0)

    # SOFEM logo block
    c.setFillColor(RED)
    c.roundRect(15*mm, H - 32*mm, 22*mm, 22*mm, 4, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(26*mm, H - 24*mm, "S")

    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(42*mm, H - 22*mm, "SOFEM")
    c.setFillColor(RED)
    c.setFont("Helvetica", 7)
    c.drawString(42*mm, H - 27*mm, "PARTENAIRE DES BRIQUETERIES")
    c.setFillColor(colors.HexColor("#9CA3AF"))
    c.setFont("Helvetica", 7)
    c.drawString(42*mm, H - 32*mm, "Route Sidi Salem 2.5KM · Sfax · +216 74 469 181")

    # FACTURE label right
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 28)
    c.drawRightString(W - 15*mm, H - 20*mm, "FACTURE")
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(W - 15*mm, H - 27*mm, fac_num)
    c.setFillColor(colors.HexColor("#9CA3AF"))
    c.setFont("Helvetica", 8)
    c.drawRightString(W - 15*mm, H - 33*mm, f"Date : {date_str}")

    # ── INFO BAND ─────────────────────────────────
    y_band = H - 63*mm
    c.setFillColor(LIGHT)
    c.rect(0, y_band, W, 22*mm, fill=1, stroke=0)
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.5)
    c.line(0, y_band, W, y_band)
    c.line(0, y_band + 22*mm, W, y_band + 22*mm)

    def info_col(label, val, sub, x):
        c.setFillColor(GRAY)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x, y_band + 18*mm, label.upper())
        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x, y_band + 13*mm, val[:30])
        c.setFillColor(GRAY)
        c.setFont("Helvetica", 7.5)
        for i, line in enumerate(sub.split('\n')):
            c.drawString(x, y_band + 8*mm - i*4*mm, line)

    info_col("OF", of['numero'], f"Créé le: {str(of.get('created_at',''))[:10]}", 15*mm)
    info_col("Produit", of['produit_nom'], f"Code: {of.get('produit_code','—')}\nAtelier: {of.get('atelier','—')}", 75*mm)
    info_col("Opérateur", of.get('operateur_nom','—'), f"Échéance: {of.get('date_echeance','—')}\nPriorité: {of.get('priorite','—')}", 135*mm)

    # ── KPI BOXES ─────────────────────────────────
    y_kpi = y_band - 18*mm
    kpis = [
        ("QUANTITÉ PRODUITE", f"{of['quantite']} pcs", RED),
        ("STATUT", "TERMINÉ ✓", GREEN),
        ("N° FACTURE", fac_num, DARK),
    ]
    box_w = (W - 30*mm) / 3
    for i, (lbl, val, col) in enumerate(kpis):
        bx = 15*mm + i * (box_w + 0*mm)
        c.setFillColor(LIGHT)
        c.roundRect(bx, y_kpi, box_w - 3*mm, 14*mm, 3, fill=1, stroke=0)
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.4)
        c.roundRect(bx, y_kpi, box_w - 3*mm, 14*mm, 3, fill=0, stroke=1)
        c.setFillColor(GRAY)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(bx + 3*mm, y_kpi + 10*mm, lbl)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(bx + 3*mm, y_kpi + 4*mm, val)

    # ── ETAPES TABLE ──────────────────────────────
    y_cur = y_kpi - 10*mm

    def section_title(title, y):
        c.setFillColor(RED)
        c.rect(15*mm, y - 0.5*mm, 3*mm, 5*mm, fill=1, stroke=0)
        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(20*mm, y, title)
        return y - 8*mm

    # ── ETAPES (interne only) ─────────────────────
    if type == "interne":
        y_cur = section_title("ÉTAPES DE PRODUCTION", y_cur)

        cols_e = [15*mm, 75*mm, 130*mm, 175*mm]
        hdrs_e = ["ÉTAPE", "STATUT", "OPÉRATEUR", "DURÉE"]
        c.setFillColor(DARK)
        c.rect(15*mm, y_cur - 6*mm, W - 30*mm, 8*mm, fill=1, stroke=0)
        for i, h in enumerate(hdrs_e):
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(cols_e[i] + 2*mm, y_cur - 3*mm, h)
        y_cur -= 6*mm

        STAGE_ORDER = ['AutoCAD','Découpage','Pliage','Soudage','Ponçage']
        for idx, etape_name in enumerate(STAGE_ORDER):
            e = next((x for x in etapes if x['etape'] == etape_name), None)
            if not e:
                continue
            row_h = 8*mm
            y_cur -= row_h
            if idx % 2 == 0:
                c.setFillColor(LIGHT)
                c.rect(15*mm, y_cur, W - 30*mm, row_h, fill=1, stroke=0)

            duree = '—'
            if e.get('debut') and e.get('fin'):
                try:
                    mins = int((datetime.fromisoformat(str(e['fin'])) -
                                datetime.fromisoformat(str(e['debut']))).total_seconds() / 60)
                    duree = f"{mins // 60}h {mins % 60}min" if mins >= 60 else f"{mins} min"
                except:
                    duree = '—'

            statut_icon = "✓ TERMINÉ" if e['statut'] == 'COMPLETED' else "⏳ EN COURS" if e['statut'] == 'IN_PROGRESS' else "— EN ATTENTE"
            stat_col = GREEN if e['statut'] == 'COMPLETED' else RED if e['statut'] == 'IN_PROGRESS' else GRAY

            c.setFillColor(DARK); c.setFont("Helvetica-Bold", 8)
            c.drawString(cols_e[0] + 2*mm, y_cur + 2.5*mm, etape_name)
            c.setFillColor(stat_col); c.setFont("Helvetica", 7.5)
            c.drawString(cols_e[1] + 2*mm, y_cur + 2.5*mm, statut_icon)
            c.setFillColor(DARK); c.setFont("Helvetica", 7.5)
            c.drawString(cols_e[2] + 2*mm, y_cur + 2.5*mm, str(e.get('operateur_nom') or '—')[:20])
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(cols_e[3] + 2*mm, y_cur + 2.5*mm, duree)
            c.setStrokeColor(BORDER); c.setLineWidth(0.3)
            c.line(15*mm, y_cur, W - 15*mm, y_cur)

        # ── MATERIAUX (interne only) ──────────────
        y_cur -= 10*mm
        y_cur = section_title("MATÉRIAUX CONSOMMÉS (ESTIMATIF)", y_cur)

        cols_m = [15*mm, 100*mm, 145*mm, 175*mm]
        hdrs_m = ["MATÉRIAU", "CODE", "UNITÉ", "QTÉ CONSOMMÉE"]
        c.setFillColor(DARK)
        c.rect(15*mm, y_cur - 6*mm, W - 30*mm, 8*mm, fill=1, stroke=0)
        for i, h in enumerate(hdrs_m):
            c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 7)
            c.drawString(cols_m[i] + 2*mm, y_cur - 3*mm, h)
        y_cur -= 6*mm

        for idx, m in enumerate(materiaux[:4]):
            consomme = round(float(m.get('stock_minimum', 0)) * 0.05 * of['quantite'] / 100, 3)
            row_h = 8*mm
            y_cur -= row_h
            if idx % 2 == 0:
                c.setFillColor(LIGHT)
                c.rect(15*mm, y_cur, W - 30*mm, row_h, fill=1, stroke=0)
            c.setFillColor(DARK); c.setFont("Helvetica", 7.5)
            c.drawString(cols_m[0] + 2*mm, y_cur + 2.5*mm, str(m.get('nom',''))[:35])
            c.drawString(cols_m[1] + 2*mm, y_cur + 2.5*mm, str(m.get('code','—')))
            c.drawString(cols_m[2] + 2*mm, y_cur + 2.5*mm, str(m.get('unite','—')))
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(cols_m[3] + 2*mm, y_cur + 2.5*mm, str(consomme))
            c.setStrokeColor(BORDER); c.setLineWidth(0.3)
            c.line(15*mm, y_cur, W - 15*mm, y_cur)

    # ── TOTALS ────────────────────────────────────
    y_cur -= 14*mm
    section_lbl = "DÉTAIL FINANCIER" if type == "interne" else "FACTURE CLIENT"
    y_cur = section_title(section_lbl, y_cur)

    # Pricing row
    ht      = PRIX_UNIT * of['quantite']
    tva_amt = ht * TVA_RATE
    ttc     = ht + tva_amt

    col_prix = [15*mm, 90*mm, 130*mm, 165*mm]
    hdrs_p   = ["DÉSIGNATION", "QTÉ", "PRIX UNIT. HT", "TOTAL HT"]
    c.setFillColor(DARK)
    c.rect(15*mm, y_cur - 6*mm, W - 30*mm, 8*mm, fill=1, stroke=0)
    for i, h in enumerate(hdrs_p):
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 7)
        c.drawString(col_prix[i] + 2*mm, y_cur - 3*mm, h)
    y_cur -= 14*mm

    c.setFillColor(LIGHT)
    c.rect(15*mm, y_cur, W - 30*mm, 8*mm, fill=1, stroke=0)
    c.setFillColor(DARK); c.setFont("Helvetica", 8)
    c.drawString(col_prix[0] + 2*mm, y_cur + 2.5*mm, f"Fabrication {of['produit_nom']} — {of['numero']}")
    c.drawString(col_prix[1] + 2*mm, y_cur + 2.5*mm, str(of['quantite']))
    c.setFont("Helvetica", 8)
    c.drawString(col_prix[2] + 2*mm, y_cur + 2.5*mm, f"{PRIX_UNIT:.3f} TND")
    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_prix[3] + 2*mm, y_cur + 2.5*mm, f"{ht:.3f} TND")

    # Totals box right
    y_cur -= 12*mm
    box_x = W - 85*mm
    totals = [
        ("Total HT",   f"{ht:.3f} TND",   LIGHT, DARK),
        ("TVA (19%)",  f"{tva_amt:.3f} TND", LIGHT, GRAY),
        ("TOTAL TTC",  f"{ttc:.3f} TND",  DARK, WHITE),
    ]
    for lbl, val, bg, fg in totals:
        row_h = 9*mm if lbl != "TOTAL TTC" else 11*mm
        c.setFillColor(bg)
        c.rect(box_x, y_cur - row_h, W - 15*mm - box_x, row_h, fill=1, stroke=0)
        c.setFillColor(fg)
        sz = 9 if lbl != "TOTAL TTC" else 11
        c.setFont("Helvetica-Bold", sz)
        c.drawString(box_x + 3*mm, y_cur - row_h + 3*mm, lbl)
        c.drawRightString(W - 17*mm, y_cur - row_h + 3*mm, val)
        c.setStrokeColor(BORDER); c.setLineWidth(0.4)
        c.line(box_x, y_cur - row_h, W - 15*mm, y_cur - row_h)
        y_cur -= row_h

    # ── SIGNATURE ─────────────────────────────────
    y_sig = y_cur - 16*mm
    c.setStrokeColor(BORDER); c.setLineWidth(0.5)
    c.roundRect(W - 75*mm, y_sig - 22*mm, 60*mm, 22*mm, 3, fill=0, stroke=1)
    c.setFillColor(GRAY); c.setFont("Helvetica", 8)
    c.drawCentredString(W - 45*mm, y_sig - 6*mm, "Signature & Cachet")
    c.line(W - 70*mm, y_sig - 18*mm, W - 20*mm, y_sig - 18*mm)

    # ── FOOTER ────────────────────────────────────
    c.setFillColor(DARK)
    c.rect(0, 0, W, 14*mm, fill=1, stroke=0)
    c.setFillColor(RED)
    c.rect(0, 14*mm, W, 0.8*mm, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 7)
    c.drawString(15*mm, 9*mm, "SOFEM · Partenaire des Briqueteries")
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 7)
    c.drawString(15*mm, 5*mm, "Route Sidi Salem 2.5KM · Sfax · +216 74 469 181 · sofem-tn.com")
    c.setFillColor(colors.HexColor("#9CA3AF"))
    c.drawRightString(W - 15*mm, 9*mm, f"{fac_num} · {date_str}")
    c.drawRightString(W - 15*mm, 5*mm, "Généré par SOFEM MES v2.0 · SMARTMOVE")

    c.save()
    buf.seek(0)
    return buf.read()


@router.get("/{of_id}")
def get_facture(of_id: int, type: str = "interne", db=Depends(get_db)):
    # Get OF with etapes
    of = q(db, """
        SELECT o.*, p.nom produit_nom, p.code produit_code,
               CONCAT(op.prenom,' ',op.nom) operateur_nom
        FROM ordres_fabrication o
        JOIN produits p ON o.produit_id=p.id
        LEFT JOIN operateurs op ON o.operateur_id=op.id
        WHERE o.id=%s
    """, (of_id,), one=True)

    if not of:
        raise HTTPException(404, "OF non trouvé")
    if of['statut'] != 'COMPLETED':
        raise HTTPException(400, "Facture disponible uniquement pour les OFs terminés")

    etapes = q(db, """
        SELECT e.*, CONCAT(op.prenom,' ',op.nom) operateur_nom
        FROM etapes_production e
        LEFT JOIN operateurs op ON e.operateur_id=op.id
        WHERE e.of_id=%s
        ORDER BY FIELD(e.etape,'AutoCAD','Découpage','Pliage','Soudage','Ponçage')
    """, (of_id,))

    materiaux = q(db, "SELECT * FROM materiaux ORDER BY nom LIMIT 5")

    # Serialize dates
    of = serialize(of)
    etapes = serialize(etapes)
    materiaux = serialize(materiaux)

    pdf_bytes = generate_pdf(of, etapes, materiaux, type)

    fac_num = f"FAC-{of['numero'].replace('OF-', '')}"
    suffix  = "-CLIENT" if type == "client" else "-INTERNE"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fac_num}{suffix}.pdf"'}
    )
