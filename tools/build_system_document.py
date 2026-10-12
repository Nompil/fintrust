"""Build the formal system record and reproducible vector behaviour diagrams.

Documentation-only dependencies: reportlab, pymupdf and svglib.
"""
import html
import math
import re
from pathlib import Path
import fitz
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/EVIDENCE/12-e2e/historical-design-diagrams"
TMP = ROOT / "tmp/pdfs"
DIAGRAMS = OUT
for directory in (OUT, TMP, DIAGRAMS):
    directory.mkdir(parents=True, exist_ok=True)


def diagram(name, title, subtitle, content):
    source = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">
    <defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#35736f"/></marker></defs>
    <rect width="1200" height="800" fill="#f6f9fb"/>
    <text x="50" y="60" font-family="Helvetica" font-size="30" fill="#182c45" font-weight="bold">{title}</text>
    <text x="50" y="95" font-family="Helvetica" font-size="16" fill="#466077">{subtitle}</text>
    {content}</svg>'''
    path = DIAGRAMS / f"{name}.svg"
    path.write_text(source, encoding="utf-8")
    renderPDF.drawToFile(svg2rlg(str(path)), str(TMP / f"{name}.pdf"))
    return TMP / f"{name}.pdf"


def label(x, y, text, size=17):
    return f'<text x="{x}" y="{y}" text-anchor="middle" font-family="Helvetica" font-size="{size}" fill="#182c45">{html.escape(text)}</text>'


def box(x, y, text, width=330):
    return f'<rect x="{x}" y="{y}" width="{width}" height="52" rx="12" fill="white" stroke="#35736f" stroke-width="2"/>' + label(x+width/2, y+32, text)


def arrow(x1, y1, x2, y2, dashed=False):
    angle = math.atan2(y2-y1, x2-x1)
    bx, by = x2-10*math.cos(angle), y2-10*math.sin(angle)
    dx, dy = 4*math.sin(angle), -4*math.cos(angle)
    head = f'<polygon points="{x2},{y2} {bx+dx},{by+dy} {bx-dx},{by-dy}" fill="#35736f"/>'
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#35736f" stroke-width="2"'+(' stroke-dasharray="6 5"' if dashed else '')+'/>' + head


def behaviour_diagrams():
    body = '<circle cx="450" cy="140" r="10" fill="#182c45"/>'
    steps = [(175,"Receive UTF-8 CSV"),(265,"Validate headers, size and row count"),(365,"Validate each row"),(585,"Commit accepted rows"),(685,"Return counts and quarantine reasons")]
    for y, text in steps:
        body += box(285,y,text)
    body += arrow(450,150,450,175)+arrow(450,227,450,265)+arrow(450,317,450,365)+arrow(450,417,450,455)
    body += '<polygon points="450,455 515,490 450,525 385,490" fill="#e5f4ef" stroke="#35736f"/>' + label(450,496,"Valid?",16)
    body += arrow(450,525,450,585)+label(477,555,"Yes",14)
    body += arrow(515,490,785,490)+label(640,477,"No / DB constraint",14)+box(785,464,"Quarantine row",300)
    body += arrow(935,516,935,711)+arrow(935,711,615,711)
    body += arrow(450,637,450,685)+arrow(450,737,450,764)
    body += '<circle cx="450" cy="775" r="11" fill="none" stroke="#182c45" stroke-width="2"/><circle cx="450" cy="775" r="7" fill="#182c45"/>'
    body += box(785,265,"Reject malformed / oversized file",360)+arrow(615,291,785,291)
    body += label(960,345,"No transaction writes for file-level rejection",14)
    body += label(930,380,"Infrastructure outage: fail and retry",14)
    body += label(930,406,"S3 deployment: eventual failure destination",14)
    activity = diagram("activity", "CSV processing activity", "Current processing decisions; retry destinations require AWS deployment evidence.", body)
    body = '<rect x="315" y="145" width="590" height="580" rx="15" fill="white" stroke="#839cae"/>' + label(610,180,"FinTrust application boundary",20)
    for ax,ay,title in [(145,340,"Operations analyst"),(1050,470,"Maintainer")]:
        body += f'<circle cx="{ax}" cy="{ay-45}" r="19" fill="none" stroke="#182c45" stroke-width="2"/><path d="M{ax},{ay-26} v60 m-35,-38 h70 m-35,38 l-30,45 m30,-45 l30,45" stroke="#182c45" stroke-width="2" fill="none"/>' + label(ax,ay+95,title,16)
    for y,title in [(240,"Submit transaction export"),(340,"Review rejected rows"),(440,"Filter and inspect ledger"),(540,"Read daily insight (fixture locally)"),(640,"Review health and test evidence")]:
        body += f'<ellipse cx="610" cy="{y}" rx="230" ry="35" fill="#eef7f5" stroke="#35736f"/>' + label(610,y+6,title)
        if y<600:
            body += f'<line x1="180" y1="340" x2="380" y2="{y}" stroke="#839cae"/>'
    body += '<line x1="1015" y1="470" x2="840" y2="640" stroke="#839cae"/>'
    usecase = diagram("use_cases", "Actors and use cases", "User-story view of the local foundation; production identity and access control remain planned.",body)
    body = ""
    xs = [140,440,745,1050]
    for x,title in zip(xs,["Analyst browser","Flask local adapter","CSV processor","PostgreSQL / mock S3"]):
        body += box(x-125,150,title,250)
        body += f'<line x1="{x}" y1="202" x2="{x}" y2="715" stroke="#839cae" stroke-dasharray="7 6"/>'
    for y,a,b,title,dash in [(250,0,1,"POST /v1/upload",False),(325,1,2,"Bound file; derive content identity",False),(400,2,3,"Write validated rows",False),(470,3,2,"Accepted / constraint failures",True),(540,2,3,"Store rejected rows in quarantine",False),(610,2,1,"Counts and rejection details",True),(680,1,0,"200 JSON result (partial success possible)",True)]:
        body += arrow(xs[a],y,xs[b],y,dash)+label((xs[a]+xs[b])/2,y-12,title,14)
    body += label(600,758,"Synchronous local upload. AWS S3-triggered ingestion has a different asynchronous entry point.",17)
    sequence = diagram("upload_sequence","Local upload interaction sequence","File-level errors return 400/413; infrastructure failures return 503. No automatic scoring follows upload.",body)
    return [activity,usecase,sequence]


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="BodyRecord",fontName="Helvetica",fontSize=9.2,leading=13,spaceAfter=8,textColor=colors.HexColor("#24394c")))
styles.add(ParagraphStyle(name="CellRecord",parent=styles["BodyRecord"],fontSize=8,leading=11,spaceAfter=0))
styles["Heading1"].textColor=colors.HexColor("#182c45")
styles["Heading2"].textColor=colors.HexColor("#35736f")


def markup(value):
    value = html.escape(value)
    value = re.sub(r"\*\*(.*?)\*\*",r"<b>\1</b>",value)
    value = re.sub(r"`([^`]+)`",r'<font face="Courier">\1</font>',value)
    return value


def footer(canvas, doc):
    canvas.setStrokeColor(colors.HexColor("#c9d6de"))
    canvas.line(42,40,553,40)
    canvas.setFont("Helvetica",8)
    canvas.setFillColor(colors.HexColor("#466077"))
    canvas.drawString(42,27,"FINTRUST  |  Engineering record  |  Local implementation")
    canvas.drawRightString(553,27,str(doc.page))


def main():
    story = [Spacer(1,75),Paragraph("FINTRUST",styles["Title"]),Spacer(1,18),
             Paragraph("Transaction Insights and Risk Monitoring",styles["Heading1"]),
             Paragraph("System design and engineering record",styles["Heading2"]),Spacer(1,30),
             Paragraph("Version 0.2 | 30 September 2026",styles["BodyRecord"]),
             Paragraph("Requirements, SDLC, user stories, database decisions, API contract, failure handling, service selection, testing and delivery.",styles["BodyRecord"]),Spacer(1,24),
             Paragraph("Evidence boundary",styles["Heading2"]),
             Paragraph("The local foundation uses real PostgreSQL and simulated AWS services. Cloud deployment, automated risk scoring, notifications and scheduled reports are not complete. Architecture diagrams distinguish implemented foundations from the proposed target.",styles["BodyRecord"]),PageBreak()]
    lines=(ROOT/"docs/system_design.md").read_text(encoding="utf-8").splitlines()
    i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line or line.startswith("# ") or line.startswith("Version "):
            i+=1; continue
        if line.startswith("| "):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith("|"):
                cells=lines[i].strip().strip("|").split("|")
                if not all(re.fullmatch(r"[\s:-]+",c) for c in cells):
                    rows.append([Paragraph(markup(c.strip()),styles["CellRecord"]) for c in cells])
                i+=1
            table=Table(rows,colWidths=[511/len(rows[0])]*len(rows[0]),repeatRows=1,hAlign="LEFT")
            table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#dceee9")),("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#c9d6de")),("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
            story.extend([table,Spacer(1,12)]);continue
        if line.startswith("## "):
            story.append(Paragraph(markup(line[3:]),styles["Heading1"]))
        elif line.startswith("### "):
            story.append(Paragraph(markup(line[4:]),styles["Heading2"]))
        else:
            story.append(Paragraph(markup(line),styles["BodyRecord"]))
        i+=1
    narrative=TMP/"system_narrative.pdf"
    SimpleDocTemplate(str(narrative),pagesize=(595,842),leftMargin=42,rightMargin=42,topMargin=42,bottomMargin=54,title="FinTrust System Design and Engineering Record",author="FinTrust").build(story,onFirstPage=footer,onLaterPages=footer)
    final=fitz.open(narrative)
    for path in [OUT/"fintrust_architecture_and_erd.pdf",*behaviour_diagrams()]:
        with fitz.open(path) as appendix:
            final.insert_pdf(appendix)
    target=OUT/"fintrust_system_documentation.pdf"
    final.save(target)
    for i,page in enumerate(final):
        page.get_pixmap(matrix=fitz.Matrix(1,1)).save(TMP/f"system-{i+1:02}.png")
    print(f"Created {target}: {len(final)} pages")


if __name__=="__main__":
    main()
