# Automated quota guidance assessment

Date: 16 October 2026 SAST.

The owner supplied the automated Support interaction response, retained verbatim
in aws-support-automated-quota-guidance.txt. It contains no case ID, approval,
or evidence of an applied quota change. No quota mutation was performed.

The response recommends 101 or 105 by applying the standard documented
100-unit unreserved floor. The actual retained CloudFormation error instead
reports a minimum of [10] for this reduced-quota account. This discrepancy must
be confirmed by the quota team; neither 101 nor 105 is an account-verified target.

The recommendation also does not resolve the observed Service Quotas validator
that rejects requested values not greater than the published default of 1,000.
Only 11 was actually attempted and rejected; 101/105 have not been attempted.
The response's Bedrock article is not evidence of this Lambda account's behavior.

Next: request manual quota review through Create a case, identify the actual
10-unit floor and below-default request rejection, and request confirmation of
the minimum supported target for one temporary reserved slot and then five
application slots. Preserve the owner's instruction against an unapproved 1,001
request, paid support upgrade, resource creation, or live migration activation.

The documentation supports standard behavior, not this account's exception:
https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html
https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html

Status: quota gate unresolved; case submission/ID not yet confirmed.
