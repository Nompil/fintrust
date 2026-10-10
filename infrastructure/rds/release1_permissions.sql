-- PROPOSED: administrator review and disposable PG16 privilege verification required.
-- Apply only AFTER migration 002 through separately approved live rollout.
-- No logins, IAM membership, secret access or schema CREATE is granted here.
BEGIN;
DO $$ BEGIN
    IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='fintrust_workflow_api') THEN
        CREATE ROLE fintrust_workflow_api NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
    IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='fintrust_workflows_owner') THEN
        CREATE ROLE fintrust_workflows_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END $$;
GRANT USAGE ON SCHEMA public TO fintrust_workflow_api,fintrust_workflows_owner;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM fintrust_workflow_api;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM fintrust_workflow_api;
GRANT SELECT ON transactions,processed_transactions,risk_events,alerts,accounts,
    ingestion_batches,ingestion_attempts,ingestion_records,risk_reviews,risk_review_history,
    quarantine_cases,quarantine_corrections,projection_outbox,batch_reconciliation,quarantine_workflow TO fintrust_workflow_api;
GRANT INSERT ON ingestion_batches,ingestion_attempts,ingestion_records,quarantine_corrections,correction_outbox TO fintrust_workflow_api;
GRANT UPDATE(review_status,reviewer_subject,reviewed_by,reviewed_at,review_notes,resolution_code,
    change_actor,change_request_id,request_digest,version) ON risk_reviews TO fintrust_workflow_api;
GRANT UPDATE(quarantine_id) ON quarantine_cases TO fintrust_workflow_api;
-- Trigger writes history under a dedicated non-login role, never under browser/API authority.
GRANT INSERT ON risk_review_history TO fintrust_workflows_owner;
ALTER FUNCTION public.record_review_history() OWNER TO fintrust_workflows_owner;
REVOKE ALL ON FUNCTION public.record_review_history() FROM PUBLIC;
GRANT SELECT(status) ON accounts TO fintrust_scoring;
GRANT SELECT,INSERT,UPDATE ON ingestion_batches,ingestion_attempts,ingestion_records,correction_outbox,projection_outbox TO fintrust_scoring;
GRANT SELECT,INSERT ON quarantine_cases,risk_reviews TO fintrust_scoring;
GRANT EXECUTE ON FUNCTION public.guard_ingestion_record(),public.guard_review_transition(),
    public.record_review_history(),public.reject_history_change(),public.guard_batch_identity(),
    public.check_batch_record_count(),public.guard_correction_submission(),public.guard_quarantine_origin()
    TO fintrust_scoring,fintrust_workflow_api;
-- No UPDATE/DELETE on financial facts or history, no API INSERT into transactions/risk_events/history.
-- IAM logins inherit only one matching service role. HTTP roles are server-side registry assignments.
COMMIT;
