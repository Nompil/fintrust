# FinTrust deployment identity

Review proposal only. No identities, policies or login profiles have been created.
Account: `966467878406`. Application region: `af-south-1`. Environment: `dev` only.

## Identity boundary

Keep `fintrust-inventory` read-only. Use a separate human IAM user,
`fintrust-deployer`, with console password, MFA and no access keys. It assumes
`fintrust-deployer-role` for a maximum one-hour deployment session. The user gets
no direct infrastructure permissions. Do not attach AdministratorAccess or
PowerUserAccess to either identity.

An authorized account administrator creates the user, enrolls MFA with the owner,
creates the role and installs the reviewed stage policy. The deployer cannot
change its own trust, permissions or boundary, create users/keys, or administer
billing. Stage 0 budget configuration belongs to the billing administrator.
Neither task is assigned to the inventory user. Root is not the deployment identity.

Attach AWS `SignInLocalDevelopmentAccess` to the new human user for browser-based
temporary CLI authentication, plus the user policy below. This is an authentication
permission, not deployment access. Use a separate `fintrust-deployer-login` profile;
never overwrite `fintrust-inventory` or export temporary credentials into the repo.
See [AWS CLI console login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html).

## Role trust policy

The account principal delegates only to the exact user ARN in the condition. It
does not permit other account users or the account root to assume this role.
An absent or false MFA context fails closed.

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "NamedHumanWithMfa",
    "Effect": "Allow",
    "Principal": {"AWS": "arn:aws:iam::966467878406:root"},
    "Action": "sts:AssumeRole",
    "Condition": {
      "ArnEquals": {"aws:PrincipalArn": "arn:aws:iam::966467878406:user/fintrust-deployer"},
      "Bool": {"aws:MultiFactorAuthPresent": "true"}
    }
  }]
}
```

## User permissions policy

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "AssumeOnlyFinTrustDeployer",
    "Effect": "Allow",
    "Action": "sts:AssumeRole",
    "Resource": "arn:aws:iam::966467878406:role/fintrust-deployer-role",
    "Condition": {"Bool": {"aws:MultiFactorAuthPresent": "true"}}
  }]
}
```

MFA enrollment and password recovery remain administrator-assisted for this small
assessment; no user-management wildcard is needed. If self-service password/MFA
management is desired later, review a separate own-user-only policy.

## Temporary session acceptance

After Stage 0 approval, authenticate with the new user's MFA browser session, then
use an assume-role profile referencing `fintrust-deployer-login`, the exact role
ARN and `duration_seconds = 3600`. Before installing infrastructure write grants,
prove the role session resolves to account `966467878406` and
`assumed-role/fintrust-deployer-role/…`. Also prove a session lacking MFA cannot
assume it. The inventory principal must be unable to assume it.

Browser login success alone does not prove STS receives the MFA condition context.
This login-to-role combination has not been executed here. If it fails, inspect
the authentication context; do not remove the MFA condition or create access keys
as a workaround. A reviewed MFA-backed role console session with temporary CLI
login is an alternative to test. See [role profiles](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-role.html)
and [MFA condition semantics](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-multifactorauthpresent).

## Stage 1 role permission specification

This is the exact action inventory and scoping design for the proposed network
stage, not an attached or AWS-validated policy. Render its final statements with
the network-only template: resource types, create-time tag support and dependent
resource authorizations must be checked together. Do not use `ec2:*`, `rds:*`,
`iam:*` or a blanket infrastructure administrator policy to resolve a denial.

Use CloudFormation with the assuming role's temporary credentials; no persistent
CloudFormation service role or `iam:PassRole` is needed for Stage 1. Permit only
the `fintrust-network-dev` stack. Require `Project=FinTrust`, `Environment=dev`
tags on managed resources and keep those ownership tags immutable. The default
VPC and all unrelated resources must fail the mutation authorization checks.

| Actions | Scope and reason |
|---|---|
| `cloudformation:ValidateTemplate`, `cloudformation:GetTemplateSummary` | `*` where required by the API; validate the local network template, with `aws:RequestedRegion=af-south-1` |
| `cloudformation:CreateChangeSet`, `cloudformation:DescribeChangeSet`, `cloudformation:ExecuteChangeSet`, `cloudformation:DeleteChangeSet`, `cloudformation:DescribeStacks`, `cloudformation:DescribeStackEvents`, `cloudformation:DescribeStackResources`, `cloudformation:ListStackResources`, `cloudformation:GetTemplate`, `cloudformation:DeleteStack`, `cloudformation:ContinueUpdateRollback` | Stack ARN `arn:aws:cloudformation:af-south-1:966467878406:stack/fintrust-network-dev/*`; exact change-set ARNs if required by that operation's authorization model. Create/update via reviewed change sets; deletion/rollback permissions support approved cleanup and recovery |
| `ec2:DescribeVpcs`, `ec2:DescribeVpcAttribute`, `ec2:DescribeSubnets`, `ec2:DescribeRouteTables`, `ec2:DescribeSecurityGroups`, `ec2:DescribeSecurityGroupRules`, `ec2:DescribeVpcEndpoints`, `ec2:DescribeVpcEndpointServices`, `ec2:DescribePrefixLists`, `ec2:DescribeAvailabilityZones`, `ec2:DescribeTags`, `ec2:DescribeNetworkInterfaces` | `*`, region condition; CloudFormation stabilization, identifiers and cleanup diagnostics. No reads of application data |
| `ec2:CreateVpc`, `ec2:CreateSubnet`, `ec2:CreateRouteTable`, `ec2:CreateSecurityGroup`, `ec2:CreateVpcEndpoint` | Respective regional/account resource types with required request ownership tags; parent VPC/subnet/route-table references must be FinTrust-owned. Endpoint type must be `Gateway`, service names only regional S3 and DynamoDB |
| `ec2:CreateTags` | Only creation-time tagging for the allowed create operations (`ec2:CreateAction`), required ownership tags. No general permission to retag unrelated resources into scope |
| `ec2:ModifyVpcAttribute`, `ec2:ModifySubnetAttribute`, `ec2:AssociateRouteTable`, `ec2:DisassociateRouteTable`, `ec2:ReplaceRouteTableAssociation` | FinTrust-owned VPC/subnet/route-table resources only; DNS, no-public-IP setting and private route associations |
| `ec2:AuthorizeSecurityGroupIngress`, `ec2:AuthorizeSecurityGroupEgress`, `ec2:RevokeSecurityGroupIngress`, `ec2:RevokeSecurityGroupEgress` | FinTrust-owned groups only, including dependent source/destination group authorization; PostgreSQL and gateway-service egress rules |
| `ec2:ModifyVpcEndpoint` | FinTrust-owned gateway endpoints only; reviewed policy/route association updates |
| `ec2:DeleteVpcEndpoints`, `ec2:DeleteSecurityGroup`, `ec2:DeleteRouteTable`, `ec2:DeleteSubnet`, `ec2:DeleteVpc` | FinTrust-owned resources only, for rollback and separately approved teardown |
| `rds:CreateDBSubnetGroup`, `rds:ModifyDBSubnetGroup`, `rds:DeleteDBSubnetGroup`, `rds:AddTagsToResource`, `rds:ListTagsForResource` | `arn:aws:rds:af-south-1:966467878406:subgrp:fintrust-db-dev`; subnet selection limited to the new VPC in the template. No database instance actions |
| `rds:DescribeDBSubnetGroups` | `*` if required; region condition, CloudFormation read/stabilization |

Constrain all regional actions with `aws:RequestedRegion=af-south-1`. Prefer
CloudFormation-forwarded service writes (`aws:CalledVia` containing
`cloudformation.amazonaws.com`) where supported; validate the real call context
before relying on that condition. No service-role bypass is granted.

Do not grant `CreateRoute`: Stage 1 has only the automatic VPC-local route and
gateway endpoint routes. No IGW, NAT, public IP allocation, EC2 instance, interface
endpoint, RDS instance, KMS, S3, DynamoDB or application mutation is authorized.
Scope an explicit deny to NAT/IGW/interface endpoint creation in the final role
boundary as additional protection; test condition keys against the exact API.

An IAM policy does not by itself validate subnet CIDRs or safe ingress contents.
Review the change set and network invariants before execution. Validate create,
update, rollback and delete action/resource combinations, plus negative cases for
the default VPC, other regions, missing tags, fixed public DB ingress and paid
resource types. No IAM simulator or Access Analyzer account call was run here.

## Later stage grants: withheld until their resources are reviewed

| Stage | Required permission scope and purpose |
|---|---|
| 0 | Administrator: named user/role/trust/policy and MFA setup; billing administrator: named budget, notifications, billing preference, billing SNS topic and alarm. These are not deployer-role grants |
| 2 | KMS create/tag/key-policy/alias for one FinTrust key; subsequent key operations restricted to its ARN. S3 create, encryption, ownership/public-access blocks, versioning, lifecycle and TLS policy for the three exact FinTrust buckets. Key administration is a separate reviewed privilege, never unrestricted `PutKeyPolicy` on other keys |
| 3 | RDS create/describe/modify/backup for exact `fintrust-ledger-dev`, its parameter/subnet group and key grants constrained to RDS. Bootstrap secret and temporary runner permissions separately approved; no routine database administrator access on application roles |
| 4 | DynamoDB create/describe/configure the exact risk table/stream; SQS create/get/configure exact transaction FIFO, FIFO DLQ and three asynchronous failure queues |
| 5–9 | Lambda create/update/configure exact five function ARNs; `iam:PassRole` only the matching pre-reviewed five execution roles with `iam:PassedToService=lambda.amazonaws.com`; log groups, S3 notification, mapping, API and schedule rights only for their named resources. IAM role creation/permissions handled by administrator or a separate bounded provisioning policy, never unrestricted deployment IAM |
| 7 | SES verify/get the approved sender/recipient identities only; email sending belongs to the scoped alert execution role and separately approved tests |
| 8 | Separate demo caller policy: `execute-api:Invoke` only approved GET paths/stage; not the deployment role and not browser-embedded AWS credentials |
| 10 | Exact FinTrust alarms, SNS topic/subscriptions and log retention/filter settings; tracing update and execution-role X-Ray grants only after review. No tracing/monitoring wildcard administration |

Later-stage action-level JSON must follow the corresponding split template and
actual resource ARNs. It is intentionally not pre-granted for all services now.
Do not change the existing application execution-role renderer during this gate.

## Approval boundary

First approve Stage 0 identity/MFA setup and billing safeguards, including a real
recipient address and the budget currency conversion. Before Stage 1 writes,
review the network-only template and rendered stage policy together. This document
does not authorize creation, policy attachment, login reconfiguration or deployment.
