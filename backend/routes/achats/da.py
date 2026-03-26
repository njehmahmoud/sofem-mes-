"""SOFEM MES v6.0 — Demandes Achat (patched)
Fixes:
  - Race condition in DA/BC/BR numbering: insert-first, id-based numero
  - N+1 in list_da: BC/BR data batch-fetched in one query
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db, q, exe, serialize, temp_numero, finalize_number, cancel_document
from auth import require_any_role, require_manager_or_admin, get_current_user
from models import DACreate, DAUpdate, CancelRequest
from datetime import datetime
import io

logger = logging.getLogger("sofem-achats")

router = APIRouter(prefix="/api/achats/da", tags=["achats-da"])


def _make_bc_br(db, da_id):
    """Create a BC + BR pair for an approved DA. Race-free numbering."""
    year = datetime.now().year
    da = q(db, """
        SELECT da.*, m.nom materiau_nom, m.unite materiau_unite, m.prix_unitaire,
               f.nom fournisseur_nom
        FROM demandes_achat da
        LEFT JOIN materiaux m ON da.materiau_id = m.id
        LEFT JOIN materiau_fournisseurs mf ON mf.materiau_id = m.id AND mf.principal = 1
        LEFT JOIN fournisseurs f ON f.id = mf.fournisseur_id
        WHERE da.id = %s
    """, (da_id,), one=True)
    if not da:
        return None

    fournisseur = da.get("fournisseur_nom") or "A definir"
    desig = da.get("materiau_nom") or da["description"]
    unite = da.get("materiau_unite") or da["unite"]
    prix  = float(da.get("prix_unitaire") or 0)

    # BC — race-free
    tmp_bc = temp_numero()
    bc_id = exe(db, """
        INSERT INTO bons_commande (bc_numero, fournisseur, da_id, statut, notes)
        VALUES (%s, %s, %s, 'DRAFT', %s)
    """, (tmp_bc, fournisseur, da_id,
          "Généré automatiquement depuis " + da["da_numero"]))
    bc_num = finalize_number(db, "bons_commande", "bc_numero", bc_id, "BC", year)

    bc_ligne_id = exe(db, """
        INSERT INTO bc_lignes (bc_id, materiau_id, description, quantite, unite, prix_unitaire)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (bc_id, da.get("materiau_id"), desig, float(da["quantite"]), unite, prix))

    # BR — race-free
    tmp_br = temp_numero()
    br_id = exe(db, """
        INSERT INTO bons_reception (br_numero, bc_id, date_reception, statut, notes)
        VALUES (%s, %s, NULL, 'EN_ATTENTE', %s)
    """, (tmp_br, bc_id, "En attente de réception - " + da["da_numero"]))
    br_num = finalize_number(db, "bons_reception", "br_numero", br_id, "BR", year)

    exe(db, "INSERT INTO br_lignes (br_id, bc_ligne_id, quantite_recue) VALUES (%s, %s, 0)",
        (br_id, bc_ligne_id))

    exe(db, "UPDATE demandes_achat SET statut='ORDERED' WHERE id=%s", (da_id,))

    return {
        "bc_id": bc_id, "bc_numero": bc_num,
        "br_id": br_id, "br_numero": br_num,
        "fournisseur": fournisseur,
    }


# ── LIST ──────────────────────────────────────────────────

@router.get("", dependencies=[Depends(require_any_role)])
def list_da(db=Depends(get_db)):
    das = serialize(q(db, """
        SELECT da.*, m.nom materiau_nom,
               o.numero of_numero,
               CONCAT(d.prenom,' ',d.nom) demandeur_nom,
               CONCAT(v.prenom,' ',v.nom) valideur_nom
        FROM demandes_achat da
        LEFT JOIN materiaux m ON da.materiau_id = m.id
        LEFT JOIN ordres_fabrication o ON da.of_id = o.id
        LEFT JOIN operateurs d ON da.demandeur_id = d.id
        LEFT JOIN operateurs v ON da.valideur_id = v.id
        ORDER BY da.created_at DESC
    """))

    if not das:
        return das

    # ── Batch-fetch BC+BR for all DAs in ONE query (eliminates N+1) ──
    da_ids = [da["id"] for da in das]
    placeholders = ",".join(["%s"] * len(da_ids))
    bc_rows = q(db, f"""
        SELECT bc.da_id, bc.id, bc.bc_numero, bc.statut,
               br.id br_id, br.br_numero, br.statut br_statut
        FROM bons_commande bc
        LEFT JOIN bons_reception br ON br.bc_id = bc.id
        WHERE bc.da_id IN ({placeholders})
        ORDER BY bc.id DESC
    """, da_ids)

    # Group by da_id, keep only the latest BC per DA
    bc_by_da: dict = {}
    for row in bc_rows:
        did = row["da_id"]
        if did not in bc_by_da:
            bc_by_da[did] = row

    for da in das:
        da["bc"] = serialize(bc_by_da.get(da["id"]))

    return das


# ── CREATE ────────────────────────────────────────────────

@router.post("", status_code=201, dependencies=[Depends(require_any_role)])
def create_da(data: DACreate, db=Depends(get_db)):
    year = datetime.now().year
    tmp = temp_numero()
    da_id = exe(db, """
        INSERT INTO demandes_achat
          (da_numero, of_id, materiau_id, description, objet, quantite, unite, urgence, notes, demandeur_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (tmp, data.of_id, data.materiau_id, data.description, data.objet,
          data.quantite, data.unite, data.urgence, data.notes, data.demandeur_id))
    numero = finalize_number(db, "demandes_achat", "da_numero", da_id, "DA", year)
    return {"id": da_id, "da_numero": numero, "message": "Demande créée"}
# ── cancel ────────────────────────────────────────────────

@router.put("/{da_id}/cancel")
def cancel_da(da_id: int, data: CancelRequest,
              user=Depends(get_current_user), db=Depends(get_db)):
    numero = cancel_document(
        db, "demandes_achat", "id", "da_numero",
        da_id, user["id"],
        f"{user.get('prenom','')} {user.get('nom','')}",
        data.reason, "DA"
    )
    return {"message": f"DA {numero} annulée"}

# ── UPDATE ────────────────────────────────────────────────

@router.put("/{da_id}", dependencies=[Depends(require_manager_or_admin)])
def update_da(da_id: int, data: DAUpdate, db=Depends(get_db)):
    if data.statut == "APPROVED":
        existing = q(db, "SELECT id FROM bons_commande WHERE da_id=%s LIMIT 1", (da_id,), one=True)
        if existing:
            exe(db, "UPDATE demandes_achat SET statut='APPROVED' WHERE id=%s", (da_id,))
            return {"message": "DA approuvée — BC/BR déjà existants"}
        result = _make_bc_br(db, da_id)
        if result:
            return {
                "message": f"DA approuvée — {result['bc_numero']} + {result['br_numero']} créés",
                **result,
            }

    fields, params = [], []
    for f, v in data.dict(exclude_none=True).items():
        fields.append(f"{f}=%s")
        params.append(v)
    if fields:
        params.append(da_id)
        exe(db, f"UPDATE demandes_achat SET {','.join(fields)} WHERE id=%s", params)
    return {"message": "DA mise à jour"}


# ── PDF: Bon d'Achat ──────────────────────────────────────

@router.get("/{da_id}/ba")
def print_ba(da_id: int, token: str = None, user=Depends(get_pdf_user), db=Depends(get_db)):
    da = q(db, """
        SELECT da.*, m.nom materiau_nom, m.code materiau_code, m.unite materiau_unite,
               o.numero of_numero, o.quantite of_quantite, o.date_echeance, c.nom client_nom
        FROM demandes_achat da
        LEFT JOIN materiaux m ON da.materiau_id = m.id
        LEFT JOIN ordres_fabrication o ON da.of_id = o.id
        LEFT JOIN clients c ON c.id = o.client_id
        WHERE da.id = %s
    """, (da_id,), one=True)
    if not da:
        raise HTTPException(404, "DA introuvable")
    da = serialize(da)

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas

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

    c.setFillColor(DARK); c.rect(0, H-32*mm, W, 32*mm, fill=1, stroke=0)
    c.setFillColor(RED);  c.rect(0, H-34*mm, W, 2*mm, fill=1, stroke=0)
    c.setFillColor(RED);  c.roundRect(12*mm, H-28*mm, 18*mm, 18*mm, 3, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 14); c.drawCentredString(21*mm, H-21*mm, "S")
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 16); c.drawString(34*mm, H-20*mm, "SOFEM")
    c.setFillColor(RED);   c.setFont("Helvetica", 6.5)
    c.drawString(34*mm, H-25*mm, "SOCIETE DE FABRICATION ELECTROMECANIQUE & DE MAINTENANCE")
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 20); c.drawRightString(W-12*mm, H-18*mm, "BESOINS & ACHATS")
    c.setFillColor(RED);   c.setFont("Helvetica-Bold", 9);  c.drawRightString(W-12*mm, H-24*mm, "ENR-ACH-01")
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 7.5)
    c.drawRightString(W-12*mm, H-29*mm, f"Rev. 00  .  {now}")

    y = H - 50*mm
    c.setFillColor(LIGHT); c.rect(12*mm, y, W-24*mm, 14*mm, fill=1, stroke=0)
    c.setStrokeColor(BORDER); c.setLineWidth(0.5); c.rect(12*mm, y, W-24*mm, 14*mm, fill=0, stroke=1)

    def cell(lbl, val, x, y0):
        c.setFillColor(GRAY); c.setFont("Helvetica-Bold", 6.5); c.drawString(x, y0+10*mm, lbl.upper())
        c.setFillColor(DARK); c.setFont("Helvetica-Bold", 9);   c.drawString(x, y0+5.5*mm, str(val or "-")[:28])

    cell("DA N°",    da["da_numero"],         14*mm, y)
    cell("OF N°",    da.get("of_numero"),     55*mm, y)
    cell("Client",   da.get("client_nom"),   100*mm, y)
    cell("Date",     now,                    155*mm, y)
    cell("Quantité", da.get("of_quantite") or da["quantite"], 14*mm, y-9*mm)
    cell("Urgence",  da["urgence"],           55*mm, y-9*mm)
    cell("Statut",   da["statut"],           100*mm, y-9*mm)

    y_cur = y - 18*mm
    c.setFillColor(DARK); c.setFont("Helvetica-Bold", 9); c.drawString(12*mm, y_cur+2*mm, "OBJET:")
    c.setFont("Helvetica", 9)
    objet_txt = da.get("objet") or da["description"]
    words = objet_txt.split()
    lines_txt, line = [], ""
    for w in words:
        test = line + " " + w if line else w
        if c.stringWidth(test, "Helvetica", 9) < (W - 28*mm):
            line = test
        else:
            lines_txt.append(line)
            line = w
    if line:
        lines_txt.append(line)
    for i, lt in enumerate(lines_txt[:3]):
        c.drawString(12*mm, y_cur-5*mm - i*5*mm, lt)
    y_cur -= 8*mm + len(lines_txt[:3]) * 5*mm

    y_cur -= 6*mm
    cols = [12, 90, 130, 160, 185]
    c.setFillColor(DARK); c.rect(12*mm, y_cur-6*mm, W-24*mm, 8*mm, fill=1, stroke=0)
    for i, h in enumerate(["DÉSIGNATION", "QUANTITÉ", "UNITÉ", "PRIX HT/DT", "MONTANT"]):
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 7.5)
        c.drawString(cols[i]*mm+1*mm, y_cur-3*mm, h)
    y_cur -= 14*mm
    desig = da.get("materiau_nom") or da["description"]
    c.setFillColor(LIGHT); c.rect(12*mm, y_cur-5*mm, W-24*mm, 7*mm, fill=1, stroke=0)
    c.setStrokeColor(BORDER); c.rect(12*mm, y_cur-5*mm, W-24*mm, 7*mm, fill=0, stroke=1)
    c.setFillColor(DARK); c.setFont("Helvetica", 8.5)
    c.drawString(cols[0]*mm+1*mm, y_cur-2*mm, desig[:50])
    c.drawString(cols[1]*mm+1*mm, y_cur-2*mm, str(float(da["quantite"])))
    c.drawString(cols[2]*mm+1*mm, y_cur-2*mm, da.get("materiau_unite") or da["unite"])
    c.drawString(cols[3]*mm+1*mm, y_cur-2*mm, "-")
    c.drawString(cols[4]*mm+1*mm, y_cur-2*mm, "-")
    for _ in range(5):
        y_cur -= 8*mm
        c.setStrokeColor(BORDER); c.setLineWidth(0.3)
        c.rect(12*mm, y_cur-5*mm, W-24*mm, 7*mm, fill=0, stroke=1)

    sig_y = max(y_cur - 40*mm, 22*mm)
    for label, sx in [("RESPONSABLE ATELIER", 12*mm), ("DIRECTION", W/2+5*mm)]:
        c.setStrokeColor(BORDER); c.setLineWidth(0.5)
        c.rect(sx, sig_y, 85*mm, 32*mm, fill=0, stroke=1)
        c.setFillColor(LIGHT); c.rect(sx, sig_y+26*mm, 85*mm, 6*mm, fill=1, stroke=0)
        c.setFillColor(GRAY);  c.setFont("Helvetica-Bold", 7); c.drawString(sx+2*mm, sig_y+28*mm, label)
        c.setFillColor(GRAY);  c.setFont("Helvetica", 7)
        c.drawString(sx+2*mm, sig_y+3*mm, "Date: _______________")
        c.line(sx+2*mm, sig_y+12*mm, sx+83*mm, sig_y+12*mm)

    c.setFillColor(DARK); c.rect(0, 0, W, 10*mm, fill=1, stroke=0)
    c.setFillColor(RED);  c.rect(0, 10*mm, W, 0.8*mm, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 6.5)
    c.drawString(12*mm, 6.5*mm, "SOFEM · Route Sidi Salem 2.5KM · Sfax · +216 74 469 181")
    c.drawRightString(W-12*mm, 6.5*mm, f"ENR-ACH-01 · {now} · SOFEM MES v6.0")

    c.save()
    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.read()),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="BA_{da["da_numero"]}.pdf"'},
    )
