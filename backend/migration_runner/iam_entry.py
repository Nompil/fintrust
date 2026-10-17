from . import iam, common

def lambda_handler(event, context):
    stage = "connection"

    def connection():
        nonlocal stage
        result = iam.connection()
        stage = "operation"
        return result

    try:
        return common.run(event, {"preflight", "migrate", "verify", "cleanup-check"}, connection, iam.operate)
    except common.RunnerFailure as failure:
        # Only fixed categories and SQLSTATE leave the runner. Never expose a
        # connection string, server error, query, token or exception repr.
        error = failure.__context__
        code = getattr(error, "pgcode", None)
        if not isinstance(code, str) or len(code) != 5 or not code.isascii() or not code.isalnum():
            code = "none"
        category = "database" if isinstance(error, common.psycopg2.Error) else "refused" if isinstance(error, common.Refused) else "internal"
        if stage == "connection" and isinstance(error, common.psycopg2.OperationalError):
            # Used for classification only; the original message is never emitted.
            message = str(error).lower()
            category = ("iam_authentication" if "pam authentication failed" in message else
                        "password_authentication" if "password authentication failed" in message else
                        "connection_timeout" if "timeout" in message else
                        "tls" if "certificate" in message or "ssl" in message else "connection")
        raise common.RunnerFailure(str(failure) + ":" + stage + ":" + category + ":" + code) from None
