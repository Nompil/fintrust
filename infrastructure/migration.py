"""Offline temporary migration templates/policies. No boto3 or AWS mutations."""
import sys as _runtime_sys
from pathlib import Path as _RuntimePath
_runtime_sys.path.insert(0, str(_RuntimePath(__file__).resolve().parents[1]/"backend"))
import argparse
from copy import deepcopy
import json
from pathlib import Path
from migration_runner import config
ACCOUNT="966467878406"
REGION=config.REGION
PREFIX=f"arn:aws:"
VPC="vpc-0aba008bb360f5147"
SUBNET="subnet-0c2d87e8a83361e30"
APP_SG="sg-0850bd798bb9505e2"
ROLE=f"arn:aws:iam::{ACCOUNT}:role/fintrust-migration-dev"
BOUNDARY=f"arn:aws:iam::{ACCOUNT}:policy/FinTrustMigrationBoundary"
FUNCTION=f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:fintrust-migration-dev"
LOG=f"arn:aws:logs:{REGION}:{ACCOUNT}:log-group:/aws/lambda/fintrust-migration-dev"
DBUSER=f"arn:aws:rds-db:{REGION}:{ACCOUNT}:dbuser:db-QZ3JN4H22YOMU7VLI22RL2IUYQ/fintrust_migrate_dev"
BUCKET=f"fintrust-reports-{ACCOUNT}-{REGION}-dev"
ENI=["ec2:CreateNetworkInterface","ec2:DescribeNetworkInterfaces","ec2:DescribeSubnets",
     "ec2:DeleteNetworkInterface","ec2:AssignPrivateIpAddresses","ec2:UnassignPrivateIpAddresses"]
TAGS=[{"Key":"Project","Value":"FinTrust"},{"Key":"Environment","Value":"dev"},{"Key":"Purpose","Value":"temporary-migration"}]
PHASES=("preflight","bootstrap","iam","cleanup","bootstrap002","iam002","cleanup002",
        "bootstrap_extensions","iam_extensions","cleanup_extensions")

def allow(sid,actions,resource,conditions=None,effect="Allow"):
    s={"Sid":sid,"Effect":effect,"Action":actions,"Resource":resource}
    if conditions:s["Condition"]=conditions
    return s

def regional():return {"StringEquals":{"aws:RequestedRegion":REGION}}

def mediated(tagged=False):
    c=regional()
    if tagged:c["StringEquals"].update({"aws:RequestTag/Project":"FinTrust","aws:RequestTag/Environment":"dev","aws:RequestTag/Purpose":"temporary-migration"})
    c["ForAnyValue:StringEquals"]={"aws:CalledVia":["cloudformation.amazonaws.com"]}
    return c

def owned():
    c=mediated();c["StringEquals"].update({"aws:ResourceTag/Project":"FinTrust","aws:ResourceTag/Environment":"dev","aws:ResourceTag/Purpose":"temporary-migration"});return c

def endpoint_policy():
    s=allow("OnlyMigrationRole",["secretsmanager:GetSecretValue"],config.SECRET,
            {"ArnEquals":{"aws:PrincipalArn":ROLE}})
    s["Principal"]="*"
    return {"Version":"2012-10-17","Statement":[s]}

def runtime_policy(phase,endpoint):
    if phase not in PHASES:raise ValueError("Invalid phase")
    statements=[allow("Logs",["logs:CreateLogStream","logs:PutLogEvents"],LOG+":log-stream:*",regional()),
                allow("LambdaEni",ENI,"*",regional()),
                allow("NoCodeEni",ENI,"*",{"ArnEquals":{"lambda:SourceFunctionArn":FUNCTION}},"Deny")]
    if phase in {"iam","iam002","iam_extensions"}:
        statements += [allow("NoMaster",["secretsmanager:GetSecretValue"],config.SECRET,effect="Deny"),
                       allow("MigrationLogin",["rds-db:connect"],DBUSER)]
    else:
        c=regional();c["StringEquals"].update({"aws:SourceVpce":endpoint,"secretsmanager:VersionStage":"AWSCURRENT"})
        statements.append(allow("MasterViaEndpoint",["secretsmanager:GetSecretValue"],config.SECRET,c))
    return {"Version":"2012-10-17","Statement":statements}

def boundary(endpoint):
    p=runtime_policy("preflight",endpoint)
    p["Statement"].append(allow("MigrationLogin",["rds-db:connect"],DBUSER))
    return p

def network_template():
    # Single AZ for BOTH Lambda and endpoint. No silently selected second subnet.
    endpoint_sg={"Type":"AWS::EC2::SecurityGroup","Properties":{
        "GroupName":"fintrust-migration-secrets-endpoint-dev","GroupDescription":"Temporary Secrets Manager private HTTPS",
        "VpcId":VPC,"SecurityGroupEgress":[{"IpProtocol":"-1","CidrIp":"127.0.0.1/32","Description":"Suppress EC2 default outbound rule"}],"Tags":TAGS}}
    client={"Type":"AWS::EC2::SecurityGroup","Properties":{
        "GroupName":"fintrust-migration-client-dev","GroupDescription":"Temporary migration HTTPS client",
        "VpcId":VPC,"SecurityGroupEgress":[{"IpProtocol":"tcp","FromPort":443,"ToPort":443,"DestinationSecurityGroupId":{"Ref":"EndpointSecurityGroup"}}],"Tags":TAGS}}
    return {"AWSTemplateFormatVersion":"2010-09-09","Description":"REVIEW ONLY: temporary single-AZ Secrets Manager path; no existing DB SG changes",
      "Resources":{
       "EndpointSecurityGroup":endpoint_sg,"ClientSecurityGroup":client,
       "EndpointIngress":{"Type":"AWS::EC2::SecurityGroupIngress","Properties":{"GroupId":{"Ref":"EndpointSecurityGroup"},"SourceSecurityGroupId":{"Ref":"ClientSecurityGroup"},"IpProtocol":"tcp","FromPort":443,"ToPort":443}},
       "SecretsEndpoint":{"Type":"AWS::EC2::VPCEndpoint","DependsOn":"EndpointIngress","Properties":{"VpcId":VPC,"VpcEndpointType":"Interface","ServiceName":"com.amazonaws.af-south-1.secretsmanager","PrivateDnsEnabled":True,"IpAddressType":"ipv4","SubnetIds":[SUBNET],"SecurityGroupIds":[{"Ref":"EndpointSecurityGroup"}],"PolicyDocument":endpoint_policy(),"Tags":TAGS}}},
      "Outputs":{"EndpointId":{"Value":{"Ref":"SecretsEndpoint"}},"ClientSecurityGroupId":{"Value":{"Ref":"ClientSecurityGroup"}}}}

def runner_template(phase):
    if phase not in PHASES:raise ValueError("Invalid phase")
    return {"AWSTemplateFormatVersion":"2010-09-09","Description":f"REVIEW ONLY: temporary migration {phase}; concurrency zero; qualified version only",
      "Parameters":{
        "EndpointId":{"Type":"String","AllowedPattern":"vpce-[a-f0-9]+"},
        "ClientSecurityGroupId":{"Type":"String","AllowedPattern":"sg-[a-f0-9]+"},
        "CodeKey":{"Type":"String","AllowedPattern":f"deployment/migration/[a-f0-9]{{64}}/fintrust-migration-{phase}\\.zip"},
        "CodeObjectVersion":{"Type":"String","MinLength":1,"AllowedPattern":"(?!null$)[A-Za-z0-9._+/=-]+"},
        "CodeSha256":{"Type":"String","AllowedPattern":"[A-Za-z0-9+/]{43}="}},
      "Resources":{
       "RunnerLogs":{"Type":"AWS::Logs::LogGroup","DeletionPolicy":"Retain","UpdateReplacePolicy":"Retain","Properties":{"LogGroupName":"/aws/lambda/fintrust-migration-dev","RetentionInDays":14,"Tags":TAGS}},
       "Runner":{"Type":"AWS::Lambda::Function","DependsOn":"RunnerLogs","Properties":{
         "FunctionName":"fintrust-migration-dev","Runtime":"python3.12","Architectures":["x86_64"],"Handler":f"migration_runner.{phase}_entry.lambda_handler",
         "MemorySize":512,"Timeout":300,"ReservedConcurrentExecutions":0,"Role":ROLE,"Tags":TAGS,
         "Code":{"S3Bucket":BUCKET,"S3Key":{"Ref":"CodeKey"},"S3ObjectVersion":{"Ref":"CodeObjectVersion"}},
         "VpcConfig":{"SubnetIds":[SUBNET],"SecurityGroupIds":[APP_SG,{"Ref":"ClientSecurityGroupId"}],"Ipv6AllowedForDualStack":False}}},
       "RunnerVersion":{"Type":"AWS::Lambda::Version","Properties":{"FunctionName":{"Ref":"Runner"},"CodeSha256":{"Ref":"CodeSha256"},"Description":f"Reviewed {phase}; do not invoke unqualified function"}}},
      "Outputs":{"QualifiedRunnerArn":{"Value":{"Ref":"RunnerVersion"}}}}

def deployment_policy():
    # Separate bootstrap/operator role, NOT existing Stage 1 deployer with explicit
    # interface-endpoint Deny. Boundary creation/version changes stay administrator-only.
    stacks=[f"arn:aws:cloudformation:{REGION}:{ACCOUNT}:stack/fintrust-migration-{s}-dev/*" for s in ("network","runner")]
    ec2=f"arn:aws:ec2:{REGION}:{ACCOUNT}:"
    statements=[allow("Validate",["cloudformation:ValidateTemplate","cloudformation:GetTemplateSummary"],"*",regional())]
    types={"network":["AWS::EC2::SecurityGroup","AWS::EC2::SecurityGroupIngress","AWS::EC2::VPCEndpoint"],
           "runner":["AWS::Lambda::Function","AWS::Lambda::Version","AWS::Logs::LogGroup"]}
    for stage,stack in zip(("network","runner"),stacks):
        c=regional();c["StringEquals"].update({"aws:RequestTag/Project":"FinTrust","aws:RequestTag/Environment":"dev","aws:RequestTag/Purpose":"temporary-migration"})
        c["ForAllValues:StringEquals"]={"cloudformation:ResourceTypes":types[stage]}
        c["Null"]={"cloudformation:ResourceTypes":"false","cloudformation:RoleArn":"true","cloudformation:ImportResourceTypes":"true"}
        c["StringLike"]={"cloudformation:ChangeSetName":f"fintrust-migration-{stage}-*"}
        statements.append(allow("Prepare"+stage.title(),["cloudformation:CreateChangeSet"],stack,c))
    statements += [allow("ReadStacks",["cloudformation:DescribeChangeSet","cloudformation:DescribeStacks","cloudformation:DescribeStackEvents","cloudformation:DescribeStackResource","cloudformation:ListStackResources","cloudformation:GetTemplate"],stacks,regional()),
       allow("ManageReviewedSets",["cloudformation:ExecuteChangeSet","cloudformation:DeleteChangeSet"],stacks,{**regional(),"StringLike":{"cloudformation:ChangeSetName":"fintrust-migration-*"}}),
       allow("DeleteTemporaryStacks",["cloudformation:DeleteStack"],stacks,{**regional(),"Null":{"cloudformation:RoleArn":"true"}}),
       allow("ReadNetwork",["ec2:DescribeVpcs","ec2:DescribeSubnets","ec2:DescribeSecurityGroups","ec2:DescribeSecurityGroupRules","ec2:DescribeVpcEndpoints","ec2:DescribeVpcEndpointServices","ec2:GetSecurityGroupsForVpc"],"*",regional()),
       allow("CreateTemporarySg",["ec2:CreateSecurityGroup"],ec2+"security-group/*",mediated(True)),
       allow("UseExistingVpc",["ec2:CreateSecurityGroup","ec2:CreateVpcEndpoint"],ec2+"vpc/"+VPC,mediated()),
       allow("UseSingleSubnet",["ec2:CreateVpcEndpoint"],ec2+"subnet/"+SUBNET,mediated()),
       allow("UseOwnedEndpointSg",["ec2:CreateVpcEndpoint"],ec2+"security-group/*",owned()),
       allow("CreateSecretEndpoint",["ec2:CreateVpcEndpoint"],ec2+"vpc-endpoint/*",mediated(True)),
       allow("OwnTemporarySgRules",["ec2:AuthorizeSecurityGroupIngress","ec2:AuthorizeSecurityGroupEgress","ec2:RevokeSecurityGroupIngress","ec2:RevokeSecurityGroupEgress","ec2:DeleteSecurityGroup"],ec2+"security-group/*",owned()),
       allow("RemoveEndpoint",["ec2:DeleteVpcEndpoints"],ec2+"vpc-endpoint/*",owned()),
       allow("CreationTags",["ec2:CreateTags"],[ec2+"security-group/*",ec2+"vpc-endpoint/*"],{**mediated(True),"StringLike":{"ec2:CreateAction":["CreateSecurityGroup","CreateVpcEndpoint"]}})]
    next(s for s in statements if s["Sid"]=="CreateSecretEndpoint")["Condition"]["StringEquals"].update({"ec2:VpceServiceName":"com.amazonaws.af-south-1.secretsmanager"})
    statements += [
       allow("PassOnlyRunner",["iam:PassRole"],ROLE,{**mediated(),"StringEquals":{"aws:RequestedRegion":REGION,"iam:PassedToService":"lambda.amazonaws.com"}}),
       allow("CreateFunction",["lambda:CreateFunction","lambda:TagResource"],FUNCTION,mediated(True)),
       allow("ManageFunction",["lambda:UpdateFunctionCode","lambda:UpdateFunctionConfiguration","lambda:PutFunctionConcurrency","lambda:DeleteFunction","lambda:PublishVersion"],[FUNCTION,FUNCTION+":*"],mediated()),
       allow("ReadFunction",["lambda:GetFunction","lambda:GetFunctionConfiguration","lambda:GetFunctionConcurrency","lambda:ListVersionsByFunction","lambda:ListTags"],[FUNCTION,FUNCTION+":*"],regional()),
       allow("CreateLogs",["logs:CreateLogGroup"],LOG+":*",mediated(True)),
       allow("LegacyTagLogs",["logs:TagLogGroup"],LOG+":*",regional()),
       allow("TagLogs",["logs:TagResource"],LOG,mediated(True)),
       allow("Retention",["logs:PutRetentionPolicy"],LOG+":*",mediated()),
       allow("ReadLogGroups",["logs:DescribeLogGroups"],"*",regional()),
       allow("ReadLogTags",["logs:ListTagsForResource"],LOG,regional())]
    return {"Version":"2012-10-17","Statement":statements}

def bootstrap_policy():
    # Administrator review-only policy: contents of trust/inline/boundary JSON
    # cannot be constrained by IAM actions. Keep it off the deployer role.
    return {"Version":"2012-10-17","Statement":[
      allow("CreateReviewedBoundary",["iam:CreatePolicy","iam:GetPolicy","iam:GetPolicyVersion"],BOUNDARY),
      allow("CreateBoundedRunnerRole",["iam:CreateRole"],ROLE,{"StringEquals":{"iam:PermissionsBoundary":BOUNDARY,"aws:RequestTag/Project":"FinTrust","aws:RequestTag/Environment":"dev","aws:RequestTag/Purpose":"temporary-migration"}}),
      allow("ManageRunnerPhasePolicy",["iam:PutRolePolicy","iam:DeleteRolePolicy","iam:GetRole","iam:GetRolePolicy","iam:ListRolePolicies","iam:TagRole","iam:DeleteRole"],ROLE),
      allow("RemoveTemporaryBoundary",["iam:DeletePolicy"],BOUNDARY)]}

def trust():
    return {"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}

def artifact_policy(sha,version,phase):
    import re
    if not re.fullmatch("[a-f0-9]{64}",sha) or not version or version=="null" or phase not in PHASES:raise ValueError("Exact verified artifact binding required")
    key=f"deployment/migration/{sha}/fintrust-migration-{phase}.zip"
    return {"Version":"2012-10-17","Statement":[
      allow("ReadVersion",["s3:GetObjectVersion"],f"arn:aws:s3:::{BUCKET}/{key}",{"StringEquals":{"s3:VersionId":version,"aws:RequestedRegion":REGION}}),
      allow("DecryptCodeViaS3",["kms:Decrypt"],f"arn:aws:kms:{REGION}:{ACCOUNT}:key/598a4158-2cc6-4946-af24-512784a276c8",{"StringEquals":{"aws:RequestedRegion":REGION,"kms:ViaService":f"s3.{REGION}.amazonaws.com","kms:CallerAccount":ACCOUNT,"kms:EncryptionContext:aws:s3:arn":[f"arn:aws:s3:::{BUCKET}",f"arn:aws:s3:::{BUCKET}/{key}"]}})]}

def render(out, endpoint="__VERIFIED_ENDPOINT_ID_REQUIRED__"):
    import re
    if endpoint!="__VERIFIED_ENDPOINT_ID_REQUIRED__" and not re.fullmatch(r"vpce-[a-f0-9]{8,17}",endpoint):raise ValueError("Invalid verified endpoint ID")
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    documents={"network-template.json":network_template(),
               "bootstrap-policy.json":bootstrap_policy(),"execution-trust.json":trust(),
               "boundary-review.json":boundary(endpoint)}
    documents.update({f"operator-{name.lower()}-policy.json":policy for name,policy in deployment_policies().items()})
    for phase in PHASES:
        documents[f"{phase}-template.json"]=runner_template(phase)
        documents[f"{phase}-runtime-policy-review.json"]=runtime_policy(phase,endpoint)
    for name,doc in documents.items():(out/name).write_text(json.dumps(doc,indent=2)+"\n",encoding="utf-8")
    return documents

# Separate grants; never bundled into deployment policy or attached automatically.
def operator_trust():
    return {"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"AWS":f"arn:aws:iam::{ACCOUNT}:root"},"Action":"sts:AssumeRole","Condition":{"ArnEquals":{"aws:PrincipalArn":f"arn:aws:iam::{ACCOUNT}:user/fintrust_deployer"},"Bool":{"aws:MultiFactorAuthPresent":"true"}}}]}

def invoke_policy(version):
    import re
    if not re.fullmatch(r"[1-9][0-9]*",str(version)):raise ValueError("Verified numeric Lambda version required")
    return {"Version":"2012-10-17","Statement":[allow("InvokeQualifiedRunner",["lambda:InvokeFunction"],FUNCTION+":"+str(version),regional())]}

def snapshot_policy(snapshot_name):
    import re
    if not re.fullmatch(r"fintrust-release1-before002-[0-9]{8}t[0-9]{6}z",snapshot_name):raise ValueError("Exact reviewed snapshot name required")
    db=f"arn:aws:rds:{REGION}:{ACCOUNT}:db:fintrust-ledger-dev"
    snap=f"arn:aws:rds:{REGION}:{ACCOUNT}:snapshot:{snapshot_name}"
    return {"Version":"2012-10-17","Statement":[allow("SnapshotExactSource",["rds:CreateDBSnapshot"],db,regional()),allow("CreateExactSnapshot",["rds:CreateDBSnapshot","rds:AddTagsToResource"],snap,{"StringEquals":{"aws:RequestedRegion":REGION,"aws:RequestTag/Project":"FinTrust","aws:RequestTag/Environment":"dev"}}),allow("InspectSnapshots",["rds:DescribeDBSnapshots"],"*",regional())]}


def deployment_policies():
    """Same reviewed action set, divided below managed-policy size limits."""
    groups={"CloudFormation":[],"Network":[],"Runner":[]}
    for statement in deployment_policy()["Statement"]:
        service=statement["Action"][0].split(":")[0]
        group="CloudFormation" if service=="cloudformation" else "Network" if service=="ec2" else "Runner"
        groups[group].append(statement)
    return {name:{"Version":"2012-10-17","Statement":statements} for name,statements in groups.items()}

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--output",default="build/migration-runner/review")
    parser.add_argument("--endpoint-id",default="__VERIFIED_ENDPOINT_ID_REQUIRED__")
    args=parser.parse_args();print("Rendered",len(render(args.output,args.endpoint_id)),"LOCAL REVIEW documents; no AWS calls")
