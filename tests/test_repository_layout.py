"""Source/archive layout contracts; no live AWS or database calls."""
import importlib.util
import os
from pathlib import Path
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1]

def test_all_runtime_modules_import_from_backend_without_external_calls():
    program=r'''import os,sys,importlib,pkgutil
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'backend'))
os.environ.update(AWS_ACCESS_KEY_ID='testing',AWS_SECRET_ACCESS_KEY='testing',AWS_SESSION_TOKEN='testing',AWS_REGION='af-south-1',AWS_DEFAULT_REGION='af-south-1',AWS_EC2_METADATA_DISABLED='true',PYTHON_DOTENV_DISABLED='1')
import psycopg2
from botocore.httpsession import URLLib3Session
def denied(*a,**k):raise AssertionError('External I/O during module import')
psycopg2.connect=denied;URLLib3Session.send=denied
count=0
for name in ['fintrust','migration_runner','src']:
 package=importlib.import_module(name)
 for m in pkgutil.walk_packages(package.__path__,name+'.'):
  mod=importlib.import_module(m.name)
  assert Path(mod.__file__).resolve().is_relative_to(Path.cwd()/'backend'),m.name
  count+=1
for handler in ['fintrust.ingest','fintrust.score','fintrust.alert_delivery','fintrust.api','fintrust.report','migration_runner.preflight_entry']:
 assert callable(importlib.import_module(handler).lambda_handler)
print('Backend production modules and stable Lambda handlers imported:',count)
'''
    result=subprocess.run([__import__('sys').executable,'-c',program],cwd=ROOT,env={**os.environ,'PYTHON_DOTENV_DISABLED':'1'},capture_output=True,text=True)
    assert result.returncode==0,result.stderr

@pytest.mark.parametrize('layout',['repository','archive'])
def test_resource_root_matches_source_and_lambda_layout(tmp_path,layout):
    parent=tmp_path/'backend' if layout=='repository' else tmp_path
    package=parent/'fintrust';package.mkdir(parents=True)
    source=package/'paths.py';source.write_bytes((ROOT/'backend/fintrust/paths.py').read_bytes())
    spec=importlib.util.spec_from_file_location('resource_path_check',source)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    assert mod.RESOURCE_ROOT==tmp_path

def test_runtime_source_has_one_authoritative_location():
    for package in ['fintrust','migration_runner','src']:
        assert (ROOT/'backend'/package/'__init__.py').is_file()
        assert not list((ROOT/package).rglob('*.py'))
    for path in ['frontend/js/release1.js','frontend/js/release1-display.js','frontend/css/release1.css','sql/schema.sql','sql/migrations/001_transaction_identity.sql','sql/migrations/002_operational_workflows.sql']:
        assert (ROOT/path).is_file(),path

def test_entry_assets_are_served_from_the_moved_locations():
    import re
    from fintrust import api
    client=api.app.test_client()
    html=client.get('/release1').data.decode('utf-8')
    assets=re.findall(r'(?:src|href)="(/assets/[^"?]+)',html)
    assert set(assets)=={'/assets/css/release1.css','/assets/js/release1-display.js','/assets/js/release1-workflows.js','/assets/js/release1.js','/assets/js/release1-analyst.js','/assets/js/release1-intake-insights.js','/assets/js/release1-cases.js','/assets/js/release1-dashboard.js','/assets/css/release1-dashboard.css'}
    for asset in assets:
        assert client.get(asset).status_code==200,asset
    assert '/assets/js/release1.js' in assets and '/assets/css/release1.css' in assets
