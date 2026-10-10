from pathlib import Path
from unittest.mock import Mock
import pytest
from migration_runner import release1_preflight,common

def test_supplement_enforces_read_only(monkeypatch):
    cur=Mock();cur.fetchone.return_value=({'read_only':'off','objects':[]},)
    with pytest.raises(common.Refused,match='not_read_only'):release1_preflight.supplement(cur)

def test_counts_never_execute_returned_sql():
    cur=Mock();cur.fetchone.return_value=({'read_only':'on','objects':[], 'conditional_count_queries':['DROP TABLE transactions']},)
    result=release1_preflight.supplement(cur)
    assert result['row_counts']=={} and 'conditional_count_queries' not in result
    assert cur.execute.call_count==1

def test_supplement_has_no_writes_or_secret_calls():
    source=Path('migration_runner/release1_preflight.py').read_text(encoding='utf-8')
    assert 'GetSecretValue' not in source and 'pg_authid' not in source
    assert 'schema_migrations ORDER BY version LIMIT 10' in source
