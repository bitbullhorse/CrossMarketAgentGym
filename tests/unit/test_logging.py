"""Credential-redaction tests."""

from __future__ import annotations

import io
import logging

from crossmarket_agentgym.audit.logging import (
    SecretRedactionFilter,
    configure_logging,
    redact_secrets,
    redact_value,
)


def test_redact_secrets_handles_assignment_and_key_prefix() -> None:
    """Common credential shapes are removed without deleting field names."""
    message = "api_key=secret-value authorization:BearerValue sk-example123456789"
    redacted = redact_secrets(message)

    assert "secret-value" not in redacted
    assert "BearerValue" not in redacted
    assert "sk-example" not in redacted
    assert redacted.count("[REDACTED]") == 3


def test_filter_redacts_formatted_arguments() -> None:
    """Redaction occurs after logging interpolation and before emission."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(SecretRedactionFilter())
    logger = logging.getLogger("crossmarket_agentgym.test")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    logger.info("token=%s", "sensitive-token")

    assert stream.getvalue().strip() == "token=[REDACTED]"


def test_configure_logging_is_idempotent() -> None:
    """Repeated setup does not duplicate log handlers."""
    logger = configure_logging()
    handler_count = len(logger.handlers)

    assert configure_logging() is logger
    assert len(logger.handlers) == handler_count


def test_recursive_redaction_preserves_environment_names_and_token_counts() -> None:
    value = {
        "api_key": "mapping-secret",
        "api_key_env": "DEEPSEEK_API_KEY",
        "prompt_tokens": 12,
        "nested": ["password=inline-secret"],
    }
    redacted = redact_value(value)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["api_key_env"] == "DEEPSEEK_API_KEY"
    assert redacted["prompt_tokens"] == 12
    assert "inline-secret" not in redacted["nested"][0]
