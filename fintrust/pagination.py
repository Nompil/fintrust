"""Opaque, filter-bound cursors for descending transaction pages."""
import base64
import binascii
import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID


def fingerprint(account_id, from_dt, to_dt, limit):
    values = [account_id, *[d.astimezone(timezone.utc).isoformat() if d else None
                           for d in (from_dt, to_dt)], limit]
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


def encode_cursor(row, scope, page):
    payload = [1, scope, row['tx_date'].isoformat(), row['tx_id'], page]
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')


def decode_cursor(token, scope):
    try:
        if not token or len(token) > 1024:
            raise ValueError()
        value = json.loads(base64.b64decode(token + '=' * (-len(token) % 4), altchars=b'-_', validate=True))
        version, bound_scope, timestamp, identifier, page = value
        if version != 1 or bound_scope != scope or type(page) is not int or not 2 <= page <= 1000000:
            raise ValueError()
        when = datetime.fromisoformat(timestamp)
        if when.tzinfo is None:
            raise ValueError()
        return when, str(UUID(identifier)), page
    except (ValueError, TypeError, binascii.Error, UnicodeError) as error:
        raise ValueError('cursor is invalid or does not match these filters') from error
