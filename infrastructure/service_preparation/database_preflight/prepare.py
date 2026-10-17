"""Offline, preflight-only shared-capacity candidate. No AWS calls."""
import hashlib
import json
from pathlib import Path

from infrastructure import migration

ROOT = Path(__file__).resolve().parent


def template(reuse_existing_logs=False):
    doc = migration.runner_template('preflight')
    doc['Description'] = ('REVIEW ONLY: fixed read-only database preflight; disabled by default; '
                          'one qualified synchronous request; shared mode has no individual concurrency cap')
    doc['Parameters']['EnableReadOnlyPreflight'] = {
        'Type': 'String', 'Default': 'false', 'AllowedValues': ['false', 'true']}
    doc['Conditions'] = {'PreflightEnabled': {'Fn::Equals': [
        {'Ref': 'EnableReadOnlyPreflight'}, 'true']}}
    doc['Resources']['Runner']['Properties']['ReservedConcurrentExecutions'] = {
        'Fn::If': ['PreflightEnabled', {'Ref': 'AWS::NoValue'}, 0]}
    if reuse_existing_logs:
        del doc['Resources']['RunnerLogs']
        del doc['Resources']['Runner']['DependsOn']
    return doc


def render():
    path = ROOT / 'runner-shared-readonly.json'
    path.write_text(json.dumps(template(), indent=2) + '\n', encoding='utf-8', newline='\n')
    existing_logs = ROOT / 'runner-existing-logs-readonly.json'
    existing_logs.write_text(json.dumps(template(reuse_existing_logs=True), indent=2) + '\n',
                             encoding='utf-8', newline='\n')
    network = ROOT / 'network-review.json'
    network.write_text(json.dumps(migration.network_template(), indent=2) + '\n', encoding='utf-8', newline='\n')
    sources = ('infrastructure/migration.py', 'backend/migration_runner/preflight_entry.py',
               'backend/migration_runner/common.py', 'backend/migration_runner/admin.py',
               'backend/migration_runner/release1_preflight.py', 'sql/preflight/002_release1_catalog.sql')
    repo = ROOT.parents[2]
    manifest = {'status': 'OFFLINE_CANDIDATE_NOT_DEPLOYED', 'aws_changes': False,
                'sql_executed': False, 'phase': 'preflight', 'per_function_cap_in_shared_mode': False,
                'endpoint_cost_exception_required': True,
                'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (path, existing_logs, network)},
                'sources': {p: hashlib.sha256((repo / p).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in sources}}
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    return manifest


if __name__ == '__main__':
    print(json.dumps(render(), indent=2))
