"""Audit original CSV contract compatibility without conversion, SQL or AWS."""
import base64,csv,hashlib,io,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fintrust.release_ingest import parse_file,FileRejected,REQUIRED
from fintrust.quarantine import FIELDS
NAMES=('fintrust_e2e_mixed_transactions.csv','fintrust_e2e_companion_transactions_B.csv')

def inspect(name):
    payload=(ROOT/'tests/fixtures/e2e'/name).read_bytes()
    reader=csv.DictReader(io.StringIO(payload.decode('utf-8-sig')));rows=list(reader);headers=reader.fieldnames
    try:parse_file(payload);admission='PASSED';reason=None
    except FileRejected as error:admission='BLOCKED';reason=error.code
    return {'filename':name,'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest(),'sha256_base64':base64.b64encode(hashlib.sha256(payload).digest()).decode(),'headers':headers,'row_count':len(rows),'unchanged':True,'admission':admission,'parser_reason':reason,'missing_required_headers':sorted(REQUIRED-set(headers)),'missing_source_reference_alternative':not bool({'source_transaction_id','source_reference'}&set(headers)),'unsupported_headers':sorted(set(headers)-FIELDS),'exact_header_matches':sorted(set(headers)&FIELDS),'row_report':[{'source_row':i,'original_transaction_label':row['transaction_id'],'expected_file_outcome':'INVALID_CSV_SCHEMA','actual_file_outcome':'INVALID_CSV_SCHEMA' if reason=='MISSING_HEADERS' else reason,'business_expected':'NOT_ASSIGNED: account/type/source mapping requires review','business_actual':'NOT_PROCESSED: whole file rejected before row work'} for i,row in enumerate(rows,2)]}

def main():
    report={'status':'BLOCKED','verified_application_source':'d648dd0a77b6906daa94ec7ade7b2ff3e3158ed0','originals':[inspect(name) for name in NAMES],'sequence':['A original','B original','A original unchanged replay'],'scope':'Compatibility audit only; actual HTTP/SQL non-mutation proof is in test_original_fixture_admission.py','application_changed':False,'artifact_rebuilt':False,'aws_actions':False,'required_semantics':['Reviewed ACC101..ACC104 UUID mapping and known-account baseline; unknown ACC999999 must remain unknown','Reviewed PURCHASE meaning; no implicit conversion to debit','Reviewed source_system namespace and upstream transaction reference mapping','Reviewed receipt clock for deterministic future timestamp expectations'],'coverage_gaps':['No raw same-label materially-changed-payload conflict row in A/B','Twelve velocity rows are four minutes apart; they do not prove >5 in five minutes'],'policy':'Do not regenerate or silently normalize originals. Propose separately named mapped fixtures only after semantic review.'}
    out=ROOT/'docs/EVIDENCE/12-e2e/original-fixture-acceptance';out.mkdir(parents=True,exist_ok=True)
    (out/'contract-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    # Import metadata is factual even when admission rejects the complete file.
    (ROOT/'tests/fixtures/e2e/import-manifest.json').write_text(json.dumps({'files':[{k:v for k,v in f.items() if k in {'filename','bytes','sha256','sha256_base64','headers','row_count','unchanged','admission','parser_reason'}} for f in report['originals']],'row_outcomes':'BLOCKED before row processing; no acceptance claims'},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='originals'},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
