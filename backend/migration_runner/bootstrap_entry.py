from . import admin, common

def lambda_handler(event, context):
    return common.run(event, {"bootstrap"}, admin.connection, admin.bootstrap)
