"""Account-authorized lifecycle reads assembled from existing domain records.
An occurrence timeline is processing evidence; risk/review/delivery remain separate.
"""
import uuid
from . import workflow_api as api

def occurrence(batch,row,principal):
    principal.require('read');batch=str(uuid.UUID(batch));row=int(row)
    rows=api._query("""SELECT i.*,b.received_at,b.source_system,a.source_bucket,a.source_file,a.source_version,a.source_etag,
        t.account_id,q.candidate_account_id,q.quarantine_id,q.quarantined_at
        FROM ingestion_records i JOIN ingestion_batches b USING(batch_id)
        JOIN ingestion_attempts a ON a.attempt_id=i.source_attempt_id
        LEFT JOIN transactions t ON t.tx_id=i.canonical_tx_id
        LEFT JOIN quarantine_cases q ON q.batch_id=i.batch_id AND q.source_row=i.source_row
        WHERE i.batch_id=%s AND i.source_row=%s""",(batch,row))
    if not rows: raise api.NotFound()
    value=rows[0];account=value['account_id'] or value['candidate_account_id']
    if account:
        try: principal.account(account)
        except PermissionError:
            # Same unknown-account authority as quarantine_detail.
            known=api._query('SELECT 1 FROM accounts WHERE account_id=%s',(account,))
            if principal.role!='Admin' or known: raise api.NotFound() from None
    elif principal.role!='Admin': raise api.NotFound()
    events=api._query('SELECT event_id,sequence,event_type,occurred_at,actor_subject,error_type FROM transaction_lifecycle_events WHERE batch_id=%s AND source_row=%s ORDER BY sequence LIMIT 1001',(batch,row))
    truncated=len(events)>1000;events=events[:1000]
    latest=api._query('SELECT event_type FROM transaction_lifecycle_events WHERE batch_id=%s AND source_row=%s ORDER BY sequence DESC LIMIT 1',(batch,row))
    for event in events:event['actor_type']='SYSTEM'
    disposition=value['disposition']
    current='STORED' if disposition=='ACCEPTED' else 'DUPLICATE' if disposition=='DUPLICATE' else 'QUARANTINED' if disposition=='QUARANTINED' else latest[0]['event_type'] if latest else disposition
    value.update(current_state=current,processing_state=latest[0]['event_type'] if latest else 'NOT_OBSERVED',timeline=events,
        timeline_complete=bool(events) and not truncated,timeline_truncated=truncated,timeline_note='Worker observation times; received_at is immutable source receipt. QUEUED means candidate handoff to worker, not validation success or proof of live SQS transport.')
    if value['quarantine_id']:
        corrections=api._query('SELECT correction_id,action,submitted_by,submitted_at,reprocess_batch_id,reprocess_source_row FROM quarantine_corrections WHERE quarantine_id=%s ORDER BY correction_version',(value['quarantine_id'],))
        value['corrections']=corrections
        value['correction_timeline']=[dict(event_type='CORRECTED' if c['action']=='RESUBMIT' else 'REJECTED',occurred_at=c['submitted_at'],actor_subject=c['submitted_by'],actor_type='HUMAN',reprocess_batch_id=c['reprocess_batch_id'],reprocess_source_row=c['reprocess_source_row']) for c in corrections]
    return value

def transaction(identifier,principal):
    principal.require('read');identifier=str(uuid.UUID(identifier))
    rows=api._query('SELECT t.*,p.result AS risk,p.processed_at FROM transactions t LEFT JOIN processed_transactions p USING(tx_id) WHERE t.tx_id=%s AND t.account_id=ANY(%s::uuid[])',(identifier,list(principal.accounts)))
    if not rows:raise api.NotFound()
    value=rows[0]
    occurrences=api._query('SELECT batch_id,source_row FROM ingestion_records WHERE canonical_tx_id=%s ORDER BY batch_id,source_row LIMIT 101',(identifier,))
    occurrences_truncated=len(occurrences)>100;occurrences=occurrences[:100]
    value['occurrences']=[occurrence(str(o['batch_id']),o['source_row'],principal) for o in occurrences]
    history=api._query('SELECT h.* FROM risk_review_history h JOIN risk_events r USING(risk_event_id) WHERE r.tx_id=%s ORDER BY h.changed_at DESC,h.version DESC LIMIT 1001',(identifier,))
    history_truncated=len(history)>1000;history=list(reversed(history[:1000]))
    value['review_state']=history[-1]['after_status'] if history else 'NOT_REQUIRED' if value['risk'] else 'NOT_ASSESSED'
    value['risk_state']=(value['risk'] or {}).get('risk_level','NOT_ASSESSED')
    value['current_state']='STORED';value['review_history']=history
    timeline=[]
    corrections=api._query('SELECT c.submitted_by,c.submitted_at,c.action,c.quarantine_id FROM quarantine_corrections c WHERE EXISTS(SELECT 1 FROM ingestion_records i WHERE i.batch_id=c.reprocess_batch_id AND i.source_row=c.reprocess_source_row AND i.canonical_tx_id=%s) ORDER BY c.submitted_at LIMIT 101',(identifier,))
    timeline.extend(dict(event_type='CORRECTED',occurred_at=c['submitted_at'],actor_subject=c['submitted_by'],actor_type='HUMAN',quarantine_id=c['quarantine_id']) for c in corrections[:100])
    operations=api._query('SELECT actor_subject,created_at,action FROM operations_requests WHERE target=%s ORDER BY created_at LIMIT 101',(identifier,))
    timeline.extend(dict(event_type='RETRY_REQUESTED',occurred_at=o['created_at'],actor_subject=o['actor_subject'],actor_type='HUMAN',action=o['action']) for o in operations[:100])
    for o in value['occurrences']:timeline.extend(dict(e,batch_id=o['batch_id'],source_row=o['source_row']) for e in o['timeline'])
    risk=api._query('SELECT risk_event_id,created_at FROM risk_events WHERE tx_id=%s ORDER BY risk_event_id',(identifier,))
    timeline.extend(dict(event_type='RISK_EVENT',occurred_at=e['created_at'],actor_subject='scoring-worker',actor_type='SYSTEM',risk_event_id=e['risk_event_id']) for e in risk)
    timeline.extend(dict(event_type=h['after_status'],occurred_at=h['changed_at'],actor_subject=h['actor_subject'],actor_type='SYSTEM' if h['actor_subject']=='scoring-worker' and h['before_status'] is None else 'HUMAN',version=h['version']) for h in history)
    # Never call an unsent or uncertain delivery ALERTED. Existing SQL receipts and cloud claim are distinct evidence sources.
    from .dynamo import get_item
    import os
    claim=get_item(os.environ.get('DYNAMODB_TABLE','risk_scores'),{'account_id':str(value['account_id']),'score_date':'ALERT#'+identifier}) or {}
    receipts=api._query('SELECT delivery_state,sent_at FROM alerts a JOIN risk_events r USING(risk_event_id) WHERE r.tx_id=%s',(identifier,))
    value['alert_state']=claim.get('delivery_state') or ('SENT' if any(x['delivery_state']=='SENT' for x in receipts) else 'PENDING' if value['risk_state']=='High' else 'NOT_REQUIRED')
    for receipt in receipts:
        if receipt['delivery_state']=='SENT' and receipt['sent_at']:timeline.append(dict(event_type='ALERTED',occurred_at=receipt['sent_at'],actor_subject='alert-worker',actor_type='SYSTEM',evidence_source='SQL_RECEIPT'))
    if claim.get('delivery_state')=='SENT' and claim.get('updated_at'):timeline.append(dict(event_type='ALERTED',occurred_at=claim['updated_at'],actor_subject='alert-worker',actor_type='SYSTEM',evidence_source='DYNAMODB_CLAIM'))
    from datetime import datetime
    value['timeline']=sorted(timeline,key=lambda e:datetime.fromisoformat(e['occurred_at'].replace('Z','+00:00')) if isinstance(e['occurred_at'],str) else e['occurred_at'])
    value['timeline_complete']=bool(value['occurrences']) and not occurrences_truncated and not history_truncated and len(corrections)<=100 and len(operations)<=100 and all(o['timeline_complete'] for o in value['occurrences'])
    return value
