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
# A "key" segment is a secret (serpapi_key, x_api_key, key) unless it follows one of these
# names of ordinary identifiers, which are useful in logs.
_BENIGN_KEY_PREFIXES = frozenset(
    {
        "cache",
        "composite",
        "foreign",
        "group",
        "hash",
        "idempotency",
        "index",
        "lookup",
        "map",
        "natural",
        "partition",
        "primary",
        "public",
        "request",
        "routing",
        "row",
        "shard",
        "sort",
        "unique",
    }
)

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NAME_SPLIT = re.compile(r"[_\-\s]+")
# Deeper nesting than this is not expected in a log call; it also stops reference cycles.
_MAX_DEPTH = 12

# Fixed patterns, applied before the name-based assignment scrubber.
_FIXED_SCRUBBERS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Authorization/Cookie headers as text: the whole value up to the end of the line.
    (
        re.compile(r"(?im)\b((?:proxy-)?authorization|set-cookie|cookie)(\s*[:=]\s*)[^\r\n]+"),
        rf"\1\2{REDACTED}",
    ),
    # Credentials after an auth scheme, e.g. "Bearer abc.def".
    (re.compile(r"(?i)\b(bearer|basic|digest)\s+[A-Za-z0-9+/=._~-]{6,}"), rf"\1 {REDACTED}"),
    # https://user:password@host
    (re.compile(r"(?<=//)[^/@\s]+@"), f"{REDACTED}@"),
)
# name=value, name: value, "name": "value", name='value': the value is replaced when the
# name is a secret name by the same rules as field names. "(?!//)" skips URL schemes such
# as "https://", so the query string inside the URL is still scanned.
_ASSIGNMENT = re.compile(
    r"(?<![\w-])(?P<q>[\"']?)(?P<name>[A-Za-z][\w-]*)(?P=q)(?P<sep>\s*[:=]\s*)(?!//)"
    r"(?P<vq>[\"']?)(?P<value>[^&\s#\"',;})\]]+)(?P=vq)"
)


def is_secret_name(name: str) -> bool:
    segments = _NAME_SPLIT.split(_CAMEL_BOUNDARY.sub("_", name).lower())
    if any(segment in _SECRET_SEGMENTS for segment in segments):
        return True
    return any(
        segment == "key" and (index == 0 or segments[index - 1] not in _BENIGN_KEY_PREFIXES)
        for index, segment in enumerate(segments)
    )


def _scrub_assignment(match: re.Match[str]) -> str:
    if not is_secret_name(match["name"]) or match["value"] == REDACTED:
        return match[0]
    return (
        f"{match['q']}{match['name']}{match['q']}{match['sep']}{match['vq']}{REDACTED}{match['vq']}"
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
            key: self._value(value, 0, secret=key != "event" and is_secret_name(str(key)))
            for key, value in event_dict.items()
        }

    def _value(self, value: object, depth: int, *, secret: bool = False) -> object:
        if secret:
            return REDACTED
        if value is None or isinstance(value, bool | int | float):
            return value
        if isinstance(value, str):
            return self._text(value)
        if depth >= _MAX_DEPTH:
            return "<nested too deep>"
        if isinstance(value, Mapping):
            # Log payloads are arbitrary; isinstance cannot recover the item types.
            mapping = cast("Mapping[object, object]", value)
            return {
                self._key(k): self._value(v, depth + 1, secret=is_secret_name(str(k)))
                for k, v in mapping.items()
            }
        if isinstance(value, list | tuple | set | frozenset):
            return self._sequence(cast("Collection[object]", value), depth + 1)
        # Exceptions, URLs, models: render as text so the scrubbers can see what would be logged.
        return self._text(str(value))

    def _key(self, key: object) -> object:
        # Numbers stay numbers; anything else becomes (scrubbed) text so JSON rendering works.
        if key is None or isinstance(key, bool | int | float):
            return key
        return self._text(str(key))

    def _sequence(self, items: Collection[object], depth: int) -> object:
        # A (name, value) pair as used for query params, e.g. [("api_key", "abc"), ...].
        if isinstance(items, tuple) and len(items) == 2:
            name = items[0]
            if isinstance(name, str):
                value = self._value(items[1], depth, secret=is_secret_name(name))
                return (self._text(name), value)
        cleaned = [self._value(item, depth) for item in items]
        return tuple(cleaned) if isinstance(items, tuple) else cleaned

    def _text(self, text: str) -> str:
        for secret in self._known:
            text = text.replace(secret, REDACTED)
        for pattern, replacement in _FIXED_SCRUBBERS:
            text = pattern.sub(replacement, text)
        return _ASSIGNMENT.sub(_scrub_assignment, text)


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
