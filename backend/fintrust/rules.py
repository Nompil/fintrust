"""Configurable teaching rules, pending facilitator approval (not a bank model).

Amount thresholds are per transaction currency, with no implied FX conversion.
Velocity counts accepted transactions including the current one in the closed
event-time window. Late arrivals do not retroactively rescore earlier decisions.
"""
import os
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ScoringConfig:
    high_amount: Decimal = Decimal("50000")
    very_high_amount: Decimal = Decimal("200000")
    amount_points: int = 30
    very_high_points: int = 25
    transfer_points: int = 20
    cross_border_points: int = 15
    merchant_points: int = 20
    velocity_count: int = 5
    velocity_seconds: int = 300
    velocity_points: int = 30
    duplicate_charge_seconds: int = 120
    duplicate_charge_points: int = 40
    medium: int = 40
    high: int = 70

    def __post_init__(self):
        if (not self.high_amount.is_finite() or not self.very_high_amount.is_finite()
                or not 0 < self.high_amount < self.very_high_amount
                or not 0 < self.medium < self.high <= 100
                or self.velocity_count < 1 or self.velocity_seconds < 1 or self.duplicate_charge_seconds < 1):
            raise ValueError("Invalid scoring thresholds")
        if any(not 0 <= getattr(self, name) <= 100 for name in (
                "amount_points", "very_high_points", "transfer_points", "cross_border_points",
                "merchant_points", "velocity_points", "duplicate_charge_points")):
            raise ValueError("Rule points must be between 0 and 100")

    @classmethod
    def from_env(cls):
        defaults = cls()
        return cls(**{name: type(getattr(defaults, name))(os.getenv("RISK_" + name.upper(),
                             str(getattr(defaults, name)))) for name in cls.__dataclass_fields__})


def evaluate(record, velocity=1, config=None, *, duplicate_matches=()):
    cfg = config or ScoringConfig.from_env()
    amount = Decimal(str(record["amount"]))
    if not amount.is_finite() or amount <= 0:
        raise ValueError("amount must be finite and positive")
    rules = []
    def add(name, points, reason):
        evidence={
            "HIGH_AMOUNT":(str(amount),str(cfg.high_amount),"greater than; transaction currency"),
            "VERY_HIGH_AMOUNT":(str(amount),str(cfg.very_high_amount),"greater than; transaction currency"),
            "HIGH_VELOCITY":(velocity,cfg.velocity_count,f"greater than; closed {cfg.velocity_seconds}-second event-time window including current transaction"),
            "CROSS_BORDER":(record.get("country","ZA"),"ZA","country differs from ZA or explicit cross-border flag"),
            "POSSIBLE_DUPLICATE_CHARGE":(len(duplicate_matches),cfg.duplicate_charge_seconds,"distinct source references; matching account/merchant/amount/currency; seconds window"),
            "TRANSFER":(record.get("transaction_type",record.get("tx_type")),"transfer","outgoing transfer"),
            "MERCHANT_MARKER":(record.get("merchant"),"highrisk","synthetic merchant marker"),
        }
        value,threshold,context=evidence[name]
        rules.append({"rule":name,"points":points,"reason":reason,"triggered_value":value,"threshold":threshold,"context":context})
    if amount > cfg.high_amount:
        add("HIGH_AMOUNT", cfg.amount_points, f"Amount exceeds {cfg.high_amount} in transaction currency")
    if amount > cfg.very_high_amount:
        add("VERY_HIGH_AMOUNT", cfg.very_high_points, f"Amount exceeds {cfg.very_high_amount} in transaction currency")
    if record.get("transaction_type", record.get("tx_type")) == "transfer":
        add("TRANSFER", cfg.transfer_points, "Outgoing transfer")
    if record.get("country", "ZA") != "ZA" or record.get("cross_border") is True:
        add("CROSS_BORDER", cfg.cross_border_points, "Transaction country differs from ZA")
    if "highrisk" in str(record.get("merchant", "")).lower():
        add("MERCHANT_MARKER", cfg.merchant_points, "Synthetic highrisk merchant marker")
    if velocity > cfg.velocity_count:
        add("HIGH_VELOCITY", cfg.velocity_points,
            f"{velocity} transactions in {cfg.velocity_seconds} seconds exceeds {cfg.velocity_count}")
    if duplicate_matches:
        add("POSSIBLE_DUPLICATE_CHARGE", cfg.duplicate_charge_points,
            f"Distinct source references match merchant/amount/currency within {cfg.duplicate_charge_seconds} seconds")
        rules[-1]["matching_transaction_ids"] = list(duplicate_matches)
        rules[-1]["window_seconds"] = cfg.duplicate_charge_seconds
    score = min(sum(rule["points"] for rule in rules), 100)
    return {"rule_version": "fintrust-r1-rules-2026-10-09", "score": score, "risk_level": classify_risk(score, cfg), "triggered_rules": rules}


def classify_risk(score, config=None):
    cfg = config or ScoringConfig.from_env()
    return "High" if score >= cfg.high else "Medium" if score >= cfg.medium else "Low"


def compute_risk_score(record):
    return evaluate(record)["score"]
