from . import common, extensions, admin


def lambda_handler(event, context):
    return common.run(event, {"cleanup_extensions"}, admin.connection, extensions.cleanup)
