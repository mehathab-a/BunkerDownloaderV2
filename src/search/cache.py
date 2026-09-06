"""In-memory TTL cache for search responses."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any

_DEFAULT_TTL_S = 600.0

_store: dict[str, tuple[float, dict[str, Any]]] = {}
_lock = threading.Lock()


def _cache_key(provider: str, request_payload: dict[str, Any]) -> str:
    raw = json.dumps({"provider": provider, **request_payload}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def get(provider: str, request_payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return a cached response if present and not expired."""
    key = _cache_key(provider, request_payload)
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        expires_at, payload = entry
        if time.monotonic() > expires_at:
            del _store[key]
            return None
        return payload


def put(
    provider: str,
    request_payload: dict[str, Any],
    payload: dict[str, Any],
    *,
    ttl_s: float = _DEFAULT_TTL_S,
) -> None:
    """Store a response payload."""
    key = _cache_key(provider, request_payload)
    with _lock:
        _store[key] = (time.monotonic() + ttl_s, payload)


def clear() -> None:
    """Drop all cached entries (mainly for tests)."""
    with _lock:
        _store.clear()
