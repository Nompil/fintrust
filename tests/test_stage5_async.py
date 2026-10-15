"""Exact async qualifier scope, unchanged concurrency, and real AWS decisions."""
import hashlib
import json
from pathlib import Path
import pytest
IAM = Path('infrastructure/iam')
ARN = 'arn:aws:lambda:af-south-1:966467878406:function:fintrust-ingest-dev'
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def digest(p): return hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
def test_async_policy_is_exact_and_does_not_widen_concurrency_or_other_operations():
    base = read(IAM/'evidence/stage5-permanent-installed-policy.json')
    assert base == read(IAM/'evidence/stage5-permanent-installed-policy.json')
    statements = {s['Sid']:s for s in base['Statement']}
    assert statements['ConfigureNamedIngest']['Resource'] == ARN
    assert 'lambda:PutFunctionConcurrency' in statements['ConfigureNamedIngest']['Action']
    policy = read(IAM/'stage5-async-policy.json')
    assert len(policy['Statement']) == 2
    mutation, inspect = policy['Statement']
    assert mutation == {'Sid':'ConfigureIngestAsync','Effect':'Allow',
        'Action':['lambda:PutFunctionEventInvokeConfig','lambda:DeleteFunctionEventInvokeConfig'],
        'Resource':ARN+':$LATEST','Condition':statements['ConfigureNamedIngest']['Condition']}
    assert inspect == {'Sid':'InspectIngestAsync','Effect':'Allow',
        'Action':['lambda:GetFunctionEventInvokeConfig'],'Resource':ARN+':$LATEST',
        'Condition':{'StringEquals':{'aws:RequestedRegion':'af-south-1'}}}
    assert '*' not in json.dumps(policy)
    assert statements['LegacyTagIngestLogGroup']['Action'] == ['logs:TagLogGroup']
    for sid in ('CreateIngestLogGroup','TagIngestLogGroup'):
        c=statements[sid]['Condition']
        assert c['StringEquals']['aws:RequestTag/Project']=='FinTrust'
        assert c['StringEquals']['aws:RequestTag/Environment']=='dev'
        assert c['ForAnyValue:StringEquals']['aws:CalledVia']==['cloudformation.amazonaws.com']
def test_validation_bound_to_both_policies_and_no_live_retry_claim():
    data=read(IAM/'evidence/stage5-async-validation.json')
    assert data['candidate_sha256']==digest(IAM/'stage5-async-policy.json')
    assert data['base_sha256']==digest(IAM/'evidence/stage5-permanent-installed-policy.json')
    assert data['access_analyzer']['findings']==[]
    assert data['aws_mutations']==0
    assert data['cloudformation_retry_verified'] is False
    assert 'supplied context only' in data['limitations']
def test_capacity_and_retained_versions_are_archived_not_deleted():
    archive=read(IAM/'evidence/stage5-async-version-baseline.json')
    assert {v['VersionId'] for v in archive['versions']['Versions']}=={'v1','v2','v5','v6','v7'}
    assert archive['v2']['PolicyVersion']['IsDefaultVersion'] is True
    assert archive['v5']['PolicyVersion']['IsDefaultVersion'] is False
    assert archive['v5']['PolicyVersion']['Document']==read(IAM/'stage5-deployment-diagnostic3-policy.json')
    assert archive['v7']['PolicyVersion']['Document']==read(IAM/'evidence/stage5-permanent-installed-policy.json')
    assert archive['proposed_managed_count']==11
    assert archive['proposed_managed_count']<=archive['account_summary']['SummaryMap']['AttachedPoliciesPerRoleQuota']
    assert archive['cleanup_required_for_this_plan'] is False
    assert archive['aws_mutations']==0
    handlers=archive['regional_provider_schema']['handlers']
    assert handlers['create']['permissions']==['lambda:PutFunctionEventInvokeConfig']
    assert handlers['read']['permissions']==['lambda:GetFunctionEventInvokeConfig']
    assert handlers['delete']['permissions']==['lambda:DeleteFunctionEventInvokeConfig']
@pytest.mark.parametrize('name',
    [f'{verb}-{suffix}' for verb in ('Put','Delete','Get') for suffix in
     ('latest','other-function','other-version','other-alias','other-account','other-region-arn','wrong-region-context')]
    +[f'before-{verb}-latest' for verb in ('Put','Delete','Get')]
    +['Put-missing-calledvia','Delete-missing-calledvia','concurrency-unqualified','concurrency-qualified-denied','no-invoke'])
def test_real_aws_matching_results(name):
    case=next(c for c in read(IAM/'evidence/stage5-async-validation.json')['simulations'] if c['name']==name)
    result=case['response']['EvaluationResults'][0]
    expected='allowed' if name in ('Put-latest','Delete-latest','Get-latest','concurrency-unqualified') else 'implicitDeny'
    assert result['EvalActionName']==case['action']
    assert result['EvalResourceName']==case['resource']
    assert result['EvalDecision']==case['expected']==expected
