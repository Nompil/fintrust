-- Read-only phase A. Run only through the separately approved private runner.
-- No credential values, row data or pg_authid reads. Review definitions, not names alone.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '15s';
SET LOCAL search_path = pg_catalog;
SELECT jsonb_build_object(
 'database', current_database(), 'user', current_user, 'session_user', session_user,
 'version', current_setting('server_version'), 'version_num', current_setting('server_version_num'),
 'current_schema', current_schema(), 'search_path', current_setting('search_path'),
 'database_owner', (SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()),
 'database_acl', (SELECT datacl::text FROM pg_database WHERE datname=current_database()),
 'target_schema', 'public', 'read_only', current_setting('transaction_read_only'),
 'ssl', (SELECT to_jsonb(s) - 'pid' - 'client_dn' - 'issuer_dn' FROM pg_stat_ssl s WHERE pid=pg_backend_pid()),
 'schemas', (SELECT jsonb_agg(jsonb_build_object('name',nspname,'owner',pg_get_userbyid(nspowner),'acl',nspacl::text))
             FROM pg_namespace WHERE nspname='public'),
 'relations', (SELECT jsonb_agg(jsonb_build_object('name',c.relname,'kind',c.relkind,'owner',pg_get_userbyid(c.relowner),
               'acl',c.relacl::text,'estimated_rows',c.reltuples,'bytes',pg_total_relation_size(c.oid),
               'rls',c.relrowsecurity,'force_rls',c.relforcerowsecurity) ORDER BY c.relname)
               FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S')),
 'columns', (SELECT jsonb_agg(jsonb_build_object('table',c.relname,'name',a.attname,
             'type',format_type(a.atttypid,a.atttypmod),'not_null',a.attnotnull,
             'default',pg_get_expr(d.adbin,d.adrelid),'identity',a.attidentity,'generated',a.attgenerated) ORDER BY c.relname,a.attnum)
             FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
             JOIN pg_namespace n ON n.oid=c.relnamespace
             LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
             WHERE n.nspname='public' AND c.relkind IN ('r','p','v') AND a.attnum>0 AND NOT a.attisdropped),
 'constraints', (SELECT jsonb_agg(jsonb_build_object('table',c.relname,'name',k.conname,'type',k.contype,
                 'validated',k.convalidated,'definition',pg_get_constraintdef(k.oid)) ORDER BY c.relname,k.conname)
                 FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
                 JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'),
 'indexes', (SELECT jsonb_agg(jsonb_build_object('table',c.relname,'name',ic.relname,'unique',i.indisunique,
             'valid',i.indisvalid,'ready',i.indisready,'definition',pg_get_indexdef(i.indexrelid),
             'predicate',pg_get_expr(i.indpred,i.indrelid)) ORDER BY ic.relname)
             FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid JOIN pg_class ic ON ic.oid=i.indexrelid
             JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'),
 'triggers', (SELECT jsonb_agg(jsonb_build_object('table',c.relname,'definition',pg_get_triggerdef(t.oid),'enabled',t.tgenabled))
              FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
              WHERE n.nspname='public' AND NOT t.tgisinternal),
 'policies', (SELECT jsonb_agg(to_jsonb(p)) FROM pg_policies p WHERE schemaname='public'),
 'views', (SELECT jsonb_agg(jsonb_build_object('name',viewname,'definition',definition)) FROM pg_views WHERE schemaname='public'),
 'roles', (SELECT jsonb_agg(jsonb_build_object('name',rolname,'login',rolcanlogin,'superuser',rolsuper,
           'create_db',rolcreatedb,'create_role',rolcreaterole,'inherit',rolinherit,'bypass_rls',rolbypassrls))
           FROM pg_roles WHERE rolname LIKE 'fintrust%' OR rolname IN ('rds_iam','rds_superuser')),
 'memberships', (SELECT jsonb_agg(jsonb_build_object('member',m.rolname,'role',r.rolname,'admin',a.admin_option,
                 'inherit',a.inherit_option,'set',a.set_option)) FROM pg_auth_members a
                 JOIN pg_roles m ON m.oid=a.member JOIN pg_roles r ON r.oid=a.roleid WHERE m.rolname LIKE 'fintrust%'),
 'column_grants', (SELECT jsonb_agg(to_jsonb(g)) FROM information_schema.column_privileges g WHERE table_schema='public'),
 'default_grants', (SELECT jsonb_agg(jsonb_build_object('owner',pg_get_userbyid(defaclrole),'type',defaclobjtype,'acl',defaclacl::text))
                    FROM pg_default_acl WHERE defaclnamespace=0 OR defaclnamespace=(SELECT oid FROM pg_namespace WHERE nspname='public')),
 'other_sessions', (SELECT jsonb_agg(jsonb_build_object('user',usename,'state',state,'wait_type',wait_event_type,
                    'transaction_started',xact_start)) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()),
 'migration_columns_present', (SELECT count(*) FROM pg_attribute WHERE attrelid=to_regclass('public.transactions')
    AND NOT attisdropped AND attname IN ('source_system','source_transaction_id','transaction_fingerprint','batch_id','file_sha256','source_row','country')),
 'migration_indexes_present', (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind='i' AND c.relname IN ('idx_tx_source_identity','idx_tx_duplicate_charge'))
) AS preflight;
ROLLBACK;
