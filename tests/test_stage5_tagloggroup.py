"""Regression checks for the one-action legacy tagging diagnostic and AWS evidence."""
import hashlib
import json
from pathlib import Path

import pytest

IAM = Path('infrastructure/iam')
CANDIDATE = IAM / 'stage5-deployment-tagloggroup-diagnostic-policy.json'
V5 = IAM / 'stage5-deployment-diagnostic3-policy.json'
CANONICAL = IAM / 'stage5-deployment-policy.json'
PERMANENT_SNAPSHOT = IAM / 'evidence/stage5-permanent-installed-policy.json'
ARCHIVE = IAM / 'evidence/stage5-tagloggroup-version-baseline.json'
VALIDATION = IAM / 'evidence/stage5-tagloggroup-validation.json'
ARN = 'arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def historical_policy_sha256(data):
    """Reconstruct original Windows CRLF bytes; preserve all other content."""
    return hashlib.sha256(data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')).hexdigest()


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


def test_archived_v2_and_v5_controls_remain_preserved():
    current = read(PERMANENT_SNAPSHOT)
    assert current['Statement'][:-1] == read(ARCHIVE)['v2']['PolicyVersion']['Document']['Statement']
    assert historical_policy_sha256(V5.read_bytes()) == 'bc51f45a07560c6a2f11adebb6db721a1303eff62b871d0d3a6aa7f69b257c48'


def test_proposed_v3_cleanup_is_nondefault_and_archived_before_any_deletion():
    archive = read(ARCHIVE)
    assert archive['policy_arn'] == 'arn:aws:iam::966467878406:policy/FinTrustStage5Deployment'
    assert len(archive['versions']['Versions']) == 5
    assert archive['v2']['PolicyVersion']['IsDefaultVersion'] is True
    assert archive['v3']['PolicyVersion']['IsDefaultVersion'] is False
    assert archive['v3']['PolicyVersion']['Document'] == read(IAM / 'stage5-deployment-diagnostic-policy.json')
    current = read(PERMANENT_SNAPSHOT)
    assert archive['v2']['PolicyVersion']['Document'] == {**current, 'Statement': current['Statement'][:-1]}
    assert archive['v5']['PolicyVersion']['Document'] == read(V5)


def test_validation_evidence_matches_current_candidate_and_preserves_simulator_limits():
    data = read(VALIDATION)
    assert data['candidate_sha256'] == historical_policy_sha256(CANDIDATE.read_bytes())
    assert data['v5_sha256'] == historical_policy_sha256(V5.read_bytes())
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


@pytest.mark.parametrize('path,expected', [
    (V5, 'bc51f45a07560c6a2f11adebb6db721a1303eff62b871d0d3a6aa7f69b257c48'),
    (CANDIDATE, '7ccef683b4e4da11aa85c9c1fdc25fd8216b1dbd5eddc4e3aea06a56641e06e6'),
])
def test_historical_policy_integrity_is_identical_for_lf_and_crlf(path, expected):
    lf = path.read_bytes().replace(b'\r\n', b'\n')
    crlf = lf.replace(b'\n', b'\r\n')
    assert historical_policy_sha256(lf) == historical_policy_sha256(crlf) == expected


@pytest.mark.parametrize('path', [V5, CANDIDATE])
@pytest.mark.parametrize('original,replacement', [
    (b'logs:CreateLogGroup', b'logs:DeleteLogGroup'),
    (b'966467878406', b'111111111111'),
    (b'af-south-1', b'us-east-1'),
    (b'"Version": "2012-10-17"', b'"Version" : "2012-10-17"'),
])
def test_newline_normalization_cannot_hide_policy_or_formatting_changes(path, original, replacement):
    data = path.read_bytes()
    assert original in data
    changed = data.replace(original, replacement, 1)
    assert historical_policy_sha256(changed) != historical_policy_sha256(data)


def test_new_policy_version_does_not_replace_historical_validation_binding():
    evidence = read(VALIDATION)
    # Historical simulations concern this immutable diagnostic, not canonical v7.
    assert evidence['candidate_sha256'] == historical_policy_sha256(CANDIDATE.read_bytes())
    assert evidence['candidate_sha256'] != historical_policy_sha256(CANONICAL.read_bytes())
    assert read(ARCHIVE)['v5']['PolicyVersion']['Document'] == read(V5)
