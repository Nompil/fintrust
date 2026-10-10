import json
import os
from pathlib import Path
from time import perf_counter
from uuid import uuid4
from datetime import date
from uuid import UUID

import awsgi
import psycopg2
from botocore.exceptions import ClientError, BotoCoreError
from flask import Flask, jsonify, request, g, send_from_directory
from werkzeug.exceptions import HTTPException

from .db import get_connection
from .query import get_insights, get_transactions, get_transaction_page, parse_datetime

from src.shared.logger import get_logger

logger = get_logger("api")
app = Flask("fintrust-api")
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 + 65536
FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


@app.before_request
def request_context():
    g.started = perf_counter()
    g.request_id = str(uuid4())
    origin = request.headers.get("Origin")
    allowed = {o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()}
    allowed.add(request.host_url.rstrip("/"))
    if origin and origin not in allowed:
        return jsonify({"error": "origin is not allowed"}), 403
    if request.path.startswith("/v1/") and request.method!="OPTIONS" and request.path!="/v1/health":
        from .auth import authenticate
        try:
            g.principal=authenticate()
            if g.principal.role=="Maintainer" and request.path not in {"/v1/session","/v1/operations","/v1/operations/retry"} and not request.path.startswith("/v1/workflows/batches"):
                return jsonify({"error":"Maintainer scope is technical operations"}),403
        except PermissionError: return jsonify({"error":"authentication required"}),401
    if request.method == "OPTIONS":
        method = request.headers.get("Access-Control-Request-Method", "GET")
        headers = {h.strip().lower() for h in request.headers.get("Access-Control-Request-Headers", "").split(",") if h.strip()}
        if method not in {"GET", "POST"} or not headers <= {"content-type","authorization"}:
            return jsonify({"error": "preflight method or headers are not allowed"}), 403
        return "", 204


@app.after_request
def finish_request(response):
    if response.is_json:
        payload = response.get_json()
        if isinstance(payload, dict):
            payload.setdefault("status", "error" if response.status_code >= 400 else "ok")
            payload.setdefault("data", {"db": payload["db"]} if "db" in payload else None)
            count = len(payload["data"]) if isinstance(payload["data"], list) else int(payload["data"] is not None)
            payload.setdefault("meta", {"count": count, "page": 1, "total": count})
            if response.status_code >= 400:
                payload.setdefault("request_id", getattr(g, "request_id", ""))
            response.set_data(app.json.dumps(payload))
    response.headers["X-Request-ID"] = getattr(g, "request_id", "")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    origin = request.headers.get("Origin")
    allowed = {o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()}
    if origin and (origin in allowed or origin == request.host_url.rstrip("/")):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.vary.add("Origin")
    logger.info(json.dumps({"event": "api_request", "request_id": getattr(g, "request_id", ""),
        "method": request.method, "path": request.path, "status": response.status_code,
        "duration_ms": round((perf_counter() - getattr(g, "started", perf_counter())) * 1000, 2)}))
    return response


@app.errorhandler(HTTPException)
def http_error(error):
    return jsonify({"error": error.name, "request_id": getattr(g, "request_id", "")}), error.code


@app.errorhandler(Exception)
def unexpected_error(error):
    if isinstance(error,psycopg2.IntegrityError):
        return jsonify({"error":"state or constraint conflict"}),409
    unavailable = isinstance(error, (psycopg2.Error, BotoCoreError, ClientError))
    logger.error(json.dumps({"event": "api_error", "request_id": getattr(g, "request_id", ""), "error_type": type(error).__name__}))
    return jsonify({"error": "service temporarily unavailable" if unavailable else "internal server error",
        "request_id": getattr(g, "request_id", "")}), 503 if unavailable else 500


@app.get("/")
def dashboard():
    return send_from_directory(FRONTEND, "index.html")


@app.get("/assets/<path:name>")
def frontend_asset(name):
    return send_from_directory(FRONTEND, name)


@app.get("/v1/accounts")
def accounts():
    from .query import get_accounts
    return jsonify({"status": "ok", "data": [r for r in get_accounts() if r["account_id"] in g.principal.accounts]})


@app.get("/v1/overview")
def overview():
    from .query import get_overview
    return jsonify({"status": "ok", "data": get_overview(g.principal.accounts), "mode": "local practice" if os.getenv("FINTRUST_LOCAL_DEMO") == "1" else "application"})


@app.post("/v1/upload")
def upload():
    if os.getenv("FINTRUST_LOCAL_DEMO") != "1" and os.getenv("FINTRUST_RELEASE1_UPLOAD") != "1":
        return jsonify({"error": "local upload is disabled"}), 404
    if g.principal.role!="Admin": raise PermissionError("Local teaching uploads require Admin")
    from .file_admission import AdmissionError,admit
    from .local_upload import receive_upload
    file = request.files.get("file")
    if file is None or len(request.files.getlist("file"))!=1 or len(list(request.files.items(multi=True)))!=1:
        return jsonify({"error":"Exactly one file is required","reason_code":"INVALID_FILE_COUNT"}),400
    try:
        if os.getenv("FINTRUST_RELEASE1_UPLOAD")=="1":
            name,payload=admit(file)
            from .operations import upload_csv
            return jsonify({"status":"ok","data":upload_csv(name,payload,g.principal)}),200
        return jsonify({"status": "ok", "data": receive_upload(file)}), 200
    except AdmissionError as error:
        return jsonify({"error":"Upload rejected: this file does not match the FinTrust transaction CSV format.","reason_code":error.code}),400
    except ValueError as error:
        return jsonify({"error": "Invalid CSV request"}), 400


def _account_id_arg() -> str:
    value = request.args.get("account_id", "").strip()
    if not value:
        raise ValueError("account_id is required")
    try:
        return g.principal.account(str(UUID(value)))
    except ValueError as error:
        raise ValueError("account_id must be a UUID") from error


@app.get("/v1/health")
def health():
    connection = None
    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return jsonify({"status": "ok", "db": "ok"}), 200
    except Exception as error:
        if connection is not None:
            connection.rollback()
        logger.exception(json.dumps({
            "event": "api_health_check_failed",
            "error_type": type(error).__name__,
        }))
        return jsonify({"status": "degraded", "db": "error"}), 503
    finally:
        if connection is not None:
            connection.close()


@app.get("/v1/transactions")
def transactions():
    try:
        allowed={"account_id","from","to","limit","offset","cursor"} if request.path=="/v1/transactions" else {"account_id","date","transaction_id"}
        if set(request.args)-allowed or any(len(request.args.getlist(k))!=1 for k in request.args): raise ValueError("Unsupported or duplicate filter")
        account_id = _account_id_arg()
        from_value = request.args.get("from")
        to_value = request.args.get("to")
        from_dt = parse_datetime(from_value) if from_value else None
        to_dt = parse_datetime(to_value) if to_value else None
        if from_dt and to_dt and from_dt > to_dt:
            raise ValueError("from must be earlier than or equal to to")
        try:
            limit = int(request.args.get("limit", "50"))
        except ValueError as error:
            raise ValueError("limit must be an integer") from error
        limit = max(1, min(limit, 500))
        try:
            offset = int(request.args.get("offset", "0"))
        except ValueError as error:
            raise ValueError("offset must be a non-negative integer") from error
        if offset < 0:
            raise ValueError("offset must be a non-negative integer")
        if 'offset' in request.args:
            if 'cursor' in request.args:
                raise ValueError('cursor and offset cannot be combined')
            rows = get_transactions(account_id, from_dt, to_dt, limit, offset)
            meta = {'count': len(rows), 'limit': limit, 'offset': offset}
        else:
            rows, meta = get_transaction_page(account_id, from_dt, to_dt, limit, request.args.get('cursor'))
        for row in rows:
            if row.get("tx_date") is not None:
                row["tx_date"] = row["tx_date"].isoformat()
        return jsonify({
            "status": "ok",
            "data": rows,
            "meta": meta,
        }), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except psycopg2.Error as error:
        logger.exception(json.dumps({
            "event": "transactions_query_failed",
            "error_type": type(error).__name__,
        }))
        return jsonify({"error": "transaction service temporarily unavailable"}), 503


@app.get("/v1/insights")
def insights():
    try:
        allowed={"account_id","from","to","limit","offset","cursor"} if request.path=="/v1/transactions" else {"account_id","date","transaction_id"}
        if set(request.args)-allowed or any(len(request.args.getlist(k))!=1 for k in request.args): raise ValueError("Unsupported or duplicate filter")
        account_id = _account_id_arg()
        date_value = request.args.get("date")
        try:
            score_date = date.fromisoformat(date_value) if date_value else date.today()
        except ValueError as error:
            raise ValueError("date must use YYYY-MM-DD format") from error
        transaction_id = request.args.get("transaction_id")
        if transaction_id is not None:
            if date_value:
                raise ValueError("transaction_id and date cannot be combined")
            try:
                transaction_id = str(UUID(transaction_id))
            except ValueError as error:
                raise ValueError("transaction_id must be a UUID") from error
            item = get_insights(account_id, transaction_id=transaction_id)
        else:
            item = get_insights(account_id, score_date)
        if item is None:
            return jsonify({"error": "No score found for this account and transaction" if transaction_id is not None
                            else "No score found for this account and date"}), 404
        payload = json.loads(json.dumps({"status": "ok", "data": item}, default=str))
        return jsonify(payload), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except ClientError as error:
        logger.exception(json.dumps({
            "event": "insights_query_failed",
            "error_type": type(error).__name__,
        }))
        return jsonify({"error": "insights service temporarily unavailable"}), 503


@app.errorhandler(PermissionError)
def denied(error):
    return jsonify({"error":"action or object is not authorized"}),403


@app.errorhandler(ValueError)
def bad_input(error):
    return jsonify({"error":"invalid request"}),400


@app.get("/release1")
def release1_dashboard():
    return send_from_directory(FRONTEND,"release1.html")


@app.get("/v1/reports")
def workflow_report():
    from .workflow_api import report
    return jsonify(report(g.principal,request.args))


@app.get("/v1/metrics")
def workflow_metrics():
    from .workflow_api import metrics
    return jsonify({"data":metrics(g.principal)})


@app.get("/v1/session")
def session():
    return jsonify({"data":{"subject":g.principal.subject,"role":g.principal.role,"accounts":g.principal.accounts}})


@app.get("/v1/workflows/<kind>")
def workflow_list(kind):
    from .workflow_api import list_page
    return jsonify(list_page(kind,g.principal,request.args))


@app.get("/v1/transactions/<identifier>")
def transaction_detail(identifier):
    from .workflow_api import detail
    return jsonify({"data":detail(identifier,g.principal)})


@app.post("/v1/reviews/<int:event>/transition")
def transition(event):
    from .workflow_api import update_review
    return jsonify({"data":update_review(event,request.get_json(),g.principal)})


@app.get("/v1/quarantine/<identifier>")
def quarantine_detail(identifier):
    from .workflow_api import quarantine_detail as read
    return jsonify({"data":read(identifier,g.principal)})


@app.post("/v1/quarantine/<identifier>/corrections")
def correction(identifier):
    from .workflow_api import correct_case
    return jsonify({"data":correct_case(identifier,request.get_json(),g.principal)}),202


from .workflow_api import Conflict,NotFound
@app.errorhandler(Conflict)
def conflicting_request(error):
    return jsonify({"error":"state or request identity conflict; refresh before retry"}),409


@app.errorhandler(NotFound)
def absent_object(error):
    return jsonify({"error":"resource not found"}),404


def lambda_handler(event, context):
    return awsgi.response(app, event, context)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)

@app.get("/v1/operations")
def operations_read():
    from .operations import snapshot
    return jsonify({"data":snapshot(g.principal)})

@app.post("/v1/operations/retry")
def operations_retry():
    from .operations import retry
    return jsonify({"data":retry(request.get_json(),g.principal)})

@app.get("/v1/administration")
def administration():
    if g.principal.role!="Admin":raise PermissionError("Admin required")
    from .release_contract import VERSION
    return jsonify({"data":{"contract_version":VERSION,"identity":"operator-controlled hashed-token registry","user_management":"Not exposed through HTTP; approved operator administration only","live_deployment":"Separate approval required"}})
