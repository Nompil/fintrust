def generate_monthly_report() -> dict:
    raise NotImplementedError("Monthly report generation is a later capstone milestone")


def lambda_handler(event, context):
    return generate_monthly_report()
