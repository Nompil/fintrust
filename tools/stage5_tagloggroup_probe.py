"""Approved one-shot direct tagged-create probe; caller must clean up and restore v2.

This module has no import-time AWS action. It refuses execution without the
explicit flag and a verified temporary policy version. Credentials never leave
process memory or appear in evidence. No CloudFormation API is used.
"""
import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

AWS = r'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
REGION = 'af-south-1'
POLICY = 'arn:aws:iam::966467878406:policy/FinTrustStage5Deployment'
GROUP = '/aws/lambda/fintrust-ingest-dev'


def cli(arguments, profile):
    env = os.environ.copy()
    env['AWS_MAX_ATTEMPTS'] = '1'
    process = subprocess.run([AWS, *arguments, '--profile', profile],
                             capture_output=True, text=True, input='', timeout=45, env=env)
    if process.returncode:
        raise RuntimeError('AWS preflight/credential command failed; no creation attempted')
    return json.loads(process.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--approved-direct-create', action='store_true')
    parser.add_argument('--expected-policy-version', required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    if not args.approved_direct_create or args.expected_policy_version in ('v2', 'v5'):
        parser.error('Explicit approval flag and a new diagnostic version are required')
    if args.evidence.exists():
        parser.error('Evidence path already exists; preserve earlier attempts')
    options = ['--region', REGION, '--no-cli-pager', '--output', 'json',
               '--cli-connect-timeout', '10', '--cli-read-timeout', '10']
    live = cli(['iam', 'get-policy-version', '--policy-arn', POLICY,
                '--version-id', args.expected_policy_version, *options], 'fintrust-inventory')
    candidate = json.loads(Path('infrastructure/iam/stage5-deployment-tagloggroup-diagnostic-policy.json').read_text(encoding='utf-8-sig'))
    if not live['PolicyVersion']['IsDefaultVersion'] or live['PolicyVersion']['Document'] != candidate:
        raise RuntimeError('Temporary default does not match reviewed candidate; no creation attempted')
    groups = cli(['logs', 'describe-log-groups', '--log-group-name-prefix', GROUP, *options], 'fintrust-inventory')
    if any(g['logGroupName'] == GROUP for g in groups['logGroups']):
        raise RuntimeError('Group already exists; no creation or cleanup authorized by this probe')
    credentials = cli(['configure', 'export-credentials', '--format', 'process'], 'fintrust-deployer-role')
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
    session = boto3.Session(aws_access_key_id=credentials['AccessKeyId'],
                            aws_secret_access_key=credentials['SecretAccessKey'],
                            aws_session_token=credentials['SessionToken'], region_name=REGION)
    config = Config(retries={'total_max_attempts': 1}, connect_timeout=10, read_timeout=15)
    identity = session.client('sts', config=config).get_caller_identity()
    if identity['Account'] != '966467878406' or not identity['Arn'].startswith('arn:aws:sts::966467878406:assumed-role/fintrust-deployer-role/'):
        raise RuntimeError('Wrong caller; no creation attempted')
    logs = session.client('logs', config=config)
    report = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'creation_attempts': 1,
              'caller': {k: identity[k] for k in ('Account', 'Arn', 'UserId')},
              'group': GROUP, 'tags': {'Project': 'FinTrust', 'Environment': 'dev'},
              'policy_version': args.expected_policy_version}
    try:
        response = logs.create_log_group(logGroupName=GROUP, tags=report['tags'])
        report.update(success=True, response=response)
    except ClientError as error:
        report.update(success=False, error=str(error), response=error.response)
    except Exception as error:
        report.update(success=False, outcome_unknown=True, error=str(error))
    finally:
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
