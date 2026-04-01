"""SOFEM MES v6.0 — Factures Achat"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db, q, exe, serialize, temp_numero, finalize_number, log_activity
from auth import require_any_role, require_manager_or_admin, get_current_user, get_pdf_user
from models import FACreate
from datetime import datetime
from routes.settings import get_all_settings
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

router = APIRouter(prefix="/api/achats/fa", tags=["achats-fa"])


@router.get("/{fa_id}", dependencies=[Depends(require_any_role)])
def get_fa_detail(fa_id: int, db=Depends(get_db)):
    """Get FA details with frozen prices from fa_lignes."""
    fa = q(db, """
        SELECT fa.*, bc.bc_numero, bc.fournisseur
        FROM factures_achat fa
        JOIN bons_commande bc ON fa.bc_id = bc.id
        WHERE fa.id = %s
    """, (fa_id,), one=True)
    if not fa:
        raise HTTPException(404, "FA non trouvée")
    
    fa = serialize(fa)
    
    # Get frozen price lines
    lignes = serialize(q(db, """
        SELECT * FROM fa_lignes WHERE fa_id = %s ORDER BY id
    """, (fa_id,)))
    
    fa["lignes"] = lignes
    return fa


@router.get("")

def list_fa(db=Depends(get_db)):
    return serialize(q(db, """
        SELECT fa.*, bc.bc_numero
        FROM factures_achat fa
        JOIN bons_commande bc ON fa.bc_id = bc.id
        ORDER BY fa.created_at DESC
    """))


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_fa(data: FACreate, user=Depends(get_current_user), db=Depends(get_db)):

    TVA_RATE = float(get_all_settings(db).get("tva_rate", 19))
    year = datetime.now().year
    tmp = temp_numero()
    bc = q(db, "SELECT id FROM bons_commande WHERE id=%s", (data.bc_id,), one=True)
    if not bc: raise HTTPException(404, "BC non trouvé")
    
    # Read prices from BR lignes (actual frozen prices at reception)
    # Use prix_unitaire_snapshot (frozen price paid)
    lignes = q(db, """
        SELECT bcl.id, bcl.quantite, bcl.description, bcl.unite, 
               COALESCE(brl.prix_unitaire_snapshot, brl.prix_unitaire, bcl.prix_unitaire, 0) as prix_snapshot
        FROM bc_lignes bcl
        LEFT JOIN br_lignes brl ON brl.bc_ligne_id = bcl.id
        WHERE bcl.bc_id=%s
    """, (data.bc_id,))
    
    ht  = sum(float(l["quantite"])*float(l["prix_snapshot"]) for l in lignes)
    tva = round(ht*TVA_RATE/100, 3)
    ttc = round(ht+tva, 3)
    
    fa_id = exe(db, """
        INSERT INTO factures_achat
          (fa_numero,bc_id,fournisseur,date_facture,montant_ht,tva,montant_ttc,
           cost_locked_at,cost_locked_by,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (tmp, data.bc_id, data.fournisseur, data.date_facture, 
          ht, tva, ttc, datetime.now(), user.get("id"), data.notes))
    
    numero = finalize_number(db, "factures_achat", "fa_numero", fa_id, "FA", year)
    
    # Create fa_lignes with frozen prices (immutable history)
    for l in lignes:
        price_snapshot = float(l["prix_snapshot"])
        amount = float(l["quantite"]) * price_snapshot
        exe(db, """
            INSERT INTO fa_lignes 
            (fa_id, bc_ligne_id, description, quantite, unite, prix_unitaire_snapshot, montant)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (fa_id, l["id"], l.get("description", ""), 
              l["quantite"], l.get("unite", "pcs"), 
              price_snapshot, amount))
    
    log_activity(db, "CREATE", "FA", fa_id, numero,
                 user.get("id"), f"{user.get('prenom','')} {user.get('nom','')}".strip(),
                 new_value={"bc_id": data.bc_id, "montant_ttc": ttc, "frozen_prices": True},
                 detail=f"FA {numero} créée — Montant TTC: {ttc} TND — Prix figés")
    
    return {"id": fa_id, "fa_numero": numero, "montant_ttc": ttc, "message": "Facture créée avec prix figés"}


@router.put("/{fa_id}/payer", dependencies=[Depends(require_manager_or_admin)])
def payer_fa(fa_id: int, db=Depends(get_db)):
    exe(db, "UPDATE factures_achat SET statut='PAYEE' WHERE id=%s", (fa_id,))
    return {"message": "Facture payée"}


@router.get("/{fa_id}/pdf")
def print_fa(fa_id: int, user=Depends(get_pdf_user), db=Depends(get_db)):
    fa = q(db, """
        SELECT fa.*, bc.bc_numero, bc.fournisseur
        FROM factures_achat fa
        JOIN bons_commande bc ON fa.bc_id = bc.id
        WHERE fa.id = %s
    """, (fa_id,), one=True)
    if not fa:
        raise HTTPException(404, "FA non trouvée")
    fa = serialize(fa)

    cfg = get_all_settings(db)
    S_NOM   = cfg.get("societe_nom",       "SOFEM")
    S_TAG   = cfg.get("societe_tagline",   "Partenaire des Briqueteries")
    S_ADDR  = cfg.get("societe_adresse",   "Route Sidi Salem 2.5KM")
    S_VILLE = cfg.get("societe_ville",     "Sfax")
    S_TEL   = cfg.get("societe_telephone", "+216 74 469 181")
    S_MF    = cfg.get("societe_mf",        "000000000/A/M/000")
    S_WEB   = cfg.get("societe_website",   "sofem-tn.com")
    PDF_PIED = cfg.get("pdf_pied_custom",  "SOFEM MES v6.0 · SMARTMOVE")

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
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 26); c.drawRightString(W-15*2.835, H-20*2.835, "FACTURE ACHAT")
    c.setFillColor(RED);   c.setFont("Helvetica-Bold", 13); c.drawRightString(W-15*2.835, H-27*2.835, fa["fa_numero"])
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 8)
    c.drawRightString(W-15*2.835, H-33*2.835, f"Date: {fa['date_facture'].strftime('%d/%m/%Y') if fa.get('date_facture') else now}")

    y = H - 63*mm
    c.setFillColor(LIGHT); c.rect(0, y, W, 18*mm, fill=1, stroke=0)
    c.setStrokeColor(BORDER); c.setLineWidth(0.5)
    c.line(0, y, W, y); c.line(0, y+18*mm, W, y+18*mm)
    c.setFillColor(GRAY); c.setFont("Helvetica-Bold", 7);  c.drawString(15*mm, y+14*mm, "FOURNISSEUR")
    c.setFillColor(DARK); c.setFont("Helvetica-Bold", 11); c.drawString(15*mm, y+8*mm, str(fa.get("fournisseur", "—"))[:40])
    c.setFillColor(GRAY); c.setFont("Helvetica", 8);       c.drawString(15*mm, y+3*mm, f"BC réf: {fa.get('bc_numero', '—')}")
    c.setFillColor(GRAY); c.setFont("Helvetica-Bold", 7);  c.drawRightString(W-15*mm, y+14*mm, "MONTANT TTC")
    c.setFillColor(DARK); c.setFont("Helvetica-Bold", 11); c.drawRightString(W-15*mm, y+8*mm, f"{fa.get('montant_ttc', 0):.2f} TND")

    # Footer
    c.setFillColor(GRAY); c.setFont("Helvetica", 7)
    c.drawCentredString(W/2, 15*mm, PDF_PIED)

    c.showPage()
    c.save()
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=FA_{fa['fa_numero']}.pdf"})