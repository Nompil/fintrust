"""Isolated extracted-ZIP imports. Dummy credentials; all network blocked."""
import importlib
import json
from pathlib import Path
import socket
import sys
root=Path(sys.argv[1]).resolve();phase=sys.argv[2]
sys.path.insert(0,str(root))
def blocked(*args,**kwargs):raise RuntimeError("Network forbidden during ZIP imports")
socket.socket.connect=blocked;socket.socket.connect_ex=blocked;socket.create_connection=blocked;socket.getaddrinfo=blocked
import boto3
import psycopg2
import psycopg2._psycopg
from botocore.httpsession import URLLib3Session
URLLib3Session.send=blocked
for name in ("boto3","psycopg2","psycopg2._psycopg"):
    assert Path(sys.modules[name].__file__).resolve().is_relative_to(root)
modules=[]
for p in sorted((root/"migration_runner").glob("*.py")):
    if p.name=="__init__.py":continue
    name="migration_runner."+p.stem
    module=importlib.import_module(name)
    assert Path(module.__file__).resolve().is_relative_to(root)
    modules.append(name)
handler=importlib.import_module("migration_runner."+phase+"_entry").lambda_handler
assert callable(handler)
import ssl
ssl.create_default_context(cafile=str(root/"certs/global-bundle.pem"))
from migration_runner.common import client
token=client("rds").generate_db_auth_token(DBHostname="db.invalid",Port=5432,DBUsername="dummy",Region="af-south-1")
assert "X-Amz-Signature=" in token
print(json.dumps({"modules":modules,"handler_imported":True,"native_loaded":True,"psycopg2":psycopg2.__version__,"libpq":psycopg2.extensions.libpq_version(),"network_requests":0,"ca_loaded":True}))
