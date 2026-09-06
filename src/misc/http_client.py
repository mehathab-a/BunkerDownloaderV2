"""Unified HTTP client with optional curl_cffi TLS/browser impersonation.

Bunkr (and several similar hosts) gate their signing/CDN endpoints behind
TLS-fingerprint bot detection, which plain header spoofing cannot satisfy. When the
optional ``curl_cffi`` dependency is installed, requests are sent with a real browser
TLS fingerprint; otherwise the client transparently falls back to ``requests`` so the
project keeps working without the extra dependency.
"""

from __future__ import annotations

from typing import Any

import requests

try:  # Optional dependency: browser TLS impersonation.
    from curl_cffi import requests as _cffi
    from curl_cffi.requests.exceptions import (
        RequestException as _CffiRequestException,
    )

    HAS_IMPERSONATE = True
except ImportError:  # pragma: no cover - exercised only without curl_cffi.
    _cffi = None
    _CffiRequestException = ()
    HAS_IMPERSONATE = False

# Browser profile used for impersonation. "chrome" tracks a recent Chrome fingerprint.
DEFAULT_IMPERSONATE = "chrome"

# Unified exception tuple so callers can catch failures regardless of backend.
RequestError: tuple[type[BaseException], ...] = tuple(
    exc
    for exc in (requests.RequestException, _CffiRequestException)
    if isinstance(exc, type)
)


def impersonation_enabled() -> bool:
    """Return True when curl_cffi browser impersonation is available."""
    return HAS_IMPERSONATE


def request(method: str, url: str, *, impersonate: bool = True, **kwargs: Any) -> Any:
    """Perform an HTTP request, using impersonation when available.

    Falls back to ``requests`` when curl_cffi is not installed or when
    ``impersonate=False`` is passed. Returns a requests-compatible response object
    (both backends expose ``status_code``, ``headers``, ``iter_content``, ``json``,
    ``raise_for_status`` and context-manager support).
    """
    if HAS_IMPERSONATE and impersonate:
        return _cffi.request(
            method,
            url,
            impersonate=DEFAULT_IMPERSONATE,
            **kwargs,
        )
    return requests.request(method, url, **kwargs)


def get(url: str, *, impersonate: bool = True, **kwargs: Any) -> Any:
    """Perform a GET request (impersonated when available)."""
    return request("GET", url, impersonate=impersonate, **kwargs)


def head(url: str, *, impersonate: bool = True, **kwargs: Any) -> Any:
    """Perform a HEAD request (impersonated when available)."""
    return request("HEAD", url, impersonate=impersonate, **kwargs)


def post(url: str, *, impersonate: bool = True, **kwargs: Any) -> Any:
    """Perform a POST request (impersonated when available)."""
    return request("POST", url, impersonate=impersonate, **kwargs)
