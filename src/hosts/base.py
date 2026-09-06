"""Host-resolver abstraction for multi-host downloading.

Each resolver knows how to recognize a host's URLs and turn an album/file page into a
list of directly downloadable items. The heavy lifting of the actual transfer (chunked
parallel download, resume, retries, integrity checks) is shared and host-agnostic, so a
resolver only has to produce ``ResolvedItem`` objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(slots=True)
class ResolvedItem:
    """A single directly-downloadable file resolved from a host URL."""

    download_url: str
    filename: str
    # Extra request headers required by the host CDN (e.g. Referer), merged over the
    # default headers at download time.
    headers: dict[str, str] = field(default_factory=dict)
    # Best-effort known size in bytes (-1 when unknown); purely informational.
    size: int = -1


@runtime_checkable
class HostResolver(Protocol):
    """Protocol implemented by every host resolver."""

    name: str

    def matches(self, url: str) -> bool:
        """Return True when this resolver can handle the given URL."""
        ...

    def resolve(self, url: str) -> list[ResolvedItem]:
        """Resolve an album/file URL into a list of downloadable items."""
        ...
