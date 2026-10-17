# Individual function tests using shared Lambda capacity

**Local candidate only. No upload, deployment or activation has occurred.**
This option avoids requesting a positive reserved slot for an individual test.
It is not a completed cloud rollout, a production capacity strategy or an
implementation of shared-capacity database migrations.

`application-functions-shared-manual.json` uses the same resource names, package,
roles, database configuration, network, aliases and outputs as the prepared
application template. It targets the same future `fintrust-application-dev`
stack; never create a second stack for these resource names. The reserved-mode
template remains unchanged and is the current deployment baseline.

With defaults, all four functions retain reserved concurrency zero. Consumers
and scheduled reports are hard-disabled; their parameters accept only false.
For a reviewed manual test, `EnableManualTest=true` and `ManualTestFunction`
select exactly one of scoring, alert, report or api. Only that function omits
its reserved-concurrency property and uses the account's shared pool. The other
three remain at zero. A missing selection is rejected by a CloudFormation rule.
No provisioned capacity is configured.

**One selected function does not mean one simultaneous execution.** The selected
function could consume all available account capacity (last observed: 10).
Sequential synchronous invocations by one approved operator are an operating
restriction, not a hard Lambda limit or cost cap. Do not expose an active API
stage, attach an upstream caller, enable consumers or run concurrent test
clients under this mode. Check existing invocation permissions and pending
asynchronous work before releasing any function.

## Before any live test

1. Verify the exact package version, artifact hashes and reviewed stack change
   set. Deployment with defaults must read back zero concurrency for all four
   functions, disabled mappings and a disabled report schedule.
2. For scoring, report or API tests, first prove the approved private RDS access,
   migrations, IAM/TLS authentication and per-service grants. Do not execute
   pre-existing database migration templates in shared mode: they retain their
   reserved-slot/security requirements and have not been changed.
3. Review an exact qualified test invocation permission separately. The current
   deployer policy intentionally does not grant direct application invocation;
   do not use admin credentials for testing. Verify all other caller paths are
   inactive, including the API stage and raw notifications. Do not send an email
   or publish financial test data without the corresponding approved test scope.
4. Review a change set releasing only the selected function. Invoke it
   synchronously, one request at a time, within the agreed usage scope. AWS
   compute, logs, storage and email are usage-dependent; this option is not free
   by definition. If a request times out, verify its outcome before retrying or
   switching functions; an ended client connection does not prove execution ended.
5. Set `EnableManualTest=false` again through the stack. Read back reserved
   concurrency zero and reconcile in-flight work/database sessions before
   enabling another function or making a new configuration change. If outcome
   is uncertain, stop and inspect; do not blindly retry or delete records.

The ingest function and migration runner are not owned or changed by this
candidate. Full automatic ingestion-to-alert E2E needs a separately reviewed
multi-service capacity and cost plan. Keep AWS Support case 179210878300923 open.

## Verification

Run locally from the repository root:

```powershell
python infrastructure/service_preparation/prepare_shared_manual.py
python -m unittest discover -s infrastructure/service_preparation -p 'test_*.py' -v
```

`manifest.json` binds this candidate and the unchanged reserved template by
SHA256. Tests cover disabled defaults, every selected service, selection rules,
the automatic-path restrictions, and preservation of all other resource
configuration. These offline checks do not establish live runtime safety.
`aws-template-validation.json` separately binds AWS's template acceptance to the
exact candidate hash; template acceptance is not resource creation or execution.

References: [Lambda concurrency](https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html),
[CloudFormation Lambda configuration](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-lambda-function.html).
