from sqlalchemy.orm import Session

from analog_tv.db.repositories import SettingsRepository
from analog_tv.domain.schemas import SettingsUpdate


class SettingsService:
    SECRET_KEYS = {"telegram_token", "youtube_client_secret", "youtube_access_token", "youtube_refresh_token", "youtube_oauth_state"}

    def __init__(self, session: Session) -> None:
        self.repository = SettingsRepository(session)

    def get_public_settings(self) -> dict[str, str]:
        values = self.repository.get_all()
        for key in self.SECRET_KEYS:
            if key in values:
                values[key] = ""
        return values

    def get_value(self, key: str, default: str = "") -> str:
        return self.repository.get(key, default)

    def set_value(self, key: str, value: str) -> None:
        self.repository.set(key, str(value))
        self.repository.save()

    def update(self, payload: SettingsUpdate) -> None:
        for key, value in payload.model_dump(exclude_none=True).items():
            if key in self.SECRET_KEYS and value == "":
                continue

            serialized = (
                str(value).lower()
                if isinstance(value, bool)
                else str(value)
            )
            self.repository.set(key, serialized)

        self.repository.save()
