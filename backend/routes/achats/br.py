"""SOFEM MES v6.0 — Bons de Réception"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db, q, exe, serialize, temp_numero, finalize_number, log_activity
from auth import require_any_role, require_manager_or_admin, get_current_user, get_pdf_user
from models import BRCreate
from datetime import datetime
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from routes.settings import get_all_settings

router = APIRouter(prefix="/api/achats/br", tags=["achats-br"])


@router.get("", dependencies=[Depends(require_any_role)])
def list_br(db=Depends(get_db)):
    brs = serialize(q(db, """
        SELECT br.*, bc.bc_numero, bc.fournisseur
        FROM bons_reception br
        JOIN bons_commande bc ON br.bc_id = bc.id
        ORDER BY br.created_at DESC
    """))
    for br in brs:
        br["lignes"] = serialize(q(db, """
            SELECT brl.*, bcl.description, bcl.unite, m.nom materiau_nom
            FROM br_lignes brl
            JOIN bc_lignes bcl ON brl.bc_ligne_id = bcl.id
            LEFT JOIN materiaux m ON bcl.materiau_id = m.id
            WHERE brl.br_id = %s
        """, (br["id"],)))
    return brs


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_br(data: BRCreate, user=Depends(get_current_user), db=Depends(get_db)):
    year = datetime.now().year
    tmp = temp_numero()
    br_id = exe(db, """
        INSERT INTO bons_reception (br_numero,bc_id,date_reception,statut,notes)
        VALUES (%s,%s,%s,%s,%s)
    """, (tmp, data.bc_id, data.date_reception, data.statut, data.notes))
    numero = finalize_number(db, "bons_reception", "br_numero", br_id, "BR", year)

    for l in data.lignes:
        price = float(l.prix_unitaire) if l.prix_unitaire else 0
        # SNAPSHOT the price paid at reception (frozen for history)
        exe(db, """INSERT INTO br_lignes 
                   (br_id,bc_ligne_id,quantite_recue,prix_unitaire,prix_unitaire_snapshot) 
                   VALUES (%s,%s,%s,%s,%s)""",
            (br_id, l.bc_ligne_id, l.quantite_recue, price, price))
        bcl = q(db, "SELECT materiau_id FROM bc_lignes WHERE id=%s", (l.bc_ligne_id,), one=True)
        if bcl and bcl["materiau_id"]:
            mat = q(db, "SELECT stock_actuel FROM materiaux WHERE id=%s",
                    (bcl["materiau_id"],), one=True)
            if mat:
                avant = float(mat["stock_actuel"])
                apres = avant + float(l.quantite_recue)
                exe(db, "UPDATE materiaux SET stock_actuel=%s WHERE id=%s",
                    (apres, bcl["materiau_id"]))
                exe(db, """
                    INSERT INTO mouvements_stock
                      (materiau_id,type,quantite,stock_avant,stock_apres,motif)
                    VALUES (%s,'ENTREE',%s,%s,%s,%s)
                """, (bcl["materiau_id"], l.quantite_recue, avant, apres, f"Réception {numero}"))

    exe(db, "UPDATE bons_commande SET statut=%s WHERE id=%s",
        ("RECU" if data.statut == "COMPLET" else "RECU_PARTIEL", data.bc_id))
    
    log_activity(db, "CREATE", "BR", br_id, numero,
                 user.get("id"), f"{user.get('prenom','')} {user.get('nom','')}".strip(),
                 new_value=data.dict(), detail=f"BR {numero} créé — stock mis à jour")
    
    return {"id": br_id, "br_numero": numero, "message": "BR créé — stock mis à jour"}


@router.put("/{br_id}/confirmer", dependencies=[Depends(require_manager_or_admin)])
def confirmer_reception(br_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    """
    Confirm reception of an auto-generated BR (EN_ATTENTE).
    Updates quantite_recue from BC line, updates stock, marks DA as RECEIVED.
    Synchronizes prices from br_lignes to bc_lignes.
    """
    br = q(db, "SELECT * FROM bons_reception WHERE id=%s", (br_id,), one=True)
    if not br: raise HTTPException(404, "BR introuvable")
    if br["statut"] not in ("EN_ATTENTE", "PARTIEL"):
        raise HTTPException(400, f"BR deja traite (statut: {br['statut']})")

    lignes = q(db, """
        SELECT brl.id, brl.bc_ligne_id, brl.quantite_recue, brl.prix_unitaire,
               bcl.materiau_id, bcl.quantite as quantite_commandee,
               bcl.unite, m.nom materiau_nom, m.stock_actuel
        FROM br_lignes brl
        JOIN bc_lignes bcl ON bcl.id = brl.bc_ligne_id
        LEFT JOIN materiaux m ON m.id = bcl.materiau_id
        WHERE brl.br_id = %s
    """, (br_id,))

    stock_updates = []
    for l in lignes:
        # Use commanded quantity as received if quantite_recue is 0
        qte_recue = float(l["quantite_recue"])
        if qte_recue == 0:
            qte_recue = float(l["quantite_commandee"])
            exe(db, "UPDATE br_lignes SET quantite_recue=%s WHERE id=%s",
                (qte_recue, l["id"]))

        # Update bc_lignes price from br_lignes if available
        if l["prix_unitaire"] and float(l["prix_unitaire"]) > 0:
            exe(db, "UPDATE bc_lignes SET prix_unitaire=%s WHERE id=%s",
                (l["prix_unitaire"], l["bc_ligne_id"]))

        if l["materiau_id"] and qte_recue > 0:
            avant = float(l["stock_actuel"] or 0)
            apres = avant + qte_recue
            exe(db, "UPDATE materiaux SET stock_actuel=%s WHERE id=%s",
                (apres, l["materiau_id"]))
            exe(db, """
                INSERT INTO mouvements_stock
                  (materiau_id, type, quantite, stock_avant, stock_apres, motif)
                VALUES (%s, 'ENTREE', %s, %s, %s, %s)
            """, (l["materiau_id"], qte_recue, avant, apres,
                  f"Reception {br['br_numero']}"))
            stock_updates.append({
                "materiau": l["materiau_nom"],
                "quantite": qte_recue,
                "stock_avant": avant,
                "stock_apres": apres
            })

    # Mark BR as COMPLET + set date
    exe(db, """
        UPDATE bons_reception
        SET statut='COMPLET', date_reception=CURDATE()
        WHERE id=%s
    """, (br_id,))

    # Mark BC as RECU
    exe(db, "UPDATE bons_commande SET statut='RECU' WHERE id=%s", (br["bc_id"],))

    # Mark DA as RECEIVED
    da = q(db, "SELECT id FROM demandes_achat WHERE id=(SELECT da_id FROM bons_commande WHERE id=%s)",
           (br["bc_id"],), one=True)
    if da:
        exe(db, "UPDATE demandes_achat SET statut='RECEIVED' WHERE id=%s", (da["id"],))

    log_activity(db, "UPDATE", "BR", br_id, br["br_numero"],
                 user.get("id"), f"{user.get('prenom','')} {user.get('nom','')}".strip(),
                 old_value={"statut": br["statut"]}, new_value={"statut": "COMPLET"},
                 detail=f"BR {br['br_numero']} confirmée — {len(stock_updates)} matériau(x) mis à jour")

    return {
        "message": f"Reception confirmee — {len(stock_updates)} materiau(x) mis a jour",
        "stock_updates": stock_updates
    }


@router.put("/{br_id}/quantite", dependencies=[Depends(require_manager_or_admin)])
def update_br_quantite(br_id: int, quantite_recue: float, db=Depends(get_db)):
    """Update the received quantity before confirming (partial reception)."""
    br = q(db, "SELECT id, statut FROM bons_reception WHERE id=%s", (br_id,), one=True)
    if not br: raise HTTPException(404, "BR introuvable")
    if br["statut"] == "COMPLET":
        raise HTTPException(400, "BR deja complete")
    # Update first line (single-line auto-generated BR)
    exe(db, """
        UPDATE br_lignes SET quantite_recue=%s
        WHERE br_id=%s
        ORDER BY id LIMIT 1
    """, (quantite_recue, br_id))
    if br["statut"] == "EN_ATTENTE":
        exe(db, "UPDATE bons_reception SET statut='PARTIEL' WHERE id=%s", (br_id,))
    return {"message": "Quantite mise a jour"}


@router.get("/{br_id}/pdf")
def print_br(br_id: int, user=Depends(get_pdf_user), db=Depends(get_db)):
    br = q(db, """
        SELECT br.*, bc.bc_numero, bc.fournisseur
        FROM bons_reception br
        JOIN bons_commande bc ON br.bc_id = bc.id
        WHERE br.id = %s
    """, (br_id,), one=True)
    if not br:
        raise HTTPException(404, "BR non trouvée")
    br = serialize(br)
    br["lignes"] = serialize(q(db, """
        SELECT brl.*, bcl.description, m.nom materiau_nom
        FROM br_lignes brl
        JOIN bc_lignes bcl ON brl.bc_ligne_id = bcl.id
        LEFT JOIN materiaux m ON bcl.materiau_id = m.id
        WHERE brl.br_id = %s
    """, (br_id,)))

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
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 26); c.drawRightString(W-15*2.835, H-20*2.835, "BON DE RECEPTION")
    c.setFillColor(RED);   c.setFont("Helvetica-Bold", 13); c.drawRightString(W-15*2.835, H-27*2.835, br["br_numero"])
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 8)
    c.drawRightString(W-15*2.835, H-33*2.835, f"Date: {br.get('date_reception', now)}")

    y = H - 63*mm
    c.setFillColor(LIGHT); c.rect(0, y, W, 18*mm, fill=1, stroke=0)
    c.setStrokeColor(BORDER); c.setLineWidth(0.5)
    c.line(0, y, W, y); c.line(0, y+18*mm, W, y+18*mm)
    c.setFillColor(GRAY); c.setFont("Helvetica-Bold", 7);  c.drawString(15*mm, y+14*mm, "FOURNISSEUR")
    c.setFillColor(DARK); c.setFont("Helvetica-Bold", 11); c.drawString(15*mm, y+8*mm, str(br.get("fournisseur", "—"))[:40])
    c.setFillColor(GRAY); c.setFont("Helvetica", 8);       c.drawString(15*mm, y+3*mm, f"BC réf: {br.get('bc_numero', '—')}")
    c.setFillColor(GRAY); c.setFont("Helvetica-Bold", 7);  c.drawRightString(W-15*mm, y+14*mm, "STATUT")
    c.setFillColor(DARK); c.setFont("Helvetica-Bold", 11); c.drawRightString(W-15*mm, y+8*mm, br.get("statut", "—"))

    # Lines table
    y_cur = y - 14*mm
    c.setFillColor(GRAY); c.setFont("Helvetica-Bold", 8)
    c.drawString(15*mm, y_cur+5*mm, "MATÉRIAU")
    c.drawString(80*mm, y_cur+5*mm, "DESCRIPTION")
    c.drawRightString(W-60*mm, y_cur+5*mm, "QTÉ RECUE")
    c.drawRightString(W-15*mm, y_cur+5*mm, "UNITÉ")
    y_cur -= 8*mm

    c.setStrokeColor(BORDER); c.setLineWidth(0.5)
    c.line(15*mm, y_cur+12*mm, W-15*mm, y_cur+12*mm)

    for ligne in br["lignes"]:
        if y_cur < 30*mm:  # New page if needed
            c.showPage()
            y_cur = H - 50*mm
            c.setFillColor(GRAY); c.setFont("Helvetica-Bold", 8)
            c.drawString(15*mm, y_cur+5*mm, "MATÉRIAU")
            c.drawString(80*mm, y_cur+5*mm, "DESCRIPTION")
            c.drawRightString(W-60*mm, y_cur+5*mm, "QTÉ RECUE")
            c.drawRightString(W-15*mm, y_cur+5*mm, "UNITÉ")
            y_cur -= 8*mm
            c.line(15*mm, y_cur+12*mm, W-15*mm, y_cur+12*mm)

        c.setFillColor(DARK); c.setFont("Helvetica", 8)
        materiau = ligne.get("materiau_nom", "—")
        desc = ligne.get("description", "—")
        qte = ligne.get("quantite_recue", 0)
        unite = ligne.get("unite", "—")

        c.drawString(15*mm, y_cur+5*mm, str(materiau)[:25])
        c.drawString(80*mm, y_cur+5*mm, str(desc)[:40])
        c.drawRightString(W-60*mm, y_cur+5*mm, f"{qte}")
        c.drawRightString(W-15*mm, y_cur+5*mm, str(unite))
        y_cur -= 8*mm

    # Footer
    c.setFillColor(GRAY); c.setFont("Helvetica", 7)
    c.drawCentredString(W/2, 15*mm, PDF_PIED)

    c.showPage()
    c.save()
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=BR_{br['br_numero']}.pdf"})