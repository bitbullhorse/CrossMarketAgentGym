"""Structured logging primitives with conservative secret redaction."""

from __future__ import annotations

import logging
import re
from typing import Any, Final

_SECRET_ASSIGNMENT: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(api[_-]?key|authorization|bearer|password|secret|token)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_KEY_PREFIX: Final[re.Pattern[str]] = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")


def redact_secrets(value: str) -> str:
    """Replace credential-like values while retaining useful field names."""
    redacted = _SECRET_ASSIGNMENT.sub(r"\1\2[REDACTED]", value)
    return _KEY_PREFIX.sub("[REDACTED]", redacted)


def redact_value(value: Any, *, field_name: str = "") -> Any:
    """Recursively redact strings and credential-like mapping fields."""
    normalized = field_name.lower().replace("-", "_")
    secret_field = normalized in {
        "api_key",
        "authorization",
        "bearer",
        "password",
        "secret",
        "access_token",
        "refresh_token",
    } or normalized.endswith(("_api_key", "_password", "_secret"))
    if secret_field and not normalized.endswith("_env"):
        return "[REDACTED]"
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return {
            str(key): redact_value(item, field_name=str(key))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_value(item, field_name=field_name) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item, field_name=field_name) for item in value)
    return value


class SecretRedactionFilter(logging.Filter):
    """Redact secrets before a record reaches any configured handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Sanitize the rendered message and retain the record."""
        record.msg = redact_secrets(record.getMessage())
        record.args = ()
        return True


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure the package logger once and return it."""
    logger = logging.getLogger("crossmarket_agentgym")
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
        handler.addFilter(SecretRedactionFilter())
        logger.addHandler(handler)
    return logger
