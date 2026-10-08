"""Permanent policy scope and recorded AWS regression evidence."""
import hashlib
import json
from pathlib import Path
import pytest

IAM = Path('infrastructure/iam')
POLICY = IAM / 'stage5-deployment-policy.json'
BASELINE = IAM / 'evidence/stage5-tagloggroup-version-baseline.json'
VALIDATION = IAM / 'evidence/stage5-permanent-validation.json'
VERSIONS = IAM / 'evidence/stage5-permanent-version-baseline.json'
ARN = 'arn:aws:logs:af-south-1:966467878406:log-group:/aws/lambda/fintrust-ingest-dev'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def test_permanent_fix_is_complete_v2_plus_only_proven_legacy_permission():
    baseline = read(BASELINE)['v2']['PolicyVersion']['Document']
    candidate = read(POLICY)
    assert {**candidate, 'Statement': candidate['Statement'][:-1]} == baseline
    assert candidate['Statement'][-1] == {
        'Sid': 'LegacyTagIngestLogGroup', 'Effect': 'Allow',
        'Action': ['logs:TagLogGroup'], 'Resource': ARN + ':*',
        'Condition': {'StringEquals': {'aws:RequestedRegion': 'af-south-1'}}}
    old_actions = {a for s in baseline['Statement'] for a in s['Action']}
    new_actions = {a for s in candidate['Statement'] for a in s['Action']}
    assert new_actions - old_actions == {'logs:TagLogGroup'}
    assert len(json.dumps(candidate, separators=(',', ':'))) <= 6144

def test_diagnostic_relaxations_are_not_promoted_and_no_logs_wildcard_added():
    statements = {s['Sid']: s for s in read(POLICY)['Statement']}
    create = statements['CreateIngestLogGroup']
    tag = statements['TagIngestLogGroup']
    assert create['Condition'] == tag['Condition'] == {
        'StringEquals': {'aws:RequestedRegion': 'af-south-1',
                         'aws:RequestTag/Project': 'FinTrust', 'aws:RequestTag/Environment': 'dev'},
        'ForAnyValue:StringEquals': {'aws:CalledVia': ['cloudformation.amazonaws.com']}}
    assert create['Resource'] == ARN + ':*'
    assert tag['Action'] == ['logs:TagResource'] and tag['Resource'] == ARN
    for statement in statements.values():
        if any(action.startswith('logs:') for action in statement['Action']):
            if statement['Sid'] == 'InspectIngestLogGroups':
                assert statement['Action'] == ['logs:DescribeLogGroups']
            else:
                assert statement['Resource'] in (ARN, ARN + ':*')
                assert not any('*' in action for action in statement['Action'])

def test_version_cleanup_preserves_v2_v5_v6_and_archives_only_proposed_v4():
    evidence = read(VERSIONS)
    assert evidence['proposed_cleanup_version'] == 'v4'
    assert len(evidence['versions']['Versions']) == 5
    assert evidence['v2']['PolicyVersion']['IsDefaultVersion'] is True
    assert evidence['v4']['PolicyVersion']['IsDefaultVersion'] is False
    assert evidence['v4']['PolicyVersion']['Document'] == read(IAM / 'stage5-deployment-diagnostic2-policy.json')
    assert evidence['v5']['PolicyVersion']['Document'] == read(IAM / 'stage5-deployment-diagnostic3-policy.json')
    assert evidence['v6']['PolicyVersion']['Document'] == read(IAM / 'stage5-deployment-tagloggroup-diagnostic-policy.json')
    assert evidence['v2']['PolicyVersion']['Document'] == read(BASELINE)['v2']['PolicyVersion']['Document']
    assert evidence['aws_mutations'] == 0

def test_validation_is_bound_to_permanent_policy_and_keeps_live_proof_separate():
    data = read(VALIDATION)
    assert data['candidate_sha256'] == hashlib.sha256(POLICY.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    assert data['access_analyzer']['findings'] == []
    assert data['aws_mutations'] == 0
    assert data['candidate_hash_normalization'] == 'LF line endings'
    assert data['live_diagnostic']['policy_version'] == 'v6'
    assert data['live_diagnostic']['success'] is True
    assert data['live_diagnostic']['response']['ResponseMetadata']['RequestId'] == 'e641540c-a094-42b4-9411-b06bfeda7e8b'
    assert data['live_diagnostic_cleanup']['logGroups'] == []
    assert data['cloudformation_retry_verified'] is False

@pytest.mark.parametrize('name,expected', [
    ('v2-no-legacy', 'implicitDeny'), ('legacy-exact', 'allowed'),
    ('legacy-with-full-context', 'allowed'), ('legacy-wrong-group', 'implicitDeny'),
    ('legacy-wrong-region-context', 'implicitDeny'), ('legacy-wrong-region-arn', 'implicitDeny'),
    ('legacy-wrong-account', 'implicitDeny'), ('legacy-unsuffixed', 'implicitDeny'),
    ('legacy-no-delete', 'implicitDeny'), ('legacy-no-untag', 'implicitDeny'),
    ('create-full-context', 'allowed'), ('create-without-calledvia', 'implicitDeny'),
    ('create-wrong-project', 'implicitDeny'), ('create-without-tags', 'implicitDeny'),
    ('modern-full-context', 'allowed'), ('modern-without-calledvia', 'implicitDeny'),
    ('modern-without-tags', 'implicitDeny'), ('legacy-direct-retag-risk', 'allowed'),
])
def test_recorded_real_aws_decisions(name, expected):
    case = next(c for c in read(VALIDATION)['simulations'] if c['name'] == name)
    result = case['response']['EvaluationResults'][0]
    assert result['EvalActionName'] == case['action']
    assert result['EvalResourceName'] == case['resource']
    assert result['EvalDecision'] == case['expected'] == expected
