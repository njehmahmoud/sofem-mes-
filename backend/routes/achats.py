"""SOFEM MES v3.0 — Module Achats Routes"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db, q, exe, serialize
from auth import require_any_role, require_manager_or_admin
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import io

router = APIRouter(prefix="/api/achats", tags=["achats"])

TVA_RATE = 19.0

# ── SCHEMAS ───────────────────────────────────────────────
class DACreate(BaseModel):
    materiau_id: Optional[int] = None
    description: str
    quantite: float
    unite: str = "pcs"
    urgence: str = "NORMAL"
    notes: Optional[str] = None
    demandeur_id: Optional[int] = None

class DAUpdate(BaseModel):
    statut: Optional[str] = None
    valideur_id: Optional[int] = None
    notes: Optional[str] = None

class BCLigne(BaseModel):
    materiau_id: Optional[int] = None
    description: str
    quantite: float
    unite: str = "pcs"
    prix_unitaire: float = 0

class BCCreate(BaseModel):
    fournisseur: str
    da_id: Optional[int] = None
    notes: Optional[str] = None
    lignes: List[BCLigne] = []

class BRLigne(BaseModel):
    bc_ligne_id: int
    quantite_recue: float

class BRCreate(BaseModel):
    bc_id: int
    date_reception: date
    statut: str = "COMPLET"
    notes: Optional[str] = None
    lignes: List[BRLigne] = []

class FACreate(BaseModel):
    bc_id: int
    fournisseur: str
    date_facture: date
    notes: Optional[str] = None

# ── NUMBER GENERATORS ────────────────────────────────────
def gen_num(db, table, col, prefix):
    last = q(db, f"SELECT {col} FROM {table} ORDER BY id DESC LIMIT 1", one=True)
    year = datetime.now().year
    try: num = int(last[col].split("-")[-1]) + 1 if last else 1
    except: num = 1
    return f"{prefix}-{year}-{str(num).zfill(3)}"

# ══════════════════════════════════════════════════════════
# DEMANDE D'ACHAT
# ══════════════════════════════════════════════════════════
@router.get("/da", dependencies=[Depends(require_any_role)])
def list_da(db=Depends(get_db)):
    return serialize(q(db, """
        SELECT da.*, m.nom materiau_nom,
               CONCAT(d.prenom,' ',d.nom) demandeur_nom,
               CONCAT(v.prenom,' ',v.nom) valideur_nom
        FROM demandes_achat da
        LEFT JOIN materiaux m ON da.materiau_id=m.id
        LEFT JOIN operateurs d ON da.demandeur_id=d.id
        LEFT JOIN operateurs v ON da.valideur_id=v.id
        ORDER BY da.created_at DESC
    """))

@router.post("/da", status_code=201, dependencies=[Depends(require_any_role)])
def create_da(data: DACreate, db=Depends(get_db)):
    numero = gen_num(db, "demandes_achat", "da_numero", "DA")
    da_id = exe(db, """INSERT INTO demandes_achat
        (da_numero,materiau_id,description,quantite,unite,urgence,notes,demandeur_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (numero, data.materiau_id, data.description, data.quantite,
         data.unite, data.urgence, data.notes, data.demandeur_id))
    return {"id": da_id, "da_numero": numero, "message": "Demande créée"}

@router.put("/da/{da_id}", dependencies=[Depends(require_manager_or_admin)])
def update_da(da_id: int, data: DAUpdate, db=Depends(get_db)):
    fields, params = [], []
    if data.statut     is not None: fields.append("statut=%s");     params.append(data.statut)
    if data.valideur_id is not None: fields.append("valideur_id=%s"); params.append(data.valideur_id)
    if data.notes      is not None: fields.append("notes=%s");      params.append(data.notes)
    if fields:
        params.append(da_id)
        exe(db, f"UPDATE demandes_achat SET {','.join(fields)} WHERE id=%s", params)
    return {"message": "DA mise à jour"}

# ══════════════════════════════════════════════════════════
# BON DE COMMANDE
# ══════════════════════════════════════════════════════════
@router.get("/bc", dependencies=[Depends(require_any_role)])
def list_bc(db=Depends(get_db)):
    bcs = serialize(q(db, """
        SELECT bc.*, da.da_numero
        FROM bons_commande bc
        LEFT JOIN demandes_achat da ON bc.da_id=da.id
        ORDER BY bc.created_at DESC
    """))
    for bc in bcs:
        bc["lignes"] = serialize(q(db, """
            SELECT bcl.*, m.nom materiau_nom
            FROM bc_lignes bcl LEFT JOIN materiaux m ON bcl.materiau_id=m.id
            WHERE bcl.bc_id=%s
        """, (bc["id"],)))
        ht = sum(float(l["quantite"]) * float(l["prix_unitaire"]) for l in bc["lignes"])
        bc["montant_ht"]  = round(ht, 3)
        bc["montant_tva"] = round(ht * TVA_RATE / 100, 3)
        bc["montant_ttc"] = round(ht * (1 + TVA_RATE / 100), 3)
    return bcs

@router.post("/bc", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_bc(data: BCCreate, db=Depends(get_db)):
    numero = gen_num(db, "bons_commande", "bc_numero", "BC")
    bc_id = exe(db, """INSERT INTO bons_commande (bc_numero,fournisseur,da_id,notes)
        VALUES (%s,%s,%s,%s)""", (numero, data.fournisseur, data.da_id, data.notes))
    for l in data.lignes:
        exe(db, """INSERT INTO bc_lignes (bc_id,materiau_id,description,quantite,unite,prix_unitaire)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (bc_id, l.materiau_id, l.description, l.quantite, l.unite, l.prix_unitaire))
    if data.da_id:
        exe(db, "UPDATE demandes_achat SET statut='ORDERED' WHERE id=%s", (data.da_id,))
    return {"id": bc_id, "bc_numero": numero, "message": "BC créé"}

@router.put("/bc/{bc_id}/statut", dependencies=[Depends(require_manager_or_admin)])
def update_bc_statut(bc_id: int, statut: str, db=Depends(get_db)):
    exe(db, "UPDATE bons_commande SET statut=%s WHERE id=%s", (statut, bc_id))
    return {"message": "BC mis à jour"}

# ══════════════════════════════════════════════════════════
# BON DE RECEPTION
# ══════════════════════════════════════════════════════════
@router.get("/br", dependencies=[Depends(require_any_role)])
def list_br(db=Depends(get_db)):
    brs = serialize(q(db, """
        SELECT br.*, bc.bc_numero, bc.fournisseur
        FROM bons_reception br
        JOIN bons_commande bc ON br.bc_id=bc.id
        ORDER BY br.created_at DESC
    """))
    for br in brs:
        br["lignes"] = serialize(q(db, """
            SELECT brl.*, bcl.description, bcl.unite, m.nom materiau_nom
            FROM br_lignes brl
            JOIN bc_lignes bcl ON brl.bc_ligne_id=bcl.id
            LEFT JOIN materiaux m ON bcl.materiau_id=m.id
            WHERE brl.br_id=%s
        """, (br["id"],)))
    return brs

@router.post("/br", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_br(data: BRCreate, db=Depends(get_db)):
    numero = gen_num(db, "bons_reception", "br_numero", "BR")
    br_id = exe(db, """INSERT INTO bons_reception (br_numero,bc_id,date_reception,statut,notes)
        VALUES (%s,%s,%s,%s,%s)""",
        (numero, data.bc_id, data.date_reception, data.statut, data.notes))

    for l in data.lignes:
        exe(db, "INSERT INTO br_lignes (br_id,bc_ligne_id,quantite_recue) VALUES (%s,%s,%s)",
            (br_id, l.bc_ligne_id, l.quantite_recue))
        # Auto update stock
        bc_ligne = q(db, "SELECT materiau_id, quantite FROM bc_lignes WHERE id=%s", (l.bc_ligne_id,), one=True)
        if bc_ligne and bc_ligne["materiau_id"]:
            mat = q(db, "SELECT stock_actuel FROM materiaux WHERE id=%s", (bc_ligne["materiau_id"],), one=True)
            if mat:
                nouveau = float(mat["stock_actuel"]) + float(l.quantite_recue)
                exe(db, "UPDATE materiaux SET stock_actuel=%s WHERE id=%s",
                    (nouveau, bc_ligne["materiau_id"]))
                exe(db, """INSERT INTO mouvements_stock
                    (materiau_id,type,quantite,stock_avant,stock_apres,motif)
                    VALUES (%s,'ENTREE',%s,%s,%s,%s)""",
                    (bc_ligne["materiau_id"], l.quantite_recue,
                     mat["stock_actuel"], nouveau, f"Réception {numero}"))

    exe(db, "UPDATE bons_commande SET statut=%s WHERE id=%s",
        ("RECU" if data.statut == "COMPLET" else "RECU_PARTIEL", data.bc_id))
    return {"id": br_id, "br_numero": numero, "message": "BR créé — stock mis à jour"}

# ══════════════════════════════════════════════════════════
# FACTURE D'ACHAT
# ══════════════════════════════════════════════════════════
@router.get("/fa", dependencies=[Depends(require_any_role)])
def list_fa(db=Depends(get_db)):
    return serialize(q(db, """
        SELECT fa.*, bc.bc_numero
        FROM factures_achat fa
        JOIN bons_commande bc ON fa.bc_id=bc.id
        ORDER BY fa.created_at DESC
    """))

@router.post("/fa", status_code=201, dependencies=[Depends(require_manager_or_admin)])
def create_fa(data: FACreate, db=Depends(get_db)):
    numero = gen_num(db, "factures_achat", "fa_numero", "FA")
    bc = q(db, "SELECT id FROM bons_commande WHERE id=%s", (data.bc_id,), one=True)
    if not bc: raise HTTPException(404, "BC non trouvé")
    lignes = q(db, "SELECT quantite, prix_unitaire FROM bc_lignes WHERE bc_id=%s", (data.bc_id,))
    ht  = sum(float(l["quantite"]) * float(l["prix_unitaire"]) for l in lignes)
    tva = round(ht * TVA_RATE / 100, 3)
    ttc = round(ht + tva, 3)
    fa_id = exe(db, """INSERT INTO factures_achat
        (fa_numero,bc_id,fournisseur,date_facture,montant_ht,tva,montant_ttc,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (numero, data.bc_id, data.fournisseur, data.date_facture, ht, tva, ttc, data.notes))
    return {"id": fa_id, "fa_numero": numero, "montant_ttc": ttc, "message": "Facture achat créée"}

@router.put("/fa/{fa_id}/payer", dependencies=[Depends(require_manager_or_admin)])
def payer_fa(fa_id: int, db=Depends(get_db)):
    exe(db, "UPDATE factures_achat SET statut='PAYEE' WHERE id=%s", (fa_id,))
    return {"message": "Facture marquée comme payée"}

# ══════════════════════════════════════════════════════════
# PDF BON DE COMMANDE
# ══════════════════════════════════════════════════════════
@router.get("/bc/{bc_id}/pdf")
def print_bc(bc_id: int, db=Depends(get_db)):
    bc = q(db, "SELECT * FROM bons_commande WHERE id=%s", (bc_id,), one=True)
    if not bc: raise HTTPException(404, "BC non trouvé")
    lignes = q(db, """SELECT bcl.*, m.nom materiau_nom FROM bc_lignes bcl
        LEFT JOIN materiaux m ON bcl.materiau_id=m.id WHERE bcl.bc_id=%s""", (bc_id,))
    bc = serialize(bc); lignes = serialize(lignes)

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas

    W, H = A4
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    RED=colors.HexColor("#D42B2B"); DARK=colors.HexColor("#111"); GRAY=colors.HexColor("#6B7280")
    LIGHT=colors.HexColor("#F9FAFB"); WHITE=colors.white; BORDER=colors.HexColor("#E5E7EB")
    now = datetime.now().strftime("%d/%m/%Y")
    ht  = sum(float(l["quantite"])*float(l["prix_unitaire"]) for l in lignes)
    tva = round(ht*TVA_RATE/100, 3); ttc = round(ht+tva, 3)

    # Header
    c.setFillColor(DARK); c.rect(0,H-38*mm,W,38*mm,fill=1,stroke=0)
    c.setFillColor(RED);  c.rect(0,H-40*mm,W,2*mm,fill=1,stroke=0)
    c.setFillColor(RED);  c.roundRect(15*mm,H-32*mm,22*mm,22*mm,4,fill=1,stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold",18); c.drawCentredString(26*mm,H-24*mm,"S")
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold",20); c.drawString(42*mm,H-22*mm,"SOFEM")
    c.setFillColor(RED);   c.setFont("Helvetica",7); c.drawString(42*mm,H-27*mm,"PARTENAIRE DES BRIQUETERIES")
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold",24); c.drawRightString(W-15*mm,H-20*mm,"BON DE COMMANDE")
    c.setFillColor(RED);   c.setFont("Helvetica-Bold",13); c.drawRightString(W-15*mm,H-27*mm,bc["bc_numero"])
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica",8); c.drawRightString(W-15*mm,H-33*mm,f"Date: {now}")

    # Fournisseur
    y=H-58*mm
    c.setFillColor(LIGHT); c.rect(0,y,W,16*mm,fill=1,stroke=0)
    c.setFillColor(GRAY);  c.setFont("Helvetica-Bold",7); c.drawString(15*mm,y+12*mm,"FOURNISSEUR")
    c.setFillColor(DARK);  c.setFont("Helvetica-Bold",11); c.drawString(15*mm,y+7*mm,bc["fournisseur"])
    c.setFillColor(GRAY);  c.setFont("Helvetica-Bold",7); c.drawRightString(W-15*mm,y+12*mm,"STATUT")
    c.setFillColor(DARK);  c.setFont("Helvetica-Bold",10); c.drawRightString(W-15*mm,y+7*mm,bc["statut"])

    # Lines table
    y_cur=y-14*mm
    c.setFillColor(DARK); c.rect(15*mm,y_cur-6*mm,W-30*mm,8*mm,fill=1,stroke=0)
    hdrs=["DESCRIPTION","QTÉ","UNITÉ","PRIX UNIT. HT","TOTAL HT"]
    cx=[15,80,120,145,170]
    for i,h in enumerate(hdrs):
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold",7); c.drawString(cx[i]*mm+2*mm,y_cur-3*mm,h)
    y_cur-=6*mm
    for idx,l in enumerate(lignes):
        rh=8*mm; y_cur-=rh
        if idx%2==0: c.setFillColor(LIGHT); c.rect(15*mm,y_cur,W-30*mm,rh,fill=1,stroke=0)
        total=round(float(l["quantite"])*float(l["prix_unitaire"]),3)
        c.setFillColor(DARK); c.setFont("Helvetica",8)
        c.drawString(cx[0]*mm+2*mm,y_cur+2.5*mm,str(l.get("materiau_nom") or l["description"])[:35])
        c.drawString(cx[1]*mm+2*mm,y_cur+2.5*mm,str(l["quantite"]))
        c.drawString(cx[2]*mm+2*mm,y_cur+2.5*mm,str(l["unite"]))
        c.drawString(cx[3]*mm+2*mm,y_cur+2.5*mm,f"{float(l['prix_unitaire']):.3f}")
        c.setFont("Helvetica-Bold",8); c.drawString(cx[4]*mm+2*mm,y_cur+2.5*mm,f"{total:.3f} TND")
        c.setStrokeColor(BORDER); c.setLineWidth(0.3); c.line(15*mm,y_cur,W-15*mm,y_cur)

    # Totals
    y_cur-=12*mm; bx=W-85*mm
    for lbl,val,bg,fg in [("Total HT",f"{ht:.3f} TND",LIGHT,DARK),
                           (f"TVA ({TVA_RATE}%)",f"{tva:.3f} TND",LIGHT,GRAY),
                           ("TOTAL TTC",f"{ttc:.3f} TND",DARK,WHITE)]:
        rh=9*mm if lbl!="TOTAL TTC" else 11*mm
        c.setFillColor(bg); c.rect(bx,y_cur-rh,W-15*mm-bx,rh,fill=1,stroke=0)
        c.setFillColor(fg); c.setFont("Helvetica-Bold",9 if lbl!="TOTAL TTC" else 11)
        c.drawString(bx+3*mm,y_cur-rh+3*mm,lbl); c.drawRightString(W-17*mm,y_cur-rh+3*mm,val)
        c.setStrokeColor(BORDER); c.setLineWidth(0.4); c.line(bx,y_cur-rh,W-15*mm,y_cur-rh)
        y_cur-=rh

    # Footer
    c.setFillColor(DARK); c.rect(0,0,W,12*mm,fill=1,stroke=0)
    c.setFillColor(RED);  c.rect(0,12*mm,W,0.8*mm,fill=1,stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold",7); c.drawString(15*mm,8*mm,"SOFEM · Partenaire des Briqueteries")
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica",7)
    c.drawString(15*mm,4*mm,"Route Sidi Salem 2.5KM · Sfax · sofem-tn.com")
    c.drawRightString(W-15*mm,8*mm,f"{bc['bc_numero']} · {now}")
    c.save(); buf.seek(0)
    return StreamingResponse(io.BytesIO(buf.read()),media_type="application/pdf",
        headers={"Content-Disposition":f'inline; filename="{bc["bc_numero"]}.pdf"'})
