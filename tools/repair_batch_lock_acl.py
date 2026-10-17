"""Fixed one-column ACL repair. No event-supplied SQL or financial writes."""
import sys,json,os
sys.path.insert(0,'/opt')
import boto3,psycopg2
def handler(event,context):
 if event!={'operation':'repair_batch_lock_acl'}:raise ValueError('Unsupported operation')
 secret=json.loads(boto3.client('secretsmanager',region_name='af-south-1').get_secret_value(SecretId='arn:aws:secretsmanager:af-south-1:966467878406:secret:rds!db-e93012ae-0d14-4225-bdc3-988f4d98f72a-BbEGMn',VersionStage='AWSCURRENT')['SecretString'])
 assert secret['username']=='fintrust_admin'
 conn=psycopg2.connect(host='fintrust-ledger-dev.cv84aee6u6up.af-south-1.rds.amazonaws.com',port=5432,dbname='fintrust',user=secret['username'],password=secret['password'],sslmode='verify-full',sslrootcert='/opt/certs/global-bundle.pem',connect_timeout=10)
 secret.clear()
 try:
  with conn:
   with conn.cursor() as c:
    c.execute("SET LOCAL statement_timeout='20s'; SET LOCAL lock_timeout='5s'")
    c.execute("SELECT current_user");assert c.fetchone()==('fintrust_admin',)
    c.execute("SELECT version FROM public.schema_migrations ORDER BY version");assert c.fetchall()==[(i,) for i in range(1,7)]
    c.execute("SELECT pg_advisory_xact_lock(hashtext('fintrust-runtime-batch-lock-repair'))")
    c.execute("SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname='fintrust_workflow_api'");assert c.fetchone()==(False,False,False,False)
    c.execute("SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid='public.ingestion_batches'::regclass");owner=c.fetchone()[0];assert owner=='fintrust_workflow_owner'
    c.execute("SELECT has_column_privilege('fintrust_workflow_api','public.ingestion_batches','batch_id','UPDATE')");before=c.fetchone()[0]
    c.execute('GRANT fintrust_workflow_owner TO fintrust_admin WITH SET TRUE, INHERIT TRUE, ADMIN FALSE')
    c.execute('SET LOCAL ROLE fintrust_workflow_owner')
    c.execute('GRANT UPDATE(batch_id) ON public.ingestion_batches TO fintrust_workflow_api')
    c.execute('RESET ROLE')
    c.execute('GRANT fintrust_workflow_owner TO fintrust_admin WITH SET FALSE, INHERIT FALSE, ADMIN FALSE')
    c.execute("SELECT has_column_privilege('fintrust_workflow_api','public.ingestion_batches','batch_id','UPDATE')");assert c.fetchone()==(True,)
    for table in ('transactions','risk_events','risk_review_history'):
     for action in ('INSERT','UPDATE','DELETE'):
      c.execute('SELECT has_table_privilege(%s,%s,%s)',('fintrust_api_dev','public.'+table,action));assert c.fetchone()==(False,)
  return {'status':'ONE_COLUMN_BATCH_LOCK_ACL_REPAIRED','previously_allowed':before,'allowed_now':True,'financial_dml_executed':False,'api_financial_writes_denied':True}
 except Exception as error:
  # Only PostgreSQL's fixed permission object metadata, never secret/row values.
  if isinstance(error,psycopg2.Error):print(json.dumps({'error_type':type(error).__name__,'sqlstate':error.pgcode,'table':error.diag.table_name}))
  raise RuntimeError('Fixed ACL repair stopped') from None
 finally:conn.close()
