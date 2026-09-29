# Remaining Work

**Target submission:** 15 October 2026. Items below are not yet evidenced as complete. Work from the top down, and do not describe a component as deployed until it has been tested in AWS.

## 1. Repository and local database

- Create a **private GitHub repository** under `Nompil`, grant the facilitator access, then add it as `origin`. The local project already has six commits on `main`; it has not been pushed.
- Run the complete test suite with `FINTRUST_TEST_DATABASE_URL` set so the 15 unit tests and five PostgreSQL integration tests are verified together, then remove the variable from the shell.
- Export a rendered architecture diagram and annotated ERD to the required PDF/image artefacts. The Markdown Mermaid ERD is present but is not yet a separate exported diagram deliverable.

## 2. AWS deployment and security

- Confirm the AWS learning account, billing alarm, region `af-south-1`, and current Free Tier limits before creating resources. Avoid NAT Gateway.
- Create the VPC, private subnets, security groups, private RDS PostgreSQL instance, and database users/grants. The current app uses a shared database credential; create separate least-privilege read/write users before claiming the query Lambda is read-only.
- Complete the S3 setup: select a globally unique bucket name, run the bucket script, and add the required encryption configuration. Verify versioning, public-access blocking, lifecycle/retention, and the final retention policy in AWS.
- Set database values in SSM Parameter Store, using `SecureString` for the password. Review every IAM action/resource and configure the S3 Lambda permission with the expected source bucket/account.
- Build and deploy the ingest Lambda with a Linux-compatible `psycopg2` package. Configure the S3 trigger only after the function exists.
- Run the DynamoDB creation script and verify `risk_scores` is `ACTIVE`, the key schema is correct, and TTL is enabled.
- Run the DLQ and CloudWatch setup scripts; verify two async retries, DLQ delivery, quarantine metric filter, and alarms in AWS. These scripts exist but have not been run.

## 3. Complete the capstone runtime

- Reconcile the training exercise's direct Lambda-to-RDS write with the final capstone architecture. The submitted brief requires S3 → ingest Lambda → SQS FIFO → scoring Lambda → RDS + DynamoDB. Avoid writing the same transaction through both paths.
- Implement and test the scoring Lambda, risk-score persistence, account-group FIFO configuration, duplicate handling, and any transaction-to-risk-event creation.
- Finish the API deployment: create API Gateway routes for `/v1/health`, `/v1/transactions`, and `/v1/insights`; use AWS_IAM for the data routes and verify the API role is read-only at the database level as well as in IAM.
- Implement the high-risk SES alert flow and verify SES sandbox recipient requirements.
- Implement the EventBridge monthly schedule and report Lambda, then verify CSV/JSON reports are written to S3.
- Configure a visual CloudWatch dashboard with operational/custom metrics. The current code has alarms and a quarantine metric filter, but not a dashboard or all required metrics (ingestion totals, high-risk counts, API activity, queue depth/errors).
- For very large CSVs, implement file chunking/Step Functions or document and enforce a supported file-size limit.

## 4. End-to-end evidence and presentation

- Run the complete local suite, including the now-passing PostgreSQL constraint tests; then run integration/smoke tests against the deployed AWS stack.
- Capture evidence required by the brief: AWS resources, API responses, CloudWatch dashboard/logs, and a green GitHub Actions run.
- Run the demo in order: upload CSV → validate/quarantine → queue/score → verify RDS and DynamoDB → query API → show alert → show dashboard/report.
- Rehearse [live_demo_script.md](live_demo_script.md) and [presentation_notes.md](presentation_notes.md) against the deployed system. Those materials describe the target end-to-end experience; do not claim unavailable services are live.
- Push the local commits and verify facilitator access after the private GitHub repository is created.

## Suggested order to 15 October

1. Run the full local suite with PostgreSQL configured and confirm all 20 tests pass.
2. Create the private GitHub repository and push only when ready.
3. Deploy the AWS foundation with cost controls and validate ingestion/DLQ.
4. Complete FIFO scoring, API Gateway, alerts, reports, and the dashboard.
5. Capture evidence, update documentation to match what is actually deployed, and rehearse the stakeholder demo.
