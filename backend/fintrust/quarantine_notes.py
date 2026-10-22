"""Append-only source-review annotations; never a transaction correction."""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from . import score, workflow_api

PREFIX='quarantine/ui-events/source-review/'


def key_prefix(identifier):
    return PREFIX+str(uuid.UUID(identifier))+'/'


def read_notes(identifier,principal,*,authorized_case=None):
    identifier=str(uuid.UUID(identifier))
    if authorized_case is None:
        authorized_case=workflow_api.quarantine_detail(identifier,principal)
    if str(authorized_case['quarantine_id'])!=identifier:
        raise PermissionError('Quarantine scope changed')
    bucket=os.environ['QUARANTINE_BUCKET']
    listing=score.s3.list_objects_v2(Bucket=bucket,Prefix=key_prefix(identifier),MaxKeys=100)
    notes=[]
    for entry in listing.get('Contents',[]):
        response=score.s3.get_object(Bucket=bucket,Key=entry['Key'])
        body=response['Body']
        try:data=json.loads(body.read(16385))
        finally:body.close()
        if data.get('quarantine_id')!=identifier or data.get('action')!='SOURCE_REVIEW_NOTE':
            raise ValueError('Invalid source-review evidence')
        notes.append({k:data[k] for k in ('request_id','notes','actor','created_at')})
    return {'data':sorted(notes,key=lambda row:row['created_at']), 'has_more':bool(listing.get('IsTruncated')), 'limit':100}


def add_note(identifier,body,principal):
    principal.require('reject_quarantine')
    if not isinstance(body,dict) or set(body)!={'request_id','notes'}:
        raise ValueError('Only request ID and source-review notes are accepted')
    request_id=str(uuid.UUID(body['request_id']))
    if not isinstance(body['notes'],str) or not 3<=len(body['notes'].strip())<=2000:
        raise ValueError('Source-review notes must contain 3 to 2000 characters')
    identifier=str(uuid.UUID(identifier))
    # Reuse the authoritative account/original-upload permission check.
    workflow_api.quarantine_detail(identifier,principal)
    notes=body['notes'].strip()
    digest=hashlib.sha256(json.dumps([identifier,principal.subject,notes]).encode()).hexdigest()
    data={'request_id':request_id,'quarantine_id':identifier,'action':'SOURCE_REVIEW_NOTE',
          'actor':principal.subject,'actor_role':principal.role,'notes':notes,'digest':digest,
          'created_at':datetime.now(timezone.utc).isoformat()}
    key=key_prefix(identifier)+request_id+'.json'
    try:
        result=score.s3.put_object(Bucket=os.environ['QUARANTINE_BUCKET'],Key=key,Body=json.dumps(data).encode(),
            ContentType='application/json',IfNoneMatch='*')
        if not result.get('VersionId'):
            raise RuntimeError('Versioned review evidence is required')
    except ClientError as error:
        if error.response['Error']['Code']!='PreconditionFailed':raise
        existing=score.s3.get_object(Bucket=os.environ['QUARANTINE_BUCKET'],Key=key)['Body']
        try:prior=json.loads(existing.read(16385))
        finally:existing.close()
        if prior.get('digest')!=digest:
            raise workflow_api.Conflict('Note request ID reused with changed content')
        return {'request_id':request_id,'status':'REPLAYED'}
    return {'request_id':request_id,'status':'RECORDED'}
