"""A conflicting SDK default must not split the application's AWS clients."""
import os
from pathlib import Path
import subprocess
import sys


def test_runtime_clients_follow_application_region():
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("AWS_", "DB_", "FINTRUST_"))}
    environment.update(AWS_REGION="af-south-1", AWS_DEFAULT_REGION="eu-west-1",
                       AWS_ACCESS_KEY_ID="testing", AWS_SECRET_ACCESS_KEY="testing",
                       AWS_EC2_METADATA_DISABLED="true", DB_CONFIG_SOURCE="environment")
    script = '''
from fintrust import ingest, score, report, alert, alert_delivery, config, db, dynamo
clients = [ingest.s3, ingest.sqs, score.lambda_client, score.s3, report.s3,
           alert.ses, alert_delivery.ses, alert_delivery.dynamodb.meta.client,
           config.ssm, db.rds, dynamo.dynamodb.meta.client]
assert all(client.meta.region_name == "af-south-1" for client in clients)
'''
    result = subprocess.run([sys.executable, "-c", script], env=environment,
                            cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
