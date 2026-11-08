from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(include_in_schema=False)


@router.get("/")
def player_page() -> FileResponse:
    return FileResponse("analog_tv/static/player.html")


@router.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse("analog_tv/static/admin.html")
