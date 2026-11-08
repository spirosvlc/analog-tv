from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

VIDEO_EXTENSIONS = {".mp4", ".m4v", ".webm", ".mov"}


@dataclass(frozen=True, slots=True)
class PlaylistEntry:
    title: str
    media_url: str


class MediaScanner:
    """Discovers video files inside an approved channel directory."""

    def scan(self, source: str) -> list[Path]:
        folder = Path(source).expanduser().resolve()
        if not folder.exists():
            raise ValueError("The configured folder does not exist.")
        if not folder.is_dir():
            raise ValueError("The configured source is not a directory.")

        return sorted(
            path
            for path in folder.rglob("*")
            if path.is_file()
            and path.suffix.lower() in VIDEO_EXTENSIONS
        )


class M3UImporter:
    """
    Downloads and parses remote M3U playlists.

    HLS manifests are intentionally kept as one playable item. The browser's
    HLS player must receive the original manifest URL so it can follow variant,
    audio, subtitle, segment, and encryption-key references correctly.

    Traditional IPTV M3U playlists are expanded into individual channel items.
    Relative URLs are resolved against the playlist URL.
    """

    HLS_TAG_PREFIXES = (
        "#EXT-X-STREAM-INF",
        "#EXT-X-TARGETDURATION",
        "#EXT-X-MEDIA-SEQUENCE",
        "#EXT-X-PLAYLIST-TYPE",
        "#EXT-X-ENDLIST",
        "#EXT-X-I-FRAME-STREAM-INF",
        "#EXT-X-MEDIA:",
        "#EXT-X-KEY:",
        "#EXT-X-MAP:",
    )

    async def import_entries(self, source: str) -> list[PlaylistEntry]:
        source = self.normalize_source_url(source)
        self._validate_http_url(source)

        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
        ) as client:
            response = await client.get(source)
            response.raise_for_status()

        content = response.text

        if self.is_hls_manifest(content, source):
            return [
                PlaylistEntry(
                    title=self._title_from_url(source),
                    media_url=str(response.url),
                )
            ]

        return self.parse(content, base_url=str(response.url))

    @classmethod
    def is_hls_manifest(cls, content: str, source: str = "") -> bool:
        """Distinguish a true HLS manifest from an IPTV channel list.

        Some public IPTV lists use a .m3u8 filename even though they contain
        many #EXTINF station entries. A true HLS manifest is identified by
        HLS-specific #EXT-X-* tags, not by the filename alone.
        """
        lines = [line.strip() for line in content.splitlines() if line.strip()]

        if any(line.startswith(cls.HLS_TAG_PREFIXES) for line in lines):
            return True

        # Multiple EXTINF records are a traditional IPTV playlist even when
        # the URL happens to end in .m3u8.
        extinf_count = sum(1 for line in lines if line.startswith("#EXTINF:"))
        if extinf_count > 1:
            return False

        # A single EXTINF without any HLS tags is also treated as an M3U list
        # so it can be imported normally.
        if extinf_count == 1:
            return False

        # Extension is only a fallback for minimal/odd HLS manifests.
        return urlparse(source).path.lower().endswith(".m3u8")

    @staticmethod
    def parse(
        content: str,
        base_url: str | None = None,
    ) -> list[PlaylistEntry]:
        entries: list[PlaylistEntry] = []
        pending_title = ""

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("#EXTINF:"):
                pending_title = (
                    line.split(",", 1)[1].strip()
                    if "," in line
                    else "Stream"
                )
                continue

            if line.startswith("#"):
                continue

            media_url = urljoin(base_url, line) if base_url else line
            title = pending_title or f"Stream {len(entries) + 1}"

            entries.append(
                PlaylistEntry(
                    title=title,
                    media_url=media_url,
                )
            )
            pending_title = ""

        return entries

    @staticmethod
    def normalize_source_url(source: str) -> str:
        """
        Converts common GitHub file-page URLs to raw file URLs.

        Example:
        https://github.com/Free-TV/IPTV/blob/master/playlist.m3u8
        becomes:
        https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8
        """
        parsed = urlparse(source)

        if parsed.netloc.lower() == "github.com":
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 5 and parts[2] == "blob":
                owner, repository, _, branch, *file_parts = parts
                raw_path = "/".join(file_parts)
                return (
                    f"https://raw.githubusercontent.com/"
                    f"{owner}/{repository}/{branch}/{raw_path}"
                )

        return source

    @staticmethod
    def _validate_http_url(source: str) -> None:
        parsed = urlparse(source)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("M3U source must use HTTP or HTTPS.")

    @staticmethod
    def _title_from_url(source: str) -> str:
        filename = Path(urlparse(source).path).name
        return filename or "HLS Stream"
