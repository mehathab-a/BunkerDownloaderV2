"""Tier A adapter: e621 JSON API."""

from __future__ import annotations

from typing import Any

import requests

from src.search.adapters.base import filter_provider_params, normalized_response
from src.search.schema import DEFAULT_TIMEOUT, SearchRequest


def search_e621(request: SearchRequest) -> dict[str, Any]:
    """Search e621 posts by tag query."""
    provider_params = filter_provider_params("e621", request.provider_params)
    params: dict[str, Any] = {
        "tags": request.query,
        "limit": request.page_size,
        "page": str(request.page),
    }
    if provider_params:
        params.update(provider_params)

    response = requests.get(
        "https://e621.net/posts.json",
        params=params,
        headers={"User-Agent": "BunkrDownloaderSearch/1.0 (public research use)"},
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    posts = response.json().get("posts", [])

    items = []
    for post in posts:
        file_info = post.get("file") or {}
        preview = post.get("preview") or {}
        tags = post.get("tags") or {}
        general_tags = tags.get("general", [])
        title = " ".join(general_tags[:8]) if general_tags else str(post.get("id"))
        items.append({
            "provider_id": str(post.get("id")),
            "title": title,
            "url": file_info.get("url"),
            "thumbnail_url": preview.get("url"),
            "media_type": file_info.get("ext", "image"),
            "author": post.get("uploader_id"),
            "created_at": post.get("created_at"),
            "tags": general_tags,
            "score": (post.get("score") or {}).get("total"),
            "nsfw": post.get("rating", "unknown"),
            "provider_fields": post,
        })

    return normalized_response(
        request,
        provider="e621",
        tier="A",
        host="e621.net",
        items=items,
        has_more=len(items) >= request.page_size,
        provider_meta={"endpoint": "https://e621.net/posts.json", "search_tier": "A"},
    )
