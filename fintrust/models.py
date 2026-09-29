from dataclasses import dataclass, asdict
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class Transaction:
    account_id: str
    transaction_id: str
    tx_date: str
    amount: Decimal
    transaction_type: str
    channel: str
    merchant_name: str = ""
    country: str = "ZA"
    currency: str = "ZAR"
    risk_score: int = 0
    reason_codes: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Transaction":
        return cls(
            account_id=str(payload.get("account_id", "")).strip(),
            transaction_id=str(payload.get("transaction_id", "")).strip(),
            tx_date=str(payload.get("tx_date", "")).strip(),
            amount=Decimal(str(payload.get("amount", "0"))),
            transaction_type=str(payload.get("transaction_type", "")).strip(),
            channel=str(payload.get("channel", "")).strip(),
            merchant_name=str(payload.get("merchant_name", "")).strip(),
            country=str(payload.get("country", "ZA")).strip() or "ZA",
            currency=str(payload.get("currency", "ZAR")).strip() or "ZAR",
            risk_score=int(payload.get("risk_score", 0) or 0),
            reason_codes=str(payload.get("reason_codes", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["amount"] = str(self.amount)
        return data


@dataclass
class RiskScore:
    account_id: str
    transaction_id: str
    score: int
    risk_level: str
    decision: str
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "account_id": self.account_id,
            "transaction_id": self.transaction_id,
            "score": self.score,
            "risk_level": self.risk_level,
            "decision": self.decision,
        }
        if self.updated_at:
            payload["updated_at"] = self.updated_at.isoformat()
        return payload
