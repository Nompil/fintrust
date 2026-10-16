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
    return {'source_and_installed_policy_bindings': 'PASS', 'canonical_lf_files': len(manifest['files']),
            'latest_template_aws_validation': 'PENDING_DEPLOYER_SIGN_IN',
            'live_log_read': 'PENDING_AFTER_SIMULATOR_DISCREPANCY', 'deployment_ready': False}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
