"""Append-only occurrence audit, not a replacement for ledger/review state.
Stages follow actual worker order: candidates are queued before DB validation.
No payloads, passwords or exception messages are stored in this audit.
"""

def append(cur, item, event, *, error_type=None):
    batch, row = item['batch']['batch_id'], item['source']['row']
    cur.execute('SELECT disposition FROM ingestion_records WHERE batch_id=%s AND source_row=%s FOR UPDATE', (batch,row))
    if not cur.fetchone(): raise ValueError('Unknown occurrence')
    if event not in {'TECHNICAL_FAILURE','RETRY','RECOVERED'}:
        cur.execute('SELECT 1 FROM transaction_lifecycle_events WHERE batch_id=%s AND source_row=%s AND event_type=%s', (batch,row,event))
        if cur.fetchone(): return
    cur.execute("""INSERT INTO transaction_lifecycle_events(batch_id,source_row,sequence,event_type,actor_subject,error_type)
        SELECT %s,%s,COALESCE(max(sequence),0)+1,%s,'scoring-worker',%s
        FROM transaction_lifecycle_events WHERE batch_id=%s AND source_row=%s""", (batch,row,event,error_type,batch,row))

def resume(cur,item):
    cur.execute('SELECT event_type FROM transaction_lifecycle_events WHERE batch_id=%s AND source_row=%s ORDER BY sequence DESC LIMIT 1', (item['batch']['batch_id'],item['source']['row']))
    row=cur.fetchone()
    if row and row[0]=='DLQ': raise ValueError('DLQ occurrence requires controlled redrive approval')
    if row and row[0]=='TECHNICAL_FAILURE': append(cur,item,'RETRY')

def recovered(cur,item):
    cur.execute("""SELECT COALESCE(max(sequence) FILTER (WHERE event_type='TECHNICAL_FAILURE'),0),
        COALESCE(max(sequence) FILTER (WHERE event_type='RECOVERED'),0)
        FROM transaction_lifecycle_events WHERE batch_id=%s AND source_row=%s""",
        (item['batch']['batch_id'],item['source']['row']))
    failure_sequence,recovery_sequence=cur.fetchone()
    # One successful recovery covers all prior failed attempts, not just one count.
    if failure_sequence>recovery_sequence: append(cur,item,'RECOVERED')
