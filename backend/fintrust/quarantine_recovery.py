"""Derived recovery detail from immutable evidence and authoritative worker events.
No direct financial writes or competing quarantine status table.
"""
import json,os
from . import workflow_api as api
from .quarantine import FIELDS
def enrich(case,principal):
    history=api._query('''SELECT c.*,r.disposition,r.canonical_tx_id,r.reason_code AS outcome_reason,
        q.reason_detail AS outcome_detail,o.envelope->'row'->>'account_id' AS corrected_account_id
        FROM quarantine_corrections c LEFT JOIN ingestion_records r ON r.batch_id=c.reprocess_batch_id AND r.source_row=c.reprocess_source_row
        LEFT JOIN quarantine_cases q ON q.batch_id=r.batch_id AND q.source_row=r.source_row
        LEFT JOIN correction_outbox o USING(correction_id)
        WHERE c.quarantine_id=%s ORDER BY c.correction_version LIMIT 101''',(case['quarantine_id'],))
    truncated=len(history)>100;history=history[:100]
    timeline=[{'event_type':'QUARANTINE_CREATED','occurred_at':case['quarantined_at'],'actor_subject':'system:scoring-worker','actor_type':'SYSTEM','quarantine_id':case['quarantine_id']}]
    for c in history:
        timeline.append({'event_type':'CORRECTION_SUBMITTED' if c['action']=='RESUBMIT' else 'QUARANTINE_REJECTED','occurred_at':c['submitted_at'],'actor_subject':c['submitted_by'],'actor_type':'HUMAN','correction_id':c['correction_id']})
        c['corrected_values']=None
        if c['action']=='RESUBMIT':
            if c['corrected_account_id'] not in principal.accounts:
                c['details_hidden']=True
                c['canonical_tx_id']=None;c['outcome_detail']=None;c['outcome_reason']=None
                continue
            from .evidence_reads import read
            data,status=read(c['corrected_payload_key'],c['corrected_payload_version'])
            c['evidence_status']=status
            c['corrected_values']={k:v for k,v in (data or {}).get('candidate',{}).items() if k in FIELDS and isinstance(v,str)} if data else None
            events=api._query('SELECT event_type,occurred_at,actor_subject FROM transaction_lifecycle_events WHERE batch_id=%s AND source_row=%s ORDER BY sequence LIMIT 1001',(c['reprocess_batch_id'],c['reprocess_source_row']))
            if len(events)>1000:truncated=True
            for e in events[:1000]:
                name={'VALIDATED':'REVALIDATION_PASSED','QUARANTINED':'REVALIDATION_FAILED','STORED':'QUARANTINE_ACCEPTED','DUPLICATE':'QUARANTINE_DUPLICATE_RESOLVED'}.get(e['event_type'],e['event_type'])
                timeline.append({**e,'event_type':name,'actor_type':'SYSTEM','correction_id':c['correction_id']})
    case['correction_history']=history;latest=history[-1] if history and not truncated else None
    # Latest outcome must not be inferred from a truncated slice.
    case['recovery_status']='PENDING_HISTORY' if truncated else 'OPEN' if latest is None else 'REJECTED' if latest['action']=='REJECT' else 'ACCEPTED' if latest['disposition'] in {'ACCEPTED','DUPLICATE'} else 'REVALIDATION_FAILED' if latest['disposition']=='QUARANTINED' else 'CORRECTED'
    case['corrected_values']=latest['corrected_values'] if latest else None
    case['correcting_analyst']=latest['submitted_by'] if latest else None
    case['correction_timestamp']=latest['submitted_at'] if latest else None
    case['resulting_transaction_id']=latest['canonical_tx_id'] if latest and not latest.get('details_hidden') else None
    case['recovery_outcome']=latest['disposition'] if latest else None
    case['latest_reason_code']=latest['outcome_reason'] if latest and latest['disposition']=='QUARANTINED' else case['reason_code']
    case['latest_reason_detail']=latest['outcome_detail'] if latest and latest['disposition']=='QUARANTINED' else case['reason_detail']
    case['revalidation_attempts']=sum(c['action']=='RESUBMIT' and c['disposition'] in {'ACCEPTED','DUPLICATE','QUARANTINED'} for c in history)
    case['audit_timeline']=sorted(timeline,key=lambda e:e['occurred_at'])
    case['timeline_complete']=case.get('evidence_available',True) and not truncated and not any(c.get('details_hidden') or c.get('evidence_status','AVAILABLE')!='AVAILABLE' for c in history)
    return case
