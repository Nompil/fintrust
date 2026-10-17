"""Local-only verification of Cognito JWT checks and application role mapping."""
import time
import uuid
from datetime import datetime, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from fintrust import api, cognito_auth

ACCOUNT = '20000000-0000-4000-8000-000000000001'
SUBJECT = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
ISSUER = 'https://cognito-idp.af-south-1.amazonaws.com/af-south-1_TestPool'
CLIENT = 'test-public-client'
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class Key:
    key = KEY.public_key()


class Jwks:
    def get_signing_key_from_jwt(self, _token):
        return Key()


def configure(monkeypatch):
    monkeypatch.setenv('AUTH_MODE', 'cognito')
    monkeypatch.setenv('AWS_REGION', 'af-south-1')
    monkeypatch.setenv('COGNITO_USER_POOL_ID', 'af-south-1_TestPool')
    monkeypatch.setenv('COGNITO_APP_CLIENT_ID', CLIENT)
    monkeypatch.setenv('COGNITO_DOMAIN', 'https://imbokodo-test.auth.af-south-1.amazoncognito.com')
    monkeypatch.setenv('COGNITO_REDIRECT_URI', 'https://workbench.example.test/release1')
    monkeypatch.setenv('COGNITO_LOGOUT_URI', 'https://workbench.example.test/release1')
    monkeypatch.setenv('COGNITO_USER_SCOPE_TABLE', 'test-user-scope')
    monkeypatch.setattr(cognito_auth, '_jwks_client', lambda issuer: Jwks())
    monkeypatch.setattr(cognito_auth, '_account_scope', lambda sub, username: (ACCOUNT,) if (sub, username) == (SUBJECT, 'analyst01') else ())


def claims(group='Analysts', **changes):
    now = int(time.time())
    result = {'iss': ISSUER, 'sub': SUBJECT, 'username': 'analyst01', 'client_id': CLIENT,
              'token_use': 'access', 'cognito:groups': [group], 'iat': now, 'exp': now + 300}
    result.update(changes)
    return result


def signed(payload=None, key=KEY):
    return jwt.encode(payload or claims(), key, algorithm='RS256', headers={'kid': 'test-key'})


@pytest.mark.parametrize('group,role', [
    ('Analysts', 'Risk/Compliance Analyst'), ('Administrators', 'Admin'),
    ('Auditors', 'Read-only/Auditor'), ('Maintainers', 'Maintainer'),
])
def test_verified_cognito_groups_map_to_existing_roles_and_scope(monkeypatch, group, role):
    configure(monkeypatch)
    token = signed(claims(group))
    principal = cognito_auth.authenticate(token)
    assert (principal.subject, principal.role, principal.accounts, principal.auth_source) == (
        'analyst01', role, (ACCOUNT,), 'cognito')
    assert principal.user_id and principal.user_id != SUBJECT


@pytest.mark.parametrize('payload', [
    claims(exp=int(time.time()) - 10),
    claims(iss='https://wrong.example/pool'),
    claims(client_id='wrong-client'),
    claims(token_use='id'),
    claims(**{'cognito:groups': []}),
    claims(**{'cognito:groups': ['Analysts', 'Administrators']}),
    claims(**{'cognito:groups': ['Analysts', 'UnapprovedGroup']}),
    claims(**{'cognito:groups': ['UnapprovedGroup']}),
    {k: v for k, v in claims().items() if k != 'sub'},
])
def test_invalid_or_ambiguous_access_claims_are_rejected(monkeypatch, payload):
    configure(monkeypatch)
    with pytest.raises(PermissionError):
        cognito_auth.verify_access_token(signed(payload))


def test_bad_signature_and_malformed_tokens_are_rejected(monkeypatch):
    configure(monkeypatch)
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(PermissionError):
        cognito_auth.verify_access_token(signed(claims(), wrong_key))
    with pytest.raises(PermissionError):
        cognito_auth.verify_access_token('not.a.jwt')


def test_invalid_configuration_and_unmapped_scope_fail_closed(monkeypatch):
    real_scope = cognito_auth._account_scope
    configure(monkeypatch)
    monkeypatch.setattr(cognito_auth, '_account_scope', real_scope)
    monkeypatch.setenv('COGNITO_USER_SCOPE_TABLE', '')
    with pytest.raises(PermissionError):
        cognito_auth.authenticate(signed())
    monkeypatch.setenv('COGNITO_USER_SCOPE_TABLE', 'test-user-scope')
    monkeypatch.setattr(cognito_auth, '_account_scope', lambda *args: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(PermissionError):
        cognito_auth.authenticate(signed())
    monkeypatch.setenv('COGNITO_USER_POOL_ID', 'us-east-1_wrong-region')
    with pytest.raises(RuntimeError):
        cognito_auth.configuration()


@pytest.mark.parametrize('group,role', [
    ('Analysts', 'Risk/Compliance Analyst'), ('Administrators', 'Admin'),
    ('Auditors', 'Read-only/Auditor'), ('Maintainers', 'Maintainer'),
])
def test_session_endpoint_uses_verified_role_and_server_scope(monkeypatch, group, role):
    configure(monkeypatch)
    client = api.app.test_client()
    response = client.get('/v1/session', headers={'Authorization': 'Bearer ' + signed(claims(group))})
    assert response.status_code == 200
    data = response.json['data']
    assert (data['subject'], data['username'], data['role'], data['accounts'], data['auth_source']) == (
        'analyst01', 'analyst01', role, [ACCOUNT], 'cognito')
    assert 'token' not in response.get_data(as_text=True).lower()


def test_cognito_auth_configuration_is_public_and_contains_no_secret(monkeypatch):
    configure(monkeypatch)
    response = api.app.test_client().get('/v1/auth/config')
    assert response.status_code == 200
    assert response.json['data']['mode'] == 'cognito'
    assert response.json['data']['client_id'] == CLIENT
    assert 'client_secret' not in response.get_data(as_text=True).lower()


def test_server_ignores_client_supplied_role_and_keeps_account_scope(monkeypatch):
    configure(monkeypatch)
    client = api.app.test_client()
    headers = {'Authorization': 'Bearer ' + signed(), 'X-Role': 'Admin', 'X-Accounts': '*'}
    session = client.get('/v1/session', headers=headers)
    assert session.status_code == 200 and session.json['data']['role'] == 'Risk/Compliance Analyst'
    denied = client.get('/v1/reports?account_id=20000000-0000-4000-8000-000000000002', headers=headers)
    assert denied.status_code == 403


@pytest.mark.parametrize('group,action,allowed', [
    ('Analysts', 'review', True), ('Administrators', 'assign_review', True),
    ('Administrators', 'review', False), ('Auditors', 'review', False),
    ('Auditors', 'audit', True), ('Maintainers', 'retry', True),
    ('Maintainers', 'review', False),
])
def test_cognito_roles_keep_existing_separation_of_duties(monkeypatch, group, action, allowed):
    configure(monkeypatch)
    _claims, role = cognito_auth.verify_access_token(signed(claims(group)))
    from fintrust.release_contract import authorize
    if allowed:
        authorize(role, action)
    else:
        with pytest.raises(PermissionError):
            authorize(role, action)


@pytest.mark.parametrize('group_claim', ['Analysts', '[Analysts]', '["Analysts"]', ['Analysts']])
@pytest.mark.parametrize('date_claims',[False,True])
def test_api_gateway_authorizer_claims_are_trusted_without_jwks(monkeypatch, group_claim,date_claims):
    configure(monkeypatch)
    monkeypatch.setenv('AWS_EXECUTION_ENV', 'AWS_Lambda_python3.12')
    gateway = claims(**{'cognito:groups': group_claim, 'scope': 'openid profile'})
    if date_claims:
        for name in ('exp','iat'):gateway[name]=datetime.fromtimestamp(gateway[name],timezone.utc).strftime('%a %b %d %H:%M:%S UTC %Y')
    monkeypatch.setattr(cognito_auth, 'verify_access_token', lambda _token: pytest.fail('JWKS lookup must not run in Lambda'))
    token = cognito_auth.set_gateway_claims(gateway)
    try:
        principal = cognito_auth.authenticate('gateway-validated-token')
    finally:
        cognito_auth.reset_gateway_claims(token)
    assert principal.role == 'Risk/Compliance Analyst'
    assert principal.accounts == (ACCOUNT,)


@pytest.mark.parametrize('change', [
    {'iss': 'https://attacker.invalid'}, {'token_use': 'id'},
    {'client_id': 'other-client'}, {'scope': 'email'}, {'exp': '1'},
    {'cognito:groups': 'Analysts,Administrators'},
    {'cognito:groups': '[Analysts, Administrators]'},
    {'cognito:groups': '["Analysts","Administrators"]'},
    {'cognito:groups': '[UnapprovedGroup]'},
    {'cognito:groups': '[Analysts'},
    {'exp':'Thu Jan 01 00:00:01 UTC 1970'},
    {'iat':'Thu Jan 01 00:00:01 GMT 1970'},
    {'exp':'not a timestamp'},
])
def test_api_gateway_authorizer_claims_fail_closed(monkeypatch, change):
    configure(monkeypatch)
    monkeypatch.setenv('AWS_EXECUTION_ENV', 'AWS_Lambda_python3.12')
    gateway = claims(**{'cognito:groups': 'Analysts', 'scope': 'openid'})
    gateway.update(change)
    token = cognito_auth.set_gateway_claims(gateway)
    try:
        with pytest.raises(PermissionError):
            cognito_auth.authenticate('gateway-validated-token')
    finally:
        cognito_auth.reset_gateway_claims(token)


def test_lambda_cognito_mode_rejects_missing_gateway_claims(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv('AWS_EXECUTION_ENV', 'AWS_Lambda_python3.12')
    token = cognito_auth.set_gateway_claims(None)
    try:
        with pytest.raises(PermissionError):
            cognito_auth.authenticate('token')
    finally:
        cognito_auth.reset_gateway_claims(token)


def test_gateway_rejection_diagnostics_do_not_log_claim_values(monkeypatch,caplog):
    configure(monkeypatch)
    with pytest.raises(PermissionError):
        cognito_auth._role_from_gateway_claims(claims(iss='secret-marker-never-log',scope='openid'))
    assert 'secret-marker-never-log' not in caplog.text
    assert 'issuer/client/token-use rejected' in caplog.text


def test_cognito_stack_and_operator_bootstrap_are_safe_by_default(monkeypatch, capsys):
    import json
    from pathlib import Path
    import sys
    template = json.loads(Path('infrastructure/auth/cognito.json').read_text(encoding='utf8'))
    resources = template['Resources']
    assert len([r for r in resources.values() if r['Type'] == 'AWS::Cognito::UserPool']) == 1
    assert len([r for r in resources.values() if r['Type'] == 'AWS::Cognito::UserPoolGroup']) == 4
    client = resources['ImbokodoWebClient']['Properties']
    assert client['GenerateSecret'] is False and client['AllowedOAuthFlows'] == ['code']
    assert resources['UserAccountScopes']['Properties']['DeletionProtectionEnabled'] is True
    policy = resources['ApiReadUserScopes']['Properties']['PolicyDocument']['Statement'][0]
    assert policy['Action'] == ['dynamodb:GetItem']
    assert 'AWS::EC2::NatGateway' not in {r['Type'] for r in resources.values()}
    from infrastructure.auth import bootstrap_cognito_user as bootstrap
    monkeypatch.setattr(sys, 'argv', ['bootstrap_cognito_user.py', '--username', 'analyst01',
        '--email', 'analyst@example.test', '--user-pool-id', 'af-south-1_test',
        '--scope-table', 'scope-table', '--account', ACCOUNT])
    assert bootstrap.main() == 0
    assert 'Dry run only' in capsys.readouterr().out


def test_jwt_crypto_dependencies_are_pinned_for_verification_and_no_deps_lambda_build():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    runtime = (root / 'requirements-runtime.txt').read_text(encoding='utf8')
    verification = (root / 'requirements-verification-lock.txt').read_text(encoding='utf8')
    lambda_lock = (root / 'requirements-lambda.txt').read_text(encoding='utf8')
    assert 'PyJWT[crypto]==2.10.1' in runtime
    assert 'PyJWT[crypto]==2.10.1' in verification
    assert '-r requirements-runtime.txt' in lambda_lock
    assert all(pin in lambda_lock for pin in (
        'cryptography==50.0.2', 'cffi==2.1.1', 'pycparser==3.11'))
