"""Load trip files (YAML) into a validated TripConfig, with command-line overrides."""

from pathlib import Path

import yaml
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from app.domain import TripConfig


class TripFileError(Exception):
    """A trip file or override that cannot be turned into a valid TripConfig."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or [message]


def load_trip(path: Path, overrides: list[str] | None = None) -> TripConfig:
    data = apply_overrides(_read_mapping(path), overrides or [])
    try:
        return TripConfig.model_validate(data)
    except ValidationError as exc:
        errors = [_format_error(e) for e in exc.errors()]
        msg = f"{path} is not a valid trip"
        raise TripFileError(msg, errors) from exc


def apply_overrides(data: dict[str, object], overrides: list[str]) -> dict[str, object]:
    """Apply `dotted.key=value` overrides; values are parsed as YAML so numbers stay numbers."""
    result = dict(data)
    for override in overrides:
        key, sep, raw_value = override.partition("=")
        if not sep or not key:
            msg = f"override {override!r} must look like key=value"
            raise TripFileError(msg)
        _set_path(result, key.split("."), yaml.safe_load(raw_value))
    return result


def _set_path(data: dict[str, object], parts: list[str], value: object) -> None:
    head, *rest = parts
    if not rest:
        data[head] = value
        return
    child = data.get(head, {})
    if not isinstance(child, dict):
        msg = f"{head} is not a section, so {'.'.join(parts)} cannot be set"
        raise TripFileError(msg)
    child_copy: dict[str, object] = dict(child)  # pyright: ignore[reportUnknownArgumentType] -- YAML mapping
    _set_path(child_copy, rest, value)
    data[head] = child_copy


def _read_mapping(path: Path) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        msg = f"trip file {path} not found"
        raise TripFileError(msg) from exc
    try:
        loaded: object = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        msg = f"trip file {path} is not valid YAML: {exc}"
        raise TripFileError(msg) from exc
    if not isinstance(loaded, dict):
        msg = f"trip file {path} must contain a mapping of settings"
        raise TripFileError(msg)
    return dict(loaded)  # pyright: ignore[reportUnknownArgumentType] -- YAML mapping, validated later


def _format_error(error: ErrorDetails) -> str:
    location = ".".join(str(part) for part in error["loc"]) or "trip"
    message = str(error["msg"]).removeprefix("Value error, ")
    return f"{location}: {message}"
