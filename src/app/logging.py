"""Structured logging (structlog): JSON or console output, a run id, and secret redaction."""

import logging
import re
import sys
from collections.abc import Collection, Iterable, Mapping
from typing import Literal, cast

import structlog
from structlog.typing import EventDict, WrappedLogger

REDACTED = "***"

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["json", "console"]

# Name segments that always mark a secret (after camelCase is split into snake_case).
_SECRET_SEGMENTS = frozenset(
    {
        "apikey",
        "auth",
        "authorization",
        "bearer",
        "cookie",
        "credential",
        "credentials",
        "dsn",
        "passwd",
        "password",
        "pwd",
        "secret",
        "sig",
        "signature",
        "token",
    }
)
# "key" alone is too broad (request_key, cache_key are useful in logs); only these qualify it.
_KEY_QUALIFIERS = frozenset(
    {"api", "access", "auth", "client", "private", "secret", "subscription"}
)

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NAME_SPLIT = re.compile(r"[_\-\s]+")

_SECRET_PARAM = r"(?:api_?key|key|token|access_token|secret|password|sig|signature|auth)"  # noqa: S105 -- names of secret parameters, not a secret
_TEXT_SCRUBBERS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Authorization: Bearer <token>
    (re.compile(r"(?i)\b(bearer)\s+[^\s\"',;]+"), rf"\1 {REDACTED}"),
    # https://user:password@host
    (re.compile(r"(?<=//)[^/@\s]+@"), f"{REDACTED}@"),
    # "api_key": "value" in JSON or Python repr text
    (
        re.compile(rf"(?i)([\"']{_SECRET_PARAM}[\"']\s*:\s*[\"'])[^\"']*([\"'])"),
        rf"\1{REDACTED}\2",
    ),
    # ?api_key=value in URLs and form bodies; the lookbehind keeps e.g. monkey=banana intact.
    (re.compile(rf"(?i)(?<![A-Za-z0-9])({_SECRET_PARAM})=([^&\s#\"']+)"), rf"\1={REDACTED}"),
)


def is_secret_name(name: str) -> bool:
    segments = _NAME_SPLIT.split(_CAMEL_BOUNDARY.sub("_", name).lower())
    if any(segment in _SECRET_SEGMENTS for segment in segments):
        return True
    return any(
        segment == "key" and (index == 0 or segments[index - 1] in _KEY_QUALIFIERS)
        for index, segment in enumerate(segments)
    )


class SecretRedactor:
    """structlog processor: never let a secret reach a log line.

    Redacts by field name, by well-known secret patterns in text, and by the exact values
    of the configured secrets (which catches formats no pattern anticipates).
    """

    def __init__(self, known_secrets: Iterable[str] = ()) -> None:
        self._known = tuple(sorted((s for s in known_secrets if s), key=len, reverse=True))

    def __call__(self, _logger: WrappedLogger, _method: str, event_dict: EventDict) -> EventDict:
        return {
            key: self._value(value, secret=key != "event" and is_secret_name(str(key)))
            for key, value in event_dict.items()
        }

    def _value(self, value: object, *, secret: bool = False) -> object:
        if secret:
            return REDACTED
        if value is None or isinstance(value, bool | int | float):
            return value
        if isinstance(value, str):
            return self._text(value)
        if isinstance(value, Mapping):
            # Log payloads are arbitrary; isinstance cannot recover the item types.
            mapping = cast("Mapping[object, object]", value)
            return {k: self._value(v, secret=is_secret_name(str(k))) for k, v in mapping.items()}
        if isinstance(value, list | tuple | set | frozenset):
            return self._sequence(cast("Collection[object]", value))
        # Exceptions, URLs, models: render as text so the scrubbers can see what would be logged.
        return self._text(str(value))

    def _sequence(self, items: Collection[object]) -> object:
        # A (name, value) pair as used for query params, e.g. [("api_key", "abc"), ...].
        if isinstance(items, tuple) and len(items) == 2:
            name = items[0]
            if isinstance(name, str):
                return (name, self._value(items[1], secret=is_secret_name(name)))
        cleaned = [self._value(item) for item in items]
        return tuple(cleaned) if isinstance(items, tuple) else cleaned

    def _text(self, text: str) -> str:
        for secret in self._known:
            text = text.replace(secret, REDACTED)
        for pattern, replacement in _TEXT_SCRUBBERS:
            text = pattern.sub(replacement, text)
        return text


redact_secrets = SecretRedactor()


def configure_logging(
    level: LogLevel = "INFO",
    fmt: LogFormat = "json",
    known_secrets: Iterable[str] = (),
) -> None:
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
            # Tracebacks become plain text before redaction, so they are scrubbed too.
            structlog.processors.format_exc_info,
            SecretRedactor(known_secrets),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[level]),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )


def bind_run_id(run_id: str) -> None:
    """Tag every following log line of this run (and its async tasks) with the run id."""
    structlog.contextvars.bind_contextvars(run_id=run_id)
