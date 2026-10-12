"""Workbench evidence against real scoped SQL reads; external network blocked."""
import os, subprocess, threading
from pathlib import Path
import pytest
from werkzeug.serving import make_server
from fintrust import api, db
from tests.test_multi_user_operations import people
from tests.test_release1_end_to_end import release_db, feed, run
from tests.test_release1_workflows import row
@pytest.mark.skipif(not os.getenv('FINTRUST_NODE'), reason='Explicit installed Node/Playwright gate')
def test_workbench_browser(release_db, people, monkeypatch):
    run(feed([row(amount='200000.01',country='US'),row(source_transaction_id='BAD-WB',amount='bad')]))
    monkeypatch.setattr(db,'get_connection',release_db[2])
    monkeypatch.delenv('FINTRUST_REVIEW_SLA_SECONDS', raising=False)
    root=Path(__file__).resolve().parents[1]
    out=root/'docs/EVIDENCE/12-e2e/analyst-workbench/browser';out.mkdir(parents=True,exist_ok=True)
    server=make_server('127.0.0.1',0,api.app,threaded=True)
    t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
    try:
        result=subprocess.run([os.environ['FINTRUST_NODE'],str(root/'tools/verify_workbench_ui.cjs'),f'http://127.0.0.1:{server.server_port}',str(out)],capture_output=True,text=True,timeout=180)
        assert result.returncode==0,result.stderr
    finally:
        server.shutdown();t.join(timeout=10);server.server_close()
