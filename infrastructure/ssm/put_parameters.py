"""Render nonsecret DB parameters; --apply is a separate live operator action."""
import argparse
import json
import os


def build_parameters():
    service = os.environ["FINTRUST_SERVICE"]
    stage = os.getenv("FINTRUST_STAGE", "dev")
    if service not in {"scoring", "api", "report"} or stage not in {"dev", "staging", "prod"}:
        raise ValueError("Invalid service or stage")
    values = {"host": os.environ["FINTRUST_DB_HOST"], "name": os.getenv("FINTRUST_DB_NAME", "fintrust"),
              "user": f"fintrust_{service}_{stage}"}
    if not all(values.values()):
        raise ValueError("Database host and name cannot be empty")
    return [{"Name": f"/fintrust/{stage}/{service}/db_{name}", "Value": value,
             "Type": "String", "Overwrite": True} for name, value in values.items()]


def store_parameters():
    parameters = build_parameters()
    import boto3
    ssm = boto3.client("ssm", region_name=os.getenv("AWS_REGION", "af-south-1"))
    for parameter in parameters:
        ssm.put_parameter(**parameter)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write to AWS; requires separate deployment approval")
    args = parser.parse_args()
    if args.apply:
        store_parameters()
    else:
        print(json.dumps(build_parameters(), indent=2))
