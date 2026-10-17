import json,uuid
import boto3,pytest
from moto import mock_aws
from fintrust.auth import Principal
from fintrust import score,upload_ownership

def test_cloud_admission_is_versioned_immutable_and_never_uses_local_authority(monkeypatch):
    for key,value in {'AUTH_MODE':'cognito','AWS_EXECUTION_ENV':'AWS_Lambda_python3.12','FINTRUST_CLOUD_INTAKE':'1','QUARANTINE_BUCKET':'safe-cloud-evidence'}.items():monkeypatch.setenv(key,value)
    monkeypatch.delenv('FINTRUST_MODE',raising=False)
    with mock_aws():
        client=boto3.client('s3',region_name='af-south-1')
        client.create_bucket(Bucket='safe-cloud-evidence',CreateBucketConfiguration={'LocationConstraint':'af-south-1'})
        client.put_bucket_versioning(Bucket='safe-cloud-evidence',VersioningConfiguration={'Status':'Enabled'})
        monkeypatch.setattr(score,'s3',client)
        batch=str(uuid.uuid4());actor=Principal('analyst01','Risk/Compliance Analyst',(),auth_source='cognito')
        assert upload_ownership.owner(batch) is None
        initial=upload_ownership.claim(batch,actor,{'version':'source-version'})
        assert initial['authority']=='AUTHENTICATED_COGNITO_ADMISSION'
        replay=upload_ownership.claim(batch,Principal('other','Risk/Compliance Analyst',(),auth_source='cognito'),{'version':'different'})
        assert replay==initial and upload_ownership.owner(batch)==initial
        versions=client.list_object_versions(Bucket='safe-cloud-evidence',Prefix=upload_ownership._key(batch))['Versions']
        assert len(versions)==1
        with pytest.raises(PermissionError):upload_ownership.claim(str(uuid.uuid4()),Principal('local','Risk/Compliance Analyst',()),{})
