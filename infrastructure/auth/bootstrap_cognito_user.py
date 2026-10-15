"""Explicit operator bootstrap for named Imbokodo Cognito test identities.

No cloud calls occur without --apply. Temporary passwords are read with getpass,
never accepted as command arguments, and never printed or written to disk.
"""
import argparse
import getpass
import re
import uuid

USERS = {"analyst01": "Analysts", "admin01": "Administrators",
         "auditor01": "Auditors", "maintainer01": "Maintainers"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", choices=sorted(USERS), required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--user-pool-id", required=True)
    parser.add_argument("--scope-table", required=True)
    parser.add_argument("--account", action="append", default=[], help="Assigned account UUID; repeat as needed.")
    parser.add_argument("--apply", action="store_true", help="Perform the explicitly requested Cognito/DynamoDB writes.")
    args = parser.parse_args()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", args.email):
        parser.error("Provide a valid operator-controlled user email")
    try:
        accounts = list(dict.fromkeys(str(uuid.UUID(value)) for value in args.account))
    except ValueError:
        parser.error("Every assigned account must be a UUID")
    if not accounts:
        parser.error("At least one explicitly assigned account UUID is required")
    if not args.apply:
        print(f"Dry run only: would create {args.username}, add group {USERS[args.username]}, and assign {len(accounts)} account(s). No AWS request was made.")
        return 0
    password = getpass.getpass("Temporary Cognito password (input hidden): ")
    if len(password) < 14 or not any(c.islower() for c in password) or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password) or not any(not c.isalnum() for c in password):
        parser.error("Temporary password does not satisfy the User Pool password policy")
    import boto3
    region = args.user_pool_id.split("_", 1)[0]
    cognito = boto3.client("cognito-idp", region_name=region)
    result = cognito.admin_create_user(UserPoolId=args.user_pool_id, Username=args.username,
        TemporaryPassword=password, MessageAction="SUPPRESS",
        UserAttributes=[{"Name": "email", "Value": args.email}, {"Name": "email_verified", "Value": "true"}])
    subject = next((a["Value"] for a in result["User"].get("Attributes", []) if a["Name"] == "sub"), None)
    if not subject:
        raise RuntimeError("Cognito did not return a subject; account scope was not written")
    cognito.admin_add_user_to_group(UserPoolId=args.user_pool_id, Username=args.username, GroupName=USERS[args.username])
    table = boto3.resource("dynamodb", region_name=region).Table(args.scope_table)
    table.put_item(Item={"subject": subject, "username": args.username, "status": "ACTIVE", "accounts": accounts},
                   ConditionExpression="attribute_not_exists(subject)")
    print(f"Created {args.username} in {USERS[args.username]} with {len(accounts)} account assignment(s). Temporary password was not displayed or saved; MFA enrollment is required at first sign-in.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
