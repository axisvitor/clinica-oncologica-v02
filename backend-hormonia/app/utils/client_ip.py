"""Trusted-proxy aware client identity resolution.

By default the application uses the direct peer address from ``request.client``.
Proxy headers are honored only when both conditions are true:

1. ``RATE_LIMIT_TRUST_PROXY_HEADERS`` is explicitly enabled.
2. The direct peer address is in ``RATE_LIMIT_TRUSTED_PROXIES`` (IP/CIDR list).

This fail-closed boundary prevents internet clients from spoofing
``X-Forwarded-For``/``X-Real-IP`` into rate-limit and audit identifiers.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Sequence

try:  # FastAPI is available in the backend runtime; keep import local-friendly.
    from fastapi import Request
except Exception:  # pragma: no cover - type-check/import fallback only
    Request = object  # type: ignore[assignment]


_UNKNOWN_CLIENT = "unknown"
_PROXY_HEADER_XFF = "x-forwarded-for"
_PROXY_HEADER_REAL_IP = "x-real-ip"
_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ClientIpResolution:
    """Result of resolving a request client identity."""

    ip_address: str
    peer_ip: str
    source: str
    trusted_proxy: bool
    proxy_headers_present: bool
    reason: str

    @property
    def client_identity_hash(self) -> str:
        """Stable, non-reversible hash safe for structured diagnostics."""
        return hash_sensitive_identifier(self.ip_address, prefix="client")

    @property
    def client_identity_redacted(self) -> str:
        """Redacted representation safe for human diagnostics."""
        return redact_client_identity(self.ip_address)


@dataclass(frozen=True)
class ProxyTrustConfig:
    """Trusted-proxy settings used by the resolver."""

    trust_proxy_headers: bool
    trusted_proxies: tuple[str, ...]


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in _TRUE_VALUES


def _parse_list(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())

    text = str(value).strip()
    if not text:
        return ()

    if text.startswith("["):
        try:
            decoded = json.loads(text)
            if isinstance(decoded, list):
                return tuple(str(item).strip() for item in decoded if str(item).strip())
        except Exception:
            pass

    return tuple(item.strip() for item in text.split(",") if item.strip())


def load_proxy_trust_config() -> ProxyTrustConfig:
    """Load trusted-proxy settings from environment variables.

    ``RATE_LIMIT_TRUSTED_PROXIES`` is intentionally empty by default. Enabling
    proxy headers without a trusted peer/CIDR list still fails closed to the
    direct peer address.
    """
    trust_headers = _truthy(os.getenv("RATE_LIMIT_TRUST_PROXY_HEADERS", "false"))
    trusted_proxies = _parse_list(
        os.getenv("RATE_LIMIT_TRUSTED_PROXIES")
        or os.getenv("TRUSTED_PROXY_CIDRS")
        or os.getenv("TRUSTED_PROXIES")
    )
    return ProxyTrustConfig(
        trust_proxy_headers=trust_headers,
        trusted_proxies=trusted_proxies,
    )


def normalize_ip_address(value: object) -> Optional[str]:
    """Return a canonical IP string or ``None`` for malformed input."""
    if value is None:
        return None

    candidate = str(value).strip()
    if not candidate:
        return None

    # Common proxy forms: [2001:db8::1]:443 or 203.0.113.5:12345.
    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1 : candidate.index("]")]
    elif candidate.count(":") == 1:
        host, maybe_port = candidate.rsplit(":", 1)
        if maybe_port.isdigit():
            candidate = host

    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def _peer_host(request: Request | None) -> str:
    if request is None:
        return _UNKNOWN_CLIENT
    client = getattr(request, "client", None)
    host = getattr(client, "host", None)
    return normalize_ip_address(host) or (str(host).strip() if host else _UNKNOWN_CLIENT)


def _headers(request: Request | None) -> Mapping[str, str]:
    if request is None:
        return {}
    return getattr(request, "headers", {}) or {}


def _is_trusted_proxy(peer_ip: str, trusted_proxies: Iterable[str]) -> bool:
    normalized_peer = normalize_ip_address(peer_ip)

    # TestClient and some local harnesses use a host token rather than an IP.
    # Treat exact non-IP names as trusted only when explicitly configured.
    if not normalized_peer:
        return any(str(entry).strip() == peer_ip for entry in trusted_proxies)

    try:
        peer = ipaddress.ip_address(normalized_peer)
    except ValueError:
        return False

    for entry in trusted_proxies:
        normalized_entry = str(entry).strip()
        if not normalized_entry:
            continue
        try:
            if "/" in normalized_entry:
                if peer in ipaddress.ip_network(normalized_entry, strict=False):
                    return True
            else:
                trusted_ip = normalize_ip_address(normalized_entry)
                if trusted_ip and peer == ipaddress.ip_address(trusted_ip):
                    return True
                if not trusted_ip and peer_ip == normalized_entry:
                    return True
        except ValueError:
            if peer_ip == normalized_entry:
                return True
            continue
    return False


def _first_forwarded_ip(header_value: Optional[str]) -> Optional[str]:
    if not header_value:
        return None
    first_hop = header_value.split(",", 1)[0].strip()
    return normalize_ip_address(first_hop)


def _proxy_headers_present(headers: Mapping[str, str]) -> bool:
    return bool(headers.get(_PROXY_HEADER_XFF) or headers.get(_PROXY_HEADER_REAL_IP))


def resolve_client_ip(
    request: Request | None,
    *,
    trust_proxy_headers: Optional[bool] = None,
    trusted_proxies: Optional[Sequence[str]] = None,
) -> ClientIpResolution:
    """Resolve client IP with a fail-closed trusted-proxy boundary."""
    peer_ip = _peer_host(request)
    headers = _headers(request)
    headers_present = _proxy_headers_present(headers)

    if request is None:
        return ClientIpResolution(
            ip_address=_UNKNOWN_CLIENT,
            peer_ip=_UNKNOWN_CLIENT,
            source="missing_request",
            trusted_proxy=False,
            proxy_headers_present=False,
            reason="missing_request",
        )

    config = load_proxy_trust_config()
    should_trust_headers = (
        config.trust_proxy_headers if trust_proxy_headers is None else bool(trust_proxy_headers)
    )
    trusted_peer_ranges = tuple(
        config.trusted_proxies if trusted_proxies is None else trusted_proxies
    )

    normalized_peer = normalize_ip_address(peer_ip) or peer_ip or _UNKNOWN_CLIENT

    if not should_trust_headers:
        return ClientIpResolution(
            ip_address=normalized_peer,
            peer_ip=normalized_peer,
            source="peer",
            trusted_proxy=False,
            proxy_headers_present=headers_present,
            reason="proxy_headers_disabled" if headers_present else "peer_address",
        )

    trusted_peer = _is_trusted_proxy(normalized_peer, trusted_peer_ranges)
    if not trusted_peer:
        return ClientIpResolution(
            ip_address=normalized_peer,
            peer_ip=normalized_peer,
            source="peer",
            trusted_proxy=False,
            proxy_headers_present=headers_present,
            reason="untrusted_proxy_peer" if headers_present else "peer_address",
        )

    xff_ip = _first_forwarded_ip(headers.get(_PROXY_HEADER_XFF))
    if xff_ip:
        return ClientIpResolution(
            ip_address=xff_ip,
            peer_ip=normalized_peer,
            source="x-forwarded-for",
            trusted_proxy=True,
            proxy_headers_present=True,
            reason="trusted_proxy_header",
        )

    real_ip = normalize_ip_address(headers.get(_PROXY_HEADER_REAL_IP))
    if real_ip:
        return ClientIpResolution(
            ip_address=real_ip,
            peer_ip=normalized_peer,
            source="x-real-ip",
            trusted_proxy=True,
            proxy_headers_present=True,
            reason="trusted_proxy_header",
        )

    return ClientIpResolution(
        ip_address=normalized_peer,
        peer_ip=normalized_peer,
        source="peer",
        trusted_proxy=True,
        proxy_headers_present=headers_present,
        reason="malformed_proxy_header" if headers_present else "trusted_proxy_no_header",
    )


def get_client_ip(request: Request | None) -> str:
    """Return the resolved client IP address for request identity keys."""
    return resolve_client_ip(request).ip_address


def get_rate_limit_client_key(request: Request | None) -> str:
    """SlowAPI-compatible key function."""
    return get_client_ip(request)


def hash_sensitive_identifier(value: object, *, prefix: str = "id") -> str:
    """Hash a sensitive identifier for logs and rate-limit keys."""
    normalized = str(value or _UNKNOWN_CLIENT).strip() or _UNKNOWN_CLIENT
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def redact_client_identity(value: object) -> str:
    """Return a non-secret, non-precise client identity representation."""
    normalized = normalize_ip_address(value)
    if not normalized:
        return _UNKNOWN_CLIENT

    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        return _UNKNOWN_CLIENT

    if isinstance(ip, ipaddress.IPv4Address):
        octets = normalized.split(".")
        return ".".join(octets[:3] + ["0"]) + "/24"

    hextets = ip.exploded.split(":")
    return ":".join(hextets[:4] + ["0000", "0000", "0000", "0000"]) + "/64"


def get_request_id(request: Request | None) -> Optional[str]:
    """Extract request/correlation ID without inspecting sensitive headers."""
    if request is None:
        return None
    state = getattr(request, "state", None)
    for attr in ("request_id", "correlation_id"):
        value = getattr(state, attr, None)
        if value:
            return str(value)
    headers = _headers(request)
    return headers.get("x-request-id") or headers.get("x-correlation-id")


def rate_limit_log_extra(
    request: Request | None,
    *,
    reason: str,
    scope: str,
    limit: Optional[int] = None,
    window_seconds: Optional[int] = None,
    retry_after: Optional[int] = None,
) -> dict[str, object]:
    """Build PHI-safe structured diagnostics for rate-limit denials."""
    resolved = resolve_client_ip(request)
    extra: dict[str, object] = {
        "event_type": "rate_limit_denied",
        "reason": reason,
        "scope": scope,
        "client_identity_hash": resolved.client_identity_hash,
        "client_identity_redacted": resolved.client_identity_redacted,
        "client_identity_source": resolved.source,
        "trusted_proxy": resolved.trusted_proxy,
    }
    if request is not None:
        extra["route"] = getattr(getattr(request, "url", None), "path", None)
        extra["method"] = getattr(request, "method", None)
        request_id = get_request_id(request)
        if request_id:
            extra["request_id"] = request_id
            extra["correlation_id"] = request_id
    if limit is not None:
        extra["limit"] = limit
    if window_seconds is not None:
        extra["window_seconds"] = window_seconds
    if retry_after is not None:
        extra["retry_after"] = retry_after
    return extra


__all__ = [
    "ClientIpResolution",
    "ProxyTrustConfig",
    "get_client_ip",
    "get_rate_limit_client_key",
    "get_request_id",
    "hash_sensitive_identifier",
    "load_proxy_trust_config",
    "normalize_ip_address",
    "rate_limit_log_extra",
    "redact_client_identity",
    "resolve_client_ip",
]
