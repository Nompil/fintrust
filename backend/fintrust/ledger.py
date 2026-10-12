"""Shared ledger admission. Caller holds the account lock in the SQL transaction."""
from .jobs import business_fingerprint


class IdentityConflict(ValueError):
    """An identifier was reused for different accepted financial data."""


def existing_transaction(cur, job):
    reference = job.get("source_transaction_id")
    cur.execute("""SELECT t.tx_id::text, t.transaction_fingerprint, p.fingerprint, p.result
        FROM transactions t LEFT JOIN processed_transactions p USING(tx_id)
        WHERE t.tx_id=%s OR (t.source_system=%s AND t.account_id=%s
                            AND t.source_transaction_id=%s)""",
        (job["transaction_id"], job.get("source_system"), job["account_id"], reference))
    rows = cur.fetchall()
    if len(rows) > 1:
        raise IdentityConflict("Internal UUID and source reference identify different transactions")
    if not rows:
        return None
    row = rows[0]
    digest = business_fingerprint(job)
    if row[1] is not None:
        # A legacy v1 replay of a v2 event can still match its saved v1 digest.
        matched = row[1] == digest or (job["schema_version"] == 1 and row[2] == digest)
    else:
        # Never overwrite/recompute historical frozen scoring results.
        legacy = {k: v for k, v in job.items() if k not in {"batch", "source_system", "source_transaction_id"}}
        legacy["schema_version"] = 1
        matched = row[2] == business_fingerprint(legacy)
    if not matched:
        raise IdentityConflict("Transaction ID conflicts with accepted financial data")
    return row


def insert_transaction(cur, job):
    batch = job.get("batch") or {}
    cur.execute("""INSERT INTO transactions
        (tx_id,account_id,amount,currency,merchant,tx_date,tx_type,cross_border,raw_file,
         source_system,source_transaction_id,transaction_fingerprint,batch_id,file_sha256,source_row,country)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT DO NOTHING RETURNING tx_id""",
        (job["transaction_id"], job["account_id"], job["amount"], job["currency"],
         job["merchant"] or None, job["transaction_timestamp"], job["transaction_type"],
         job["country"] != "ZA", job["source"]["key"], job.get("source_system"),
         job.get("source_transaction_id"), business_fingerprint(job), batch.get("batch_id"),
         batch.get("file_sha256"), job["source"]["row"], job["country"]))
    if not cur.fetchone():
        # Cross-account UUID conflicts cannot be serialized by our account lock.
        raise IdentityConflict("Transaction ID conflicts with another ledger writer")
