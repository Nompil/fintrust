import os
from functools import lru_cache
from typing import Any

import boto3

AWS_REGION = os.getenv("AWS_REGION", "af-south-1")
ssm = boto3.client("ssm", region_name=AWS_REGION)


def get_setting(name: str, default: Any = None, *, required: bool = False) -> Any:
    value = os.getenv(name, default)
    if required and value in (None, ""):
        raise RuntimeError(f"Missing required environment setting: {name}")
    return value


@lru_cache(maxsize=1)
def load_settings() -> dict:
    parameter_names = {
        "db_host": "/fintrust/dev/db_host",
        "db_name": "/fintrust/dev/db_name",
        "db_user": "/fintrust/dev/db_user",
        "db_password": "/fintrust/dev/db_password",
    }
    settings = {
        "aws_region": AWS_REGION,
        "s3_raw_bucket": get_setting("S3_RAW_BUCKET", "fintrust-ingest-dev"),
        "s3_report_bucket": get_setting("S3_REPORT_BUCKET", "fintrust-reports"),
        "dynamodb_table": get_setting("DYNAMODB_TABLE", "risk_scores"),
        "db_port": int(get_setting("DB_PORT", 5432)),
    }
    for setting, parameter in parameter_names.items():
        environment_value = os.getenv(setting.upper())
        if environment_value:
            settings[setting] = environment_value
            continue
        response = ssm.get_parameter(Name=parameter, WithDecryption=True)
        settings[setting] = response["Parameter"]["Value"]
    return settings
