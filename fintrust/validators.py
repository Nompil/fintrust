"""Shared CSV validation; scoring rules remain an unapproved prototype."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import uuid

REQUIRED_COLUMNS = {"account_id", "amount", "tx_date", "tx_type"}
ALLOWED_CURRENCIES = {"ZAR", "USD", "EUR", "GBP", "KES"}


def validate_row(row: dict[str, str]) -> str | None:
    if None in row:
        return "row has more values than the CSV header"
    missing = [column for column in REQUIRED_COLUMNS if not (row.get(column) or "").strip()]
    if missing:
        return f"missing required field(s): {', '.join(sorted(missing))}"

    try:
        amount = Decimal(row["amount"])
    except (InvalidOperation, ValueError):
        return "amount must be numeric"
    if not amount.is_finite() or amount <= 0:
        return "amount must be greater than zero"
    if amount >= Decimal("10000000000000"):
        return "amount exceeds NUMERIC(15,2) capacity"
    if amount != amount.quantize(Decimal("0.01")):
        return "amount must have at most two decimal places"

    currency = (row.get("currency") or "ZAR").strip().upper() or "ZAR"
    if currency not in ALLOWED_CURRENCIES:
        return f"unsupported currency: {currency}"

    if row["tx_type"].strip().lower() not in {"debit", "credit", "transfer", "fee"}:
        return "unsupported tx_type"

    try:
        parse_transaction_date(row["tx_date"])
    except ValueError:
        return "tx_date must be a valid ISO-8601 date or timestamp"

    try:
        uuid.UUID(row["account_id"].strip())
    except ValueError:
        return "account_id must be a UUID present in the accounts table"

    return None


def parse_transaction_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def validate_transaction_record(record: dict) -> tuple[bool, str | None]:
    error = validate_row(record)
    return error is None, error


def compute_risk_score(record: dict) -> int:
    score = 0
    amount = Decimal(str(record.get("amount", "0")))

    if not amount.is_finite() or amount <= 0:
        raise ValueError("amount must be finite and positive")

    if amount > Decimal("50000"):
        score += 30
    if amount > Decimal("200000"):
        score += 25

    if str(record.get("tx_type", "")).lower() in {"withdrawal", "transfer"}:
        score += 20

    if record.get("cross_border", False):
        score += 15

    if str(record.get("merchant", "")).lower().find("highrisk") >= 0:
        score += 20

    return min(score, 100)


def classify_risk(score: int) -> str:
    if score >= 70:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"
