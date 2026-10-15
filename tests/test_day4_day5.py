import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fintrust import api
from fintrust.pagination import fingerprint, encode_cursor, decode_cursor
from src.shared.logger import JsonFormatter
from infrastructure.iam.create_roles import build_policies

ACCOUNT = '20000000-0000-4000-8000-000000000001'


def test_cursor_round_trip_and_filter_binding():
    scope = fingerprint(ACCOUNT, None, None, 50)
    when = datetime(2026, 9, 30, tzinfo=timezone.utc)
    token = encode_cursor({'tx_date': when, 'tx_id': ACCOUNT}, scope, 2)
    assert decode_cursor(token, scope) == (when, ACCOUNT, 2)
    with pytest.raises(ValueError):
        decode_cursor(token, fingerprint(ACCOUNT, None, None, 10))


@pytest.mark.parametrize('token', ['', 'not-json', 'a' * 1025, 'bnVsbA', 'e30'])
def test_invalid_cursor_returns_400_without_database(token):
    response = api.app.test_client().get('/v1/transactions', query_string={'account_id': ACCOUNT, 'cursor': token})
    assert response.status_code == 400


def test_default_page_contract(monkeypatch):
    monkeypatch.setattr(api, 'get_transaction_page', lambda *args: ([], {
        'count': 0, 'page': 1, 'total': 0, 'limit': 50, 'next_cursor': None}))
    result = api.app.test_client().get('/v1/transactions', query_string={'account_id': ACCOUNT})
    assert result.status_code == 200
    assert result.json['meta'] == {'count': 0, 'page': 1, 'total': 0, 'limit': 50, 'next_cursor': None}


def test_json_logger_omits_exception_message():
    try:
        raise ValueError('secret database password')
    except ValueError:
        import sys
        record = logging.LogRecord('api', logging.ERROR, '', 0, '{"event":"failed"}', (), sys.exc_info())
    result = JsonFormatter().format(record)
    assert 'secret' not in result
    assert json.loads(result)['error_type'] == 'ValueError'
    assert '\n' not in result


def test_service_policies_enforce_distinct_resources():
    policies = build_policies('123456789012', 'af-south-1', 'dev', 'test-bucket', 'risk_scores',
                              'db-example', 'alerts@example.com')
    actions = lambda service: {a for s in policies[service]['Statement'] for a in s['Action']}
    assert not any(a.startswith('dynamodb:') for a in actions('ingest'))
    assert actions('api') & {'dynamodb:PutItem', 'dynamodb:UpdateItem', 'ses:SendEmail'} == set()
    assert {'dynamodb:PutItem', 'sqs:ReceiveMessage', 'sqs:DeleteMessage', 's3:PutObject'} <= actions('scoring')
    assert 'lambda:InvokeFunction' not in actions('scoring')
    assert 'ses:SendEmail' not in actions('scoring')
    assert 'ses:SendEmail' in actions('alert')
    assert 's3:PutObject' in actions('report')
    assert 's3:GetObject' not in actions('scoring')
    for service, policy in policies.items():
        if service in {'ingest', 'alert'}:
            assert 'rds-db:connect' not in actions(service)
            continue
        rds = next(s for s in policy['Statement'] if s['Action'] == ['rds-db:connect'])
        assert rds['Resource'].endswith('/fintrust_' + service + '_dev')


def test_gateway_routes_and_restricted_invocation():
    template = json.loads(Path('infrastructure/api/gateway.json').read_text())
    resources = template['Resources']
    methods = [v['Properties'] for v in resources.values() if v['Type'] == 'AWS::ApiGateway::Method']
    assert len(methods) == 7
    assert {(m['HttpMethod'], m['AuthorizationType']) for m in methods} == {
        ('GET', 'NONE'), ('POST', 'COGNITO_USER_POOLS'),
        ('GET', 'COGNITO_USER_POOLS'), ('OPTIONS', 'NONE')}
    assert all(m.get('AuthorizationScopes') == ['openid'] for m in methods
               if m['AuthorizationType'] == 'COGNITO_USER_POOLS')
    assert resources['CognitoAuthorizer']['Properties']['Type'] == 'COGNITO_USER_POOLS'
    assert resources['CognitoAuthorizer']['Properties']['IdentitySource'] == 'method.request.header.Authorization'
    permissions = [v['Properties'] for v in resources.values() if v['Type'] == 'AWS::Lambda::Permission']
    assert len(permissions) == 1
    assert 'SourceArn' in permissions[0] and 'SourceAccount' in permissions[0]
    assert '${StageName}/*' in permissions[0]['SourceArn']['Fn::Sub']
    assert {'ApiId', 'BaseUrl', 'CallbackUrl'} <= set(template['Outputs'])
    shell = json.loads(Path('infrastructure/api/gateway-shell.json').read_text())
    assert shell['Resources']['Api']['Type'] == 'AWS::ApiGateway::RestApi'
    assert shell['Outputs']['ApiId']['Value'] == {'Ref': 'Api'}
    assert shell['Outputs']['CallbackUrl']['Value']['Fn::Sub'].endswith('/${StageName}/')


@pytest.fixture(autouse=True)
def authenticated_test_caller(monkeypatch):
    from fintrust import auth
    accounts=tuple("20000000-0000-4000-8000-00000000000"+str(i) for i in range(1,6))
    monkeypatch.setattr(auth,"authenticate",lambda:auth.Principal("test-admin","Admin",accounts))
