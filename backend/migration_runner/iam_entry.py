from . import iam, common

def lambda_handler(event, context):
    return common.run(event, {"preflight", "migrate", "verify", "cleanup-check"}, iam.connection, iam.operate)
