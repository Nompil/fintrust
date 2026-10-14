"""Scoped investigation evidence. Frozen scoring results are never recomputed."""
import os
from datetime import timedelta
from psycopg2.extras import RealDictCursor
from . import workflow_api as api

def detail(event,principal):
    principal.require('read')
    rows=api._query('''SELECT r.*,t.*,p.result AS risk,p.processed_at,
        w.review_status,w.reviewer_subject,w.created_at AS review_created_at,w.version,w.reviewed_by,w.reviewed_at,w.review_notes,w.resolution_code,
        EXISTS(SELECT 1 FROM ingestion_records i WHERE i.canonical_tx_id=t.tx_id) AS has_occurrence
        FROM risk_events r JOIN transactions t USING(tx_id)
        LEFT JOIN processed_transactions p USING(tx_id) LEFT JOIN risk_reviews w USING(risk_event_id)
        WHERE r.risk_event_id=%s AND t.account_id=ANY(%s::uuid[])''',(event,list(principal.accounts)))
    if not rows:raise api.NotFound()
    value=rows[0]
    # Explicitly obtain event timestamp: t.* must not shadow r.created_at.
    stamp=api._query('SELECT created_at FROM risk_events WHERE risk_event_id=%s',(event,))[0]['created_at']
    value['created_at']=stamp
    from .analyst_workflow import decorate
    decorate([value])
    risk=value.get('risk') or {}
    value['risk_level']=risk.get('risk_level','NOT_ASSESSED')
    value['signals']=[dict(signal,created_at=value['processed_at']) for signal in risk.get('triggered_rules',[])]
    value['signal_evidence_note']='Historical results lacking measured values retain their original explanation; they are not rescored.'
    when=value['tx_date'];start=when-timedelta(days=30)
    # Baseline is strictly preceding event time and same currency, never cross-currency averaging.
    context=api._query('''SELECT count(*) AS transaction_count,avg(amount) AS average_amount,
        count(*) FILTER(WHERE country<>'ZA') AS international_count
        FROM transactions WHERE account_id=%s AND currency=%s AND tx_date>=%s AND tx_date<%s AND tx_id<>%s''',
        (value['account_id'],value['currency'],start,when,value['tx_id']))[0]
    context.update(window_start=start,window_end=when,currency=value['currency'],basis='Current ledger, preceding 30 event-time days; not the original scoring-time snapshot')
    related=api._query('''SELECT t.tx_id,t.amount,t.currency,t.tx_date,t.merchant,t.country,t.raw_file,
        t.batch_id,t.source_system,t.source_transaction_id,t.transaction_fingerprint,r.risk_event_id,r.risk_score,
        p.result AS risk,p.result->>'risk_level' AS risk_level,w.review_status,w.reviewer_subject,
        EXISTS(SELECT 1 FROM ingestion_records i WHERE i.canonical_tx_id=t.tx_id) AS has_occurrence
        FROM transactions t LEFT JOIN risk_events r USING(tx_id) LEFT JOIN processed_transactions p USING(tx_id)
        LEFT JOIN risk_reviews w USING(risk_event_id)
        WHERE t.account_id=%s AND t.tx_date>=%s AND t.tx_date<=%s AND t.tx_id<>%s
        ORDER BY t.tx_date DESC,t.tx_id LIMIT 21''',(value['account_id'],start,when,value['tx_id']))
    totals=api._query("""SELECT count(*) FILTER(WHERE p.result->>'risk_level' IN ('Medium','High')) AS prior_risk_events,
        count(*) FILTER(WHERE w.review_status IN ('OPEN','UNDER_REVIEW','ESCALATED')) AS prior_active_reviews
        FROM risk_events r JOIN transactions t USING(tx_id) LEFT JOIN processed_transactions p USING(tx_id)
        LEFT JOIN risk_reviews w USING(risk_event_id) WHERE t.account_id=%s AND t.tx_date>=%s AND t.tx_date<%s""",
        (value['account_id'],start,when))[0]
    context.update(totals)
    from .analyst_workflow import assessment
    for row in related:assessment(row)
    value['account_context']=context;value['related_transactions']=related[:20];value['related_truncated']=len(related)>20
    from .lifecycle_api import transaction
    lifecycle=transaction(str(value['tx_id']),principal)
    value['timeline']=lifecycle['timeline'];value['timeline_complete']=lifecycle['timeline_complete']
    value['review_history']=lifecycle['review_history']
    for key in ('referral_target','referral_target_label','referral_kind','referral_requested_by','referral_requested_at','referral_note','referral_active','referral_assignment_note','source_provenance','source_journey','submitted_by','submitted_at','submission_channel','original_filename'):
        value[key]=lifecycle.get(key)
    from .review_referral import decode
    latest=value['review_history'][-1] if value['review_history'] else None
    if latest and latest.get('raw_notes'):value.update(raw_review_notes=value.get('review_notes'),review_notes=latest['notes'])
    from .analyst_workflow import review
    review(value,history=value['review_history'])
    # Read the independent cloud delivery claim, not review state or an assumed send.
    from .dynamo import get_item
    from botocore.exceptions import ClientError,BotoCoreError
    try:claim=get_item(os.environ.get('DYNAMODB_TABLE','risk_scores'),{'account_id':str(value['account_id']),'score_date':'ALERT#'+str(value['tx_id'])}) or {}
    except (ClientError,BotoCoreError):claim={};lifecycle['alert_state']='UNAVAILABLE'
    value['alert']={'required':value['risk_level']=='High','delivery_state':lifecycle['alert_state'],
        'updated_at':claim.get('updated_at'),'reconciliation_required':lifecycle['alert_state'] in {'UNKNOWN','SENDING'},
        'source':'UNAVAILABLE' if lifecycle['alert_state']=='UNAVAILABLE' else 'DYNAMODB_CLAIM' if claim else 'SQL_RECEIPT_OR_PENDING_INTENT'}
    owner=value.get('reviewer_subject')==principal.subject
    value['allowed_actions']={'claim':principal.role=='Risk/Compliance Analyst' and value.get('review_status')=='OPEN' and not value.get('reviewer_subject'),
        'assign':principal.role=='Admin' and value.get('review_status') in {'OPEN','UNDER_REVIEW','ESCALATED'},
        'resume':principal.role=='Risk/Compliance Analyst' and owner and value.get('review_status')=='ESCALATED',
        'note':principal.role=='Risk/Compliance Analyst' and owner and value.get('review_status')=='UNDER_REVIEW',
        'decide':principal.role=='Risk/Compliance Analyst' and owner and value.get('review_status')=='UNDER_REVIEW'}
    value['updated_at']=value['review_history'][-1]['changed_at'] if value['review_history'] else stamp
    return value

def add_note(event,body,principal):
    principal.require('review')
    request,digest=api._body(body,{'request_id','expected_version','notes'})
    if type(body['expected_version']) is not int or body['expected_version']<1:raise ValueError('Expected version required')
    from .identity_registry import locked_registry,read_registry
    with locked_registry(os.environ['FINTRUST_AUTH_FILE']):
        current=[u for u in read_registry()['principals'] if u['subject']==principal.subject]
        if len(current)!=1 or current[0]['role']!=principal.role or current[0].get('status','ACTIVE')!='ACTIVE':raise PermissionError('Identity changed')
        conn=api.connection()
        try:
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute('''SELECT w.*,t.account_id FROM risk_reviews w JOIN risk_events r USING(risk_event_id)
                        JOIN transactions t USING(tx_id) WHERE w.risk_event_id=%s FOR UPDATE OF w''',(event,))
                    row=cur.fetchone()
                    if not row:raise api.NotFound()
                    principal.account(row['account_id'])
                    cur.execute('SELECT * FROM risk_review_history WHERE request_id=%s',(request,));prior=cur.fetchone()
                    if prior:
                        if prior['risk_event_id']!=event or prior['actor_subject']!=principal.subject or prior['request_digest']!=digest:raise api.Conflict('Request identifier reused')
                        return {'risk_event_id':event,'version':prior['version'],'replayed':True}
                    if row['reviewer_subject']!=principal.subject:raise PermissionError('Only assigned Analyst may add notes')
                    if row['review_status']!='UNDER_REVIEW' or row['version']!=body['expected_version']:raise api.Conflict('Review changed; refresh before retry')
                    cur.execute('''UPDATE risk_reviews SET review_notes=%s,change_actor=%s,change_request_id=%s,
                        request_digest=%s,version=version+1 WHERE risk_event_id=%s RETURNING version''',(body['notes'],principal.subject,request,digest,event))
                    return {'risk_event_id':event,'version':cur.fetchone()['version'],'review_status':'UNDER_REVIEW'}
        finally:conn.close()
