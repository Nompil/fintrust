"""Exercise UI risk totals and navigation without changing business rules."""
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_scored_risk_totals_do_not_infer_historical_risk():
    source = (ROOT / "frontend/release1.js").read_text(encoding="utf-8")
    helper = re.search(r"function riskCount\(.*?\n", source).group(0)
    program = helper + r'''const assert=require('node:assert/strict');
const rows={risk_distribution:[{risk_level:'Low',count:3},{risk_level:'LOW',count:'2'},{risk_level:'Medium',count:1},{risk_level:'High',count:4},{risk_level:null,count:17}]};
assert.equal(riskCount(rows,'Low'),5);assert.equal(riskCount(rows,'Medium'),1);assert.equal(riskCount(rows,'High'),4);
assert.equal(riskCount({risk_distribution:[]},'Low'),0);assert.equal(riskCount({},'Low'),null);assert.equal(riskCount({risk_distribution:null},'High'),null);
'''
    result = subprocess.run([os.environ["FINTRUST_NODE"], "-e", program], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

def test_role_navigation_preserves_auditor_evidence_priority():
    source = (ROOT / "frontend/release1.js").read_text(encoding="utf-8")
    helper = re.search(r"function navigationPages\(.*?\n", source).group(0)
    program = "const pages={Overview:1,Transactions:1,Accounts:1};let principal;" + helper + r'''const assert=require('node:assert/strict');
principal={role:'Read-only/Auditor'};const audit=navigationPages();assert.ok(audit.indexOf('Audit')<audit.indexOf('Ingestion Batches'));assert.ok(audit.indexOf('Reports')<audit.indexOf('Ingestion Batches'));assert.ok(!audit.includes('Upload Transactions'));assert.ok(audit.includes('Accounts')&&audit.includes('Account History'));
principal={role:'Risk/Compliance Analyst'};assert.deepEqual(navigationPages(),Object.keys(pages));
'''
    result = subprocess.run([os.environ["FINTRUST_NODE"], "-e", program], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
