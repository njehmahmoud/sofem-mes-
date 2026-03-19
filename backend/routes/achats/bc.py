"""SOFEM MES v6.0 — Bons de Commande + PDF"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db, q, exe, serialize
from auth import require_any_role, get_pdf_user, require_manager_or_admin
from models import BCCreate
from datetime import datetime
import io

router = APIRouter(prefix="/api/achats/bc", tags=["achats-bc"])


def gen_num(db):
    last = q(db, "SELECT bc_numero FROM bons_commande ORDER BY id DESC LIMIT 1", one=True)
    year = datetime.now().year
    try: n = int(last["bc_numero"].split("-")[-1]) + 1 if last else 1
    except: n = 1
    return f"BC-{year}-{str(n).zfill(3)}"


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
    for bc in bcs:
        bc["lignes"] = serialize(q(db, """
            SELECT bcl.*, m.nom materiau_nom
            FROM bc_lignes bcl LEFT JOIN materiaux m ON bcl.materiau_id = m.id
            WHERE bcl.bc_id = %s
        """, (bc["id"],)))
        ht = sum(float(l["quantite"]) * float(l["prix_unitaire"]) for l in bc["lignes"])
        bc["montant_ht"]  = round(ht, 3)
        bc["montant_tva"] = round(ht * TVA_RATE / 100, 3)
        bc["montant_ttc"] = round(ht * (1 + TVA_RATE / 100), 3)
    return bcs


@router.post("", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_bc(data: BCCreate, db=Depends(get_db)):
    from routes.settings import get_all_settings
    TVA_RATE = float(get_all_settings(db).get("tva_rate", 19))
    numero = gen_num(db)
    bc_id = exe(db, """
        INSERT INTO bons_commande (bc_numero,fournisseur,da_id,notes)
        VALUES (%s,%s,%s,%s)
    """, (numero, data.fournisseur, data.da_id, data.notes))
    for l in data.lignes:
        exe(db, """
            INSERT INTO bc_lignes (bc_id,materiau_id,description,quantite,unite,prix_unitaire)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (bc_id, l.materiau_id, l.description, l.quantite, l.unite, l.prix_unitaire))
    if data.da_id:
        exe(db, "UPDATE demandes_achat SET statut='ORDERED' WHERE id=%s", (data.da_id,))
    return {"id": bc_id, "bc_numero": numero, "message": "BC créé"}


@router.put("/{bc_id}/statut", dependencies=[Depends(require_manager_or_admin)])
def update_statut(bc_id: int, statut: str, db=Depends(get_db)):
    exe(db, "UPDATE bons_commande SET statut=%s WHERE id=%s", (statut, bc_id))
    return {"message": "BC mis à jour"}


@router.get("/{bc_id}/pdf")
def print_bc(bc_id: int, token: str=None, user=Depends(get_pdf_user), db=Depends(get_db)):
    from routes.settings import get_all_settings
    TVA_RATE = float(get_all_settings(db).get("tva_rate", 19))
    bc = q(db, "SELECT * FROM bons_commande WHERE id=%s", (bc_id,), one=True)
    if not bc: raise HTTPException(404, "BC non trouvé")
    lignes = q(db, """
        SELECT bcl.*, m.nom materiau_nom FROM bc_lignes bcl
        LEFT JOIN materiaux m ON bcl.materiau_id = m.id WHERE bcl.bc_id = %s
    """, (bc_id,))
    bc = serialize(bc); lignes = serialize(lignes)

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas

    W, H = A4; buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    RED=colors.HexColor("#D42B2B"); DARK=colors.HexColor("#111")
    GRAY=colors.HexColor("#6B7280"); LIGHT=colors.HexColor("#F9FAFB")
    WHITE=colors.white; BORDER=colors.HexColor("#E5E7EB")
    now = datetime.now().strftime("%d/%m/%Y")
    ht = sum(float(l["quantite"])*float(l["prix_unitaire"]) for l in lignes)
    tva = round(ht*TVA_RATE/100,3); ttc = round(ht+tva,3)

    c.setFillColor(DARK); c.rect(0,H-38*mm,W,38*mm,fill=1,stroke=0)
    c.setFillColor(RED);  c.rect(0,H-40*mm,W,2*mm,fill=1,stroke=0)
    c.setFillColor(RED);  c.roundRect(15*mm,H-32*mm,22*mm,22*mm,4,fill=1,stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold",18); c.drawCentredString(26*mm,H-24*mm,"S")
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold",20); c.drawString(42*mm,H-22*mm,"SOFEM")
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold",24); c.drawRightString(W-15*mm,H-20*mm,"BON DE COMMANDE")
    c.setFillColor(RED);   c.setFont("Helvetica-Bold",13); c.drawRightString(W-15*mm,H-27*mm,bc["bc_numero"])
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica",8); c.drawRightString(W-15*mm,H-33*mm,f"Date: {now}")

    y=H-58*mm
    c.setFillColor(LIGHT); c.rect(0,y,W,16*mm,fill=1,stroke=0)
    c.setFillColor(GRAY);  c.setFont("Helvetica-Bold",7); c.drawString(15*mm,y+12*mm,"FOURNISSEUR")
    c.setFillColor(DARK);  c.setFont("Helvetica-Bold",11); c.drawString(15*mm,y+7*mm,bc["fournisseur"])
    c.setFillColor(GRAY);  c.setFont("Helvetica-Bold",7); c.drawRightString(W-15*mm,y+12*mm,"STATUT")
    c.setFillColor(DARK);  c.setFont("Helvetica-Bold",10); c.drawRightString(W-15*mm,y+7*mm,bc["statut"])

    y_cur=y-14*mm
    c.setFillColor(DARK); c.rect(15*mm,y_cur-6*mm,W-30*mm,8*mm,fill=1,stroke=0)
    for i,(h,x) in enumerate(zip(["DESCRIPTION","QTÉ","UNITÉ","PRIX UNIT. HT","TOTAL HT"],
                                  [15,80,120,145,170])):
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold",7); c.drawString(x*mm+2*mm,y_cur-3*mm,h)
    y_cur-=6*mm
    for idx,l in enumerate(lignes):
        y_cur-=8*mm
        if idx%2==0: c.setFillColor(LIGHT); c.rect(15*mm,y_cur,W-30*mm,8*mm,fill=1,stroke=0)
        total=round(float(l["quantite"])*float(l["prix_unitaire"]),3)
        c.setFillColor(DARK); c.setFont("Helvetica",8)
        c.drawString(17*mm,y_cur+2.5*mm,str(l.get("materiau_nom") or l["description"])[:35])
        c.drawString(82*mm,y_cur+2.5*mm,str(l["quantite"]))
        c.drawString(122*mm,y_cur+2.5*mm,str(l["unite"]))
        c.drawString(147*mm,y_cur+2.5*mm,f"{float(l['prix_unitaire']):.3f}")
        c.setFont("Helvetica-Bold",8); c.drawString(172*mm,y_cur+2.5*mm,f"{total:.3f} TND")
        c.setStrokeColor(BORDER); c.setLineWidth(0.3); c.line(15*mm,y_cur,W-15*mm,y_cur)

    y_cur-=12*mm; bx=W-85*mm
    for lbl,val,bg,fg in [("Total HT",f"{ht:.3f} TND",LIGHT,DARK),
                           (f"TVA ({TVA_RATE}%)",f"{tva:.3f} TND",LIGHT,GRAY),
                           ("TOTAL TTC",f"{ttc:.3f} TND",DARK,WHITE)]:
        rh=9*mm if "TTC" not in lbl else 11*mm
        c.setFillColor(bg); c.rect(bx,y_cur-rh,W-15*mm-bx,rh,fill=1,stroke=0)
        c.setFillColor(fg); c.setFont("Helvetica-Bold",9 if "TTC" not in lbl else 11)
        c.drawString(bx+3*mm,y_cur-rh+3*mm,lbl); c.drawRightString(W-17*mm,y_cur-rh+3*mm,val)
        y_cur-=rh

    c.setFillColor(DARK); c.rect(0,0,W,12*mm,fill=1,stroke=0)
    c.setFillColor(RED);  c.rect(0,12*mm,W,0.8*mm,fill=1,stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold",7); c.drawString(15*mm,8*mm,"SOFEM · Partenaire des Briqueteries")
    c.drawRightString(W-15*mm,8*mm,f"{bc['bc_numero']} · {now}")
    c.save(); buf.seek(0)
    return StreamingResponse(io.BytesIO(buf.read()),media_type="application/pdf",
        headers={"Content-Disposition":f'inline; filename="{bc["bc_numero"]}.pdf"'})