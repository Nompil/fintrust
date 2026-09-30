import json
import logging
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
from .query import get_insights, get_transactions, parse_datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
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
    if request.method == "OPTIONS":
        method = request.headers.get("Access-Control-Request-Method", "GET")
        headers = {h.strip().lower() for h in request.headers.get("Access-Control-Request-Headers", "").split(",") if h.strip()}
        if method not in {"GET", "POST"} or not headers <= {"content-type"}:
            return jsonify({"error": "preflight method or headers are not allowed"}), 403
        return "", 204


@app.after_request
def finish_request(response):
    response.headers["X-Request-ID"] = getattr(g, "request_id", "")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    origin = request.headers.get("Origin")
    allowed = {o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()}
    if origin and (origin in allowed or origin == request.host_url.rstrip("/")):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
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
    return jsonify({"status": "ok", "data": get_accounts()})


@app.get("/v1/overview")
def overview():
    from .query import get_overview
    return jsonify({"status": "ok", "data": get_overview(), "mode": "local practice" if os.getenv("FINTRUST_LOCAL_DEMO") == "1" else "application"})


@app.post("/v1/upload")
def upload():
    if os.getenv("FINTRUST_LOCAL_DEMO") != "1":
        return jsonify({"error": "local upload is disabled"}), 404
    from .local_upload import receive_upload
    file = request.files.get("file")
    if file is None:
        return jsonify({"error": "multipart field 'file' is required"}), 400
    try:
        return jsonify({"status": "ok", "data": receive_upload(file)}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


def _account_id_arg() -> str:
    value = request.args.get("account_id", "").strip()
    if not value:
        raise ValueError("account_id is required")
    try:
        return str(UUID(value))
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
        rows = get_transactions(account_id, from_dt, to_dt, limit, offset)
        for row in rows:
            if row.get("tx_date") is not None:
                row["tx_date"] = row["tx_date"].isoformat()
        return jsonify({
            "status": "ok",
            "data": rows,
            "meta": {"count": len(rows), "limit": limit, "offset": offset},
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
        account_id = _account_id_arg()
        date_value = request.args.get("date")
        try:
            score_date = date.fromisoformat(date_value) if date_value else date.today()
        except ValueError as error:
            raise ValueError("date must use YYYY-MM-DD format") from error
        item = get_insights(account_id, score_date)
        if item is None:
            return jsonify({"error": "No score found for this account and date"}), 404
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


def lambda_handler(event, context):
    return awsgi.response(app, event, context)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
