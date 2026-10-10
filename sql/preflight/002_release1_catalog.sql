-- Proposed Release 1 catalog supplement; not packaged into the 001-only runner.
-- Execute only after separate private-runner approval. No row payloads or credentials.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '15s';
SET LOCAL search_path = pg_catalog;
WITH expected(name) AS (VALUES
 ('customers'),('accounts'),('transactions'),('risk_events'),('alerts'),
 ('processed_transactions'),('schema_migrations'),('ingestion_batches'),
 ('ingestion_attempts'),('ingestion_records'),('risk_reviews'),('risk_review_history'),
 ('quarantine_cases'),('quarantine_corrections'),('correction_outbox'),
 ('projection_outbox'),('operations_requests'),('batch_reconciliation'),('quarantine_workflow')),
objects AS (
 SELECT e.name,c.oid,c.relkind,c.relowner,c.relacl,c.relrowsecurity,c.relforcerowsecurity
 FROM expected e LEFT JOIN pg_namespace n ON n.nspname='public'
 LEFT JOIN pg_class c ON c.relnamespace=n.oid AND c.relname=e.name
)
SELECT jsonb_build_object(
 'read_only',current_setting('transaction_read_only'),
 'database',current_database(),'user',current_user,
 'version',current_setting('server_version'),
 'objects',(SELECT jsonb_agg(jsonb_build_object(
   'name',name,'present',oid IS NOT NULL,'kind',relkind,
   'owner',pg_get_userbyid(relowner),'acl',relacl::text,
   'rls',relrowsecurity,'force_rls',relforcerowsecurity,
   'can_select',CASE WHEN oid IS NOT NULL THEN has_table_privilege(oid,'SELECT') END)
   ORDER BY name) FROM objects),
 'columns',(SELECT jsonb_agg(jsonb_build_object('table',o.name,'name',a.attname,
   'type',format_type(a.atttypid,a.atttypmod),'not_null',a.attnotnull,
   'default_md5',md5(pg_get_expr(d.adbin,d.adrelid))) ORDER BY o.name,a.attnum)
   FROM objects o JOIN pg_attribute a ON a.attrelid=o.oid
   LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
   WHERE a.attnum>0 AND NOT a.attisdropped),
 'constraints',(SELECT jsonb_agg(jsonb_build_object('table',o.name,'name',k.conname,
   'type',k.contype,'validated',k.convalidated,'definition_md5',md5(pg_get_constraintdef(k.oid)))
   ORDER BY o.name,k.conname) FROM objects o JOIN pg_constraint k ON k.conrelid=o.oid),
 'indexes',(SELECT jsonb_agg(jsonb_build_object('table',o.name,'name',c.relname,
   'valid',i.indisvalid,'ready',i.indisready,'unique',i.indisunique,
   'definition_md5',md5(pg_get_indexdef(i.indexrelid))) ORDER BY o.name,c.relname)
   FROM objects o JOIN pg_index i ON i.indrelid=o.oid JOIN pg_class c ON c.oid=i.indexrelid),
 'trigger_functions',(SELECT jsonb_agg(jsonb_build_object('table',o.name,'trigger',t.tgname,
   'enabled',t.tgenabled,'function',p.proname,'owner',pg_get_userbyid(p.proowner),
   'security_definer',p.prosecdef,'acl',p.proacl::text,
   'definition_md5',md5(pg_get_functiondef(p.oid))) ORDER BY o.name,t.tgname)
   FROM objects o JOIN pg_trigger t ON t.tgrelid=o.oid
   JOIN pg_proc p ON p.oid=t.tgfoid WHERE NOT t.tgisinternal),
 'views',(SELECT jsonb_agg(jsonb_build_object('name',o.name,
   'definition_md5',md5(pg_get_viewdef(o.oid))) ORDER BY o.name)
   FROM objects o WHERE o.relkind='v'),
 'conditional_count_queries',(SELECT jsonb_agg(format(
   'SELECT count(*) AS row_count FROM %I.%I;', 'public',name) ORDER BY name)
   FROM objects WHERE relkind IN ('r','p') AND has_table_privilege(oid,'SELECT'))
) AS preflight;
ROLLBACK;
