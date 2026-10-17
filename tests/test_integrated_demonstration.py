from infrastructure.service_preparation.prepare_integrated_demonstration import render

def test_integrated_defaults_and_scopes_remain_disabled_and_bounded():
    data=render();resources=data['Resources']
    for name in ('EnableFunctions','EnableConsumers','EnableMonthlyReports','EnableManualTest'):
        assert data['Parameters'][name]['Default']=='false'
    assert resources['ScoringMapping']['Properties']['BatchSize']==1
    assert resources['ScoringMapping']['Properties']['ScalingConfig']=={'MaximumConcurrency':2}
    assert resources['OutboxSchedule']['Properties']['State']=={'Fn::If':['ConsumersEnabled','ENABLED','DISABLED']}
    assert resources['OutboxSchedule']['Properties']['Targets'][0]['RetryPolicy']['MaximumRetryAttempts']==2
    assert resources['MonthlySchedule']['Properties']['State']=={'Fn::If':['ReportsEnabled','ENABLED','DISABLED']}
    assert not any(v['Type'].startswith(('AWS::IAM::','AWS::RDS::','AWS::EC2::')) for v in resources.values())
    for name in ('ScoringFunction','AlertFunction','ReportFunction','ApiFunction'):
        assert resources[name]['Properties']['ReservedConcurrentExecutions']=={'Fn::If':[name+'Available',{'Ref':'AWS::NoValue'},0]}
    permission=resources['OutboxInvoke']['Properties']
    assert permission['Principal']=='events.amazonaws.com' and permission['SourceArn'].endswith(':rule/fintrust-outbox-dev')
    assert permission['SourceAccount']=={'Ref':'AWS::AccountId'}
