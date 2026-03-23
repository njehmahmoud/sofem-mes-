"""
SOFEM MES v3.0 — Facture Routes
- Single OF invoice (interne/client)
- Multi-OF grouped client invoice
SMARTMOVE · Mahmoud Njeh
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db, q, serialize
from auth import require_any_role, get_pdf_user, require_manager_or_admin
from pydantic import BaseModel
from typing import List
from datetime import datetime
import io

router = APIRouter(prefix="/api/facture", tags=["facture"])


def get_of_data(of_id, db):
    of = q(db, """SELECT o.*, p.nom produit_nom, p.code produit_code,
        p.prix_vente_ht,
        CONCAT(op.prenom,' ',op.nom) operateur_nom,
        c.nom client_nom, c.matricule_fiscal client_mf,
        c.adresse client_adresse, c.ville client_ville,
        c.telephone client_tel
        FROM ordres_fabrication o
        JOIN produits p ON o.produit_id=p.id
        LEFT JOIN operateurs op ON o.chef_projet_id=op.id
        LEFT JOIN clients c ON c.id=o.client_id
        WHERE o.id=%s""", (of_id,), one=True)
    if not of: raise HTTPException(404, f"OF {of_id} non trouvé")
    of["etapes"] = q(db, """
            SELECT op2.operation_nom etape, op2.statut,
                   GROUP_CONCAT(CONCAT(o2.prenom,' ',o2.nom) SEPARATOR ', ') operateur_nom,
                   op2.duree_reelle
            FROM of_operations op2
            LEFT JOIN op_operateurs oo ON oo.operation_id = op2.id
            LEFT JOIN operateurs o2 ON o2.id = oo.operateur_id
            WHERE op2.of_id=%s
            GROUP BY op2.id ORDER BY op2.ordre""", (of_id,))
    return serialize(of)

def draw_header(c, W, H, colors, title, numero, now):
    RED=colors.HexColor("#D42B2B"); DARK=colors.HexColor("#111"); WHITE=colors.white
    c.setFillColor(DARK); c.rect(0,H-38*2.835,W,38*2.835,fill=1,stroke=0)
    c.setFillColor(RED);  c.rect(0,H-40*2.835,W,2*2.835,fill=1,stroke=0)
    c.setFillColor(RED);  c.roundRect(15*2.835,H-32*2.835,22*2.835,22*2.835,4,fill=1,stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold",18); c.drawCentredString(26*2.835,H-24*2.835,"S")
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold",20); c.drawString(42*2.835,H-22*2.835,"SOFEM")
    c.setFillColor(RED); c.setFont("Helvetica",7); c.drawString(42*2.835,H-27*2.835,"PARTENAIRE DES BRIQUETERIES")
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica",7)
    c.drawString(42*2.835,H-32*2.835,"Route Sidi Salem 2.5KM · Sfax · +216 74 469 181")
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold",26); c.drawRightString(W-15*2.835,H-20*2.835,title)
    c.setFillColor(RED); c.setFont("Helvetica-Bold",13); c.drawRightString(W-15*2.835,H-27*2.835,numero)
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica",8)
    c.drawRightString(W-15*2.835,H-33*2.835,f"Date: {now}")

def draw_footer(c, W, colors, numero, now,
                S_NOM="SOFEM", S_TAG="Partenaire des Briqueteries",
                S_ADDR="Route Sidi Salem 2.5KM", S_VILLE="Sfax",
                S_WEB="sofem-tn.com", S_MF="000000000/A/M/000",
                PDF_PIED="SOFEM MES v6.0 · SMARTMOVE"):
    RED=colors.HexColor("#D42B2B"); DARK=colors.HexColor("#111"); WHITE=colors.white
    c.setFillColor(DARK); c.rect(0,0,W,14*2.835,fill=1,stroke=0)
    c.setFillColor(RED);  c.rect(0,14*2.835,W,0.8*2.835,fill=1,stroke=0)
    c.setFillColor(WHITE); c.setFont("Helvetica-Bold",7); c.drawString(15*2.835,9*2.835,f"{S_NOM} · {S_TAG}")
    c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica",7)
    c.drawString(15*2.835,5*2.835,f"{S_ADDR} · {S_VILLE} · {S_WEB} · MF: {S_MF}")
    c.drawRightString(W-15*2.835,9*2.835,f"{numero} · {now}")
    c.drawRightString(W-15*2.835,5*2.835,PDF_PIED)

# ── SINGLE OF FACTURE ─────────────────────────────────────
@router.get("/{of_id}")
def get_facture(of_id: int, type: str = "interne", token: str=None, user=Depends(get_pdf_user), db=Depends(get_db)):
    of = get_of_data(of_id, db)
    # Load settings
    from routes.settings import get_all_settings
    cfg = get_all_settings(db)
    S_NOM  = cfg.get("societe_nom",       "SOFEM")
    S_TAG  = cfg.get("societe_tagline",   "Partenaire des Briqueteries")
    S_ADDR = cfg.get("societe_adresse",   "Route Sidi Salem 2.5KM")
    S_VILLE= cfg.get("societe_ville",     "Sfax")
    S_TEL  = cfg.get("societe_telephone", "+216 74 469 181")
    S_MF   = cfg.get("societe_mf",        "000000000/A/M/000")
    S_WEB  = cfg.get("societe_website",   "sofem-tn.com")
    TVA_RATE = float(cfg.get("tva_rate",  19)) / 100
    PDF_PIED = cfg.get("pdf_pied_custom", "SOFEM MES v6.0 · SMARTMOVE")

    if of["statut"] != "COMPLETED":
        raise HTTPException(400, "Facture disponible uniquement pour les OFs terminés")
    # Fetch actual BOM for this OF (of_bom table), fallback to product BOM
    materiaux = serialize(q(db, """
        SELECT m.nom, m.code, m.unite,
               ob.quantite_requise AS quantite_estimee
        FROM of_bom ob
        JOIN materiaux m ON m.id = ob.materiau_id
        WHERE ob.of_id = %s
        ORDER BY m.nom
    """, (of_id,)))
    # If of_bom is empty, fall back to product BOM × quantite
    if not materiaux:
        materiaux = serialize(q(db, """
            SELECT m.nom, m.code, m.unite,
                   ROUND(b.quantite_par_unite * %s, 3) AS quantite_estimee
            FROM bom b
            JOIN materiaux m ON m.id = b.materiau_id
            JOIN produits p ON p.id = b.produit_id
            JOIN ordres_fabrication o ON o.produit_id = p.id
            WHERE o.id = %s
            ORDER BY m.nom
        """, (of["quantite"], of_id)))

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas

    W, H = A4
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    RED=colors.HexColor("#D42B2B"); DARK=colors.HexColor("#111"); GRAY=colors.HexColor("#6B7280")
    LIGHT=colors.HexColor("#F9FAFB"); WHITE=colors.white; BORDER=colors.HexColor("#E5E7EB")
    GREEN=colors.HexColor("#16a34a")
    now = datetime.now().strftime("%d / %m / %Y")
    fac_num = f"FAC-{of['numero'].replace('OF-','')}"
    suffix = "-INTERNE" if type == "interne" else "-CLIENT"

    draw_header(c, W, H, colors, "FACTURE", fac_num+suffix, now)

    FOOTER_H = 14*2.835   # footer height in points
    SAFE_Y   = FOOTER_H + 30*mm  # trigger new page below this

    page_num = [1]

    def fac_draw_footer():
        draw_footer(c,W,colors,fac_num+suffix,now,S_NOM,S_TAG,S_ADDR,S_VILLE,S_WEB,S_MF,PDF_PIED)

    def fac_new_page():
        fac_draw_footer()
        c.showPage()
        page_num[0] += 1
        # Mini continuation header
        c.setFillColor(colors.HexColor("#111")); c.rect(0, H-12*mm, W, 12*mm, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#D42B2B")); c.rect(0, H-13*mm, W, 1*mm, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 9)
        c.drawString(15*mm, H-8*mm, f"{S_NOM}  ·  FACTURE {fac_num+suffix}  (suite)")
        c.setFillColor(colors.HexColor("#9CA3AF")); c.setFont("Helvetica", 7)
        c.drawRightString(W-15*mm, H-8*mm, f"Page {page_num[0]}")
        return H - 18*mm

    # Info band
    y = H - 63*mm
    c.setFillColor(LIGHT); c.rect(0,y,W,22*mm,fill=1,stroke=0)
    c.setStrokeColor(BORDER); c.setLineWidth(0.5)
    c.line(0,y,W,y); c.line(0,y+22*mm,W,y+22*mm)

    def icol(lbl,val,sub,x):
        c.setFillColor(GRAY); c.setFont("Helvetica-Bold",7); c.drawString(x,y+18*mm,lbl.upper())
        c.setFillColor(DARK); c.setFont("Helvetica-Bold",10); c.drawString(x,y+13*mm,str(val)[:30])
        c.setFillColor(GRAY); c.setFont("Helvetica",7.5)
        for i,line in enumerate(str(sub).split('\n')):
            c.drawString(x,y+8*mm-i*4*mm,line[:40])

    icol("OF",of["numero"],f"Créé: {str(of.get('created_at',''))[:10]}",15*mm)
    icol("Produit",of["produit_nom"],f"Code: {of.get('produit_code','—')}\nAtelier: {of.get('atelier','—')}",75*mm)
    icol("Opérateur",of.get("operateur_nom","—"),f"Échéance: {of.get('date_echeance','—')}\nPriorité: {of.get('priorite','—')}",145*mm)

    # KPIs
    y_kpi = y - 18*mm
    kpis=[("QUANTITÉ PRODUITE",f"{of['quantite']} pcs",RED),("STATUT","TERMINÉ ✓",GREEN),("N° FACTURE",fac_num+suffix,DARK)]
    bw=(W-30*mm)/3
    for i,(lbl,val,col) in enumerate(kpis):
        bx=15*mm+i*bw
        c.setFillColor(LIGHT); c.roundRect(bx,y_kpi,bw-3*mm,14*mm,3,fill=1,stroke=0)
        c.setStrokeColor(BORDER); c.setLineWidth(0.4); c.roundRect(bx,y_kpi,bw-3*mm,14*mm,3,fill=0,stroke=1)
        c.setFillColor(GRAY); c.setFont("Helvetica-Bold",7); c.drawString(bx+3*mm,y_kpi+10*mm,lbl)
        c.setFillColor(col); c.setFont("Helvetica-Bold",11); c.drawString(bx+3*mm,y_kpi+4*mm,val)

    y_cur = y_kpi - 10*mm

    def sec_title(title, y):
        c.setFillColor(RED); c.rect(15*mm,y-0.5*mm,3*mm,5*mm,fill=1,stroke=0)
        c.setFillColor(DARK); c.setFont("Helvetica-Bold",9); c.drawString(20*mm,y,title)
        return y - 8*mm

    if type == "interne":
        y_cur = sec_title("ÉTAPES DE PRODUCTION", y_cur)
        cols_e=[15*mm,75*mm,130*mm,175*mm]
        c.setFillColor(DARK); c.rect(15*mm,y_cur-6*mm,W-30*mm,8*mm,fill=1,stroke=0)
        for i,h in enumerate(["ÉTAPE","STATUT","OPÉRATEUR","DURÉE"]):
            c.setFillColor(WHITE); c.setFont("Helvetica-Bold",7); c.drawString(cols_e[i]+2*mm,y_cur-3*mm,h)
        y_cur-=6*mm
        for idx,e in enumerate(of["etapes"]):
            if y_cur < SAFE_Y:
                y_cur = fac_new_page()
                # re-draw ops table header
                c.setFillColor(DARK); c.rect(15*mm,y_cur-6*mm,W-30*mm,8*mm,fill=1,stroke=0)
                for i,h in enumerate(["ÉTAPE","STATUT","OPÉRATEUR","DURÉE"]):
                    c.setFillColor(WHITE); c.setFont("Helvetica-Bold",7); c.drawString(cols_e[i]+2*mm,y_cur-3*mm,h)
                y_cur-=6*mm
            sn = e.get("etape") or e.get("operation_nom","—")
            rh=8*mm; y_cur-=rh
            if idx%2==0: c.setFillColor(LIGHT); c.rect(15*mm,y_cur,W-30*mm,rh,fill=1,stroke=0)
            duree = "—"
            if e.get("duree_reelle"):
                mins = int(e["duree_reelle"])
                duree = f"{mins//60}h {mins%60}min" if mins >= 60 else f"{mins} min"
            elif e.get("debut") and e.get("fin"):
                try:
                    def parse_dt(d):
                        if isinstance(d, str):
                            return datetime.fromisoformat(d.replace('Z','').replace('T',' '))
                        return d
                    mins = int((parse_dt(e["fin"]) - parse_dt(e["debut"])).total_seconds() / 60)
                    duree = f"{mins//60}h {mins%60}min" if mins >= 60 else f"{mins} min"
                except: pass
            st_icon="✓ TERMINÉ" if e["statut"]=="COMPLETED" else "⏳ EN COURS" if e["statut"]=="IN_PROGRESS" else "— EN ATTENTE"
            st_col=GREEN if e["statut"]=="COMPLETED" else RED if e["statut"]=="IN_PROGRESS" else GRAY
            c.setFillColor(DARK); c.setFont("Helvetica-Bold",8); c.drawString(cols_e[0]+2*mm,y_cur+2.5*mm,sn)
            c.setFillColor(st_col); c.setFont("Helvetica",7.5); c.drawString(cols_e[1]+2*mm,y_cur+2.5*mm,st_icon)
            c.setFillColor(DARK); c.setFont("Helvetica",7.5); c.drawString(cols_e[2]+2*mm,y_cur+2.5*mm,str(e.get("operateur_nom") or "—")[:20])
            c.setFont("Helvetica-Bold",7.5); c.drawString(cols_e[3]+2*mm,y_cur+2.5*mm,duree)
            c.setStrokeColor(BORDER); c.setLineWidth(0.3); c.line(15*mm,y_cur,W-15*mm,y_cur)

        y_cur-=10*mm
        if y_cur < SAFE_Y + 30*mm: y_cur = fac_new_page()
        y_cur=sec_title("MATÉRIAUX CONSOMMÉS (ESTIMATIF)",y_cur)
        cols_m=[15*mm,100*mm,145*mm,175*mm]
        c.setFillColor(DARK); c.rect(15*mm,y_cur-6*mm,W-30*mm,8*mm,fill=1,stroke=0)
        for i,h in enumerate(["MATÉRIAU","CODE","UNITÉ","QTÉ ESTIMÉE"]):
            c.setFillColor(WHITE); c.setFont("Helvetica-Bold",7); c.drawString(cols_m[i]+2*mm,y_cur-3*mm,h)
        y_cur-=6*mm
        for idx,m in enumerate(materiaux):
            if y_cur < SAFE_Y:
                y_cur = fac_new_page()
                c.setFillColor(DARK); c.rect(15*mm,y_cur-6*mm,W-30*mm,8*mm,fill=1,stroke=0)
                for i,h in enumerate(["MATÉRIAU","CODE","UNITÉ","QTÉ ESTIMÉE"]):
                    c.setFillColor(WHITE); c.setFont("Helvetica-Bold",7); c.drawString(cols_m[i]+2*mm,y_cur-3*mm,h)
                y_cur-=6*mm
            cons=float(m.get("quantite_estimee") or 0)
            rh=8*mm; y_cur-=rh
            if idx%2==0: c.setFillColor(LIGHT); c.rect(15*mm,y_cur,W-30*mm,rh,fill=1,stroke=0)
            c.setFillColor(DARK); c.setFont("Helvetica",7.5)
            c.drawString(cols_m[0]+2*mm,y_cur+2.5*mm,str(m.get("nom",""))[:35])
            c.drawString(cols_m[1]+2*mm,y_cur+2.5*mm,str(m.get("code","—")))
            c.drawString(cols_m[2]+2*mm,y_cur+2.5*mm,str(m.get("unite","—")))
            c.setFont("Helvetica-Bold",7.5); c.drawString(cols_m[3]+2*mm,y_cur+2.5*mm,str(cons))
            c.setStrokeColor(BORDER); c.setLineWidth(0.3); c.line(15*mm,y_cur,W-15*mm,y_cur)

    # ── DÉTAIL FINANCIER — needs ~90mm, force new page if not enough ──
    FINANCIAL_NEEDED = 90*mm
    if y_cur < SAFE_Y + FINANCIAL_NEEDED:
        y_cur = fac_new_page()

    y_cur-=14*mm
    lbl_sec="DÉTAIL FINANCIER" if type=="interne" else "FACTURE CLIENT"
    y_cur=sec_title(lbl_sec,y_cur)
    ht=float(of.get('prix_vente_ht') or 85.0)*of["quantite"]; tva=ht*TVA_RATE; ttc=ht+tva
    cols_p=[15*mm,90*mm,130*mm,165*mm]
    c.setFillColor(DARK); c.rect(15*mm,y_cur-6*mm,W-30*mm,8*mm,fill=1,stroke=0)
    for i,h in enumerate(["DÉSIGNATION","QTÉ","PRIX UNIT. HT","TOTAL HT"]):
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold",7); c.drawString(cols_p[i]+2*mm,y_cur-3*mm,h)
    y_cur-=14*mm
    c.setFillColor(LIGHT); c.rect(15*mm,y_cur,W-30*mm,8*mm,fill=1,stroke=0)
    c.setFillColor(DARK); c.setFont("Helvetica",8)
    c.drawString(cols_p[0]+2*mm,y_cur+2.5*mm,f"Fabrication {of['produit_nom']} — {of['numero']}")
    c.drawString(cols_p[1]+2*mm,y_cur+2.5*mm,str(of["quantite"]))
    c.drawString(cols_p[2]+2*mm,y_cur+2.5*mm,f"{float(of.get('prix_vente_ht') or 85.0):.3f} TND")
    c.setFont("Helvetica-Bold",8); c.drawString(cols_p[3]+2*mm,y_cur+2.5*mm,f"{ht:.3f} TND")

    y_cur-=12*mm; bx=W-85*mm
    tva_label = f"TVA ({round(TVA_RATE*100)}%)"
    for lbl,val,bg,fg in [("Total HT",f"{ht:.3f} TND",LIGHT,DARK),(tva_label,f"{tva:.3f} TND",LIGHT,GRAY),("TOTAL TTC",f"{ttc:.3f} TND",DARK,WHITE)]:
        rh=9*mm if lbl!="TOTAL TTC" else 11*mm
        c.setFillColor(bg); c.rect(bx,y_cur-rh,W-15*mm-bx,rh,fill=1,stroke=0)
        c.setFillColor(fg); c.setFont("Helvetica-Bold",9 if lbl!="TOTAL TTC" else 11)
        c.drawString(bx+3*mm,y_cur-rh+3*mm,lbl); c.drawRightString(W-17*mm,y_cur-rh+3*mm,val)
        c.setStrokeColor(BORDER); c.setLineWidth(0.4); c.line(bx,y_cur-rh,W-15*mm,y_cur-rh)
        y_cur-=rh

    # Signature
    y_sig=y_cur-16*mm
    c.setStrokeColor(BORDER); c.setLineWidth(0.5)
    c.roundRect(W-75*mm,y_sig-22*mm,60*mm,22*mm,3,fill=0,stroke=1)
    c.setFillColor(GRAY); c.setFont("Helvetica",8); c.drawCentredString(W-45*mm,y_sig-6*mm,"Signature & Cachet")
    c.line(W-70*mm,y_sig-18*mm,W-20*mm,y_sig-18*mm)

    fac_draw_footer()
    c.save(); buf.seek(0)
    return StreamingResponse(io.BytesIO(buf.read()),media_type="application/pdf",
        headers={"Content-Disposition":f'inline; filename="{fac_num}{suffix}.pdf"'})

# ── MULTI-OF GROUPED CLIENT INVOICE ──────────────────────
class MultiOFRequest(BaseModel):
    of_ids: List[int]

@router.post("/grouped")
def get_facture_groupee(data: MultiOFRequest, db=Depends(get_db)):
    if not data.of_ids:
        raise HTTPException(400, "Aucun OF sélectionné")

    ofs = []
    for oid in data.of_ids:
        of = get_of_data(oid, db)
        if of["statut"] != "COMPLETED":
            raise HTTPException(400, f"OF {of['numero']} n'est pas terminé")
        ofs.append(of)

    # Load company settings for footer
    from routes.settings import get_all_settings
    cfg = get_all_settings(db)
    S_NOM   = cfg.get("societe_nom",       "SOFEM")
    S_TAG   = cfg.get("societe_tagline",   "Partenaire des Briqueteries")
    S_ADDR  = cfg.get("societe_adresse",   "Route Sidi Salem 2.5KM")
    S_VILLE = cfg.get("societe_ville",     "Sfax")
    S_WEB   = cfg.get("societe_website",   "sofem-tn.com")
    S_MF    = cfg.get("societe_mf",        "000000000/A/M/000")
    PDF_PIED = cfg.get("pdf_pied_custom",  "SOFEM MES v6.0 · SMARTMOVE")
    TVA_RATE  = float(cfg.get("tva_rate", 19)) / 100

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas

    W, H = A4
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    RED=colors.HexColor("#D42B2B"); DARK=colors.HexColor("#111"); GRAY=colors.HexColor("#6B7280")
    LIGHT=colors.HexColor("#F9FAFB"); WHITE=colors.white; BORDER=colors.HexColor("#E5E7EB")
    GREEN=colors.HexColor("#16a34a")

    now = datetime.now().strftime("%d / %m / %Y")
    fac_num = f"FAC-GROUP-{datetime.now().strftime('%Y%m%d%H%M')}"
    total_ht  = sum(float(of.get('prix_vente_ht') or 85.0) * of["quantite"] for of in ofs)
    total_tva = round(total_ht * TVA_RATE, 3)
    total_ttc = round(total_ht + total_tva, 3)

    draw_header(c,W,H,colors,"FACTURE GROUPÉE CLIENT",fac_num,now)

    y=H-63*mm
    c.setFillColor(LIGHT); c.rect(0,y,W,16*mm,fill=1,stroke=0)
    c.setStrokeColor(BORDER); c.setLineWidth(0.5)
    c.line(0,y,W,y); c.line(0,y+16*mm,W,y+16*mm)
    c.setFillColor(GRAY);  c.setFont("Helvetica-Bold",7); c.drawString(15*mm,y+12*mm,"CLIENT")
    c.setFillColor(DARK);  c.setFont("Helvetica-Bold",11); c.drawString(15*mm,y+7*mm,"SOFEM")
    c.setFillColor(GRAY);  c.setFont("Helvetica",8); c.drawString(15*mm,y+3*mm,"Route Sidi Salem 2.5KM · Sfax · +216 74 469 181")
    c.setFillColor(GRAY);  c.setFont("Helvetica-Bold",7); c.drawRightString(W-15*mm,y+12*mm,f"{len(ofs)} ORDRES FACTURÉS")
    c.setFillColor(RED);   c.setFont("Helvetica-Bold",11); c.drawRightString(W-15*mm,y+7*mm,f"TOTAL TTC: {total_ttc:.3f} TND")

    y_cur=y-14*mm
    c.setFillColor(RED); c.rect(15*mm,y_cur-0.5*mm,3*mm,5*mm,fill=1,stroke=0)
    c.setFillColor(DARK); c.setFont("Helvetica-Bold",9); c.drawString(20*mm,y_cur,"DÉTAIL DES ORDRES DE FABRICATION")
    y_cur-=10*mm

    cols=[15*mm,65*mm,115*mm,140*mm,165*mm]
    hdrs=["N° OF","PRODUIT","QTÉ","PRIX UNIT. HT","TOTAL HT"]
    c.setFillColor(DARK); c.rect(15*mm,y_cur-6*mm,W-30*mm,8*mm,fill=1,stroke=0)
    for i,h in enumerate(hdrs):
        c.setFillColor(WHITE); c.setFont("Helvetica-Bold",7.5); c.drawString(cols[i]+2*mm,y_cur-3*mm,h)
    y_cur-=6*mm

    for idx,of in enumerate(ofs):
        ht=float(of.get('prix_vente_ht') or 85.0)*of["quantite"]; rh=8*mm; y_cur-=rh
        if idx%2==0: c.setFillColor(LIGHT); c.rect(15*mm,y_cur,W-30*mm,rh,fill=1,stroke=0)
        c.setFillColor(RED);  c.setFont("Helvetica-Bold",8); c.drawString(cols[0]+2*mm,y_cur+2.5*mm,of["numero"])
        c.setFillColor(DARK); c.setFont("Helvetica",8)
        c.drawString(cols[1]+2*mm,y_cur+2.5*mm,of["produit_nom"][:25])
        c.drawString(cols[2]+2*mm,y_cur+2.5*mm,str(of["quantite"]))
        c.drawString(cols[3]+2*mm,y_cur+2.5*mm,f"{float(of.get('prix_vente_ht') or 85.0):.3f}")
        c.setFont("Helvetica-Bold",8); c.drawString(cols[4]+2*mm,y_cur+2.5*mm,f"{ht:.3f} TND")
        c.setStrokeColor(BORDER); c.setLineWidth(0.3); c.line(15*mm,y_cur,W-15*mm,y_cur)

    # Totals
    y_cur-=14*mm; bx=W-85*mm
    for lbl,val,bg,fg in [("Total HT",f"{total_ht:.3f} TND",LIGHT,DARK),(f"TVA (19%)",f"{total_tva:.3f} TND",LIGHT,GRAY),("TOTAL TTC",f"{total_ttc:.3f} TND",DARK,WHITE)]:
        rh=9*mm if lbl!="TOTAL TTC" else 12*mm
        c.setFillColor(bg); c.rect(bx,y_cur-rh,W-15*mm-bx,rh,fill=1,stroke=0)
        c.setFillColor(fg); c.setFont("Helvetica-Bold",9 if lbl!="TOTAL TTC" else 12)
        c.drawString(bx+3*mm,y_cur-rh+3*mm,lbl); c.drawRightString(W-17*mm,y_cur-rh+3*mm,val)
        c.setStrokeColor(BORDER); c.setLineWidth(0.4); c.line(bx,y_cur-rh,W-15*mm,y_cur-rh)
        y_cur-=rh

    # Signature
    y_sig=y_cur-16*mm
    c.setStrokeColor(BORDER); c.setLineWidth(0.5)
    c.roundRect(W-75*mm,y_sig-22*mm,60*mm,22*mm,3,fill=0,stroke=1)
    c.setFillColor(GRAY); c.setFont("Helvetica",8); c.drawCentredString(W-45*mm,y_sig-6*mm,"Signature & Cachet")
    c.line(W-70*mm,y_sig-18*mm,W-20*mm,y_sig-18*mm)

    draw_footer(c,W,colors,fac_num,now,S_NOM,S_TAG,S_ADDR,S_VILLE,S_WEB,S_MF,PDF_PIED)
    c.save(); buf.seek(0)
    return StreamingResponse(io.BytesIO(buf.read()),media_type="application/pdf",
        headers={"Content-Disposition":f'inline; filename="{fac_num}.pdf"'})