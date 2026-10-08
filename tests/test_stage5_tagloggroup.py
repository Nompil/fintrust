"""Regression checks for the one-action legacy tagging diagnostic and AWS evidence."""
import hashlib
import json
from pathlib import Path

import pytest

IAM = Path('infrastructure/iam')
CANDIDATE = IAM / 'stage5-deployment-tagloggroup-diagnostic-policy.json'
V5 = IAM / 'stage5-deployment-diagnostic3-policy.json'
CANONICAL = IAM / 'stage5-deployment-policy.json'
ARCHIVE = IAM / 'evidence/stage5-tagloggroup-version-baseline.json'
VALIDATION = IAM / 'evidence/stage5-tagloggroup-validation.json'
ARN = 'arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def test_candidate_adds_exactly_one_legacy_grant_and_preserves_all_v5_statements():
    candidate, original = read(CANDIDATE), read(V5)
    assert candidate['Version'] == original['Version']
    assert candidate['Statement'][:-1] == original['Statement']
    assert candidate['Statement'][-1] == {
        'Sid': 'LegacyTagIngestLogGroup', 'Effect': 'Allow',
        'Action': ['logs:TagLogGroup'], 'Resource': ARN + ':*',
        'Condition': {'StringEquals': {'aws:RequestedRegion': 'af-south-1'}}}
    before = {a for s in original['Statement'] for a in s['Action']}
    after = {a for s in candidate['Statement'] for a in s['Action']}
    assert after - before == {'logs:TagLogGroup'}
    assert len(json.dumps(candidate, separators=(',', ':'))) <= 6144


def test_canonical_v2_and_v5_control_bytes_remain_unchanged():
    assert hashlib.sha256(CANONICAL.read_bytes()).hexdigest() == 'cfe1844fa9119fed207ef1d903a71e09dc668814fb1ab9478ea235cc0ca6cbf5'
    assert hashlib.sha256(V5.read_bytes()).hexdigest() == 'bc51f45a07560c6a2f11adebb6db721a1303eff62b871d0d3a6aa7f69b257c48'


def test_proposed_v3_cleanup_is_nondefault_and_archived_before_any_deletion():
    archive = read(ARCHIVE)
    assert archive['policy_arn'] == 'arn:aws:iam::966467878406:policy/FinTrustStage5Deployment'
    assert len(archive['versions']['Versions']) == 5
    assert archive['v2']['PolicyVersion']['IsDefaultVersion'] is True
    assert archive['v3']['PolicyVersion']['IsDefaultVersion'] is False
    assert archive['v3']['PolicyVersion']['Document'] == read(IAM / 'stage5-deployment-diagnostic-policy.json')
    assert archive['v2']['PolicyVersion']['Document'] == read(CANONICAL)
    assert archive['v5']['PolicyVersion']['Document'] == read(V5)


def test_validation_evidence_matches_current_candidate_and_preserves_simulator_limits():
    data = read(VALIDATION)
    assert data['candidate_sha256'] == hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    assert data['v5_sha256'] == hashlib.sha256(V5.read_bytes()).hexdigest()
    assert data['access_analyzer']['findings'] == []
    assert data['aws_mutations'] == 0
    assert 'no live tagged-create success' in data['limitations']


@pytest.mark.parametrize('name,decision', [
    ('v5-no-legacy', 'implicitDeny'), ('candidate-exact-legacy', 'allowed'),
    ('candidate-other-group', 'implicitDeny'), ('candidate-other-region', 'implicitDeny'),
    ('candidate-other-account', 'implicitDeny'), ('candidate-unsuffixed', 'implicitDeny'),
    ('candidate-no-untag', 'implicitDeny'), ('candidate-no-delete', 'implicitDeny'),
    ('candidate-create-preserved', 'allowed'), ('candidate-tagresource-preserved', 'allowed'),
    ('candidate-create-wrong-tag', 'implicitDeny'),
])
def test_recorded_aws_simulations_prove_the_exact_scoped_grants(name, decision):
    # Recorded real AWS simulations, bound to the candidate digest above; not a local IAM emulator.
    case = next(c for c in read(VALIDATION)['simulations'] if c['name'] == name)
    entry = case['response']['EvaluationResults'][0]
    assert entry['EvalActionName'] == case['action']
    assert entry['EvalResourceName'] == case['resource']
    assert entry['EvalDecision'] == case['expected'] == decision

@pytest.mark.parametrize('version,approved', [('v6', False), ('v2', True), ('v5', True)])
def test_live_probe_refuses_missing_approval_or_control_versions_before_aws(tmp_path, version, approved):
    import subprocess
    import sys
    evidence = tmp_path / 'must-not-be-created.json'
    command = [sys.executable, 'tools/stage5_tagloggroup_probe.py',
               '--expected-policy-version', version, '--evidence', str(evidence)]
    if approved:
        command.append('--approved-direct-create')
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert 'Explicit approval flag' in result.stderr
    assert not evidence.exists()
