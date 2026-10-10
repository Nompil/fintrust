"""Strict Release 1 intake. Fully parse before publishing any financial work."""
import csv
import io
import json
import hashlib
import uuid
from datetime import datetime, timezone
from .batches import metadata, BatchAudit
from .quarantine import FIELDS

MAX_ROW_BYTES = 32768
REQUIRED = {"account_id", "amount", "currency", "country", "tx_date", "tx_type", "source_system"}

class FileRejected(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

def parse_file(payload):
    if len(payload)>1048576: raise FileRejected("FILE_TOO_LARGE")
    try: text=payload.decode("utf-8-sig")
    except UnicodeDecodeError: raise FileRejected("INVALID_ENCODING") from None
    try:
        reader=csv.DictReader(io.StringIO(text, newline=""), strict=True)
        headers=reader.fieldnames or []
        if not headers: raise FileRejected("EMPTY_FILE")
        if len(headers)!=len(set(headers)): raise FileRejected("DUPLICATE_HEADERS")
        if not REQUIRED<=set(headers) or not {"source_transaction_id","source_reference"}&set(headers):
            raise FileRejected("MISSING_HEADERS")
        if set(headers)-FIELDS: raise FileRejected("UNSUPPORTED_HEADERS")
        rows=[]
        for ordinal,row in enumerate(reader,2):
            if len(rows)>=5000: raise FileRejected("TOO_MANY_ROWS")
            malformed=None in row or any(v is None for v in row.values())
            oversized=len(json.dumps(row,ensure_ascii=False).encode())>MAX_ROW_BYTES
            safe={k:str(v or "")[:MAX_ROW_BYTES] for k,v in row.items() if k in FIELDS}
            rows.append((ordinal,safe,"MALFORMED_ROW" if malformed else "ROW_TOO_LARGE" if oversized else None))
        if not rows: raise FileRejected("HEADER_ONLY_FILE")
        return rows
    except csv.Error: raise FileRejected("MALFORMED_CSV") from None

def envelopes(bucket,key,payload,*,version=None,etag=None,batch=None):
    batch=batch or metadata(bucket,payload)
    attempt=str(uuid.uuid5(uuid.NAMESPACE_URL,json.dumps([bucket,key,version,etag,batch["file_sha256"]])))
    base={"schema_version":3,"batch":batch,"attempt_id":attempt,
          "source":{"bucket":bucket,"key":key,"version":version,"etag":etag},"source_system":"release1-feed"}
    try: rows=parse_file(payload)
    except FileRejected as error:
        return [{**base,"kind":"FILE_FAILURE","rows_received":0 if error.code in {"EMPTY_FILE","HEADER_ONLY_FILE"} else None,"error_code":error.code}]
    result=[{**base,"kind":"ROW","rows_received":len(rows),"source":{**base["source"],"row":n},
             "row":row,"parse_error":error} for n,row,error in rows]
    result.append({**base,"kind":"PUBLICATION","rows_received":len(rows)})
    return result

def publish(client,queue_client,queue_url,bucket,key,payload,*,version=None,etag=None):
    import os
    batch=metadata(bucket,payload)
    audit=BatchAudit(client,os.environ["QUARANTINE_BUCKET"],bucket,key,batch,version,etag)
    audit.first_receipt()
    completed=audit.completed()
    if completed:
        audit.record("DUPLICATE_FILE",completed["counts"],"DUPLICATE_FILE")
        attempt=str(uuid.uuid5(uuid.NAMESPACE_URL,json.dumps([bucket,key,version,etag,batch["file_sha256"]])))
        control={"schema_version":3,"kind":"DUPLICATE_FILE","batch":batch,"attempt_id":attempt,
                 "source_system":"release1-feed","rows_received":completed["counts"]["rows_received"],
                 "source":{"bucket":bucket,"key":key,"version":version,"etag":etag}}
        body=json.dumps(control,sort_keys=True)
        queue_client.send_message(QueueUrl=queue_url,MessageBody=body,MessageGroupId=batch["batch_id"],
            MessageDeduplicationId=hashlib.sha256(body.encode()).hexdigest())
        return {"batch_id":batch["batch_id"],"status":"DUPLICATE_FILE","rows_received":completed["counts"]["rows_received"],"rows_queued":0}
    items=envelopes(bucket,key,payload,version=version,etag=etag,batch=batch)
    audit.record("PROCESSING")
    try:
        for start in range(0,len(items),10):
            entries=[]
            for i,item in enumerate(items[start:start+10]):
                body=json.dumps(item,sort_keys=True)
                try: group=str(uuid.UUID(item.get("row",{}).get("account_id","").strip()))
                except (ValueError,AttributeError): group=batch["batch_id"]
                entries.append({"Id":str(i),"MessageBody":body,
                    "MessageGroupId":group,
                    "MessageDeduplicationId":hashlib.sha256(body.encode()).hexdigest()})
            response=queue_client.send_message_batch(QueueUrl=queue_url,Entries=entries)
            if response.get("Failed") or {x["Id"] for x in response.get("Successful",[])}!={x["Id"] for x in entries}:
                raise RuntimeError("Partial FIFO publication; retry the entire immutable input")
        if items[0]["kind"]=="FILE_FAILURE":
            audit.record("FAILED",reason=items[0]["error_code"])
            return {"batch_id":batch["batch_id"],"status":"FAILED","rows_received":None,"reason_code":items[0]["error_code"]}
        counts={"rows_received":len(items)-1,"rows_valid":len(items)-1,"rows_quarantined":0}
        audit.complete(counts)
        return {"batch_id":batch["batch_id"],"status":"QUEUED","rows_received":len(items)-1,"rows_queued":len(items)-1,"accepted":0}
    except Exception:
        audit.record("FAILED",reason="PUBLICATION_FAILURE")
        raise
