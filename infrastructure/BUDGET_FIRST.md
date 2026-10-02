# Budget-first preparation

## Dependency review before code changes

R = required, L = legacy compatibility only, O = optional, D = removed from the proposed deployed path. CloudWatch refers to Lambda-managed stdout delivery, not a runtime SDK call.

| Lambda | RDS | S3 | SQS | DynamoDB | SES | SSM | CloudWatch | Can stay outside VPC? |
|---|---|---|---|---|---|---|---|---|
| Ingest | D: move account existence check to score; L: local CSV loader | R: read CSV/write malformed rows | R: publish validated messages | No | No | No | R: processing logs | Yes after moving account validation |
| Score | R: account check, ledger, frozen score, idempotency | R: quarantine unknown accounts | Managed polling, no SDK calls | R: immutable score projection/event source | No | D: deployment resolves nonsecret DB settings | R | No |
| Alert | D: delivery claims move to conditional DynamoDB writes; L: old direct SQL helper | No | No | R: verify score and maintain delivery state; stream trigger | R: send email | No | R | Yes with conditional delivery claims |
| Query | R: ledger/accounts | No | No | R: risk lookup | No | D: deployment-resolved DB settings | R | No |
| Report | R: SQL analysis | R: monthly exports | Managed failure destination | No | No | D: deployment-resolved DB settings | R | No |

Current ingest checks account existence in SQL before publishing. This business check will move to scoring: unknown accounts go to sanitized S3 quarantine and are acknowledged only after that write succeeds. Database/service failures remain retryable technical failures. Malformed CSV rows remain ingest quarantine. Existing local direct-loading helpers remain for teaching tools.

Current alert locks SQL delivery state. The deployed alert handler will instead consume immutable transaction projections from DynamoDB Streams and claim a separate `ALERT#<transaction UUID>` item using conditional writes. Claims commit before SES. SENT is never resent; SENDING/UNKNOWN require reconciliation; definitive rejections remain retryable. SQL remains the authoritative ledger; delivery status becomes an operational DynamoDB record. The old direct SQL alert helper is retained only for existing local tests/tools, never wired to a deployed function.

Scoring will stop synchronously invoking alert. A successful SQL write followed by a failed DynamoDB write remains a queue retry. Successful projection publication delegates email retries to the stream consumer. The alert filter accepts transaction items and ignores delivery-state items, preventing recursion. Stream processing needs its own failure capture and monitoring because email no longer controls scoring acknowledgement.

These changes remove runtime SSM, SQS, Lambda API and SES calls from private functions. Private functions use only PostgreSQL plus S3/DynamoDB gateway endpoints. Ingest and alert use AWS public service endpoints from outside the customer VPC. No NAT or interface endpoints are selected. IAM database token generation is local signing; standard Lambda polling/log delivery is service-managed.

## Implementation boundaries

Prepare and test locally only. No AWS access. Preserve original routes and SQL ledger behavior. No frontend styling, identity platform, PDF changes or deployment. Paid KMS is an intentional requirement; use one regional key. The final readiness report will distinguish built artifacts, Linux execution checks and unverified cloud behavior.
