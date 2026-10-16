"""Offline service configuration. No AWS client, credentials or deployment path."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'source'))
from infrastructure.application_functions import build_template

EMAIL = 'nompilomabuya@outlook.com'


def ref(name):
    return {'Ref': name}


def flag(description):
    return {'Type': 'String', 'Default': 'false', 'AllowedValues': ['false', 'true'], 'Description': description}


def enabled(name):
    return {'Fn::Equals': [ref(name), 'true']}


def email_parameter():
    return {'Type': 'String', 'Default': EMAIL, 'AllowedPattern': r'[^\s@*?]+@[^\s@*?]+\.[^\s@*?]+', 'MaxLength': 254}


def ses_template():
    return {
        'AWSTemplateFormatVersion': '2010-09-09',
        'Description': 'FinTrust SES email identity proposal; no sending or paid add-ons',
        'Parameters': {'SesSender': email_parameter(), 'SesRecipient': email_parameter(),
                       'CreateSenderIdentity': flag('Set true only after confirming the sender identity does not exist.'),
                       'CreateRecipientIdentity': flag('For a distinct sandbox recipient only; inspect existing identities first.')},
        'Conditions': {'CreateSender': enabled('CreateSenderIdentity'),
                       'CreateRecipient': {'Fn::And': [enabled('CreateRecipientIdentity'),
                           {'Fn::Not': [{'Fn::Equals': [ref('SesSender'), ref('SesRecipient')]}]}]}},
        'Resources': {name: {'Type': 'AWS::SES::EmailIdentity', 'Condition': condition,
                             'DeletionPolicy': 'Retain', 'UpdateReplacePolicy': 'Retain',
                             'Properties': {'EmailIdentity': ref(parameter)}}
                      for name, condition, parameter in [('SenderIdentity', 'CreateSender', 'SesSender'),
                                                          ('RecipientIdentity', 'CreateRecipient', 'SesRecipient')]},
        'Outputs': {'SesSender': {'Value': ref('SesSender')}, 'SesRecipient': {'Value': ref('SesRecipient')}}}


def application_template():
    template = build_template()
    template['Parameters']['SesSender'] = email_parameter()
    template['Parameters']['SesRecipient'] = email_parameter()
    template['Parameters']['EnableMonthlyReports'] = flag('Independent report schedule activation after report validation and cost review.')
    template['Conditions']['ReportsEnabled'] = {'Fn::And': [
        {'Condition': 'FunctionsEnabled'}, enabled('EnableMonthlyReports')]}
    template['Resources']['MonthlySchedule']['Properties']['State'] = {
        'Fn::If': ['ReportsEnabled', 'ENABLED', 'DISABLED']}
    for resource in template['Resources'].values():
        if resource['Type'] in {'AWS::Lambda::Function', 'AWS::Lambda::EventSourceMapping', 'AWS::Logs::LogGroup'}:
            resource['Properties']['Tags'] = [
                {'Key': 'Project', 'Value': 'FinTrust'},
                {'Key': 'Environment', 'Value': ref('Stage')}]
        if resource['Type'] == 'AWS::Logs::LogGroup':
            resource['DeletionPolicy'] = 'Retain'
            resource['UpdateReplacePolicy'] = 'Retain'
    return template


def api_template():
    template = json.loads((ROOT / 'source/infrastructure/api/gateway.json').read_text(encoding='utf-8'))
    # Keep the access-log destination stable for deployment and operator checks.
    template['Resources']['AccessLogs']['Properties']['LogGroupName'] = {
        'Fn::Sub': '/aws/apigateway/fintrust-${StageName}'}
    for name in ['Api', 'AccessLogs']:
        template['Resources'][name]['Properties']['Tags'] = [
            {'Key': 'Project', 'Value': 'FinTrust'},
            {'Key': 'Environment', 'Value': ref('StageName')}]
    # Detailed method metrics are optional billable CloudWatch metrics.
    for settings in template['Resources']['Stage']['Properties']['MethodSettings']:
        settings['MetricsEnabled'] = False
    return template


def monitoring_template():
    params = {'Stage': {'Type': 'String', 'Default': 'dev', 'AllowedValues': ['dev', 'staging', 'prod']},
              'EnableAlarms': flag('Creating alarms may incur charges. Keep false until billing allowance is verified.'),
              'DbInstanceIdentifier': {'Type': 'String', 'MinLength': 1}}
    for key in ['TransactionsQueueName', 'TransactionDlqName', 'IngestFailuresName', 'AlertFailuresName', 'ReportFailuresName']:
        params[key] = {'Type': 'String', 'MinLength': 1, 'Description': 'Actual existing queue name from verified messaging inventory.'}
    resources = {}

    def alarm(name, namespace, metric, dimensions, threshold, statistic='Sum'):
        resources[name] = {'Type': 'AWS::CloudWatch::Alarm', 'Condition': 'AlarmsEnabled', 'Properties': {
            'AlarmName': {'Fn::Sub': 'fintrust-' + name.lower() + '-${Stage}'},
            'AlarmDescription': 'FinTrust operator-visible alarm; no automatic remediation or notifications.',
            'Namespace': namespace, 'MetricName': metric, 'Dimensions': dimensions,
            'Statistic': statistic, 'Period': 300, 'EvaluationPeriods': 2, 'DatapointsToAlarm': 2,
            'Threshold': threshold, 'ComparisonOperator': 'GreaterThanThreshold',
            'TreatMissingData': 'notBreaching', 'ActionsEnabled': False}}

    for service in ['ingest', 'scoring', 'alert', 'api', 'report']:
        dimensions = [{'Name': 'FunctionName', 'Value': {'Fn::Sub': 'fintrust-' + service + '-${Stage}'}}]
        for metric in ['Errors', 'Throttles']:
            alarm(service.title() + metric, 'AWS/Lambda', metric, dimensions, 0)
    for key in ['TransactionDlqName', 'IngestFailuresName', 'AlertFailuresName', 'ReportFailuresName']:
        alarm(key + 'Visible', 'AWS/SQS', 'ApproximateNumberOfMessagesVisible',
              [{'Name': 'QueueName', 'Value': ref(key)}], 0, 'Maximum')
    alarm('TransactionsAge', 'AWS/SQS', 'ApproximateAgeOfOldestMessage',
          [{'Name': 'QueueName', 'Value': ref('TransactionsQueueName')}], 900, 'Maximum')
    alarm('AlertStreamLag', 'AWS/Lambda', 'IteratorAge',
          [{'Name': 'FunctionName', 'Value': {'Fn::Sub': 'fintrust-alert-${Stage}'}}], 60000, 'Maximum')
    db_dimensions = [{'Name': 'DBInstanceIdentifier', 'Value': ref('DbInstanceIdentifier')}]
    alarm('DatabaseCpu', 'AWS/RDS', 'CPUUtilization', db_dimensions, 80, 'Average')
    alarm('DatabaseStorage', 'AWS/RDS', 'FreeStorageSpace', db_dimensions, 1073741824, 'Minimum')
    resources['DatabaseStorage']['Properties']['ComparisonOperator'] = 'LessThanThreshold'
    return {'AWSTemplateFormatVersion': '2010-09-09',
            'Description': 'FinTrust optional standard-metric alarms; no logs, custom metrics, SNS or dashboards created',
            'Parameters': params, 'Conditions': {'AlarmsEnabled': enabled('EnableAlarms')}, 'Resources': resources}


def alert_send_policy():
    return {'Version': '2012-10-17', 'Statement': [{'Effect': 'Allow', 'Action': ['ses:SendEmail'],
        'Resource': f'arn:aws:ses:af-south-1:966467878406:identity/{EMAIL}',
        'Condition': {'StringEquals': {'aws:RequestedRegion': 'af-south-1', 'ses:FromAddress': EMAIL},
                      'ForAllValues:StringEquals': {'ses:Recipients': [EMAIL]}}}]}


def cognito_template():
    template = json.loads((ROOT / 'source/infrastructure/auth/cognito.json').read_text(encoding='utf-8'))
    # The admin installs the exact-table GetItem grant separately. The deployer
    # must not acquire PutRolePolicy merely to create sign-in resources.
    template['Resources'].pop('ApiReadUserScopes')
    template['Parameters'].pop('ApiExecutionRoleArn')
    template['Resources']['ImbokodoUserPool']['Properties']['UserPoolTags'] = {
        'Project': 'FinTrust', 'Environment': ref('StageName'), 'Service': 'fintrust-auth'}
    template['Parameters']['EnableScopeRecovery'] = flag('Optional DynamoDB point-in-time recovery; may incur charges.')
    template.setdefault('Conditions', {})['ScopeRecoveryEnabled'] = enabled('EnableScopeRecovery')
    for resource in template['Resources'].values():
        if resource['Type'] == 'AWS::DynamoDB::Table':
            resource['Properties']['PointInTimeRecoverySpecification'] = {
                'PointInTimeRecoveryEnabled': {'Fn::If': ['ScopeRecoveryEnabled', True, False]}}
    return template


def main():
    out = ROOT / 'templates'
    out.mkdir(exist_ok=True)
    generated = {'ses-identities.json': ses_template(), 'application-functions.json': application_template(),
                 'monitoring.json': monitoring_template(), 'alert-ses-policy.json': alert_send_policy(),
                 'cognito.json': cognito_template(), 'api.json': api_template()}
    for name, source in [('api-shell.json', 'api/gateway-shell.json')]:
        generated[name] = json.loads((ROOT / 'source/infrastructure' / source).read_text(encoding='utf-8'))
        generated[name]['Resources']['Api']['Properties']['Tags'] = [
            {'Key': 'Project', 'Value': 'FinTrust'},
            {'Key': 'Environment', 'Value': ref('StageName')}]
    for name, data in generated.items():
        (out / name).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8', newline='\n')
    missing = {name: {key: None for key, value in data.get('Parameters', {}).items() if 'Default' not in value}
               for name, data in generated.items() if 'Parameters' in data}
    (ROOT / 'required-inputs.json').write_text(json.dumps(missing, indent=2) + '\n', encoding='utf-8', newline='\n')
    result = {'status': 'PREPARED_LOCALLY_NOT_DEPLOYED', 'aws_changes': 0,
              'api_detailed_metrics_enabled': False,
              'email_verification': 'NOT_CHECKED', 'sender': EMAIL, 'recipient': EMAIL,
              'files': {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in generated},
              'remaining_gates': ['Actual resource and identity inventory', 'Required inputs and IAM review',
                                  'One consolidated source release', 'Linux artifact verification',
                                  'Quota resolution', 'Cost-compatible live migration and grants', 'Live E2E']}
    (ROOT / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print('Prepared 7 local configuration documents. AWS changes: 0.')


if __name__ == '__main__':
    main()
