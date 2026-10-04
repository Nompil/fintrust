-- Apply after schema.sql as administrator in the dedicated FinTrust database.
-- Stage-specific IAM logins inherit only their matching service role.
BEGIN;
DO $$
DECLARE service TEXT;
BEGIN
    FOREACH service IN ARRAY ARRAY['ingest','scoring','alert','api','report'] LOOP
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='fintrust_' || service) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN', 'fintrust_' || service);
        END IF;
    END LOOP;
END $$;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM fintrust_ingest, fintrust_scoring, fintrust_alert, fintrust_api, fintrust_report;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM fintrust_ingest, fintrust_scoring, fintrust_alert, fintrust_api, fintrust_report;
GRANT USAGE ON SCHEMA public TO fintrust_ingest, fintrust_scoring, fintrust_alert, fintrust_api, fintrust_report;
GRANT SELECT(account_id) ON accounts TO fintrust_ingest;
-- UPDATE on the lock column is needed for SELECT ... FOR UPDATE.
GRANT SELECT(account_id), UPDATE(account_id) ON accounts TO fintrust_scoring;
GRANT SELECT, INSERT ON transactions, risk_events, processed_transactions TO fintrust_scoring;
GRANT USAGE ON SEQUENCE risk_events_risk_event_id_seq TO fintrust_scoring;
GRANT SELECT, UPDATE(tx_id) ON processed_transactions TO fintrust_alert;
GRANT SELECT, INSERT, UPDATE ON alerts TO fintrust_alert;
GRANT USAGE ON SEQUENCE alerts_alert_id_seq TO fintrust_alert;
GRANT SELECT ON transactions TO fintrust_api, fintrust_report;
GRANT SELECT(account_id, account_type, status) ON accounts TO fintrust_api;
COMMIT;
-- Cloud IAM logins are provisioned ONLY for scoring, api and report.
-- The ingest and alert NOLOGIN groups above support legacy local tools only.
-- For each cloud service/stage, provision LOGIN INHERIT NOCREATEDB NOCREATEROLE
-- NOSUPERUSER fintrust_<service>_<stage>, then grant its matching service role.
-- On RDS also GRANT rds_iam TO that login; SSM db_user must match exactly.
-- The local CSV teaching loader uses local credentials, never the ingest AWS role.
