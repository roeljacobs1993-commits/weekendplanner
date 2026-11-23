import pytest
from pydantic import ValidationError

from app.config import Settings

CONTACT = "https://example.org/contact"


def make(**overrides: str) -> Settings:
    # _env_file=None keeps tests independent of a developer's local .env. The ignore is needed
    # because pydantic-settings' `_env_file` init kwarg and the env-style field aliases are not
    # part of the generated __init__ signature that pyright sees.
    return Settings(_env_file=None, **overrides)  # pyright: ignore[reportCallIssue]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "SERPAPI_KEY",
        "TRAVELPAYOUTS_TOKEN",
        "NS_API_KEY",
        "ORS_API_KEY",
        "CONTACT_URL",
        "LOG_LEVEL",
        "LOG_FORMAT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_valid_config_applies_defaults() -> None:
    settings = make(CONTACT_URL=CONTACT)

    assert settings.contact_url == CONTACT
    assert settings.log_level == "INFO"
    assert settings.log_format == "json"
    assert settings.serpapi_key is None


def test_valid_key_is_kept_secret() -> None:
    settings = make(CONTACT_URL=CONTACT, SERPAPI_KEY="abcdef1234567890")

    assert settings.serpapi_key is not None
    assert settings.serpapi_key.get_secret_value() == "abcdef1234567890"
    assert "abcdef1234567890" not in repr(settings)


def test_missing_contact_url_is_rejected() -> None:
    with pytest.raises(ValidationError, match="contact_url"):
        make()


@pytest.mark.parametrize(
    "key_name", ["SERPAPI_KEY", "TRAVELPAYOUTS_TOKEN", "NS_API_KEY", "ORS_API_KEY"]
)
def test_key_with_space_is_rejected(key_name: str) -> None:
    with pytest.raises(ValidationError, match="spaces"):
        make(CONTACT_URL=CONTACT, **{key_name: "abcd efgh12345678"})


def test_rejected_key_value_is_not_echoed_in_the_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        make(CONTACT_URL=CONTACT, SERPAPI_KEY="leaky secret 1234567890")

    assert "leaky secret" not in str(exc_info.value)


def test_explicitly_passed_empty_key_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        make(CONTACT_URL=CONTACT, SERPAPI_KEY="")


def test_too_short_key_is_rejected() -> None:
    with pytest.raises(ValidationError, match="at least"):
        make(CONTACT_URL=CONTACT, NS_API_KEY="short")


def test_empty_key_counts_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # `KEY=` as copied from .env.example arrives via the environment, not as an init argument.
    monkeypatch.setenv("ORS_API_KEY", "")

    settings = make(CONTACT_URL=CONTACT)

    assert settings.ors_api_key is None


@pytest.mark.parametrize(
    "value",
    [
        "mailto:me@example.org",
        "me@example.org",
        "http://example.org",
        "https://me@example.org",
        "https://example.org/?contact=me@example.org",
    ],
)
def test_non_https_or_email_contact_is_rejected(value: str) -> None:
    with pytest.raises(ValidationError, match="https"):
        make(CONTACT_URL=value)


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError, match="log_level"):
        make(CONTACT_URL=CONTACT, LOG_LEVEL="LOUD")


def test_environ_is_only_read_in_config_module() -> None:
    from pathlib import Path

    src = Path(__file__).parents[2] / "src" / "app"
    config_module = src / "config.py"
    offenders = [
        str(p.relative_to(src))
        for p in src.rglob("*.py")
        if p != config_module
        and any(token in p.read_text(encoding="utf-8") for token in ("environ", "getenv", "putenv"))
    ]

    assert offenders == []
