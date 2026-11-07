from fastapi import APIRouter

from analog_tv.api.dependencies import DatabaseSession
from analog_tv.domain.schemas import SettingsUpdate
from analog_tv.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings(session: DatabaseSession):
    return SettingsService(session).get_public_settings()


@router.put("")
def update_settings(
    payload: SettingsUpdate,
    session: DatabaseSession,
):
    SettingsService(session).update(payload)
    return {"ok": True}
