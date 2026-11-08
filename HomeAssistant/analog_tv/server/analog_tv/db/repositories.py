from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from analog_tv.db.models import (
    AlertModel,
    ChannelModel,
    SettingModel,
)


class ChannelRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_enabled(self) -> list[ChannelModel]:
        statement = (
            select(ChannelModel)
            .where(ChannelModel.enabled.is_(True))
            .options(selectinload(ChannelModel.items))
            .order_by(ChannelModel.number)
        )
        return list(self.session.scalars(statement).all())

    def get(self, channel_id: int) -> ChannelModel | None:
        statement = (
            select(ChannelModel)
            .where(ChannelModel.id == channel_id)
            .options(selectinload(ChannelModel.items))
        )
        return self.session.scalar(statement)

    def add(self, channel: ChannelModel) -> ChannelModel:
        self.session.add(channel)
        self.session.commit()
        self.session.refresh(channel)
        return channel

    def save(self) -> None:
        self.session.commit()

    def delete(self, channel: ChannelModel) -> None:
        self.session.delete(channel)
        self.session.commit()


class AlertRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, alert: AlertModel) -> AlertModel:
        self.session.add(alert)
        self.session.commit()
        self.session.refresh(alert)
        return alert

    def latest_after(self, alert_id: int) -> AlertModel | None:
        statement = (
            select(AlertModel)
            .where(
                AlertModel.active.is_(True),
                AlertModel.id > alert_id,
            )
            .order_by(AlertModel.id.desc())
        )
        return self.session.scalar(statement)

    def get(self, alert_id: int) -> AlertModel | None:
        return self.session.get(AlertModel, alert_id)

    def save(self) -> None:
        self.session.commit()


class SettingsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, key: str, default: str = "") -> str:
        row = self.session.get(SettingModel, key)
        return row.value if row else default

    def get_all(self) -> dict[str, str]:
        rows = self.session.scalars(select(SettingModel)).all()
        return {row.key: row.value for row in rows}

    def set(self, key: str, value: str) -> None:
        row = self.session.get(SettingModel, key)
        if row is None:
            row = SettingModel(key=key, value=value)
            self.session.add(row)
        else:
            row.value = value

    def save(self) -> None:
        self.session.commit()
