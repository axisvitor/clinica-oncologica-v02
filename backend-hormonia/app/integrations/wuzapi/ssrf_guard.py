from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Sequence
from urllib.parse import urlsplit

from app.integrations.wuzapi.errors import UnsafeMediaUrlError

ResolvedAddress = str | ipaddress.IPv4Address | ipaddress.IPv6Address
Resolver = Callable[[str, int], Awaitable[Sequence[ResolvedAddress]]]

_CARRIER_GRADE_NAT = ipaddress.ip_network("100.64.0.0/10")
_METADATA_IPV4 = ipaddress.ip_network("169.254.169.254/32")
_LOCALHOST_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
}
_LOCALHOST_SUFFIXES = (
    ".localhost",
    ".localdomain",
)


async def validate_media_url(url: str, resolver: Resolver | None = None) -> str:
    """Validate that a media URL is safe for an outbound WuzAPI fetch.

    The original URL is returned unchanged so callers do not accidentally log or
    rewrite attacker-controlled paths/query strings during validation.
    """

    parsed = _parse_media_url(url)
    host = _normalized_hostname(parsed.hostname)

    if _is_localhost_name(host):
        _raise_blocked()

    port = parsed.port if parsed.port is not None else _default_port(parsed.scheme)

    try:
        ip_address = ipaddress.ip_address(host)
    except ValueError:
        addresses = await _resolve_addresses(host, port, resolver)
    else:
        addresses = [ip_address]

    if not addresses:
        _raise_blocked()

    for address in addresses:
        try:
            parsed_address = (
                address
                if isinstance(address, (ipaddress.IPv4Address, ipaddress.IPv6Address))
                else ipaddress.ip_address(str(address))
            )
        except ValueError:
            _raise_blocked()

        if is_blocked_address(parsed_address):
            _raise_blocked()

    return url


async def resolve_host(host: str, port: int) -> Sequence[str]:
    """Resolve a hostname to IP address strings using the OS resolver."""

    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses: list[str] = []
    seen: set[str] = set()
    for *_, sockaddr in infos:
        address = sockaddr[0]
        if address not in seen:
            seen.add(address)
            addresses.append(address)
    return addresses


def is_blocked_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True when an IP address belongs to a non-public or metadata range."""

    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        return is_blocked_address(mapped)

    if isinstance(address, ipaddress.IPv4Address):
        if address in _CARRIER_GRADE_NAT or address in _METADATA_IPV4:
            return True

    return any(
        (
            address.is_loopback,
            address.is_private,
            address.is_link_local,
            address.is_multicast,
            address.is_unspecified,
            address.is_reserved,
        )
    )


def _parse_media_url(url: str):
    if not isinstance(url, str) or not url.strip():
        _raise_blocked()

    try:
        parsed = urlsplit(url)
    except ValueError:
        _raise_blocked()

    if parsed.scheme not in {"http", "https"}:
        _raise_blocked()

    if not parsed.hostname:
        _raise_blocked()

    if parsed.username is not None or parsed.password is not None:
        _raise_blocked()

    try:
        port = parsed.port
    except ValueError:
        _raise_blocked()

    if port is not None and port <= 0:
        _raise_blocked()

    return parsed


def _normalized_hostname(hostname: str | None) -> str:
    if hostname is None:
        _raise_blocked()
    normalized = hostname.strip().lower().rstrip(".")
    if not normalized:
        _raise_blocked()
    return normalized


def _is_localhost_name(host: str) -> bool:
    return host in _LOCALHOST_HOSTNAMES or host.endswith(_LOCALHOST_SUFFIXES)


async def _resolve_addresses(host: str, port: int, resolver: Resolver | None) -> Sequence[ResolvedAddress]:
    try:
        active_resolver = resolver or resolve_host
        return await active_resolver(host, port)
    except Exception as exc:  # noqa: BLE001 - fail closed without leaking the URL/resolver details
        raise UnsafeMediaUrlError() from exc


def _default_port(scheme: str) -> int:
    if scheme == "http":
        return 80
    if scheme == "https":
        return 443
    _raise_blocked()


def _raise_blocked() -> None:
    raise UnsafeMediaUrlError()
