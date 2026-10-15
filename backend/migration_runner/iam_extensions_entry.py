from . import common, extensions, iam


def lambda_handler(event, context):
    return common.run(event, {*extensions.OPERATIONS, "verify_extensions"}, iam.connection, extensions.operate)
