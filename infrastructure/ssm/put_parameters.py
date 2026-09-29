import os

import boto3

REGION = os.getenv("AWS_REGION", "af-south-1")
ssm = boto3.client("ssm", region_name=REGION)


def store_parameters() -> None:
    parameter_values = {
        "/fintrust/dev/db_host": os.getenv("FINTRUST_DB_HOST"),
        "/fintrust/dev/db_name": os.getenv("FINTRUST_DB_NAME", "fintrust"),
        "/fintrust/dev/db_user": os.getenv("FINTRUST_DB_USER"),
        "/fintrust/dev/db_password": os.getenv("FINTRUST_DB_PASSWORD"),
    }
    missing = [name for name, value in parameter_values.items() if not value]
    if missing:
        raise RuntimeError(
            "Set the corresponding FINTRUST_DB_* environment variables before running; "
            "do not put credentials in source control. Missing: " + ", ".join(missing)
        )

    for name, value in parameter_values.items():
        parameter_type = "SecureString" if name.endswith("db_password") else "String"
        ssm.put_parameter(
            Name=name,
            Value=value,
            Type=parameter_type,
            Overwrite=True,
        )
        print(f"Stored parameter {name} ({parameter_type})")


if __name__ == "__main__":
    store_parameters()
