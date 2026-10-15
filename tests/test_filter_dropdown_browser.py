import os
import subprocess
import threading
from pathlib import Path
from werkzeug.serving import make_server
from fintrust import api
from tests.test_multi_user_operations import people, assignment
from tests.test_release1_end_to_end import release_db, run, feed
from tests.test_release1_workflows import row


def test_filter_dropdowns_in_browser(release_db,people):
    client,headers,_=people
    run(feed([row(source_transaction_id='BROWSER-COUNTRY-ZA',country='ZA',amount='210001'),
              row(source_transaction_id='BROWSER-COUNTRY-US',country='US',amount='210002')]))
    event=release_db[3]("SELECT r.risk_event_id FROM risk_events r JOIN transactions t USING(tx_id) WHERE source_transaction_id='BROWSER-COUNTRY-ZA'")[0][0]
    assert assignment(client,headers,event,'admin01','analyst02').status_code==200
    root=Path(__file__).resolve().parents[1]
    out=root/'build/dropdown-browser';out.mkdir(parents=True,exist_ok=True)
    server=make_server('127.0.0.1',0,api.app,threaded=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        result=subprocess.run([os.environ['FINTRUST_NODE'],str(root/'tools/verify_filter_dropdowns.cjs'),
                               f'http://127.0.0.1:{server.server_port}',str(out)],capture_output=True,text=True,timeout=120)
        assert result.returncode==0,result.stderr
    finally:
        server.shutdown();thread.join(timeout=10);server.server_close()
