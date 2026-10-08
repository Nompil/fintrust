"""Build the shared hardened archive without SDK example documentation; no AWS calls."""
import argparse
import json
from pathlib import Path
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.package_lambda import build, verify_archive

def is_sdk_example(name):
    return name.startswith('boto3/examples/') or (
        name.startswith('botocore/data/') and name.endswith('/examples-1.json'))

def build_hardened(ca_bundle, output, wheelhouse=None):
    output = Path(output)
    manifest = build(ca_bundle, output, wheelhouse)
    temporary = output.with_suffix('.filtered.zip')
    excluded = []
    try:
        with zipfile.ZipFile(output) as source, zipfile.ZipFile(temporary, 'w') as target:
            for info in source.infolist():
                if is_sdk_example(info.filename):
                    excluded.append(info.filename)
                else:
                    target.writestr(info, source.read(info.filename))
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    manifest.update(verify_archive(output))
    manifest['linux_execution_verified'] = False
    manifest['excluded_sdk_examples'] = excluded
    output.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ca-bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wheelhouse', type=Path)
    args = parser.parse_args()
    print(json.dumps(build_hardened(args.ca_bundle, args.output, args.wheelhouse), indent=2))
