"""PixelDrain resolver.

PixelDrain exposes a clean, documented REST API:
    - Single file page:  https://pixeldrain.com/u/<id>
    - File list/album:   https://pixeldrain.com/l/<id>
    - File info:         GET https://pixeldrain.com/api/file/<id>/info
    - List info:         GET https://pixeldrain.com/api/list/<id>
    - Direct download:   https://pixeldrain.com/api/file/<id>?download

Reads are unauthenticated, so no signing/tokens are required.
"""

from __future__ import annotations

import re

from src.misc import http_client

_API = "https://pixeldrain.com/api"
_FILE_RE = re.compile(r"pixeldrain\.com/(?:u|api/file)/([A-Za-z0-9]+)")
_LIST_RE = re.compile(r"pixeldrain\.com/(?:l|api/list)/([A-Za-z0-9]+)")
_TIMEOUT = (10, 30)


class PixeldrainResolver:
    """Resolve PixelDrain file and list URLs."""

    name = "pixeldrain"

    def matches(self, url: str) -> bool:
        """Return True for PixelDrain file or list URLs."""
        return "pixeldrain.com" in url

    def resolve(self, url: str) -> list:
        """Resolve a PixelDrain file or list URL into downloadable items."""
        from .base import ResolvedItem

        list_match = _LIST_RE.search(url)
        if list_match:
            return self._resolve_list(list_match.group(1), ResolvedItem)

        file_match = _FILE_RE.search(url)
        if file_match:
            item = self._resolve_file(file_match.group(1), ResolvedItem)
            return [item] if item else []

        return []

    def _resolve_file(self, file_id: str, item_cls: type) -> object | None:
        """Resolve a single file id to a ResolvedItem via its info endpoint."""
        try:
            response = http_client.get(f"{_API}/file/{file_id}/info", timeout=_TIMEOUT)
            response.raise_for_status()
            info = response.json()
        except (*http_client.RequestError, ValueError):
            return None

        name = info.get("name") or f"{file_id}.bin"
        size = int(info.get("size", -1))
        return item_cls(
            download_url=f"{_API}/file/{file_id}?download",
            filename=name,
            size=size,
        )

    def _resolve_list(self, list_id: str, item_cls: type) -> list:
        """Resolve a list/album id to all of its files."""
        try:
            response = http_client.get(f"{_API}/list/{list_id}", timeout=_TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except (*http_client.RequestError, ValueError):
            return []

        items = []
        for entry in data.get("files", []):
            file_id = entry.get("id")
            if not file_id:
                continue
            items.append(item_cls(
                download_url=f"{_API}/file/{file_id}?download",
                filename=entry.get("name") or f"{file_id}.bin",
                size=int(entry.get("size", -1)),
            ))
        return items
