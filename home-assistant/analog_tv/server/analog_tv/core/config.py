"""Analog TV settings. Never commit .env or /config/auth.env to GitHub."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApplicationSettings(BaseSettings):
    app_name: str = "Analog TV"
    host: str = "0.0.0.0"
    port: int = 8080
    database_url: str = "sqlite:///./data/analog_tv.db"
    log_level: str = "INFO"
    alert_poll_seconds: int = 2

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    admin_email: str = ""
    session_secret: str = ""
    public_base_url: str = ""
    cookie_secure: bool = True

    model_config = SettingsConfigDict(
        env_file=(".env", "/config/auth.env"),
        env_prefix="ANALOG_",
        extra="ignore",
    )

    def ensure_directories(self) -> None:
        Path("data").mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> ApplicationSettings:
    settings = ApplicationSettings()
    settings.ensure_directories()
    return settings
