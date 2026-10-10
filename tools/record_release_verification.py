"""Record actual runner evidence, including failures; require a zero-skip suite."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import xml.etree.ElementTree as ET


def record():
    archive = Path(os.environ.get("FINTRUST_RELEASE_ARCHIVE","build/hardened-release/fintrust-hardened-linux-py312.zip"))
    manifest_path = archive.with_suffix(".manifest.json")
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    junit = Path("test-results/pytest.xml")
    counts = None
    if junit.exists():
        root = ET.parse(junit).getroot()
        suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
        counts = {key: sum(int(s.get(key, 0)) for s in suites)
                  for key in ("tests", "failures", "errors", "skipped")}
        counts["passed"] = counts["tests"] - sum(counts[k] for k in ("failures", "errors", "skipped"))
    actual = hashlib.sha256(archive.read_bytes()).hexdigest() if archive.exists() else None
    probe = manifest.get("linux_verification", {})
    passed = (platform.system() == "Linux" and platform.machine() == "x86_64"
              and platform.python_implementation() == "CPython"
              and platform.python_version_tuple()[:2] == ("3", "12")
              and actual is not None and actual == manifest.get("sha256")
              and manifest.get("content_checked") is True
              and manifest.get("linux_execution_verified") is True
              and probe.get("all_production_modules_checked") is True
              and counts is not None and counts["passed"] > 0
              and not any(counts[k] for k in ("failures", "errors", "skipped")))
    evidence = {"status": "PASSED" if passed else "NOT VERIFIED",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "commit": os.environ["GITHUB_SHA"], "run_id": os.environ["GITHUB_RUN_ID"],
                "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
                "run_url": f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
                "runner": {"os": platform.system(), "architecture": platform.machine(),
                           "python": platform.python_version(), "platform": platform.platform()},
                "artifact_filename": archive.name, "artifact_sha256": actual,
                "artifact_sha256_base64": manifest.get("code_sha256_base64"),
                "manifest_sha256": manifest.get("sha256"),
                "artifact_bytes": archive.stat().st_size if archive.exists() else None,
                "tests": counts, "package": manifest,
                "linux_execution_verified": manifest.get("linux_execution_verified", False),
                "release_gate_passed": bool(passed)}
    folder = Path("docs/EVIDENCE/11-ci")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "hardened-release-linux-ci.json").write_text(json.dumps(evidence, indent=2) + "\n")
    summary = (f"# Exact hardened ZIP Linux gate: {evidence['status']}\n\n"
               f"Run: {evidence['run_url']}\n\nCommit: {evidence['commit']}\n\n"
               f"SHA256: {actual}\n\nRunner: {evidence['runner']}\n\n"
               f"Tests: {counts}\n\nAll production imports: {probe.get('all_production_modules_checked', False)}\n\n"
               "No AWS deployment or activation occurs in this workflow.\n")
    (folder / "hardened-release-linux-ci.md").write_text(summary)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as output:
        output.write(summary)
    if not passed:
        raise RuntimeError("Exact release gate failed; inspect archived probe output and test evidence")


if __name__ == "__main__":
    record()
