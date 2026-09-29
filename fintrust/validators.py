from decimal import Decimal, InvalidOperation


ALLOWED_CHANNELS = {"online", "branch", "atm", "mobile", "card"}
ALLOWED_TYPES = {"debit", "credit", "transfer", "withdrawal", "payment"}
ALLOWED_CURRENCIES = {"ZAR", "USD", "EUR"}


def validate_transaction_record(record: dict) -> tuple[bool, str | None]:
    required = [
        "account_id",
        "transaction_id",
        "tx_date",
        "amount",
        "transaction_type",
        "channel",
    ]

    for field in required:
        if record.get(field) in (None, ""):
            return False, f"Missing required field: {field}"

    try:
        amount = Decimal(str(record["amount"]))
    except (InvalidOperation, TypeError, ValueError):
        return False, "amount must be numeric"

    if amount <= 0:
        return False, "amount must be greater than zero"

    if record["transaction_type"].lower() not in ALLOWED_TYPES:
        return False, "invalid transaction_type"

    if record["channel"].lower() not in ALLOWED_CHANNELS:
        return False, "invalid channel"

    if record.get("currency", "ZAR").upper() not in ALLOWED_CURRENCIES:
        return False, "invalid currency code"

    if len(str(record["account_id"]).strip()) < 3:
        return False, "account_id too short"

    return True, None


def compute_risk_score(record: dict) -> int:
    score = 0
    amount = Decimal(str(record.get("amount", "0")))

    if amount > Decimal("50000"):
        score += 30
    if amount > Decimal("200000"):
        score += 25

    if str(record.get("transaction_type", "")).lower() in {"withdrawal", "transfer"}:
        score += 20

    if str(record.get("channel", "")).lower() in {"online", "mobile"}:
        score += 10

    if str(record.get("country", "ZA")).upper() != "ZA":
        score += 15

    if str(record.get("merchant_name", "")).lower().find("highrisk") >= 0:
        score += 20

    return min(score, 100)


def classify_risk(score: int) -> str:
    if score >= 70:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"
