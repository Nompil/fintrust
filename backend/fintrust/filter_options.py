"""Read-only filter choices from the caller's authorized ledger, not a directory."""
import re
from . import workflow_api as api


def read(principal, args):
    principal.require("read")
    if principal.role == "Maintainer":
        raise PermissionError("Financial filter choices unavailable to Maintainer")
    if set(args) - {"account_id"} or any(len(args.getlist(k)) != 1 for k in args):
        raise ValueError("Unsupported or duplicate filter")
    scope = [principal.account(args["account_id"])] if args.get("account_id") else list(principal.accounts)
    rows = api._query("SELECT DISTINCT country,tx_type FROM transactions WHERE account_id=ANY(%s::uuid[])", (scope,))
    owners = api._query("""SELECT DISTINCT w.reviewer_subject FROM risk_reviews w
        JOIN risk_events r USING(risk_event_id) JOIN transactions t USING(tx_id)
        WHERE t.account_id=ANY(%s::uuid[]) AND w.reviewer_subject IS NOT NULL
        ORDER BY w.reviewer_subject""", (scope,))
    countries = sorted({row["country"].strip().upper() for row in rows
                        if row.get("country") and re.fullmatch("[A-Za-z]{2}", row["country"].strip())})
    types = sorted({row["tx_type"] for row in rows if row["tx_type"] in {"debit", "credit", "transfer", "fee"}})
    return {"countries": countries, "transaction_types": types,
            "assignees": [{"value": row["reviewer_subject"], "label": row["reviewer_subject"]}
                          for row in owners if row["reviewer_subject"]]}
