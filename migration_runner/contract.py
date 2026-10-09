"""Conservative definition checks; no row values or SQL expressions in results."""
import hashlib
import re

COLUMNS = {"source_system": "character varying(100)", "source_transaction_id": "character varying(200)",
           "transaction_fingerprint": "character(64)", "batch_id": "uuid", "file_sha256": "character(64)",
           "source_row": "integer", "country": "character(2)"}
BASE = {"tx_id": "uuid", "account_id": "uuid", "amount": "numeric(15,2)", "currency": "character(3)",
        "merchant": "character varying(200)", "tx_date": "timestamp with time zone", "tx_type": "character varying(30)",
        "cross_border": "boolean", "raw_file": "text"}
CHECKS = {
 "transactions_transaction_fingerprint_check": "CHECK ((transaction_fingerprint ~ '^[0-9a-f]{64}$'::text))",
 "transactions_file_sha256_check": "CHECK ((file_sha256 ~ '^[0-9a-f]{64}$'::text))",
 "transactions_source_row_check": "CHECK ((source_row >= 2))",
 "transactions_source_identity_check": "CHECK (((source_transaction_id IS NULL) OR ((length(btrim((source_transaction_id)::text)) > 0) AND (length(btrim((source_system)::text)) > 0) AND (source_system IS NOT NULL))))",
}
INDEXES = {"idx_tx_source_identity": (True, "source_system, account_id, source_transaction_id"),
           "idx_tx_duplicate_charge": (False, "account_id, merchant, currency, amount, tx_date")}

def normalized(text):
    # Only whitespace normalization: never discard casts, predicates or literals.
    return re.sub(r"\s+", " ", text or "").strip()

def digest(value):
    return hashlib.sha256((value or "").encode()).hexdigest()

def assess(catalog, data=None):
    from .config import TABLES
    relations = {r["name"]: r for r in catalog.get("relations") or []}
    columns = {c["name"]: c for c in catalog.get("columns") or [] if c["table"] == "transactions"}
    issues = []
    if not set(TABLES) <= relations.keys():
        return {"state": "missing-base", "issues": ["base_tables_missing"], "base_valid": False}
    for table in TABLES:
        if relations[table]["kind"] != "r" or relations[table]["rls"] or relations[table]["force_rls"]:
            issues.append("unsupported_relation_security")
    for name, kind in BASE.items():
        if name not in columns or columns[name]["type"] != kind:
            issues.append("base_column_conflict")
    if catalog.get("triggers") or catalog.get("policies"):
        issues.append("unreviewed_trigger_or_policy")
    base_valid = not issues
    for name, kind in COLUMNS.items():
        c = columns.get(name)
        if c and (c["type"] != kind or c["not_null"] or c["default"] is not None or c["identity"] or c["generated"]):
            issues.append("migration_column_conflict")
    constraints = {c["name"]: c for c in catalog.get("constraints") or [] if c["table"] == "transactions"}
    for name, definition in CHECKS.items():
        c = constraints.get(name)
        if c and (c["type"] != "c" or not c["validated"] or normalized(c["definition"]) != normalized(definition)):
            issues.append("migration_constraint_conflict")
    # Existing partial columns whose inline CHECK was never installed cannot be
    # repaired by ADD COLUMN IF NOT EXISTS. Refuse rather than invent new DDL.
    for col, check in (("transaction_fingerprint", "transactions_transaction_fingerprint_check"),
                       ("file_sha256", "transactions_file_sha256_check"), ("source_row", "transactions_source_row_check")):
        if col in columns and check not in constraints:
            issues.append("partial_inline_check_missing")
    indexes = {i["name"]: i for i in catalog.get("indexes") or []}
    for name, (unique, keys) in INDEXES.items():
        i = indexes.get(name)
        expected = f"CREATE {'UNIQUE ' if unique else ''}INDEX {name} ON public.transactions USING btree ({keys}) WHERE (source_transaction_id IS NOT NULL)"
        if i and (i["table"] != "transactions" or i["unique"] != unique or not i["valid"] or not i["ready"]
                  or normalized(i["predicate"]) != "(source_transaction_id IS NOT NULL)"
                  or normalized(i["definition"]) != expected):
            issues.append("migration_index_conflict")
    # Extra constraints on new fields (e.g. UNIQUE fingerprint) are not approved.
    for name, c in constraints.items():
        if name not in CHECKS and any(re.search(r"\b" + field + r"\b", c["definition"]) for field in COLUMNS):
            issues.append("unreviewed_identity_constraint")
    for name, i in indexes.items():
        if i["table"] == "transactions" and name not in INDEXES and i["unique"] and any(
                re.search(r"\b" + field + r"\b", i["definition"]) for field in COLUMNS):
            issues.append("unreviewed_identity_unique_index")
    if data:
        if data["duplicate_source_identity_groups"]:
            issues.append("duplicate_source_identity")
        if any(data[k] for k in data if k.startswith("invalid_") and k.endswith("_rows")):
            issues.append("invalid_partial_data")
    complete = set(COLUMNS) <= columns.keys() and set(CHECKS) <= constraints.keys() and set(INDEXES) <= indexes.keys()
    any_present = bool(set(COLUMNS) & columns.keys() or set(CHECKS) & constraints.keys() or set(INDEXES) & indexes.keys())
    return {"state": "conflicting" if issues else "correct" if complete else "partial" if any_present else "absent",
            "issues": sorted(set(issues)), "base_valid": base_valid}

def safe_report(catalog, data, assessment):
    # Never return raw catalog SQL/defaults, arbitrary error strings or row data.
    result = {"assessment": assessment, "database": catalog["database"], "user": catalog["user"],
              "version": catalog["version"], "ssl": bool((catalog.get("ssl") or {}).get("ssl")),
              "tables": [{k:r[k] for k in ("name","kind","owner","rls","force_rls")} for r in catalog.get("relations") or []],
              "columns": [{"table":c["table"],"name":c["name"],"type":c["type"],"not_null":c["not_null"],
                           "default_sha256":digest(c["default"])} for c in catalog.get("columns") or []],
              "constraints": [{"table":c["table"],"name":c["name"],"validated":c["validated"],
                               "definition_sha256":digest(c["definition"])} for c in catalog.get("constraints") or []],
              "indexes": [{"table":i["table"],"name":i["name"],"valid":i["valid"],
                           "definition_sha256":digest(i["definition"])} for i in catalog.get("indexes") or []],
              "roles": catalog.get("roles") or [], "memberships": catalog.get("memberships") or [],
              "table_grants": [{"table":r["name"],"acl":r.get("acl")} for r in catalog.get("relations") or []],
              "column_grants": [{k:g.get(k) for k in ("grantor","grantee","table_name","column_name","privilege_type","is_grantable")} for g in catalog.get("column_grants") or []],
              "grants_sha256": digest(__import__('json').dumps({"relations":[r.get("acl") for r in catalog.get("relations") or []],
                                  "columns":catalog.get("column_grants"),"defaults":catalog.get("default_grants")},sort_keys=True))}
    if data is not None:
        result["counts"] = data
    return result
