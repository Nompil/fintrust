"""Rebuild diagrams: pip install reportlab pillow pymupdf.

Optional first argument: path to the official AWS July 2026 icon ZIP.
Subsequent builds use the selected icons saved in docs/diagrams/aws-icons/.
"""
from pathlib import Path
import base64
import html
import sys
import zipfile
import xml.etree.ElementTree as ET

from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/diagrams"
ICONS = OUT / "aws-icons"
PDF = ROOT / "output/pdf/fintrust_architecture_and_erd.pdf"
W, H = 1440, 900
SERVICES = {
    "s3": "Amazon-Simple-Storage-Service", "lambda": "AWS-Lambda",
    "rds": "Amazon-RDS", "ddb": "Amazon-DynamoDB",
    "sqs": "Amazon-Simple-Queue-Service", "api": "Amazon-API-Gateway",
    "cw": "Amazon-CloudWatch", "iam": "AWS-Identity-and-Access-Management",
    "ssm": "AWS-Systems-Manager", "kms": "AWS-Key-Management-Service",
    "event": "Amazon-EventBridge", "ses": "Amazon-Simple-Email-Service",
}
for directory in (OUT, ICONS, PDF.parent, ROOT / "tmp/pdfs"):
    directory.mkdir(parents=True, exist_ok=True)
if len(sys.argv) > 1:
    with zipfile.ZipFile(sys.argv[1]) as pack:
        for key, service in SERVICES.items():
            suffix = f"/Arch_{service}_64@5x.png"
            member = next(n for n in pack.namelist() if n.startswith("Architecture-Service") and n.endswith(suffix))
            (ICONS / f"{key}.png").write_bytes(pack.read(member))

c = canvas.Canvas(str(PDF), pagesize=(W, H))
c.setTitle("FinTrust | Day 1-3 architecture and relational model")
c.setAuthor("FinTrust project")
mxfile = ET.Element("mxfile", host="app.diagrams.net")
svg = []
cells = None


def cell(value, style, x, y, w, h):
    node = ET.SubElement(cells, "mxCell", id=str(len(cells)), value=value, style=style, vertex="1", parent="1")
    ET.SubElement(node, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), **{"as": "geometry"})


def rect(x, y, w, h, fill="#ffffff", stroke="#cbd5e1"):
    c.setFillColor(HexColor(fill)); c.setStrokeColor(HexColor(stroke))
    c.rect(x, H-y-h, w, h, fill=1, stroke=1)
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}"/>')
    cell("", f"rounded=0;fillColor={fill};strokeColor={stroke};", x,y,w,h)


def text(x, y, value, size=16, color="#182c45", bold=False):
    c.setFillColor(HexColor(color)); c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, H-y, value)
    svg.append(f'<text x="{x}" y="{y}" font-family="Arial" font-size="{size}" fill="{color}" font-weight="{700 if bold else 400}">{html.escape(value)}</text>')
    cell(value, f"text;html=0;align=left;verticalAlign=middle;whiteSpace=wrap;fontSize={size};fontColor={color};fontStyle={1 if bold else 0};",x,y-size, max(80,len(value)*size*.56),size+5)


def line(points, label=None, dashed=False, arrow=True):
    c.setStrokeColor(HexColor("#537086")); c.setLineWidth(1.6)
    c.setDash(5,3) if dashed else c.setDash()
    path = c.beginPath(); path.moveTo(points[0][0], H-points[0][1])
    for x,y in points[1:]: path.lineTo(x,H-y)
    c.drawPath(path)
    svg.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" fill="none" stroke="#537086" stroke-width="1.6"' + (' stroke-dasharray="5,3"' if dashed else '') + '/>')
    c.setDash()
    if arrow:
        import math
        x,y=points[-1]; x0,y0=points[-2]; a=math.atan2(y-y0,x-x0)
        for angle in (a+.5,a-.5):
            line([(x,y),(x-9*math.cos(angle),y-9*math.sin(angle))],arrow=False)
    node=ET.SubElement(cells,"mxCell",id=str(len(cells)),style=f"edgeStyle=none;endArrow={'classic' if arrow else 'none'};dashed={int(dashed)};strokeColor=#537086;",edge="1",parent="1")
    geo=ET.SubElement(node,"mxGeometry",relative="1",**{"as":"geometry"})
    for name,p in (("sourcePoint",points[0]),("targetPoint",points[-1])):
        ET.SubElement(geo,"mxPoint",x=str(p[0]),y=str(p[1]),**{"as":name})
    if len(points)>2:
        arr=ET.SubElement(geo,"Array",**{"as":"points"})
        for p in points[1:-1]: ET.SubElement(arr,"mxPoint",x=str(p[0]),y=str(p[1]))
    if label: text(*label, size=13)


def node(x,y,key,title,subtitle,w=220):
    rect(x,y,w,100)
    filename=ICONS/f"{key}.png"
    c.drawImage(str(filename),x+14,H-y-67,48,48,mask="auto")
    data=base64.b64encode(filename.read_bytes()).decode()
    svg.append(f'<image x="{x+14}" y="{y+19}" width="48" height="48" href="data:image/png;base64,{data}"/>')
    cell("",f"shape=image;image=data:image/png,{data};",x+14,y+19,48,48)
    from reportlab.pdfbase.pdfmetrics import stringWidth
    font_size = min(16, 16 * (w-84) / max(1, stringWidth(title, "Helvetica-Bold", 16)))
    text(x+73,y+35,title,font_size,bold=True)
    text(x+14,y+84,subtitle,13)


def start(name,title,subtitle):
    global svg,cells
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    diagram=ET.SubElement(mxfile,"diagram",name=name)
    model=ET.SubElement(diagram,"mxGraphModel",page="1",pageWidth=str(W),pageHeight=str(H))
    cells=ET.SubElement(model,"root"); ET.SubElement(cells,"mxCell",id="0"); ET.SubElement(cells,"mxCell",id="1",parent="0")
    rect(0,0,W,H,"#f8fafc","#f8fafc")
    rect(0,0,W,112,"#182c45","#182c45")
    text(40,48,title,28,"#ffffff",True)
    text(40,81,subtitle,16,"#c9d9e7")


def end(filename,number):
    text(40,866,"FINTRUST  |  30 September 2026  |  Synthetic data only",13)
    text(1220,866,f"DESIGN  /  {number:02}",13)
    (OUT / f"{filename}.svg").write_text("\n".join(svg)+"</svg>",encoding="utf-8")
    c.showPage()


start("Day 1-3","01 / Day 1-3 implementation","Application flow and provisioning scripts in the repository. AWS deployment has not been verified.")
rect(35,140,1370,510,"#eef4f8")
text(55,168,"AWS target environment: af-south-1  /  Service placement requires deployment configuration",15,bold=True)
rect(565,192,785,213,"#f6f9fc","#7893a7")
text(585,216,"VPC / private subnets - proposed network boundary",14,bold=True)
node(80,250,"s3","Amazon S3","CSV uploads: raw/")
node(595,250,"lambda","AWS Lambda","Ingest: validate and load")
node(1100,250,"rds","Amazon RDS","PostgreSQL ledger")
line([(300,300),(595,300)],(338,281,"ObjectCreated:Put / async"))
line([(815,300),(1100,300)],(850,281,"SQL insert / port 5432"))
node(335,480,"s3","Amazon S3","Invalid rows: quarantine/")
node(645,480,"sqs","Amazon SQS","Ingest DLQ / standard")
node(1110,480,"ddb","Amazon DynamoDB","risk_scores: account + date")
line([(640,350),(640,425),(445,425),(445,480)],(450,416,"Bad rows"))
line([(755,350),(755,480)],(775,444,"After failed retries"),True)
text(70,710,"READ API",15,bold=True)
text(70,738,"Flask / local + Lambda adapter",16)
text(70,764,"/v1/health and /v1/transactions -> PostgreSQL",15)
text(70,790,"/v1/insights -> DynamoDB (preloaded scores)",15)
text(760,710,"OPERATIONS AND SECURITY",15,bold=True)
text(760,738,"Scripts: IAM roles, SSM parameters, CloudWatch alarms",15)
text(760,764,"Missing: KMS setup, access logging, VPC deployment",15)
text(760,790,"No automated scoring, email delivery or monthly reports yet",15)
end("architecture_day1_day3",1)

start("Final target","02 / Final capstone target","Planned architecture. Replace the direct ingest-to-RDS write when introducing FIFO; this is not a deployed-system claim.")
rect(35,140,1370,655,"#eef4f8")
text(55,170,"AWS / af-south-1  |  IAM per function  |  Customer-managed KMS keys  |  CloudWatch logs and alarms",15,bold=True)
node(70,220,"s3","Amazon S3","raw/ and quarantine/",220)
node(335,220,"lambda","AWS Lambda","Ingest / validation",220)
node(600,220,"sqs","Amazon SQS","FIFO / group by account",220)
rect(900,197,460,220,"#f6f9fc","#7893a7")
text(920,216,"VPC / private subnets",13,bold=True)
node(935,232,"lambda","AWS Lambda","Scoring + persistence",185)
node(1140,232,"rds","Amazon RDS","PostgreSQL",195)
line([(290,270),(335,270)])
line([(555,270),(600,270)])
line([(820,270),(935,270)])
line([(1120,270),(1140,270)])
node(70,440,"api","API Gateway","IAM-authorized data routes")
node(335,440,"lambda","AWS Lambda","Query / read API")
node(690,440,"ddb","Amazon DynamoDB","Daily account risk scores")
node(990,440,"lambda","AWS Lambda","Alert dispatcher",180)
node(1200,440,"ses","Amazon SES","Email alerts",165)
line([(290,490),(335,490)])
line([(555,490),(690,490)])
line([(480,440),(480,380),(1235,380),(1235,332)],(515,371,"Query reads ledger; VPC attachment required"))
line([(1000,332),(1000,350),(800,350),(800,440)])
line([(1080,332),(1080,440)])
line([(1170,490),(1200,490)])
node(70,630,"event","EventBridge","Monthly schedule")
node(335,630,"lambda","AWS Lambda","Report / query ledger")
node(600,630,"s3","Amazon S3","CSV and JSON reports")
line([(290,680),(335,680)])
line([(555,680),(600,680)])
text(880,650,"RESILIENCE / DEPLOYMENT GAPS",15,bold=True)
text(880,678,"Separate ingest and scoring DLQs; replay tests",14)
text(880,704,"Private AWS service access must be designed",14)
text(880,730,"Budget review: no NAT; endpoints and KMS have costs",14)
text(880,756,"Nightly Step Functions workflow: separate later scope",14)
end("architecture_target",2)


def table(x,y,name,fields,w=390):
    rect(x,y,w,45+len(fields)*26)
    rect(x,y,w,40,"#182c45","#182c45")
    text(x+14,y+27,name,19,"#ffffff",True)
    for i,field in enumerate(fields): text(x+14,y+62+i*26,field,14)


start("Relational ERD","03 / PostgreSQL entity relationship diagram","Schema: sql/schema.sql  |  All attributes shown  |  PK primary key, FK foreign key, UK unique  |  ? nullable; others NOT NULL")
table(40,160,"customers",["PK  customer_id : UUID","full_name : VARCHAR(150)","UK  id_number : VARCHAR(20)","kyc_status : VARCHAR(20)","created_at : TIMESTAMPTZ"])
table(525,160,"accounts",["PK  account_id : UUID","FK  customer_id : UUID","account_type : VARCHAR(30)","balance : NUMERIC(15,2)","status : VARCHAR(20)","opened_at : TIMESTAMPTZ"])
table(1010,160,"transactions",["PK  tx_id : UUID","FK  account_id : UUID","amount : NUMERIC(15,2)","currency : CHAR(3)","merchant : VARCHAR(200) ?","tx_date : TIMESTAMPTZ","tx_type : VARCHAR(30)","cross_border : BOOLEAN","raw_file : VARCHAR(200)"])
table(525,520,"risk_events",["PK  risk_event_id : BIGSERIAL","FK  tx_id : UUID","risk_score : INTEGER","reason : VARCHAR(255)","created_at : TIMESTAMPTZ"])
table(40,520,"alerts",["PK  alert_id : BIGSERIAL","FK  risk_event_id : BIGINT","severity : VARCHAR(20)","message : TEXT","sent_at : TIMESTAMPTZ"])
line([(430,240),(525,240)],arrow=False)
text(440,231,"1",14);text(487,231,"0..*",14)
line([(915,240),(1010,240)],arrow=False)
text(925,231,"1",14);text(972,231,"0..*",14)
line([(1205,439),(1205,601),(915,601)],arrow=False)
text(1220,471,"1",14);text(927,591,"0..*",14)
line([(525,601),(430,601)],arrow=False)
text(503,591,"1",14);text(441,591,"0..*",14)
text(990,670,"DynamoDB is a separate store",16,bold=True)
text(990,698,"risk_scores: account_id + score_date",14)
text(990,724,"No relational FK enforced across stores",14)
text(40,786,"Constraints: amount > 0; risk_score 0-100; KYC, account type, currency and transaction type allowlists.",15)
text(40,812,"Customer/account deletes are restricted. Each child has exactly one parent; a parent may have zero or many children.",15)
end("erd",3)
c.save()
ET.indent(mxfile)
ET.ElementTree(mxfile).write(OUT / "fintrust.drawio",encoding="utf-8",xml_declaration=True)
doc=fitz.open(PDF)
for index,page in enumerate(doc):
    page.get_pixmap(matrix=fitz.Matrix(1,1)).save(ROOT / f"tmp/pdfs/diagram-{index+1}.png")
print(f"Created {PDF} ({len(doc)} pages), editable draw.io file and 3 SVG diagrams")
