# Read-only preflight: preserve retained migration logs

The first live attempt on 17 October 2026 created the temporary private
endpoint, then CloudFormation rejected `RunnerLogs` because
`/aws/lambda/fintrust-migration-dev` already existed. The runner was never
invoked: the receipt records zero invocation attempts and no SQL writes.

Cleanup verified that both temporary stacks, the charged endpoint and the
temporary execution/operator IAM resources were removed. The receipt and its
reviewed policies are preserved in `first-attempt/`; the log group was kept.
Its observed retention was 14 days.

`runner-existing-logs-readonly.json` omits only the log-group resource and the
function's dependency on its creation. It retains the exact read-only handler,
disabled default, immutable package parameters and qualified version. Its
successful AWS template validation is recorded in `aws-template-validation.json`.
The additional focused test checks that this is the only difference from the
original candidate. No write-phase template or runtime ZIP changed.

Before a corrected attempt creates the endpoint, the controller verifies the
existing log group's exact name and retention. It downloads and verifies the
already staged S3 version; it does not upload another ZIP. A corrected attempt
still requires its own live result and cleanup receipt. This recovery record
does not establish database connectivity or migration readiness.
