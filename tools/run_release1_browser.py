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
    target=ROOT/"build/release1-browser-check.py";target.parent.mkdir(exist_ok=True)
    target.write_text('''import os,subprocess,threading
from pathlib import Path
from werkzeug.serving import make_server
from tests.conftest import prohibit_unmocked_aws_transport
from tests.test_release1_end_to_end import release_db,authenticated_client,feed,run,row
from fintrust import api

def test_browser_release1(release_db,authenticated_client):
    run(feed([row(amount="200000.01",country="US"),row(source_transaction_id="INVALID",amount="bad")]))
    root=Path(__file__).resolve().parents[1]
    evidence=root/"docs/EVIDENCE/12-e2e/release1-closure/browser"
    evidence.mkdir(parents=True,exist_ok=True)
    server=make_server("127.0.0.1",0,api.app,threaded=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        result=subprocess.run([os.environ["FINTRUST_NODE"],str(root/"tools/verify_release1_ui.cjs"),f"http://127.0.0.1:{server.server_port}",str(evidence)],capture_output=True,text=True,timeout=100)
        assert result.returncode==0,result.stderr
    finally:
        server.shutdown();thread.join(timeout=10);server.server_close()
''',encoding="utf-8")
    from tools.run_release1_tests import main as tests
    sys.argv=[sys.argv[0],str(target)]
    return tests()

if __name__=="__main__":raise SystemExit(main())
