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
    configuration = {}
    app_path = prep / 'shared_manual/application-disabled-live.json'
    if app_path.exists():
        app = read(app_path)
        assert app['status'] == 'CREATE_COMPLETE_FUNCTIONS_ZERO_CONSUMERS_AND_REPORTS_DISABLED'
        assert digest(prep / 'shared_manual/application-functions-shared-manual.json') == app['template_sha256']
        assert app['stack_read_back']['StackStatus'] == 'CREATE_COMPLETE'
        assert len(app['functions']) == 4 and len(app['mappings']) == 2
        assert all(f['concurrency']['ReservedConcurrentExecutions'] == 0 for f in app['functions'].values())
        assert all(m['State'] == 'Disabled' for m in app['mappings'])
        assert app['monthly_rule']['State'] == 'DISABLED' and not app['raw_notifications_after']
        configuration['application'] = 'DEPLOYED_DISABLED_RECEIPT_BOUND'
    api_path = ROOT / 'evidence/api-configuration-live.json'
    if api_path.exists():
        configured = read(api_path)
        assert configured['status'] == 'UPDATE_COMPLETE_API_CONFIGURED_LAMBDA_ZERO_NO_TEST_TRAFFIC'
        assert digest(prep / 'templates/api.json') == configured['template_sha256']
        assert configured['outputs']['ApiId'] == manifest['api_id']
        assert configured['outputs']['CallbackUrl'] == api['outputs']['CallbackUrl']
        assert configured['stack_read_back']['StackStatus'] == 'UPDATE_COMPLETE'
        assert configured['access_log_group']['retentionInDays'] == 30
        assert len(configured['methods']) == 7
        assert all(c['ReservedConcurrentExecutions'] == 0 for c in configured['concurrency'].values())
        assert all(m['State'] == 'Disabled' for m in configured['mappings'])
        assert configured['requests_sent'] == configured['application_invocations'] == configured['emails_sent'] == 0
        assert not configured['sql_executed'] and not configured['processing_enabled']
        cleanup = read(ROOT / 'evidence/api-empty-log-cleanup-permission.json')
        assert cleanup['cleanup_verified'] and not cleanup['attached'] and not cleanup['created']
        configuration['api'] = 'CONFIGURED_LAMBDA_ZERO_RECEIPT_BOUND'
    return {'source_and_installed_policy_bindings': 'PASS', 'canonical_lf_files': len(manifest['files']),
            'latest_template_aws_validation': 'FOUR_TEMPLATES_ACCEPTED',
            'api_id_bound': manifest['api_id'],
            'empty_cognito_configuration': 'READ_BACK',
            'gateway_scope_read_policy': 'UPDATED_IN_PLACE_READ_BACK',
            'historical_log_probe': 'RESOURCE_NOT_FOUND_BEFORE_DEPLOYMENT; DELIVERY_UNTESTED',
            'latest_configuration_receipts': configuration,
            'deployment_ready': False}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
