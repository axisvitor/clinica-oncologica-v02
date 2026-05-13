"""
Cache header classification helpers.

Centralizes the browser-cache safety rules for HTTP responses that may contain
PHI, session state, CSRF state, token-bearing public quiz content, or other
browser-authenticated payloads. Sensitive responses are marked no-store and are
kept out of the reusable HTTP cache.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from fastapi import Request, Response

logger = logging.getLogger(__name__)

NO_STORE_CACHE_CONTROL = "no-store, no-cache, must-revalidate, private, max-age=0"

SENSITIVE_COOKIE_NAMES = frozenset(
    {
        "session",
        "sessionid",
        "session_id",
        "sessionid",
        "access_token",
        "refresh_token",
        "csrf_token",
        "csrftoken",
        "csrf",
        "xsrf-token",
        "x-csrf-token",
        "quiz_session_id",
        "quiz_session_state",
    }
)

SENSITIVE_QUERY_PARAM_NAMES = frozenset(
    {
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "session",
        "session_id",
        "sessionid",
        "quiz_session_id",
        "quiz_session_state",
        "csrf_token",
        "state",
    }
)

SENSITIVE_PATH_PREFIXES = (
    "/api/v2/auth",
    "/api/v2/patients",
    "/api/v2/dashboard",
    "/api/v2/reports",
    "/api/v2/alerts",
    "/api/v2/messages",
    "/api/v2/ai",
    "/api/v2/clinical",
    "/api/v2/physician",
    "/api/v2/quiz-extensions/session/active",
    "/api/v2/quiz-extensions/monthly/public/current",
    "/api/v2/quiz-extensions/access",
    "/api/v2/quiz-extensions/submit",
    "/api/v2/quiz-extensions/logout",
)

REUSABLE_VALIDATOR_HEADERS = (
    "etag",
    "last-modified",
    "age",
    "x-cache",
)


@dataclass(frozen=True)
class CacheSensitivity:
    """Sanitized classification result for cache safety decisions."""

    sensitive: bool
    reason: str = "non_sensitive"


def _matches_prefix(path: str, prefix: str) -> bool:
    if prefix.endswith("/"):
        return path.startswith(prefix)
    return path == prefix or path.startswith(f"{prefix}/")


def _normalize_name(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def _has_sensitive_cookie_name(cookie_names: Iterable[str]) -> bool:
    normalized_sensitive = {_normalize_name(name) for name in SENSITIVE_COOKIE_NAMES}
    for name in cookie_names:
        normalized = _normalize_name(name)
        if normalized in normalized_sensitive:
            return True
        if "session" in normalized or "csrf" in normalized:
            return True
    return False


def _cookie_header_has_sensitive_name(raw_cookie_header: str | None) -> bool:
    if not raw_cookie_header:
        return False

    try:
        cookie_names = [part.split("=", 1)[0].strip() for part in raw_cookie_header.split(";")]
    except Exception:
        # Malformed cookie headers on browser-facing requests are safest as
        # no-store; do not try to log or parse values.
        return True

    return _has_sensitive_cookie_name(name for name in cookie_names if name)


def classify_request_cache_sensitivity(request: Request) -> CacheSensitivity:
    """
    Classify whether a request can receive reusable browser cache headers.

    The result intentionally carries only a coarse reason; it never includes raw
    cookies, tokens, query values, PHI labels, or filesystem paths.
    """

    path = request.url.path
    if any(_matches_prefix(path, prefix) for prefix in SENSITIVE_PATH_PREFIXES):
        return CacheSensitivity(True, "sensitive_path")

    if request.headers.get("Authorization"):
        return CacheSensitivity(True, "authorization_header")

    try:
        if _has_sensitive_cookie_name(request.cookies.keys()):
            return CacheSensitivity(True, "sensitive_cookie")
    except Exception:
        return CacheSensitivity(True, "malformed_cookie_header")

    if _cookie_header_has_sensitive_name(request.headers.get("cookie")):
        return CacheSensitivity(True, "sensitive_cookie")

    try:
        for name in request.query_params.keys():
            normalized = _normalize_name(name)
            if normalized in {_normalize_name(p) for p in SENSITIVE_QUERY_PARAM_NAMES}:
                return CacheSensitivity(True, "sensitive_query_param")
            if "token" in normalized or "session" in normalized or "csrf" in normalized:
                return CacheSensitivity(True, "sensitive_query_param")
    except Exception:
        return CacheSensitivity(True, "malformed_query_params")

    return CacheSensitivity(False)


def response_sets_cookie(response: Response) -> bool:
    """Return True when a response mutates browser cookie state."""

    try:
        return "set-cookie" in response.headers
    except Exception:
        return True


def apply_no_store_headers(response: Response, *, reason: str = "sensitive") -> Response:
    """
    Apply non-replayable cache headers and strip reusable validators.

    Mutates and returns the response for convenient middleware use.
    """

    for header in REUSABLE_VALIDATOR_HEADERS:
        try:
            if header in response.headers:
                del response.headers[header]
        except Exception:
            # Header deletion failures should not prevent no-store fallback.
            logger.debug("Could not remove reusable cache header", extra={"reason": reason})

    response.headers["Cache-Control"] = NO_STORE_CACHE_CONTROL
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def response_headers_are_sensitive(headers: dict[str, str]) -> bool:
    """Detect legacy cached entries that should no longer be replayed."""

    return any(key.lower() == "set-cookie" for key in headers.keys())
