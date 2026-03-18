"""SOFEM MES v6.0 — Bon de Livraison Routes"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
import io

router = APIRouter(prefix="/api/bl", tags=["bon-livraison"])

class BLCreate(BaseModel):
    of_id: int
    date_livraison: Optional[date] = None
    destinataire: str = "SOFEM"
    adresse: str = "Route Sidi Salem 2.5KM, Sfax"
    notes: Optional[str] = None

class BLUpdate(BaseModel):
    statut: Optional[str] = None
    date_livraison: Optional[date] = None
    notes: Optional[str] = None

def gen_bl_number(db) -> str:
    last = q(db, "SELECT bl_numero FROM bons_livraison ORDER BY id DESC LIMIT 1", one=True)
    year = datetime.now().year
    if last:
        try: num = int(last["bl_numero"].split("-")[-1]) + 1
        except: num = 1
    else: num = 1
    return f"BL-{year}-{str(num).zfill(3)}"

@router.get("", dependencies=[Depends(require_any_role)])
def list_bl(db=Depends(get_db)):
    return serialize(q(db, """
        SELECT bl.*, o.numero of_numero, o.statut of_statut,
               p.nom produit_nom, o.quantite,
               c.nom client_nom, c.matricule_fiscal client_mf
        FROM bons_livraison bl
        JOIN ordres_fabrication o ON bl.of_id=o.id
        JOIN produits p ON o.produit_id=p.id
        LEFT JOIN clients c ON c.id = o.client_id
        ORDER BY bl.created_at DESC
    """))

@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_bl(data: BLCreate, db=Depends(get_db)):
    of = q(db, "SELECT id FROM ordres_fabrication WHERE id=%s", (data.of_id,), one=True)
    if not of: raise HTTPException(404, "OF non trouvé")
    existing = q(db, "SELECT id FROM bons_livraison WHERE of_id=%s", (data.of_id,), one=True)
    if existing: raise HTTPException(400, "Un BL existe déjà pour cet OF")
    numero = gen_bl_number(db)
    bl_id = exe(db, """INSERT INTO bons_livraison (bl_numero,of_id,date_livraison,destinataire,adresse,notes)
        VALUES (%s,%s,%s,%s,%s,%s)""",
        (numero, data.of_id, data.date_livraison, data.destinataire, data.adresse, data.notes))
    return {"id": bl_id, "bl_numero": numero, "message": "BL créé"}

@router.get("/{bl_id}/pdf")
def print_bl(bl_id: int, db=Depends(get_db)):
    bl = q(db, """
        SELECT bl.*, o.numero of_numero, o.quantite, o.atelier, o.date_echeance,
               p.nom produit_nom, p.code produit_code,
               CONCAT(cp.prenom,' ',cp.nom) operateur_nom,
               c.nom client_nom, c.matricule_fiscal client_mf,
               c.adresse client_adresse, c.ville client_ville
        FROM bons_livraison bl
        JOIN ordres_fabrication o ON bl.of_id=o.id
        JOIN produits p ON o.produit_id=p.id
        LEFT JOIN operateurs cp ON o.chef_projet_id=cp.id
        LEFT JOIN clients c ON c.id=o.client_id
        WHERE bl.id=%s
    """, (bl_id,), one=True)
    if not bl: raise HTTPException(404, "BL non trouvé")
    bl = serialize(bl)

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
    LIGHT = colors.HexColor("#F9FAFB")
    WHITE = colors.white
    BORDER = colors.HexColor("#E5E7EB")
    GREEN = colors.HexColor("#16a34a")

    now = datetime.now().strftime("%d / %m / %Y")

    # Header
    c.setFillColor(DARK); c.rect(0, H-38*mm, W, 38*mm, fill=1, stroke=0)
    c.setFillColor(RED);  c.rect(0, H-40*mm, W, 2*mm,  fill=1, stroke=0)
    c.setFillColor(RED);  c.roundRect(15*mm, H-32*mm, 22*mm, 22*mm, 4, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 18); c.drawCentredString(26*mm, H-24*mm, "S")
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 20); c.drawString(42*mm, H-22*mm, "SOFEM")
    c.setFillColor(RED);   c.setFont("Helvetica", 7);  c.drawString(42*mm, H-27*mm, "PARTENAIRE DES BRIQUETERIES")
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 7)
    c.drawString(42*mm, H-32*mm, "Route Sidi Salem 2.5KM · Sfax · +216 74 469 181")
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 26); c.drawRightString(W-15*mm, H-20*mm, "BON DE LIVRAISON")
    c.setFillColor(RED);   c.setFont("Helvetica-Bold", 13); c.drawRightString(W-15*mm, H-27*mm, bl["bl_numero"])
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 8)
    c.drawRightString(W-15*mm, H-33*mm, f"Date: {now}")

    # Info band
    y = H-60*mm
    c.setFillColor(LIGHT); c.rect(0, y, W, 18*mm, fill=1, stroke=0)
    c.setStrokeColor(BORDER); c.setLineWidth(0.5)
    c.line(0, y, W, y); c.line(0, y+18*mm, W, y+18*mm)

    def info_col(lbl, val, sub, x):
        c.setFillColor(GRAY);  c.setFont("Helvetica-Bold", 7);  c.drawString(x, y+14*mm, lbl.upper())
        c.setFillColor(DARK);  c.setFont("Helvetica-Bold", 10); c.drawString(x, y+9*mm, str(val)[:28])
        c.setFillColor(GRAY);  c.setFont("Helvetica", 7.5);     c.drawString(x, y+5*mm, str(sub)[:35])

    info_col("N° OF", bl["of_numero"], f"Produit: {bl['produit_nom']}", 15*mm)
    info_col("Destinataire", bl["destinataire"], bl["adresse"][:40], 75*mm)
    info_col("Opérateur", bl["operateur_nom"] or "—", f"Atelier: {bl['atelier'] or '—'}", 145*mm)

    # Detail table
    y_cur = y - 12*mm
    c.setFillColor(DARK); c.setFont("Helvetica-Bold", 11)
    c.rect(15*mm, y_cur-0.5*mm, 3*mm, 5*mm, fill=1, stroke=0)
    c.setFillColor(DARK); c.drawString(20*mm, y_cur, "DÉTAIL DE LA LIVRAISON")
    y_cur -= 10*mm

    cols = [15*mm, 75*mm, 135*mm, 165*mm]
    hdrs = ["DÉSIGNATION", "CODE PRODUIT", "QUANTITÉ", "STATUT"]
    c.setFillColor(DARK); c.rect(15*mm, y_cur-6*mm, W-30*mm, 8*mm, fill=1, stroke=0)
    for i,h in enumerate(hdrs):
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 7.5)
        c.drawString(cols[i]+2*mm, y_cur-3*mm, h)
    y_cur -= 14*mm

    c.setFillColor(LIGHT); c.rect(15*mm, y_cur, W-30*mm, 10*mm, fill=1, stroke=0)
    c.setFillColor(DARK);  c.setFont("Helvetica", 9)
    c.drawString(cols[0]+2*mm, y_cur+3*mm, bl["produit_nom"])
    c.drawString(cols[1]+2*mm, y_cur+3*mm, bl["produit_code"] or "—")
    c.setFont("Helvetica-Bold", 9)
    c.drawString(cols[2]+2*mm, y_cur+3*mm, str(bl["quantite"]))
    c.setFillColor(GREEN); c.drawString(cols[3]+2*mm, y_cur+3*mm, "✓ LIVRÉ")
    c.setStrokeColor(BORDER); c.setLineWidth(0.4)
    c.line(15*mm, y_cur, W-15*mm, y_cur)
    y_cur -= 16*mm

    # Signatures
    c.setFillColor(DARK); c.setFont("Helvetica-Bold", 9)
    for label, x in [("Signature Expéditeur", 15*mm), ("Signature Destinataire", W/2+10*mm)]:
        c.rect(x, y_cur-28*mm, 75*mm, 30*mm, fill=0, stroke=1)
        c.setStrokeColor(BORDER); c.setLineWidth(0.5)
        c.setFillColor(GRAY); c.setFont("Helvetica", 8)
        c.drawString(x+3*mm, y_cur-6*mm, label)
        c.line(x+5*mm, y_cur-22*mm, x+70*mm, y_cur-22*mm)

    # Footer
    c.setFillColor(DARK); c.rect(0, 0, W, 12*mm, fill=1, stroke=0)
    c.setFillColor(RED);  c.rect(0, 12*mm, W, 0.8*mm, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold", 7); c.drawString(15*mm, 8*mm, "SOFEM · Partenaire des Briqueteries")
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 7)
    c.drawString(15*mm, 4*mm, "Route Sidi Salem 2.5KM · Sfax · sofem-tn.com")
    c.drawRightString(W-15*mm, 8*mm, f"{bl['bl_numero']} · {now}")
    c.drawRightString(W-15*mm, 4*mm, "SOFEM MES v3.0 · SMARTMOVE")

    c.save(); buf.seek(0)
    return StreamingResponse(io.BytesIO(buf.read()), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{bl["bl_numero"]}.pdf"'})


@router.put("/{bl_id}")
def update_bl(bl_id: int, data: BLUpdate, db=Depends(get_db),
              user=Depends(require_any_role)):
    bl = q(db, "SELECT * FROM bons_livraison WHERE id=%s", (bl_id,), one=True)
    if not bl: raise HTTPException(404, "BL non trouvé")
    # Save current version before update
    last_ver = q(db, "SELECT MAX(version) v FROM bl_versions WHERE bl_id=%s",
                 (bl_id,), one=True)
    ver = (last_ver["v"] or 0) + 1
    try:
        exe(db, """
            INSERT INTO bl_versions
              (bl_id,version,destinataire,adresse,date_livraison,notes,modifie_par)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (bl_id, ver, bl["destinataire"], bl["adresse"],
              bl["date_livraison"], bl["notes"],
              user.get("prenom","") + " " + user.get("nom","")))
    except Exception: pass  # bl_versions table may not exist yet
    fields, vals = [], []
    if data.statut         is not None: fields.append("statut=%s");         vals.append(data.statut)
    if data.date_livraison is not None: fields.append("date_livraison=%s"); vals.append(data.date_livraison)
    if data.notes          is not None: fields.append("notes=%s");          vals.append(data.notes)
    if fields:
        vals.append(bl_id)
        exe(db, f"UPDATE bons_livraison SET {','.join(fields)} WHERE id=%s", vals)
    return {"message": "BL mis à jour", "version": ver}


@router.put("/{bl_id}/details")
def update_bl_details(bl_id: int, db=Depends(get_db),
                      user=Depends(require_any_role),
                      destinataire: str = None,
                      adresse: str = None,
                      notes: str = None):
    """Update BL recipient/address/notes (editable even after delivery)."""
    bl = q(db, "SELECT * FROM bons_livraison WHERE id=%s", (bl_id,), one=True)
    if not bl: raise HTTPException(404, "BL non trouvé")
    # Save version
    last_ver = q(db, "SELECT MAX(version) v FROM bl_versions WHERE bl_id=%s",
                 (bl_id,), one=True)
    ver = (last_ver["v"] or 0) + 1
    try:
        exe(db, """
            INSERT INTO bl_versions
              (bl_id,version,destinataire,adresse,date_livraison,notes,modifie_par)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (bl_id, ver, bl["destinataire"], bl["adresse"],
              bl["date_livraison"], bl["notes"],
              user.get("prenom","") + " " + user.get("nom","")))
    except Exception: pass
    fields, vals = [], []
    if destinataire is not None: fields.append("destinataire=%s"); vals.append(destinataire)
    if adresse      is not None: fields.append("adresse=%s");      vals.append(adresse)
    if notes        is not None: fields.append("notes=%s");        vals.append(notes)
    if fields:
        vals.append(bl_id)
        exe(db, f"UPDATE bons_livraison SET {','.join(fields)} WHERE id=%s", vals)
    return {"message": "BL mis à jour", "version": ver}


@router.get("/{bl_id}/versions")
def get_bl_versions(bl_id: int, db=Depends(get_db), user=Depends(require_any_role)):
    """Get version history for a BL."""
    try:
        versions = q(db, """
            SELECT * FROM bl_versions WHERE bl_id=%s ORDER BY version DESC
        """, (bl_id,))
        return serialize(versions)
    except Exception:
        return []


class BLLivrer(BaseModel):
    destinataire: str
    adresse: str
    date_livraison: date
    notes: Optional[str] = None

@router.post("/{bl_id}/livrer")
def livrer_bl(bl_id: int, data: BLLivrer, db=Depends(get_db),
              user=Depends(require_manager_or_admin)):
    """Mark BL as LIVRÉ, record recipient + date, auto-complete the OF."""
    bl = q(db, "SELECT * FROM bons_livraison WHERE id=%s", (bl_id,), one=True)
    if not bl: raise HTTPException(404, "BL non trouvé")
    # Check OF is COMPLETED before allowing delivery
    of_check = q(db, "SELECT statut FROM ordres_fabrication WHERE id=%s",
                 (bl["of_id"],), one=True)
    if of_check and of_check["statut"] != "COMPLETED":
        raise HTTPException(409, {
            "message": "Impossible de livrer — l'OF n'est pas terminé",
            "of_statut": of_check["statut"]
        })
    if bl["statut"] == "LIVRE":
        raise HTTPException(400, "BL déjà livré")

    exe(db, """
        UPDATE bons_livraison
        SET statut='LIVRE',
            date_livraison=%s,
            date_livraison_reelle=%s,
            destinataire_final=%s,
            adresse_finale=%s,
            notes=%s
        WHERE id=%s
    """, (data.date_livraison, data.date_livraison,
          data.destinataire, data.adresse,
          data.notes, bl_id))

    # Auto-complete the OF
    exe(db, "UPDATE ordres_fabrication SET statut='COMPLETED' WHERE id=%s", (bl["of_id"],))

    return {"message": "BL marqué LIVRÉ — OF clôturé", "bl_id": bl_id, "of_id": bl["of_id"]}