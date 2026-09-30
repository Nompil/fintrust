"""Synchronous, local-only upload adapter for synthetic-data demonstrations."""
from hashlib import sha256
import json
import uuid

from werkzeug.utils import secure_filename
from . import ingest


def receive_upload(file):
    filename = secure_filename(file.filename or "")
    if not filename.lower().endswith(".csv"):
        raise ValueError("a .csv file is required")
    payload = file.stream.read(ingest.MAX_FILE_BYTES + 1)
    if len(payload) > ingest.MAX_FILE_BYTES:
        raise ValueError("CSV exceeds the 1 MiB file limit")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("CSV must use UTF-8 encoding") from error
    digest = sha256(payload).hexdigest()
    identity = f"local-upload:{digest}"
    key = f"raw/uploads/{digest}.csv"
    bucket = "fintrust-local-practice"
    ingest.s3.put_object(Bucket=bucket, Key=key, Body=payload)
    counts = ingest.process_csv(bucket, key, text, identity)
    quarantine = []
    if counts["rows_quarantined"]:
        quarantine_key = f"quarantine/{uuid.uuid5(uuid.NAMESPACE_URL, identity)}.jsonl"
        body = ingest.s3.get_object(Bucket=bucket, Key=quarantine_key)["Body"].read().decode()
        quarantine = [json.loads(row) for row in body.splitlines()]
    ingest.logger.info(json.dumps({"event": "local_upload_complete", "upload_id": digest, **counts}))
    return {"filename": filename, "upload_id": digest, **counts,
        "quarantine": quarantine[:50], "quarantine_preview_limit": 50,
        "note": "Accepted rows include replayed rows; identical file bytes are deduplicated in this upload path."}
