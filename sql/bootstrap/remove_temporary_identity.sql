-- Separate administrator cleanup approval; never called by IAM-phase handler.
DO $$ BEGIN
 IF current_user <> 'fintrust_admin' OR current_database() <> 'fintrust' THEN RAISE EXCEPTION 'cleanup identity mismatch'; END IF;
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='fintrust_migrate_dev') THEN RAISE EXCEPTION 'missing maintenance role requires review'; END IF;
 IF EXISTS (SELECT FROM pg_stat_activity WHERE usename='fintrust_migrate_dev') THEN RAISE EXCEPTION 'maintenance sessions still active'; END IF;
 IF EXISTS (SELECT FROM pg_class WHERE relowner=(SELECT oid FROM pg_roles WHERE rolname='fintrust_migrate_dev')) THEN RAISE EXCEPTION 'unexpected owned objects'; END IF;
END $$;
ALTER ROLE fintrust_migrate_dev NOLOGIN;
REVOKE fintrust_transactions_owner FROM fintrust_migrate_dev;
REVOKE rds_iam FROM fintrust_migrate_dev;
REVOKE SELECT (customer_id) ON public.customers FROM fintrust_migrate_dev;
REVOKE SELECT (account_id) ON public.accounts FROM fintrust_migrate_dev;
REVOKE SELECT (risk_event_id) ON public.risk_events FROM fintrust_migrate_dev;
REVOKE SELECT (alert_id) ON public.alerts FROM fintrust_migrate_dev;
REVOKE SELECT (tx_id) ON public.processed_transactions FROM fintrust_migrate_dev;
-- The transactions ACL grantor changed with ownership. Revoke as exact owner.
GRANT fintrust_transactions_owner TO fintrust_admin WITH SET TRUE, INHERIT FALSE, ADMIN FALSE;
SET LOCAL ROLE fintrust_transactions_owner;
REVOKE SELECT ON public.transactions FROM fintrust_migrate_dev;
RESET ROLE;
GRANT fintrust_transactions_owner TO fintrust_admin WITH SET FALSE, INHERIT FALSE, ADMIN FALSE;
REVOKE USAGE ON SCHEMA public FROM fintrust_migrate_dev;
REVOKE CONNECT ON DATABASE fintrust FROM fintrust_migrate_dev;
REVOKE SELECT (customer_id) ON public.customers FROM fintrust_transactions_owner;
REVOKE SELECT (account_id) ON public.accounts FROM fintrust_transactions_owner;
REVOKE SELECT (risk_event_id) ON public.risk_events FROM fintrust_transactions_owner;
REVOKE SELECT (alert_id) ON public.alerts FROM fintrust_transactions_owner;
REVOKE SELECT (tx_id) ON public.processed_transactions FROM fintrust_transactions_owner;
DROP ROLE fintrust_migrate_dev;
-- DROP ROLE fails transactionally on unexpected dependencies. Never DROP OWNED.
-- The persistent NOLOGIN transactions owner and existing application grants remain.
