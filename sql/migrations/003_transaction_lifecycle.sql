-- Additive processing audit; business dispositions/review state remain authoritative.
-- Apply after verified 001/002. Historical events are NOT fabricated or backfilled.
BEGIN;
CREATE TABLE public.transaction_lifecycle_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id UUID NOT NULL,
    source_row INTEGER NOT NULL,
    sequence INTEGER NOT NULL CHECK(sequence>0),
    event_type TEXT NOT NULL CHECK(event_type IN
      ('RECEIVED','QUEUED','VALIDATED','REVALIDATED','SCORED','STORED','QUARANTINED','DUPLICATE',
       'TECHNICAL_FAILURE','RETRY','RECOVERED','DLQ')),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    actor_subject TEXT NOT NULL CHECK(actor_subject='scoring-worker'),
    error_type TEXT CHECK(error_type ~ '^[A-Za-z_][A-Za-z0-9_]{0,99}$'),
    UNIQUE(batch_id,source_row,sequence),
    FOREIGN KEY(batch_id,source_row) REFERENCES public.ingestion_records(batch_id,source_row)
);
CREATE UNIQUE INDEX lifecycle_business_once ON public.transaction_lifecycle_events(batch_id,source_row,event_type)
 WHERE event_type NOT IN ('TECHNICAL_FAILURE','RETRY','RECOVERED');
CREATE FUNCTION public.validate_lifecycle_event() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
DECLARE previous text; previous_sequence integer; phase text; disposition text;
BEGIN
 SELECT i.disposition INTO disposition FROM public.ingestion_records i
 WHERE i.batch_id=NEW.batch_id AND i.source_row=NEW.source_row FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Unknown occurrence'; END IF;
 SELECT e.event_type,e.sequence INTO previous,previous_sequence FROM public.transaction_lifecycle_events e
 WHERE e.batch_id=NEW.batch_id AND e.source_row=NEW.source_row ORDER BY e.sequence DESC LIMIT 1;
 IF NEW.sequence<>COALESCE(previous_sequence,0)+1 THEN RAISE EXCEPTION 'Lifecycle sequence conflict'; END IF;
 SELECT e.event_type INTO phase FROM public.transaction_lifecycle_events e
 WHERE e.batch_id=NEW.batch_id AND e.source_row=NEW.source_row AND e.event_type IN
 ('RECEIVED','QUEUED','VALIDATED','REVALIDATED','SCORED','STORED','QUARANTINED','DUPLICATE')
 ORDER BY e.sequence DESC LIMIT 1;
 IF previous='DLQ' OR phase='QUARANTINED' THEN
   RAISE EXCEPTION 'Terminal occurrence cannot transition';
 END IF;
 IF NEW.event_type='RECEIVED' THEN
   IF previous IS NOT NULL THEN RAISE EXCEPTION 'Receipt already recorded'; END IF;
 ELSIF previous IS NULL THEN RAISE EXCEPTION 'Receipt required';
 ELSIF NEW.event_type='TECHNICAL_FAILURE' THEN
   IF NEW.error_type IS NULL OR previous='TECHNICAL_FAILURE' THEN RAISE EXCEPTION 'Failure context required'; END IF;
 ELSIF NEW.event_type='RETRY' THEN
   IF previous<>'TECHNICAL_FAILURE' THEN RAISE EXCEPTION 'Retry requires failure'; END IF;
 ELSIF NEW.event_type='DLQ' THEN
   IF previous<>'TECHNICAL_FAILURE' THEN RAISE EXCEPTION 'DLQ requires verified failure'; END IF;
 ELSIF NEW.event_type='RECOVERED' THEN
   IF NOT EXISTS(SELECT 1 FROM public.transaction_lifecycle_events f
      WHERE f.batch_id=NEW.batch_id AND f.source_row=NEW.source_row AND f.event_type='TECHNICAL_FAILURE'
      AND f.sequence>COALESCE((SELECT max(sequence) FROM public.transaction_lifecycle_events e
         WHERE e.batch_id=NEW.batch_id AND e.source_row=NEW.source_row AND e.event_type='RECOVERED'),0)
      AND EXISTS(SELECT 1 FROM public.transaction_lifecycle_events retry
        WHERE retry.batch_id=f.batch_id AND retry.source_row=f.source_row AND retry.event_type='RETRY'
        AND retry.sequence>f.sequence)) THEN RAISE EXCEPTION 'Recovery requires an observed failure and retry'; END IF;
   IF phase NOT IN ('STORED','DUPLICATE') OR NOT EXISTS(SELECT 1 FROM public.projection_outbox p JOIN public.ingestion_records i
     ON i.canonical_tx_id=p.tx_id WHERE i.batch_id=NEW.batch_id AND i.source_row=NEW.source_row
     AND p.state='COMPLETED') THEN RAISE EXCEPTION 'Recovery requires completed durable effects'; END IF;
 ELSIF previous='TECHNICAL_FAILURE' THEN RAISE EXCEPTION 'Retry required';
 ELSIF NEW.event_type='QUEUED' AND phase='RECEIVED' THEN NULL;
 ELSIF NEW.event_type IN ('VALIDATED','REVALIDATED','QUARANTINED') AND phase='QUEUED' THEN NULL;
 ELSIF NEW.event_type='QUARANTINED' AND phase IN ('VALIDATED','REVALIDATED') THEN NULL;
 ELSIF NEW.event_type='SCORED' AND phase IN ('VALIDATED','REVALIDATED') THEN NULL;
 ELSIF NEW.event_type='STORED' AND phase='SCORED' AND disposition='ACCEPTED' THEN NULL;
 ELSIF NEW.event_type='DUPLICATE' AND phase IN ('VALIDATED','REVALIDATED') AND disposition='DUPLICATE' THEN NULL;
 ELSE RAISE EXCEPTION 'Prohibited lifecycle transition'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER lifecycle_transition BEFORE INSERT ON public.transaction_lifecycle_events
 FOR EACH ROW EXECUTE FUNCTION public.validate_lifecycle_event();
CREATE TRIGGER lifecycle_immutable BEFORE UPDATE OR DELETE ON public.transaction_lifecycle_events
 FOR EACH ROW EXECUTE FUNCTION public.reject_history_change();
REVOKE ALL ON public.transaction_lifecycle_events FROM PUBLIC;
REVOKE ALL ON FUNCTION public.validate_lifecycle_event() FROM PUBLIC;
COMMIT;
