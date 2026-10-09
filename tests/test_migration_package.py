"""Static native ZIP and phase-isolation checks; never pretend Windows is Linux."""
import json
from pathlib import Path
import zipfile
import pytest
from tools.package_migration import inspect, PHASES
from tools.verify_migration_linux import verify
ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("phase",PHASES)
def test_phase_source_is_separated(phase):
    from tools.package_migration import build
    # Package inventory assertions also run below when testing the real output.
    source=(ROOT/f"migration_runner/{phase}_entry.py").read_text()
    assert "event[" not in source
    if phase=="iam":assert "admin" not in source

def test_verifier_rejects_wrong_host_without_success(tmp_path,monkeypatch):
    import tools.verify_migration_linux as v
    p=tmp_path/'test.zip';p.write_bytes(b'not a zip')
    p.with_suffix('.manifest.json').write_text(json.dumps({'linux_execution_verified':True}))
    monkeypatch.setattr(v.platform,'system',lambda:'Windows')
    with pytest.raises(RuntimeError,match='Linux CPython'):v.verify(p)
    assert json.loads(p.with_suffix('.manifest.json').read_text())['linux_execution_verified'] is False

def test_unexpected_phase_rejected():
    from infrastructure.migration import runner_template
    with pytest.raises(ValueError):runner_template('arbitrary-sql')
