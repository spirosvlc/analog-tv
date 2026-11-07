from fastapi import APIRouter, HTTPException, status

from analog_tv.api.dependencies import DatabaseSession
from analog_tv.domain.schemas import AlertCreate, AlertResponse
from analog_tv.services.alert_service import (
    AlertNotFoundError,
    AlertService,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_alert(
    payload: AlertCreate,
    session: DatabaseSession,
):
    alert = AlertService(session).create(payload)
    return {"id": alert.id}


@router.post("/test-weather", status_code=status.HTTP_201_CREATED)
def test_weather_alert(session: DatabaseSession):
    alert = AlertService(session).create(
        AlertCreate(
            level="medium",
            message="[ΕΜΥ TEST • ΑΤΤΙΚΗ]  Δοκιμαστική προειδοποίηση καιρού για την περιοχή της Αττικής • Ισχυρές βροχές και καταιγίδες κατά τόπους. Αυτό είναι δοκιμαστικό μήνυμα Analog TV.",
        )
    )
    return {"id": alert.id, "ok": True}


@router.get("/latest", response_model=AlertResponse | None)
def latest_alert(
    session: DatabaseSession,
    after_id: int = 0,
):
    alert = AlertService(session).latest_after(after_id)
    if alert is None:
        return None

    return AlertResponse(
        id=alert.id,
        level=alert.level,
        message=alert.message,
        created_at=alert.created_at.isoformat(),
    )


@router.post("/{alert_id}/dismiss")
def dismiss_alert(
    alert_id: int,
    session: DatabaseSession,
):
    try:
        AlertService(session).dismiss(alert_id)
    except AlertNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    return {"ok": True}
