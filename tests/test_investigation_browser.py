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
        assert release_db[3]("SELECT count(*) FROM transactions WHERE source_transaction_id='BAD-UI'")[0][0]==0
    finally:stop.set();correction_thread.join(timeout=10);server.shutdown();t.join(timeout=10);server.server_close()


@pytest.mark.skipif(not os.getenv('FINTRUST_NODE'),reason='Explicit installed Node/Playwright gate')
def test_missing_original_evidence_browser(release_db,people,monkeypatch):
    from fintrust import score
    run(feed([row(amount='bad')]))
    key,version=release_db[3]('SELECT safe_payload_key,safe_payload_version FROM quarantine_cases')[0]
    score.s3.delete_object(Bucket='release1-safe',Key=key,VersionId=version)
    monkeypatch.setattr(db,'get_connection',release_db[2])
    root=Path(__file__).resolve().parents[1];out=Path(os.getenv('FINTRUST_UI_COPY_EVIDENCE',str(root/'docs/EVIDENCE/12-e2e/workflow-continuity')))/'missing-evidence';out.mkdir(parents=True,exist_ok=True)
    server=make_server('127.0.0.1',0,api.app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        result=subprocess.run([os.environ['FINTRUST_NODE'],str(root/'tools/verify_missing_evidence_ui.cjs'),f'http://127.0.0.1:{server.server_port}',str(out)],capture_output=True,text=True,timeout=90)
        assert result.returncode==0,result.stderr
    finally:server.shutdown();thread.join(timeout=10);server.server_close()

@pytest.mark.skipif(not os.getenv('FINTRUST_NODE'),reason='Explicit installed Node/Playwright gate')
def test_owned_unknown_account_browser(release_db,people,monkeypatch):
    import io
    from tests.test_release1_end_to_end import file_bytes
    c,h,_=people;monkeypatch.setenv('FINTRUST_RELEASE1_UPLOAD','1');monkeypatch.setenv('INPUT_BUCKET','synthetic-input')
    s3=release_db[4];s3.create_bucket(Bucket='synthetic-input',CreateBucketConfiguration={'LocationConstraint':'af-south-1'})
    s3.put_bucket_versioning(Bucket='synthetic-input',VersioningConfiguration={'Status':'Enabled'})
    response=c.post('/v1/upload',headers=h('analyst01'),data={'file':(io.BytesIO(file_bytes([row(account_id='f0000000-0000-4000-8000-000000000001')])),'unknown.csv')})
    assert response.status_code==200,response.json
    monkeypatch.setattr(db,'get_connection',release_db[2])
    root=Path(__file__).resolve().parents[1];out=Path(os.getenv('FINTRUST_UI_COPY_EVIDENCE',str(root/'docs/EVIDENCE/12-e2e/workflow-continuity')))/'owned-unknown';out.mkdir(parents=True,exist_ok=True)
    server=make_server('127.0.0.1',0,api.app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    stop=threading.Event();errors=[]
    def drain():
        while not stop.wait(.2):
            try:worker.drain_corrections(limit=1)
            except Exception as error:errors.append(type(error).__name__);return
    worker_thread=threading.Thread(target=drain,daemon=True);worker_thread.start()
    try:
        result=subprocess.run([os.environ['FINTRUST_NODE'],str(root/'tools/verify_owned_quarantine_ui.cjs'),f'http://127.0.0.1:{server.server_port}',str(out)],capture_output=True,text=True,timeout=120)
        assert result.returncode==0,result.stderr
        assert not errors,errors
        assert release_db[3]("SELECT count(*) FROM transactions WHERE source_transaction_id='REF-001'")==[(0,)]
    finally:stop.set();worker_thread.join(timeout=10);server.shutdown();thread.join(timeout=10);server.server_close()
