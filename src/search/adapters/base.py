"""Shared helpers for search adapters."""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse

from src.search.schema import (
    PROVIDER_PARAM_ALLOWLIST,
    SearchRequest,
    SearchTier,
)


def filter_provider_params(provider: str, raw_params: dict[str, str] | None) -> dict[str, str]:
    """Filter provider params using a provider-specific allowlist."""
    if not raw_params:
        return {}

    allowed = PROVIDER_PARAM_ALLOWLIST.get(provider)
    if not allowed:
        return dict(raw_params)

    return {key: value for key, value in raw_params.items() if key in allowed}


def tokenize(value: str) -> list[str]:
    """Split text into lowercase alphanumeric tokens."""
    return re.findall(r"[a-z0-9]+", value.lower())


def matches_exact(
    item: dict[str, Any],
    query: str,
    mode: str,
    fields: tuple[str, ...],
) -> bool:
    """Apply optional exact-mode filtering on normalized fields."""
    if mode == "none":
        return True

    field_values: list[str] = []
    for field in fields:
        raw_value = item.get(field)
        if isinstance(raw_value, list):
            field_values.extend(str(value) for value in raw_value)
        elif raw_value is not None:
            field_values.append(str(raw_value))

    haystack = " ".join(field_values).strip().lower()
    if not haystack:
        return False

    normalized_query = query.strip().lower()
    query_tokens = tokenize(normalized_query)
    haystack_tokens = tokenize(haystack)

    if mode == "phrase":
        return normalized_query in haystack
    if mode == "token_all":
        return all(token in haystack_tokens for token in query_tokens)
    if mode == "token_exact":
        return normalized_query == haystack

    msg = f"Unsupported exact mode: {mode}"
    raise ValueError(msg)


def get_api_key(env_key: str, provider: str) -> str:
    """Read a required API key from the environment."""
    value = os.getenv(env_key, "").strip()
    if not value:
        msg = (
            f"Missing API key for '{provider}'. "
            f"Set environment variable '{env_key}'."
        )
        raise ValueError(msg)
    return value


def host_from_url(url: str | None, *, fallback: str) -> str:
    """Extract hostname from a result URL."""
    if not url:
        return fallback
    parsed = urlparse(url)
    return parsed.netloc or fallback


def stamp_item(
    item: dict[str, Any],
    *,
    provider: str,
    tier: SearchTier,
    host: str | None = None,
) -> dict[str, Any]:
    """Attach cross-provider metadata to a normalized item."""
    item["provider"] = provider
    item["search_tier"] = tier
    item["host"] = host or host_from_url(item.get("url"), fallback=provider)
    provider_fields = item.get("provider_fields") or {}
    if "file_count" not in item and provider_fields.get("file_count") is not None:
        item["file_count"] = provider_fields["file_count"]
    return item


def normalized_response(
    request: SearchRequest,
    *,
    provider: str,
    tier: SearchTier,
    host: str,
    items: list[dict[str, Any]],
    next_cursor: str | None = None,
    total: int | None = None,
    has_more: bool | None = None,
    warnings: list[str] | None = None,
    provider_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the standard search response envelope."""
    filtered_items: list[dict[str, Any]] = []
    for raw_item in items:
        item = stamp_item(dict(raw_item), provider=provider, tier=tier, host=host)
        exact_match = matches_exact(
            item,
            request.query,
            request.exact_mode,
            request.exact_fields,
        )
        item["exact_match"] = exact_match
        if request.exact_mode == "none" or exact_match:
            filtered_items.append(item)

    limited_items = filtered_items[: request.page_size]

    if has_more is None:
        has_more = bool(next_cursor) or len(filtered_items) > len(limited_items)

    return {
        "provider": provider,
        "request_echo": {
            "query": request.query,
            "page": request.page,
            "page_size": request.page_size,
            "sort": request.sort,
            "exact_mode": request.exact_mode,
            "exact_fields": list(request.exact_fields),
            "provider_params": filter_provider_params(provider, request.provider_params),
        },
        "pagination": {
            "page": request.page,
            "page_size": request.page_size,
            "next": next_cursor,
            "has_more": has_more,
            "total": total,
        },
        "items": limited_items,
        "provider_meta": provider_meta or {},
        "warnings": warnings or [],
    }
