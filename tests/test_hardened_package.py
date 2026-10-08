"""The hardened build drops SDK examples but preserves required runtime models."""
import hashlib
import json
import zipfile
from tools import package_hardened_lambda as package

def test_sdk_examples_removed_runtime_models_preserved_and_verification_reset(tmp_path, monkeypatch):
    output=tmp_path/'candidate.zip'
    files={'bin/dotenv.exe':b'MZ Windows launcher',
           'bin/flask':b'#!/usr/bin/python3 Linux CLI launcher',
           'boto3/examples/cloudfront.rst':b'public sample credential',
           'botocore/data/sts/2011-06-15/examples-1.json':b'public examples',
           'botocore/data/sts/2011-06-15/service-2.json':b'required service model',
           'fintrust/ingest.py':b'handler source'}
    def fake_build(*args):
        with zipfile.ZipFile(output,'w') as z:
            for name, content in files.items(): z.writestr(name,content)
        return {'linux_execution_verified':True,'sha256':'stale'}
    monkeypatch.setattr(package,'build',fake_build)
    monkeypatch.setattr(package,'verify_archive',lambda p:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    manifest=package.build_hardened(tmp_path/'ca.pem',output)
    with zipfile.ZipFile(output) as z:
        assert set(z.namelist())=={'botocore/data/sts/2011-06-15/service-2.json','fintrust/ingest.py'}
        assert z.read('botocore/data/sts/2011-06-15/service-2.json')==files['botocore/data/sts/2011-06-15/service-2.json']
    assert manifest['sha256']==hashlib.sha256(output.read_bytes()).hexdigest()
    assert manifest['linux_execution_verified'] is False
    assert manifest['excluded_cli_launchers']==['bin/dotenv.exe','bin/flask']
    assert json.loads(output.with_suffix('.manifest.json').read_text())==manifest
