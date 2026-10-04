# Read-only inventory procedure

Prepared only. No commands in this document have been executed against AWS.
Run only after separate account-access authorization, using an existing read-only
operator profile. Do not run the provisioning helpers. Do not fetch SSM values,
Lambda environment values, objects, database rows, queue messages or log events.
Keep inventory output private; account IDs, network details and policies are operational metadata.

## Scope and identity

Set the approved profile and expected account ID. Leave pagination enabled. An
AccessDenied response means UNKNOWN, not absent. Resolve access with the owner;
do not grant permissions as part of inventory. Record each command's exit status.

```powershell
$InventoryProfile = '<approved-read-only-profile>'
$ExpectedAccountId = '<12-digit-account-id>'
$Region = 'af-south-1'
$Common = @('--profile', $InventoryProfile, '--region', $Region, '--no-cli-pager')
$Identity = aws sts get-caller-identity @Common --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $Identity.Account -ne $ExpectedAccountId) { throw 'Account verification failed' }
aws ec2 describe-regions @Common --all-regions --region-names af-south-1
```

Stop if the region is not enabled. Enabling it requires separate authorization.
Review names, tags and CloudFormation ownership before choosing each ID below.

## Network and database

```powershell
aws ec2 describe-vpcs @Common
aws ec2 describe-subnets @Common
aws ec2 describe-route-tables @Common
aws ec2 describe-internet-gateways @Common
aws ec2 describe-nat-gateways @Common
aws ec2 describe-vpc-endpoints @Common
aws ec2 describe-security-groups @Common
aws ec2 describe-network-acls @Common
aws ec2 describe-managed-prefix-lists @Common --filters Name=owner-id,Values=AWS
aws rds describe-db-instances @Common --query 'DBInstances[].{Id:DBInstanceIdentifier,Arn:DBInstanceArn,ResourceId:DbiResourceId,Engine:Engine,Version:EngineVersion,Class:DBInstanceClass,Endpoint:Endpoint,Vpc:DBSubnetGroup,Groups:VpcSecurityGroups,IAM:IAMDatabaseAuthenticationEnabled,Public:PubliclyAccessible,Encrypted:StorageEncrypted,Kms:KmsKeyId,BackupDays:BackupRetentionPeriod,DeletionProtection:DeletionProtection,Parameters:DBParameterGroups,Storage:AllocatedStorage,StorageType:StorageType,MultiAZ:MultiAZ,Status:DBInstanceStatus}'
aws rds describe-db-subnet-groups @Common
aws rds describe-db-snapshots @Common --snapshot-type manual --query 'DBSnapshots[].{Id:DBSnapshotIdentifier,DB:DBInstanceIdentifier,Status:Status,Encrypted:Encrypted,Kms:KmsKeyId}'
aws rds describe-db-parameters @Common --db-parameter-group-name '<selected-group>' --query 'Parameters[?ParameterName==`rds.force_ssl`]'
```

Check all subnet associations, including inherited main routes, gateway endpoint
policies, DNS support/hostnames, and outbound rules. For the selected VPC:

```powershell
aws ec2 describe-vpc-attribute @Common --vpc-id '<vpc-id>' --attribute enableDnsSupport
aws ec2 describe-vpc-attribute @Common --vpc-id '<vpc-id>' --attribute enableDnsHostnames
```

## Storage, projection and queues

`list-buckets` is account-wide: inspect each candidate's location before further
reads. Do not interpret a bucket name collision as permission to replace it.
For each selected raw, quarantine and reports bucket:

```powershell
aws s3api list-buckets @Common --query 'Buckets[].Name'
aws s3api get-bucket-location @Common --bucket '<bucket>'
aws s3api get-bucket-tagging @Common --bucket '<bucket>'
aws s3api get-public-access-block @Common --bucket '<bucket>'
aws s3api get-bucket-encryption @Common --bucket '<bucket>'
aws s3api get-bucket-versioning @Common --bucket '<bucket>'
aws s3api get-bucket-policy @Common --bucket '<bucket>'
aws s3api get-bucket-notification-configuration @Common --bucket '<bucket>'
aws s3api get-bucket-lifecycle-configuration @Common --bucket '<bucket>'
aws s3api get-bucket-logging @Common --bucket '<bucket>'
aws dynamodb list-tables @Common
aws dynamodb describe-table @Common --table-name '<table>'
aws dynamodb describe-continuous-backups @Common --table-name '<table>'
aws dynamodb describe-time-to-live @Common --table-name '<table>'
aws dynamodb list-tags-of-resource @Common --resource-arn '<table-arn>'
aws sqs list-queues @Common
aws sqs get-queue-attributes @Common --queue-url '<queue-url>' --attribute-names All
aws sqs list-queue-tags @Common --queue-url '<queue-url>'
```

Repeat queue reads for the ingest FIFO, its FIFO DLQ and the separate standard
stream-failure queue. Inspect redrive allow policy, visibility, retention and encryption.
Do not receive, purge or replay messages. Missing optional configuration errors
such as NoSuchLifecycleConfiguration must be distinguished from denied access.

## Functions, API, identity and encryption

```powershell
aws lambda list-functions @Common --query 'Functions[].{Name:FunctionName,Arn:FunctionArn,Runtime:Runtime,Arch:Architectures,Handler:Handler,Role:Role,Size:CodeSize,Hash:CodeSha256,Vpc:VpcConfig,Tracing:TracingConfig,Timeout:Timeout,Memory:MemorySize}'
aws lambda list-event-source-mappings @Common
aws lambda list-aliases @Common --function-name '<function>'
aws lambda get-function-concurrency @Common --function-name '<function>'
aws lambda get-policy @Common --function-name '<function>'
aws lambda list-tags @Common --resource '<function-arn>'
aws apigateway get-rest-apis @Common
aws apigateway get-resources @Common --rest-api-id '<api-id>' --embed methods
aws apigateway get-stages @Common --rest-api-id '<api-id>' --query 'item[].{Name:stageName,Deployment:deploymentId,Methods:methodSettings,Tracing:tracingEnabled,AccessLogs:accessLogSettings,CacheEnabled:cacheClusterEnabled}'
aws apigateway get-method @Common --rest-api-id '<api-id>' --resource-id '<resource-id>' --http-method GET
aws apigateway get-integration @Common --rest-api-id '<api-id>' --resource-id '<resource-id>' --http-method GET
aws iam list-roles @Common --query 'Roles[].{Name:RoleName,Arn:Arn,Path:Path}'
aws iam get-role @Common --role-name '<role>'
aws iam list-attached-role-policies @Common --role-name '<role>'
aws iam list-role-policies @Common --role-name '<role>'
aws iam get-role-policy @Common --role-name '<role>' --policy-name '<inline-policy>'
aws iam get-policy @Common --policy-arn '<managed-policy-arn>'
aws iam get-policy-version @Common --policy-arn '<managed-policy-arn>' --version-id '<default-version-id>'
aws kms list-aliases @Common
aws kms list-keys @Common
aws kms describe-key @Common --key-id '<key-id>'
aws kms get-key-policy @Common --key-id '<key-id>' --policy-name default
aws kms get-key-rotation-status @Common --key-id '<key-id>'
aws kms list-resource-tags @Common --key-id '<key-id>'
aws ssm describe-parameters @Common --parameter-filters 'Key=Name,Option=BeginsWith,Values=/fintrust/' --query 'Parameters[].{Name:Name,Type:Type,Tier:Tier,Version:Version,KeyId:KeyId}'
aws cloudformation describe-stacks @Common --query 'Stacks[].{Id:StackId,Name:StackName,Status:StackStatus,Tags:Tags}'
aws cloudformation list-stack-resources @Common --stack-name '<stack>'
```

Repeat method/integration reads for every returned API method. Repeat IAM reads
for every attached policy and permissions boundary. IAM is global; `--region`
does not make roles regional. Do not request Lambda code download URLs or SSM secrets.

## Email, scheduling, monitoring and budget

```powershell
aws sesv2 get-account @Common
aws sesv2 list-email-identities @Common
aws sesv2 get-email-identity @Common --email-identity '<approved-sender-identity>'
aws events list-rules @Common
aws events describe-rule @Common --name '<rule>'
aws events list-targets-by-rule @Common --rule '<rule>' --query 'Targets[].{Id:Id,Arn:Arn,Role:RoleArn,Retry:RetryPolicy,DLQ:DeadLetterConfig}'
aws logs describe-log-groups @Common --log-group-name-prefix '/aws/lambda/fintrust'
aws cloudwatch describe-alarms @Common
aws xray get-sampling-rules @Common
```

Billing APIs have global endpoints. These explicit `us-east-1` calls are a billing
exception, not a change to the deployment region. Billing visibility can require
payer-account authorization. Do not activate Cost Explorer or buy anything.
Cost Explorer API requests can incur charges; approve that small query cost first.

```powershell
aws budgets describe-budgets --profile $InventoryProfile --region us-east-1 --account-id $ExpectedAccountId --no-cli-pager
aws budgets describe-notifications-for-budget --profile $InventoryProfile --region us-east-1 --account-id $ExpectedAccountId --budget-name '<budget-name>' --no-cli-pager
aws ce get-cost-and-usage --profile $InventoryProfile --region us-east-1 --time-period Start='<approved-start>',End='<exclusive-end>' --granularity MONTHLY --metrics UnblendedCost --group-by Type=DIMENSION,Key=SERVICE --no-cli-pager
aws freetier get-free-tier-usage --profile $InventoryProfile --region us-east-1 --no-cli-pager
```

The account owner must separately confirm plan, remaining credits, expiry, tax,
currency and billing-console alerts. No free-tier eligibility is inferred here.
Finish with a resource map and reconciliation review; stop before any writes.

## Reconciliation decisions

REUSE references a compatible existing resource without adopting ownership.
IMPORT requires separately approved CloudFormation import support and exact
configuration. UPDATE requires an approved non-destructive diff. CREATE applies
only to confirmed absence and approved cost. LEAVE UNTOUCHED protects unrelated
resources. CONFLICT REVIEW blocks mismatched ownership, region or configuration.

| Resource | Candidate decision after inventory | Protection / stop condition |
|---|---|---|
| VPC, subnets, routes, SGs | REUSE; IMPORT only if supported; CREATE only when absent | Never replace route associations, main routes or shared SG rules automatically. Compare two existing private subnets with the template's shared app/DB topology. |
| NAT / interface endpoints | LEAVE UNTOUCHED; CONFLICT REVIEW | No new NAT permitted; interface endpoint costs unapproved. Do not delete shared resources to meet this design. |
| S3/DynamoDB gateway endpoints | REUSE or reviewed UPDATE; otherwise CREATE | Preserve other route-table associations and policy consumers. |
| RDS / subnet and parameter groups | REUSE; reviewed UPDATE | Existing RDS is external to foundation. Snapshot and rollback approval precede changes. No replacement, migration or schema execution during inventory. |
| Raw/quarantine/report buckets | REUSE or supported IMPORT; otherwise CREATE | Preserve objects, versions, lifecycle, policies and all notification bindings. Merge the raw CSV binding only after conflict review. |
| DynamoDB / streams | REUSE or supported IMPORT | Preserve TX and ALERT state; never reset deduplication claims or replace a populated table. Review keys, stream view and backups. |
| FIFO / FIFO DLQ / stream failure queue | REUSE, UPDATE or CREATE | Preserve queued messages and DLQ links; incompatible queue type means CONFLICT REVIEW. |
| IAM roles and policies | REUSE or reviewed UPDATE; CREATE for new dedicated roles | Never overwrite shared roles/trust/policies. Check boundaries and owners. |
| KMS key / alias | REUSE compatible key; CREATE one only if absent and approved | Never repoint an alias or disable/delete the old key while ciphertext depends on it. Retain decrypt access. |
| SSM metadata | REUSE or reviewed UPDATE | Inventory reads no values; keep existing service paths. Secret access needs separate scope. |
| Lambda / API | REUSE or reviewed UPDATE; otherwise CREATE | Preserve versions, aliases, auth and unrelated routes; publish with consumers disabled. |
| SES identities | REUSE | Region/sandbox verification and recipient approval precede sending; no mail during inventory. |
| EventBridge / logs / alarms / budgets | REUSE or reviewed UPDATE; CREATE missing approved controls | Preserve targets, retention and recipients. Keep schedule disabled until checks pass. |

For every candidate record: actual ID, owner/stack, region, decision, exact diff,
data dependencies, rollback and approval. Until inventory succeeds, all candidate
decisions remain provisional. An existing physical name cannot simply be passed
to a CREATE-only template; adapt references or obtain an approved import first.
