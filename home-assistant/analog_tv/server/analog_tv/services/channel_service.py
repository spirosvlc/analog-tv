import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from analog_tv.db.models import ChannelItemModel, ChannelModel
from analog_tv.db.repositories import ChannelRepository
from analog_tv.domain.enums import ChannelSourceType
from analog_tv.services.media_service import M3UImporter, MediaScanner, PlaylistEntry
from analog_tv.services.media_probe import MediaProbe
from analog_tv.integrations.youtube import YouTubeClient


class DuplicateChannelNumberError(ValueError):
    pass


class ChannelNotFoundError(ValueError):
    pass


class ChannelService:
    def __init__(self, session: Session, media_scanner=None, m3u_importer=None):
        self.repository = ChannelRepository(session)
        self.media_scanner = media_scanner or MediaScanner()
        self.m3u_importer = m3u_importer or M3UImporter()
        self.probe = MediaProbe()
        self.session = session

    def list_channels(self):
        return self.repository.list_enabled()

    async def create_channel(self, payload):
        # Multi-station IPTV lists become real Analog TV channels. The number entered
        # in Admin is the first channel number assigned to the imported list.
        if payload.source_type == ChannelSourceType.M3U:
            entries = await self.m3u_importer.import_entries(payload.source)
            if len(entries) > 1:
                return self._create_m3u_channels(payload, entries)

        channel = ChannelModel(
            number=payload.number,
            name=payload.name,
            source_type=payload.source_type.value,
            source=payload.source,
            logo_url=payload.logo_url,
            enabled=payload.enabled,
            broadcast_epoch=datetime.utcnow(),
        )
        try:
            self.repository.add(channel)
        except IntegrityError as exc:
            self.repository.session.rollback()
            raise DuplicateChannelNumberError(
                "A channel with this number already exists."
            ) from exc

        try:
            count = await self.scan_channel(channel.id)
        except Exception:
            self.repository.delete(channel)
            raise
        return channel, count, 1

    def _create_m3u_channels(self, payload, entries: list[PlaylistEntry]):
        end_number = payload.number + len(entries) - 1
        if end_number > 999:
            raise ValueError(
                f"Playlist contains {len(entries)} stations; starting at "
                f"{payload.number} would exceed Analog TV channel 999."
            )

        requested_numbers = list(range(payload.number, end_number + 1))
        existing = set(
            self.session.scalars(
                select(ChannelModel.number).where(
                    ChannelModel.number.in_(requested_numbers)
                )
            ).all()
        )
        if existing:
            numbers = ", ".join(str(number) for number in sorted(existing))
            raise DuplicateChannelNumberError(
                f"Cannot import playlist because Analog TV channel number(s) "
                f"{numbers} already exist. Choose a different starting number."
            )

        created = []
        now = datetime.utcnow()
        try:
            for offset, entry in enumerate(entries):
                number = payload.number + offset
                channel = ChannelModel(
                    number=number,
                    name=(entry.title or f"Stream {offset + 1}")[:120],
                    source_type=ChannelSourceType.STREAM.value,
                    source=entry.media_url,
                    logo_url=None,
                    enabled=payload.enabled,
                    broadcast_epoch=now,
                )
                channel.items.append(
                    ChannelItemModel(
                        title=entry.title or f"Stream {offset + 1}",
                        media_url=entry.media_url,
                        position=0,
                        duration_seconds=0,
                        media_kind="hls" if ".m3u8" in entry.media_url.lower() else "video",
                    )
                )
                self.session.add(channel)
                created.append(channel)

            # One commit means collisions/errors cannot leave a partial import.
            self.session.commit()
            for channel in created:
                self.session.refresh(channel)
        except Exception:
            self.session.rollback()
            raise

        return created[0], len(entries), len(created)

    async def scan_channel(self, channel_id):
        channel = self.repository.get(channel_id)
        if channel is None:
            raise ChannelNotFoundError("Channel not found.")
        channel.items.clear()

        if channel.source_type == ChannelSourceType.FOLDER.value:
            files = self.media_scanner.scan(channel.source)
            for pos, media_file in enumerate(files):
                channel.items.append(
                    ChannelItemModel(
                        title=media_file.stem,
                        media_url=f"/api/channels/media/{channel.id}/{pos}",
                        position=pos,
                        duration_seconds=self.probe.duration(media_file),
                        media_kind="video",
                    )
                )

        elif channel.source_type == ChannelSourceType.M3U.value:
            entries = await self.m3u_importer.import_entries(channel.source)
            if len(entries) > 1:
                return self._expand_existing_m3u_channel(channel, entries)
            for pos, entry in enumerate(entries):
                channel.items.append(
                    ChannelItemModel(
                        title=entry.title,
                        media_url=entry.media_url,
                        position=pos,
                        duration_seconds=0,
                        media_kind="hls",
                    )
                )

        elif channel.source_type == ChannelSourceType.STREAM.value:
            channel.items.append(
                ChannelItemModel(
                    title=channel.name,
                    media_url=channel.source,
                    position=0,
                    duration_seconds=0,
                    media_kind=(
                        "hls" if ".m3u8" in channel.source.lower() else "video"
                    ),
                )
            )

        elif channel.source_type == ChannelSourceType.YOUTUBE.value:
            try:
                channel_ids = json.loads(channel.source)
            except json.JSONDecodeError:
                channel_ids = [
                    item.strip()
                    for item in channel.source.split(",")
                    if item.strip()
                ]
            per = int(
                __import__(
                    "app.services.settings_service",
                    fromlist=["SettingsService"],
                ).SettingsService(self.session).get_value(
                    "youtube_videos_per_creator", "3"
                )
            )
            videos = await YouTubeClient(self.session).latest_videos(
                channel_ids, per
            )
            for pos, video in enumerate(videos):
                channel.items.append(
                    ChannelItemModel(
                        title=f"{video['creator']} — {video['title']}",
                        media_url=f"youtube:{video['video_id']}",
                        position=pos,
                        duration_seconds=float(video.get("duration_seconds", 0)),
                        media_kind="youtube",
                        provider_id=video["video_id"],
                        thumbnail_url=video.get("thumbnail"),
                    )
                )
        elif channel.source_type == ChannelSourceType.WEATHER.value:
            # Generated live in the Analog TV player, no downloadable media.
            pass
        elif channel.source_type == ChannelSourceType.PLUTO.value:
            # Official Pluto TV channel URL opens in the authorized Pluto app.
            if not channel.source.startswith(("https://pluto.tv/", "https://www.pluto.tv/")):
                raise ValueError("Pluto links must use an official pluto.tv URL.")
        else:
            raise ValueError("Unsupported channel source type.")

        channel.broadcast_epoch = datetime.utcnow()
        self.repository.save()
        return len(channel.items)


    def _expand_existing_m3u_channel(
        self, channel: ChannelModel, entries: list[PlaylistEntry]
    ) -> int:
        """Convert a legacy multi-item M3U channel into real Analog TV channels."""
        end_number = channel.number + len(entries) - 1
        if end_number > 999:
            raise ValueError(
                f"Playlist contains {len(entries)} stations; starting at "
                f"{channel.number} would exceed Analog TV channel 999."
            )

        additional_numbers = list(range(channel.number + 1, end_number + 1))
        if additional_numbers:
            existing = set(
                self.session.scalars(
                    select(ChannelModel.number).where(
                        ChannelModel.number.in_(additional_numbers)
                    )
                ).all()
            )
            if existing:
                numbers = ", ".join(str(number) for number in sorted(existing))
                raise DuplicateChannelNumberError(
                    f"Cannot expand playlist because Analog TV channel number(s) "
                    f"{numbers} already exist. Move/delete those channels or "
                    f"re-import the playlist using another starting number."
                )

        original_source = channel.source
        original_logo = channel.logo_url
        original_enabled = channel.enabled
        now = datetime.utcnow()

        try:
            # Reuse the existing DB row for the first station so bookmarks/API
            # references to this Analog TV channel remain as stable as possible.
            first = entries[0]
            channel.name = (first.title or "Stream 1")[:120]
            channel.source_type = ChannelSourceType.STREAM.value
            channel.source = first.media_url
            channel.logo_url = original_logo
            channel.broadcast_epoch = now
            channel.items.clear()
            channel.items.append(
                ChannelItemModel(
                    title=first.title or "Stream 1",
                    media_url=first.media_url,
                    position=0,
                    duration_seconds=0,
                    media_kind=(
                        "hls" if ".m3u8" in first.media_url.lower() else "video"
                    ),
                )
            )

            for offset, entry in enumerate(entries[1:], start=1):
                new_channel = ChannelModel(
                    number=channel.number + offset,
                    name=(entry.title or f"Stream {offset + 1}")[:120],
                    source_type=ChannelSourceType.STREAM.value,
                    source=entry.media_url,
                    logo_url=None,
                    enabled=original_enabled,
                    broadcast_epoch=now,
                )
                new_channel.items.append(
                    ChannelItemModel(
                        title=entry.title or f"Stream {offset + 1}",
                        media_url=entry.media_url,
                        position=0,
                        duration_seconds=0,
                        media_kind=(
                            "hls"
                            if ".m3u8" in entry.media_url.lower()
                            else "video"
                        ),
                    )
                )
                self.session.add(new_channel)

            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

        return len(entries)

    def delete_channel(self, channel_id):
        channel = self.repository.get(channel_id)
        if channel is None:
            raise ChannelNotFoundError("Channel not found.")
        self.repository.delete(channel)

    def resolve_local_media(self, channel_id, position):
        channel = self.repository.get(channel_id)
        if (
            channel is None
            or channel.source_type != ChannelSourceType.FOLDER.value
        ):
            raise ChannelNotFoundError("Media not found.")
        files = self.media_scanner.scan(channel.source)
        if position < 0 or position >= len(files):
            raise ChannelNotFoundError("Media not found.")
        folder = Path(channel.source).expanduser().resolve()
        media_file = files[position].resolve()
        if folder not in media_file.parents:
            raise PermissionError("Invalid media path.")
        return media_file
