from . import admin, common

def lambda_handler(event, context):
    return common.run(event, {"cleanup"}, admin.connection, admin.cleanup)
