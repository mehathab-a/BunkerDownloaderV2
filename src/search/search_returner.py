"""Provider-based search returner with normalized output.

Backward-compatible facade over the modular adapter/orchestrator package.
"""

from __future__ import annotations

from src.search.orchestrator import search, search_all
from src.search.registry import supported_providers
from src.search.schema import SearchRequest, parse_provider_params

__all__ = [
    "SearchRequest",
    "parse_provider_params",
    "search",
    "search_all",
    "supported_providers",
]
