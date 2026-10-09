"""No AWS calls: local disposable schemas plus mocked credential failure paths."""
import copy
import json
import uuid
from unittest.mock import Mock
import pytest
import psycopg2
from migration_runner import common, admin, iam, config, contract, preflight_entry, iam_entry
from test_private_rds_preflight import isolated, base

EVENT = {"operation":"preflight","request_id":"20000000-0000-4000-8000-000000000001"}
SENTINEL = "SENSITIVE_SENTINEL_PASSWORD_TOKEN_PII"

@pytest.fixture
def database(isolated, monkeypatch):
    conn, schema = isolated
    original = common.body
    def local_body(path, **kwargs):
        return original(path, **kwargs).replace("public.", schema+".").replace("'public'", "'"+schema+"'")
    monkeypatch.setattr(common,"body",local_body)
    original_catalog = common.catalog
    def cat(cur):
        value=original_catalog(cur)
        for i in value.get("indexes") or []:
            i["definition"]=i["definition"].replace(schema+".","public.")
        return value
    monkeypatch.setattr(common,"catalog",cat)
    # This machine's PostgreSQL 18 / non-TLS local test session is never presented
    # as target validation. Independent tests exercise the production identity guard.
    monkeypatch.setattr(common,"session_check",lambda cur,user: None)
    monkeypatch.setattr(iam,"identity",lambda cur: None)
    return conn,schema

def inspect(conn):
    with conn.cursor() as cur:
        common.setup(cur,read_only=True)
        c,d,a=common.inspect(cur)
    conn.rollback()
    return c,d,a

def test_missing_schema(database):
    c,d,a=inspect(database[0]);assert a["state"]=="missing-base" and d is None

def test_legacy_preflight_counts_and_redaction(database):
    conn,_=database;base(conn)
    c,d,a=inspect(conn)
    assert a["state"]=="absent" and d["row_counts"]["transactions"]==200
    c["columns"][0]["default"]=SENTINEL
    assert SENTINEL not in json.dumps(contract.safe_report(c,d,a))

def test_partial_safe_columns(database):
    conn,_=database;base(conn)
    with conn.cursor() as cur:cur.execute("ALTER TABLE transactions ADD source_system varchar(100)")
    conn.commit();assert inspect(conn)[2]["state"]=="partial"

def test_conflicting_index(database):
    conn,_=database;base(conn)
    with conn.cursor() as cur:cur.execute("CREATE INDEX idx_tx_source_identity ON transactions(amount)")
    conn.commit();assert "migration_index_conflict" in inspect(conn)[2]["issues"]

def test_duplicate_source_identity(database):
    conn,_=database;base(conn)
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE transactions ADD source_system varchar(100), ADD source_transaction_id varchar(200)")
        cur.execute("UPDATE transactions SET source_system='test', source_transaction_id='duplicate'")
    conn.commit();c,d,a=inspect(conn)
    assert d["duplicate_source_identity_groups"]>0 and a["state"]=="conflicting"

def test_missing_inline_check_blocks_unsafe_partial(database):
    conn,_=database;base(conn)
    with conn.cursor() as cur:cur.execute("ALTER TABLE transactions ADD file_sha256 char(64)")
    conn.commit();assert "partial_inline_check_missing" in inspect(conn)[2]["issues"]

def test_canonical_migration_definitions_and_rerun(database):
    conn,_=database;base(conn)
    for _ in range(2):
        with conn.cursor() as cur:cur.execute(common.body("sql/migrations/001_transaction_identity.sql",migration=True))
        conn.commit()
        c,d,a=inspect(conn)
        assert a["state"]=="correct", (a,[k for k in c["constraints"] if k["name"] in contract.CHECKS])
        assert d["row_counts"]["transactions"]==200

def test_atomic_ddl_rollback(database):
    conn,_=database;base(conn)
    with pytest.raises(psycopg2.Error):
        with conn.cursor() as cur:
            cur.execute(common.body("sql/migrations/001_transaction_identity.sql",migration=True))
            cur.execute("SELECT 1/0")
    conn.rollback();assert inspect(conn)[2]["state"]=="absent"

@pytest.mark.parametrize("event", [{}, {**EVENT,"sql":"DROP TABLE transactions"}, {**EVENT,"password":SENTINEL}, {**EVENT,"operation":"migrate"}, {**EVENT,"request_id":SENTINEL}])
def test_preflight_rejects_payload_before_credentials(event,monkeypatch,capsys):
    connector=Mock();monkeypatch.setattr(admin,"connection",connector)
    with pytest.raises(common.RunnerFailure) as error:preflight_entry.lambda_handler(event,None)
    connector.assert_not_called();assert SENTINEL not in str(error.value)+capsys.readouterr().out

@pytest.mark.parametrize("failure", [RuntimeError(SENTINEL), psycopg2.OperationalError(SENTINEL)])
def test_failures_redacted_and_connections_closed(failure,capsys):
    conn=Mock()
    with pytest.raises(common.RunnerFailure) as error:
        common.run(EVENT,{"preflight"},lambda:conn,Mock(side_effect=failure))
    assert SENTINEL not in str(error.value)+capsys.readouterr().out
    conn.rollback.assert_called_once();conn.close.assert_called_once()

def test_secret_failure_never_leaks(monkeypatch,capsys):
    sdk=Mock();sdk.get_secret_value.side_effect=RuntimeError(SENTINEL)
    monkeypatch.setattr(common,"client",lambda service:sdk)
    with pytest.raises(common.RunnerFailure) as error:preflight_entry.lambda_handler(EVENT,None)
    assert SENTINEL not in str(error.value)+capsys.readouterr().out
    sdk.get_secret_value.assert_called_once_with(SecretId=config.SECRET,VersionStage="AWSCURRENT")

def test_exact_secret_memory_only(monkeypatch):
    response={"ARN":config.SECRET,"VersionStages":["AWSCURRENT"],"SecretString":json.dumps({"username":config.MASTER,"password":SENTINEL})}
    sdk=Mock();sdk.get_secret_value.return_value=response
    monkeypatch.setattr(common,"client",lambda service:sdk)
    connect=Mock();monkeypatch.setattr(common,"connect",connect)
    admin.connection();connect.assert_called_once_with(config.MASTER,SENTINEL)
    assert response=={}

def test_iam_token_path_has_no_secret_fetch(monkeypatch):
    sdk=Mock();sdk.generate_db_auth_token.return_value=SENTINEL
    calls=[]
    monkeypatch.setattr(common,"client",lambda service:calls.append(service) or sdk)
    connect=Mock();monkeypatch.setattr(common,"connect",connect)
    iam.connection();assert calls==["rds"]
    connect.assert_called_once_with(config.USER,SENTINEL)
    sdk.generate_db_auth_token.assert_called_once_with(DBHostname=config.HOST,Port=5432,DBUsername=config.USER,Region="af-south-1")

def test_token_signing_offline(monkeypatch):
    import socket
    def blocked(*args,**kwargs):raise AssertionError("network blocked")
    monkeypatch.setattr(socket,"getaddrinfo",blocked);monkeypatch.setattr(socket.socket,"connect",blocked)
    token=common.client("rds").generate_db_auth_token(DBHostname="db.invalid",Port=5432,DBUsername=config.USER,Region=config.REGION)
    assert "X-Amz-Signature=" in token and "X-Amz-Expires=900" in token

def test_tls_and_timeout_fixed(monkeypatch):
    connect=Mock();monkeypatch.setattr(psycopg2,"connect",connect)
    common.connect(config.USER,SENTINEL)
    assert connect.call_args.kwargs["sslmode"]=="verify-full"
    assert connect.call_args.kwargs["connect_timeout"]==5
    assert connect.call_args.kwargs["host"]==config.HOST

@pytest.mark.parametrize("row",[("other",config.USER,160015,True),(config.DATABASE,"wrong",160015,True),(config.DATABASE,config.USER,180006,True),(config.DATABASE,config.USER,160015,False)])
def test_production_target_guard_rejects_mismatch(row):
    cur=Mock();cur.fetchone.return_value=row
    with pytest.raises(common.Refused):common.session_check(cur,config.USER)

def test_target_guard_accepts_pg16_tls():
    cur=Mock();cur.fetchone.return_value=(config.DATABASE,config.USER,160015,True)
    common.session_check(cur,config.USER)

def test_commit_failure_is_unknown_not_success(capsys):
    conn=Mock();conn.commit.side_effect=RuntimeError(SENTINEL)
    with pytest.raises(common.RunnerFailure,match="commit_outcome_unknown"):
        common.run(EVENT,{"preflight"},lambda:conn,lambda conn,op:({},True))
    assert SENTINEL not in capsys.readouterr().out
    conn.close.assert_called_once()

def test_read_only_preflight_never_commits(monkeypatch):
    conn=Mock();monkeypatch.setattr(admin,"connection",lambda:conn)
    monkeypatch.setattr(admin,"preflight",lambda conn,op:({"counts":{}},False))
    assert preflight_entry.lambda_handler(EVENT,None)["success"]
    conn.commit.assert_not_called();conn.rollback.assert_called_once()


class LocalCursor:
    """Exercise real SQL transaction path, substituting only cluster role selection."""
    def __init__(self,cur):self.cur=cur
    def __enter__(self):self.cur.__enter__();return self
    def __exit__(self,*args):return self.cur.__exit__(*args)
    def execute(self,query,*args):
        if query in ("SET LOCAL ROLE fintrust_transactions_owner", "RESET ROLE"):return
        if query=="SELECT public.fintrust_create_identity_indexes()":
            return self.cur.execute(common.migration_parts()[1])
        if query=="LOCK TABLE public.transactions IN ACCESS EXCLUSIVE MODE":query="LOCK TABLE transactions IN ACCESS EXCLUSIVE MODE"
        return self.cur.execute(query,*args)
    def __getattr__(self,name):return getattr(self.cur,name)
class LocalConnection:
    def __init__(self,conn):self.conn=conn
    def cursor(self):return LocalCursor(self.conn.cursor())

@pytest.fixture
def migration_database(database,monkeypatch):
    conn,schema=database
    original=common.setup
    def setup(cur,*,read_only):
        original(cur,read_only=read_only)
        from psycopg2 import sql
        cur.execute(sql.SQL("SET LOCAL search_path = pg_catalog, {}").format(sql.Identifier(schema)))
    monkeypatch.setattr(common,"setup",setup)
    base(conn)
    return conn,LocalConnection(conn)

def test_real_migration_path_and_rerun(migration_database):
    conn,wrapped=migration_database
    for _ in range(2):
        result,write=iam.operate(wrapped,"migrate")
        assert write and result["rows_preserved"] and result["assessment"]["state"]=="correct"
        conn.commit()
    result,write=iam.operate(wrapped,"verify")
    assert not write and result["counts"]["row_counts"]["transactions"]==200
    conn.rollback()

def test_postcheck_failure_rolls_back_migration(migration_database,monkeypatch):
    conn,wrapped=migration_database
    original=common.inspect;calls=[]
    def altered(cur):
        c,d,a=original(cur);calls.append(1)
        if len(calls)==2:d["row_counts"]["transactions"]+=1
        return c,d,a
    monkeypatch.setattr(common,"inspect",altered)
    with pytest.raises(common.Refused):iam.operate(wrapped,"migrate")
    conn.rollback();assert inspect(conn)[2]["state"]=="absent"

def test_live_path_refuses_conflict_before_ddl(migration_database):
    conn,wrapped=migration_database
    with conn.cursor() as cur:cur.execute("CREATE INDEX idx_tx_source_identity ON transactions(amount)")
    conn.commit()
    with pytest.raises(common.Refused):iam.operate(wrapped,"migrate")
    conn.rollback()
    c,d,a=inspect(conn);assert len([x for x in c["columns"] if x["name"] in contract.COLUMNS])==0

@pytest.mark.parametrize("row",[(False,True,False,False,False,False,False),(True,True,True,False,False,False,False),(True,True,False,False,True,False,False)])
def test_iam_membership_guard(row,monkeypatch):
    monkeypatch.setattr(common,"session_check",lambda *args:None)
    cur=Mock();cur.fetchone.return_value=row
    with pytest.raises(common.Refused):iam.identity(cur)


def test_transaction_search_path_places_temp_schema_last():
    cur=Mock()
    common.setup(cur,read_only=False)
    cur.execute.assert_any_call("SET LOCAL search_path = pg_catalog, public, pg_temp")
