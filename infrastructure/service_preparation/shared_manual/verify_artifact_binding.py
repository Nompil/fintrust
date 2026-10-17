"""Verify saved version/checksum bindings offline; never contact AWS."""
import base64
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def verify():
    plan = read(HERE / 'artifact-upload-plan.json')
    receipt = read(HERE / 'artifact-staging-live.json')
    worksheet = read(REPO / 'docs/EVIDENCE/11-ci/consolidated-release-2026-10-16/live-deployment-inputs.json')
    assert receipt['status'] == 'UPLOADED_VERSION_BYTES_VERIFIED_TEMP_PERMISSION_REMOVED'
    assert receipt['temporary_permission_removal_verified'] and receipt['exact_version_bytes_verified']
    assert not receipt['temporary_policy_attached'] and not receipt['temporary_policy_created']
    assert receipt['attachment_count_before'] == receipt['attachment_count_after']
    assert not receipt['policy_validation']['findings']
    assert receipt['atomic_create_only']
    for key in ('bucket', 'key', 'version_id'):
        assert plan[key] == receipt[key] == worksheet['artifact_staging'][key]
    assert receipt['expected_sha256'] == receipt['downloaded_version_sha256'] == plan['sha256'] == worksheet['artifact_sha256']
    checksum = base64.b64encode(bytes.fromhex(plan['sha256'])).decode()
    assert checksum == plan['checksum_sha256_base64'] == receipt['put_result']['ChecksumSHA256'] == receipt['get_result']['ChecksumSHA256']
    assert receipt['get_result']['ContentLength'] == receipt['size_bytes'] == plan['size_bytes']
    assert receipt['get_result']['VersionId'] == receipt['version_id'] != 'null'
    assert receipt['put_result']['VersionId'] == receipt['version_id']
    assert receipt['get_result']['ServerSideEncryption'] == 'aws:kms'
    parameters = worksheet.get('parameters', worksheet.get('template_parameters'))['application-functions.json']
    assert parameters['CodeBucket'] == receipt['bucket']
    assert parameters['CodeKey'] == receipt['key']
    assert parameters['CodeObjectVersion'] == receipt['version_id']
    assert parameters['CodeSha256'] == checksum
    assert worksheet['artifact_uploaded']
    for flag in ('deploy_functions', 'invoke_functions', 'activate_triggers', 'new_bucket'):
        assert not receipt[flag]
    return {'artifact_version_bindings': 'PASS', 'checksum_bindings': 'PASS',
            'temporary_permission_cleanup_receipt': 'PASS',
            'version_id': receipt['version_id'], 'deployment_ready': False}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
