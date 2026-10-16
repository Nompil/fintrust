"""Check release-file bytes and installed policy objects without AWS access."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    manifest = read(ROOT / 'manifest.json')
    installed = read(ROOT / 'evidence/installed.json')
    validation = read(ROOT / 'evidence/validation.json')
    manifest_hash = digest(ROOT / 'manifest.json')
    assert installed['bundle_manifest_sha256'] == validation['manifest_sha256'] == manifest_hash
    assert all(not item['findings'] for item in validation['results'].values())
    for name, binding in manifest['files'].items():
        path = ROOT / name
        assert b'\r\n' not in path.read_bytes(), name
        assert digest(path) == binding['sha256'], name
        assert len(json.dumps(read(path), separators=(',', ':'))) == binding['nonwhitespace_characters'] <= 6144
        if name.startswith('FinTrust'):
            assert read(path) == installed['policies'][path.stem]['document'], name
    assert read(ROOT / 'AdminInstalledApiScopeRead.json') == installed['api_scope_readback']
    prep = ROOT.parent
    for name, expected in read(prep / 'manifest.json')['files'].items():
        assert digest(prep / 'templates' / name) == expected, name
    runtime = prep / 'runtime_iam'
    runtime_manifest = read(runtime / 'manifest.json')
    for name, expected in runtime_manifest['files_sha256'].items():
        assert digest(runtime / name) == expected, name
    assert digest(ROOT / 'AdminInstalledApiScopeRead.json') == runtime_manifest['additional_admin_grant']['sha256']
    live = read(ROOT / 'evidence/live-deployer-checks-20261016.json')
    for name in ('api-shell', 'api', 'application-functions', 'cognito'):
        assert live['checks'][name]['value']['exit_code'] == 0, name
    api = read(ROOT / 'evidence/api-shell-live.json')
    assert api['status'] == 'CREATE_COMPLETE_NON_SERVING_API_IDENTITY'
    assert manifest['api_id'] == api['outputs']['ApiId']
    auth = read(ROOT / 'evidence/auth-configuration-live.json')
    assert auth['status'] == 'CREATE_COMPLETE_EMPTY_AUTH_CONFIGURATION'
    assert digest(prep / 'templates/cognito.json') == auth['template_sha256']
    assert auth['user_pool_read_back']['UserPool']['UserPoolTier'] == 'LITE'
    assert auth['user_pool_read_back']['UserPool']['MfaConfiguration'] == 'ON'
    assert not auth['api_stages_after'].get('item')
    client = auth['client_read_back']['UserPoolClient']
    assert client['CallbackURLs'] == client['LogoutURLs'] == [api['outputs']['CallbackUrl']]
    assert client['AllowedOAuthFlows'] == ['code'] and not client.get('ClientSecret')
    assert not auth['users_created'] and not auth['scope_records_written']
    gateway = read(ROOT / 'evidence/gateway-account-scope-live.json')
    assert gateway['status'] == 'UPDATE_COMPLETE_IN_PLACE_POLICY_ONLY'
    assert digest(prep.parent / 'network-account-scope-update.json') == gateway['candidate_sha256']
    assert gateway['after_stack']['StackStatus'] == 'UPDATE_COMPLETE'
    endpoint = gateway['endpoint_read_back']
    assert endpoint['VpcEndpointId'] == 'vpce-0647afafb32f34e6d' and endpoint['State'] == 'available'
    scope = next(s for s in json.loads(endpoint['PolicyDocument'])['Statement'] if s.get('Sid') == 'ApiReadAccountScopes')
    assert scope['Action'] in ('dynamodb:GetItem', ['dynamodb:GetItem'])
    assert scope['Resource'] == 'arn:aws:dynamodb:af-south-1:966467878406:table/imbokodo-dev-user-account-scopes'
    assert scope['Condition']['StringEquals']['aws:PrincipalArn'] == 'arn:aws:iam::966467878406:role/fintrust-api-dev'
    return {'source_and_installed_policy_bindings': 'PASS', 'canonical_lf_files': len(manifest['files']),
            'latest_template_aws_validation': 'FOUR_TEMPLATES_ACCEPTED',
            'api_id_bound': manifest['api_id'],
            'empty_cognito_configuration': 'READ_BACK',
            'gateway_scope_read_policy': 'UPDATED_IN_PLACE_READ_BACK',
            'live_log_read': 'RESOURCE_NOT_FOUND_FOR_UNCREATED_GROUP; DELIVERY_UNTESTED',
            'deployment_ready': False}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
