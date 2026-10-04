"""Import archived handlers on Linux CPython 3.12 without network access."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import zipfile

from package_lambda import HANDLERS, verify_archive


def verify(path):
    if platform.system() != "Linux" or sys.version_info[:2] != (3, 12):
        raise RuntimeError("This verification requires Linux and CPython 3.12")
    path = Path(path).resolve()
    evidence = verify_archive(path)
    with tempfile.TemporaryDirectory(prefix="fintrust-import-") as folder:
        with zipfile.ZipFile(path) as archive:
            root = Path(folder).resolve()
            if any(not (root / name).resolve().is_relative_to(root) for name in archive.namelist()):
                raise ValueError("Unsafe archive member")
            archive.extractall(root)
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("AWS_", "DB_", "FINTRUST_"))}
        environment.update(AWS_ACCESS_KEY_ID="testing", AWS_SECRET_ACCESS_KEY="testing",
                           AWS_DEFAULT_REGION="af-south-1", AWS_REGION="af-south-1",
                           AWS_EC2_METADATA_DISABLED="true", DB_CONFIG_SOURCE="environment",
                           DB_AUTH_MODE="iam", DB_HOST="db.invalid", DB_NAME="fintrust",
                           DB_USER="fintrust_api_dev", FINTRUST_SERVICE="api", FINTRUST_STAGE="dev",
                           DB_SSLROOTCERT=str(root / "certs/global-bundle.pem"))
        script = "import sys,importlib,socket; sys.path.insert(0, sys.argv[1]); "
        script += "socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('Network disabled')); "
        script += "handlers=" + repr(list(HANDLERS.values())) + "; "
        script += "[getattr(importlib.import_module(h.rsplit('.',1)[0]),h.rsplit('.',1)[1]) for h in handlers]"
        subprocess.run([sys.executable, "-I", "-c", script, str(root)],
                       cwd=root, env=environment, check=True, timeout=60)
    manifest_path = path.with_suffix(".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["sha256"] != evidence["sha256"]:
        raise ValueError("Manifest does not match verified archive")
    manifest["linux_execution_verified"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("All five archived handlers imported on Linux CPython 3.12.")


if __name__ == "__main__":
    verify(sys.argv[1])
