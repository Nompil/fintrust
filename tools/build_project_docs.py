"""Regenerate the two living project PDFs; no application or AWS execution.
Dependencies: reportlab, PyMuPDF. Run from the repository root.
"""
from pathlib import Path
import json, html, hashlib
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak, Table, TableStyle, Flowable, KeepTogether
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
ROOT=Path(__file__).resolve().parents[1]
INK=HexColor('#15343b');GREEN=HexColor('#177258');PALE=HexColor('#edf5ef');MUTED=HexColor('#51676c')
fontdir=Path('C:/Windows/Fonts')
if (fontdir/'arial.ttf').exists():
 pdfmetrics.registerFont(TTFont('FT',str(fontdir/'arial.ttf')));pdfmetrics.registerFont(TTFont('FTB',str(fontdir/'arialbd.ttf')))
else:
 from reportlab import rl_config
 fonts=Path(rl_config.TTFSearchPath[0])
 # Core PDF fonts retain a portable fallback; all source text is ASCII.
 pdfmetrics.registerFont(pdfmetrics.Font('FT','Helvetica','WinAnsiEncoding'));pdfmetrics.registerFont(pdfmetrics.Font('FTB','Helvetica-Bold','WinAnsiEncoding'))
styles=getSampleStyleSheet()
styles.add(ParagraphStyle('FTBody',fontName='FT',fontSize=10.5,leading=15,textColor=INK,spaceAfter=9))
styles.add(ParagraphStyle('FTHeading',fontName='FTB',fontSize=17,leading=21,textColor=GREEN,spaceBefore=14,spaceAfter=8,keepWithNext=True))
styles.add(ParagraphStyle('FTSmall',fontName='FT',fontSize=8.3,leading=11.5,textColor=MUTED,spaceAfter=8))
styles.add(ParagraphStyle('FTCover',fontName='FTB',fontSize=34,leading=41,textColor=INK,spaceAfter=23))
styles.add(ParagraphStyle('FTBadge',fontName='FTB',fontSize=9,leading=12,textColor=GREEN,spaceAfter=9,keepWithNext=True))
def p(t,style='FTBody'):return Paragraph(html.escape(t),styles[style])
class Doc(BaseDocTemplate):
 def afterFlowable(self,f):
  if isinstance(f,Paragraph) and f.style.name=='FTHeading' and getattr(f,'section_key',None):
   key=f.section_key;self.canv.bookmarkPage(key);self.canv.addOutlineEntry(f.getPlainText(),key,0)
   self.notify('TOCEntry',(0,f.getPlainText(),self.page,key))
def header(c,d):
 w,h=A4;c.saveState();c.setFillColor(GREEN);c.rect(0,h-9,w,9,fill=1,stroke=0)
 c.setFont('FTB',9);c.setFillColor(GREEN);c.drawString(45,h-29,'fintrust.');c.setFont('FT',8);c.setFillColor(MUTED);c.drawRightString(w-45,h-29,d.project_title)
 c.setStrokeColor(PALE);c.line(45,36,w-45,36);c.setFont('FT',8);c.drawString(45,23,'Source '+d.project_checkpoint+' | '+d.project_date+' | Local proof != live deployment')
 c.drawRightString(w-45,23,str(d.page));c.restoreState()
class Diagram(Flowable):
 def __init__(self,kind):super().__init__();self.kind=kind;self.width=A4[0]-90;self.height=440 if kind!='aws' else 520
 def draw(self):
  c=self.canv;w=self.width
  def box(x,y,bw,bh,title,desc='',icon=None):
   c.setFillColor(PALE);c.setStrokeColor(GREEN);c.roundRect(x,y,bw,bh,8,fill=1)
   off=10
   if icon:
    c.drawImage(str(ROOT/'docs/diagrams/aws-icons'/f'{icon}.png'),x+10,y+bh-42,width=30,height=30,mask='auto');off=48
   q=Paragraph(html.escape(title),ParagraphStyle('dt',fontName='FTB',fontSize=10,leading=13,textColor=INK));_,hh=q.wrap(bw-off-10,bh);q.drawOn(c,x+off,y+bh-14-hh)
   q=p(desc,'FTSmall');_,hh=q.wrap(bw-20,bh);q.drawOn(c,x+10,y+10)
  def arrow(x1,y1,x2,y2):
   c.setStrokeColor(GREEN);c.setFillColor(GREEN);c.line(x1,y1,x2,y2)
   import math
   a=math.atan2(y2-y1,x2-x1);path=c.beginPath();path.moveTo(x2,y2);path.lineTo(x2-7*math.cos(a-.5),y2-7*math.sin(a-.5));path.lineTo(x2-7*math.cos(a+.5),y2-7*math.sin(a+.5));path.close();c.drawPath(path,fill=1)
  if self.kind=='flow':
   for y,title,desc in [(360,'CSV admission / source provenance','Reject invalid files; preserve version, hash, batch and row'),(270,'Candidate queue -> database-aware validation','RECEIVED -> QUEUED -> VALIDATED'),(180,'Accepted ledger + frozen risk assessment','SCORED -> STORED; all valid risk levels retained')]:
    box(15,y,w-30,65,title,desc)
   arrow(w/2,360,w/2,335);arrow(w/2,270,w/2,245)
   box(15,50,(w-45)/2,95,'Medium / High review','OPEN -> UNDER_REVIEW -> business decision')
   box(w/2+7,50,(w-45)/2,95,'High email delivery','SENT -> ALERTED; UNKNOWN held for reconciliation')
   arrow(w/3,180,w/3,145);arrow(w*2/3,180,w*2/3,145)
   q=p('Invalid rows branch to quarantine. Corrections create new linked occurrences and repeat validation/deduplication. Review does not wait for email.','FTSmall');_,hh=q.wrap(w,100);q.drawOn(c,0,5)
  elif self.kind=='aws':
   box(0,420,160,80,'S3 source / evidence','Versioned, encrypted input','s3');box(190,420,140,80,'Ingest Lambda','Outside VPC; parsing','lambda');box(360,420,w-360,80,'SQS FIFO','Ordered candidates','sqs')
   arrow(160,460,190,460);arrow(330,460,360,460)
   c.setStrokeColor(MUTED);c.roundRect(0,175,w,215,8,fill=0);c.setFont('FTB',10);c.setFillColor(MUTED);c.drawString(12,373,'PRIVATE VPC | af-south-1 | no NAT')
   box(15,270,200,80,'Scoring / API / Report','Python 3.12; verified TLS','lambda');box(w-205,270,190,80,'RDS PostgreSQL','Private ledger + audit','rds');arrow(215,310,w-205,310)
   box(15,190,w-30,62,'S3 / DynamoDB gateway endpoints','Private service path; IAM and endpoint policies both apply')
   arrow(w-70,420,w-70,357);arrow(w-70,357,210,357);arrow(210,357,210,350)
   box(0,65,160,85,'DynamoDB','Projection / delivery claim','ddb');box(190,65,140,85,'Alert Lambda','Outside VPC','lambda');box(360,65,w-360,85,'SES','High-only email','ses')
   arrow(75,270,5,260);arrow(5,260,5,163);arrow(5,163,80,163);arrow(80,163,80,150)
   arrow(160,105,190,105);arrow(330,105,360,105)
   q=p('Official AWS icons retained in docs/diagrams/aws-icons/. Foundation historically verified; current-release wiring pending. Temporary migration interface endpoint is not standing infrastructure.','FTSmall');_,hh=q.wrap(w,70);q.drawOn(c,0,10)
  else:
   # Current logical ERD: grouped entities, not a replacement for full physical FK sheets.
   box(0,350,w,75,'Customer -> Account -> Transaction','Identity: immutable tx_id; source namespace/reference; fingerprint')
   for x,y,title,desc in [(0,230,'Ingestion / provenance','batches, records, attempts, reconciliation'),(w/2+8,230,'Assessment / investigation','processed result, risk_events, reviews/history'),(0,105,'Quarantine / correction','cases, corrections, workflow, correction_outbox'),(w/2+8,105,'Recovery / delivery','projection_outbox, operations_requests, alerts')]:box(x,y,w/2-8,90,title,desc)
   arrow(w/4,350,w/4,320);arrow(w*3/4,350,w*3/4,320);arrow(w/4,230,w/4,195);arrow(w*3/4,230,w*3/4,195)
   box(0,0,w,75,'003: transaction_lifecycle_events','Append-only observations linked to ingestion occurrence; actor, time, sequence')
   arrow(w/4,105,w/4,75);arrow(w*3/4,105,w*3/4,75)
def build(source,out):
 data=json.loads(source.read_text(encoding='utf8'));doc=Doc(str(out),pagesize=A4,leftMargin=45,rightMargin=45,topMargin=48,bottomMargin=49,title=data['title'],author='FinTrust',pageCompression=1)
 doc.project_title=data['title'];doc.project_checkpoint=data['checkpoint'];doc.project_date=data['date'];doc.addPageTemplates(PageTemplate(id='main',frames=[Frame(45,49,A4[0]-90,A4[1]-97,id='body')],onPage=header))
 story=[Spacer(1,130),p('fintrust.','FTCover'),p(data['title'],'FTCover'),p(data['subtitle']),Spacer(1,25),p('RELEASE 1 | '+data['date'],'FTBadge'),p('Source checkpoint '+data['checkpoint']),p('Authoritative consolidated documentation. Explicitly separates local verification, historical deployment evidence and pending live gates.'),Spacer(1,25),p('Fictional client: Imbokodo Bank. No real bank adoption or production compliance certification is claimed.','FTSmall'),PageBreak(),p('Contents','FTHeading')]
 toc=TableOfContents();toc.levelStyles=[ParagraphStyle('toc',fontName='FT',fontSize=10,leading=14,textColor=INK,spaceBefore=3,leftIndent=0,firstLineIndent=0)];story.extend([toc,PageBreak()])
 for i,s in enumerate(data['sections'],1):
  h=p(f'{i}. '+s['title'],'FTHeading');h.section_key='section-'+str(i);story.extend([h,p(s['status'],'FTBadge')])
  for t in s['paragraphs']:story.append(p(t))
  if s.get('table'):
   rows=[[p(str(cell),'FTSmall') for cell in row] for row in s['table']];n=len(rows[0]);width=A4[0]-90
   widths=[width*.20,width*.16,width*.64] if n==3 else [width*.29,width*.71]
   tab=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT');tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PALE),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,GREEN),('LINEBELOW',(0,1),(-1,-1),.3,HexColor('#d7e2dc')),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),3)]));story.extend([tab,Spacer(1,8)])
  if s.get('references'):
   story.append(p('Source: '+'; '.join(s['references']),'FTSmall'))
  if s.get('diagram'):
   kind='aws' if 'AWS' in s['diagram'] else 'erd' if 'ERD' in s['diagram'] else 'flow'
   story.extend([PageBreak(),p({'aws':'Architecture - official AWS icons','erd':'Current data domains and lifecycle extension','flow':'Processing, review and delivery'}[kind],'FTHeading'),Diagram(kind)])
   if kind=='erd':story.append(p('Logical groups and evidence relationships; arrows are not physical foreign keys. The linked baseline ERD has the detailed key sheets.','FTSmall'))
   story.extend([p('Supporting detailed diagram: docs/presentation/diagrams/'+s['diagram'],'FTSmall'),PageBreak()])
 doc.multiBuild(story)
 return out
def main():
 for name in ['Master','Progress']:
  source=ROOT/'docs/source'/('project-'+name.lower()+'.json');out=ROOT/'docs'/('FinTrust_Project_'+name+'.pdf');build(source,out);print(out)
if __name__=='__main__':main()
