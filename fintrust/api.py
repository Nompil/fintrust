import json
import logging
from datetime import date
from uuid import UUID

import awsgi
import psycopg2
from botocore.exceptions import ClientError
from flask import Flask, jsonify, request

from .db import get_connection
from .query import get_insights, get_transactions, parse_datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
app = Flask("fintrust-api")


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
        rows = get_transactions(account_id, from_dt, to_dt, limit)
        for row in rows:
            if row.get("tx_date") is not None:
                row["tx_date"] = row["tx_date"].isoformat()
        return jsonify({
            "status": "ok",
            "data": rows,
            "meta": {"count": len(rows), "limit": limit},
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
