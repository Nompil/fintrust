"""Run the optional explicit local browser gate with existing Node/Playwright/Chrome.
No installation, AWS access, live DB or application artifact rebuild.
"""
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    node=os.environ.get("FINTRUST_NODE")
    package=os.environ.get("FINTRUST_PLAYWRIGHT_MODULE")
    if not node or not Path(node).is_file() or not package:
        raise SystemExit("Set FINTRUST_NODE and FINTRUST_PLAYWRIGHT_MODULE to existing installations")
    if not os.getenv("FINTRUST_RELEASE_COMMIT"):
        import subprocess
        os.environ["FINTRUST_RELEASE_COMMIT"]=os.getenv("GITHUB_SHA") or subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    target=ROOT/"build/release1-browser-check.py";target.parent.mkdir(exist_ok=True)
    target.write_text('''import os,subprocess,threading
from pathlib import Path
from werkzeug.serving import make_server
from tests.conftest import prohibit_unmocked_aws_transport
from tests.test_release1_end_to_end import release_db,authenticated_client,feed,run,row
from tests.test_release1_candidate import maintainer_headers
from tests.test_release1_dataset_lifecycle import dataset_db
from fintrust import api

def test_browser_release1(dataset_db,authenticated_client,maintainer_headers,monkeypatch):
    release_db=dataset_db
    from fintrust import db
    monkeypatch.setattr(db,"get_connection",release_db[2])
    monkeypatch.setenv("FINTRUST_RELEASE1_UPLOAD","1");monkeypatch.setenv("FINTRUST_MODE","local");monkeypatch.setenv("INPUT_BUCKET","browser-input")
    s3=release_db[4];s3.create_bucket(Bucket="browser-input",CreateBucketConfiguration={"LocationConstraint":"af-south-1"});s3.put_bucket_versioning(Bucket="browser-input",VersioningConfiguration={"Status":"Enabled"})
    monkeypatch.setenv("FINTRUST_DATASET_FIXTURES",str(Path(__file__).resolve().parents[1]/"tests/fixtures/e2e/release1"))
    import json
    registry_path=Path(os.environ["FINTRUST_AUTH_FILE"])
    registry=json.loads(registry_path.read_text())
    names={"Admin":"admin01","Risk/Compliance Analyst":"analyst01","Read-only/Auditor":"auditor01","Maintainer":"maintainer01"}
    for entry in registry["principals"]:
        entry["subject"]=names[entry["role"]]
        entry["display_name"]=entry["subject"]
    registry_path.write_text(json.dumps(registry))
    root=Path(__file__).resolve().parents[1]
    evidence=Path(os.environ.get("FINTRUST_BROWSER_EVIDENCE",str(root/"docs/EVIDENCE/12-e2e/release1-lifecycle/browser")))
    evidence.mkdir(parents=True,exist_ok=True)
    server=make_server("127.0.0.1",0,api.app,threaded=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        result=subprocess.run([os.environ["FINTRUST_NODE"],str(root/"tools/verify_release1_ui.cjs"),f"http://127.0.0.1:{server.server_port}",str(evidence)],capture_output=True,text=True,timeout=180)
        assert result.returncode==0,result.stderr
    finally:
        server.shutdown();thread.join(timeout=10);server.server_close()
''',encoding="utf-8")
    from tools.run_release1_tests import main as tests
    sys.argv=[sys.argv[0],str(target)]
    return tests()

if __name__=="__main__":raise SystemExit(main())
