"""Authenticated, immutable first-admission ownership for local intake only.
Never inferred from CSV, correction bodies or later replay receipts. Cloud intake
without this trusted admission path and historical unowned batches fail closed.
This extends provenance, not transaction state or account assignments.
"""
import json,os,uuid
from datetime import datetime,timezone
from botocore.exceptions import ClientError
from . import score
from .cloud_intake import available,enabled
PREFIX='quarantine/upload-owners/'
from .request_cache import request_cached
def _key(batch):return PREFIX+str(uuid.UUID(str(batch)))+'.json'
@request_cached
def owner(batch):
    if not available():return None
    if enabled():
        # Prefix-scoped ListBucket makes absence explicit. Never reinterpret an
        # S3 AccessDenied response as an unowned file.
        found=score.s3.list_objects_v2(Bucket=os.environ['QUARANTINE_BUCKET'],Prefix=_key(batch),MaxKeys=1)
        if not any(item['Key']==_key(batch) for item in found.get('Contents',[])):return None
    try:response=score.s3.get_object(Bucket=os.environ['QUARANTINE_BUCKET'],Key=_key(batch))
    except ClientError as error:
        if error.response.get('Error',{}).get('Code') in {'NoSuchKey','NoSuchVersion','404'}:return None
        raise
    body=response['Body']
    try:data=json.loads(body.read(8193))
    finally:body.close()
    authority='AUTHENTICATED_COGNITO_ADMISSION' if enabled() else 'AUTHENTICATED_LOCAL_ADMISSION'
    if data.get('batch_id')!=str(batch) or data.get('authority')!=authority or not isinstance(data.get('actor'),str):raise ValueError('Invalid ownership evidence')
    return data
def claim(batch,principal,source):
    from .request_cache import invalidate
    invalidate()
    principal.require('upload')
    if not available() or enabled() and principal.auth_source!='cognito':raise PermissionError('Trusted authenticated admission required')
    authority='AUTHENTICATED_COGNITO_ADMISSION' if enabled() else 'AUTHENTICATED_LOCAL_ADMISSION'
    data={'batch_id':str(batch),'actor':principal.subject,'admitted_at':datetime.now(timezone.utc).isoformat(),'authority':authority,'source':source}
    try:
        response=score.s3.put_object(Bucket=os.environ['QUARANTINE_BUCKET'],Key=_key(batch),Body=json.dumps(data).encode(),ContentType='application/json',IfNoneMatch='*')
        if not response.get('VersionId'):raise RuntimeError('Versioned ownership evidence required')
    except ClientError as error:
        if error.response.get('Error',{}).get('Code')!='PreconditionFailed':raise
        # Another authenticated first admission won; never replace it.
        return owner(batch)
    return data
def owns(batch,principal):
    if principal.role!='Risk/Compliance Analyst':return False
    data=owner(batch)
    return bool(data and data['actor']==principal.subject)
@request_cached
def owned_batches(principal):
    if principal.role!='Risk/Compliance Analyst' or not available():return []
    result=[];cursor=None;scanned=0
    while True:
        args={'Bucket':os.environ['QUARANTINE_BUCKET'],'Prefix':PREFIX,'MaxKeys':1000}
        if cursor:args['ContinuationToken']=cursor
        page=score.s3.list_objects_v2(**args)
        for item in page.get('Contents',[]):
            batch=str(uuid.UUID(item['Key'][len(PREFIX):-5]))
            if owns(batch,principal):result.append(batch)
        scanned+=len(page.get('Contents',[]))
        if not page.get('IsTruncated'):return result
        if scanned>=5000:raise ValueError('Ownership view exceeds bounded local scope')
        cursor=page['NextContinuationToken']


@request_cached
def owned_unknown_batches(principal):
    """Only unknown-account rows need uploader authority; avoid scanning all receipts."""
    if principal.role!='Risk/Compliance Analyst' or not available():return []
    from . import workflow_api
    candidates=workflow_api._query('''SELECT DISTINCT q.batch_id
        FROM quarantine_cases q WHERE NOT EXISTS
        (SELECT 1 FROM accounts a WHERE a.account_id=q.candidate_account_id)
        ORDER BY q.batch_id LIMIT 5001''')
    if len(candidates)>5000:raise ValueError('Unknown-account ownership index exceeds the bounded view')
    return [str(row['batch_id']) for row in candidates if owns(str(row['batch_id']),principal)]
