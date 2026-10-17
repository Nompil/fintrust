"""Build separate fixed-phase Linux-wheel archives; never modify application ZIP."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
import zipfile
ROOT=Path(__file__).resolve().parents[1]
PHASES=("base","runtime","demo_reference","preflight","bootstrap","iam","cleanup","bootstrap002","iam002","cleanup002",
        "bootstrap_extensions","iam_extensions","cleanup_extensions")
VERIFIED_APPLICATION_SHA="cf9c18a5f267373e2fc2e22331987bb6dce8e2e65366b2d1f5651bb035dd6654"
VERIFIED_APPLICATION_SHAS = {VERIFIED_APPLICATION_SHA,
    "44e73618102d5b1caa963ed0cfd30fd0ac8c6f1de6f3c1ffbbbbe7e9fbead335",
    "ff6324d64a5d65dab18523a30ea72bb1594d2fa5ca7fbe6b8391c52f03ed589d"}
PREFIXES=("boto3/","botocore/","jmespath/","dateutil/","s3transfer/","urllib3/","psycopg2/","psycopg2_binary.libs/")
DIST=("boto3-","botocore-","jmespath-","python_dateutil-","s3transfer-","six-","urllib3-","psycopg2_binary-")

def selected(name):
    return (name.startswith(PREFIXES) or name=="six.py" or (name.startswith(DIST) and ".dist-info/" in name)) and not name.startswith("boto3/examples/") and not name.endswith("/examples-1.json")

def inspect(path,phase):
    from hashlib import sha256
    path=Path(path)
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or any(n.startswith(("/","\\")) or ".." in Path(n).parts or "\\" in n for n in names):raise ValueError("Unsafe archive")
        if any(n.endswith((".pyd",".dll",".pyc")) or ".env" in Path(n).parts or n.startswith(("fintrust/","tests/","frontend/","src/")) for n in names):raise ValueError("Unexpected archive content")
        driver=[n for n in names if n.startswith("psycopg2/_psycopg") and n.endswith(".so")]
        if len(driver)!=1 or "cpython-312-x86_64" not in driver[0]:raise ValueError("Wrong native ABI")
        for n in names:
            if ".so" in n:
                h=z.read(n)[:20]
                if h[:6]!=b"\x7fELF\x02\x01" or int.from_bytes(h[18:20],"little")!=62:raise ValueError("Not Linux x86_64 ELF")
        if z.testzip():raise ValueError("ZIP CRC failed")
        handler=f"migration_runner/{phase}_entry.py"
        if handler not in names or "certs/global-bundle.pem" not in names:raise ValueError("Missing handler/CA")
        if phase in {"iam","iam002","iam_extensions"} and any(n.endswith("admin.py") or n.startswith("sql/bootstrap/") or n.endswith(("bootstrap_entry.py","preflight_entry.py","cleanup_entry.py")) for n in names):raise ValueError("Administrator code in IAM package")
        if sum(i.file_size for i in z.infolist()) >= 250*1024*1024:raise ValueError("Lambda size limit")
        bindings=json.loads(z.read("source-binding.json"))
        for name,digest in bindings.items():
            if sha256(z.read(name)).hexdigest()!=digest:raise ValueError("Source binding mismatch")
        if phase=="iam" and sha256(z.read("sql/migrations/001_transaction_identity.sql")).hexdigest()!=bindings["sql/migrations/001_transaction_identity.sql"]:raise ValueError("SQL mismatch")
    data=path.read_bytes()
    return {"filename":path.name,"byte_size":len(data),"sha256":sha256(data).hexdigest(),
            "sha256_base64":base64.b64encode(sha256(data).digest()).decode(),"phase":phase,
            "runtime":"python3.12","architecture":"x86_64","target_os":"Linux","psycopg2_binary":"2.9.13"}

def build(phase,out,ca,dependency_archive=None):
    if phase not in PHASES:raise ValueError("Unknown phase")
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    ca=Path(ca).resolve();ssl.create_default_context(cafile=str(ca))
    # Keep staging on the host's temporary filesystem. WSL-mounted workspaces
    # otherwise turn thousands of dependency writes into a lengthy build.
    with tempfile.TemporaryDirectory(prefix="migration-build-") as temp:
        package=Path(temp)
        if dependency_archive:
            dep=Path(dependency_archive).resolve()
            if hashlib.sha256(dep.read_bytes()).hexdigest() not in VERIFIED_APPLICATION_SHAS:raise ValueError("Unverified dependency archive")
            with zipfile.ZipFile(dep) as z:
                for name in z.namelist():
                    if selected(name) and not name.endswith("/"):
                        dest=(package/name).resolve()
                        if not dest.is_relative_to(package):raise ValueError("Unsafe dependency path")
                        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name))
        else:
            subprocess.run([sys.executable,"-m","pip","install","--disable-pip-version-check","--no-compile","--platform","manylinux2014_x86_64","--implementation","cp","--python-version","3.12","--only-binary=:all:","--no-deps","--target",str(package),"-r",str(ROOT/"requirements-migration.txt")],check=True)
        modules=["__init__.py","config.py","contract.py","common.py","sql_binding.py",phase+"_entry.py","iam.py" if phase in {"iam","iam002","iam_extensions"} else "admin.py"]
        sources=["migration_runner/"+n for n in modules]+["sql/preflight/001_transaction_identity_catalog.sql","sql/preflight/001_transaction_identity_data.sql"]
        if phase=="preflight":sources += ["migration_runner/release1_preflight.py","sql/preflight/002_release1_catalog.sql"]
        if phase=="base":sources += ["migration_runner/base.py","sql/schema.sql"]
        if phase=="demo_reference":sources += ["migration_runner/demo_reference.py"]
        if phase=="runtime":sources += ["migration_runner/runtime.py","migration_runner/extension_catalog.py",
            "migration_runner/workflow_catalog.py","infrastructure/rds/permissions.sql","infrastructure/rds/release1_permissions.sql"]
        if phase.endswith("002") or phase.endswith("_extensions"):
            sources += ["migration_runner/workflows.py","migration_runner/workflow_catalog.py","migration_runner/iam.py","sql/migrations/002_operational_workflows.sql"]
            sources=list(dict.fromkeys(sources))
        if phase.endswith("_extensions"):
            sources += ["migration_runner/extensions.py", "migration_runner/extension_catalog.py"]
            sources += ["sql/migrations/"+name for name in (
                "003_transaction_lifecycle.sql", "004_review_assignment.sql",
                "005_investigation_notes.sql", "006_versioned_risk_review.sql")]
        if phase=="iam":sources.append("sql/migrations/001_transaction_identity.sql")
        elif phase=="bootstrap":sources.extend(["sql/bootstrap/temporary_identity.sql","sql/bootstrap/fixed_identity_indexes.sql"])
        elif phase=="cleanup":sources.append("sql/bootstrap/remove_temporary_identity.sql")
        bindings={}
        for name in sources:
            source=ROOT/"backend"/name if name.startswith("migration_runner/") else ROOT/name
            content=source.read_bytes().replace(b"\r\n",b"\n")
            target=package/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
            bindings[name]=hashlib.sha256(content).hexdigest()
        (package/"certs").mkdir();shutil.copyfile(ca,package/"certs/global-bundle.pem")
        bindings["certs/global-bundle.pem"]=hashlib.sha256(ca.read_bytes()).hexdigest()
        (package/"source-binding.json").write_text(json.dumps(bindings,sort_keys=True),encoding="utf-8")
        target=out/f"fintrust-migration-{phase}.zip"
        with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED) as z:
            for p in sorted(package.rglob("*")):
                if not p.is_file() or "__pycache__" in p.parts or p.parts[len(package.parts)]=="bin":continue
                name=p.relative_to(package).as_posix()
                if name.startswith("boto3/examples/") or name.endswith("/examples-1.json"):continue
                info=zipfile.ZipInfo(name);info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
                z.writestr(info,p.read_bytes())
    manifest={**inspect(target,phase),"linux_execution_verified":False,"postgresql16_execution_verified":False,
              "handler":f"migration_runner.{phase}_entry.lambda_handler","source_binding":bindings,
              "dependency_source":"verified application ZIP (read-only subset)" if dependency_archive else "pinned Linux wheels"}
    if dependency_archive:
        manifest["dependency_archive_sha256"] = hashlib.sha256(Path(dependency_archive).read_bytes()).hexdigest()
    target.with_suffix(".manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--phase",choices=PHASES,required=True);p.add_argument("--output",default="build/migration-runner");p.add_argument("--ca-bundle",required=True);p.add_argument("--dependency-archive")
    a=p.parse_args();print(json.dumps(build(a.phase,a.output,a.ca_bundle,a.dependency_archive),indent=2))
