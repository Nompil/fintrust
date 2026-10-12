"""Reproduce the eight FinTrust presentation PDFs. Documentation tools only.
Run tools/render_release1_diagrams.cjs first. Requires reportlab, svglib, pymupdf.
No AWS access, database connection, or application execution.
"""
from pathlib import Path
import html,json,re,hashlib
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4,A3,landscape
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph,Table,TableStyle
from reportlab.graphics import renderPDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from svglib.svglib import svg2rlg
import pymupdf
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/presentation'; DIAGRAMS=OUT/'diagrams'; DIAGRAMS.mkdir(parents=True,exist_ok=True)
TMP=ROOT/'build/presentation-pdf'; TMP.mkdir(parents=True,exist_ok=True)
SVG=TMP/'svg' if (TMP/'svg').exists() else ROOT/'docs/diagrams'
FONTDIR=Path('C:/Windows/Fonts')
for name,file in [('FT','arial.ttf'),('FTB','arialbd.ttf')]:pdfmetrics.registerFont(TTFont(name,str(FONTDIR/file)))
INK=HexColor('#173f38');GREEN=HexColor('#2b6557');MUTED=HexColor('#516b66');PALE=HexColor('#edf5f3')
BODY=ParagraphStyle('body',fontName='FT',fontSize=11,leading=15,textColor=INK,spaceAfter=7)
SMALL=ParagraphStyle('small',parent=BODY,fontSize=8.5,leading=11)
BOLD=ParagraphStyle('bold',parent=BODY,fontName='FTB',fontSize=13,leading=18)
NAMES={'erd':('FinTrust_ERD.pdf','Database / ERD'),'aws-architecture':('FinTrust_AWS_Architecture.pdf','AWS architecture'),'activity':('FinTrust_Activity_Diagram.pdf','End-to-end activity'),'use-cases':('FinTrust_Use_Case_Diagram.pdf','Use cases'),'data-decisions':('FinTrust_Data_Decision_Flow.pdf','Data decisions'),'duplicate-handling':('FinTrust_Duplicate_Handling.pdf','Duplicate handling'),'role-separation':('FinTrust_Role_Separation.pdf','Role separation')}
C=None;W=H=Y=PAGE=0

def start(title,size=A4,sub='Release 1 | Planning and design evidence | 12 October 2026'):
 global W,H,Y,PAGE
 W,H=size; C.setPageSize(size);PAGE+=1
 C.setFillColor(GREEN);C.rect(0,H-10,W,10,fill=1,stroke=0)
 C.setFillColor(INK);C.setFont('FTB',min(18,(W-68)*18/max(1,pdfmetrics.stringWidth(title,'FTB',18))));C.drawString(34,H-43,title)
 C.setFillColor(MUTED);C.setFont('FT',8.5);C.drawString(34,H-60,sub)
 C.setStrokeColor(PALE);C.line(34,31,W-34,31)
 C.setFont('FT',8);C.drawString(34,18,'FinTrust | Local evidence; live application integration pending')
 C.drawRightString(W-34,18,str(PAGE));Y=H-83
 C.bookmarkPage('page-'+str(PAGE));C.addOutlineEntry(title,'page-'+str(PAGE),0,False)

def p(text,style=BODY):
 global Y
 para=Paragraph(text,style);_,h=para.wrap(W-68,H)
 assert Y-h>43,(PAGE,text[:50],Y,h)
 para.drawOn(C,34,Y-h);Y-=h+7

def heading(text):p(text,BOLD)
def bullets(items):
 for item in items:p('- '+item)
def table(rows,widths=None,size=10):
 global Y
 style=ParagraphStyle('cell',parent=BODY,fontSize=size,leading=size+3)
 data=[[Paragraph(str(cell),style) for cell in row] for row in rows]
 t=Table(data,colWidths=widths or [(W-68)/len(rows[0])]*len(rows[0]))
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PALE),('VALIGN',(0,0),(-1,-1),'TOP'),('BOX',(0,0),(-1,-1),.4,GREEN),('INNERGRID',(0,0),(-1,-1),.25,HexColor('#ccded8')),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
 _,h=t.wrap(W-68,H);assert Y-h>43,(PAGE,'table',h,Y);t.drawOn(C,34,Y-h);Y-=h+10

def diagram(name,maxheight=None,index=0):
 global Y
 d=svg2rlg(str(SVG/('fintrust-release1-'+name+('-'+str(index+1) if index else '')+'.svg')));assert d
 available=min(maxheight or Y-48,Y-48);scale=min((W-68)/d.width,available/d.height)
 h=d.height*scale;w=d.width*scale
 C.saveState();C.translate((W-w)/2,Y-h);C.scale(scale,scale);renderPDF.draw(d,C,0,0);C.restoreState();Y-=h+10
 return scale

def end():C.showPage()
def newfile(path):
 global C,PAGE
 PAGE=0;C=canvas.Canvas(str(path),pagesize=A4,pageCompression=1);C.setTitle('FinTrust - '+path.stem.replace('_',' '));C.setAuthor('FinTrust');C.setSubject('Frozen Release 1 business process, schema and architecture; no new AWS verification')

CAPTIONS={
'erd':'17 physical tables and two derived views, verified locally on PostgreSQL 16.15. Solid connectors are actual foreign keys. PK / FK / UK mean primary / foreign / unique key. Composite markers apply together. Larger A3 page preserves readable keys.',
'aws-architecture':'Official AWS service icons are embedded. GREEN: verified foundation; BLUE: Release 1 target with pending wiring; GOLD: disabled historical ingest. Outline: private VPC. Region af-south-1; no NAT Gateway. Icons do not prove deployment.',
'activity':'Read admission and scoring from top to bottom. Separate recovery and review paths are on the second page. Invalid files are rejected; invalid rows are quarantined. A controlled technical retry is not a compliance decision.',
'use-cases':'Four named roles, enforced by the backend. Administrator visibility does not confer routine Analyst mutation authority. Auditor is read-only. Maintainer recovery does not resolve risk reviews.',
'data-decisions':'Bad file: reject. Bad row: quarantine. Good unique row: process. Risky good row: investigate. LOW stores without routine review; MEDIUM opens review; HIGH opens review and the alert path.',
'duplicate-handling':'Duplicate protection protects the ledger. Duplicate-charge detection protects the customer. Same source identity with changed facts is quarantined; distinct genuine transactions are kept and assessed.',
'role-separation':'Technical recovery != compliance decision. Account scope and backend role checks apply. Local identity registry and governance receipts are outside the relational identity model.'}
VIEWS=json.loads((SVG/'views.json').read_text())
def viewpages(name):
 for view in [v for v in VIEWS if v['name']==name]:
  d=svg2rlg(str(SVG/view['file']))
  # Large evidence sheets retain readable keys; wide process views use landscape.
  size=landscape(A3) if d.width>d.height else A3
  if name=='role-separation':size=landscape(A4)
  start('FinTrust | '+view['title'],size)
  if name=='erd':
   p('Conceptual domain map: process arrows, not foreign keys.' if view['index']==0 else 'Physical foreign keys and keys are unchanged. Grey reference boxes connect domains across pages. PK / FK / UK: primary / foreign / unique keys. All 17 tables and 16 foreign keys are preserved.')
  else:p(CAPTIONS[name])
  diagram(name,index=view['index']);end()
for name,(filename,title) in NAMES.items():
 newfile(DIAGRAMS/filename);viewpages(name);C.save()

newfile(OUT/'FinTrust_Project_Planning_and_Design_Evidence.pdf')
start('FinTrust | Planning and design')
heading('1. Project problem')
p('Transaction exports need reliable admission, duplicate protection, explainable risk signals and accountable human review. FinTrust records and investigates financial events. It does not move money, reverse charges or establish fraud.')
heading('2. Users and roles')
table([['Role','Accountability'],['Administrator','Governance, users/access, role assignment, disable/reactivate and oversight.'],['Risk / Compliance Analyst','CSV upload, quarantine correction, investigation and review decisions.'],['Auditor','Read-only scoped records, reports and audit history.'],['Technical Maintainer','Technical failure diagnosis, controlled retry/redrive and recovery.']], [160,W-228])
p('Technical recovery != compliance decision. Admin visibility != routine Analyst authority.')
diagram('role-separation',160)
heading('Evidence boundary')
p('The frozen local application uses isolated PostgreSQL and local service substitutes. AWS stages 1-4 are recorded as verified; historical ingest remains disabled. Live schema bootstrap and complete application wiring remain pending. This document creates no new AWS evidence.',SMALL)
end()
start('Admission | Files and rows')
heading('3. Core use case')
p('An Analyst admits a scoped CSV, reviews its reconciled outcomes, corrects invalid business rows and investigates risk cases. An Auditor can inspect the resulting evidence without changing it.')
heading('4. File-ingestion rules')
p('CSV only; maximum 1 MiB and 5,000 rows. Invalid structure or unsupported files produce a safe rejection receipt and no ledger processing. Exact file replay returns the original batch rather than processing a second time.')
heading('5. Row-validation rules')
p('Require source transaction identity, account, valid timestamp and positive amount. Validate supported currency, country and transaction type; scoring confirms the account exists. Missing/unknown account, malformed or future timestamp, invalid amount and zero/negative amount are quarantined. Negative rows are not silently interpreted as refunds.')
diagram('data-decisions',430)
end()
start('Identity | Duplicate decisions',landscape(A4))
heading('6. Duplicate-handling decisions')
diagram('duplicate-handling',185)
table([['Case','Release 1 outcome'],['Exact same file hash in the source bucket','Audit replay attempt; no second processing; view original batch.'],['Same transaction in the same file / across files','Record occurrence; no second ledger entry. A new file still processes its other rows.'],['Same source identity with changed financial facts','Quarantine identity conflict; investigate; no silent overwrite.'],['Different trusted IDs with similar genuine facts','Keep both accepted events; raise possible duplicate-charge risk if conditions match.']],[260,W-328],10)
p('Duplicate protection protects the ledger. Duplicate-charge detection protects the customer.')
end()
start('Quarantine | Risk and review')
heading('7. Quarantine and correction')
p('Preserve safe original payload, reason code/detail, source file, batch, row and actor. Correction records a new occurrence/version; the worker revalidates it and repeats identity checks. The original is retained. Rejected/invalid data is distinct from technical failure work.')
heading('8. Frozen risk-scoring rules')
table([['Rule','Points / boundary'],['Amount &gt; R50,000','30; R50,000 exactly does not trigger.'],['Amount &gt; R200,000','Additional 25.'],['Velocity: &gt; 5 accepted including current','30; inclusive 5-minute / 300-second window.'],['Non-ZA country','15.'],['Possible duplicate debit charge','40; distinct IDs, matching merchant/amount/currency within inclusive 120 seconds.'],['Outgoing transfer / high-risk merchant','20 each; combined score capped at 100.']],[275,W-343],10)
p('R49,999.99 and R50,000.00 do not trigger the first amount rule; R50,000.01 does. Cross-border or high amount alone need not be HIGH. 10/11/12 per hour is deferred exploration.')
heading('9. Review workflow')
table([['Band','Outcome'],['LOW: 0-39','Store ledger and assessment; no routine review.'],['MEDIUM: 40-69','Store and open review.'],['HIGH: 70-100','Store, open review and enter the idempotent alert path.']],[150,W-218],10)
p('OPEN -&gt; UNDER_REVIEW -&gt; CLEARED / CONFIRMED_RISK / ESCALATED. Backend-enforced transitions preserve named actor, notes, versions and history. A risk flag is a reason to investigate, not proven fraud.')
end()
start('Use cases | Separation of duties',A3)
p('Scope follows the signed-in identity and assigned accounts. Sign out before changing roles; do not reuse another person\'s session.')
diagram('use-cases')
end()
start('Operations | Evidence and reporting')
heading('10. Failure handling / DLQ')
p('Quarantine concerns business data; retry/dead-letter queues concern technical processing. FIFO groups work by account. Durable correction/projection outboxes preserve pending intent after partial failures. Retry must not duplicate ledger entries or alerts; uncertain email outcomes need reconciliation.')
table([['Received rows','Must resolve to visible outcomes'],['Accepted','One canonical ledger identity.'],['Quarantined','Original and reason retained; controlled correction.'],['Duplicate','Occurrence retained; no new ledger entry.'],['Pending / technical failure','Visible and recoverable; nothing disappears silently.']],[160,W-228])
heading('11. Audit and accountability')
p('Keep named human subjects, timestamps, reason/notes, version history and operation receipts. Local identities use an ignored file-backed registry with hashed tokens; governance receipts use the S3-style receipt store. Do not invent SQL users/roles or notifications tables. Browser notices are session-local.')
heading('12. Reports and Insights')
p('Scoped reports and Insights expose actual financial and workflow aggregates, batch outcomes, review queues and account history. CSV/JSON exports support evidence; summaries are not a complete restorable archive. No ledger deletion is approved by a summary report.')
p('Presentation references such as ACC-0005, TX-0180, BATCH-1042 and RISK-0091 are readable examples, not replacement identity keys. UUIDs remain authoritative where the implementation uses them.')
end()
start('Database | Meaning and relationships')
heading('13. Database / ERD')
table([['Term','Meaning'],['File','Uploaded CSV.'],['Batch','Processing record for an accepted file.'],['Row','One financial-event candidate with source row lineage.'],['Account','Financial account being monitored.'],['Transaction','Accepted financial event in the ledger.'],['Quarantine','Invalid/conflicting business row awaiting a controlled decision.'],['Risk event','Frozen scoring evidence for visibility and, by score band, review.']],[135,W-203])
p('File -&gt; Batch -&gt; Rows -&gt; Transactions. Account -&gt; Transactions. Transaction -&gt; Risk event -&gt; Review. These are process relationships; only declared catalog foreign keys are drawn as physical relationships.')
p('The verified local PostgreSQL 16.15 catalog contains 17 tables and two derived views: batch_reconciliation and quarantine_workflow. Transactions.batch_id is lineage, not a declared foreign key. Source-system/account/source-transaction identity is conditionally unique; fingerprints are not globally unique.')
p('S3 holds original/safe payloads and reports; DynamoDB holds immutable projections and alert claims. SQL owns ledger, workflows, outboxes and migration history. Live RDS schema bootstrap remains pending.')
p('The following conceptual and four domain pages preserve readable physical keys and cardinalities. PK/FK/UK markers describe primary/foreign/unique keys; composite markers apply together. The retained schema notes provide exact constraint definitions.')
end()
viewpages('erd')
viewpages('aws-architecture')
viewpages('activity')
start('Release boundary | Present safely')
heading('17. Release 1 scope vs deferred work')
bullets(['Locally verified: scoped roles, bounded CSV admission, identity protection, quarantine/correction, frozen risk review, reconciliation, reports/Insights and accountability.','Recorded AWS foundation: private network, S3/KMS, private PostgreSQL instance, SQS/DynamoDB; historical ingest disabled.','Pending approval and verification: live base schema/migration chain, hardened final Linux candidate, cloud identity/API, triggers, report schedule, SES delivery and complete live end-to-end wiring.','Deferred: velocity changes to hour-based rules, automatic refunds/reversals, proven fraud classification and complete archive/deletion workflow.'])
heading('Short live-demo script')
bullets(['Use the existing Monday runbook for local launch and approved fixtures; never seed or migrate live RDS for presentation.','Sign in as the prepared Analyst. Show assigned scope and reconciled accepted / duplicate / quarantine outcomes.','Show file rejection versus row quarantine, lineage and an approved correction fixture.','Show LOW / MEDIUM / HIGH reasons and review history, then reports/Insights and audit.','Sign out, then demonstrate Auditor read-only scope. Explain Admin and Maintainer duties with the role diagram.','Close with the AWS diagram. Say explicitly which components remain pending; do not improvise technical retries or claim mocked email was delivered.'])
p('CSV A/B were created outside the repository and are not assumed to exist at invented paths. If a fixture is unavailable, show verified evidence and state that limitation. Keep credentials out of slides, logs and evidence.',SMALL)
end()
start('References | Source and maintenance')
heading('Authoritative sources')
bullets(['Application freeze: 10eb378; latest icon diagram checkpoint: c6f4274. The PDF conversion preserves those design decisions.','Verified local catalog: docs/EVIDENCE/05-rds/presentation-ux-freeze/postgres16-integrity.json.','Canonical schema detail: docs/diagrams/fintrust-release1-erd-notes.md. Business contract: docs/RELEASE1_BUSINESS_PROCESS.md.','Current local readiness: docs/RELEASE1_PRESENTATION_READINESS.md. Launch/fixture procedure: docs/RELEASE1_MONDAY_DEMO.md.','Official AWS icon attribution: aws.amazon.com/architecture/icons/. Icons are embedded unchanged from the retained service assets; no AWS deployment is implied.'])
heading('Reproduction and file discipline')
p('Seven DOT sources under docs/presentation/diagram-source/ produce intermediate SVGs under ignored build/presentation-pdf/svg/. tools/render_release1_diagrams.cjs performs the vector layout and embeds official icons. tools/build_presentation_pdf.py produces the eight final PDFs. Requires Node/Viz.js, Python/reportlab/svglib/PyMuPDF and Arial fonts.')
p('Current planning Markdown and current standalone SVG duplicates are removed only after PDF validation. Canonical development Markdown, historical screenshots, deployment/recovery history, AWS icon assets and project-reference remain retained. No AWS, application, migration or push operation is part of conversion.')
heading('Historical design inventory')
p('Archive-only exports retained under docs/EVIDENCE/12-e2e/historical-design-diagrams/: architecture_day1_day3.svg, architecture_target.svg, erd.svg, activity.svg, use_cases.svg, upload_sequence.svg, fintrust.drawio, fintrust_architecture_and_erd.pdf and fintrust_system_documentation.pdf. Their hash/move manifest remains in the diagram-pack evidence folder.',SMALL)
p('No history is discarded for visual appearance. The two historical Python renderers write only into that archive. Current authority is one planning PDF, seven diagram PDFs and seven editable DOT sources. Current-file references are updated to the PDF set; no extra current PDF versions are kept.',SMALL)
end()
start('Inventory | Final files and support notes')
table([['PDF','Purpose / editable source'],*[[filename,title+' / fintrust-release1-'+name+'.dot'] for name,(filename,title) in NAMES.items()],['FinTrust_Project_Planning_and_Design_Evidence.pdf','Combined planning, rules, demo and inventory / tools/build_presentation_pdf.py']],[260,W-328],9)
heading('Project-reference: keep unchanged today')
table([['File','Classification / recommendation after presentation'],['README.md / HANDOFF.md','Keep useful navigation/handoff; review against current readiness.'],['presentation_notes.md / live_demo_script.md','Keep safety net; use the current PDF script as authority; consolidate later.'],['learning_guide.md','Keep learning/reference history.'],['completed_work.md / component_guide.md','Duplicate or dated milestone narrative; consolidate after comparison.'],['local_software_setup.md','Earlier setup duplicate; consolidate into canonical Operations after review.'],['daily_log.md','Preserve chronological history; archive/consolidate later.'],['requirements_day1_day3.md / upcoming_features.md','Outdated milestone/future scope; archive or consolidate after presentation.']],[240,W-308],9)
p('No project-reference file is approved for deletion today. SAFE TO DELETE AFTER PRESENTATION applies only to copies confirmed redundant in a later comparison. Six earlier inline diagram duplicates already point to the authoritative views.',SMALL)
end();C.save()

# Open and render every page for visual review; record PDF readability checks.
results=[]
for path in [OUT/'FinTrust_Project_Planning_and_Design_Evidence.pdf',*[DIAGRAMS/f for f,_ in NAMES.values()]]:
 doc=pymupdf.open(path);folder=TMP/path.stem;folder.mkdir(exist_ok=True);pages=[]
 for i,page in enumerate(doc):
  text=page.get_text();assert text.strip(),(path,i,'blank')
  assert '\ufffd' not in text,(path,i,'replacement character')
  clipped=[]
  for block in page.get_text('dict')['blocks']:
   for line in block.get('lines',[]):
    for span in line['spans']:
     r=pymupdf.Rect(span['bbox'])
     if not (page.rect+pymupdf.Rect(-2,-2,2,2)).contains(r):clipped.append(span['text'])
  assert not clipped,(path,i,clipped)
  png=folder/f'page-{i+1:02d}.png';page.get_pixmap(matrix=pymupdf.Matrix(1.25,1.25),alpha=False).save(png)
  pages.append({'page':i+1,'size_points':[page.rect.width,page.rect.height],'text_chars':len(text),'images':len(page.get_image_info()),'clipped_text':clipped,'render':png.relative_to(ROOT).as_posix()})
 results.append({'pdf':path.relative_to(ROOT).as_posix(),'purpose':path.stem.replace('_',' '),'pages':len(doc),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'validation':pages});doc.close()
assert sum(p['images'] for p in next(x for x in results if 'AWS_Architecture' in x['pdf'])['validation'])>=21,'AWS icons missing'
EVIDENCE=ROOT/'docs/EVIDENCE/12-e2e/presentation-diagram-pack'
(EVIDENCE/'pdf-validation.json').write_text(json.dumps({'status':'RENDERED_FOR_VISUAL_REVIEW','aws_access':False,'outputs':results},indent=2)+'\n',encoding='utf-8')
print(json.dumps([{'pdf':r['pdf'],'pages':r['pages']} for r in results],indent=2))
