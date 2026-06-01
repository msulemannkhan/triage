"""Structured logging (structlog): JSON logs with correlation IDs and PII redaction.

Correlation IDs (conversation_id, job_id, node, …) are bound to context vars by the
service / worker / graph and merged into every event. A redaction processor scrubs
email / phone / card-like patterns as a safety net (recursively, including nested
dict / list values); raw message bodies are never logged in the first place.

``ms_since`` is the shared stopwatch used across the code base to attach a
``duration_ms`` to a log line, so every I/O hop (LLM call, DB query, lock op) is
timed on the path it actually runs.
"""

import logging
import re
from time import perf_counter

import structlog
from structlog.typing import EventDict

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_CARD = re.compile(r"\b\d{13,16}\b")
_PHONE = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")


def _scrub(value: object) -> object:
    """Recursively redact PII in strings, walking dict/list/tuple containers so a
    nested value (e.g. a structured event payload) can't smuggle PII past us."""
    if isinstance(value, str):
        value = _EMAIL.sub("[redacted-email]", value)
        value = _CARD.sub("[redacted-card]", value)
        return _PHONE.sub("[redacted-phone]", value)
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_scrub(v) for v in value)
    return value


def _redact_pii(_logger, _method, event_dict: EventDict) -> EventDict:
    for key, value in list(event_dict.items()):
        event_dict[key] = _scrub(value)
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_pii,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)


def ms_since(start: float) -> float:
    """Milliseconds elapsed since a ``perf_counter()`` mark, rounded for logging."""
    return round((perf_counter() - start) * 1000, 1)
