from . import admin,common,demo_reference


def lambda_handler(event,context):
    return common.run(event,{'create_demo_reference'},admin.connection,demo_reference.create)
