from pathlib import Path
from fintrust import api
from fintrust.release_ingest import REQUIRED
from fintrust.quarantine import FIELDS
from tests.test_release1_end_to_end import authenticated_client


def test_default_entry_is_current_authenticated_workspace():
    client=api.app.test_client()
    for path in ('/', '/index.html', '/release1'):
        response=client.get(path)
        assert response.status_code==200
        assert response.data==client.get('/release1').data
        assert b'earlier learning interface' not in response.data
        assert b'id="login"' in response.data and b'id="workspace" hidden' in response.data
        assert b'Validate and Process' in response.data


def test_csv_contract_matches_validator_and_is_analyst_scoped(authenticated_client):
    client,headers=authenticated_client
    data=client.get('/v1/upload-contract',headers=headers('Risk/Compliance Analyst')).json['data']
    assert set(data['required'])==REQUIRED
    assert set(data['identity_one_of'])=={'source_transaction_id','source_reference'}
    assert set(data['optional'])==FIELDS-REQUIRED-set(data['identity_one_of'])
    assert (data['max_files'],data['max_file_bytes'],data['max_rows'])==(1,1048576,5000)
    assert client.get('/v1/upload-contract',headers=headers('Read-only/Auditor')).status_code==403


def test_csv_contract_requires_real_session(monkeypatch):
    monkeypatch.delenv('FINTRUST_AUTH_FILE',raising=False)
    assert api.app.test_client().get('/v1/upload-contract').status_code==401


def test_legacy_entry_redirects_even_for_already_running_servers():
    entry = (Path(__file__).resolve().parents[1] / 'frontend' / 'index.html').read_text(encoding='utf-8')
    assert '<meta http-equiv="refresh" content="0; url=/release1">' in entry
    assert '<a href="/release1">Continue to sign in</a>' in entry
    assert '/assets/app.js' not in entry
    assert 'Demo workspace' not in entry
