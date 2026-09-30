"""Read-only AWS identity check; does not provision services or verify free usage."""
import argparse
import json

import boto3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, help="Existing approved AWS CLI profile")
    args = parser.parse_args()
    session = boto3.Session(profile_name=args.profile, region_name="af-south-1")
    identity = session.client("sts").get_caller_identity()
    print(json.dumps({"account": identity["Account"], "principal": identity["Arn"],
        "region": session.region_name, "resources_created": 0,
        "cost_review": "Billing plan, credit expiry, resource inventory and regional estimate still required"}, indent=2))


if __name__ == "__main__":
    main()
