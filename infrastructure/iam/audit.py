"""Read deployed role policies, including managed policies and trust, without mutations."""
import argparse
import json
import boto3


def inspect_role(iam, name):
    role = iam.get_role(RoleName=name)['Role']
    result = {'role': role, 'inline': {}, 'managed': {}}
    for page in iam.get_paginator('list_role_policies').paginate(RoleName=name):
        for policy in page['PolicyNames']:
            result['inline'][policy] = iam.get_role_policy(RoleName=name, PolicyName=policy)['PolicyDocument']
    for page in iam.get_paginator('list_attached_role_policies').paginate(RoleName=name):
        for policy in page['AttachedPolicies']:
            arn = policy['PolicyArn']
            version = iam.get_policy(PolicyArn=arn)['Policy']['DefaultVersionId']
            result['managed'][arn] = iam.get_policy_version(PolicyArn=arn, VersionId=version)['PolicyVersion']['Document']
    result['tags'] = [tag for page in iam.get_paginator('list_role_tags').paginate(RoleName=name) for tag in page['Tags']]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('roles', nargs='+')
    parser.add_argument('--rest-api-id')
    args = parser.parse_args()
    iam = boto3.client('iam')
    result = {'roles': [inspect_role(iam, name) for name in args.roles]}
    if args.rest_api_id:
        result['api'] = boto3.client('apigateway').get_rest_api(restApiId=args.rest_api_id)
    print(json.dumps(result, default=str, indent=2))


if __name__ == '__main__':
    main()
