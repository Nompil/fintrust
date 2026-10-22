"""Seed pre-policy history directly in disposable SQL; never reopen the removed API."""
import json
import uuid
from psycopg2.extras import Json
from tests.test_release1_end_to_end import feed,run


def historical_correction(release_db,case,candidate,actor='analyst01'):
    query,s3=release_db[3:5]
    correction=str(uuid.uuid4())
    key='quarantine/corrections/'+correction+'.json'
    version=s3.put_object(Bucket='release1-safe',Key=key,Body=json.dumps({'correction_id':correction,'candidate':candidate}).encode())['VersionId']
    items=feed([candidate],'raw/historical-fixture-'+correction+'.csv');run(items)
    batch=items[0]['batch']['batch_id']
    query('''INSERT INTO quarantine_corrections(correction_id,quarantine_id,request_id,request_digest,submitted_by,
        submitted_at,correction_notes,corrected_payload_key,corrected_payload_version,action,reprocess_batch_id,reprocess_source_row)
        VALUES(%s,%s,%s,%s,%s,NOW(),'Pre-policy historical fixture',%s,%s,'RESUBMIT',%s,2)''',
        (correction,case,str(uuid.uuid4()),'a'*64,actor,key,version,batch))
    query("INSERT INTO correction_outbox(correction_id,envelope,state,completed_at) VALUES(%s,%s,'COMPLETED',NOW())",(correction,Json({'row':candidate})))
    return {'key':key,'version':version,'batch_id':batch,'correction_id':correction}
