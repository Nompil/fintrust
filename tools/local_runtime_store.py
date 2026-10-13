"""Durable backing for local-only mocked services. Never used by Lambda runtime.
Exact object version IDs and typed DynamoDB items survive server restarts.
The ignored SQLite store contains synthetic local data, never credentials.
"""
import io,json,hashlib,sqlite3,threading,time
from datetime import datetime,timezone
from pathlib import Path
from contextlib import contextmanager
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeSerializer,TypeDeserializer

class LocalStore:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock()
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS objects(bucket TEXT,key TEXT,version TEXT,body BLOB,content_type TEXT,etag TEXT,digest TEXT,created_ns INTEGER,PRIMARY KEY(bucket,key,version))')
            c.execute('CREATE TABLE IF NOT EXISTS items(table_name TEXT,item_key TEXT,item TEXT,PRIMARY KEY(table_name,item_key))')
    @contextmanager
    def connect(self):
        connection=sqlite3.connect(self.path,timeout=15)
        try:
            with connection:yield connection
        finally:connection.close()

class DurableS3:
    def __init__(self,client,store):self.client=client;self.store=store
    def __getattr__(self,name):return getattr(self.client,name)
    def put_object(self,**args):
        body=args['Body'];body=body.encode() if isinstance(body,str) else body.read() if hasattr(body,'read') else bytes(body)
        with self.store.lock:
            with self.store.connect() as c:
                if args.get('IfNoneMatch')=='*' and c.execute('SELECT 1 FROM objects WHERE bucket=? AND key=?',(args['Bucket'],args['Key'])).fetchone():
                    raise ClientError({'Error':{'Code':'PreconditionFailed'},'ResponseMetadata':{'HTTPStatusCode':412}},'PutObject')
            response=self.client.put_object(**{**args,'Body':body})
            version=response.get('VersionId')
            if not version:raise RuntimeError('Local evidence bucket must be versioned')
            with self.store.connect() as c:
                c.execute('INSERT INTO objects VALUES(?,?,?,?,?,?,?,?)',(args['Bucket'],args['Key'],version,body,args.get('ContentType','application/octet-stream'),response.get('ETag',''),hashlib.sha256(body).hexdigest(),time.time_ns()))
            return response
    def get_object(self,**args):
        query='SELECT version,body,content_type,etag,digest FROM objects WHERE bucket=? AND key=?';params=[args['Bucket'],args['Key']]
        if args.get('VersionId'):query+=' AND version=?';params.append(args['VersionId'])
        query+=' ORDER BY created_ns DESC LIMIT 1'
        with self.store.connect() as c:row=c.execute(query,params).fetchone()
        if not row:return self.client.get_object(**args)
        version,body,content_type,etag,digest=row
        if hashlib.sha256(body).hexdigest()!=digest:raise RuntimeError('Local evidence integrity check failed')
        return {'Body':io.BytesIO(body),'VersionId':version,'ContentType':content_type,'ContentLength':len(body),'ETag':etag,'ResponseMetadata':{'HTTPStatusCode':200}}
    def list_objects_v2(self,**args):
        # Same latest-key listing after restart; pagination is deterministic by key.
        prefix=args.get('Prefix','');after=args.get('ContinuationToken','');limit=args.get('MaxKeys',1000)
        with self.store.connect() as c:
            rows=c.execute('SELECT key,max(created_ns) FROM objects WHERE bucket=? GROUP BY key ORDER BY key',(args['Bucket'],)).fetchall()
        rows=[r for r in rows if r[0].startswith(prefix) and r[0]>after];page=rows[:limit]
        result={'Contents':[{'Key':k,'LastModified':datetime.fromtimestamp(ns/1e9,timezone.utc)} for k,ns in page],'IsTruncated':len(rows)>limit,'KeyCount':len(page)}
        if result['IsTruncated']:result['NextContinuationToken']=page[-1][0]
        return result

class DurableDynamo:
    def __init__(self,resource,store):
        self.resource=resource;self.store=store
        with store.connect() as c:rows=c.execute('SELECT table_name,item FROM items').fetchall()
        decode=TypeDeserializer()
        for table,payload in rows:resource.Table(table).put_item(Item={k:decode.deserialize(v) for k,v in json.loads(payload).items()})
    def __getattr__(self,name):return getattr(self.resource,name)
    def Table(self,name):return DurableTable(self.resource.Table(name),name,self.store)

class DurableTable:
    def __init__(self,table,name,store):self.table=table;self.name=name;self.store=store
    def __getattr__(self,name):return getattr(self.table,name)
    def save(self,key):
        item=self.table.get_item(Key=key,ConsistentRead=True).get('Item');identifier=json.dumps(key,sort_keys=True)
        with self.store.connect() as c:
            if item:c.execute('INSERT OR REPLACE INTO items VALUES(?,?,?)',(self.name,identifier,json.dumps({k:TypeSerializer().serialize(v) for k,v in item.items()})))
            else:c.execute('DELETE FROM items WHERE table_name=? AND item_key=?',(self.name,identifier))
    def put_item(self,**args):
        with self.store.lock:
            result=self.table.put_item(**args);self.save({k:args['Item'][k] for k in ('account_id','score_date')});return result
    def update_item(self,**args):
        with self.store.lock:
            result=self.table.update_item(**args);self.save(args['Key']);return result
    def delete_item(self,**args):
        with self.store.lock:
            result=self.table.delete_item(**args);self.save(args['Key']);return result
