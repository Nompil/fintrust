import pytest
from fintrust import score,release_workflow

RULE='arn:aws:events:af-south-1:966467878406:rule/fintrust-outbox-dev'
EVENT={'source':'aws.events','detail-type':'Scheduled Event','resources':[RULE],'account':'966467878406','region':'af-south-1'}

def test_only_fixed_schedule_drains_bounded_authorized_work(monkeypatch):
    monkeypatch.setenv('FINTRUST_OUTBOX_RULE_ARN',RULE);calls=[]
    monkeypatch.setattr(release_workflow,'drain_corrections',lambda **kw:(calls.append(('correction',kw)) or {'completed':1}))
    monkeypatch.setattr(release_workflow,'drain_projections',lambda **kw:(calls.append(('projection',kw)) or {'completed':0}))
    result=score.lambda_handler(EVENT,None)
    assert calls==[('correction',{'limit':5}),('projection',{'limit':5})] and result['corrections']['completed']==1

@pytest.mark.parametrize('change',[{'resources':[]},{'resources':[RULE+'-other']},{'account':'000000000000'},{'region':'us-east-1'},{'detail-type':'arbitrary'}])
def test_unrecognized_tick_does_not_run_database_work(monkeypatch,change):
    monkeypatch.setenv('FINTRUST_OUTBOX_RULE_ARN',RULE)
    monkeypatch.setattr(release_workflow,'drain_corrections',lambda **kw:pytest.fail('Unauthorized tick'))
    with pytest.raises(ValueError):score.lambda_handler({**EVENT,**change},None)
