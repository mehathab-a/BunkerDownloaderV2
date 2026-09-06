"""Tier A adapter: Gelbooru JSON API."""

from __future__ import annotations

from typing import Any

import requests

from src.search.adapters.base import filter_provider_params, normalized_response
from src.search.schema import DEFAULT_TIMEOUT, SearchRequest


def search_gelbooru(request: SearchRequest) -> dict[str, Any]:
    """Search Gelbooru via the dapi JSON endpoint."""
    provider_params = filter_provider_params("gelbooru", request.provider_params)
    params: dict[str, Any] = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "json": 1,
        "tags": request.query,
        "pid": max(request.page - 1, 0),
        "limit": request.page_size,
    }
    if provider_params:
        params.update(provider_params)

    response = requests.get(
        "https://gelbooru.com/index.php",
        params=params,
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    posts = data if isinstance(data, list) else data.get("post", [])

    items = [{
        "provider_id": str(post.get("id")),
        "title": post.get("title") or post.get("tags", ""),
        "url": post.get("file_url") or post.get("source"),
        "thumbnail_url": post.get("preview_url"),
        "media_type": "image",
        "author": post.get("owner"),
        "created_at": None,
        "tags": str(post.get("tags", "")).split(),
        "score": post.get("score"),
        "nsfw": post.get("rating", "unknown"),
        "provider_fields": post,
    } for post in posts if post.get("file_url") or post.get("source")]

    return normalized_response(
        request,
        provider="gelbooru",
        tier="A",
        host="gelbooru.com",
        items=items,
        has_more=len(items) >= request.page_size,
        provider_meta={"endpoint": "https://gelbooru.com/index.php", "search_tier": "A"},
    )
