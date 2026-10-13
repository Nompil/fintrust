"""Actual new mock-service sessions; exact version/delivery state must survive."""
import json
from decimal import Decimal
import boto3,pytest
from moto import mock_aws
from botocore.exceptions import ClientError
from tools.local_runtime_store import LocalStore,DurableS3,DurableDynamo

def services(store):
    client=boto3.client('s3',region_name='af-south-1')
    client.create_bucket(Bucket='local-safe',CreateBucketConfiguration={'LocationConstraint':'af-south-1'})
    client.put_bucket_versioning(Bucket='local-safe',VersioningConfiguration={'Status':'Enabled'})
    resource=boto3.resource('dynamodb',region_name='af-south-1')
    resource.create_table(TableName='local-scores',BillingMode='PAY_PER_REQUEST',AttributeDefinitions=[{'AttributeName':x,'AttributeType':'S'} for x in ('account_id','score_date')],KeySchema=[{'AttributeName':'account_id','KeyType':'HASH'},{'AttributeName':'score_date','KeyType':'RANGE'}])
    return DurableS3(client,store),DurableDynamo(resource,store).Table('local-scores')

def test_exact_versions_and_conditional_delivery_survive_restart(tmp_path):
    path=tmp_path/'services.sqlite';key={'account_id':'synthetic','score_date':'ALERT#synthetic'}
    with mock_aws():
        s3,table=services(LocalStore(path));v1=s3.put_object(Bucket='local-safe',Key='original',Body=b'original')['VersionId'];v2=s3.put_object(Bucket='local-safe',Key='original',Body=b'correction')['VersionId']
        table.put_item(Item={**key,'delivery_state':'SENT','risk_score':Decimal('4.25'),'provider_message_id':'synthetic-receipt'})
        with pytest.raises(ClientError):table.put_item(Item={**key,'delivery_state':'PENDING'},ConditionExpression='attribute_not_exists(account_id)')
    with mock_aws():
        s3,table=services(LocalStore(path))
        assert s3.get_object(Bucket='local-safe',Key='original',VersionId=v1)['Body'].read()==b'original'
        assert s3.get_object(Bucket='local-safe',Key='original',VersionId=v2)['Body'].read()==b'correction'
        assert s3.get_object(Bucket='local-safe',Key='original')['VersionId']==v2
        item=table.get_item(Key=key)['Item'];assert item['delivery_state']=='SENT' and item['risk_score']==Decimal('4.25') and item['provider_message_id']=='synthetic-receipt'
        with pytest.raises(ClientError):s3.get_object(Bucket='local-safe',Key='original',VersionId='nonexistent')
        with pytest.raises(ClientError):s3.put_object(Bucket='local-safe',Key='original',Body=b'overwrite',IfNoneMatch='*')
        assert s3.list_objects_v2(Bucket='local-safe')['Contents'][0]['Key']=='original'

def test_object_integrity_detects_corruption(tmp_path):
    store=LocalStore(tmp_path/'services.sqlite')
    with mock_aws():
        s3,_=services(store);version=s3.put_object(Bucket='local-safe',Key='original',Body=b'exact')['VersionId']
        with store.connect() as c:c.execute("UPDATE objects SET body=? WHERE key='original'",(b'corrupt',))
        with pytest.raises(RuntimeError,match='integrity'):s3.get_object(Bucket='local-safe',Key='original',VersionId=version)
