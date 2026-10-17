from . import admin, common, runtime


def lambda_handler(event, context):
    return common.run(event, {'provision_runtime'}, admin.connection, runtime.provision)
