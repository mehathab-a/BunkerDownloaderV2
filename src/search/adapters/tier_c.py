"""Tier C stubs: URL-only hosts with no keyword search."""

from __future__ import annotations

from typing import Any

from src.search.adapters.base import normalized_response
from src.search.schema import SearchRequest, TIER_C_HOSTS


def search_tier_c_host(request: SearchRequest, *, host: str) -> dict[str, Any]:
    """Return an empty result with a clear degradation warning."""
    return normalized_response(
        request,
        provider=host,
        tier="C",
        host=host,
        items=[],
        has_more=False,
        warnings=[
            f"{host}: keyword search not supported; pass a direct URL to fetch.py or downloader.py",
        ],
        provider_meta={"search_tier": "C", "url_only": True},
    )


TIER_C_HANDLERS = {
    host: (lambda request, host=host: search_tier_c_host(request, host=host))
    for host in TIER_C_HOSTS
}
