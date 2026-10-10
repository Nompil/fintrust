"""Migration-tool-only copy of the frozen application catalog signature contract.
No application import, network, DDL or secret access. Kept byte-equivalent by tests.
"""
import hashlib
import json
TABLES=("ingestion_batches","ingestion_attempts","ingestion_records","risk_reviews","risk_review_history","quarantine_cases","quarantine_corrections","correction_outbox","projection_outbox","operations_requests")
IDENTITY_COLUMNS={"source_system":"character varying(100)","source_transaction_id":"character varying(200)","transaction_fingerprint":"character(64)","batch_id":"uuid","file_sha256":"character(64)","source_row":"integer","country":"character(2)"}
class SchemaDrift(ValueError):pass

def _catalog(cur,schema,version):
    if version==1:
        cur.execute("""SELECT a.attname,pg_catalog.format_type(a.atttypid,a.atttypmod) FROM pg_attribute a
            JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname=%s AND c.relname='transactions' AND a.attname=ANY(%s) AND NOT a.attisdropped ORDER BY a.attname""",(schema,list(IDENTITY_COLUMNS)))
        columns=cur.fetchall()
        if dict(columns)!=IDENTITY_COLUMNS: raise SchemaDrift("Identity column contract mismatch")
        cur.execute("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname=%s AND indexname=ANY(%s) ORDER BY indexname",(schema,["idx_tx_source_identity","idx_tx_duplicate_charge"]))
        indexes=cur.fetchall()
        if len(indexes)!=2 or not any("UNIQUE INDEX" in d and "(source_system, account_id, source_transaction_id)" in d and "WHERE (source_transaction_id IS NOT NULL)" in d for _,d in indexes):
            raise SchemaDrift("Identity index contract mismatch")
        cur.execute("""SELECT pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname='transactions' AND k.conname='transactions_source_identity_check'""",(schema,))
        constraints=cur.fetchall()
        import re
        expected="CHECK (((source_transaction_id IS NULL) OR ((length(btrim((source_transaction_id)::text)) > 0) AND (length(btrim((source_system)::text)) > 0) AND (source_system IS NOT NULL))))"
        normalize=lambda text:re.sub(r"[\s()]","",text).lower()
        if len(constraints)!=1 or normalize(constraints[0][0])!=normalize(expected): raise SchemaDrift("Identity constraint mismatch")
        values=[columns,indexes,constraints]
    else:
        cur.execute("""SELECT c.relname,a.attname,pg_catalog.format_type(a.atttypid,a.atttypmod),a.attnotnull,
            pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
            WHERE n.nspname=%s AND c.relname=ANY(%s) AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum""",(schema,list(TABLES)))
        columns=cur.fetchall()
        if {x[0] for x in columns}!=set(TABLES): raise SchemaDrift("Operational table missing")
        cur.execute("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname=%s AND tablename=ANY(%s) ORDER BY indexname",(schema,list(TABLES)));indexes=cur.fetchall()
        cur.execute("""SELECT c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k
            JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname=%s AND c.relname=ANY(%s) ORDER BY c.relname,k.conname""",(schema,list(TABLES)));constraints=cur.fetchall()
        cur.execute("""SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname=ANY(%s) AND NOT t.tgisinternal ORDER BY c.relname,t.tgname""",(schema,list(TABLES)));triggers=cur.fetchall()
        cur.execute("SELECT viewname,definition FROM pg_views WHERE schemaname=%s AND viewname=ANY(%s) ORDER BY viewname",(schema,["batch_reconciliation","quarantine_workflow"]));views=cur.fetchall()
        cur.execute("""SELECT DISTINCT p.proname,pg_get_functiondef(p.oid),p.prosecdef,p.proconfig
            FROM pg_proc p JOIN pg_trigger t ON t.tgfoid=p.oid JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname=ANY(%s) ORDER BY p.proname""",(schema,list(TABLES)));functions=cur.fetchall()
        values=[columns,indexes,constraints,triggers,views,functions]
    return hashlib.sha256(json.dumps(values,default=str,sort_keys=True).encode()).hexdigest()
