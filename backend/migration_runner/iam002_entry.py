from . import common,workflows,iam

def lambda_handler(event,context):
    return common.run(event,{"migrate002","verify002"},iam.connection,workflows.operate)
