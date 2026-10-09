"""Offline contract tests for temporary resource/IAM/phase isolation."""
import json
import re
from pathlib import Path
import pytest
from infrastructure import migration as m

def test_one_az_both_endpoint_and_runner():
    n=m.network_template();r=m.runner_template("preflight")
    assert n["Resources"]["SecretsEndpoint"]["Properties"]["SubnetIds"]==[m.SUBNET]
    assert r["Resources"]["Runner"]["Properties"]["VpcConfig"]["SubnetIds"]==[m.SUBNET]
    assert len(n["Resources"])==4 and len(r["Resources"])==3
    assert all(v["Type"] not in {"AWS::EC2::NatGateway","AWS::RDS::DBInstance"} for v in n["Resources"].values())

def test_endpoint_https_and_no_db_sg_edit():
    resources=m.network_template()["Resources"]
    assert resources["SecretsEndpoint"]["Properties"]["PrivateDnsEnabled"] is True
    client=resources["ClientSecurityGroup"]["Properties"]
    assert "SecurityGroupIngress" not in client
    rule=client["SecurityGroupEgress"][0]
    assert rule["FromPort"]==rule["ToPort"]==443 and "DestinationSecurityGroupId" in rule
    assert resources["EndpointSecurityGroup"]["Properties"]["SecurityGroupEgress"]==[{"IpProtocol":"-1","CidrIp":"127.0.0.1/32","Description":"Suppress EC2 default outbound rule"}]
    assert "sg-01644a4c9f2c44162" not in json.dumps(resources)

@pytest.mark.parametrize("phase",m.PHASES)
def test_disabled_phase_and_version_binding(phase):
    t=m.runner_template(phase);p=t["Resources"]["Runner"]["Properties"]
    assert p["ReservedConcurrentExecutions"]==0 and p["Runtime"]=="python3.12"
    assert "Environment" not in p and p["Role"]==m.ROLE
    assert p["Handler"]==f"migration_runner.{phase}_entry.lambda_handler"
    assert p["Code"]["S3ObjectVersion"]=={"Ref":"CodeObjectVersion"}
    assert t["Resources"]["RunnerVersion"]["Properties"]["CodeSha256"]=={"Ref":"CodeSha256"}
    assert re.fullmatch(t["Parameters"]["CodeKey"]["AllowedPattern"],f"deployment/migration/{'a'*64}/fintrust-migration-{phase}.zip")
    assert not any(v["Type"] in {"AWS::Lambda::EventSourceMapping","AWS::Lambda::Permission","AWS::Lambda::EventInvokeConfig"} for v in t["Resources"].values())

def test_iam_phase_cannot_read_master():
    p=m.runtime_policy("iam","vpce-abc")["Statement"]
    assert any(s["Effect"]=="Deny" and s["Resource"]==m.config.SECRET for s in p)
    assert not any(s["Effect"]=="Allow" and "secretsmanager:GetSecretValue" in s["Action"] for s in p)
    assert any(s["Resource"]==m.DBUSER for s in p)

def test_master_policy_exact_endpoint_and_current_version():
    p=m.runtime_policy("preflight","vpce-abc")["Statement"]
    s=next(s for s in p if s["Sid"]=="MasterViaEndpoint")
    assert s["Resource"]==m.config.SECRET
    assert s["Condition"]["StringEquals"]=={"aws:RequestedRegion":"af-south-1","aws:SourceVpce":"vpce-abc","secretsmanager:VersionStage":"AWSCURRENT"}
    assert not any(any(a.startswith("kms:") for a in s["Action"]) for s in p)

def test_function_code_cannot_use_eni_permissions():
    p=m.boundary("vpce-abc")["Statement"]
    s=next(s for s in p if s["Sid"]=="NoCodeEni")
    assert s["Effect"]=="Deny" and s["Action"]==m.ENI
    assert s["Condition"]["ArnEquals"]["lambda:SourceFunctionArn"]==m.FUNCTION

def test_deployer_cannot_change_boundary_or_create_roles():
    p=m.deployment_policy()["Statement"]
    actions={a for s in p for a in s["Action"]}
    assert not {"iam:CreateRole","iam:PutRolePolicy","iam:CreatePolicyVersion","iam:PutRolePermissionsBoundary","iam:DeleteRolePermissionsBoundary"}&actions
    assert "lambda:InvokeFunction" not in actions
    assert not {"s3:PutObject","rds:ModifyDBInstance","ec2:AuthorizeSecurityGroupIngress"}&{a for s in p if s["Resource"]=="*" for a in s["Action"]}
    assert "AWS::IAM::Role" not in json.dumps(p)

def test_artifact_version_pinned():
    p=m.artifact_policy("a"*64,"version-1","preflight")["Statement"][0]
    assert p["Condition"]["StringEquals"]["s3:VersionId"]=="version-1"
    with pytest.raises(ValueError):m.artifact_policy("a"*64,"null","preflight")

def test_bootstrap_sql_does_not_grant_admin_to_migration():
    s=Path("sql/bootstrap/temporary_identity.sql").read_text()
    assert "TO fintrust_migrate_dev WITH SET TRUE, INHERIT FALSE, ADMIN FALSE" in s
    assert "GRANT rds_superuser" not in s
    assert "REVOKE CREATE ON SCHEMA public" in s
    assert "OWNER TO fintrust_transactions_owner" in s
    cleanup=Path("sql/bootstrap/remove_temporary_identity.sql").read_text()
    assert "DROP OWNED CASCADE" not in cleanup and "DROP ROLE fintrust_transactions_owner" not in cleanup


def test_endpoint_binding_rejects_invalid_id(tmp_path):
    with pytest.raises(ValueError):m.render(tmp_path,"*")
    docs=m.render(tmp_path,"vpce-0123456789abcdef0")
    assert "__VERIFIED_ENDPOINT_ID_REQUIRED__" not in json.dumps(docs)
