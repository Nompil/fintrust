"""Focused fixed 002 source, catalog and fail-closed checks; PG16 ACL proof is CI."""
import ast,hashlib
from pathlib import Path
from unittest.mock import Mock
import pytest
from migration_runner import workflows,common,workflow_catalog
from fintrust.migrations import _catalog,apply_local
from test_private_rds_preflight import isolated,base
ROOT=Path(__file__).resolve().parents[1]

def test_fixed_source_wrapper_and_hash():
    body=workflows.migration_body()
    assert "CREATE TABLE public.ingestion_batches" in body and not body.endswith("COMMIT;\n")
    assert hashlib.sha256((ROOT/'sql/migrations/002_operational_workflows.sql').read_bytes().replace(b'\r\n',b'\n')).hexdigest()==workflows.WORKFLOW_SHA256

def test_modified_sql_refused(tmp_path,monkeypatch):
    target=tmp_path/'sql/migrations';target.mkdir(parents=True)
    (target/'002_operational_workflows.sql').write_text('BEGIN;\nDROP TABLE public.transactions;\nCOMMIT;\n')
    monkeypatch.setattr(workflows.config,'ROOT',tmp_path)
    with pytest.raises(common.Refused,match='hash_mismatch'):workflows.migration_body()

def test_catalog_copy_matches_frozen_contract_ast():
    original=ast.parse((ROOT/'fintrust/migrations.py').read_text(encoding='utf-8'))
    copied=ast.parse((ROOT/'migration_runner/workflow_catalog.py').read_text(encoding='utf-8'))
    fn=lambda tree:next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_catalog')
    assert ast.dump(fn(original),include_attributes=False)==ast.dump(fn(copied),include_attributes=False)

def test_real_catalog_signatures_match_both_migrations(isolated):
    conn,schema=isolated;base(conn)
    for version in (1,2):
        apply_local(conn,version,schema=schema)
        with conn.cursor() as cur:assert workflow_catalog._catalog(cur,schema,version)==_catalog(cur,schema,version)
        conn.rollback()
    with conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM "'+schema+'".transactions');assert cur.fetchone()[0]==200
    conn.rollback()

@pytest.mark.parametrize('op',['migrate','arbitrary-sql','bootstrap002','cleanup002'])
def test_iam002_surface_rejects_other_operations(op):
    conn=Mock()
    with pytest.raises(common.Refused):workflows.operate(conn,op)
    conn.cursor.assert_not_called()

def test_helper_has_no_user_sql_or_owner_set_path():
    source=(ROOT/'migration_runner/workflows.py').read_text(encoding='utf-8')
    executor=source[source.index('def operate'):source.index('def bootstrap')]
    assert 'SELECT public.fintrust_create_release1_workflows()' in executor
    assert 'SET LOCAL ROLE fintrust_workflow_owner' not in executor
    assert 'migration_body()' not in executor
    assert 'verify(cur)' in executor and 'baseline(cur)!=before' in executor
    assert 'partial_workflow_state' in executor and 'ALREADY_APPLIED' in executor

def test_catalog_supplement_is_bound_in_preflight_package():
    source=(ROOT/'tools/package_migration.py').read_text(encoding='utf-8')
    assert 'migration_runner/release1_preflight.py' in source and 'sql/preflight/002_release1_catalog.sql' in source

@pytest.mark.parametrize('phase',['bootstrap002','iam002','cleanup002'])
def test_002_phase_is_separate_and_disabled(phase):
    from infrastructure.migration import runner_template,runtime_policy
    template=runner_template(phase)['Resources']['Runner']['Properties']
    assert template['Handler']==f'migration_runner.{phase}_entry.lambda_handler'
    assert template['ReservedConcurrentExecutions']==0
    if phase=='iam002':
        policy=runtime_policy(phase,'vpce-123456789')
        assert any(s['Effect']=='Deny' and 'secretsmanager:GetSecretValue' in s['Action'] for s in policy['Statement'])
