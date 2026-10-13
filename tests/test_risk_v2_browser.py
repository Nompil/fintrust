"""Measurable V2 evidence and legacy display in a real scoped Analyst browser."""
import json,os,subprocess,threading
from pathlib import Path
import pytest
from psycopg2.extras import Json
from werkzeug.serving import make_server
from fintrust import api
from tests.test_release1_end_to_end import release_db,feed,run
from tests.test_multi_user_operations import people
from tests.test_release1_workflows import row

@pytest.mark.skipif(not os.getenv('FINTRUST_NODE'),reason='Explicit installed Node/Playwright gate')
def test_v2_component_investigation_browser(release_db,people):
    rows=[row(source_transaction_id=f'V2-V{i}',amount=str(10+i),merchant=f'M{i}',tx_date=f'2026-10-09T09:{55+i:02d}:00Z') for i in range(5)]
    rows.extend([row(source_transaction_id='V2-V5',amount='20',merchant='M5',tx_date='2026-10-09T09:59:30Z'),row(source_transaction_id='V2-V6',amount='21',merchant='M6',tx_date='2026-10-09T09:59:40Z'),row(source_transaction_id='V2-DEMO',amount='150000',country='US',merchant='Demo',tx_date='2026-10-09T10:00:00Z')])
    rows.extend([row(source_transaction_id='V2-ZERO',amount='10',tx_date='2026-10-09T08:00:00Z'),row(source_transaction_id='V2-OLD',amount='200000.01',country='US',tx_date='2026-10-09T08:10:00Z'),row(source_transaction_id='V2-DUP-A',amount='50',merchant='Same shop',tx_date='2026-10-09T08:20:00Z'),row(source_transaction_id='V2-DUP-B',amount='50',merchant='Same shop',tx_date='2026-10-09T08:20:30Z')])
    run(feed(rows));q=release_db[3]
    tx,old=q("SELECT t.tx_id::text,p.result FROM transactions t JOIN processed_transactions p USING(tx_id) WHERE source_transaction_id='V2-OLD'")[0]
    legacy={**old,'score':70,'risk_level':'High','rule_version':'fintrust-r1-rules-2026-10-09','triggered_rules':[{'rule':'HIGH_AMOUNT','points':30,'reason':'Amount exceeds 50000'},{'rule':'VERY_HIGH_AMOUNT','points':25,'reason':'Amount exceeds 200000'},{'rule':'CROSS_BORDER','points':15,'reason':'Country differs from ZA'}]}
    legacy.pop('components');legacy.pop('evaluated_at')
    q('UPDATE processed_transactions SET result=%s WHERE tx_id=%s',(Json(legacy),tx));q('UPDATE risk_events SET risk_score=70 WHERE tx_id=%s',(tx,))
    data={r[0]:{'tx':r[1],'event':r[2]} for r in q("SELECT source_transaction_id,t.tx_id::text,r.risk_event_id FROM transactions t JOIN risk_events r USING(tx_id) WHERE source_transaction_id IN ('V2-DEMO','V2-ZERO','V2-OLD','V2-DUP-B')")}
    root=Path(__file__).resolve().parents[1];out=Path(os.getenv('FINTRUST_UI_COPY_EVIDENCE',str(root/'build/risk-v2/browser')))/'risk-v2';out.mkdir(parents=True,exist_ok=True)
    server=make_server('127.0.0.1',0,api.app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    env={**os.environ,'FINTRUST_RISK_BROWSER_ROWS':json.dumps(data)}
    try:
        r=subprocess.run([os.environ['FINTRUST_NODE'],str(root/'tools/verify_risk_v2_ui.cjs'),f'http://127.0.0.1:{server.server_port}',str(out)],env=env,capture_output=True,text=True,timeout=180)
        assert r.returncode==0,r.stderr
        assert q('SELECT result FROM processed_transactions WHERE tx_id=%s',(tx,))[0][0]==legacy
    finally:server.shutdown();thread.join(timeout=10);server.server_close()
