"""Authenticated asynchronous intake; SQL writes belong to the FIFO worker."""
import hashlib,os,uuid

def enabled():
    return (os.getenv('FINTRUST_CLOUD_INTAKE')=='1' and os.getenv('AUTH_MODE')=='cognito'
            and bool(os.getenv('AWS_EXECUTION_ENV')))

def available():
    return os.getenv('FINTRUST_MODE')=='local' or enabled()

def upload(filename,payload,principal):
    if not enabled() or principal.auth_source!='cognito':raise PermissionError('Cloud intake is unavailable')
    principal.require('upload')
    from . import workflow_api as api,score
    from .release_ingest import parse_file
    from .batches import metadata
    from .upload_ownership import claim,owner
    from .frontend_workflows import record_upload
    identifiers=set()
    rows=parse_file(payload)
    for _,row,_ in rows:
        try:identifiers.add(str(uuid.UUID(row.get('account_id','').strip())))
        except (ValueError,AttributeError):continue
    if identifiers:
        for account in api._query('SELECT account_id::text FROM accounts WHERE account_id=ANY(%s::uuid[])',(list(identifiers),)):
            principal.account(account['account_id'])
    bucket=os.environ['INPUT_BUCKET'];digest=hashlib.sha256(payload).hexdigest()
    batch=metadata(bucket,payload);prior=owner(batch['batch_id'])
    # A later upload may not adopt another analyst's immutable ownership.
    if prior and prior['actor']!=principal.subject:raise PermissionError('File belongs to another uploader')
    key='raw/uploads/'+digest+'.csv'
    response=score.s3.put_object(Bucket=bucket,Key=key,Body=payload,ContentType='text/csv')
    version=response.get('VersionId')
    if not version:raise RuntimeError('Versioned intake storage is required')
    admission=claim(batch['batch_id'],principal,{'bucket':bucket,'key':key,'version':version,
        'sha256':digest,'filename':filename,'actor_role':principal.role,'channel':'MANUAL_UPLOAD'})
    if admission['actor']!=principal.subject:raise PermissionError('File belongs to another uploader')
    record_upload(principal,filename,'UPLOAD_ACCEPTED','QUEUED',batch_id=batch['batch_id'])
    # No synchronous worker call and no claim that rows are already accepted.
    return {'filename':filename,'batch_id':batch['batch_id'],'upload_status':'QUEUED',
        'reconciliation':{'status':'QUEUED','rows_received':len(rows),'pending':len(rows),
                          'accepted':0,'quarantined':0,'duplicate':0,'failed_technical':0,'counts_consistent':True},
        'notification':{'severity':'info','message':'File stored for processing. Processing History will show the recorded row outcomes.'},
        'execution':'Versioned S3 intake, FIFO queue and private scoring worker',
        'submitted_by':admission['actor'],'submitted_at':admission['admitted_at'],
        'original_filename':admission['source']['filename'],'submission_channel':'MANUAL_UPLOAD'}
