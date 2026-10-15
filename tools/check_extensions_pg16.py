"""Production-handler rehearsal on a dedicated, disposable loopback PG16.15.

No AWS clients are used. Test-only connectors replace RDS IAM/TLS transport;
the production session guard is NOT weakened in any shipped module.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]
import hashlib
import json
import os
import platform
import uuid
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn
from migration_runner import common, config, extensions, iam
from migration_runner import bootstrap_extensions_entry, iam_extensions_entry, cleanup_extensions_entry
from tools.check_migration_roles_pg16 import run as identity_rehearsal, expect_denied
from tools.check_workflows_pg16 import run as workflow_rehearsal


def run():
    if os.getenv("FINTRUST_DISPOSABLE_PG16_LOCAL") != "1":
        raise RuntimeError("Explicit disposable local database required")
    target = parse_dsn(os.environ["FINTRUST_TEST_DATABASE_URL"])
    if (target.get("host") != "127.0.0.1" or target.get("dbname") != "fintrust_test"
            or target.get("user") != "postgres" or platform.system() != "Linux"):
        raise RuntimeError("Isolated Linux loopback database required")
    with psycopg2.connect(**target) as probe:
        with probe.cursor() as cur:
            cur.execute("SELECT current_setting('server_version_num')::int")
            if cur.fetchone()[0] != 160015:
                raise RuntimeError("Exact PostgreSQL 16.15 required")
    cases = [(None, 39, None, False), (None, 40, None, True),
             ('fintrust-r1-rules-2026-10-09',20,'Medium',False),
             ('fintrust-r1-rules-2026-10-09',40,'Medium',True),
             ('fintrust-r1-rules-2026-10-09',70,'High',True),
             ('fintrust-r2-rules-2026-10-13',15,'Low',False),
             ('fintrust-r2-rules-2026-10-13',20,'Medium',True),
             ('fintrust-r2-rules-2026-10-13',40,'High',True),
             ('unknown-version',40,'High',False)]
    events = []
    def seed_history(cur):
        # Fixture-only facts precede 001 hardening, exactly as historical data
        # would. No production-owner grants are weakened to seed test records.
        cur.execute("SELECT tx_id FROM public.transactions ORDER BY tx_id LIMIT 10")
        txs = [r[0] for r in cur.fetchall()]
        for tx, (rule, points, level, allowed) in zip(txs, cases + [('fintrust-r1-rules-2026-10-09',70,'High',True)]):
            cur.execute("INSERT INTO public.risk_events(tx_id,risk_score,reason) VALUES(%s,%s,'historical fixture') RETURNING risk_event_id", (tx,points))
            events.append(cur.fetchone()[0])
            if rule is not None:
                cur.execute("INSERT INTO public.processed_transactions(tx_id,fingerprint,result) VALUES(%s,%s,%s::jsonb)", (tx,hashlib.sha256(str(tx).encode()).hexdigest(),json.dumps({'rule_version':rule,'risk_level':level,'score':points})))
    identity_result = identity_rehearsal(seed_fixture=seed_history)
    workflow_result = workflow_rehearsal()
    target["dbname"] = "fintrust"
    admin = psycopg2.connect(**target)
    admin.autocommit = True
    original_guard, original_connection = common.session_check, iam.connection

    def local_guard(cur, user):
        cur.execute("SELECT current_database(),session_user,current_setting('server_version_num')::int")
        if cur.fetchone() != ("fintrust", user, 160015):
            raise common.Refused("local_database_identity_mismatch")

    def connector(user):
        conn = psycopg2.connect(**target)
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SET SESSION AUTHORIZATION {}").format(sql.Identifier(user)))
        conn.commit()
        return conn

    def invoke(op, handler=iam_extensions_entry.lambda_handler, user=config.USER):
        # Exercise the real handler -> request allowlist -> common.run -> executor
        # -> transaction commit/rollback path. Only credential transport is local.
        actual = iam.connection if user == config.USER else bootstrap_extensions_entry.admin.connection
        if user == config.USER:
            iam.connection = lambda: connector(user)
        else:
            bootstrap_extensions_entry.admin.connection = lambda: connector(user)
        try:
            return handler({"operation": op, "request_id": str(uuid.uuid4())}, None)
        finally:
            if user == config.USER:
                iam.connection = actual
            else:
                bootstrap_extensions_entry.admin.connection = actual

    def snapshot():
        with admin.cursor() as cur:
            values = {}
            for table in (*config.TABLES, "risk_reviews", "risk_review_history"):
                cur.execute(sql.SQL("SELECT row_to_json(t)::text FROM public.{} t ORDER BY row_to_json(t)::text").format(sql.Identifier(table)))
                rows = cur.fetchall()
                values[table] = {"count": len(rows), "sha256": hashlib.sha256(json.dumps(rows).encode()).hexdigest()}
            return values

    def expect_refused(op):
        try:
            invoke(op)
        except common.RunnerFailure:
            return
        raise AssertionError("Expected runner refusal: " + op)

    def behavior(version, historical_event):
        with admin.cursor() as cur:
            cur.execute("BEGIN")
            try:
                if version == 3:
                    batch, attempt = str(uuid.uuid4()), str(uuid.uuid4())
                    cur.execute("INSERT INTO public.ingestion_batches(batch_id,source_system,source_bucket,file_sha256,received_at,rows_received) VALUES(%s,'fixture','fixture',%s,NOW(),1)", (batch,'a'*64))
                    cur.execute("INSERT INTO public.ingestion_attempts(attempt_id,batch_id,source_bucket,source_file,received_at,status) VALUES(%s,%s,'fixture','fixture.csv',NOW(),'RECEIVED')", (attempt,batch))
                    cur.execute("INSERT INTO public.ingestion_records(batch_id,source_row,source_attempt_id,disposition) VALUES(%s,2,%s,'RECEIVED')", (batch,attempt))
                    for sequence, kind in [(1,'RECEIVED'),(2,'QUEUED')]:
                        cur.execute("INSERT INTO public.transaction_lifecycle_events(batch_id,source_row,sequence,event_type,actor_subject) VALUES(%s,2,%s,%s,'scoring-worker')", (batch,sequence,kind))
                    expect_denied(cur, "INSERT INTO public.transaction_lifecycle_events(batch_id,source_row,sequence,event_type,actor_subject) SELECT batch_id,source_row,4,'VALIDATED','scoring-worker' FROM public.ingestion_records LIMIT 1", psycopg2.errors.RaiseException)
                    expect_denied(cur, "UPDATE public.transaction_lifecycle_events SET actor_subject='intruder'", psycopg2.errors.RaiseException)
                    expect_denied(cur, "DELETE FROM public.transaction_lifecycle_events", psycopg2.errors.RaiseException)
                else:
                    cur.execute("UPDATE public.risk_reviews SET review_status='UNDER_REVIEW',reviewer_subject='analyst01',change_actor='analyst01',review_notes='Claim',version=2,change_request_id=gen_random_uuid() WHERE risk_event_id=%s", (historical_event,))
                    cur.execute("UPDATE public.risk_reviews SET reviewer_subject='analyst02',change_actor='admin01',review_notes='Reassign',version=3,change_request_id=gen_random_uuid() WHERE risk_event_id=%s", (historical_event,))
                    note = "UPDATE public.risk_reviews SET change_actor='analyst02',review_notes='Investigation evidence',version=4,change_request_id=gen_random_uuid() WHERE risk_event_id=" + str(historical_event)
                    if version == 4:
                        expect_denied(cur, note, psycopg2.errors.RaiseException)
                    else:
                        cur.execute(note)
                        cur.execute("SELECT notes FROM public.risk_review_history WHERE risk_event_id=%s AND version=4", (historical_event,))
                        assert cur.fetchone() == ('Investigation evidence',)
                cur.execute("ROLLBACK")
            except BaseException:
                cur.execute("ROLLBACK")
                raise

    try:
        common.session_check = local_guard
        with admin.cursor() as cur:
            cur.execute("SET SESSION AUTHORIZATION fintrust_admin")
            cur.execute("CREATE ROLE fintrust_migrate_dev LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS")
            cur.execute("GRANT rds_iam TO fintrust_migrate_dev")
            cur.execute("GRANT CONNECT ON DATABASE fintrust TO fintrust_migrate_dev")
            cur.execute("GRANT USAGE ON SCHEMA public TO fintrust_migrate_dev")
            for table, key in [('customers','customer_id'),('accounts','account_id'),('risk_events','risk_event_id'),('alerts','alert_id'),('processed_transactions','tx_id')]:
                cur.execute(sql.SQL("GRANT SELECT({}) ON public.{} TO fintrust_migrate_dev").format(sql.Identifier(key), sql.Identifier(table)))
            cur.execute("GRANT fintrust_transactions_owner TO fintrust_admin WITH SET TRUE, INHERIT FALSE, ADMIN FALSE")
            cur.execute("SET ROLE fintrust_transactions_owner")
            cur.execute("GRANT SELECT ON public.transactions TO fintrust_migrate_dev")
            cur.execute("RESET ROLE")
            cur.execute("GRANT fintrust_transactions_owner TO fintrust_admin WITH SET FALSE, INHERIT FALSE, ADMIN FALSE")
            cur.execute("RESET SESSION AUTHORIZATION")
            # One existing V1 review makes history preservation non-empty.
            historical_event = events[-1]
            cur.execute("INSERT INTO public.risk_reviews(risk_event_id,change_actor) VALUES(%s,'historical-analyst')", (historical_event,))
        initial = snapshot()
        result = invoke("bootstrap_extensions", bootstrap_extensions_entry.lambda_handler, config.MASTER)
        assert result["result"]["migration_executed"] is False
        assert snapshot() == initial
        with connector(config.USER) as conn:
            with conn.cursor() as cur:
                expect_denied(cur, "SET ROLE fintrust_workflow_owner")
                expect_denied(cur, "CREATE TABLE public.unapproved(id integer)")
                expect_denied(cur, "UPDATE public.transactions SET amount=1")
                expect_denied(cur, "UPDATE public.schema_migrations SET source_sha256=repeat('0',64)")
                expect_denied(cur, "SELECT public.fintrust_apply_migration_003('SELECT 1')", psycopg2.errors.UndefinedFunction)
                expect_denied(cur, "SELECT public.fintrust_apply_migration_006()", psycopg2.errors.RaiseException)
        expect_refused("migrate006")
        expect_refused("verify_extensions")
        with admin.cursor() as cur:
            cur.execute("SELECT pg_get_functiondef('public.fintrust_apply_migration_003()'::regprocedure)")
            helper_definition = cur.fetchone()[0]
            cur.execute("CREATE OR REPLACE FUNCTION public.fintrust_apply_migration_003() RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$ BEGIN NULL; END $$")
        expect_refused("migrate003")
        with admin.cursor() as cur:
            cur.execute(helper_definition)
            cur.execute("GRANT EXECUTE ON FUNCTION public.fintrust_apply_migration_003() TO PUBLIC")
        expect_refused("migrate003")
        with admin.cursor() as cur:
            cur.execute("REVOKE EXECUTE ON FUNCTION public.fintrust_apply_migration_003() FROM PUBLIC")
        per_migration = []
        for version in range(3, 7):
            operation = f"migrate{version:03d}"
            before = snapshot()
            # The real common.run rollback must restore DDL, old guard and helper.
            real_verify = extensions.verify_after
            def fail_after_ddl(cur, applied):
                cur.execute("SELECT 1/0")
            extensions.verify_after = fail_after_ddl
            try:
                expect_refused(operation)
            finally:
                extensions.verify_after = real_verify
            assert snapshot() == before
            with admin.cursor() as cur:
                cur.execute("SELECT count(*) FROM public.schema_migrations WHERE version=%s", (version,))
                assert cur.fetchone()[0] == 0
                cur.execute("SELECT to_regprocedure(%s) IS NOT NULL", ("public."+extensions.helper(version)+"()",))
                assert cur.fetchone()[0]
                if version == 3:
                    cur.execute("SELECT to_regclass('public.transaction_lifecycle_events') IS NULL")
                    assert cur.fetchone()[0]
                if version == 4:
                    cur.execute("SELECT to_regclass('public.risk_reviews_assignee_queue') IS NULL")
                    assert cur.fetchone()[0]
            # Rollback after ledger INSERT, not only before it.
            real_history = extensions.history
            calls = [0]
            def fail_after_ledger(cur):
                saved = real_history(cur)
                calls[0] += 1
                if calls[0] == 2:
                    raise common.Refused("injected_after_ledger_insert")
                return saved
            extensions.history = fail_after_ledger
            try:
                expect_refused(operation)
            finally:
                extensions.history = real_history
            assert snapshot() == before
            with admin.cursor() as cur:
                cur.execute("SELECT max(version) FROM public.schema_migrations")
                assert cur.fetchone()[0] == version - 1
            # Conflicting partial lifecycle/index must not be silently repaired.
            if version in {3, 4}:
                with admin.cursor() as cur:
                    cur.execute("CREATE TABLE public.transaction_lifecycle_events(unapproved integer)" if version == 3 else
                                "CREATE INDEX risk_reviews_assignee_queue ON public.risk_reviews(version)")
                expect_refused(operation)
                with admin.cursor() as cur:
                    cur.execute("DROP TABLE public.transaction_lifecycle_events" if version == 3 else
                                "DROP INDEX public.risk_reviews_assignee_queue")
            applied = invoke(operation)
            assert applied["result"]["status"] == "APPLIED"
            assert snapshot() == before
            behavior(version, historical_event)
            assert snapshot() == before
            for prior in range(3, version + 1):
                assert invoke(f"migrate{prior:03d}")["result"]["status"] == "ALREADY_APPLIED"
            assert snapshot() == before
            with admin.cursor() as cur:
                cur.execute("SELECT to_regprocedure(%s) IS NULL", ("public."+extensions.helper(version)+"()",))
                assert cur.fetchone()[0]
            per_migration.append({"version": version, "source_sha256": extensions.SOURCES[version],
                                  "applied": True, "rerun_noop": True, "earlier_extension_reruns_noop": True,
                                  "ddl_failure_rollback": True, "post_ledger_failure_rollback": True,
                                  "financial_and_review_history_unchanged": True, "helper_self_removed": True})
        assert invoke("verify_extensions")["result"]["status"] == "VERIFIED"
        # Modified live catalog must refuse every extension rerun, not only 006.
        with admin.cursor() as cur:
            cur.execute("SELECT pg_get_functiondef('public.guard_review_transition()'::regprocedure)")
            definition = cur.fetchone()[0]
            cur.execute("CREATE OR REPLACE FUNCTION public.guard_review_transition() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$")
        for version in range(3, 7):
            expect_refused(f"migrate{version:03d}")
        with admin.cursor() as cur:
            cur.execute(definition)
        assert invoke("verify_extensions")["result"]["status"] == "VERIFIED"
        # Verify 006 eligibility directly through the migrated database guard.
        eligibility = []
        with admin.cursor() as cur:
            for event, (rule, points, level, allowed) in zip(events, cases):
                if allowed:
                    cur.execute("INSERT INTO public.risk_reviews(risk_event_id,change_actor) VALUES(%s,'fixture-worker')",(event,))
                else:
                    try:
                        cur.execute("INSERT INTO public.risk_reviews(risk_event_id,change_actor) VALUES(%s,'fixture-worker')",(event,))
                    except psycopg2.errors.RaiseException:
                        pass
                    else:
                        raise AssertionError("Ineligible review accepted")
                eligibility.append({"rule_version":rule,"points":points,"risk_level":level,"accepted":allowed})
        # Cleanup uses a different administrator connection after every IAM session closes.
        outcome = invoke("cleanup_extensions", cleanup_extensions_entry.lambda_handler, config.MASTER)
        assert outcome["result"]["owner_create_revoked"]
        with admin.cursor() as cur:
            cur.execute("SELECT has_schema_privilege('fintrust_workflow_owner','public','CREATE'), pg_has_role('fintrust_admin','fintrust_workflow_owner','SET')")
            assert cur.fetchone() == (False,False)
            cur.execute("SELECT count(*) FROM pg_proc WHERE proname LIKE 'fintrust_apply_migration_%'")
            assert cur.fetchone()[0] == 0
            cur.execute("SELECT count(*) FROM public.schema_migrations")
            assert cur.fetchone()[0] == 6
        return {"status":"PASSED", "postgresql_version":"16.15", "platform":platform.platform(),
                "python":platform.python_version(), "aws_access":False, "live_rds_access":False,
                "real_rds_iam_tls_tested":False, "transport":"local session authorization, no cloud credentials",
                "001_rehearsal_passed":identity_result['bootstrap_migrate_rerun_cleanup_passed'],
                "002_rehearsal_passed":workflow_result['status']=='PASSED', "migrations":per_migration,
                "out_of_order_refused":True, "partial_state_refused":True, "catalog_drift_refused":True,
                "modified_helper_refused":True,"public_helper_execute_refused":True,
                "migration_behavior_verified":True,
                "no_arbitrary_sql_or_owner_membership":True, "cleanup_verified":True,
                "eligibility_006":eligibility, "before_migrations":initial,
                "tested_files_sha256": {
                    p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
                    for p in [*sorted((ROOT/'backend/migration_runner').glob('*.py')),
                              *sorted((ROOT/'sql/migrations').glob('*.sql')),
                              ROOT/'tools/check_extensions_pg16.py',ROOT/'tools/check_migration_roles_pg16.py',
                              ROOT/'tools/check_workflows_pg16.py']},
                "source_sha256":{str(v):value[1] for v,value in extensions.MIGRATIONS.items()}}
    finally:
        common.session_check, iam.connection = original_guard, original_connection
        admin.close()


if __name__ == "__main__":
    result = run()
    path = ROOT / "build/migration-runner/pg16-extensions-rehearsal.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result))
