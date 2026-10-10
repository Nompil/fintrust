# Release1 controlled AWS execution plan — not executable approval

Region af-south-1, account966467878406. Existing deployed stacks remain unchanged. Source/artifact/manifest must match the final candidate CI evidence. No commands in this plan were executed. No live database secrets, snapshots, writes, artifact uploads, concurrency or triggers were accessed.

First future checkpoint is read-only inventory ONLY, separately approved:

```bash
aws sts get-caller-identity --profile fintrust-inventory --region af-south-1 --no-cli-pager
aws rds describe-db-instances --db-instance-identifier fintrust-ledger-dev --profile fintrust-inventory --region af-south-1 --query 'DBInstances[0].{Status:DBInstanceStatus,Engine:EngineVersion,Public:PubliclyAccessible,Encrypted:StorageEncrypted,IamAuth:IAMDatabaseAuthenticationEnabled,Subnets:DBSubnetGroup.DBSubnetGroupName,SGs:VpcSecurityGroups[*].VpcSecurityGroupId}' --no-cli-pager
aws cloudformation describe-stacks --stack-name fintrust-database-dev --profile fintrust-inventory --region af-south-1 --no-cli-pager
```

Then proceed through explicit gates in this order:

1. Read-only AWS inventory and caller identity; no deployment.
2. Confirm DB/network state against approved PG16/private/app-SG/subnet assumptions.
3. Review/create temporary Secrets Manager interface endpoint using existing PRIVATE_RDS_RUNNER.md templates; approve cost separately, no NAT.
4. Prepare/deploy verified phase-specific migration runner with master secret restricted to endpoint/bootstrap/cleanup only.
5. Invoke read-only live RDS preflight. Do not log secret values.
6. STOP and compare actual schema, owners, grants, versions and row counts with candidate assumptions.
7. Approve/create DB snapshot and wait for availability.
8. Bootstrap narrowly scoped temporary IAM DB identity through the established secure endpoint path.
9. Execute reviewed001 identity migration using its verified runner, preserving rows.
10. STOP:002 live runner is not yet implemented/verified. Prepare exact002 plus tracking/grants/catalog capability, validatePG16 then review before any live execution. Never pass002 to001-only runner. Apply only after approval.
11. Verify source/catalog/version/row counts and runtime service privileges.
12. Remove temporary DB identity/helper roles, runner/IAM/endpoint; verify cleanup and costs.
13. Review runtime policies/template parameter values, existing-function ownership/import requirements and exact artifact/version/checksum; deploy Lambda with concurrency0 and triggers disabled. Do not duplicate existing named ingest resources.
14. Controlled smoke tests with synthetic IDs and outcome/projection reconciliation.
15. Deploy API only after its private DB grants/configuration and secure cloud identity path are reviewed. Local token registry is not automatically provisioned in AWS.
16. Deploy packaged frontend and approved auth. No Cognito creation is authorized now.
17. Approve bounded concurrency based on DB connection capacity.
18. Wire reviewedSQS/S3/DynamoDB-stream/EventBridge triggers individually; review alert destinations first.
19. Upload reviewed actualCSV A only after immutable per-row/hash manifest is complete.
20. Upload reviewed actualCSV B and reconcile cross-file duplicates.
21. Re-upload exactA bytes for whole-file duplicate proof.
22. Verify authoritative ledger/risk/review/quarantine/corrections/projections/alerts/batches.
23. Investigate/fix/redrive one approved technical failure with operator receipt and duplicate assertions. Cloud operations controller is a separate gate; private API cannot reach publicSQS without a designed path.
24. Final health/evidence, cost/cleanup check and presentation truth matrix.

Blocked deployment prerequisites: actualCSV A/B manifests; verified002 live execution path; cloud API identity provisioning; reviewed cloud operations controller/network path. These are not excuses to alter RDS publicly or add NAT. The new ZIP is prepared only; historical ZIP is preserved. All existing resource names/values remain repository assumptions until approved fresh inventory/preflight confirms them. Exact mutation commands/change sets must be produced only after those values and gates are resolved; this document intentionally refuses fabricated executable002/auth/controller commands.
