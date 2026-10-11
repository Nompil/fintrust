"""Offline assurance inventory: no AWS, no database, no credential output."""
import ast, hashlib, json, re, subprocess, time, tracemalloc
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/EVIDENCE/12-e2e/system-assurance'
OUT.mkdir(parents=True,exist_ok=True)
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(name,value):(OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def main():
    tracked=git('ls-files','-z').decode().strip('\0').split('\0')
    prior=json.loads((ROOT/'docs/EVIDENCE/12-e2e/presentation-readiness/freeze-worktree-classification.json').read_text())
    preserved=[r['file'] for r in prior if not r['include']]
    save('preserved-files.json',{'files':[{'path':p,'sha256':digest(ROOT/p)} for p in preserved if (ROOT/p).is_file()], 'policy':'Preserve unrelated work and forensic evidence; no archiving or deletion.'})
    tree=ast.parse((ROOT/'fintrust/api.py').read_text(encoding='utf-8'))
    routes=[]
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                if isinstance(deco,ast.Call) and isinstance(deco.func,ast.Attribute) and deco.func.attr in {'get','post','route'}:
                    routes.append({'method':deco.func.attr.upper(),'route':ast.literal_eval(deco.args[0]),'handler':node.name,'line':node.lineno})
    save('component-map.json',{'source_commit':git('rev-parse','HEAD').decode().strip(),'api_routes':routes,
        'file_inventory':{category:[p for p in tracked if p.startswith(prefix)] for category,prefix in {'frontend':'frontend/','production':'fintrust/','sql':'sql/','iam':'infrastructure/iam/','fixtures':'tests/fixtures/','deployment':'infrastructure/','workflows':'.github/workflows/'}.items()},
        'roles':['Admin','Risk/Compliance Analyst','Read-only/Auditor','Maintainer'],
        'pages_source':'frontend/release1.js','flow':['authenticated UI','CSV admission','file/row identity','validation/quarantine','SQL ledger and scoring','projection outbox','mock DynamoDB/alerts','review/correction audit','SQL reports and eight insights'],
        'sql':['sql/bootstrap/release1-base-manifest.json','sql/schema.sql (base prefix only)','sql/migrations/001_transaction_identity.sql','sql/migrations/002_operational_workflows.sql'],
        'test_files':[p for p in tracked if p.startswith('tests/') and p.endswith('.py')],
        'cloud_boundary':'No AWS calls. Local real PostgreSQL and mocked cloud services. Live E2E unverified.'})
    candidates=[]
    for p in ROOT.rglob('__pycache__'):
        if p.is_dir() and not p.is_symlink() and '.git' not in p.parts and not any(part in {'.venv','venv','node_modules'} for part in p.parts):
            relative=p.relative_to(ROOT).as_posix()
            if not any(t==relative or t.startswith(relative+'/') for t in tracked):
                candidates.append({'path':relative,'reason':'Ignored regenerable Python bytecode only','files':sum(1 for x in p.rglob('*') if x.is_file())})
    save('cleanup-proposal.json',{'delete_only':candidates,'preserve':['all historical ZIPs and manifests','all AWS failure/recovery evidence','build scripts and runner packages','test result XML and logs','157 unrelated worktree files'],'authorization':'User-authorized safe cleanup; verify resolved paths and reparse points before deletion.'})
    patterns={'aws_access_key':r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b','github_token':r'\bgh[pousr]_[A-Za-z0-9]{30,}\b','private_key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----','credential_url':r'(?:postgres(?:ql)?|mysql)://[^\s:/]+:[^\s@]+@'}
    hits=[]
    for name in sorted(set(tracked+preserved+git('ls-files','--others','--exclude-standard','-z').decode().strip('\0').split('\0'))):
        path=ROOT/name
        if not path.is_file() or path.suffix.lower() not in {'.py','.js','.cjs','.json','.yaml','.yml','.md','.txt','.sql','.xml','.html','.csv'}:continue
        content=path.read_text(encoding='utf-8',errors='replace')
        for kind,pat in patterns.items():
            for match in re.finditer(pat,content):
                synthetic=('test_release_verification' in name or 'release1-base-source-review.json' in name or (path.suffix=='.xml' and 'test_release_input_rejects_secret_dev_or_unsafe_material' in content))
                synthetic = synthetic or (name=='tools/system_assurance_inventory.py' and kind=='credential_url' and match.group() in {'postgresql://postgres:postgres@','postgresql://postgres:YOUR_LOCAL_PASSWORD@'})
                synthetic = synthetic or (kind=='credential_url' and match.group() in {'postgresql://postgres:postgres@','postgresql://postgres:YOUR_LOCAL_PASSWORD@'} and content[match.end():].startswith('localhost:5432/fintrust_test'))
                hits.append({'file':name,'line':content.count('\n',0,match.start())+1,'kind':kind,'classification':'reviewed synthetic test/scan marker' if synthetic else 'NEEDS_REVIEW'})
    save('secret-scan.json',{'scope':'Tracked text and preserved unrelated untracked text; ignored local credentials excluded. No matched values printed. Pattern scan does not prove absence of all secrets or personal data.','findings':hits})
    # Parser-only measurements are not database/queue throughput or production capacity.
    import sys,os
    sys.path.insert(0,str(ROOT));os.environ['AWS_EC2_METADATA_DISABLED']='true'
    from tests.test_release1_end_to_end import file_bytes
    from tests.test_release1_workflows import row
    from fintrust.release_ingest import parse_file
    measurements=[]
    for count in (1,100,1000,5000):
        payload=file_bytes([row(source_transaction_id='PERF-'+str(i)) for i in range(count)])
        tracemalloc.start();start=time.perf_counter();parsed=parse_file(payload);seconds=time.perf_counter()-start
        peak=tracemalloc.get_traced_memory()[1];tracemalloc.stop()
        assert len(parsed)==count
        measurements.append({'rows':count,'bytes':len(payload),'seconds':round(seconds,4),'peak_bytes':peak})
    save('parser-performance.json',{'scope':'CSV parser only; no AWS/SQL calls, no end-to-end capacity claim','measurements':measurements,'database_1000_5000_throughput':'UNVERIFIED'})
    print(json.dumps({'routes':len(routes),'preserved':len(preserved),'cleanup_directories':len(candidates),'secret_findings':len(hits),'needs_review':sum(h['classification']=='NEEDS_REVIEW' for h in hits),'parser_rows':[r['rows'] for r in measurements]}))
if __name__=='__main__':main()
