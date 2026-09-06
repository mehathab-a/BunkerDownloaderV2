"""Search request schema and provider configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SearchTier = Literal["A", "B", "C"]

SUPPORTED_PROVIDERS: tuple[str, ...] = (
    "balbums",
    "turbo_library",
    "gelbooru",
    "e621",
    "unsplash",
    "pexels",
    "pixabay",
    "flickr",
    "tenor",
)

_PROVIDER_ALIASES: dict[str, str] = {
    "turbo": "turbo_library",
}

# Backward-compatible alias used by the CLI and docs.
SUPPORTED_PROVIDERS_LEGACY = SUPPORTED_PROVIDERS

PROVIDER_PARAM_ALLOWLIST: dict[str, frozenset[str]] = {
    "balbums": frozenset({"search", "page", "per", "mode", "sort"}),
    "turbo_library": frozenset({"q", "page", "view"}),
    "gelbooru": frozenset({"page", "s", "q", "json", "tags", "pid", "limit", "id", "cid"}),
    "e621": frozenset({"tags", "limit", "page"}),
    "unsplash": frozenset({
        "query", "page", "per_page", "order_by", "collections", "content_filter",
        "color", "orientation", "lang",
    }),
    "pexels": frozenset({"query", "page", "per_page", "orientation", "size", "color", "locale"}),
    "pixabay": frozenset({
        "q", "page", "per_page", "order", "safesearch", "category", "image_type",
        "colors", "min_width", "min_height",
    }),
    "flickr": frozenset({
        "method", "text", "tags", "tag_mode", "sort", "license", "safe_search",
        "content_type", "media", "page", "per_page", "min_upload_date", "max_upload_date",
    }),
    "tenor": frozenset({
        "q", "limit", "pos", "contentfilter", "media_filter", "searchfilter", "country",
        "locale", "ar_range", "random", "client_key",
    }),
}

PROVIDER_TIERS: dict[str, SearchTier] = {
    "balbums": "B",
    "turbo_library": "A",
    "gelbooru": "A",
    "e621": "A",
    "unsplash": "A",
    "pexels": "A",
    "pixabay": "A",
    "flickr": "A",
    "tenor": "A",
}

# Tier C hosts resolved by fetch.py — keyword search is not supported.
TIER_C_HOSTS: tuple[str, ...] = ("bunkr", "pixeldrain", "gofile", "cyberdrop", "saint")

DEFAULT_TIMEOUT: tuple[float, float] = (10, 30)


@dataclass(frozen=True, slots=True)
class SearchRequest:
    """Common normalized search request."""

    provider: str
    query: str
    page: int = 1
    page_size: int = 20
    sort: str | None = None
    exact_mode: str = "none"
    exact_fields: tuple[str, ...] = ("title", "tags")
    provider_params: dict[str, str] | None = None
    timeout_s: float = 30.0
    providers_filter: tuple[str, ...] | None = None
    use_cache: bool = True


def parse_provider_params(raw_pairs: list[str] | None) -> dict[str, str]:
    """Parse repeated KEY=VALUE arguments into a dictionary."""
    params: dict[str, str] = {}
    for raw_pair in raw_pairs or []:
        if "=" not in raw_pair:
            msg = f"Invalid provider param '{raw_pair}'. Use KEY=VALUE."
            raise ValueError(msg)
        key, value = raw_pair.split("=", maxsplit=1)
        key = key.strip()
        if not key:
            raise ValueError("Provider param key cannot be empty.")
        params[key] = value
    return params


def normalize_provider_name(name: str) -> str:
    """Map legacy provider aliases to canonical adapter ids."""
    normalized = name.lower().strip()
    return _PROVIDER_ALIASES.get(normalized, normalized)
