# Draft for AWS Support — not submitted

Account: 966467878406. Region: Africa (Cape Town), af-south-1.
Service: AWS Lambda. Quota: Concurrent executions, L-B99A9384.

The applied regional quota is 10, confirmed by GetServiceQuota. We need a
temporary database migration Lambda with reserved concurrency **1**, followed
by deletion. The runner has no event triggers and accepts only fixed operations.

CloudFormation rejected ReservedConcurrentExecutions=1:

> Specified ReservedConcurrentExecutions for function decreases account's
> UnreservedConcurrentExecution below its minimum value of [10].

Lambda request ID: 7b1e2b06-a4d0-4299-af36-03a9e9902d7a.
Timestamp: 2026-10-14T23:12:00Z (15 October 2026 SAST).

A minimal Service Quotas request for 11 was rejected:

> You must provide a quota value greater than the default quota value of 1000.0

No quota request was created. The owner elected to keep the quota unchanged
pending AWS Support review rather than request 1001.

Please confirm the supported way to raise this reduced applied regional limit
from 10 to 11, or advise the minimum supported value that allows a one-execution
reservation. We need a bounded concurrency safeguard, not provisioned concurrency.
Do not increase the limit to 1001 without the account owner's separate decision.

The migration runner was removed without invocation. No live SQL or secret access
occurred. Temporary network cleanup was verified on 15 October 2026 at 07:18 SAST;
temporary migration IAM cleanup was verified at 07:21 SAST. The two receipts are
retained alongside this draft. No Secrets Manager interface endpoint remains.

References:
- https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html
- https://docs.aws.amazon.com/lambda/latest/dg/troubleshooting-deployment.html
