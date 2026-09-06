"""Cyberdrop resolver.

Album pages expose per-file ids; each file is signed via the public API:
    1. GET https://api.cyberdrop.cr/api/file/info/<id>
    2. GET <auth_url>  ->  {"url": "<signed CDN URL>"}

Album URL shape: https://cyberdrop.cr/a/<album_id>
File URL shape:  https://cyberdrop.cr/{f|e|v}/<file_id>
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.misc import http_client

from .base import ResolvedItem

_ROOT = "https://cyberdrop.cr"
_API = "https://api.cyberdrop.cr"
_ALBUM_RE = re.compile(r"cyberdrop\.[a-z.]+/a/([^/?#]+)", re.I)
_FILE_RE = re.compile(r"cyberdrop\.[a-z.]+/[fev]/([^/?#]+)", re.I)
_TIMEOUT = (10, 30)
_REFERER = {"Referer": f"{_ROOT}/"}


class CyberdropResolver:
    """Resolve Cyberdrop album and single-file URLs."""

    name = "cyberdrop"

    def matches(self, url: str) -> bool:
        """Return True for Cyberdrop album or file URLs."""
        host = urlparse(url).netloc.lower()
        return "cyberdrop." in host

    def resolve(self, url: str) -> list[ResolvedItem]:
        """Resolve a Cyberdrop URL into downloadable items."""
        album_match = _ALBUM_RE.search(url)
        if album_match:
            return self._resolve_album(album_match.group(1))

        file_match = _FILE_RE.search(url)
        if file_match:
            item = self._resolve_file(file_match.group(1))
            return [item] if item else []

        return []

    def _resolve_album(self, album_id: str) -> list[ResolvedItem]:
        try:
            response = http_client.get(f"{_ROOT}/a/{album_id}", timeout=_TIMEOUT)
            response.raise_for_status()
        except http_client.RequestError:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        file_ids: list[str] = []
        for anchor in soup.find_all("a", href=True, id="file"):
            href = anchor["href"]
            match = re.search(r"/[fev]/([^/?#]+)", href, re.I)
            if match:
                file_ids.append(match.group(1))

        if not file_ids:
            # Fallback: any /f/ links on the album page.
            for match in re.finditer(r'/[fev]/([A-Za-z0-9_-]+)"', response.text):
                file_ids.append(match.group(1))

        items: list[ResolvedItem] = []
        for file_id in dict.fromkeys(file_ids):
            item = self._resolve_file(file_id)
            if item:
                items.append(item)
        return items

    def _resolve_file(self, file_id: str) -> ResolvedItem | None:
        try:
            info_response = http_client.get(
                f"{_API}/api/file/info/{file_id}",
                timeout=_TIMEOUT,
            )
            info_response.raise_for_status()
            info = info_response.json()

            auth_url = info.get("auth_url") or f"{_API}/api/file/auth/{file_id}"
            auth_response = http_client.get(auth_url, timeout=_TIMEOUT)
            auth_response.raise_for_status()
            auth = auth_response.json()
        except (*http_client.RequestError, ValueError, TypeError):
            return None

        download_url = auth.get("url")
        if not download_url:
            return None

        filename = info.get("name") or info.get("filename") or f"{file_id}.bin"
        # Cyberdrop filenames often end with -<shortid>; keep as-is for uniqueness.
        size = int(info.get("size", -1) or -1)
        return ResolvedItem(
            download_url=download_url,
            filename=filename,
            headers=dict(_REFERER),
            size=size,
        )
