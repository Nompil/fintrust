"""Executable Release 1 design contract; NOT wired into production handlers.
No database, network, AWS, or credential access. API integration remains future work.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import uuid

VERSION = "fintrust-r1-2026-10-09"
CURRENCIES = frozenset({"ZAR", "USD", "EUR", "GBP", "KES"})
# Explicit supported demo countries, not a claim to validate every ISO country.
COUNTRIES = frozenset({"ZA", "US", "GB", "KE", "DE", "FR"})
TYPES = frozenset({"debit", "credit", "transfer", "fee"})
REVIEW_TRANSITIONS = {
    "OPEN": {"UNDER_REVIEW"},
    "UNDER_REVIEW": {"CLEARED", "CONFIRMED_RISK", "ESCALATED"},
    "ESCALATED": {"UNDER_REVIEW"},
    "CLEARED": {"UNDER_REVIEW"},
    "CONFIRMED_RISK": {"UNDER_REVIEW"},
}

def validation_errors(row, received_at, *, known_account=True):
    if received_at.tzinfo is None:
        raise ValueError("Receipt clock must be timezone aware")
    errors=[]
    def add(code, detail): errors.append({"reason_code":code,"reason_detail":detail})
    if None in row or not all(isinstance(k,str) and isinstance(v,str) for k,v in row.items()):
        return [{"reason_code":"MALFORMED_ROW","reason_detail":"Named text fields required"}]
    required=("account_id","amount","tx_date","tx_type","currency","country")
    for name in required:
        if not row.get(name,"").strip(): add("MISSING_REQUIRED_FIELD",f"Missing {name}")
    if row.get("account_id","").strip():
        try: uuid.UUID(row["account_id"].strip())
        except ValueError: add("INVALID_ACCOUNT_ID","Account identifier must be UUID")
        else:
            if not known_account: add("UNKNOWN_ACCOUNT","Account is not in the ledger")
    raw=row.get("amount","").strip()
    if raw:
        try: amount=Decimal(raw)
        except InvalidOperation: add("INVALID_AMOUNT","Amount must be numeric")
        else:
            if not amount.is_finite(): add("INVALID_AMOUNT","Amount must be finite")
            elif amount==0: add("ZERO_AMOUNT","Amount must be positive")
            elif amount<0: add("NEGATIVE_AMOUNT","Amount must be positive")
            elif amount>=Decimal("10000000000000"): add("AMOUNT_OUT_OF_RANGE","Exceeds NUMERIC(15,2)")
            elif amount!=amount.quantize(Decimal("0.01")): add("AMOUNT_PRECISION","At most two decimal places")
    kind=row.get("tx_type","").strip().lower()
    if kind in {"refund","reversal","chargeback"}: add("UNSUPPORTED_FINANCIAL_OPERATION","Refunds, reversals and chargebacks are deferred")
    elif kind and kind not in TYPES: add("INVALID_TRANSACTION_TYPE","Unsupported transaction type")
    if row.get("currency","").strip() and row["currency"].strip().upper() not in CURRENCIES:
        add("UNSUPPORTED_CURRENCY","Currency is outside the release contract")
    country=row.get("country","").strip().upper()
    if country:
        if len(country)!=2 or not country.isascii() or not country.isalpha(): add("INVALID_COUNTRY","Two-letter country code required")
        elif country not in COUNTRIES: add("UNSUPPORTED_COUNTRY","Country is outside the approved demo list")
    if row.get("tx_date","").strip():
        try:
            import re
            raw=row["tx_date"].strip()
            if any(len(x)>6 for x in re.findall(r"[.,](\d+)",raw)): raise ValueError()
            when=datetime.fromisoformat(raw.replace("Z","+00:00"))
            if when.tzinfo is None or "T" not in raw: raise ValueError()
        except ValueError: add("INVALID_TIMESTAMP","Timezone-bearing ISO timestamp required; max microsecond precision")
        else:
            if when>received_at+timedelta(minutes=5): add("FUTURE_TIMESTAMP","More than five minutes after first receipt")
    namespace=row.get("source_system","").strip()
    reference=(row.get("source_transaction_id") or row.get("source_reference") or "").strip()
    if not namespace or not reference: add("MISSING_SOURCE_IDENTITY","Stable source system and transaction reference required")
    if len(namespace)>100 or len(reference)>200: add("INVALID_SOURCE_IDENTITY","Source identity exceeds storage bounds")
    if row.get("source_transaction_id") and row.get("source_reference") and row["source_transaction_id"].strip()!=row["source_reference"].strip():
        add("TRANSACTION_IDENTITY_CONFLICT","Source reference aliases disagree")
    for name in ("transaction_id","tx_id"):
        if name in row:
            try: uuid.UUID(row[name].strip())
            except ValueError: add("INVALID_TRANSACTION_ID","Supplied internal identity must be UUID")
    if row.get("transaction_id") and row.get("tx_id"):
        try:
            if uuid.UUID(row["transaction_id"].strip())!=uuid.UUID(row["tx_id"].strip()):
                add("TRANSACTION_IDENTITY_CONFLICT","Internal identity aliases disagree")
        except ValueError: pass
    if len(row.get("merchant","").strip())>200: add("INVALID_MERCHANT","Merchant exceeds 200 characters")
    return errors

def authorize(role, action):
    permissions={
        "Admin":{"read","review","correct","reject_quarantine","reopen","reconcile_alert","audit"},
        "Risk/Compliance Analyst":{"read","review","correct","reject_quarantine"},
        "Read-only/Auditor":{"read","audit"},
    }
    if action not in permissions.get(role,set()): raise PermissionError("Action is not authorized")

def review_transition(before, after, *, role, notes, resolution_code=None):
    authorize(role,"reopen" if before in {"CLEARED","CONFIRMED_RISK"} else "review")
    if after not in REVIEW_TRANSITIONS.get(before,set()): raise ValueError("Invalid review transition")
    if not notes.strip(): raise ValueError("Review note required")
    expected={"CLEARED":"VALID_ACTIVITY","CONFIRMED_RISK":"CONFIRMED_SUSPICIOUS","ESCALATED":"SPECIALIST_REVIEW"}
    if after in expected and resolution_code!=expected[after]: raise ValueError("Resolution code required")
    return after

def reconcile(outcomes, *, total, publication_complete, file_failure=False):
    allowed={"RECEIVED","QUEUED","ACCEPTED","QUARANTINED","DUPLICATE","FAILED_TECHNICAL"}
    if any(x not in allowed for x in outcomes) or total is not None and len(outcomes)>total:
        raise ValueError("Invalid reconciliation input")
    counts={x:outcomes.count(x) for x in allowed}
    if total is None:
        return {"status":"FAILED" if file_failure else "RECEIVED","rows_received":None,"pending":None,"counts":counts}
    pending=total-sum(counts[x] for x in ("ACCEPTED","QUARANTINED","DUPLICATE","FAILED_TECHNICAL"))
    assert total==counts["ACCEPTED"]+counts["QUARANTINED"]+counts["DUPLICATE"]+counts["FAILED_TECHNICAL"]+pending
    resolved=sum(counts[x] for x in ("ACCEPTED","QUARANTINED","DUPLICATE"))
    if file_failure: status="PARTIAL" if resolved else "FAILED"
    elif counts["FAILED_TECHNICAL"]: status="PARTIAL" if resolved else "FAILED"
    elif pending: status="PUBLISHED" if publication_complete else "PROCESSING"
    else: status="COMPLETED"
    return {"status":status,"rows_received":total,"pending":pending,"counts":counts}
