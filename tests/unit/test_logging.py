import json
from collections.abc import Iterator

import pytest
import structlog

from app.logging import REDACTED, bind_run_id, configure_logging, redact_secrets


@pytest.fixture(autouse=True)
def reset_structlog() -> Iterator[None]:
    yield
    structlog.contextvars.clear_contextvars()
    structlog.reset_defaults()


def test_secret_like_keys_are_redacted() -> None:
    event = {"event": "call", "api_key": "abc", "Token": "def", "db_password": "ghi"}

    result = redact_secrets(None, "info", event)

    assert result == {
        "event": "call",
        "api_key": REDACTED,
        "Token": REDACTED,
        "db_password": REDACTED,
    }


def test_secrets_in_nested_mappings_are_redacted() -> None:
    event = {"event": "call", "params": {"q": "AMS", "api_key": "abc"}}

    result = redact_secrets(None, "info", event)

    assert result["params"] == {"q": "AMS", "api_key": REDACTED}


def test_non_string_values_are_kept() -> None:
    result = redact_secrets(None, "info", {"event": "ranked", "rank": 1, "total": 7.4})

    assert result == {"event": "ranked", "rank": 1, "total": 7.4}


def test_secret_values_in_urls_are_redacted() -> None:
    event = {"event": "call", "url": "https://serpapi.com/search?q=AMS&api_key=abc123&hl=nl"}

    result = redact_secrets(None, "info", event)

    assert result["url"] == f"https://serpapi.com/search?q=AMS&api_key={REDACTED}&hl=nl"


def test_ordinary_fields_are_left_alone() -> None:
    event = {"event": "ranked", "city": "Porto", "keyboard": "qwerty", "monkey": "yes"}

    result = redact_secrets(None, "info", dict(event))

    assert result == {"event": "ranked", "city": "Porto", "keyboard": "qwerty", "monkey": "yes"}


def test_json_output_contains_level_run_id_and_no_secret(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(level="INFO", fmt="json")
    bind_run_id("run-42")

    structlog.get_logger().info("source_called", source="serpapi", api_key="abc123")

    line = json.loads(capsys.readouterr().err.strip())
    assert line["event"] == "source_called"
    assert line["level"] == "info"
    assert line["run_id"] == "run-42"
    assert line["api_key"] == REDACTED
    assert "abc123" not in json.dumps(line)


def test_messages_below_the_level_are_dropped(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="WARNING", fmt="json")

    structlog.get_logger().info("chatty")

    assert capsys.readouterr().err == ""
