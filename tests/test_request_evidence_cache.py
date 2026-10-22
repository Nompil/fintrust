from flask import Flask
from fintrust.request_cache import request_cached, invalidate


def test_evidence_cache_is_request_scoped_and_defensive():
    calls=[]
    @request_cached
    def read(subject):
        calls.append(subject)
        return {'actor':subject,'items':[1]}
    app=Flask('cache-test')
    with app.test_request_context('/'):
        first=read('a');first['items'].append(9)
        assert read('a')['items']==[1]
        assert read('b')['actor']=='b'
        assert calls==['a','b']
        invalidate();read('a')
        assert calls==['a','b','a']
    with app.test_request_context('/'):
        read('a')
        assert calls==['a','b','a','a']


def test_no_cross_request_or_background_cache():
    calls=[]
    @request_cached
    def read():calls.append(1);return len(calls)
    assert read()==1 and read()==2


def test_unknown_owner_lookup_does_not_scan_known_account_receipts(monkeypatch):
    from types import SimpleNamespace
    from fintrust import upload_ownership, workflow_api
    calls=[]
    monkeypatch.setattr(upload_ownership,'available',lambda:True)
    monkeypatch.setattr(workflow_api,'_query',lambda sql: [{'batch_id':'unknown-a'},{'batch_id':'unknown-b'}])
    monkeypatch.setattr(upload_ownership,'owns',lambda batch,principal: calls.append(batch) or batch=='unknown-a')
    monkeypatch.setattr(upload_ownership,'owned_batches',lambda principal: (_ for _ in ()).throw(AssertionError('Whole owner scan forbidden')))
    principal=SimpleNamespace(role='Risk/Compliance Analyst')
    assert upload_ownership.owned_unknown_batches(principal)==['unknown-a']
    assert calls==['unknown-a','unknown-b']
