"""Unit tests for search adapters and orchestration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.search.adapters.base import matches_exact, normalized_response
from src.search.adapters.balbums import search_balbums
from src.search.adapters.turbo import search_turbo_library
from src.search.adapters.tier_c import search_tier_c_host
from src.search.cache import clear as clear_search_cache
from src.search.orchestrator import search, search_all
from src.search.registry import get_handler, provider_tier, supported_providers
from src.search.schema import SearchRequest, parse_provider_params


SAMPLE_BALBUMS_HTML = """
<html><body>
<a class="card" href="https://bunkr.si/a/ABC123">
  <img class="thumb-img" src="https://cdn.example/thumb.jpg">
  <h3>My Album Title</h3>
  12 files
</a>
Page 2 of 5
</body></html>
"""

SAMPLE_TURBO_HTML = """
<html><body>
<div>Showing 15 albums • Page 2 of 8</div>
<a href="/a/ABC123xyz" class="album-row group flex w-full items-center gap-4 px-5 py-4 text-left">
  <div class="min-w-0 flex-1">
    <div class="truncate text-sm font-semibold text-white">Turbo Album Title</div>
    <div class="mt-0.5 text-xs text-white/50">3 days ago</div>
  </div>
  42 files
</a>
<a href="/a/ABC123xyz" class="album-card group relative overflow-hidden rounded-3xl">
  <div class="truncate text-sm font-semibold">duplicate card</div>
</a>
Page 2 of 8
</body></html>
"""


def setup_function() -> None:
    clear_search_cache()


def test_supported_providers() -> None:
    assert "balbums" in supported_providers()
    assert "turbo_library" in supported_providers()
    assert "bunkr" not in supported_providers()
    assert "bunkr" in supported_providers(include_tier_c=True)


def test_provider_tiers() -> None:
    assert provider_tier("balbums") == "B"
    assert provider_tier("turbo_library") == "A"
    assert provider_tier("e621") == "A"
    assert provider_tier("gofile") == "C"


def test_parse_provider_params() -> None:
    assert parse_provider_params(["mode=fuzzy", "sort=latest"]) == {
        "mode": "fuzzy",
        "sort": "latest",
    }


def test_matches_exact_phrase() -> None:
    item = {"title": "hello world", "tags": []}
    assert matches_exact(item, "hello world", "phrase", ("title",))


def test_balbums_parser() -> None:
    fake = MagicMock()
    fake.raise_for_status = MagicMock()
    fake.text = SAMPLE_BALBUMS_HTML
    request = SearchRequest(provider="balbums", query="test", page=2, page_size=20)
    with patch("src.search.adapters.balbums.requests.get", return_value=fake):
        payload = search_balbums(request)

    assert payload["provider"] == "balbums"
    assert payload["warnings"] == ["html_scrape_no_official_api"]
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["title"] == "My Album Title"
    assert item["url"] == "https://bunkr.si/a/ABC123"
    assert item["file_count"] == 12
    assert item["host"] == "balbums.st"
    assert item["search_tier"] == "B"
    assert payload["pagination"]["has_more"] is True


def test_turbo_parser() -> None:
    fake = MagicMock()
    fake.raise_for_status = MagicMock()
    fake.text = SAMPLE_TURBO_HTML
    request = SearchRequest(
        provider="turbo_library",
        query="test",
        page=2,
        page_size=5,
        provider_params={"view": "popular"},
    )
    with patch("src.search.adapters.turbo.requests.get", return_value=fake) as get_mock:
        payload = search_turbo_library(request)

    get_mock.assert_called_once()
    call_kwargs = get_mock.call_args
    assert call_kwargs[0][0] == "https://turbo.cr/library"
    assert call_kwargs[1]["params"]["q"] == "test"
    assert call_kwargs[1]["params"]["page"] == 2
    assert call_kwargs[1]["params"]["view"] == "popular"

    assert payload["provider"] == "turbo_library"
    assert payload["warnings"] == ["html_scrape_official_library"]
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["title"] == "Turbo Album Title"
    assert item["url"] == "https://turbo.cr/a/ABC123xyz"
    assert item["file_count"] == 42
    assert item["host"] == "turbo.cr"
    assert item["search_tier"] == "A"
    assert item["created_at"] == "3 days ago"
    assert payload["pagination"]["has_more"] is True


def test_turbo_alias_resolves() -> None:
    from src.search.schema import normalize_provider_name

    assert normalize_provider_name("turbo") == "turbo_library"
    handler = get_handler("turbo")
    request = SearchRequest(provider="turbo", query="x")
    with patch(
        "src.search.adapters.turbo.requests.get",
        return_value=MagicMock(raise_for_status=MagicMock(), text="<html></html>"),
    ):
        payload = handler(request)
    assert payload["provider"] == "turbo_library"


def test_tier_c_degrades_gracefully() -> None:
    request = SearchRequest(provider="gofile", query="anything")
    payload = search_tier_c_host(request, host="gofile")
    assert payload["items"] == []
    assert any("keyword search not supported" in warning for warning in payload["warnings"])


def test_tier_c_handler_registered() -> None:
    handler = get_handler("pixeldrain")
    request = SearchRequest(provider="pixeldrain", query="x")
    payload = handler(request)
    assert payload["provider"] == "pixeldrain"
    assert payload["items"] == []


def test_search_all_parallel_partial_failure() -> None:
    request = SearchRequest(provider="all", query="cat", page_size=5, use_cache=False)

    def fake_search(req: SearchRequest):
        if req.provider == "balbums":
            return normalized_response(
                req,
                provider="balbums",
                tier="B",
                host="balbums.st",
                items=[{
                    "provider_id": "1",
                    "title": "cat album",
                    "url": "https://bunkr.si/a/1",
                    "thumbnail_url": None,
                    "media_type": "album",
                    "author": None,
                    "created_at": None,
                    "tags": [],
                    "score": None,
                    "nsfw": "unknown",
                    "provider_fields": {},
                }],
            )
        raise ValueError("missing API key")

    with patch("src.search.orchestrator._search_uncached", side_effect=fake_search):
        payload = search_all(request, max_workers=4)

    assert payload["provider"] == "all"
    assert len(payload["results"]) == 1
    assert payload["results"][0]["provider"] == "balbums"
    assert len(payload["errors"]) == len(supported_providers()) - 1
    assert payload["meta"]["providers_succeeded"] == 1


def test_search_uses_cache() -> None:
    request = SearchRequest(provider="gofile", query="x", use_cache=True)
    with patch(
        "src.search.orchestrator._search_uncached",
        return_value={"provider": "gofile", "items": []},
    ) as uncached:
        first = search(request)
        second = search(request)

    assert uncached.call_count == 1
    assert second.get("provider_meta", {}).get("cache_hit") is True
