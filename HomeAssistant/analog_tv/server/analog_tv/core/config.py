"""Analog TV settings. Never commit .env or /config/auth.env to GitHub."""
import os
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApplicationSettings(BaseSettings):
    app_name: str = "Analog TV"
    host: str = "0.0.0.0"
    port: int = 8080
    database_url: str = "sqlite:///./data/analog_tv.db"
    log_level: str = "INFO"
    alert_poll_seconds: int = 2

    lan_admin: bool = False
    allow_admin_setup: bool = False
    admin_username: str = ""
    admin_password_hash: str = ""
    session_secret: str = ""
    public_base_url: str = ""
    cookie_secure: bool | None = True

    @field_validator("cookie_secure", mode="before")
    @classmethod
    def parse_cookie_secure(cls, value):
        return {"true": True, "false": False}.get(str(value).lower())

    model_config = SettingsConfigDict(
        env_file=(".env", "auth.env", "/config/auth.env"),
        env_prefix="ANALOG_",
        extra="ignore",
    )

    def ensure_directories(self) -> None:
        Path("data").mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> ApplicationSettings:
    settings = (ApplicationSettings(_env_file=None) if os.environ.get("ANALOG_LAN_ADMIN") == "true"
                else ApplicationSettings())
    settings.ensure_directories()
    return settings
