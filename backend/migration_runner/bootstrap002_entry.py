from . import common,workflows,admin

def lambda_handler(event,context):
    return common.run(event,{"bootstrap002"},admin.connection,workflows.bootstrap)
