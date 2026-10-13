"""Deterministic investigation-priority components; never a fraud probability.

V2 amounts contribute once in transaction currency (no FX). Velocity retains
the closed 300-second event-time window including the current accepted entry.
SQL stores the full result once; replay returns it without evaluating again.
"""
import os
from dataclasses import dataclass
from decimal import Decimal
from datetime import timedelta
from .validators import parse_transaction_date

RULE_VERSION = "fintrust-r2-rules-2026-10-13"


@dataclass(frozen=True)
class ScoringConfig:
    high_amount: Decimal = Decimal("50000")
    middle_amount: Decimal = Decimal("100000")
    very_high_amount: Decimal = Decimal("200000")
    amount_points: int = 15
    middle_points: int = 25
    very_high_points: int = 40
    cross_border_points: int = 15
    velocity_count: int = 5
    velocity_seconds: int = 300
    velocity_points: int = 25
    duplicate_charge_seconds: int = 120
    duplicate_charge_points: int = 20
    medium: int = 20
    high: int = 40

    def __post_init__(self):
        limits = (self.high_amount, self.middle_amount, self.very_high_amount)
        if (not all(x.is_finite() for x in limits)
                or not 0 < self.high_amount < self.middle_amount < self.very_high_amount
                or not 0 < self.medium < self.high <= 100
                or self.velocity_count < 1 or self.velocity_seconds < 1
                or self.duplicate_charge_seconds < 1):
            raise ValueError("Invalid scoring thresholds")
        points = (self.amount_points, self.middle_points, self.very_high_points,
                  self.cross_border_points, self.velocity_points, self.duplicate_charge_points)
        if any(type(x) is not int or not 0 <= x <= 100 for x in points):
            raise ValueError("Rule points must be integer values between 0 and 100")
        if not self.amount_points <= self.middle_points <= self.very_high_points:
            raise ValueError("Amount component points must increase with the band")

    @classmethod
    def from_env(cls):
        defaults = cls()
        return cls(**{name: type(getattr(defaults, name))(os.getenv("RISK_" + name.upper(),
                             str(getattr(defaults, name)))) for name in cls.__dataclass_fields__})


def evaluate(record, velocity=1, config=None, *, duplicate_matches=(),
             duplicate_evidence=(), velocity_evidence=None, evaluated_at=None):
    cfg = config or ScoringConfig.from_env()
    amount = Decimal(str(record["amount"]))
    # Zero can be assessed in rule unit checks; CSV/ledger admission still rejects it.
    if not amount.is_finite() or amount < 0:
        raise ValueError("amount must be finite and nonnegative")
    if type(velocity) is not int or velocity < 1:
        raise ValueError("Accepted transaction count must be a positive integer")
    components = []

    def component(name, label, active, points, value, threshold, reason, **evidence):
        result = {"rule": name, "label": label, "triggered": bool(active),
                  "points": points if active else 0, "triggered_value": value,
                  "threshold": threshold, "reason": reason, "context": reason,
                  "evaluated_at": evaluated_at, "rule_version": RULE_VERSION, **evidence}
        components.append(result)
        return result

    if amount > cfg.very_high_amount:
        lower, upper, points = cfg.very_high_amount, None, cfg.very_high_points
    elif amount > cfg.middle_amount:
        lower, upper, points = cfg.middle_amount, cfg.very_high_amount, cfg.middle_points
    elif amount > cfg.high_amount:
        lower, upper, points = cfg.high_amount, cfg.middle_amount, cfg.amount_points
    else:
        lower, upper, points = Decimal("0"), cfg.high_amount, 0
    band = {"lower": str(lower), "lower_inclusive": points == 0,
            "upper": str(upper) if upper is not None else None, "upper_inclusive": True}
    description = (f"Amount greater than {lower} and at most {upper} in transaction currency"
                   if upper is not None and points else
                   f"Amount at most {upper} in transaction currency" if not points else
                   f"Amount greater than {lower} in transaction currency")
    component("AMOUNT_RISK", "Amount risk", points > 0, points, str(amount), band, description,
              currency=record.get("currency"), amount_band=band)

    country = record.get("country", "ZA")
    cross_border = country != "ZA" or record.get("cross_border") is True
    component("CROSS_BORDER", "Cross-border", cross_border, cfg.cross_border_points,
              country, "ZA", "Transaction country differs from ZA" if country != "ZA" else
              "Explicit cross-border flag" if cross_border else "Transaction country matches ZA",
              domestic_country="ZA", explicit_cross_border=record.get("cross_border") is True)

    window = dict(velocity_evidence or {})
    timestamp = record.get("transaction_timestamp") or record.get("tx_date")
    if timestamp:
        when = parse_transaction_date(timestamp)
        window.update(window_start=(when-timedelta(seconds=cfg.velocity_seconds)).isoformat(),
                      window_end=when.isoformat())
    component("HIGH_VELOCITY", "High velocity", velocity > cfg.velocity_count,
              cfg.velocity_points, velocity, cfg.velocity_count,
              f"{velocity} accepted transactions within {cfg.velocity_seconds} seconds; threshold more than {cfg.velocity_count}",
              account_id=record.get("account_id"), window_seconds=cfg.velocity_seconds,
              comparison="greater than", includes_current=True, closed_window=True, **window)

    matches = list(duplicate_matches)
    component("POSSIBLE_DUPLICATE_CHARGE", "Possible duplicate", bool(matches),
              cfg.duplicate_charge_points, len(matches), cfg.duplicate_charge_seconds,
              "Distinct source references match account/merchant/amount/currency within the configured time window",
              matching_transaction_ids=matches, matching_transactions=list(duplicate_evidence),
              matching_fields=["account_id", "merchant", "amount", "currency", "source_system", "tx_type"],
              distinct_source_references=True, window_seconds=cfg.duplicate_charge_seconds,
              comparison="at most; either side of event time", match_limit=20)
    score = min(sum(c["points"] for c in components), 100)
    return {"rule_version": RULE_VERSION, "evaluated_at": evaluated_at,
            "score": score, "risk_level": classify_risk(score, cfg), "components": components,
            "triggered_rules": [dict(c) for c in components if c["triggered"]]}


def classify_risk(score, config=None):
    cfg = config or ScoringConfig.from_env()
    if isinstance(score, bool) or not Decimal(str(score)).is_finite() or not 0 <= score <= 100:
        raise ValueError("Risk score must be between 0 and 100")
    return "High" if score >= cfg.high else "Medium" if score >= cfg.medium else "Low"


def compute_risk_score(record):
    return evaluate(record)["score"]
