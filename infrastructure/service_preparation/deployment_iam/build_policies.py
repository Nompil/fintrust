"""Offline, dev-only deployment permissions. No AWS calls or credential access."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
PREP = ROOT.parent
ACCOUNT = '966467878406'
REGION = 'af-south-1'
ARTIFACT = 'ff6324d64a5d65dab18523a30ea72bb1594d2fa5ca7fbe6b8391c52f03ed589d'
CODE_KEY = f'deployment/lambda/{ARTIFACT}/fintrust.zip'
CODE = f'arn:aws:s3:::fintrust-reports-{ACCOUNT}-{REGION}-dev/{CODE_KEY}'
KEY = f'arn:aws:kms:{REGION}:{ACCOUNT}:key/598a4158-2cc6-4946-af24-512784a276c8'
SERVICES = ['scoring', 'alert', 'report', 'api']
FUNCTIONS = [f'arn:aws:lambda:{REGION}:{ACCOUNT}:function:fintrust-{s}-dev' for s in SERVICES]
STACKS = {
    'application': 'application-functions.json', 'api': 'api.json',
    'auth': 'cognito.json', 'monitoring': 'monitoring.json'}


def stmt(sid, actions, resources, via=False, extra=None):
    condition = {'StringEquals': {'aws:RequestedRegion': REGION}}
    if via:
        condition['ForAnyValue:StringEquals'] = {'aws:CalledVia': ['cloudformation.amazonaws.com']}
    for op, values in (extra or {}).items():
        condition.setdefault(op, {}).update(values)
    return {'Sid': sid, 'Effect': 'Allow', 'Action': actions, 'Resource': resources, 'Condition': condition}


def policy(statements):
    return {'Version': '2012-10-17', 'Statement': statements}


def templates():
    return {k: json.loads((PREP / 'templates' / v).read_text(encoding='utf-8')) for k, v in STACKS.items()}


def generate(api_id=None):
    t = templates()
    cfn = []
    stack_arns = []
    for name, template in t.items():
        stack = f'arn:aws:cloudformation:{REGION}:{ACCOUNT}:stack/fintrust-{name}-dev/*'
        stack_arns.append(stack)
        types = sorted({r['Type'] for r in template['Resources'].values()})
        assert not any(x.startswith(('AWS::IAM::', 'Custom::')) for x in types)
        cfn.append(stmt('Prepare' + name.title(), ['cloudformation:CreateChangeSet'], stack, extra={
            'StringEquals': {'aws:RequestTag/Project': 'FinTrust', 'aws:RequestTag/Environment': 'dev'},
            'StringLike': {'cloudformation:ChangeSetName': f'fintrust-{name}-*'},
            'ForAllValues:StringEquals': {'cloudformation:ResourceTypes': types},
            'Null': {'cloudformation:ResourceTypes': 'false', 'cloudformation:RoleArn': 'true',
                     'cloudformation:ImportResourceTypes': 'true'}}))
        cfn.append(stmt('Manage' + name.title(), ['cloudformation:ExecuteChangeSet', 'cloudformation:DeleteChangeSet'], stack,
                        extra={'StringLike': {'cloudformation:ChangeSetName': f'fintrust-{name}-*'}}))
    cfn.append(stmt('ReadRemainingStacks', ['cloudformation:DescribeChangeSet', 'cloudformation:DescribeStacks',
        'cloudformation:DescribeStackEvents', 'cloudformation:DescribeStackResources', 'cloudformation:DescribeStackResource',
        'cloudformation:ListStackResources', 'cloudformation:ListChangeSets', 'cloudformation:GetTemplate'], stack_arns))
    cfn.append(stmt('RecoverRemainingStacks', ['cloudformation:ContinueUpdateRollback', 'cloudformation:DeleteStack'],
                    stack_arns, extra={'Null': {'cloudformation:RoleArn': 'true'}}))

    application = [
        stmt('ManageFourFunctions', ['lambda:CreateFunction', 'lambda:UpdateFunctionCode', 'lambda:UpdateFunctionConfiguration',
            'lambda:DeleteFunction', 'lambda:PutFunctionConcurrency', 'lambda:DeleteFunctionConcurrency',
            'lambda:TagResource', 'lambda:UntagResource'], FUNCTIONS, via=True),
        stmt('ReadFourFunctions', ['lambda:GetFunction', 'lambda:GetFunctionConfiguration', 'lambda:GetFunctionConcurrency',
            'lambda:GetFunctionCodeSigningConfig', 'lambda:ListTags', 'lambda:GetPolicy'], FUNCTIONS + [FUNCTIONS[-1] + ':*']),
        stmt('ManageApiVersionsAndAlias', ['lambda:PublishVersion', 'lambda:CreateAlias', 'lambda:UpdateAlias',
            'lambda:DeleteAlias', 'lambda:DeleteFunction'], [FUNCTIONS[-1], FUNCTIONS[-1] + ':*'], via=True),
        stmt('ReadApiVersionsAndAlias', ['lambda:GetAlias', 'lambda:ListAliases', 'lambda:ListVersionsByFunction'],
             [FUNCTIONS[-1], FUNCTIONS[-1] + ':*']),
        stmt('ManageReportAsync', ['lambda:PutFunctionEventInvokeConfig', 'lambda:UpdateFunctionEventInvokeConfig',
            'lambda:DeleteFunctionEventInvokeConfig'], FUNCTIONS[2] + ':$LATEST', via=True),
        stmt('ReadReportAsync', ['lambda:GetFunctionEventInvokeConfig'], FUNCTIONS[2] + ':$LATEST'),
        stmt('CreateTwoMappings', ['lambda:CreateEventSourceMapping'], '*', via=True,
             extra={'ArnEquals': {'lambda:FunctionArn': FUNCTIONS[:2]}}),
        stmt('ManageTwoMappings', ['lambda:UpdateEventSourceMapping', 'lambda:DeleteEventSourceMapping'],
             f'arn:aws:lambda:{REGION}:{ACCOUNT}:event-source-mapping:*', via=True,
             extra={'ArnEquals': {'lambda:FunctionArn': FUNCTIONS[:2]}}),
        stmt('ReadTwoMappings', ['lambda:GetEventSourceMapping'],
             f'arn:aws:lambda:{REGION}:{ACCOUNT}:event-source-mapping:*',
             extra={'ArnEquals': {'lambda:FunctionArn': FUNCTIONS[:2]}}),
        stmt('ListMappingMetadata', ['lambda:ListEventSourceMappings'], '*'),
        stmt('PassOnlyFourRuntimeRoles', ['iam:PassRole'],
             [f'arn:aws:iam::{ACCOUNT}:role/fintrust-{s}-dev' for s in SERVICES], via=True,
             extra={'StringEquals': {'iam:PassedToService': 'lambda.amazonaws.com'}}),
        stmt('GrantScheduleInvoke', ['lambda:AddPermission'], FUNCTIONS[2], via=True,
             extra={'StringEquals': {'lambda:Principal': 'events.amazonaws.com'}}),
        stmt('GrantApiGatewayInvoke', ['lambda:AddPermission'], FUNCTIONS[-1] + ':dev', via=True,
             extra={'StringEquals': {'lambda:Principal': 'apigateway.amazonaws.com'}}),
        stmt('RemoveOwnedInvokeStatements', ['lambda:RemovePermission'], [FUNCTIONS[2], FUNCTIONS[-1] + ':dev'], via=True),
        stmt('ManageMonthlyRule', ['events:PutRule', 'events:DeleteRule', 'events:RemoveTargets',
             'events:TagResource', 'events:UntagResource'], f'arn:aws:events:{REGION}:{ACCOUNT}:rule/fintrust-monthly-dev', via=True),
        stmt('SetOnlyReportTarget', ['events:PutTargets'], f'arn:aws:events:{REGION}:{ACCOUNT}:rule/fintrust-monthly-dev',
             via=True, extra={'ForAllValues:ArnEquals': {'events:TargetArn': [FUNCTIONS[2]]},
                              'Null': {'events:TargetArn': 'false'}}),
        stmt('ReadMonthlyRule', ['events:DescribeRule', 'events:ListTargetsByRule', 'events:ListTagsForResource'],
             f'arn:aws:events:{REGION}:{ACCOUNT}:rule/fintrust-monthly-dev'),
        stmt('ManageOnlyReportDeliveryQueuePolicy', ['sqs:SetQueueAttributes'],
             f'arn:aws:sqs:{REGION}:{ACCOUNT}:fintrust-report-failures-dev', via=True),
        stmt('ReadReportDeliveryQueuePolicy', ['sqs:GetQueueAttributes'], f'arn:aws:sqs:{REGION}:{ACCOUNT}:fintrust-report-failures-dev')]

    log_names = [f'/aws/lambda/fintrust-{s}-dev' for s in SERVICES] + ['/aws/apigateway/fintrust-dev']
    logs = [f'arn:aws:logs:{REGION}:{ACCOUNT}:log-group:{n}' for n in log_names]
    dependencies = [
        stmt('ReadOnlyBoundReleaseObject', ['s3:GetObjectVersion'], CODE),
        stmt('DecryptOnlyBoundReleaseViaS3', ['kms:Decrypt'], KEY, extra={
            'StringEquals': {'kms:ViaService': f's3.{REGION}.amazonaws.com', 'kms:CallerAccount': ACCOUNT},
            'StringLike': {'kms:EncryptionContext:aws:s3:arn': [CODE, f'arn:aws:s3:::fintrust-reports-{ACCOUNT}-{REGION}-dev']}}),
        stmt('ReadNineNonsecretSettings', ['ssm:GetParameters', 'ssm:GetParameter'],
             [f'arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/fintrust/dev/{s}/{k}'
              for s in ['scoring', 'report', 'api'] for k in ['db_host', 'db_name', 'db_user']]),
        stmt('ManageOwnedLogConfiguration', ['logs:CreateLogGroup', 'logs:PutRetentionPolicy', 'logs:DeleteRetentionPolicy',
             'logs:TagLogGroup', 'logs:UntagLogGroup'], [r + ':*' for r in logs], via=True),
        stmt('TagOwnedLogGroups', ['logs:TagResource', 'logs:UntagResource'], logs, via=True),
        stmt('ReadOwnedLogTags', ['logs:ListTagsForResource'], logs),
        stmt('DescribeLogGroups', ['logs:DescribeLogGroups'], '*')]
    # Keep each managed document below IAM's independent 6,144-character limit.
    scheduling = application[-5:]
    application = application[:-5]
    dependencies.extend(application[6:10])
    application = application[:6] + application[10:]
    mapping_arns = f'arn:aws:lambda:{REGION}:{ACCOUNT}:event-source-mapping:*'
    dependencies.extend([
        stmt('TagCreatedMappings', ['lambda:TagResource'], mapping_arns, via=True,
             extra={'StringEquals': {'aws:RequestTag/Project': 'FinTrust', 'aws:RequestTag/Environment': 'dev'}}),
        stmt('UntagOwnedMappings', ['lambda:UntagResource'], mapping_arns, via=True,
             extra={'StringEquals': {'aws:ResourceTag/Project': 'FinTrust', 'aws:ResourceTag/Environment': 'dev'}}),
        stmt('ReadOwnedMappingTags', ['lambda:ListTags'], mapping_arns,
             extra={'StringEquals': {'aws:ResourceTag/Project': 'FinTrust', 'aws:ResourceTag/Environment': 'dev'}})])
    application.append(dependencies.pop(2))  # Nine settings resolved by the function stack.
    dependencies.append(stmt('RetagExistingDynamoGatewayDuringStackUpdate', ['ec2:CreateTags'],
        f'arn:aws:ec2:{REGION}:{ACCOUNT}:vpc-endpoint/vpce-0647afafb32f34e6d', via=True,
        extra={'StringEquals': {'aws:ResourceTag/Project': 'FinTrust', 'aws:ResourceTag/Environment': 'dev'}}))

    pools = f'arn:aws:cognito-idp:{REGION}:{ACCOUNT}:userpool/{REGION}_*'
    pool_tags = {'aws:ResourceTag/Project': 'FinTrust', 'aws:ResourceTag/Environment': 'dev',
                 'aws:ResourceTag/Service': 'fintrust-auth'}
    scope_table = f'arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/imbokodo-dev-user-account-scopes'
    identity = [
        stmt('CreateTaggedWorkforcePool', ['cognito-idp:CreateUserPool'], '*', via=True, extra={
            'StringEquals': {k.replace('ResourceTag', 'RequestTag'): v for k, v in pool_tags.items()}}),
        stmt('ManageTaggedWorkforcePool', ['cognito-idp:UpdateUserPool', 'cognito-idp:DeleteUserPool',
            'cognito-idp:SetUserPoolMfaConfig', 'cognito-idp:CreateUserPoolClient', 'cognito-idp:UpdateUserPoolClient',
            'cognito-idp:DeleteUserPoolClient', 'cognito-idp:CreateUserPoolDomain', 'cognito-idp:UpdateUserPoolDomain',
            'cognito-idp:DeleteUserPoolDomain', 'cognito-idp:CreateGroup', 'cognito-idp:UpdateGroup', 'cognito-idp:DeleteGroup'],
            pools, via=True, extra={'StringEquals': pool_tags}),
        # CreateUserPool authorizes its tag-on-create dependency before an ID exists.
        # Keep the account/region, required ownership request tags and CFN boundary.
        stmt('TagCreatedWorkforcePool', ['cognito-idp:TagResource'],
             f'arn:aws:cognito-idp:{REGION}:{ACCOUNT}:userpool/*', via=True,
             extra={'StringEquals': {k.replace('ResourceTag', 'RequestTag'): v for k, v in pool_tags.items()}}),
        stmt('ReadTaggedWorkforcePool', ['cognito-idp:DescribeUserPool', 'cognito-idp:GetUserPoolMfaConfig',
            'cognito-idp:DescribeUserPoolClient', 'cognito-idp:GetGroup', 'cognito-idp:ListGroups',
            'cognito-idp:ListUserPoolClients', 'cognito-idp:ListTagsForResource'], pools, extra={'StringEquals': pool_tags}),
        stmt('DiscoverIdentityMetadata', ['cognito-idp:ListUserPools', 'cognito-idp:DescribeUserPoolDomain'], '*'),
        stmt('ManageOnlyScopeTable', ['dynamodb:CreateTable', 'dynamodb:UpdateTable', 'dynamodb:DeleteTable', 'dynamodb:UpdateContinuousBackups',
            'dynamodb:TagResource', 'dynamodb:UntagResource'], scope_table, via=True),
        stmt('ReadOnlyScopeTableMetadata', ['dynamodb:DescribeTable', 'dynamodb:DescribeContinuousBackups',
            'dynamodb:DescribeTimeToLive', 'dynamodb:ListTagsOfResource'], scope_table)]

    api = [stmt('CreateNamedRegionalApiOnly', ['apigateway:POST'], f'arn:aws:apigateway:{REGION}::/restapis', via=True,
                extra={'StringEquals': {'apigateway:Request/ApiName': 'fintrust-dev'},
                       'ForAllValues:StringEquals': {'apigateway:Request/EndpointType': ['REGIONAL']},
                       'Null': {'apigateway:Request/EndpointType': 'false'}}),
           stmt('ReadApiInventoryAndAccount', ['apigateway:GET'],
                [f'arn:aws:apigateway:{REGION}::/restapis', f'arn:aws:apigateway:{REGION}::/account'])]
    if api_id:
        assert api_id.isalnum() and 1 <= len(api_id) <= 20
        api = [entry for entry in api if entry['Sid'] != 'CreateNamedRegionalApiOnly']
        base = f'arn:aws:apigateway:{REGION}::/restapis/{api_id}'
        tag = f'arn:aws:apigateway:{REGION}::/tags/{quote(base, safe="")}'
        api += [stmt('ManageOnlyBoundApi', ['apigateway:POST', 'apigateway:PUT', 'apigateway:PATCH', 'apigateway:DELETE'],
                     [base, base + '/*', tag], via=True),
                stmt('ReadOnlyBoundApi', ['apigateway:GET'], [base, base + '/*', tag])]
    else:
        # CloudFormation must read its newly generated API ID before it can
        # return outputs. Bootstrap grants metadata reads, never API mutations.
        api.append(stmt('BootstrapReadApiMetadata', ['apigateway:GET'],
                        f'arn:aws:apigateway:{REGION}::/restapis/*'))
        tag_prefix = quote(f'arn:aws:apigateway:{REGION}::/restapis/', safe='')
        api.append(stmt('BootstrapTagNewApi', ['apigateway:PUT'],
            f'arn:aws:apigateway:{REGION}::/tags/{tag_prefix}*', via=True,
            extra={'StringEquals': {'aws:RequestTag/Project': 'FinTrust', 'aws:RequestTag/Environment': 'dev'}}))

    alarms = [f'arn:aws:cloudwatch:{REGION}:{ACCOUNT}:alarm:' + r['Properties']['AlarmName']['Fn::Sub'].replace('${Stage}', 'dev')
              for r in t['monitoring']['Resources'].values()]
    monitoring = [stmt('ManageOnlyPreparedAlarms', ['cloudwatch:PutMetricAlarm', 'cloudwatch:DeleteAlarms',
         'cloudwatch:TagResource', 'cloudwatch:UntagResource'], alarms, via=True),
        stmt('ReadOnlyPreparedAlarms', ['cloudwatch:DescribeAlarms', 'cloudwatch:DescribeAlarmHistory',
             'cloudwatch:ListTagsForResource'], alarms)]
    monitoring.extend(scheduling)
    monitoring.append(stmt('ReadOwnedApplicationLogStreams',
        ['logs:DescribeLogStreams', 'logs:GetLogEvents', 'logs:FilterLogEvents'], [r + ':*' for r in logs]))
    output = {k: policy(v) for k, v in {
        'FinTrustRemainingCloudFormation': cfn, 'FinTrustApplicationDeployment': application,
        'FinTrustReleaseDependencies': dependencies, 'FinTrustIdentityDeployment': identity,
        'FinTrustApiDeployment': api, 'FinTrustMonitoringDeployment': monitoring}.items()}
    return output, policy([stmt('ReadOnlyWorkforceAccountScope', ['dynamodb:GetItem'], scope_table)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--api-id')
    args = parser.parse_args()
    policies, scopes = generate(args.api_id)
    manifest = {'account': ACCOUNT, 'region': REGION, 'stage': 'dev', 'api_id': args.api_id,
        'bound_artifact_sha256': ARTIFACT, 'proposed_code_key_not_uploaded': CODE_KEY,
        'activation_authorized_by_policy_install': False, 'files': {}}
    for name, doc in {**policies, 'AdminInstalledApiScopeRead': scopes}.items():
        size = len(json.dumps(doc, separators=(',', ':')))
        assert size <= 6144, (name, size)
        path = ROOT / (name + '.json')
        path.write_text(json.dumps(doc, indent=2) + '\n', encoding='utf-8', newline='\n')
        manifest['files'][path.name] = {'nonwhitespace_characters': size,
                                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest['stack_resource_types'] = {name: sorted({r['Type'] for r in t['Resources'].values()})
                                        for name, t in templates().items()}
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({name: v['nonwhitespace_characters'] for name, v in manifest['files'].items()}))


if __name__ == '__main__':
    main()
