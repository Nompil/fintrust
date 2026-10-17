"""Prepare the reviewed shared-capacity demonstration; no AWS calls."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parent

def render():
    original=json.loads((ROOT/'shared_manual/application-functions-shared-manual.json').read_text())
    data=json.loads(json.dumps(original))
    data['Description']='FinTrust controlled dev demonstration using shared regional Lambda capacity; disabled defaults'
    for name in ('EnableFunctions','EnableConsumers','EnableMonthlyReports'):
        data['Parameters'][name]['AllowedValues']=['false','true']
    for name in ('ScoringFunction','AlertFunction','ReportFunction','ApiFunction'):
        cond=name+'Available'
        data['Conditions'][cond]={'Fn::Or':[{'Condition':'FunctionsEnabled'},{'Condition':name+'ManualTestEnabled'}]}
        data['Resources'][name]['Properties']['ReservedConcurrentExecutions']={'Fn::If':[cond,{'Ref':'AWS::NoValue'},0]}
    data['Resources']['ScoringMapping']['Properties'].update(Enabled={'Fn::If':['ConsumersEnabled',True,False]},BatchSize=1,
        ScalingConfig={'Fn::If':['ConsumersEnabled',{'MaximumConcurrency':2},{'Ref':'AWS::NoValue'}]})
    data['Resources']['AlertMapping']['Properties']['Enabled']={'Fn::If':['ConsumersEnabled',True,False]}
    data['Resources']['MonthlySchedule']['Properties']['State']={'Fn::If':['ReportsEnabled','ENABLED','DISABLED']}
    env=data['Resources']['ApiFunction']['Properties']['Environment']['Variables']
    env.update(FINTRUST_CLOUD_INTAKE='1',FINTRUST_RELEASE1_UPLOAD='1',INPUT_BUCKET='fintrust-raw-966467878406-af-south-1-dev',
               QUARANTINE_BUCKET={'Ref':'QuarantineBucket'})
    rule='arn:aws:events:af-south-1:966467878406:rule/fintrust-outbox-dev'
    data['Resources']['ScoringFunction']['Properties']['Environment']['Variables']['FINTRUST_OUTBOX_RULE_ARN']=rule
    data['Resources']['OutboxSchedule']={'Type':'AWS::Events::Rule','Properties':{
        'Name':'fintrust-outbox-dev','ScheduleExpression':'rate(1 minute)',
        'State':{'Fn::If':['ConsumersEnabled','ENABLED','DISABLED']},
        'Targets':[{'Id':'OutboxRecovery','Arn':{'Fn::GetAtt':['ScoringFunction','Arn']},
                    'RetryPolicy':{'MaximumRetryAttempts':2,'MaximumEventAgeInSeconds':3600},
                    'DeadLetterConfig':{'Arn':{'Ref':'ExistingReportFailuresArn'}}}]}}
    data['Resources']['OutboxInvoke']={'Type':'AWS::Lambda::Permission','Properties':{
        'FunctionName':{'Ref':'ScoringFunction'},'Action':'lambda:InvokeFunction','Principal':'events.amazonaws.com',
        'SourceAccount':{'Ref':'AWS::AccountId'},'SourceArn':rule}}
    queues=[r for r in data['Resources'].values() if r['Type']=='AWS::SQS::QueuePolicy']
    assert len(queues)==1
    queues[0]['Properties']['PolicyDocument']['Statement'].append({'Sid':'OutboxScheduleFailure',
        'Effect':'Allow','Principal':{'Service':'events.amazonaws.com'},'Action':'sqs:SendMessage',
        'Resource':{'Ref':'ExistingReportFailuresArn'},'Condition':{'ArnEquals':{'aws:SourceArn':rule},'StringEquals':{'aws:SourceAccount':{'Ref':'AWS::AccountId'}}}})
    out=ROOT/'integrated_demonstration';out.mkdir(exist_ok=True)
    path=out/'application-functions.json';path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8',newline='\n')
    manifest={'status':'OFFLINE_PREPARATION_NOT_DEPLOYED','template_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'source_template_sha256':hashlib.sha256((ROOT/'shared_manual/application-functions-shared-manual.json').read_bytes()).hexdigest(),
        'defaults_disabled':True,'positive_reserved_capacity':False,'regional_shared_limit_last_observed':10,
        'sqs_consumer_max_concurrency':2,'monthly_reports_default_disabled':True,'outbox_rows_per_kind_per_tick':5,
        'raw_notification_managed_here':False,'new_paid_interface_endpoints':False,'support_plan_change':False,
        'activation_requires':['Live database setup and cleanup complete','Final immutable code binding and disabled deploy',
          'Scoped runtime permissions and private endpoint policies read back','Cloud Cognito enrollment and server account scopes',
          'Bounded service tests and delivery evidence','Reviewed shared-capacity activation; raw notification connected last']}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    return data

if __name__=='__main__':render();print('INTEGRATED DEMONSTRATION TEMPLATE PREPARED DISABLED; NOT DEPLOYED')
