# FinTrust deployment identity

Stage 0 identity configuration verified from the saved read-only evidence in
`build/stage0/`. Stage 1 permissions below are proposals only and are not attached.
The interrupted `verify.py` completed its metadata reads successfully; its script
and raw evidence remain ignored. No partial tracked edit needed reconstruction.
Account: `966467878406`. Application region: `af-south-1`. Environment: `dev` only.

## Verified Stage 0 state

| Check | Evidence and result |
|---|---|
| Inventory identity | Account `966467878406`, `user/fintrust-inventory`; current STS check matches. Saved IAM evidence has ReadOnlyAccess and SignInLocalDevelopmentAccess, no inline policies or groups; no infrastructure write policy found |
| Deployer identity | Saved STS result is `user/fintrust_deployer`; zero access keys, one MFA device, no groups |
| Deployer permissions | SignInLocalDevelopmentAccess plus only inline `AssumeFinTrustDeployer`; the inline policy allows MFA-backed AssumeRole to the exact role ARN below |
| Role trust | Exact underscore username in `aws:PrincipalArn`, MFA true, one-hour maximum session |
| Role permissions | Both attached and inline role-policy lists are empty; no deployment grant installed |
| Live role assumption | Owner reports successful STS assumption. It was not repeated; the stored role metadata alone does not prove that live session or a negative MFA test |
| Budget | Saved successful reads confirm `FinTrust-Monthly-Budget`, fixed USD 10, MONTHLY/COST, no service filter, actual 50/80/100 and forecast 100, one email subscriber per notification. Recipient values stay in ignored evidence |
| Infrastructure | The completed inventory found no FinTrust application infrastructure; no later infrastructure write was performed here. This is not a repeated full inventory |

Scope: identity-policy configuration is verified, not an exhaustive proof of every
resource policy/SCP/session combination. ReadOnlyAccess is broad metadata/data
read access; it is not restricted to FinTrust. The local-development sign-in
policy authorizes OAuth credential issuance, not infrastructure changes.

Mismatches: the old design used a hyphen in the username; the trust correctly uses
`fintrust_deployer`. The live role description still mentions the old hyphenated
name, a cosmetic discrepancy left untouched. Budget creation is complete; the
older proposed name `fintrust-assessment-monthly` is superseded. The returned budget
uses UnblendedCost but does not establish that credits/refunds are excluded from
its cost measure. Confirm gross-usage visibility before paid stages; do not treat
zero displayed spend as zero credit consumption. The separate billing alarm/SNS
proposal is not verified or created. Email configuration does not prove delivery.
The existing Zero-Spend Budget was not modified.

## Identity boundary

Keep `fintrust-inventory` read-only. Use a separate human IAM user,
`fintrust_deployer`, with console password, MFA and no access keys. It assumes
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
      "ArnEquals": {"aws:PrincipalArn": "arn:aws:iam::966467878406:user/fintrust_deployer"},
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
The owner reports this login-to-role combination succeeded. If a later check fails, inspect
the authentication context; do not remove the MFA condition or create access keys
as a workaround. A reviewed MFA-backed role console session with temporary CLI
login is an alternative to test. See [role profiles](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-role.html)
and [MFA condition semantics](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-multifactorauthpresent).

## Exact proposed Stage 1 policy bundle

Review these three JSON documents together for `fintrust-deployer-role`:

- [CloudFormation control](stage1-cloudformation-policy.json)
- [EC2 network operations](stage1-network-policy.json)
- [Named DB subnet group](stage1-db-subnet-policy.json)

They are intended as three **inline role policies**, not three managed policies:
the network document exceeds the managed-policy 6,144-character limit. Their
combined non-whitespace JSON length is **10,055**, below the role's aggregate
10,240-character inline limit while it has no other inline policies. Re-evaluate
that limit and replace/split the grants before later stages; do not append blindly.
No policy has been attached, and this is not an IAM permissions boundary.

All allows require `aws:RequestedRegion=af-south-1`. Service writes additionally
require `aws:CalledVia` containing `cloudformation.amazonaws.com`: use the caller's
temporary role credentials, no persistent service role and no `iam:PassRole`.
Creation requires `Project=FinTrust` and `Environment=dev` request tags. Existing
EC2 parent resources and mutations require the same resource tags. EC2 tagging is
creation-only (`ec2:CreateAction`), so unrelated resources cannot be retagged into
scope through these grants. RDS tagging is restricted to the exact subnet group
and both approved ownership values; tag removal is not granted.

In this table, **EC2 ARN** means
`arn:aws:ec2:af-south-1:966467878406:<type>/*` with the tag conditions above;
**stack ARN** means `arn:aws:cloudformation:af-south-1:966467878406:stack/fintrust-network-dev/*`;
**DB subnet ARN** means `arn:aws:rds:af-south-1:966467878406:subgrp:fintrust-db-dev`.
The JSON is authoritative for each statement and condition.

| Actions | Resource / why needed / wildcard requirement |
|---|---|
| `cloudformation:ValidateTemplate`, `cloudformation:GetTemplateSummary` | `*` for validation/summary of a local template before a stack exists; regional only |
| `cloudformation:CreateChangeSet` | Stack ARN only; prepare a reviewable change. Require `fintrust-network-*` change-set name, ownership tags and a nonempty `cloudformation:ResourceTypes` subset matching the eight template types. No import or service-role ARN |
| `cloudformation:DescribeChangeSet`, `cloudformation:ExecuteChangeSet`, `cloudformation:DeleteChangeSet` | Stack ARN and change-set-name prefix; inspect, later execute or discard the reviewed change. These actions authorize against stack resources, not a guessed change-set ARN |
| `cloudformation:DescribeStacks`, `cloudformation:DescribeStackEvents`, `cloudformation:DescribeStackResources`, `cloudformation:ListStackResources`, `cloudformation:GetTemplate` | Stack ARN; named-stack status/resources/template evidence. No account-wide ListStacks |
| `cloudformation:DeleteStack`, `cloudformation:ContinueUpdateRollback` | Stack ARN; separately approved cleanup/recovery, no service-role override. Neither is executed in this task |
| `ec2:DescribeVpcs`, `ec2:DescribeSubnets`, `ec2:DescribeRouteTables`, `ec2:DescribeSecurityGroups`, `ec2:DescribeSecurityGroupRules`, `ec2:DescribeVpcEndpoints`, `ec2:DescribeVpcEndpointServices`, `ec2:DescribePrefixLists`, `ec2:DescribeAvailabilityZones`, `ec2:DescribeTags`, `ec2:DescribeNetworkInterfaces` | `*` required for these EC2 describe APIs; regional topology, CloudFormation stabilization and cleanup diagnostics |
| `ec2:DescribeVpcAttribute` | Owned VPC ARN; read DNS settings. This API supports resource scoping, so no global resource wildcard |
| `ec2:CreateVpc` | New VPC ARN with request tags; dedicated VPC. No IPAM or IPv6-pool authorization |
| `ec2:CreateSubnet`, `ec2:CreateRouteTable`, `ec2:CreateSecurityGroup` | Respective new EC2 ARNs with request tags **and** owned parent VPC ARN in separate statements; four private subnets, two route tables and two SGs |
| `ec2:CreateVpcEndpoint` | New endpoint ARN with request tags and exact regional S3/DynamoDB service names; owned parent VPC and route-table ARNs. Explicit denial of subnet/SG attachment authorization, used by interface endpoints |
| `ec2:CreateTags` | Only the five allowed EC2 creation resource types and corresponding `ec2:CreateAction`; creation tags, no standalone retagging |
| `ec2:ModifyVpcAttribute` | Owned VPC ARN; only enableDnsSupport/enableDnsHostnames attributes |
| `ec2:ModifySubnetAttribute` | Owned subnet ARN; only mapPublicIpOnLaunch, string value `false` |
| `ec2:AssociateRouteTable`, `ec2:DisassociateRouteTable`, `ec2:ReplaceRouteTableAssociation` | Owned route-table and subnet ARNs; explicit private associations and rollback. No IGW/VPN attachment authorization |
| `ec2:AuthorizeSecurityGroupIngress`, `ec2:AuthorizeSecurityGroupEgress`, `ec2:RevokeSecurityGroupIngress`, `ec2:RevokeSecurityGroupEgress` | Owned SG ARNs; PostgreSQL/gateway egress and removal of default egress. No permission to administer unrelated groups |
| `ec2:ModifyVpcEndpoint` | Owned endpoint/route-table ARNs; endpoint policy and app-route association maintenance, subnet/SG attachment denied |
| `ec2:DeleteVpcEndpoints`, `ec2:DeleteSecurityGroup`, `ec2:DeleteRouteTable`, `ec2:DeleteSubnet`, `ec2:DeleteVpc` | Respective owned EC2 ARNs; CloudFormation rollback and approved teardown |
| `rds:CreateDBSubnetGroup`, `rds:AddTagsToResource` | Exact DB subnet ARN and both request tags; create/tag only the named group. No database instance permission |
| `rds:DescribeDBSubnetGroups`, `rds:ListTagsForResource` | Exact DB subnet ARN; named-group stabilization/tag reads. `Resource: "*"` is not needed |
| `rds:ModifyDBSubnetGroup`, `rds:DeleteDBSubnetGroup` | Exact DB subnet ARN plus ownership tags; reviewed subnet membership changes and cleanup |

Sources: AWS [EC2](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ec2.html),
[RDS](https://docs.aws.amazon.com/service-authorization/latest/reference/list_rds.html),
[CloudFormation](https://docs.aws.amazon.com/service-authorization/latest/reference/list_cloudformation.html)
action/resource/condition references and their public machine-readable definitions.
Read-only Access Analyzer ValidatePolicy returned zero findings for the
CloudFormation and DB-subnet documents and the preceding network revision.
It first caught a Bool/String mismatch for mapPublicIpOnLaunch; that was corrected.
The final network edit narrows DescribeVpcAttribute from `*` to owned VPC ARNs,
using resource scoping listed in AWS's action reference. Its three local boundary
tests passed, but revalidation was interrupted and the resumed attempt returned
an expired AWS session. **Final network-policy validation remains pending before
attachment approval.** Do not treat the preceding revision's result as final evidence.

### Template and limits of permission validation

Use [network.py](../network.py), not the combined `foundation.py`. It defines one
VPC, two private application subnets, two private database subnets in two distinct
AZs, separate route tables with four associations, two SGs, a PostgreSQL ingress
rule, one named DB subnet group and two **Gateway** endpoints on app routes only.
Endpoint policies target deterministic future resource ARNs; they create no data
resources. AZs/prefix lists are inputs, account/region use pseudo-parameters.
No NAT, IGW, interface endpoint, default internet route, RDS instance, parameter
group, KMS key, bucket, table, queue or function is included.

Expected Stage 1 resource standing cost: **USD 0** for these native networking
resources, DB subnet group and gateway endpoints. Later service traffic, paid
monitoring and application resources are not included. Four subnets add no fee.

CloudFormation ValidateTemplate succeeded; 19 focused network/budget tests passed.
These checks do not prove every provider lifecycle call will be authorized. No
change set, stack execution, IAM simulation or deployment was performed. Actual
CloudFormation forwarding/tagging/rollback behavior remains an execution check.
Fail closed on a denial and review its exact action; do not grant a wildcard fix.

IAM has no documented `ec2:VpcEndpointType` condition key. The policy restricts
service names and denies endpoint subnet/SG attachments; the reviewed template
and tests enforce Gateway explicitly. Do not claim IAM alone validates every
endpoint property. CIDRs, SG port/source contents, exactly four subnets, route
membership and DB-subnet membership are template/change-set invariants. The role
cannot create an IGW/NAT/ENI or add arbitrary routes with this policy, but an edited
template could still make unsafe changes within allowed resource types. Review
the exact change set before execution; policy validation is not that review.

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

Stage 0 identities and the monthly budget exist. The next approval is the exact
Stage 1 policy bundle and network-only template together. Permission attachment
and stack/change-set creation remain separate authorized actions. This document
does not authorize creation, policy attachment, login reconfiguration or deployment.
