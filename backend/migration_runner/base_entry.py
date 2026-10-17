from . import admin, base, common


def lambda_handler(event, context):
    return common.run(event, {'initialize_base'}, admin.connection, base.initialize)
