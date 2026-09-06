"""Tier A adapters for licensed stock/media APIs."""

from __future__ import annotations

from typing import Any

import requests

from src.search.adapters.base import filter_provider_params, get_api_key, normalized_response
from src.search.schema import DEFAULT_TIMEOUT, SearchRequest


def search_unsplash(request: SearchRequest) -> dict[str, Any]:
    """Search Unsplash photos."""
    access_key = get_api_key("UNSPLASH_ACCESS_KEY", "unsplash")
    provider_params = filter_provider_params("unsplash", request.provider_params)
    params: dict[str, Any] = {
        "query": request.query,
        "page": request.page,
        "per_page": request.page_size,
    }
    if request.sort:
        params["order_by"] = request.sort
    if provider_params:
        params.update(provider_params)

    response = requests.get(
        "https://api.unsplash.com/search/photos",
        params=params,
        headers={"Authorization": f"Client-ID {access_key}"},
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    results = data.get("results", [])

    items = [{
        "provider_id": photo.get("id"),
        "title": photo.get("description") or photo.get("alt_description") or photo.get("id"),
        "url": (photo.get("urls") or {}).get("full"),
        "thumbnail_url": (photo.get("urls") or {}).get("thumb"),
        "media_type": "image",
        "author": ((photo.get("user") or {}).get("name")),
        "created_at": photo.get("created_at"),
        "tags": [tag.get("title", "") for tag in photo.get("tags", [])],
        "score": None,
        "nsfw": "unknown",
        "provider_fields": photo,
    } for photo in results]

    return normalized_response(
        request,
        provider="unsplash",
        tier="A",
        host="unsplash.com",
        items=items,
        total=data.get("total_pages"),
        has_more=request.page < (data.get("total_pages") or request.page),
        provider_meta={"endpoint": "https://api.unsplash.com/search/photos", "search_tier": "A"},
    )


def search_pexels(request: SearchRequest) -> dict[str, Any]:
    """Search Pexels photos."""
    api_key = get_api_key("PEXELS_API_KEY", "pexels")
    provider_params = filter_provider_params("pexels", request.provider_params)
    params: dict[str, Any] = {
        "query": request.query,
        "page": request.page,
        "per_page": request.page_size,
    }
    if provider_params:
        params.update(provider_params)

    response = requests.get(
        "https://api.pexels.com/v1/search",
        params=params,
        headers={"Authorization": api_key},
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    photos = data.get("photos", [])

    items = [{
        "provider_id": str(photo.get("id")),
        "title": photo.get("alt") or str(photo.get("id")),
        "url": photo.get("url"),
        "thumbnail_url": (photo.get("src") or {}).get("medium"),
        "media_type": "image",
        "author": photo.get("photographer"),
        "created_at": None,
        "tags": [],
        "score": None,
        "nsfw": "unknown",
        "provider_fields": photo,
    } for photo in photos]

    return normalized_response(
        request,
        provider="pexels",
        tier="A",
        host="pexels.com",
        items=items,
        next_cursor=data.get("next_page"),
        has_more=bool(data.get("next_page")),
        provider_meta={"endpoint": "https://api.pexels.com/v1/search", "search_tier": "A"},
    )


def search_pixabay(request: SearchRequest) -> dict[str, Any]:
    """Search Pixabay images."""
    api_key = get_api_key("PIXABAY_API_KEY", "pixabay")
    provider_params = filter_provider_params("pixabay", request.provider_params)
    params: dict[str, Any] = {
        "key": api_key,
        "q": request.query,
        "page": request.page,
        "per_page": request.page_size,
    }
    if provider_params:
        params.update(provider_params)

    response = requests.get(
        "https://pixabay.com/api/",
        params=params,
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    hits = data.get("hits", [])

    items = [{
        "provider_id": str(hit.get("id")),
        "title": hit.get("tags", str(hit.get("id"))),
        "url": hit.get("largeImageURL") or hit.get("webformatURL"),
        "thumbnail_url": hit.get("previewURL"),
        "media_type": "image",
        "author": hit.get("user"),
        "created_at": None,
        "tags": str(hit.get("tags", "")).split(", "),
        "score": hit.get("likes"),
        "nsfw": "unknown",
        "provider_fields": hit,
    } for hit in hits]

    total_hits = data.get("totalHits")
    has_more = bool(total_hits and request.page * request.page_size < total_hits)

    return normalized_response(
        request,
        provider="pixabay",
        tier="A",
        host="pixabay.com",
        items=items,
        total=total_hits,
        has_more=has_more,
        provider_meta={"endpoint": "https://pixabay.com/api/", "search_tier": "A"},
    )


def search_flickr(request: SearchRequest) -> dict[str, Any]:
    """Search Flickr photos."""
    api_key = get_api_key("FLICKR_API_KEY", "flickr")
    provider_params = filter_provider_params("flickr", request.provider_params)
    params: dict[str, Any] = {
        "method": "flickr.photos.search",
        "api_key": api_key,
        "format": "json",
        "nojsoncallback": 1,
        "text": request.query,
        "page": request.page,
        "per_page": request.page_size,
    }
    if provider_params:
        params.update(provider_params)

    response = requests.get(
        "https://api.flickr.com/services/rest",
        params=params,
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    photos = (data.get("photos") or {}).get("photo", [])

    items = []
    for photo in photos:
        image_url = (
            "https://farm{farm}.staticflickr.com/{server}/{id}_{secret}.jpg".format(
                farm=photo.get("farm"),
                server=photo.get("server"),
                id=photo.get("id"),
                secret=photo.get("secret"),
            )
        )
        items.append({
            "provider_id": photo.get("id"),
            "title": photo.get("title") or photo.get("id"),
            "url": image_url,
            "thumbnail_url": image_url,
            "media_type": "image",
            "author": photo.get("owner"),
            "created_at": None,
            "tags": [],
            "score": None,
            "nsfw": "unknown",
            "provider_fields": photo,
        })

    total_pages = int((data.get("photos") or {}).get("pages", 0))
    return normalized_response(
        request,
        provider="flickr",
        tier="A",
        host="flickr.com",
        items=items,
        total=total_pages,
        has_more=request.page < total_pages,
        provider_meta={"endpoint": "https://api.flickr.com/services/rest", "search_tier": "A"},
    )


def search_tenor(request: SearchRequest) -> dict[str, Any]:
    """Search Tenor GIFs."""
    api_key = get_api_key("TENOR_API_KEY", "tenor")
    provider_params = filter_provider_params("tenor", request.provider_params)
    params: dict[str, Any] = {
        "q": request.query,
        "key": api_key,
        "limit": request.page_size,
    }
    if provider_params:
        params.update(provider_params)

    response = requests.get(
        "https://tenor.googleapis.com/v2/search",
        params=params,
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    results = data.get("results", [])

    items = []
    for result in results:
        media_formats = result.get("media_formats", {})
        gif = media_formats.get("gif", {})
        tinygif = media_formats.get("tinygif", {})
        items.append({
            "provider_id": result.get("id"),
            "title": result.get("content_description") or result.get("id"),
            "url": gif.get("url"),
            "thumbnail_url": tinygif.get("url"),
            "media_type": "gif",
            "author": (result.get("user") or {}).get("username"),
            "created_at": None,
            "tags": [],
            "score": None,
            "nsfw": "unknown",
            "provider_fields": result,
        })

    return normalized_response(
        request,
        provider="tenor",
        tier="A",
        host="tenor.com",
        items=items,
        next_cursor=data.get("next"),
        has_more=bool(data.get("next")),
        provider_meta={"endpoint": "https://tenor.googleapis.com/v2/search", "search_tier": "A"},
    )
