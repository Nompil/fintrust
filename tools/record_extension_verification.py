"""Bind local PG16.15 rehearsal, focused tests and exact phase archives. No AWS."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile
from xml.etree import ElementTree as ET
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.package_migration import inspect


def record():
    directory = ROOT / "build/migration-runner"
    rehearsal = json.loads((directory / "pg16-extensions-rehearsal.json").read_text())
    if rehearsal["status"] != "PASSED" or rehearsal["postgresql_version"] != "16.15":
        raise ValueError("PG16.15 rehearsal required")
    if rehearsal["aws_access"] or rehearsal["live_rds_access"]:
        raise ValueError("Only isolated rehearsal evidence accepted")
    if [m["version"] for m in rehearsal["migrations"]] != [3,4,5,6]:
        raise ValueError("All four extensions required")
    for name, expected in rehearsal["tested_files_sha256"].items():
        actual = hashlib.sha256((ROOT / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        if actual != expected:
            raise ValueError("Tested source changed: " + name)
    suites = list(ET.parse(directory / "extensions-focused.xml").getroot().iter("testsuite"))
    tests = sum(int(s.get("tests",0)) for s in suites)
    if not tests or any(int(s.get(k,0)) for s in suites for k in ("errors","failures","skipped")):
        raise ValueError("Focused tests must pass without skips")
    packages = []
    for phase in ("bootstrap_extensions","iam_extensions","cleanup_extensions"):
        archive = directory / "extensions-packages" / f"fintrust-migration-{phase}.zip"
        path = archive.with_suffix(".manifest.json")
        manifest = json.loads(path.read_text())
        actual = inspect(archive, phase)
        with zipfile.ZipFile(archive) as bundle:
            if json.loads(bundle.read("source-binding.json")) != manifest["source_binding"]:
                raise ValueError("Archive and manifest source bindings differ")
        if any(manifest.get(k) != v for k,v in actual.items()) or not manifest["linux_execution_verified"]:
            raise ValueError("Exact Linux-imported archive required")
        for name, digest in manifest["source_binding"].items():
            if name.startswith("migration_runner/"):
                tested = "backend/" + name
            elif name.startswith("sql/migrations/"):
                tested = name
            else:
                continue
            if rehearsal["tested_files_sha256"].get(tested) != digest:
                raise ValueError("Packaged source differs from rehearsed source: " + name)
        manifest["postgresql16_execution_verified"] = True
        manifest["postgresql_verification_scope"] = "Checksum-identical runner modules and SQL rehearsed via real handlers; local credential transport"
        path.write_text(json.dumps(manifest,indent=2)+"\n")
        packages.append({**actual, "handler": manifest["handler"],
                         "linux_execution_verified": True, "postgresql16_execution_verified": True})
    result = {"status":"LOCAL_RUNNER_GATE_PASSED", "live_deployment":"BLOCKED",
              "quota_gate":"UNRESOLVED", "aws_changed":False, "live_migration_executed":False,
              "postgresql_version":"16.15", "focused_tests_passed":tests,
              "focused_tests_failed":0,"focused_tests_skipped":0,"packages":packages,
              "limitations":["No real RDS IAM/TLS test", "No live schema reconciliation",
                             "Runtime application grants remain a separate gate",
                             "New runner sources are working-tree changes, not a new release commit"]}
    (directory / "extensions-verification.json").write_text(json.dumps(result,indent=2)+"\n")
    return result


if __name__ == "__main__":
    print(json.dumps(record(),indent=2))
