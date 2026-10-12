-- Local-only reviewed assignment extension; no live application is authorized.
-- Reuses reviewer_subject/version and immutable risk_review_history. No new state table.
BEGIN;
CREATE OR REPLACE FUNCTION public.guard_review_transition() RETURNS trigger
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
            (OLD.review_status='ESCALATED' AND NEW.review_status='ESCALATED' AND
             NEW.reviewer_subject IS DISTINCT FROM OLD.reviewer_subject AND NEW.reviewed_by=OLD.reviewed_by AND
             NEW.reviewed_at=OLD.reviewed_at AND NEW.resolution_code=OLD.resolution_code) OR
            (OLD.review_status='UNDER_REVIEW' AND NEW.review_status='UNDER_REVIEW' AND
             NEW.reviewer_subject IS DISTINCT FROM OLD.reviewer_subject AND NEW.reviewed_by IS NULL AND NEW.reviewed_at IS NULL AND NEW.resolution_code IS NULL) OR
            (OLD.review_status='UNDER_REVIEW' AND NEW.review_status='OPEN' AND NEW.reviewer_subject IS NULL AND
             NEW.reviewed_by IS NULL AND NEW.reviewed_at IS NULL AND NEW.resolution_code IS NULL) OR
            (OLD.review_status='UNDER_REVIEW' AND NEW.review_status IN ('CLEARED','CONFIRMED_RISK','ESCALATED')) OR
            (OLD.review_status IN ('ESCALATED','CLEARED','CONFIRMED_RISK') AND NEW.review_status='UNDER_REVIEW')) THEN
            RAISE EXCEPTION 'Invalid review transition';
        END IF;
        IF length(btrim(NEW.review_notes))=0 THEN RAISE EXCEPTION 'Review note required'; END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE INDEX risk_reviews_assignee_queue ON public.risk_reviews(reviewer_subject,review_status,created_at,risk_event_id);
COMMIT;
