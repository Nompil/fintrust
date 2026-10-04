"""CSV admission checks. Risk rules live in fintrust.rules."""
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

    for field in ("transaction_id", "tx_id"):
        if field in row:
            try:
                uuid.UUID((row[field] or "").strip())
            except (ValueError, AttributeError):
                return f"{field} must be a UUID"
    if row.get("transaction_id") and row.get("tx_id"):
        if uuid.UUID(row["transaction_id"].strip()) != uuid.UUID(row["tx_id"].strip()):
            return "transaction_id and tx_id disagree"
    country = (row.get("country") or "ZA").strip().upper()
    if len(country) != 2 or not country.isascii() or not country.isalpha():
        return "country must be a two-letter country code"
    if len((row.get("merchant") or "").strip()) > 200:
        return "merchant exceeds 200 characters"
    return None


def parse_transaction_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def validate_transaction_record(record: dict) -> tuple[bool, str | None]:
    error = validate_row(record)
    return error is None, error
