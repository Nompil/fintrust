from infrastructure.service_preparation.prepare_integrated_demonstration import render
from infrastructure.service_preparation import prepare_integrated_demonstration as preparation
import shutil

def test_integrated_defaults_and_scopes_remain_disabled_and_bounded(tmp_path,monkeypatch):
    shutil.copytree(preparation.ROOT/'shared_manual',tmp_path/'shared_manual')
    monkeypatch.setattr(preparation,'ROOT',tmp_path)
    data=render();resources=data['Resources']
    for name in ('EnableFunctions','EnableConsumers','EnableMonthlyReports','EnableManualTest'):
        assert data['Parameters'][name]['Default']=='false'
    assert resources['ScoringMapping']['Properties']['BatchSize']==1
    # AWS refuses maximum concurrency 2 while a function is reserved at zero,
    # even if its mapping is disabled. Supply this limit only at activation.
    assert resources['ScoringMapping']['Properties']['ScalingConfig']=={'Fn::If':['ConsumersEnabled',{'MaximumConcurrency':2},{'Ref':'AWS::NoValue'}]}
    assert resources['OutboxSchedule']['Properties']['State']=={'Fn::If':['ConsumersEnabled','ENABLED','DISABLED']}
    assert resources['OutboxSchedule']['Properties']['Targets'][0]['RetryPolicy']['MaximumRetryAttempts']==2
    assert resources['MonthlySchedule']['Properties']['State']=={'Fn::If':['ReportsEnabled','ENABLED','DISABLED']}
    assert not any(v['Type'].startswith(('AWS::IAM::','AWS::RDS::','AWS::EC2::')) for v in resources.values())
    for name in ('ScoringFunction','AlertFunction','ReportFunction','ApiFunction'):
        assert resources[name]['Properties']['ReservedConcurrentExecutions']=={'Fn::If':[name+'Available',{'Ref':'AWS::NoValue'},0]}
    permission=resources['OutboxInvoke']['Properties']
    assert permission['Principal']=='events.amazonaws.com' and permission['SourceArn'].endswith(':rule/fintrust-outbox-dev')
    assert permission['SourceAccount']=={'Ref':'AWS::AccountId'}
