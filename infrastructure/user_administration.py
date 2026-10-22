"""Extend the existing same-origin API with isolated Cognito administration.

The new function has no VPC/database access. It uses the existing authorizer,
MFA user pool and account-scope table; no NAT or paid interface endpoint is added.
"""
import copy


def add_user_administration(template):
    template = copy.deepcopy(template)
    params = template['Parameters']
    params.update({
        'UserAdminCodeBucket': {'Type': 'String'},
        'UserAdminCodeKey': {'Type': 'String'},
        'UserAdminCodeVersion': {'Type': 'String', 'MinLength': 1},
        'UserAdminAppClientId': {'Type': 'String'},
        'UserAdminCognitoDomain': {'Type': 'String', 'AllowedPattern': 'https://[^/]+', 'Description': 'Existing managed-login HTTPS origin'},
        'UserAdminScopeTable': {'Type': 'String'},
        'EnableUserAdministration': {'Type': 'String', 'Default': 'false', 'AllowedValues': ['false', 'true']},
    })
    template.setdefault('Conditions', {})['UserAdministrationEnabled'] = {'Fn::Equals': [{'Ref': 'EnableUserAdministration'}, 'true']}
    resources = template['Resources']
    function_name = {'Fn::Sub': 'fintrust-user-admin-${StageName}'}
    pool_id = {'Fn::Select': [1, {'Fn::Split': ['/', {'Ref': 'UserPoolArn'}]}]}
    scope_arn = {'Fn::Sub': 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${UserAdminScopeTable}'}
    tags = [{'Key': 'Project', 'Value': 'FinTrust'}, {'Key': 'Environment', 'Value': {'Ref': 'StageName'}}]
    resources.update({
        'UserProvisioningReceipts': {
            'Type': 'AWS::DynamoDB::Table', 'DeletionPolicy': 'Retain', 'UpdateReplacePolicy': 'Retain',
            'Properties': {'TableName': {'Fn::Sub': 'imbokodo-${StageName}-user-provisioning'},
                'BillingMode': 'PAY_PER_REQUEST', 'AttributeDefinitions': [{'AttributeName': 'request_id', 'AttributeType': 'S'}],
                'KeySchema': [{'AttributeName': 'request_id', 'KeyType': 'HASH'}],
                'SSESpecification': {'SSEEnabled': True}, 'DeletionProtectionEnabled': True, 'Tags': tags}},
        'UserAdminLogs': {'Type': 'AWS::Logs::LogGroup', 'DeletionPolicy': 'Retain', 'UpdateReplacePolicy': 'Retain',
            'Properties': {'LogGroupName': {'Fn::Sub': '/aws/lambda/fintrust-user-admin-${StageName}'}, 'RetentionInDays': 14, 'Tags': tags}},
        'UserAdminRole': {'Type': 'AWS::IAM::Role', 'Properties': {
            'RoleName': {'Fn::Sub': 'fintrust-user-admin-${StageName}'},
            'AssumeRolePolicyDocument': {'Version': '2012-10-17', 'Statement': [{'Effect': 'Allow', 'Principal': {'Service': 'lambda.amazonaws.com'}, 'Action': 'sts:AssumeRole'}]},
            'Tags': tags, 'Policies': [{'PolicyName': 'ScopedWorkforceProvisioning', 'PolicyDocument': {'Version': '2012-10-17', 'Statement': [
                {'Effect': 'Allow', 'Action': ['cognito-idp:AdminCreateUser', 'cognito-idp:AdminAddUserToGroup', 'cognito-idp:AdminListGroupsForUser'], 'Resource': {'Ref': 'UserPoolArn'}},
                {'Effect': 'Allow', 'Action': ['dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:UpdateItem'], 'Resource': [scope_arn, {'Fn::GetAtt': ['UserProvisioningReceipts', 'Arn']}]},
                {'Effect': 'Allow', 'Action': ['logs:CreateLogStream', 'logs:PutLogEvents'], 'Resource': {'Fn::Sub': 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/fintrust-user-admin-${StageName}:*'}}
            ]}}]}},
        'UserAdminFunction': {'Type': 'AWS::Lambda::Function', 'DependsOn': 'UserAdminLogs', 'Properties': {
            'FunctionName': function_name, 'Role': {'Fn::GetAtt': ['UserAdminRole', 'Arn']},
            'Runtime': 'python3.12', 'Handler': 'fintrust.cloud_users.lambda_handler', 'Architectures': ['x86_64'],
            'Timeout': 28, 'MemorySize': 256,
            'Code': {'S3Bucket': {'Ref': 'UserAdminCodeBucket'}, 'S3Key': {'Ref': 'UserAdminCodeKey'}, 'S3ObjectVersion': {'Ref': 'UserAdminCodeVersion'}},
            'ReservedConcurrentExecutions': {'Fn::If': ['UserAdministrationEnabled', {'Ref': 'AWS::NoValue'}, 0]},
            'Environment': {'Variables': {'AUTH_MODE': 'cognito', 'COGNITO_USER_POOL_ID': pool_id,
                'COGNITO_APP_CLIENT_ID': {'Ref': 'UserAdminAppClientId'}, 'COGNITO_DOMAIN': {'Ref': 'UserAdminCognitoDomain'},
                'COGNITO_REDIRECT_URI': {'Fn::Sub': 'https://${Api}.execute-api.${AWS::Region}.${AWS::URLSuffix}/${StageName}/'},
                'COGNITO_LOGOUT_URI': {'Fn::Sub': 'https://${Api}.execute-api.${AWS::Region}.${AWS::URLSuffix}/${StageName}/'},
                'COGNITO_USER_SCOPE_TABLE': {'Ref': 'UserAdminScopeTable'}, 'USER_PROVISIONING_TABLE': {'Ref': 'UserProvisioningReceipts'}}}, 'Tags': tags}},
        'UserProvisioningEndpoint': {'Type': 'AWS::ApiGateway::Resource', 'Properties': {
            'RestApiId': {'Ref': 'Api'}, 'ParentId': {'Ref': 'V1'}, 'PathPart': 'user-provisioning'}},
        'UserAdminInvoke': {'Type': 'AWS::Lambda::Permission', 'Properties': {
            'Action': 'lambda:InvokeFunction', 'Principal': 'apigateway.amazonaws.com', 'FunctionName': {'Ref': 'UserAdminFunction'},
            'SourceAccount': {'Ref': 'AWS::AccountId'},
            'SourceArn': {'Fn::Sub': 'arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:${Api}/${StageName}/*/v1/user-provisioning'}}},
    })
    methods = []
    for method in ('GET', 'POST'):
        name = 'UserProvisioning' + method.title()
        methods.append(name)
        resources[name] = {'Type': 'AWS::ApiGateway::Method', 'Properties': {
            'RestApiId': {'Ref': 'Api'}, 'ResourceId': {'Ref': 'UserProvisioningEndpoint'}, 'HttpMethod': method,
            'AuthorizationType': 'COGNITO_USER_POOLS', 'AuthorizerId': {'Ref': 'CognitoAuthorizer'}, 'AuthorizationScopes': ['openid'],
            'Integration': {'Type': 'AWS_PROXY', 'IntegrationHttpMethod': 'POST',
                'Uri': {'Fn::Sub': 'arn:${AWS::Partition}:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${UserAdminFunction.Arn}/invocations'}}}}
    # Existing deployment snapshots do not pick up newly added methods. Give
    # the snapshot a new identity and move stage references to that snapshot.
    renamed = {}
    for name, resource in list(resources.items()):
        if resource['Type'] == 'AWS::ApiGateway::Deployment':
            depends = resource.get('DependsOn', [])
            if isinstance(depends, str): depends = [depends]
            resource['DependsOn'] = list(dict.fromkeys(depends + methods))
            if not name.endswith('Workforce20261022'):
                renamed[name] = name + 'Workforce20261022'
    for before, after in renamed.items():
        resources[after] = resources.pop(before)

    def replace_refs(value):
        if isinstance(value, dict):
            if set(value) == {'Ref'} and value['Ref'] in renamed:
                value['Ref'] = renamed[value['Ref']]
            for child in value.values(): replace_refs(child)
        elif isinstance(value, list):
            for child in value: replace_refs(child)
    replace_refs(template)
    return template
