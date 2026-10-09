"""Pinned, nonsecret deployment targets. Invocation input cannot override them."""
from pathlib import Path
REGION = "af-south-1"
HOST = "fintrust-ledger-dev.cv84aee6u6up.af-south-1.rds.amazonaws.com"
PORT = 5432
DATABASE = "fintrust"
MASTER = "fintrust_admin"
USER = "fintrust_migrate_dev"
OWNER = "fintrust_transactions_owner"
SECRET = "arn:aws:secretsmanager:af-south-1:966467878406:secret:rds!db-e93012ae-0d14-4225-bdc3-988f4d98f72a-BbEGMn"
ROOT = Path(__file__).resolve().parents[1]
CA = ROOT / "certs/global-bundle.pem"
TABLES = ("customers", "accounts", "transactions", "risk_events", "alerts", "processed_transactions")
