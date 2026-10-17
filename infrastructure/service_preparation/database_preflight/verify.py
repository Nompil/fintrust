"""Verify recorded candidate bindings offline; does not authorize AWS execution."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def verify():
    manifest = read(ROOT / 'manifest.json')
    acceptance = read(ROOT / 'aws-template-validation.json')
    assert acceptance['status'] == 'TWO_TEMPLATES_ACCEPTED_NOT_DEPLOYED'
    for name, expected in manifest['files'].items():
        assert b'\r\n' not in (ROOT / name).read_bytes()
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
        assert acceptance['templates'][name]['sha256'] == expected
    for name, expected in manifest['sources'].items():
        assert hashlib.sha256((ROOT.parents[2] / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == expected
    package = read(ROOT / 'preflight-package.manifest.json')
    checks = read(ROOT / 'pg16-verification.json')
    assert package['phase'] == 'preflight'
    assert package['linux_execution_verified'] and package['postgresql16_execution_verified']
    assert package['sha256'] == checks['artifact_sha256']
    assert checks['status'] == 'PASSED' and checks['temporary_cluster_removed']
    assert checks['tests'] == {'tests': 65, 'failures': 0, 'errors': 0, 'skipped': 0}
    assert not checks['aws_access'] and not checks['live_rds_access']
    return {'candidate_bindings': 'PASS', 'focused_tests_passed': 65,
            'linux_native_import': 'PASS', 'aws_templates': 'ACCEPTED_NOT_DEPLOYED',
            'live_database_verified': False, 'endpoint_cost_exception_required': True}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
