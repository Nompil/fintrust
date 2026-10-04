"""Single-line service logs without exception messages or transaction payloads."""
import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        try:
            fields = json.loads(record.getMessage())
            if not isinstance(fields, dict):
                fields = {'event': 'service_message'}
        except (ValueError, TypeError):
            fields = {'event': record.getMessage()}
        fields.update(timestamp=datetime.now(timezone.utc).isoformat(),
                      level=record.levelname, service=record.name)
        if record.exc_info:
            fields['error_type'] = record.exc_info[0].__name__
        return json.dumps(fields, default=str, separators=(',', ':'))


def get_logger(service):
    logger = logging.getLogger(service)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
