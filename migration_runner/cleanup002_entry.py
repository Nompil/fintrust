from . import common,workflows,admin

def lambda_handler(event,context):
    return common.run(event,{"cleanup002"},admin.connection,workflows.cleanup)
