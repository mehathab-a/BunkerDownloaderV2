"""Tier A adapter: turbo.cr official library search (HTML scrape)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.search.adapters.base import filter_provider_params, normalized_response
from src.search.schema import DEFAULT_TIMEOUT, SearchRequest

_ENDPOINT = "https://turbo.cr/library"
_BASE_URL = "https://turbo.cr"
_HOST = "turbo.cr"


def search_turbo_library(request: SearchRequest) -> dict[str, Any]:
    """Query the turbo.cr public album library."""
    provider_params = filter_provider_params("turbo_library", request.provider_params)
    params: dict[str, str | int] = {
        "q": request.query,
        "page": request.page,
        "view": provider_params.get("view", request.sort or "popular"),
    }
    if provider_params:
        params.update(provider_params)

    response = requests.get(
        _ENDPOINT,
        params=params,
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": "BunkrDownloader/1.0"},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in soup.select("a.album-row[href]"):
        href = row.get("href", "").strip()
        if "/a/" not in href:
            continue

        album_id = href.rstrip("/").split("/")[-1]
        if album_id in seen_ids:
            continue
        seen_ids.add(album_id)

        album_url = urljoin(_BASE_URL, href)
        title_el = row.select_one(".min-w-0.flex-1 .truncate")
        created_el = row.select_one(".min-w-0.flex-1 .text-xs")
        file_match = re.search(r"(\d+)\s+files?", row.get_text(" ", strip=True), re.I)
        file_count = int(file_match.group(1)) if file_match else None

        items.append({
            "provider_id": album_id,
            "title": title_el.get_text(" ", strip=True) if title_el else album_id,
            "url": album_url,
            "thumbnail_url": None,
            "media_type": "album",
            "author": None,
            "created_at": created_el.get_text(" ", strip=True) if created_el else None,
            "tags": [],
            "score": None,
            "nsfw": "unknown",
            "file_count": file_count,
            "provider_fields": {
                "file_count": file_count,
                "params": params,
            },
        })

    page_text = soup.get_text(" ", strip=True)
    page_match = re.search(
        r"Page\s+(\d+)\s+of\s+(\d+)",
        page_text,
        flags=re.I,
    )
    total_pages = int(page_match.group(2)) if page_match else None
    has_more = bool(total_pages and request.page < total_pages)

    return normalized_response(
        request,
        provider="turbo_library",
        tier="A",
        host=_HOST,
        items=items,
        has_more=has_more,
        total=total_pages,
        warnings=["html_scrape_official_library"],
        provider_meta={"endpoint": _ENDPOINT, "search_tier": "A"},
    )
