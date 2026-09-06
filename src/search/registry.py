"""Search adapter registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.search.adapters import balbums, e621, gelbooru, licensed, tier_c, turbo
from src.search.schema import PROVIDER_TIERS, SUPPORTED_PROVIDERS, SearchRequest, TIER_C_HOSTS

SearchHandler = Callable[[SearchRequest], dict[str, Any]]

SEARCH_HANDLERS: dict[str, SearchHandler] = {
    "balbums": balbums.search_balbums,
    "turbo_library": turbo.search_turbo_library,
    "turbo": turbo.search_turbo_library,
    "gelbooru": gelbooru.search_gelbooru,
    "e621": e621.search_e621,
    "unsplash": licensed.search_unsplash,
    "pexels": licensed.search_pexels,
    "pixabay": licensed.search_pixabay,
    "flickr": licensed.search_flickr,
    "tenor": licensed.search_tenor,
    **tier_c.TIER_C_HANDLERS,
}


def supported_providers(*, include_tier_c: bool = False) -> tuple[str, ...]:
    """Return searchable provider ids."""
    if include_tier_c:
        return SUPPORTED_PROVIDERS + TIER_C_HOSTS
    return SUPPORTED_PROVIDERS


def provider_tier(provider: str) -> str:
    """Return the search tier for a provider."""
    return PROVIDER_TIERS.get(provider, "C")


def get_handler(provider: str) -> SearchHandler:
    """Look up a provider search handler."""
    handler = SEARCH_HANDLERS.get(provider)
    if handler is None:
        supported = ", ".join(supported_providers(include_tier_c=True))
        msg = f"Unsupported provider '{provider}'. Supported providers: {supported}"
        raise ValueError(msg)
    return handler
