"""Verify the exact runner ZIP under Linux CPython 3.12 x86_64; no AWS."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import zipfile
try:from .package_migration import inspect
except ImportError:from package_migration import inspect

def verify(path):
    path=Path(path).resolve();mp=path.with_suffix(".manifest.json");m=json.loads(mp.read_text())
    m["linux_execution_verified"]=False;m.pop("linux_verification",None)
    mp.write_text(json.dumps(m,indent=2)+"\n")
    if platform.system()!="Linux" or platform.machine()!="x86_64" or sys.version_info[:2]!=(3,12) or platform.python_implementation()!="CPython":
        raise RuntimeError("Linux CPython 3.12 x86_64 execution environment unavailable")
    evidence=inspect(path,m["phase"])
    if any(m.get(k)!=v for k,v in evidence.items()):raise ValueError("Artifact manifest mismatch")
    env={k:v for k,v in os.environ.items() if not k.startswith(("AWS_","DB_","FINTRUST_","PYTHON"))}
    env.update(AWS_ACCESS_KEY_ID="dummy",AWS_SECRET_ACCESS_KEY="dummy",AWS_SESSION_TOKEN="dummy",AWS_DEFAULT_REGION="af-south-1",AWS_EC2_METADATA_DISABLED="true",AWS_CONFIG_FILE="/dev/null",AWS_SHARED_CREDENTIALS_FILE="/dev/null")
    with tempfile.TemporaryDirectory(prefix="migration-import-") as temp:
        with zipfile.ZipFile(path) as z:z.extractall(temp)
        result=subprocess.run([sys.executable,"-I",str(Path(__file__).with_name("migration_import_probe.py")),temp,m["phase"]],cwd=temp,env=env,capture_output=True,text=True,timeout=60)
        if result.returncode:raise RuntimeError("Isolated runner ZIP import failed; no credentials were supplied")
        probe=json.loads(result.stdout)
    if evidence!=inspect(path,m["phase"]):raise ValueError("Artifact changed during verification")
    m["linux_execution_verified"]=True
    m["linux_verification"]={**probe,"python":platform.python_version(),"platform":platform.platform(),"machine":platform.machine()}
    mp.write_text(json.dumps(m,indent=2)+"\n")
    return m
if __name__=="__main__":print(json.dumps(verify(sys.argv[1]),indent=2))
