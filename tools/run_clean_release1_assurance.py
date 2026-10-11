"""Reproduce the isolated Windows assurance sequence after the documented setup.
Requires a clean source archive, fresh venv, portable PG16 and fresh Playwright.
Never AWS or live RDS. Refuses reused cluster state; always stops its own server.
"""
import json,os,secrets,socket,subprocess,sys,shutil,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'build/assurance-clean-start';SOURCE=WORK/'source';BIN=ROOT/'build/assurance-pg16/pgsql/bin';DATA=ROOT/'build/assurance-pg16'/('data-'+uuid.uuid4().hex);PY=ROOT/'build/assurance-clean-env/Scripts/python.exe'
E=ROOT/'docs/EVIDENCE/12-e2e/clean-start';RDS=ROOT/'docs/EVIDENCE/05-rds/local-pg16-assurance'
E.mkdir(parents=True,exist_ok=True);RDS.mkdir(parents=True,exist_ok=True)
password=secrets.token_urlsafe(32);env=os.environ.copy()
env.update(AWS_ACCESS_KEY_ID='testing',AWS_SECRET_ACCESS_KEY='testing',AWS_SESSION_TOKEN='testing',AWS_DEFAULT_REGION='af-south-1',AWS_EC2_METADATA_DISABLED='true',AWS_IGNORE_CONFIGURED_ENDPOINT_URLS='true',PYTHONNOUSERSITE='1',PYTHON_DOTENV_DISABLED='1',FINTRUST_DISPOSABLE_PG16_LOCAL='1',DB_HOST='127.0.0.1',DB_PORT='55416',DB_NAME='fintrust_test',DB_USER='postgres',DB_PASSWORD=password)
env.pop('PYTHONPATH',None)
started=False;results={}
def safe(value):return value.replace(password,'[REDACTED_DISPOSABLE_CREDENTIAL]').replace(env.get('FINTRUST_TEST_DATABASE_URL','nevermatch'),'[REDACTED_DISPOSABLE_DSN]')
def run(label,args,cwd=SOURCE,timeout=900):
    global started
    print('START',label,flush=True);start=time.perf_counter()
    temporary=WORK/(label+'-output.tmp')
    with temporary.open('w',encoding='utf-8') as stream:
        p=subprocess.run([str(x) for x in args],cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if label=='server-start' and p.returncode==0:started=True
    text=safe(temporary.read_text(encoding='utf-8',errors='replace'))
    try:temporary.unlink()
    except PermissionError:pass
    (E/(label+'.txt')).write_text(text,encoding='utf-8')
    results[label]={'exit_code':p.returncode,'seconds':round(time.perf_counter()-start,2)}
    print('END',label,results[label],flush=True)
    if p.returncode:print(text[-4000:],flush=True);raise RuntimeError(label+' failed')
    return text
try:
    with socket.socket() as sock:sock.bind(('127.0.0.1',55416))
    assert not DATA.exists(),'Refuse existing cluster/state'
    pw=ROOT/'build/assurance-pg16/init-password.txt';pw.write_text(password,encoding='utf-8')
    try:run('initdb',[BIN/'initdb.exe','-D',DATA,'-U','postgres','--pwfile',pw,'--auth=scram-sha-256','--encoding=UTF8','--locale=C'],cwd=ROOT,timeout=120)
    finally:pw.unlink(missing_ok=True)
    run('server-start',[BIN/'pg_ctl.exe','-D',DATA,'-l',DATA/'server.log','-o','-h 127.0.0.1 -p 55416','-w','start'],cwd=ROOT,timeout=60);started=True
    import psycopg2
    from psycopg2.extensions import make_dsn
    env['FINTRUST_TEST_DATABASE_URL']=make_dsn(host='127.0.0.1',port=55416,dbname='fintrust_test',user='postgres',password=password)
    c=psycopg2.connect(host='127.0.0.1',port=55416,dbname='postgres',user='postgres',password=password);c.autocommit=True
    with c.cursor() as cur:cur.execute('CREATE DATABASE fintrust_test')
    c.close()
    run('dependency-check',[PY,'-m','pip','check'])
    frozen=run('dependency-freeze',[PY,'-m','pip','freeze']);(E/'installed-dependencies.txt').write_text(frozen,encoding='utf-8')
    code="import importlib,pkgutil,fintrust; modules=[m.name for m in pkgutil.iter_modules(fintrust.__path__)]; [importlib.import_module('fintrust.'+m) for m in modules]; from fintrust.api import lambda_handler; print('Major production modules and API handler imported:',len(modules))"
    run('production-imports',[PY,'-c',code])
    run('service-role-proof',[PY,'tools/check_release1_roles_pg16.py'])
    shutil.copyfile(SOURCE/'docs/EVIDENCE/12-e2e/release1-closure/postgres16-roles.json',RDS/'service-roles.json')
    run('migration-identity-proof',[PY,'tools/check_migration_roles_pg16.py'])
    shutil.copyfile(SOURCE/'build/migration-runner/pg16-role-rehearsal.json',RDS/'migration-identity.json')
    run('migration-workflows-proof',[PY,'tools/check_workflows_pg16.py'])
    shutil.copyfile(SOURCE/'build/migration-runner/pg16-workflows-rehearsal.json',RDS/'migration-workflows.json')
    env['FINTRUST_LOCAL_ASSURANCE_EVIDENCE']=str(RDS)
    run('catalog-integrity-performance',[PY,'tools/check_local_pg16_assurance.py'])
    run('focused-smoke',[PY,'tools/run_release1_tests.py','tests/test_system_assurance.py','tests/test_release1_end_to_end.py','tests/test_role_workflow_ux.py'])
    env.update(FINTRUST_NODE=os.environ['FINTRUST_NODE'],FINTRUST_PLAYWRIGHT_MODULE=str(WORK/'browser-tools/node_modules/playwright'),FINTRUST_RELEASE_COMMIT='8b86b699f7a9c2a492eb159b58fb35bf22c3fdcf',FINTRUST_BROWSER_EVIDENCE=str(E/'browser'))
    run('fresh-browser',[PY,'tools/run_release1_browser.py'])
    run('fresh-full',[PY,'tools/run_release1_tests.py'],timeout=1200)
    results['status']='PASSED'
except Exception as error:
    results['status']='BLOCKED';results['blocker']=safe(str(error));print('BLOCKED',results['blocker'],flush=True)
finally:
    if started:
        try:run('server-stop',[BIN/'pg_ctl.exe','-D',DATA,'-m','fast','-w','stop'],cwd=ROOT,timeout=60)
        except Exception as error:results['cleanup_blocker']=type(error).__name__
    result={'results':results,'source_commit':'8b86b699f7a9c2a492eb159b58fb35bf22c3fdcf','application_source':'Git archive; no prior runtime state or virtualenv copied','python':'Fresh Windows CPython 3.14 venv, no global/user site packages','browser':'Fresh CI-pinned Playwright 1.62.1; existing installed Chrome and Node are documented host prerequisites','aws_access':False,'database':'Fresh PostgreSQL 16.15 loopback cluster, SCRAM random ephemeral credential; stopped afterward','live_rds':False,'dotenv_discovery':'Disabled to prevent ancestor repository credentials being discovered','harness_changes':'Explicit local disposable gate opt-in, added catalogue/performance checker with benchmark rollback, and launcher test fixture target correction; business source unchanged'}
    (E/'reproduction-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
sys.exit(0 if results.get('status')=='PASSED' else 1)
