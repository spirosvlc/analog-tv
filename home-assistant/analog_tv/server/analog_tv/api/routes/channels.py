import mimetypes

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from analog_tv.api.dependencies import DatabaseSession
from analog_tv.domain.schemas import (
    ChannelCreate,
    ChannelCreatedResponse,
    ChannelResponse,
    NowPlayingResponse,
)
from analog_tv.services.folder_picker_service import FolderPickerService
from analog_tv.services.broadcast_service import BroadcastService
from analog_tv.services.channel_service import (
    ChannelNotFoundError,
    ChannelService,
    DuplicateChannelNumberError,
)

router = APIRouter(prefix="/channels", tags=["channels"])


@router.post("/select-folder")
def select_folder():
    selected = FolderPickerService().select_folder()
    return {"path": selected}


@router.get("", response_model=list[ChannelResponse])
def list_channels(session: DatabaseSession):
    return ChannelService(session).list_channels()


@router.post(
    "",
    response_model=ChannelCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel(
    payload: ChannelCreate,
    session: DatabaseSession,
):
    service = ChannelService(session)

    try:
        channel, item_count, channels_created = await service.create_channel(payload)
    except DuplicateChannelNumberError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    return ChannelCreatedResponse(
        id=channel.id,
        items_imported=item_count,
        channels_created=channels_created,
    )


@router.get("/{channel_id}/now", response_model=NowPlayingResponse)
def now_playing(channel_id:int, session:DatabaseSession):
    try:
        channel,item,offset,live=BroadcastService(session).now(channel_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND,str(exc)) from exc
    return NowPlayingResponse(channel_id=channel.id,channel_number=channel.number,channel_name=channel.name,item=item,offset_seconds=offset,live=live)


@router.post("/{channel_id}/scan")
async def scan_channel(
    channel_id: int,
    session: DatabaseSession,
):
    try:
        item_count = await ChannelService(session).scan_channel(
            channel_id
        )
    except ChannelNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    return {"items_imported": item_count}


@router.delete(
    "/{channel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_channel(
    channel_id: int,
    session: DatabaseSession,
):
    try:
        ChannelService(session).delete_channel(channel_id)
    except ChannelNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.get("/media/{channel_id}/{position}", include_in_schema=False)
def local_media(
    channel_id: int,
    position: int,
    session: DatabaseSession,
):
    try:
        media_file = ChannelService(session).resolve_local_media(
            channel_id,
            position,
        )
    except ChannelNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc

    media_type, _ = mimetypes.guess_type(media_file.name)
    return FileResponse(
        media_file,
        media_type=media_type or "application/octet-stream",
    )
