"""Local release evidence runner: loopback test DB only, sanitized output, no AWS."""
import os
import sys
import subprocess
import uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    from tools.local import local_settings,TEST_DATABASE,ROLE
    from psycopg2.extensions import make_dsn
    environment=os.environ.copy()
    environment["PYTHONPATH"]=os.pathsep.join([str(ROOT/"backend"),str(ROOT)])
    if environment.get("FINTRUST_TEST_DATABASE_URL"):
        from psycopg2.extensions import parse_dsn
        dsn=environment["FINTRUST_TEST_DATABASE_URL"];target=parse_dsn(dsn)
        if target.get("host") not in {"localhost","127.0.0.1","::1"} or target.get("dbname") not in {"fintrust_test","fintrust_local_test"}:raise ValueError("Dedicated loopback test database required")
        credential=target.get("password","")
    else:
        values=local_settings()
        dsn=make_dsn(host=values["DB_HOST"],port=values.get("DB_PORT","5432"),dbname=TEST_DATABASE,user=ROLE,password=values["DB_PASSWORD"],connect_timeout=5)
        credential=values["DB_PASSWORD"]
    environment.update(FINTRUST_TEST_DATABASE_URL=dsn,AWS_ACCESS_KEY_ID="testing",AWS_SECRET_ACCESS_KEY="testing",AWS_SESSION_TOKEN="testing",AWS_DEFAULT_REGION="af-south-1",AWS_EC2_METADATA_DISABLED="true")
    run=ROOT/"build/release1-closure"/uuid.uuid4().hex;run.mkdir(parents=True)
    selection=sys.argv[1:]
    result=subprocess.run([sys.executable,"-m","pytest","-q","--tb=short",*selection,"--basetemp",str(run/"tmp"),"-o","cache_dir="+str(run/"cache"),"--junitxml="+str(run/"results.xml")],cwd=ROOT,env=environment,capture_output=True,text=True)
    secrets=[x for x in (credential,dsn) if x]
    def sanitized(text):
        for secret in secrets:text=text.replace(secret,"[REDACTED_LOCAL_TEST_CREDENTIAL]")
        return text
    text=sanitized(result.stdout+result.stderr)
    (run/"test-output.txt").write_text(text,encoding="utf-8")
    report=run/"results.xml"
    if report.exists():report.write_text(sanitized(report.read_text(encoding="utf-8")),encoding="utf-8")
    print(text[-14000:]);print("Evidence:",run)
    return result.returncode

if __name__=="__main__":raise SystemExit(main())
