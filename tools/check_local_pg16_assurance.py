"""Disposable loopback PostgreSQL 16 catalogue/integrity and bounded SQL plans.
No AWS calls. Requires a fresh fintrust_test database and an administrator.
"""
import os,json,hashlib,time,sys
from pathlib import Path
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
def main():
    from fintrust import migrations
    dsn=os.environ['FINTRUST_TEST_DATABASE_URL'];target=parse_dsn(dsn)
    assert os.getenv('FINTRUST_DISPOSABLE_PG16_LOCAL')=='1'
    assert target['host']=='127.0.0.1' and target['dbname']=='fintrust_test' and target['port']=='55416'
    c=psycopg2.connect(dsn)
    def q(statement,args=()):
        with c.cursor() as cur:
            cur.execute(statement,args) if args else cur.execute(statement)
            return cur.fetchall() if cur.description else []
    version,admin=q("SELECT version(),rolsuper FROM pg_roles WHERE rolname=current_user")[0]
    assert 'PostgreSQL 16.' in version and admin
    assert q("SELECT count(*) FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind IN ('r','v','m')")==[(0,)]
    manifest=json.loads((ROOT/'sql/bootstrap/release1-base-manifest.json').read_text())
    base=(ROOT/'sql/schema.sql').read_text().split('-- Additive identity hardening.')[0]
    assert hashlib.sha256(base.encode()).hexdigest()==manifest['base']['sha256']
    q(base);c.commit()
    assert migrations.apply_local(c,1)=='APPLIED';assert migrations.apply_local(c,2)=='APPLIED'
    q((ROOT/'sql/seed.sql').read_text());c.commit()
    assert migrations.apply_local(c,1)=='ALREADY_APPLIED';assert migrations.apply_local(c,2)=='ALREADY_APPLIED'
    objects=q("SELECT relname,relkind,pg_get_userbyid(relowner) FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind IN ('r','v') ORDER BY relname")
    constraints=q("SELECT conrelid::regclass::text,conname,contype,pg_get_constraintdef(oid),convalidated FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY 1,2")
    assert all(r[4] for r in constraints)
    indexes=q("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY indexname")
    assert any('UNIQUE' in definition and ' WHERE ' in definition for _,definition in indexes)
    violations={}
    for table in [r[0] for r in objects if r[1]=='r']:
        cols=q("SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass AND attnum>0 AND attnotnull AND NOT attisdropped",('public.'+table,))
        for (col,) in cols:
            violations['not_null:'+table+'.'+col]=q(sql.SQL('SELECT count(*) FROM {} WHERE {} IS NULL').format(sql.Identifier(table),sql.Identifier(col)))[0][0]
    fks=q("SELECT conname,conrelid::regclass::text,confrelid::regclass::text,conkey,confkey FROM pg_constraint WHERE connamespace='public'::regnamespace AND contype='f'")
    for name,child,parent,keys,refs in fks:
        a=[q('SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass AND attnum=%s',(child,n))[0][0] for n in keys]
        b=[q('SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass AND attnum=%s',(parent,n))[0][0] for n in refs]
        join=sql.SQL(' AND ').join(sql.SQL('c.{}=p.{}').format(sql.Identifier(x),sql.Identifier(y)) for x,y in zip(a,b))
        required=sql.SQL(' AND ').join(sql.SQL('c.{} IS NOT NULL').format(sql.Identifier(x)) for x in a)
        stmt=sql.SQL('SELECT count(*) FROM {} c WHERE {} AND NOT EXISTS (SELECT 1 FROM {} p WHERE {})').format(sql.Identifier(child.split('.')[-1]),required,sql.Identifier(parent.split('.')[-1]),join)
        violations['orphan:'+name]=q(stmt)[0][0]
    for name,table,keys in q("SELECT conname,conrelid::regclass::text,conkey FROM pg_constraint WHERE connamespace='public'::regnamespace AND contype IN ('p','u')"):
        cols=[q('SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass AND attnum=%s',(table,n))[0][0] for n in keys]
        ids=sql.SQL(',').join(map(sql.Identifier,cols));nonnull=sql.SQL(' AND ').join(sql.SQL('{} IS NOT NULL').format(sql.Identifier(x)) for x in cols)
        violations['duplicate:'+name]=q(sql.SQL('SELECT count(*) FROM (SELECT {} FROM {} WHERE {} GROUP BY {} HAVING count(*)>1) d').format(ids,sql.Identifier(table.split('.')[-1]),nonnull,ids))[0][0]
    for table,name,kind,definition,_ in constraints:
        if kind=='c':
            expression=definition.removeprefix('CHECK ').removesuffix(' NOT VALID')
            violations['check:'+name]=q(sql.SQL('SELECT count(*) FROM {} WHERE NOT ').format(sql.Identifier(table.split('.')[-1]))+sql.SQL(expression))[0][0]
    violations['trusted_identity']=q("SELECT count(*) FROM (SELECT account_id,source_system,source_transaction_id FROM transactions WHERE source_transaction_id IS NOT NULL GROUP BY 1,2,3 HAVING count(*)>1) x")[0][0]
    violations['batch_reconciliation']=q('SELECT count(*) FROM batch_reconciliation WHERE NOT counts_consistent')[0][0]
    assert sum(violations.values())==0
    assert len([r for r in objects if r[1]=='r'])==17 and len([r for r in objects if r[1]=='v'])==2
    integrity={'status':'PASSED','postgresql':version,'schemas':['public'],'objects':objects,'constraints':constraints,'indexes':indexes,'functions':q("SELECT proname,pg_get_userbyid(proowner),prosecdef FROM pg_proc WHERE pronamespace='public'::regnamespace ORDER BY proname"),'migration_history':q('SELECT version,source_sha256,catalog_sha256 FROM schema_migrations ORDER BY version'),'violations':violations,'unexplained_violations':sum(violations.values()),'actor_references':'Only SQL-enforced constraints checked; actor strings are not enterprise-directory foreign keys','seed_rows':200,'order':'empty Ã¢â€ â€™ authoritative base Ã¢â€ â€™ 001 Ã¢â€ â€™ 002 Ã¢â€ â€™ synthetic seed','aws_access':False}
    from tools.check_migration_roles_pg16 import expect_denied
    for file in ('permissions.sql','release1_permissions.sql'):q((ROOT/'infrastructure/rds'/file).read_text())
    c.commit();denials=[]
    with c.cursor() as cur:
        for role in ('fintrust_scoring','fintrust_workflow_api'):
            cur.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
            cur.execute('SELECT count(*) FROM public.transactions');assert cur.fetchone()==(200,)
            for statement in ('CREATE TABLE public.assurance_denied(id int)','DROP TABLE public.transactions','ALTER TABLE public.transactions ADD COLUMN assurance_denied int','CREATE FUNCTION public.assurance_denied() RETURNS int LANGUAGE sql AS $$SELECT 1$$'):
                expect_denied(cur,statement);denials.append({'role':role,'statement':statement,'result':'DENIED'})
            cur.execute('RESET ROLE')
    c.rollback()
    integrity['runtime_ddl_denials']=denials
    integrity['exact_relation_grants']=q("SELECT relname,relacl::text FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind IN ('r','v') ORDER BY relname")
    integrity['role_flags']=q("SELECT rolname,rolsuper,rolcreaterole,rolcreatedb,rolbypassrls FROM pg_roles WHERE rolname LIKE 'fintrust_%' ORDER BY rolname")
    out=Path(os.environ['FINTRUST_LOCAL_ASSURANCE_EVIDENCE']);out.mkdir(parents=True,exist_ok=True)
    (out/'postgres16-integrity.json').write_text(json.dumps(integrity,indent=2,default=str)+'\n',encoding='utf-8')
    account='20000000-0000-4000-8000-000000000001';plans=[]
    queries={'transactions':('SELECT * FROM transactions WHERE account_id=%s ORDER BY tx_date DESC,tx_id DESC LIMIT 25',(account,)), 'history':('SELECT * FROM transactions WHERE account_id=%s AND amount>50000 ORDER BY tx_date DESC LIMIT 25',(account,)), 'risk_events':('SELECT r.* FROM risk_events r JOIN transactions t USING(tx_id) WHERE t.account_id=%s LIMIT 25',(account,)), 'reviews':("SELECT w.* FROM risk_reviews w JOIN risk_events r USING(risk_event_id) JOIN transactions t USING(tx_id) WHERE t.account_id=%s AND w.review_status='OPEN' LIMIT 25",(account,)), 'monthly_summary':("SELECT date_trunc('month',tx_date),currency,count(*),sum(amount) FROM transactions WHERE account_id=%s GROUP BY 1,2",(account,)), 'risk_report':('SELECT r.reason,count(*) FROM risk_events r JOIN transactions t USING(tx_id) WHERE t.account_id=%s GROUP BY 1',(account,)), 'duplicate_lookup':("SELECT tx_id FROM transactions WHERE account_id=%s AND source_system='assurance-perf' AND source_transaction_id='PERF-999'",(account,)), 'dashboard':('SELECT currency,count(*),sum(amount) FROM transactions WHERE account_id=%s GROUP BY currency',(account,))}
    for size in (200,1000,10000):
        existing=q('SELECT count(*) FROM transactions')[0][0]
        if size>existing:
            q("""INSERT INTO transactions(account_id,amount,currency,merchant,tx_date,tx_type,raw_file,source_system,source_transaction_id)
              SELECT %s, (g%%100000)+1,'ZAR','Synthetic performance',NOW()-g*interval '1 minute','debit','synthetic/assurance.csv','assurance-perf','PERF-'||g FROM generate_series(%s,%s) g""",(account,existing+1,size))
            q("INSERT INTO risk_events(tx_id,risk_score,reason) SELECT tx_id,80,'Synthetic query benchmark' FROM transactions t WHERE source_system='assurance-perf' AND (substring(source_transaction_id from 6)::int)%100=0 AND NOT EXISTS(SELECT 1 FROM risk_events r WHERE r.tx_id=t.tx_id)")
            q("INSERT INTO risk_reviews(risk_event_id,change_actor) SELECT r.risk_event_id,'synthetic-benchmark' FROM risk_events r WHERE NOT EXISTS(SELECT 1 FROM risk_reviews w WHERE w.risk_event_id=r.risk_event_id)")
        q('ANALYZE')
        for label,(statement,args) in queries.items():
            plan=q('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+statement,args)[0][0][0]
            plans.append({'transactions':size,'operation':label,'execution_ms':plan['Execution Time'],'planning_ms':plan['Planning Time'],'plan':plan['Plan']})
    (out/'postgres16-query-plans.json').write_text(json.dumps({'scope':'Synthetic SQL query sanity; direct generation is not ingestion throughput','scales':[200,1000,10000],'plans':plans,'production_capacity':'DEFERRED'},indent=2,default=str)+'\n',encoding='utf-8')
    c.rollback();c.close();print('PostgreSQL 16 catalogue/integrity passed; zero violations; query plans measured at 200/1000/10000 rows.')
if __name__=='__main__':main()
