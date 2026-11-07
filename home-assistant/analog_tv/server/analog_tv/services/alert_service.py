from sqlalchemy.orm import Session

from analog_tv.db.models import AlertModel
from analog_tv.db.repositories import AlertRepository
from analog_tv.domain.schemas import AlertCreate


class AlertNotFoundError(ValueError):
    pass


class AlertService:
    def __init__(self, session: Session) -> None:
        self.repository = AlertRepository(session)

    def create(self, payload: AlertCreate) -> AlertModel:
        return self.repository.create(
            AlertModel(
                level=payload.level.value,
                message=payload.message,
                active=True,
            )
        )

    def latest_after(self, alert_id: int) -> AlertModel | None:
        return self.repository.latest_after(alert_id)

    def dismiss(self, alert_id: int) -> None:
        alert = self.repository.get(alert_id)
        if alert is None:
            raise AlertNotFoundError("Alert not found.")

        alert.active = False
        self.repository.save()
