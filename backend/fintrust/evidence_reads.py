"""Version-pinned evidence reads. Missing evidence never fabricates original values."""
import json,os
from botocore.exceptions import ClientError,BotoCoreError

def read(key,version):
    from . import score
    try:
        response=score.s3.get_object(Bucket=os.environ['QUARANTINE_BUCKET'],Key=key,VersionId=version)
        body=response['Body']
        try:payload=body.read(262145)
        finally:body.close()
        if len(payload)>262144:raise ValueError('Evidence exceeds supported bound')
        data=json.loads(payload)
        if not isinstance(data,dict):raise ValueError('Evidence must be an object')
        return data,'AVAILABLE'
    except ClientError as error:
        code=error.response.get('Error',{}).get('Code')
        return None,'MISSING' if code in {'NoSuchKey','NoSuchVersion','404'} else 'UNAVAILABLE'
    except BotoCoreError:return None,'UNAVAILABLE'
