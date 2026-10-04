"""Monthly UTC reports; deterministic keys make a scheduled retry replace outputs."""
import csv
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import boto3
from .db import run_query
from .config import AWS_REGION

s3 = boto3.client("s3", region_name=AWS_REGION)
SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "monthly_summary.sql"


def month_bounds(month=None, now=None):
    now = now or datetime.now(timezone.utc)
    if month is None:
        first = now.astimezone(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        year, number = (first.year - 1, 12) if first.month == 1 else (first.year, first.month - 1)
    else:
        parsed = datetime.strptime(month, "%Y-%m")
        if parsed.strftime("%Y-%m") != month:
            raise ValueError("month must be YYYY-MM")
        year, number = parsed.year, parsed.month
    start = datetime(year, number, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if number == 12 else datetime(year, number + 1, 1, tzinfo=timezone.utc)
    return start, end


def generate_monthly_report(month=None, now=None):
    start, end = month_bounds(month, now)
    # Reuse the required window-function artefact. Filter after the window so the
    # running movement retains prior history; no mixed-currency arithmetic.
    base = SQL_PATH.read_text(encoding="utf-8").strip().rstrip(";")
    rows = run_query("SELECT * FROM (" + base + ") AS movement WHERE tx_date >= %s AND tx_date < %s "
                     "ORDER BY account_id,currency,tx_date,tx_id", (start, end))
    for row in rows:
        row["tx_date"] = row["tx_date"].astimezone(timezone.utc).isoformat()
    columns = ["account_id", "currency", "tx_date", "tx_id", "signed_amount", "running_balance"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    label = start.strftime("%Y-%m")
    payload = {"month": label, "timezone": "UTC", "start_inclusive": start.isoformat(),
               "end_exclusive": end.isoformat(), "count": len(rows), "transactions": rows}
    bucket = os.environ["S3_REPORT_BUCKET"]
    prefix = f"monthly/{label}/transactions"
    for suffix, body, content_type in (
        ("csv", output.getvalue(), "text/csv"),
        ("json", json.dumps(payload, default=str), "application/json")):
        s3.put_object(Bucket=bucket, Key=f"{prefix}.{suffix}", Body=body.encode("utf-8"), ContentType=content_type)
    return {"month": label, "rows": len(rows), "bucket": bucket,
            "keys": [f"{prefix}.csv", f"{prefix}.json"]}


def lambda_handler(event, context):
    # Scheduled event time, not retry wall-clock time, determines the previous month.
    when = datetime.fromisoformat(event["time"].replace("Z", "+00:00")) if event.get("time") else None
    return generate_monthly_report(event.get("month"), when)
