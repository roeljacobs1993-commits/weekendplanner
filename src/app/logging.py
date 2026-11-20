"""Structured logging (structlog): JSON or console output, a run id, and secret redaction."""

import logging
import re
import sys
from collections.abc import Mapping, MutableMapping
from typing import Literal

import structlog
from structlog.typing import EventDict, WrappedLogger

REDACTED = "***"

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["json", "console"]

# "key" only as a whole name segment (api_key, apikey, key), so "keyboard" or "monkey" stay.
_SECRET_KEY = re.compile(
    r"(?:^|[_\-])(?:api_?)?key(?:$|[_\-])|token|secret|passw(?:or)?d", re.IGNORECASE
)
# SerpApi and others put the key in the query string, so URLs are scrubbed too.
_SECRET_IN_QUERY = re.compile(r"((?:api_)?key|token|secret|password)=([^&\s#]+)", re.IGNORECASE)


def redact_secrets(_logger: WrappedLogger, _method: str, event_dict: EventDict) -> EventDict:
    """structlog processor: never let a secret reach a log line."""
    redacted = _redact_mapping(event_dict)
    event_dict.clear()
    event_dict.update(redacted)
    return event_dict


def configure_logging(level: LogLevel = "INFO", fmt: LogFormat = "json") -> None:
    renderer = (
        structlog.processors.JSONRenderer()
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_secrets,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[level]),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )


def bind_run_id(run_id: str) -> None:
    """Tag every following log line of this run (and its async tasks) with the run id."""
    structlog.contextvars.bind_contextvars(run_id=run_id)


def _redact_mapping(data: Mapping[str, object]) -> MutableMapping[str, object]:
    return {key: _redact_value(key, value) for key, value in data.items()}


def _redact_value(key: str, value: object) -> object:
    if key != "event" and _SECRET_KEY.search(key):
        return REDACTED
    if isinstance(value, Mapping):
        return _redact_mapping(value)  # pyright: ignore[reportUnknownArgumentType] -- log payload
    if isinstance(value, str):
        return _SECRET_IN_QUERY.sub(rf"\1={REDACTED}", value)
    return value
