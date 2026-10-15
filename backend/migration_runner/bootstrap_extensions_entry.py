from . import common, extensions, admin


def lambda_handler(event, context):
    return common.run(event, {"bootstrap_extensions"}, admin.connection, extensions.bootstrap)
