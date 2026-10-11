"""Actual supplied CSV byte preservation and fail-closed admission, not acceptance."""
import io,hashlib
from pathlib import Path
from unittest.mock import Mock
import pytest
from fintrust.file_admission import admit,AdmissionError
from werkzeug.datastructures import FileStorage
from tests.test_release1_end_to_end import release_db,authenticated_client
from tools.audit_release1_fixtures import inspect,NAMES
ROOT=Path(__file__).resolve().parents[1]
HASHES={NAMES[0]:('1b2a3a1fa424b7c4e320b2fc9d0f13154945d0dc370a0aaa5a0e44f0573ff8df',33,2328),NAMES[1]:('7d981dd595b0ba56dbedbe683fd991ad5cec41f49fc68b7d5e7e1a8b96da60b6',11,868)}
@pytest.mark.parametrize('name',NAMES)
def test_original_bytes_and_precise_contract_mismatch(name):
    data=(ROOT/'tests/fixtures/e2e'/name).read_bytes();digest,count,size=HASHES[name]
    assert hashlib.sha256(data).hexdigest()==digest and len(data)==size
    audit=inspect(name);assert audit['row_count']==count and audit['parser_reason']=='MISSING_HEADERS'
    assert audit['missing_required_headers']==['source_system','tx_date','tx_type']
    assert audit['unsupported_headers']==['transaction_timestamp','transaction_type']
    assert audit['missing_source_reference_alternative']
    with pytest.raises(AdmissionError) as error:admit(FileStorage(stream=io.BytesIO(data),filename=name,content_type='text/csv'))
    assert error.value.code=='INVALID_CSV_SCHEMA'

def test_actual_a_then_b_then_a_rejected_before_sql_or_storage(release_db,authenticated_client,monkeypatch):
    _,_,_,query,_=release_db;client,headers=authenticated_client
    monkeypatch.setenv('FINTRUST_RELEASE1_UPLOAD','1');monkeypatch.setenv('FINTRUST_MODE','local')
    from fintrust import operations
    worker=Mock(side_effect=AssertionError('Incompatible originals must never enter row worker'));monkeypatch.setattr(operations,'upload_csv',worker)
    for name in [NAMES[0],NAMES[1],NAMES[0]]:
        payload=(ROOT/'tests/fixtures/e2e'/name).read_bytes()
        response=client.post('/v1/upload',data={'file':(io.BytesIO(payload),name,'text/csv')},headers=headers('Risk/Compliance Analyst'))
        assert response.status_code==400 and response.json['reason_code']=='INVALID_CSV_SCHEMA'
    worker.assert_not_called()
    assert query('SELECT count(*) FROM transactions')==[(200,)]
    assert query('SELECT count(*) FROM ingestion_batches')==[(0,)]
    assert query('SELECT count(*) FROM quarantine_cases')==[(0,)]
