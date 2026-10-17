"""Additive exact-resource supplements; no existing grant is replaced."""
from pathlib import Path
import json
ACCOUNT='966467878406';REGION='af-south-1';BASE=f'arn:aws:s3:::fintrust-'
RAW=f'{BASE}raw-{ACCOUNT}-{REGION}-dev';SAFE=f'{BASE}quarantine-{ACCOUNT}-{REGION}-dev'
KMS=f'arn:aws:kms:{REGION}:{ACCOUNT}:key/598a4158-2cc6-4946-af24-512784a276c8'

def allow(sid,actions,resources,condition=None):
    item={'Sid':sid,'Effect':'Allow','Action':actions,'Resource':resources}
    if condition:item['Condition']=condition
    return item

def render():
    folder=Path(__file__).resolve().parent
    def kms(sid,actions,bucket,prefix):
        return allow(sid,actions,KMS,{'StringEquals':{'kms:ViaService':f's3.{REGION}.amazonaws.com','kms:CallerAccount':ACCOUNT},
              'StringLike':{'kms:EncryptionContext:aws:s3:arn':[bucket,bucket+'/'+prefix]}})
    docs={
     'ingest':[
        allow('ReadFrozenPublicationReceipts',['s3:GetObject','s3:GetObjectVersion'],SAFE+'/quarantine/batches/*'),
        allow('FindFrozenPublicationReceipts',['s3:ListBucket'],SAFE,{'StringLike':{'s3:prefix':['quarantine/batches/*']}}),
        kms('DecryptFrozenPublicationReceipts',['kms:Decrypt'],SAFE,'quarantine/batches/*')],
     'api':[
        allow('StoreScopedVersionedUploads',['s3:PutObject'],RAW+'/raw/uploads/*'),
        allow('ReadAdmissionAndUIReceipts',['s3:GetObject','s3:GetObjectVersion'],[SAFE+'/quarantine/upload-owners/*',SAFE+'/quarantine/ui-events/*']),
        allow('WriteImmutableAdmissionAndUIReceipts',['s3:PutObject'],[SAFE+'/quarantine/upload-owners/*',SAFE+'/quarantine/ui-events/*']),
        allow('ListAdmissionAndUIReceipts',['s3:ListBucket'],SAFE,{'StringLike':{'s3:prefix':['quarantine/upload-owners/*','quarantine/ui-events/*']}}),
        kms('EncryptScopedRawUploads',['kms:GenerateDataKey','kms:Decrypt'],RAW,'raw/uploads/*')],
     'alert':[allow('CreateFirstDeliveryClaim',['dynamodb:PutItem'],f'arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/fintrust-risk-dev')]
    }
    for name,statements in docs.items():
        (folder/('runtime-'+name+'-supplement.json')).write_text(json.dumps({'Version':'2012-10-17','Statement':statements},indent=2)+'\n',encoding='utf-8',newline='\n')
    return docs

if __name__=='__main__':render();print('RUNTIME SUPPLEMENTS PREPARED; NOT INSTALLED')
