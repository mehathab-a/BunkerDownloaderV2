"""Saint / saint2 resolver.

Saint is primarily a single-video host. Resolution strategy:
    1. Normalize /d/<id> and /embed/<id> URLs to an embed page.
    2. Scrape the <video> source URL from the embed HTML.
    3. Fall back to any /api/download.php?file=... link found on the page.

Known domains rotate (saint2.su, saint2.pk, etc.); matching is hostname-based.
"""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

from src.misc import http_client

from .base import ResolvedItem

_HOST_RE = re.compile(r"(?:^|\.)saint2?\.(?:su|to|pk|cr|st)$", re.I)
_ID_RE = re.compile(r"/(?:embed|d)/([^/?#]+)", re.I)
_DOWNLOAD_RE = re.compile(
    r"https?://[^\"'\s]+/api/download\.php\?file=[^\"'\s]+",
    re.I,
)
_TIMEOUT = (10, 30)


class SaintResolver:
    """Resolve Saint/saint2 video URLs."""

    name = "saint"

    def matches(self, url: str) -> bool:
        """Return True for Saint / saint2 video URLs."""
        host = urlparse(url).netloc.lower().split(":")[0]
        # Strip leading subdomain (e.g. simp2.saint2.su).
        parts = host.split(".")
        for indx in range(len(parts) - 1):
            candidate = ".".join(parts[indx:])
            if _HOST_RE.search(candidate) or candidate.startswith("saint2.") or candidate.startswith("saint."):
                return True
        return "saint2." in host or host.endswith("saint.to")

    def resolve(self, url: str) -> list[ResolvedItem]:
        """Resolve a Saint video URL into a downloadable item."""
        parsed = urlparse(url)
        root = f"{parsed.scheme or 'https'}://{parsed.netloc}"
        id_match = _ID_RE.search(parsed.path)
        video_id = id_match.group(1) if id_match else None

        candidates = []
        if video_id:
            candidates.append(f"{root}/embed/{video_id}")
            candidates.append(f"{root}/d/{video_id}")
        candidates.append(url)

        for page_url in dict.fromkeys(candidates):
            item = self._resolve_page(page_url, video_id or "saint")
            if item:
                return [item]
        return []

    def _resolve_page(self, page_url: str, fallback_id: str) -> ResolvedItem | None:
        try:
            response = http_client.get(page_url, timeout=_TIMEOUT)
            response.raise_for_status()
        except http_client.RequestError:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        source = soup.select_one("video#main-video source, video source, source[src]")
        download_url = source.get("src") if source else None

        if not download_url:
            match = _DOWNLOAD_RE.search(response.text)
            download_url = match.group(0) if match else None

        if not download_url:
            return None

        filename = self._guess_filename(download_url, fallback_id)
        return ResolvedItem(
            download_url=download_url,
            filename=filename,
            headers={"Referer": page_url},
        )

    def _guess_filename(self, download_url: str, fallback_id: str) -> str:
        path_name = unquote(urlparse(download_url).path.rstrip("/").split("/")[-1])
        if path_name and "." in path_name and path_name != "download.php":
            return path_name
        return f"{fallback_id}.mp4"
