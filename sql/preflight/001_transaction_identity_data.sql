-- Read-only phase B. STOP unless phase A confirms the six base tables, correct
-- base types, no unexpected RLS/triggers/ownership, and approved bounded size.
-- JSON field access allows legacy and partially migrated columns without dynamic SQL.
-- Only counts leave the database. No identifiers or transaction values are returned.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '15s';
SET LOCAL search_path = pg_catalog;
WITH records AS MATERIALIZED (SELECT to_jsonb(t) AS j FROM public.transactions t),
duplicates AS (
 SELECT 1 FROM records WHERE j->>'source_transaction_id' IS NOT NULL
 AND j->>'source_system' IS NOT NULL AND j->>'account_id' IS NOT NULL
 GROUP BY j->>'source_system',j->>'account_id',j->>'source_transaction_id' HAVING count(*)>1
)
SELECT jsonb_build_object(
 'read_only',current_setting('transaction_read_only'),
 'row_counts',jsonb_build_object('customers',(SELECT count(*) FROM public.customers),
   'accounts',(SELECT count(*) FROM public.accounts),'transactions',(SELECT count(*) FROM records),
   'risk_events',(SELECT count(*) FROM public.risk_events),'alerts',(SELECT count(*) FROM public.alerts),
   'processed_transactions',(SELECT count(*) FROM public.processed_transactions)),
 'duplicate_source_identity_groups',(SELECT count(*) FROM duplicates),
 'invalid_source_identity_rows',(SELECT count(*) FROM records WHERE j->>'source_transaction_id' IS NOT NULL
   AND (length(btrim(j->>'source_transaction_id'))=0 OR j->>'source_system' IS NULL OR length(btrim(j->>'source_system'))=0)),
 'invalid_fingerprint_rows',(SELECT count(*) FROM records WHERE j->>'transaction_fingerprint' IS NOT NULL
   AND j->>'transaction_fingerprint' !~ '^[0-9a-f]{64}$'),
 'invalid_file_hash_rows',(SELECT count(*) FROM records WHERE j->>'file_sha256' IS NOT NULL AND j->>'file_sha256' !~ '^[0-9a-f]{64}$'),
 'invalid_source_row_rows',(SELECT count(*) FROM records WHERE j->>'source_row' IS NOT NULL
   AND CASE WHEN j->>'source_row' ~ '^[0-9]+$' THEN (j->>'source_row')::numeric < 2 ELSE true END)
) AS preflight;
ROLLBACK;
