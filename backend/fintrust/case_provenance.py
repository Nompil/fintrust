"""Read recorded submission lineage without guessing an automated channel."""
import os
from .request_cache import request_cached


@request_cached
def source(batch,principal,receipts=None):
    from . import workflow_api as api
    if not batch:return {'submission_channel':'NOT_RECORDED','submitted_by':None,'submitted_at':None,
        'original_filename':None,'submission_note':'No processing-run submission provenance is recorded.'}
    batch=str(batch)
    rows=api._query('''SELECT b.batch_id,b.source_system AS pipeline_source_system,b.received_at,
        a.source_bucket,a.source_file,a.source_version,a.source_etag,b.file_sha256
        FROM ingestion_batches b LEFT JOIN LATERAL (SELECT * FROM ingestion_attempts i
          WHERE i.batch_id=b.batch_id ORDER BY received_at,attempt_id LIMIT 1) a ON TRUE
        WHERE b.batch_id=%s''',(batch,))
    if not rows:return {'submission_channel':'NOT_RECORDED','submitted_by':None,'submitted_at':None,'original_filename':None}
    evidence=dict(rows[0]);evidence.update(submission_channel='NOT_RECORDED',submitted_by=None,submitted_at=None,
        submitted_actor_role='Not recorded',original_filename=None,
        submission_note='A source object is recorded. The ingestion channel and submitting actor are not inferred from the scoring worker.')
    from .upload_ownership import owner
    admission=owner(batch)
    if admission:
        stored=admission.get('source') or {}
        evidence.update(submission_channel='MANUAL_UPLOAD',submitted_by=admission['actor'],submitted_at=admission['admitted_at'],
            original_filename=stored.get('filename'),submitted_actor_role=stored.get('actor_role','Not recorded'),
            source_bucket=stored.get('bucket',evidence.get('source_bucket')),source_file=stored.get('key',evidence.get('source_file')),
            source_version=stored.get('version',evidence.get('source_version')),file_sha256=stored.get('sha256',evidence.get('file_sha256')),
            submission_note='First authenticated local admission; later replay attempts do not replace the original uploader or source version.')
    else:
        corrections=api._query('SELECT quarantine_id,submitted_by,submitted_at FROM quarantine_corrections WHERE reprocess_batch_id=%s ORDER BY submitted_at LIMIT 1',(batch,))
        if corrections:
            correction=corrections[0]
            evidence.update(submission_channel='MANUAL_CORRECTION',submitted_by=correction['submitted_by'],submitted_at=correction['submitted_at'],
                original_quarantine_id=correction['quarantine_id'],submission_note='Recorded manual correction created this processing run; the original quarantine evidence is retained.')
    # Old upload messages do not contain the original S3 version. Present their
    # filename as receipt evidence, never as a verified original admission name.
    if receipts is None and os.getenv('FINTRUST_MODE')=='local' and principal.role!='Maintainer':
        from .frontend_workflows import upload_history
        receipts=upload_history(principal)
    matches=[r for r in receipts or [] if r.get('batch_id')==batch and r.get('action')=='UPLOAD_ACCEPTED'
             and (not admission or r.get('actor')==admission['actor'])]
    if matches:
        receipt=min(matches,key=lambda r:r['attempted_at'])
        evidence['recorded_upload_filename']=receipt.get('filename')
        evidence['upload_receipt_recorded_at']=receipt['attempted_at']
        if admission and evidence['submitted_actor_role']=='Not recorded':evidence['submitted_actor_role']=receipt.get('actor_role','Not recorded')
    return evidence


def enrich(rows,principal,kind):
    receipts=[]
    if os.getenv('FINTRUST_MODE')=='local' and principal.role!='Maintainer':
        from .frontend_workflows import upload_history
        receipts=upload_history(principal)
    cache={}
    for row in rows:
        batch=row.get('batch_id') or ((row.get('risk') or {}).get('batch') or {}).get('batch_id')
        key=str(batch) if batch else None
        if key not in cache:cache[key]=source(batch,principal,receipts)
        evidence=cache[key]
        row['source_provenance']=evidence
        for field in ('submitted_by','submitted_at','submitted_actor_role','submission_channel','original_filename'):
            row[field]=evidence.get(field)
        if kind in {'quarantine','batches'}:
            row['filename']=evidence.get('original_filename') or evidence.get('recorded_upload_filename') or row.get('source_filename')
            row['actor']=evidence.get('submitted_by')
        row['source_system_note']='Declared source system from the export; not proof of a verified banking connection.'
    return rows


def journey(transaction):
    events=transaction.get('timeline') or []
    names={'RECEIVED':'Received','VALIDATED':'Validated','REVALIDATED':'Revalidated','SCORED':'Assessed','STORED':'Stored',
           'RISK_EVENT':'Risk event recorded','OPEN':'Review opened','UNDER_REVIEW':'Investigation started',
           'INVESTIGATION_NOTE':'Investigation note','CLEARED':'Cleared','CONFIRMED_RISK':'Confirmed risk','ESCALATED':'Specialist review requested',
           'CORRECTED':'Data corrected','RETRY_REQUESTED':'Recovery requested','ALERTED':'Alert delivery recorded',
           'ASSIGNED':'Ownership changed','UNASSIGNED':'Returned to unassigned work','QUEUED':'Queued for processing','PROCESSING':'Processing started','ACCEPTED':'Accepted','DUPLICATE':'Duplicate identified'}
    stages=[];source=transaction.get('source_provenance') or {}
    if source.get('submitted_at') and source.get('submitted_by'):
        stages.append({'stage':'Submitted','occurred_at':source['submitted_at'],'actor_subject':source['submitted_by'],
                       'actor_type':'HUMAN','actor_role':source.get('submitted_actor_role','Not recorded'),'evidence_source':'IMMUTABLE_ADMISSION_OR_CORRECTION'})
    for event in events:
        if event.get('event_type') in names:stages.append({**event,'stage':names[event['event_type']]})
    return {'stages':stages,'complete':transaction.get('timeline_complete',False),
            'report_availability':{'state':'AVAILABLE_FOR_REPORTS' if transaction.get('current_state')=='STORED' else 'NOT_APPLICABLE',
             'note':'Accepted ledger entries can be included in reports. No report-generation event is inferred.'}}
