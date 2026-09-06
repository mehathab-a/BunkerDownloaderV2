"""GoFile resolver.

GoFile requires a short handshake before content can be listed/downloaded:
    1. Create a guest account:  POST https://api.gofile.io/accounts  -> data.token
    2. Discover the website token (``wt``) from the site's global JS bundle.
    3. List folder contents:    GET https://api.gofile.io/contents/<code>?wt=<wt>
                                (Authorization: Bearer <token>)
    4. Each file entry exposes a direct ``link``; downloads must send the guest token
       as an ``accountToken`` cookie.

The website token and API shapes change periodically, so resolution is best-effort and
fails gracefully (returning an empty list) rather than raising.
"""

from __future__ import annotations

import re

from src.misc import http_client

_API = "https://api.gofile.io"
_GLOBAL_JS = "https://gofile.io/dist/js/global.js"
_CODE_RE = re.compile(r"gofile\.io/d/([A-Za-z0-9]+)")
_WT_RE = re.compile(r'wt\s*[:=]\s*["\']([A-Za-z0-9]+)["\']')
_TIMEOUT = (10, 30)


class GofileResolver:
    """Resolve GoFile folder/download URLs."""

    name = "gofile"

    def matches(self, url: str) -> bool:
        """Return True for GoFile download URLs."""
        return "gofile.io/d/" in url

    def resolve(self, url: str) -> list:
        """Resolve a GoFile folder URL into downloadable items."""
        from .base import ResolvedItem

        code_match = _CODE_RE.search(url)
        if not code_match:
            return []
        code = code_match.group(1)

        token = self._create_guest_token()
        if not token:
            return []

        website_token = self._discover_website_token()
        if not website_token:
            return []

        contents = self._fetch_contents(code, token, website_token)
        if not contents:
            return []

        cookie = f"accountToken={token}"
        items = []
        for entry in contents.values():
            if entry.get("type") != "file":
                continue
            link = entry.get("link")
            if not link:
                continue
            items.append(ResolvedItem(
                download_url=link,
                filename=entry.get("name") or "gofile.bin",
                headers={"Cookie": cookie, "Referer": "https://gofile.io/"},
                size=int(entry.get("size", -1)),
            ))
        return items

    def _create_guest_token(self) -> str | None:
        try:
            response = http_client.post(f"{_API}/accounts", timeout=_TIMEOUT)
            response.raise_for_status()
            return (response.json().get("data") or {}).get("token")
        except (*http_client.RequestError, ValueError):
            return None

    def _discover_website_token(self) -> str | None:
        try:
            response = http_client.get(_GLOBAL_JS, timeout=_TIMEOUT)
            response.raise_for_status()
            match = _WT_RE.search(response.text)
            return match.group(1) if match else None
        except (*http_client.RequestError, ValueError):
            return None

    def _fetch_contents(self, code: str, token: str, website_token: str) -> dict | None:
        try:
            response = http_client.get(
                f"{_API}/contents/{code}",
                params={"wt": website_token},
                headers={"Authorization": f"Bearer {token}"},
                timeout=_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json().get("data") or {}
            return data.get("children") or data.get("contents") or {}
        except (*http_client.RequestError, ValueError):
            return None
