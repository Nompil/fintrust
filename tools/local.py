"""Local learning commands. Run from the project root: py tools/local.py --help."""
import argparse
from contextlib import contextmanager
from datetime import date, datetime, timezone
from getpass import getpass
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATABASE = "fintrust_local"
TEST_DATABASE = "fintrust_local_test"
ROLE = "fintrust_local_app"
ACCOUNT = "20000000-0000-4000-8000-000000000001"


def local_settings():
    from dotenv import dotenv_values
    values = dotenv_values(ROOT / ".env")
    if values.get("DB_HOST") not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Local commands require DB_HOST=127.0.0.1 in .env. Run setup first.")
    if values.get("DB_NAME") != DATABASE or values.get("DB_USER") != ROLE:
        raise ValueError("Local commands use fintrust_local and fintrust_local_app. Run setup first.")
    if not values.get("DB_PASSWORD"):
        raise ValueError("The local database password is missing. Run setup first.")
    return values


def connect(values, *, testing=False):
    import psycopg2
    return psycopg2.connect(
        host=values["DB_HOST"], port=values.get("DB_PORT", "5432"),
        dbname=TEST_DATABASE if testing else DATABASE,
        user=ROLE, password=values["DB_PASSWORD"], connect_timeout=5,
    )


def setup():
    """Create two dedicated databases without changing the existing postgres user."""
    import psycopg2
    from psycopg2 import sql
    from dotenv import dotenv_values
    env_path = ROOT / ".env"
    saved = dotenv_values(env_path) if env_path.exists() else {}
    if saved and (saved.get("DB_NAME") != DATABASE or saved.get("DB_USER") != ROLE):
        raise ValueError("Existing .env belongs to another setup and was left unchanged. Rename it yourself before setup.")
    port = input("Local PostgreSQL port [5432]: ").strip() or "5432"
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ValueError("Port must be an integer from 1 to 65535.")
    admin_user = input("PostgreSQL administrator username [postgres]: ").strip() or "postgres"
    admin_password = getpass("PostgreSQL administrator password (hidden): ")
    admin = psycopg2.connect(host="127.0.0.1", port=port, dbname="postgres",
        user=admin_user, password=admin_password, connect_timeout=5)
    admin.autocommit = True
    app_password = saved.get("DB_PASSWORD") or secrets.token_urlsafe(32)
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (ROLE,))
            exists = bool(cur.fetchone())
            if exists and not saved.get("DB_PASSWORD"):
                raise ValueError("The dedicated role already exists without matching .env settings. No password was changed.")
            if not exists:
                cur.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE").format(sql.Identifier(ROLE)), (app_password,))
            # Save generated app credentials for a resumable setup; never save admin credentials.
            from dotenv import set_key
            for key, value in {
                "FINTRUST_MODE": "local", "AWS_REGION": "af-south-1",
                "DYNAMODB_TABLE": "risk_scores", "DB_HOST": "127.0.0.1",
                "DB_PORT": port, "DB_NAME": DATABASE, "DB_USER": ROLE,
                "DB_PASSWORD": app_password,
            }.items():
                set_key(str(env_path), key, value)
            for name in (DATABASE, TEST_DATABASE):
                cur.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s", (name,))
                owner = cur.fetchone()
                if owner and owner[0] != ROLE:
                    raise ValueError(f"{name} belongs to another owner and was left unchanged.")
                if not owner:
                    cur.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(name), sql.Identifier(ROLE)))
    finally:
        admin.close()
    values = local_settings()
    conn = connect(values)
    try:
        with conn.cursor() as cur:
            for name in ("schema.sql", "seed.sql", "views.sql", "procedure.sql"):
                cur.execute((ROOT / "sql" / name).read_text(encoding="utf-8"))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print("Setup complete. App credentials saved in ignored .env; administrator password was not saved.")
    print(f"Practice database: {DATABASE}; separate test database: {TEST_DATABASE}.")
    check()


def check():
    conn = connect(local_settings())
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user")
            database, user = cur.fetchone()
            print(f"Connected: {database} as {user}")
            cur.execute("SELECT count(*), count(DISTINCT account_id) FROM transactions")
            rows, accounts = cur.fetchone()
            print(f"Transactions: {rows}; accounts with transactions: {accounts}")
            print("Expected after first setup: 200 transactions across 5 accounts.")
    finally:
        conn.close()


def test(database=False):
    environment = os.environ.copy()
    environment.pop("FINTRUST_TEST_DATABASE_URL", None)
    environment.update(AWS_ACCESS_KEY_ID="testing", AWS_SECRET_ACCESS_KEY="testing",
        AWS_SESSION_TOKEN="testing", AWS_DEFAULT_REGION="af-south-1",
        AWS_EC2_METADATA_DISABLED="true")
    if database:
        from psycopg2.extensions import make_dsn
        values = local_settings()
        environment["FINTRUST_TEST_DATABASE_URL"] = make_dsn(
            host=values["DB_HOST"], port=values.get("DB_PORT", "5432"),
            dbname=TEST_DATABASE, user=ROLE, password=values["DB_PASSWORD"], connect_timeout=5)
        print(f"Database tests use only {TEST_DATABASE}.", flush=True)
    # Each run owns its scratch space; do not reuse pytest-of-<user> across
    # Windows accounts or sandbox sessions with different folder permissions.
    temp_root = Path(tempfile.gettempdir()).resolve()
    with tempfile.TemporaryDirectory(prefix="fintrust-tests-", dir=temp_root) as run_temp:
        scratch = Path(run_temp).resolve()
        if scratch.parent != temp_root:
            raise RuntimeError("Test scratch directory is outside the temporary folder")
        return subprocess.call(
            [sys.executable, "-m", "pytest", "-q", "--basetemp", str(scratch / "pytest"),
             "-o", f"cache_dir={scratch / 'cache'}"],
            cwd=ROOT, env=environment,
        )


@contextmanager
def local_services():
    """Real local PostgreSQL; in-process fake AWS services. No AWS credentials required."""
    values = local_settings()
    os.environ.update({k: str(v) for k, v in values.items() if v is not None and (k.startswith("DB_") or k in {"FINTRUST_MODE", "AWS_REGION", "DYNAMODB_TABLE"})})
    os.environ.update(AWS_ACCESS_KEY_ID="testing", AWS_SECRET_ACCESS_KEY="testing",
        AWS_SESSION_TOKEN="testing", AWS_DEFAULT_REGION="af-south-1",
        AWS_EC2_METADATA_DISABLED="true")
    # Ignore externally configured service URLs; Moto must intercept ordinary AWS endpoints.
    for key in list(os.environ):
        if key.startswith("AWS_ENDPOINT_URL"):
            os.environ.pop(key)
    os.environ["AWS_IGNORE_CONFIGURED_ENDPOINT_URLS"] = "true"
    from moto import mock_aws
    from unittest.mock import patch
    import boto3
    from botocore.httpsession import URLLib3Session
    with mock_aws():
        from fintrust import config, dynamo, ingest
        config.load_settings.cache_clear()
        # Replace clients imported before Moto (for example during pytest collection).
        with patch.object(ingest, "s3", boto3.client("s3", region_name="af-south-1")), \
             patch.object(dynamo, "dynamodb", boto3.resource("dynamodb", region_name="af-south-1")), \
             patch.object(URLLib3Session, "send", side_effect=RuntimeError("Local practice blocked an unmocked AWS request")):
            try:
                yield
            finally:
                config.load_settings.cache_clear()


def ingest_sample():
    with local_services():
        from fintrust import ingest
        bucket = "fintrust-local-practice"
        ingest.s3.create_bucket(Bucket=bucket,
            CreateBucketConfiguration={"LocationConstraint": "af-south-1"})
        counts = ingest.process_csv(bucket, "raw/transactions_day2.csv",
            (ROOT / "samples/transactions_day2.csv").read_text(encoding="utf-8"),
            "local-practice:transactions_day2:v1")
        print(json.dumps(counts, indent=2))
        output = ROOT / "output/local"
        output.mkdir(parents=True, exist_ok=True)
        quarantined = []
        for item in ingest.s3.list_objects_v2(Bucket=bucket, Prefix="quarantine/").get("Contents", []):
            quarantined.append(ingest.s3.get_object(Bucket=bucket, Key=item["Key"])["Body"].read().decode())
        (output / "quarantine.jsonl").write_text("".join(quarantined), encoding="utf-8")
        print("Real local database updated; fake S3 quarantine copied to output/local/quarantine.jsonl.")
        print("Expected: 4 received, 2 valid, 2 quarantined (50%). Replay should not add more rows.")


def serve():
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    check()
    with local_services():
        import boto3
        os.environ["FINTRUST_LOCAL_DEMO"] = "1"
        boto3.client("s3", region_name="af-south-1").create_bucket(
            Bucket="fintrust-local-practice", CreateBucketConfiguration={"LocationConstraint": "af-south-1"})
        table = boto3.resource("dynamodb", region_name="af-south-1").create_table(
            TableName=os.environ.get("DYNAMODB_TABLE", "risk_scores"),
            KeySchema=[{"AttributeName": "account_id", "KeyType": "HASH"},
                {"AttributeName": "score_date", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": k, "AttributeType": "S"}
                for k in ("account_id", "score_date")], BillingMode="PAY_PER_REQUEST")
        table.put_item(Item={"account_id": ACCOUNT, "score_date": date.today().isoformat(),
            "risk_score": 45, "flags": ["practice_fixture"],
            "calculated_at": datetime.now(timezone.utc).isoformat(), "ttl": 9999999999})
        from fintrust.api import app
        print("LOCAL PRACTICE: real PostgreSQL + temporary mocked DynamoDB.")
        print("The example score is preloaded, not calculated. Stop with Ctrl+C.")
        print("Dashboard: http://127.0.0.1:5000/")
        print(f"http://127.0.0.1:5000/v1/insights?account_id={ACCOUNT}")
        app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["setup", "check", "test", "ingest", "serve"])
    parser.add_argument("--database", action="store_true", help="Include the dedicated local PostgreSQL test database")
    args = parser.parse_args()
    if args.database and args.command != "test":
        parser.error("--database is only valid with test")
    try:
        if args.command == "test":
            return test(args.database)
        {"setup": setup, "check": check, "ingest": ingest_sample, "serve": serve}[args.command]()
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130
    except Exception as error:
        import psycopg2
        if isinstance(error, psycopg2.OperationalError):
            print("Database connection failed. Check PostgreSQL is running, the port, username and password.")
        elif isinstance(error, psycopg2.Error):
            print(f"Database command failed ({error.pgcode or type(error).__name__}). Check the local guide.")
        else:
            print(f"{type(error).__name__}: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
