import os

import boto3
from botocore.exceptions import ClientError

REGION = os.getenv("AWS_REGION", "af-south-1")
BUCKET = os.getenv("FINTRUST_INGEST_BUCKET", "fintrust-ingest-dev")
s3 = boto3.client("s3", region_name=REGION)


def ensure_bucket() -> None:
    try:
        s3.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": REGION},
        )
        print(f"Created bucket {BUCKET}")
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        if code != "BucketAlreadyOwnedByYou":
            raise
        print(f"Bucket {BUCKET} already belongs to this account")

    s3.put_bucket_versioning(
        Bucket=BUCKET,
        VersioningConfiguration={"Status": "Enabled"},
    )
    s3.put_public_access_block(
        Bucket=BUCKET,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    s3.put_bucket_lifecycle_configuration(
        Bucket=BUCKET,
        LifecycleConfiguration={
            "Rules": [
                {
                    "ID": "archive-and-expire-raw-objects",
                    "Status": "Enabled",
                    "Filter": {"Prefix": "raw/"},
                    "Transitions": [{"Days": 90, "StorageClass": "GLACIER"}],
                    "Expiration": {"Days": 2555},
                    "NoncurrentVersionTransitions": [
                        {"NoncurrentDays": 90, "StorageClass": "GLACIER"}
                    ],
                    "NoncurrentVersionExpiration": {"NoncurrentDays": 2555},
                }
            ]
        },
    )
    print(f"Configured versioning, public access block, and lifecycle for {BUCKET}")


if __name__ == "__main__":
    ensure_bucket()
