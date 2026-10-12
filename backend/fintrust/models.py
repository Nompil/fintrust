"""Data shapes matching the ledger and daily score store."""
from dataclasses import dataclass, asdict
from datetime import datetime
from decimal import Decimal


@dataclass
class Transaction:
    tx_id: str
    account_id: str
    amount: Decimal
    currency: str
    tx_date: datetime
    tx_type: str
    cross_border: bool
    raw_file: str
    merchant: str | None = None
    source_system: str | None = None
    source_transaction_id: str | None = None
    transaction_fingerprint: str | None = None
    batch_id: str | None = None
    file_sha256: str | None = None
    source_row: int | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["amount"] = str(self.amount)
        data["tx_date"] = self.tx_date.isoformat()
        return data


@dataclass
class RiskScore:
    account_id: str
    score_date: str
    risk_score: int
    flags: list[str]
    calculated_at: str
    ttl: int

    def to_dict(self) -> dict:
        return asdict(self)
