# Cognito authentication candidate

This is a local implementation and un-deployed CloudFormation proposal. It has not created, inspected, or changed AWS resources. Do not describe Cognito sign-in as live or verified in AWS.

## Design

The cognito.json template follows the repository's CloudFormation approach. It proposes one workforce user pool, public OAuth client (no client secret), hosted Cognito domain, four groups, an encrypted on-demand DynamoDB account-scope table with point-in-time recovery, and a narrowly scoped GetItem policy for the existing API execution role. Callback and logout URLs are operator-supplied HTTPS URLs. The template does not create a NAT gateway, VPC endpoint, database, or Lambda.

The pool permits administrator-created users only, requires software-token MFA, and uses a 14-character temporary-password policy. The selected Cognito Lite tier avoids enabling advanced threat protection. Test users are never created by CloudFormation. The bootstrap_cognito_user.py command has a no-call dry-run by default; --apply creates only one selected test identity, group membership, and its explicit account scope. It reads a temporary password with hidden input and never prints or writes that password. The operator must deliver the temporary password through an approved out-of-band channel. Four named test-user identities are analyst01, admin01, auditor01, and maintainer01.

The browser uses Authorization Code with PKCE and a cryptographically random state value. It keeps the access token in memory and removes callback query values from the address bar. API Gateway's Cognito user-pool authorizer validates the bearer token and forwards its claims to the private API Lambda. The Lambda accepts those claims only from the API Gateway authorizer context, then checks issuer, client, token type, expiry and exactly one supported group before reading account assignments by Cognito subject. Cognito group membership maps to existing application roles only. The account-scope table is independently required; missing, disabled, mismatched or malformed mappings fail closed. Existing application RBAC remains the authority for operations.

| Cognito group | Existing application role |
| --- | --- |
| Analysts | Risk/Compliance Analyst |
| Administrators | Admin |
| Auditors | Read-only/Auditor |
| Maintainers | Maintainer |

Switch user clears in-memory workspace state, ends the Cognito hosted session, and returns to sign-in. Local mode retains the existing hashed-token registry and does not require Cognito. The existing Admin user-management screens remain local-registry administration; cloud Cognito provisioning uses the separate operator command until a reviewed cloud-admin workflow is implemented.

## Deployment sequence and cost review

The API template now protects `/v1/{proxy+}` GET/POST routes with a Cognito user-pool authorizer and requires the `openid` scope. Only health/auth configuration, OPTIONS preflight, root workbench, and static asset routes are public. The Lambda invoke permission is scoped to the named API stage. No public JWKS access, NAT or endpoint is needed.

The OAuth callback/API-ID dependency is resolved without replacing the API: create the API stack initially from `infrastructure/api/gateway-shell.json`, record its `CallbackUrl`, create the Cognito stack with that exact callback and logout URL, then update the same API stack with `infrastructure/api/gateway.json`, the exact `UserPoolArn`, API alias and stage. Both API templates use the same logical resource ID `Api`, preserving its ID. Do not leave the shell as the final deployment or create a second API. This integration remains un-deployed until AWS CloudFormation validation, reviewed change sets and live authentication tests pass.

The current Release 1 database checkpoint remains a gate: inspect live RDS catalog/migration state using the approved private runner and reconcile schema/runtime grants before deploying API/scoring/report Lambdas. Do not deploy the standalone Cognito stack ahead of that sequence. See `infrastructure/RELEASE1_CONTROLLED_PREFLIGHT_PLAN.md`.

The template explicitly selects Cognito Lite, enables authenticator-app MFA rather than SMS, and does not enable the separately billed advanced security features. Cognito user pools bill by monthly active users; the AWS pricing page currently lists 10,000 monthly active users per account or organization per month as a free tier for Lite and Essentials, with usage above that tier billed. Confirm current regional pricing and the account's eligibility before change approval. DynamoDB on-demand reads/writes and point-in-time recovery can add usage and storage charges. No exact total is claimed without measured usage, regional price, and the account's existing free-tier usage. [AWS Cognito pricing](https://aws.amazon.com/cognito/pricing/), [Cognito cost monitoring](https://docs.aws.amazon.com/cognito/latest/developerguide/tracking-cost.html).

## Local verification

Local cryptographic tests use generated disposable RSA keys and mocked JWKS/account-scope lookups. They do not call Cognito or AWS. Existing local role and browser workflows must continue to pass. Cloud sign-in and the proposed CloudFormation have not been validated against a deployed pool. Exact-source Linux verification remains a separate release gate.
