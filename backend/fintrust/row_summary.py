"""Partition source row outcomes without assigning a risk verdict to quarantine."""


def summary(batch, principal):
    from . import workflow_api as api
    from .analyst_workflow import assessed_sql
    counts = api._query("""SELECT
        count(*) FILTER(WHERE """ + assessed_sql() + """ AND p.result->>'risk_level'='Low') AS low,
        count(*) FILTER(WHERE """ + assessed_sql() + """ AND p.result->>'risk_level'='Medium') AS medium,
        count(*) FILTER(WHERE """ + assessed_sql() + """ AND p.result->>'risk_level'='High') AS high
        FROM ingestion_records i JOIN transactions t ON t.tx_id=i.canonical_tx_id
        LEFT JOIN processed_transactions p ON p.tx_id=t.tx_id
        WHERE i.batch_id=%s AND i.disposition='ACCEPTED' AND t.account_id=ANY(%s::uuid[])
        """, (str(batch['batch_id']), list(principal.accounts)))[0]
    counts = {key: int(counts[key]) for key in ('low', 'medium', 'high')}
    counts.update(unassessed=int(batch['accepted'])-sum(counts.values()),
                  quarantined=int(batch['quarantined']), duplicates=int(batch['duplicate']),
                  technical_failures=int(batch['failed_technical']), pending=batch['pending'])
    received = batch['rows_received']
    consistent = (bool(batch['counts_consistent']) and received is not None
                  and all(type(value) is int and value >= 0 for value in counts.values())
                  and sum(counts.values()) == received)
    return {'rows_received': received, **counts, 'counts_consistent': consistent,
            'complete': consistent and counts['pending'] == 0,
            'risk_scope': 'Accepted source rows only, using their stored scoring version; duplicate rows do not add another assessment.',
            'quarantine_note': 'Quarantined means not yet accepted: a validation or reference issue requires source review. It is not a finding of fraud or bad data.'}
