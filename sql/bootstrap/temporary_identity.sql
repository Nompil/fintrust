-- Fixed administrator-only operation. Transaction owned by runner.
-- Existing roles or unexpected ownership require review, never automatic repair.
DO $$ BEGIN
 IF current_user <> 'fintrust_admin' OR current_database() <> 'fintrust' THEN
   RAISE EXCEPTION 'bootstrap identity mismatch';
 END IF;
 IF EXISTS (SELECT FROM pg_roles WHERE rolname IN ('fintrust_migrate_dev','fintrust_transactions_owner','fintrust_index_builder')) THEN
   RAISE EXCEPTION 'existing maintenance role requires review';
 END IF;
 IF (SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid='public.transactions'::regclass) <> current_user THEN
   RAISE EXCEPTION 'table ownership requires review';
 END IF;
 IF to_regprocedure('public.fintrust_create_identity_indexes()') IS NOT NULL THEN
   RAISE EXCEPTION 'existing index helper requires review';
 END IF;
END $$;
CREATE ROLE fintrust_transactions_owner NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE fintrust_migrate_dev LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 1;
GRANT rds_iam TO fintrust_migrate_dev;
GRANT CONNECT ON DATABASE fintrust TO fintrust_migrate_dev;
GRANT USAGE ON SCHEMA public TO fintrust_migrate_dev, fintrust_transactions_owner;
GRANT SELECT ON public.transactions TO fintrust_migrate_dev;
GRANT SELECT (customer_id) ON public.customers TO fintrust_migrate_dev;
GRANT SELECT (account_id) ON public.accounts TO fintrust_migrate_dev;
GRANT SELECT (risk_event_id) ON public.risk_events TO fintrust_migrate_dev;
GRANT SELECT (alert_id) ON public.alerts TO fintrust_migrate_dev;
GRANT SELECT (tx_id) ON public.processed_transactions TO fintrust_migrate_dev;
-- SET ROLE changes SELECT rights too: fixed aggregate postchecks require these.
GRANT SELECT (customer_id) ON public.customers TO fintrust_transactions_owner;
GRANT SELECT (account_id) ON public.accounts TO fintrust_transactions_owner;
GRANT SELECT (risk_event_id) ON public.risk_events TO fintrust_transactions_owner;
GRANT SELECT (alert_id) ON public.alerts TO fintrust_transactions_owner;
GRANT SELECT (tx_id) ON public.processed_transactions TO fintrust_transactions_owner;
-- PostgreSQL 16 gives the creator ADMIN via the bootstrap superuser.
-- Self-grants control SET only: repeating ADMIN TRUE creates a grant cycle.
GRANT fintrust_transactions_owner TO fintrust_admin WITH SET TRUE, INHERIT FALSE, ADMIN FALSE;
GRANT CREATE ON SCHEMA public TO fintrust_transactions_owner;
ALTER TABLE public.transactions OWNER TO fintrust_transactions_owner;
REVOKE CREATE ON SCHEMA public FROM fintrust_transactions_owner;
-- Ownership/ACL operations require the controlled SET path after transfer.
SET LOCAL ROLE fintrust_transactions_owner;
-- Ownership conveys DDL, not a permanent runtime DML role.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON public.transactions FROM fintrust_transactions_owner;
RESET ROLE;
GRANT fintrust_transactions_owner TO fintrust_migrate_dev WITH SET TRUE, INHERIT FALSE, ADMIN FALSE;
-- Creator ADMIN membership is supplied by PostgreSQL, not this self-grant.
-- Disable only the separate self-granted SET/inheritance path after bootstrap.
GRANT fintrust_transactions_owner TO fintrust_admin WITH SET FALSE, INHERIT FALSE, ADMIN FALSE;

-- Privileged index capability is held by a separate NOLOGIN definer owner.
-- The migration login has neither membership nor SET access to this role.
CREATE ROLE fintrust_index_builder NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT USAGE, CREATE ON SCHEMA public TO fintrust_index_builder;
GRANT fintrust_transactions_owner TO fintrust_index_builder WITH INHERIT TRUE, SET FALSE, ADMIN FALSE;
GRANT fintrust_index_builder TO fintrust_admin WITH SET TRUE, INHERIT FALSE, ADMIN FALSE;
