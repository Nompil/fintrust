"""Render the Stage 3 private PostgreSQL instance; no AWS calls or SQL execution."""
import argparse
import json
from pathlib import Path


def build_template():
    tags = [{"Key":"Project", "Value":"FinTrust"}, {"Key":"Environment", "Value":"dev"}]
    return {
        "AWSTemplateFormatVersion":"2010-09-09",
        "Description":"FinTrust Stage 3 private PostgreSQL; approval required before deployment",
        "Parameters":{
            "DatabaseSubnetGroup":{"Type":"String", "AllowedValues":["fintrust-db-dev"]},
            "DatabaseSecurityGroup":{"Type":"AWS::EC2::SecurityGroup::Id", "AllowedValues":["sg-01644a4c9f2c44162"]},
        },
        "Resources":{
            "DatabaseTls":{
                "Type":"AWS::RDS::DBParameterGroup",
                "Properties":{"DBParameterGroupName":"fintrust-postgres16-dev", "Family":"postgres16",
                    "Description":"FinTrust PostgreSQL 16 requires TLS", "Parameters":{"rds.force_ssl":"1"}, "Tags":tags},
                "DeletionPolicy":"Retain", "UpdateReplacePolicy":"Retain"},
            "LedgerDatabase":{
                "Type":"AWS::RDS::DBInstance",
                "Properties":{
                    "DBInstanceIdentifier":"fintrust-ledger-dev", "DBName":"fintrust",
                    "Engine":"postgres", "EngineVersion":"16.15", "DBInstanceClass":"db.t4g.micro",
                    "AllocatedStorage":"20", "StorageType":"gp3", "MultiAZ":False,
                    "PubliclyAccessible":False, "NetworkType":"IPV4",
                    "DBSubnetGroupName":{"Ref":"DatabaseSubnetGroup"},
                    "VPCSecurityGroups":[{"Ref":"DatabaseSecurityGroup"}],
                    "DBParameterGroupName":{"Ref":"DatabaseTls"}, "Port":5432,
                    "StorageEncrypted":True, "EnableIAMDatabaseAuthentication":True,
                    "MasterUsername":"fintrust_admin", "ManageMasterUserPassword":True,
                    "BackupRetentionPeriod":1, "CopyTagsToSnapshot":True, "DeletionProtection":True,
                    "AutoMinorVersionUpgrade":True, "AllowMajorVersionUpgrade":False,
                    "EngineLifecycleSupport":"open-source-rds-extended-support-disabled",
                    "MonitoringInterval":0, "EnablePerformanceInsights":False, "Tags":tags,
                },
                "DeletionPolicy":"Snapshot", "UpdateReplacePolicy":"Snapshot"},
        },
        "Outputs":{
            "DatabaseHost":{"Value":{"Fn::GetAtt":["LedgerDatabase","Endpoint.Address"]}},
            "DatabasePort":{"Value":{"Fn::GetAtt":["LedgerDatabase","Endpoint.Port"]}},
            "DatabaseResourceId":{"Value":{"Fn::GetAtt":["LedgerDatabase","DbiResourceId"]}},
            "MasterSecretArn":{"Value":{"Fn::GetAtt":["LedgerDatabase","MasterUserSecret.SecretArn"]}},
        },
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("build/stage3-database.json"))
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(build_template(),indent=2)+"\n",encoding="utf-8")
    print("Rendered Stage 3 database only; no AWS resources changed.")


if __name__ == "__main__":
    main()
