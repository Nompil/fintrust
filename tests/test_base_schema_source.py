"""Offline source composition checks; these do not claim PostgreSQL 16 execution."""
import pytest
from tools import render_release1_base as base

def test_base_has_no_identity_or_workflow_or_seed():
    text=base.render()
    assert "CREATE TABLE IF NOT EXISTS transactions" in text
    assert "source_transaction_id" not in text and "ingestion_batches" not in text
    assert "INSERT INTO customers" not in text and "INSERT INTO transactions" not in text
    assert "requires an empty application schema" in text
    assert text.endswith("COMMIT;\n")

def test_source_change_requires_review(tmp_path,monkeypatch):
    import shutil
    (tmp_path/"sql/bootstrap").mkdir(parents=True)
    shutil.copy(base.ROOT/"sql/bootstrap/release1-base-manifest.json",tmp_path/"sql/bootstrap/release1-base-manifest.json")
    (tmp_path/"sql/schema.sql").write_text("changed\n-- Additive identity hardening.",encoding="utf-8")
    monkeypatch.setattr(base,"ROOT",tmp_path)
    with pytest.raises(ValueError,match="checksum"):base.render()
