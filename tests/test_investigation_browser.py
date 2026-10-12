"""Real loopback UI/API/SQL investigation verification; AWS mocked."""
import os,subprocess,threading
from pathlib import Path
import pytest
from werkzeug.serving import make_server
from fintrust import api,db,release_workflow as worker
from tests.test_multi_user_operations import people
from tests.test_release1_end_to_end import release_db,feed,run
from tests.test_release1_workflows import row
@pytest.mark.skipif(not os.getenv('FINTRUST_NODE'),reason='Explicit installed Node/Playwright gate')
def test_investigation_browser(release_db,people,monkeypatch):
    run(feed([row(amount='200000.01',country='US'),row(source_transaction_id='BAD-UI',amount='bad')]))
    monkeypatch.setattr(db,'get_connection',release_db[2])
    root=Path(__file__).resolve().parents[1];out=root/'docs/EVIDENCE/12-e2e/risk-investigation/browser';out=Path(os.environ['FINTRUST_UI_COPY_EVIDENCE'])/'investigation' if os.getenv('FINTRUST_UI_COPY_EVIDENCE') else out;out.mkdir(parents=True,exist_ok=True)
    server=make_server('127.0.0.1',0,api.app,threaded=True);t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
    stop=threading.Event();worker_errors=[]
    def drain():
        while not stop.wait(.2):
            try:worker.drain_corrections(limit=1)
            except Exception as error:worker_errors.append(type(error).__name__);return
    correction_thread=threading.Thread(target=drain,daemon=True);correction_thread.start()
    try:
        result=subprocess.run([os.environ['FINTRUST_NODE'],str(root/'tools/verify_investigation_ui.cjs'),f'http://127.0.0.1:{server.server_port}',str(out)],capture_output=True,text=True,timeout=180)
        assert result.returncode==0,result.stderr
        assert not worker_errors,worker_errors
        assert release_db[3]("SELECT count(*) FROM transactions WHERE source_transaction_id='BAD-UI'")[0][0]==1
    finally:stop.set();correction_thread.join(timeout=10);server.shutdown();t.join(timeout=10);server.server_close()
