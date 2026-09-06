"""Host resolver registry and dispatch helpers."""

from __future__ import annotations

from urllib.parse import urlparse

from .base import HostResolver, ResolvedItem
from .cyberdrop import CyberdropResolver
from .gofile import GofileResolver
from .pixeldrain import PixeldrainResolver
from .saint import SaintResolver

# Order matters only for overlapping matches; keep most-specific first.
_RESOLVERS: list[HostResolver] = [
    PixeldrainResolver(),
    GofileResolver(),
    CyberdropResolver(),
    SaintResolver(),
]


def supported_hosts() -> list[str]:
    """Return the registered host resolver names."""
    return [resolver.name for resolver in _RESOLVERS]


def get_resolver(url: str) -> HostResolver | None:
    """Return the first resolver that matches the URL, or None."""
    for resolver in _RESOLVERS:
        if resolver.matches(url):
            return resolver
    return None


def resolve_url(url: str) -> tuple[str, list[ResolvedItem]]:
    """Resolve a URL into (host_name, items). Raises ValueError if unsupported."""
    resolver = get_resolver(url)
    if resolver is None:
        host = urlparse(url).netloc or url
        supported = ", ".join(supported_hosts())
        msg = (
            f"Unsupported host for URL: {url} ({host}). "
            f"Supported multi-host resolvers: {supported}. "
            "Use downloader.py for Bunkr URLs."
        )
        raise ValueError(msg)

    items = resolver.resolve(url)
    return resolver.name, items
