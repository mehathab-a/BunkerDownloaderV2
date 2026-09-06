"""Tier B adapter: balbums.st HTML index search (no public API)."""

from __future__ import annotations

import re
from typing import Any

import requests
from bs4 import BeautifulSoup

from src.search.adapters.base import filter_provider_params, normalized_response
from src.search.schema import DEFAULT_TIMEOUT, SearchRequest


def search_balbums(request: SearchRequest) -> dict[str, Any]:
    """Query the balalbums.st HTML search index."""
    provider_params = filter_provider_params("balbums", request.provider_params)
    params = {
        "search": request.query,
        "page": request.page,
        "per": provider_params.get("per", request.page_size),
        "mode": provider_params.get("mode", "fuzzy"),
        "sort": provider_params.get("sort", request.sort or "latest"),
    }
    if provider_params:
        params.update(provider_params)

    response = requests.get(
        "https://balbums.st/",
        params=params,
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    cards = soup.select("a.card[href]")
    items: list[dict[str, Any]] = []
    for card in cards:
        album_url = card.get("href", "").strip()
        if "/a/" not in album_url:
            continue

        title = card.select_one("h3")
        thumb = card.select_one("img.thumb-img")
        file_match = re.search(r"(\d+)\s+files", card.get_text(" ", strip=True), re.I)
        file_count = int(file_match.group(1)) if file_match else None

        items.append({
            "provider_id": album_url.rstrip("/").split("/")[-1],
            "title": title.get_text(" ", strip=True) if title else album_url,
            "url": album_url,
            "thumbnail_url": thumb.get("src", "").strip() if thumb else None,
            "media_type": "album",
            "author": None,
            "created_at": None,
            "tags": [],
            "score": None,
            "nsfw": "unknown",
            "file_count": file_count,
            "provider_fields": {
                "file_count": file_count,
                "params": params,
            },
        })

    page_match = re.search(
        r"Page\s+(\d+)\s+of\s+(\d+)",
        soup.get_text(" ", strip=True),
        flags=re.I,
    )
    total_pages = int(page_match.group(2)) if page_match else None
    has_more = bool(total_pages and request.page < total_pages)

    return normalized_response(
        request,
        provider="balbums",
        tier="B",
        host="balbums.st",
        items=items,
        has_more=has_more,
        total=total_pages,
        warnings=["html_scrape_no_official_api"],
        provider_meta={"endpoint": "https://balbums.st/", "search_tier": "B"},
    )
