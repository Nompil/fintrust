# Private database read-only preflight candidate

Status: prepared and verified locally; AWS accepted both templates. **Not
deployed, uploaded or invoked. No secret value or live SQL was retrieved.**

The account still reports total/unreserved concurrency 10. The existing support
case cannot be read through the AWS Support API on Basic Support; the metadata
receipt records SubscriptionRequiredException. No support upgrade is proposed.

The owner subsequently authorized a budget increase if needed for this bounded
check, while explicitly prohibiting a support-plan change. See
`cost-authorization.json`. Authentication/transport delays stopped the initial
setup before runtime-role creation or package upload; no endpoint was created.
The latest terminal/session receipt, rather than the historical operator-session
status, determines whether a live check has actually started or completed.

This candidate is limited to the fixed `migration_runner.preflight_entry` handler.
It accepts only the existing `preflight` operation and request UUID. Its fixed
queries inspect catalog metadata, migration hashes and aggregate row counts in a
read-only transaction; no arbitrary SQL, customer records or credentials are
returned. The package uses the exact verified application dependency subset,
with every pinned dependency version checked. Its Linux native imports and
source bindings were verified. The focused disposable PostgreSQL 16 run passed
65 tests, zero failures/errors/skips, and the task-owned cluster was removed.
Local checks do not establish live RDS authentication or schema state.

## Scope and cost decision required

- One temporary single-AZ Secrets Manager interface endpoint and two dedicated
  security groups; preserve the existing VPC, app/DB security groups, RDS instance
  and gateway endpoints. No NAT, public RDS access or standing interface endpoint.
- A separate temporary migration operator, the bounded Lambda execution role,
  exact artifact staging and the three-resource runner stack. The existing
  deployer's explicit endpoint Deny must remain unchanged. Operator permissions,
  runtime boundary and actual endpoint binding need validation/read-back before
  execution; template acceptance alone does not establish IAM authorization.
- Runner deploys at reserved concurrency zero. Only after qualified invocation
  permission and inactive upstream checks may shared capacity be released for
  **one synchronous request**. There is no individual concurrency cap in shared
  mode; the operator sends one request without retries. All five application
  functions remain at zero, mappings/report rule disabled and raw notification
  absent. No runner trigger, URL, alias or async invocation is introduced.
- Inspect and save only the sanitized result, throttle the runner immediately,
  revoke invocation/secret permissions, then remove the temporary endpoint,
  runner and operator resources. Verify deletion; do not merely request it.
  If the result is uncertain, stop and inspect instead of replaying it. Cleanup
  permissions must be installed and verified before starting the charged path.
- **No migration, snapshot, bootstrap, user/grant creation or data modification
  is authorized by a read-only preflight decision.** Review the actual catalog
  result before choosing any write phase. Existing canonical migration templates
  remain unchanged at concurrency zero.

AWS's Cape Town public price list reports **USD 0.01309 per endpoint-hour** in
one AZ and USD 0.01/GB for the first data tier. Partial hours are billed as full
hours. There is also small S3/KMS/Lambda/log/API usage. The proposed operating
allowance is **up to USD 1 incremental usage**, with an endpoint cleanup target
within one hour of creation. That is an operating limit and cleanup target,
not an AWS-enforced spending cap or a guarantee that the whole account stays
below USD 10. Do not create the endpoint until the owner grants an exception
to the earlier no-paid-endpoint instruction and the bounded session is ready.

Sources: [Cape Town AmazonVPC price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonVPC/current/af-south-1/index.json),
[PrivateLink billing](https://aws.amazon.com/privatelink/pricing/).

## Evidence

`manifest.json` binds the prepared templates and unchanged runner sources.
`aws-template-validation.json` binds AWS acceptance to the exact template hashes.
`preflight-package.manifest.json` records the 20,673,673-byte ZIP, SHA256
`667f1aba96d8deed5033bb4f9ec14b1ac02e8e36b4db04b77f20d9699fdb4d57`,
native Linux imports and package source bindings. The ZIP remains local under
the workspace build directory; do not commit it to Git or upload it implicitly.
`pg16-verification.json`, `pg16-focused.xml` and `pg16-verification.log` record
the focused verification. `endpoint-price.json` records the retrieved regional
price and its publication date. The latest read-only AWS gate inventory is in
`../deployment_iam/evidence/database-preflight-gates-20261017.json`.

Regenerate/check the candidate offline from the repository root:

```text
python -m infrastructure.service_preparation.database_preflight.prepare
python -m unittest infrastructure.service_preparation.database_preflight.test_candidate -v
```

The original migration architecture remains documented in
`../../PRIVATE_RDS_RUNNER.md`. This candidate changes only capacity handling for
the read-only phase; it does not approve shared-capacity write migrations or
clear any application activation gate.
