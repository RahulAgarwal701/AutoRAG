import json
import logging
import re
from datetime import UTC, datetime

_RESERVED_LOG_RECORD_KEYS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "taskName",
    "thread",
    "threadName",
}

_SENSITIVE_KEY = re.compile(
    r"(?:authorization|cookie|password|passwd|secret|token|api[_-]?key|access[_-]?key|"
    r"refresh[_-]?key|email|prompt|question|query|document[_-]?text)",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_AGENT_KEY = re.compile(r"\bark_live_[A-Za-z0-9_-]+\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_URL_CREDENTIALS = re.compile(r"(\w+://[^:/\s]+:)[^@/\s]+(@)")
_LABELED_SECRET = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization)"
    r"\s*[:=]\s*[\"']?[^\s,\"']+"
)


def redact_text(value: str) -> str:
    value = _EMAIL.sub("[REDACTED_EMAIL]", value)
    value = _BEARER.sub("Bearer [REDACTED]", value)
    value = _AGENT_KEY.sub("ark_live_[REDACTED]", value)
    value = _JWT.sub("[REDACTED_JWT]", value)
    value = _URL_CREDENTIALS.sub(r"\1[REDACTED]\2", value)
    return _LABELED_SECRET.sub(r"\1=[REDACTED]", value)


def redact_value(value: object, *, key: str | None = None) -> object:
    if key is not None and _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(item_key): redact_value(item, key=str(item_key)) for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
        }
        payload.update(
            {
                key: redact_value(value, key=key)
                for key, value in record.__dict__.items()
                if key not in _RESERVED_LOG_RECORD_KEYS and not key.startswith("_")
            }
        )
        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level.upper(), handlers=[handler], force=True)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
