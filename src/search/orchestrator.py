"""Parallel search orchestration with caching and rate limits."""

from __future__ import annotations

import copy
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from src.search import cache as search_cache
from src.search.rate_limits import throttle
from src.search.registry import SUPPORTED_PROVIDERS, get_handler
from src.search.schema import SearchRequest, normalize_provider_name


def _request_cache_payload(request: SearchRequest) -> dict[str, Any]:
    return {
        "query": request.query,
        "page": request.page,
        "page_size": request.page_size,
        "sort": request.sort,
        "exact_mode": request.exact_mode,
        "exact_fields": list(request.exact_fields),
        "provider_params": request.provider_params or {},
    }


def _search_uncached(request: SearchRequest) -> dict[str, Any]:
    provider = normalize_provider_name(request.provider)
    throttle(provider)
    handler = get_handler(provider)
    provider_request = SearchRequest(
        provider=provider,
        query=request.query,
        page=request.page,
        page_size=request.page_size,
        sort=request.sort,
        exact_mode=request.exact_mode,
        exact_fields=request.exact_fields,
        provider_params=request.provider_params,
        timeout_s=request.timeout_s,
        use_cache=False,
    )
    return handler(provider_request)


def search(request: SearchRequest) -> dict[str, Any]:
    """Search one provider and return a normalized response."""
    provider = normalize_provider_name(request.provider)
    get_handler(provider)

    cache_payload = _request_cache_payload(request)
    if request.use_cache:
        cached = search_cache.get(provider, cache_payload)
        if cached is not None:
            result = copy.deepcopy(cached)
            meta = dict(result.get("provider_meta") or {})
            meta["cache_hit"] = True
            result["provider_meta"] = meta
            return result

    result = _search_uncached(request)
    if request.use_cache:
        search_cache.put(provider, cache_payload, result)
    return result


def _providers_for_fanout(request: SearchRequest) -> tuple[str, ...]:
    if request.providers_filter:
        return tuple(normalize_provider_name(name) for name in request.providers_filter)
    return SUPPORTED_PROVIDERS


def search_all(request: SearchRequest, *, max_workers: int = 8) -> dict[str, Any]:
    """Search providers in parallel, returning per-provider responses and errors."""
    started = time.monotonic()
    providers = _providers_for_fanout(request)
    responses: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    def _run(provider: str) -> dict[str, Any]:
        provider_request = SearchRequest(
            provider=provider,
            query=request.query,
            page=request.page,
            page_size=request.page_size,
            sort=request.sort,
            exact_mode=request.exact_mode,
            exact_fields=request.exact_fields,
            provider_params=request.provider_params,
            timeout_s=request.timeout_s,
            use_cache=request.use_cache,
        )
        return search(provider_request)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(_run, provider): provider for provider in providers}
        for future in as_completed(future_map, timeout=request.timeout_s):
            provider = future_map[future]
            try:
                responses.append(future.result())
            except Exception as err:
                errors.append({"provider": provider, "error": str(err)})

    responses.sort(key=lambda payload: str(payload.get("provider", "")))

    return {
        "provider": "all",
        "request_echo": {
            "query": request.query,
            "page": request.page,
            "page_size": request.page_size,
            "sort": request.sort,
            "exact_mode": request.exact_mode,
            "exact_fields": list(request.exact_fields),
            "provider_params": request.provider_params or {},
            "providers_filter": list(providers),
        },
        "results": responses,
        "errors": errors,
        "meta": {
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "providers_queried": len(providers),
            "providers_succeeded": len(responses),
            "providers_failed": len(errors),
        },
    }
