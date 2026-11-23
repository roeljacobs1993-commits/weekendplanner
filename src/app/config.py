"""Application settings. The only module that reads the environment or `.env`."""

from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import AfterValidator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_KEY_LENGTH = 8


def _validate_key(value: SecretStr) -> SecretStr:
    raw = value.get_secret_value()
    if not raw:
        msg = "must not be empty"
        raise ValueError(msg)
    if any(ch.isspace() for ch in raw):
        msg = "must not contain spaces"
        raise ValueError(msg)
    if len(raw) < MIN_KEY_LENGTH:
        msg = f"must be at least {MIN_KEY_LENGTH} characters"
        raise ValueError(msg)
    return value


def _validate_contact_url(value: str) -> str:
    parsed = urlparse(value)
    # The contact ends up in public User-Agent headers, so no e-mail address anywhere in it.
    if parsed.scheme != "https" or not parsed.netloc or "@" in value:
        msg = "must be an https:// URL (no e-mail address or mailto:)"
        raise ValueError(msg)
    return value


ApiKey = Annotated[SecretStr, AfterValidator(_validate_key)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        # `KEY=` lines copied from .env.example count as unset.
        env_ignore_empty=True,
        # A rejected API key must never be echoed back in a validation error.
        hide_input_in_errors=True,
    )

    serpapi_key: ApiKey | None = None
    travelpayouts_token: ApiKey | None = None
    ns_api_key: ApiKey | None = None
    ors_api_key: ApiKey | None = None
    contact_url: Annotated[str, AfterValidator(_validate_contact_url)]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"
