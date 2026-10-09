-- PROPOSED RELEASE 1 SCHEMA. Local tests only; not approved for live application.
-- Requires canonical base schema and migration 001. No financial history changes.
BEGIN;
CREATE TABLE public.ingestion_batches (
    batch_id UUID PRIMARY KEY,
    source_system VARCHAR(100) NOT NULL CHECK (length(btrim(source_system))>0),
    source_bucket TEXT NOT NULL CHECK (length(source_bucket)>0),
    file_sha256 CHAR(64) NOT NULL CHECK (file_sha256 ~ '^[0-9a-f]{64}$'),
    received_at TIMESTAMPTZ NOT NULL,
    rows_received INTEGER CHECK (rows_received>=0),
    publication_complete BOOLEAN NOT NULL DEFAULT FALSE,
    file_failure_code TEXT,
    UNIQUE(source_bucket,file_sha256)
);
CREATE TABLE public.ingestion_attempts (
    attempt_id UUID PRIMARY KEY,
    batch_id UUID REFERENCES public.ingestion_batches(batch_id),
    source_bucket TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_version TEXT,
    source_etag TEXT,
    received_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('RECEIVED','PROCESSING','PUBLISHED','DUPLICATE_FILE','FAILED')),
    error_code TEXT,
    -- Whole-file replay belongs to an attempt, never a new batch of money.
    UNIQUE(batch_id,attempt_id)
);
CREATE TABLE public.ingestion_records (
    batch_id UUID NOT NULL REFERENCES public.ingestion_batches(batch_id),
    source_row INTEGER NOT NULL CHECK (source_row>=2),
    source_attempt_id UUID NOT NULL,
    disposition TEXT NOT NULL CHECK (disposition IN ('RECEIVED','QUEUED','ACCEPTED','QUARANTINED','DUPLICATE','FAILED_TECHNICAL')),
    canonical_tx_id UUID REFERENCES public.transactions(tx_id),
    reason_code TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(batch_id,source_row),
    FOREIGN KEY(batch_id,source_attempt_id) REFERENCES public.ingestion_attempts(batch_id,attempt_id),
    CHECK (disposition<>'ACCEPTED' OR canonical_tx_id IS NOT NULL),
    CHECK (disposition NOT IN ('QUARANTINED','DUPLICATE','FAILED_TECHNICAL') OR length(btrim(reason_code))>0 AND reason_code IS NOT NULL)
);
CREATE FUNCTION public.guard_ingestion_record() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$
BEGIN
    IF NEW.batch_id<>OLD.batch_id OR NEW.source_row<>OLD.source_row OR NEW.source_attempt_id<>OLD.source_attempt_id THEN
        RAISE EXCEPTION 'Record occurrence identity is immutable';
    END IF;
    IF OLD.disposition IN ('ACCEPTED','QUARANTINED','DUPLICATE') AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Terminal outcome is immutable; correction requires new occurrence';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER ingestion_record_guard BEFORE UPDATE ON public.ingestion_records
FOR EACH ROW EXECUTE FUNCTION public.guard_ingestion_record();

CREATE TABLE public.risk_reviews (
    risk_event_id BIGINT PRIMARY KEY REFERENCES public.risk_events(risk_event_id),
    review_status TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (review_status IN ('OPEN','UNDER_REVIEW','CLEARED','CONFIRMED_RISK','ESCALATED')),
    reviewer_subject TEXT,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT NOT NULL DEFAULT '',
    resolution_code TEXT,
    change_actor TEXT NOT NULL CHECK (length(btrim(change_actor))>0),
    change_request_id UUID NOT NULL DEFAULT gen_random_uuid(),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version>0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (review_status='OPEN' OR length(btrim(reviewer_subject))>0 AND reviewer_subject IS NOT NULL),
    CHECK (review_status NOT IN ('CLEARED','CONFIRMED_RISK','ESCALATED') OR
        reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL AND
        CASE review_status WHEN 'CLEARED' THEN resolution_code='VALID_ACTIVITY'
            WHEN 'CONFIRMED_RISK' THEN resolution_code='CONFIRMED_SUSPICIOUS'
            ELSE resolution_code='SPECIALIST_REVIEW' END AND resolution_code IS NOT NULL)
);
-- Transaction ID comes from the risk-event FK, avoiding contradictory redundant IDs.
CREATE TABLE public.risk_review_history (
    risk_event_id BIGINT NOT NULL REFERENCES public.risk_reviews(risk_event_id),
    version INTEGER NOT NULL,
    request_id UUID NOT NULL UNIQUE,
    before_status TEXT,
    after_status TEXT NOT NULL,
    actor_subject TEXT NOT NULL,
    reviewer_subject TEXT,
    notes TEXT NOT NULL,
    resolution_code TEXT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(risk_event_id,version)
);
CREATE FUNCTION public.guard_review_transition() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$
BEGIN
    IF TG_OP='INSERT' THEN
        IF NEW.review_status<>'OPEN' OR NEW.version<>1 THEN RAISE EXCEPTION 'Review must open at version 1'; END IF;
        IF NOT EXISTS (SELECT 1 FROM public.risk_events WHERE risk_event_id=NEW.risk_event_id AND risk_score>=40) THEN
            RAISE EXCEPTION 'Review requires a Medium or High risk event';
        END IF;
    ELSE
        IF NEW.risk_event_id<>OLD.risk_event_id OR NEW.created_at<>OLD.created_at OR NEW.version<>OLD.version+1 OR NEW.change_request_id=OLD.change_request_id THEN
            RAISE EXCEPTION 'Review identity or version conflict';
        END IF;
        IF NOT ((OLD.review_status='OPEN' AND NEW.review_status='UNDER_REVIEW') OR
            (OLD.review_status='UNDER_REVIEW' AND NEW.review_status IN ('CLEARED','CONFIRMED_RISK','ESCALATED')) OR
            (OLD.review_status IN ('ESCALATED','CLEARED','CONFIRMED_RISK') AND NEW.review_status='UNDER_REVIEW')) THEN
            RAISE EXCEPTION 'Invalid review transition';
        END IF;
        IF length(btrim(NEW.review_notes))=0 THEN RAISE EXCEPTION 'Review note required'; END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE FUNCTION public.record_review_history() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$
BEGIN
    INSERT INTO public.risk_review_history(risk_event_id,version,request_id,before_status,after_status,actor_subject,reviewer_subject,notes,resolution_code)
    VALUES(NEW.risk_event_id,NEW.version,NEW.change_request_id,CASE WHEN TG_OP='UPDATE' THEN OLD.review_status ELSE NULL END,
        NEW.review_status,NEW.change_actor,NEW.reviewer_subject,NEW.review_notes,NEW.resolution_code);
    RETURN NEW;
END $$;
CREATE FUNCTION public.reject_history_change() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$
BEGIN RAISE EXCEPTION 'Audit history cannot be updated or deleted'; END $$;
CREATE TRIGGER review_transition_guard BEFORE INSERT OR UPDATE ON public.risk_reviews
FOR EACH ROW EXECUTE FUNCTION public.guard_review_transition();
CREATE TRIGGER review_history_record AFTER INSERT OR UPDATE ON public.risk_reviews
FOR EACH ROW EXECUTE FUNCTION public.record_review_history();
CREATE TRIGGER review_history_immutable BEFORE UPDATE OR DELETE ON public.risk_review_history
FOR EACH ROW EXECUTE FUNCTION public.reject_history_change();

CREATE TABLE public.quarantine_cases (
    quarantine_id UUID PRIMARY KEY,
    batch_id UUID NOT NULL,
    source_row INTEGER NOT NULL,
    reason_code TEXT NOT NULL CHECK (length(btrim(reason_code))>0),
    reason_detail TEXT NOT NULL CHECK (length(btrim(reason_detail))>0),
    safe_payload_key TEXT NOT NULL CHECK (length(safe_payload_key)>0),
    safe_payload_version TEXT NOT NULL CHECK (length(safe_payload_version)>0),
    source_reference TEXT,
    quarantined_at TIMESTAMPTZ NOT NULL,
    -- Original evidence is immutable. State is derived from correction outcomes.
    UNIQUE(batch_id,source_row),
    FOREIGN KEY(batch_id,source_row) REFERENCES public.ingestion_records(batch_id,source_row)
);
CREATE TRIGGER quarantine_evidence_immutable BEFORE UPDATE OR DELETE ON public.quarantine_cases
FOR EACH ROW EXECUTE FUNCTION public.reject_history_change();
CREATE TABLE public.quarantine_corrections (
    correction_id UUID PRIMARY KEY,
    quarantine_id UUID NOT NULL REFERENCES public.quarantine_cases(quarantine_id),
    request_id UUID NOT NULL UNIQUE,
    correction_version INTEGER NOT NULL DEFAULT 1 CHECK (correction_version>0),
    UNIQUE(quarantine_id,correction_version),
    submitted_by TEXT NOT NULL CHECK (length(btrim(submitted_by))>0),
    submitted_at TIMESTAMPTZ NOT NULL,
    correction_notes TEXT NOT NULL CHECK (length(btrim(correction_notes))>0),
    corrected_payload_key TEXT,
    corrected_payload_version TEXT,
    action TEXT NOT NULL CHECK (action IN ('RESUBMIT','REJECT')),
    reprocess_batch_id UUID,
    reprocess_source_row INTEGER,
    CHECK ((action='REJECT' AND corrected_payload_key IS NULL AND corrected_payload_version IS NULL
            AND reprocess_batch_id IS NULL AND reprocess_source_row IS NULL) OR
           (action='RESUBMIT' AND length(corrected_payload_key)>0 AND corrected_payload_key IS NOT NULL
            AND length(corrected_payload_version)>0 AND corrected_payload_version IS NOT NULL
            AND reprocess_batch_id IS NOT NULL AND reprocess_source_row IS NOT NULL)),
    FOREIGN KEY(reprocess_batch_id,reprocess_source_row)
        REFERENCES public.ingestion_records(batch_id,source_row)
);
CREATE TRIGGER correction_evidence_immutable BEFORE UPDATE OR DELETE ON public.quarantine_corrections
FOR EACH ROW EXECUTE FUNCTION public.reject_history_change();
CREATE UNIQUE INDEX quarantine_one_active_resolution ON public.quarantine_corrections(quarantine_id)
WHERE action='REJECT';
CREATE INDEX ingestion_records_tx ON public.ingestion_records(canonical_tx_id) WHERE canonical_tx_id IS NOT NULL;
CREATE INDEX risk_reviews_queue ON public.risk_reviews(review_status,created_at,risk_event_id);
CREATE INDEX correction_case_time ON public.quarantine_corrections(quarantine_id,submitted_at,correction_id);

CREATE VIEW public.batch_reconciliation AS
WITH counts AS (
    SELECT b.batch_id,b.rows_received,b.publication_complete,b.file_failure_code,
        count(r.source_row) AS recorded,
        count(*) FILTER(WHERE r.disposition='ACCEPTED') AS accepted,
        count(*) FILTER(WHERE r.disposition='QUARANTINED') AS quarantined,
        count(*) FILTER(WHERE r.disposition='DUPLICATE') AS duplicate,
        count(*) FILTER(WHERE r.disposition='FAILED_TECHNICAL') AS failed_technical
    FROM public.ingestion_batches b LEFT JOIN public.ingestion_records r USING(batch_id)
    GROUP BY b.batch_id
), reconciled AS (
    SELECT *,rows_received-accepted-quarantined-duplicate-failed_technical AS pending,
        rows_received IS NOT NULL AND recorded<=rows_received AS counts_consistent FROM counts
)
SELECT *,CASE
    WHEN NOT counts_consistent THEN CASE WHEN file_failure_code IS NOT NULL THEN 'FAILED' ELSE 'RECEIVED' END
    WHEN file_failure_code IS NOT NULL OR failed_technical>0 THEN
        CASE WHEN accepted+quarantined+duplicate>0 THEN 'PARTIAL' ELSE 'FAILED' END
    WHEN pending>0 THEN CASE WHEN publication_complete THEN 'PUBLISHED' ELSE 'PROCESSING' END
    ELSE 'COMPLETED' END AS status
FROM reconciled;
-- No alert table duplication: cloud delivery claims remain DynamoDB ALERT#canonical_tx.
-- No runtime grants, authentication implementation, secrets, or deployment in this migration.
-- SECURITY INVOKER functions do not authenticate browser actors; API RBAC remains required.
REVOKE ALL ON FUNCTION public.guard_ingestion_record(), public.guard_review_transition(),
    public.record_review_history(), public.reject_history_change() FROM PUBLIC;

CREATE FUNCTION public.guard_batch_identity() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$
BEGIN
    IF NEW.batch_id<>OLD.batch_id OR NEW.source_bucket<>OLD.source_bucket OR
       NEW.source_system<>OLD.source_system OR NEW.file_sha256<>OLD.file_sha256 OR
       NEW.received_at<>OLD.received_at OR
       (OLD.rows_received IS NOT NULL AND NEW.rows_received IS DISTINCT FROM OLD.rows_received) THEN
        RAISE EXCEPTION 'Batch identity, receipt clock and parsed total are immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER batch_identity_guard BEFORE UPDATE ON public.ingestion_batches
FOR EACH ROW EXECUTE FUNCTION public.guard_batch_identity();
CREATE FUNCTION public.check_batch_record_count() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$
DECLARE total integer; actual bigint;
BEGIN
    SELECT rows_received INTO total FROM public.ingestion_batches WHERE batch_id=NEW.batch_id FOR UPDATE;
    SELECT count(*) INTO actual FROM public.ingestion_records WHERE batch_id=NEW.batch_id;
    IF total IS NOT NULL AND actual>total THEN RAISE EXCEPTION 'Record count exceeds parsed batch total'; END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER batch_record_count AFTER INSERT OR UPDATE ON public.ingestion_records
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.check_batch_record_count();
CREATE CONSTRAINT TRIGGER batch_total_count AFTER INSERT OR UPDATE ON public.ingestion_batches
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.check_batch_record_count();
CREATE FUNCTION public.guard_correction_submission() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$
DECLARE previous_action text; previous_disposition text; previous_version integer;
BEGIN
    PERFORM 1 FROM public.quarantine_cases WHERE quarantine_id=NEW.quarantine_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Unknown quarantine case'; END IF;
    SELECT c.action,r.disposition,c.correction_version INTO previous_action,previous_disposition,previous_version
    FROM public.quarantine_corrections c LEFT JOIN public.ingestion_records r
        ON r.batch_id=c.reprocess_batch_id AND r.source_row=c.reprocess_source_row
    WHERE c.quarantine_id=NEW.quarantine_id ORDER BY c.correction_version DESC LIMIT 1;
    NEW.correction_version := COALESCE(previous_version,0)+1;
    IF previous_action='REJECT' OR (previous_action='RESUBMIT' AND previous_disposition<>'QUARANTINED') THEN
        RAISE EXCEPTION 'Case resolved or correction still requires reconciliation';
    END IF;
    IF NEW.action='RESUBMIT' AND EXISTS (SELECT 1 FROM public.quarantine_cases
        WHERE quarantine_id=NEW.quarantine_id AND batch_id=NEW.reprocess_batch_id AND source_row=NEW.reprocess_source_row) THEN
        RAISE EXCEPTION 'Correction requires a new record occurrence';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER correction_submission_guard BEFORE INSERT ON public.quarantine_corrections
FOR EACH ROW EXECUTE FUNCTION public.guard_correction_submission();
CREATE VIEW public.quarantine_workflow AS
SELECT q.*,c.correction_id,r.canonical_tx_id,
    CASE WHEN c.correction_id IS NULL THEN 'OPEN'
         WHEN c.action='REJECT' THEN 'REJECTED'
         WHEN r.disposition IN ('ACCEPTED','DUPLICATE') THEN 'RESOLVED'
         WHEN r.disposition='QUARANTINED' THEN 'OPEN'
         ELSE 'RESUBMITTED' END AS workflow_status
FROM public.quarantine_cases q
LEFT JOIN LATERAL (SELECT * FROM public.quarantine_corrections c WHERE c.quarantine_id=q.quarantine_id
    ORDER BY correction_version DESC LIMIT 1) c ON TRUE
LEFT JOIN public.ingestion_records r ON r.batch_id=c.reprocess_batch_id AND r.source_row=c.reprocess_source_row;
REVOKE ALL ON FUNCTION public.guard_batch_identity(),public.check_batch_record_count(),
    public.guard_correction_submission() FROM PUBLIC;

CREATE FUNCTION public.guard_quarantine_origin() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.ingestion_records WHERE batch_id=NEW.batch_id
        AND source_row=NEW.source_row AND disposition='QUARANTINED') THEN
        RAISE EXCEPTION 'Quarantine case requires a quarantined record occurrence';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER quarantine_origin_guard BEFORE INSERT ON public.quarantine_cases
FOR EACH ROW EXECUTE FUNCTION public.guard_quarantine_origin();
REVOKE ALL ON FUNCTION public.guard_quarantine_origin() FROM PUBLIC;
CREATE TRIGGER ingestion_record_no_delete BEFORE DELETE ON public.ingestion_records
FOR EACH ROW EXECUTE FUNCTION public.reject_history_change();
COMMIT;
