import json
from collections.abc import Iterator

import pytest
import structlog

from app.logging import REDACTED, SecretRedactor, bind_run_id, configure_logging, redact_secrets


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


@pytest.mark.parametrize(
    "name",
    [
        "Authorization",
        "Proxy-Authorization",
        "Cookie",
        "credentials",
        "serpApiKey",
        "privateKey",
        "serpapi_key",
        "SERPAPI_KEY",
        "ors_api_key",
    ],
)
def test_auth_headers_and_camel_case_key_names_are_redacted(name: str) -> None:
    result = redact_secrets(None, "info", {"event": "call", name: "s3cr3t-value"})

    assert result[name] == REDACTED


@pytest.mark.parametrize("name", ["request_key", "cache_key", "tokens_used", "keyboard", "monkey"])
def test_ordinary_names_that_resemble_secrets_are_kept(name: str) -> None:
    result = redact_secrets(None, "info", {"event": "call", name: "visible"})

    assert result[name] == "visible"


def test_secrets_in_nested_mappings_are_redacted() -> None:
    event = {"event": "call", "params": {"q": "AMS", "api_key": "abc"}}

    result = redact_secrets(None, "info", event)

    assert result["params"] == {"q": "AMS", "api_key": REDACTED}


def test_secrets_inside_lists_of_pairs_are_redacted() -> None:
    event = {"event": "call", "params": [("api_key", "abc"), ("q", "AMS")]}

    result = redact_secrets(None, "info", event)

    assert result["params"] == [("api_key", REDACTED), ("q", "AMS")]


def test_a_pair_of_urls_is_scrubbed_on_both_sides() -> None:
    out_url = "https://serpapi.com/search?q=AMS&api_key=abc123"
    in_url = "https://serpapi.com/search?q=OPO&api_key=abc123"

    result = redact_secrets(None, "info", {"event": "searched", "urls": (out_url, in_url)})

    assert result["urls"] == (
        f"https://serpapi.com/search?q=AMS&api_key={REDACTED}",
        f"https://serpapi.com/search?q=OPO&api_key={REDACTED}",
    )


def test_text_in_the_name_slot_of_a_pair_is_scrubbed() -> None:
    # A neutral field name, so only the pair handling can redact the first element.
    result = redact_secrets(None, "info", {"event": "call", "pair": ("token=abc123", 1)})

    assert result["pair"] == (f"token={REDACTED}", 1)


def test_secrets_in_mapping_keys_are_scrubbed() -> None:
    url = "https://serpapi.com/search?api_key=abc123"

    result = redact_secrets(None, "info", {"event": "statuses", "by_url": {url: 200}})

    assert result["by_url"] == {f"https://serpapi.com/search?api_key={REDACTED}": 200}


def test_secret_values_in_urls_are_redacted() -> None:
    event = {"event": "call", "url": "https://serpapi.com/search?q=AMS&api_key=abc123&hl=nl"}

    result = redact_secrets(None, "info", event)

    assert result["url"] == f"https://serpapi.com/search?q=AMS&api_key={REDACTED}&hl=nl"


def test_query_parameters_merely_ending_in_key_are_kept() -> None:
    result = redact_secrets(None, "info", {"event": "call", "url": "https://x.org/?monkey=banana"})

    assert result["url"] == "https://x.org/?monkey=banana"


def test_vendor_key_parameters_in_text_are_redacted() -> None:
    result = redact_secrets(None, "info", {"event": "call", "note": "used serpapi_key=abc123"})

    assert result["note"] == f"used serpapi_key={REDACTED}"


def test_ordinary_key_parameters_in_text_are_kept() -> None:
    result = redact_secrets(None, "info", {"event": "call", "note": "cache_key=abc request_key=d"})

    assert result["note"] == "cache_key=abc request_key=d"


def test_authorization_header_text_is_redacted() -> None:
    result = redact_secrets(
        None, "info", {"event": "call", "note": "Authorization: Basic Ym9iOnB3"}
    )

    assert result["note"] == f"Authorization: {REDACTED}"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Client(api_key='abc123', q='AMS')", f"Client(api_key='{REDACTED}', q='AMS')"),
        ('token="abc123"', f'token="{REDACTED}"'),
        ("X-Api-Key: abc123", f"X-Api-Key: {REDACTED}"),
        ('{"client_secret": "abc123"}', f'{{"client_secret": "{REDACTED}"}}'),
        ('{"refresh_token": "abc123"}', f'{{"refresh_token": "{REDACTED}"}}'),
        ("passwd=abc123&x=1", f"passwd={REDACTED}&x=1"),
        # An ordinary assignment in front must not swallow the secret behind it.
        ("error: api_key=abc123", f"error: api_key={REDACTED}"),
        (
            "url=https://serpapi.com/search?api_key=abc123&q=AMS",
            f"url=https://serpapi.com/search?api_key={REDACTED}&q=AMS",
        ),
        (
            "input_value='https://serpapi.com/search?api_key=abc123'",
            f"input_value='https://serpapi.com/search?api_key={REDACTED}'",
        ),
        # Quoted values with spaces or separators.
        ('{"password": "correct horse"}', f'{{"password": "{REDACTED}"}}'),
        ("{'Authorization': 'Token abc123'}", f"{{'Authorization': '{REDACTED}'}}"),
        ('{"Cookie": "a=1; sid=xyz"}', f'{{"Cookie": "{REDACTED}"}}'),
        # Names starting with dashes or an underscore.
        ("--api-key=abc123", f"--api-key={REDACTED}"),
        ("_token=abc123", f"_token={REDACTED}"),
    ],
)
def test_secret_assignments_in_text_are_redacted(text: str, expected: str) -> None:
    result = redact_secrets(None, "info", {"event": "call", "note": text})

    assert result["note"] == expected


def test_self_referencing_structures_do_not_break_logging() -> None:
    loop: list[object] = ["x"]
    loop.append(loop)

    result = redact_secrets(None, "info", {"event": "call", "data": loop})

    assert result["data"][0] == "x"


def test_tuple_keys_become_text_so_json_rendering_works() -> None:
    result = redact_secrets(None, "info", {"event": "call", "by_pair": {("AMS", "OPO"): 1}})

    assert result["by_pair"] == {"('AMS', 'OPO')": 1}


def test_fare_names_that_look_like_auth_schemes_are_kept() -> None:
    result = redact_secrets(
        None, "info", {"event": "fare", "note": "Basic Economy, Digest included"}
    )

    assert result["note"] == "Basic Economy, Digest included"


def test_long_chains_of_assignments_are_handled() -> None:
    text = "a=" * 5000 + "api_key=abc123"

    result = redact_secrets(None, "info", {"event": "call", "note": text})

    assert result["note"].endswith(f"api_key={REDACTED}")


def test_bearer_tokens_in_text_are_redacted() -> None:
    result = redact_secrets(None, "info", {"event": "call", "note": "sent Bearer abc.def.ghi"})

    assert result["note"] == f"sent Bearer {REDACTED}"


def test_credentials_in_url_userinfo_are_redacted() -> None:
    result = redact_secrets(None, "info", {"event": "call", "url": "https://bob:pw@host.org/x"})

    assert result["url"] == f"https://{REDACTED}@host.org/x"


def test_secrets_in_json_or_repr_text_are_redacted() -> None:
    body = '{"api_key": "abc123", "q": "AMS"}'

    result = redact_secrets(None, "info", {"event": "call", "body": body})

    assert result["body"] == f'{{"api_key": "{REDACTED}", "q": "AMS"}}'


def test_objects_are_rendered_as_text_and_scrubbed() -> None:
    class Url:
        def __str__(self) -> str:
            return "https://serpapi.com/search?api_key=abc123"

    result = redact_secrets(None, "info", {"event": "call", "url": Url()})

    assert result["url"] == f"https://serpapi.com/search?api_key={REDACTED}"


def test_known_secret_values_are_redacted_wherever_they_appear() -> None:
    redactor = SecretRedactor(known_secrets=["zx81-unusual-format"])

    result = redactor(None, "info", {"event": "call", "detail": "got zx81-unusual-format back"})

    assert result["detail"] == f"got {REDACTED} back"


def test_non_string_keys_do_not_break_logging() -> None:
    result = redact_secrets(None, "info", {"event": "ranked", "by_rank": {1: "Porto"}})

    assert result["by_rank"] == {1: "Porto"}


def test_ordinary_fields_are_left_alone() -> None:
    result = redact_secrets(None, "info", {"event": "ranked", "rank": 1, "total": 7.4})

    assert result == {"event": "ranked", "rank": 1, "total": 7.4}


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


def test_logged_exceptions_are_scrubbed_in_json(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", fmt="json")

    try:
        raise RuntimeError("GET https://serpapi.com/search?api_key=abc123 failed")
    except RuntimeError:
        structlog.get_logger().exception("serpapi_failed")

    output = capsys.readouterr().err
    assert "RuntimeError" in output
    assert "abc123" not in output


def test_logged_exceptions_are_scrubbed_in_console(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", fmt="console")

    try:
        raise RuntimeError("GET https://serpapi.com/search?api_key=abc123 failed")
    except RuntimeError:
        structlog.get_logger().exception("serpapi_failed")

    output = capsys.readouterr().err
    assert "serpapi_failed" in output
    assert "abc123" not in output


def test_known_secrets_passed_to_configure_are_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", fmt="json", known_secrets=["zx81-unusual-format"])

    structlog.get_logger().info("echo", detail="zx81-unusual-format")

    assert "zx81-unusual-format" not in capsys.readouterr().err


def test_messages_below_the_level_are_dropped(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="WARNING", fmt="json")

    structlog.get_logger().info("chatty")

    assert capsys.readouterr().err == ""
