"""Per-provider request throttling for search adapters."""

from __future__ import annotations

import threading
import time

# Minimum seconds between consecutive requests to each provider.
PROVIDER_MIN_INTERVAL_S: dict[str, float] = {
    "balbums": 1.0,
    "turbo_library": 1.0,
    "gelbooru": 1.0,
    "e621": 0.5,
    "unsplash": 0.1,
    "pexels": 0.1,
    "pixabay": 0.1,
    "flickr": 0.2,
    "tenor": 0.1,
}

_last_request: dict[str, float] = {}
_lock = threading.Lock()


def throttle(provider: str) -> None:
    """Block until the provider's minimum interval has elapsed."""
    interval = PROVIDER_MIN_INTERVAL_S.get(provider, 0.5)
    with _lock:
        now = time.monotonic()
        last = _last_request.get(provider, 0.0)
        wait = interval - (now - last)
        if wait > 0:
            time.sleep(wait)
        _last_request[provider] = time.monotonic()
