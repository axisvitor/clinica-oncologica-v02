from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.integrations.wuzapi.errors import UnsafeMediaUrlError
from app.integrations.wuzapi.ssrf_guard import validate_media_url

PUBLIC_IPV4 = "93.184.216.34"
PUBLIC_IPV6 = "2606:2800:220:1:248:1893:25c8:1946"


def resolver_for(addresses: Sequence[str], calls: list[tuple[str, int]] | None = None):
    async def _resolver(host: str, port: int) -> Sequence[str]:
        if calls is not None:
            calls.append((host, port))
        return list(addresses)

    return _resolver


@pytest.mark.asyncio
async def test_validate_media_url_allows_public_hostname_resolution():
    calls: list[tuple[str, int]] = []

    result = await validate_media_url(
        "https://media.example.com:8443/path/file.jpg?token=secret",
        resolver=resolver_for([PUBLIC_IPV4, PUBLIC_IPV6], calls),
    )

    assert result == "https://media.example.com:8443/path/file.jpg?token=secret"
    assert calls == [("media.example.com", 8443)]


@pytest.mark.asyncio
async def test_validate_media_url_uses_default_scheme_port_for_dns_resolution():
    calls: list[tuple[str, int]] = []

    await validate_media_url("http://media.example.com/file.jpg", resolver=resolver_for([PUBLIC_IPV4], calls))

    assert calls == [("media.example.com", 80)]


@pytest.mark.asyncio
async def test_validate_media_url_allows_public_ip_literal_without_dns():
    async def fail_if_called(host: str, port: int) -> Sequence[str]:
        raise AssertionError(f"resolver should not be called for IP literal {host}:{port}")

    assert (
        await validate_media_url(f"https://{PUBLIC_IPV4}/file.jpg", resolver=fail_if_called)
        == f"https://{PUBLIC_IPV4}/file.jpg"
    )
    assert (
        await validate_media_url(f"https://[{PUBLIC_IPV6}]/file.jpg", resolver=fail_if_called)
        == f"https://[{PUBLIC_IPV6}]/file.jpg"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "/relative/path.jpg",
        "https:///missing-host.jpg",
        "file:///etc/passwd",
        "ftp://example.com/file.jpg",
        "https://user:pass@example.com/file.jpg",
        "https://user@example.com/file.jpg",
        "https://example.com:0/file.jpg",
        "https://example.com:99999/file.jpg",
        "https://example.com:not-a-port/file.jpg",
    ],
)
async def test_validate_media_url_rejects_malformed_or_unsupported_urls(url):
    with pytest.raises(UnsafeMediaUrlError) as exc_info:
        await validate_media_url(url, resolver=resolver_for([PUBLIC_IPV4]))

    assert str(exc_info.value) == "Blocked media URL"
    if url:
        assert url not in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/file.jpg",
        "https://LOCALHOST./file.jpg",
        "https://media.localhost/file.jpg",
        "https://localhost.localdomain/file.jpg",
        "https://printer.localdomain/file.jpg",
        "https://ip6-localhost/file.jpg",
    ],
)
async def test_validate_media_url_rejects_localhost_like_names_before_dns(url):
    async def fail_if_called(host: str, port: int) -> Sequence[str]:
        raise AssertionError(f"resolver should not be called for localhost-like name {host}:{port}")

    with pytest.raises(UnsafeMediaUrlError) as exc_info:
        await validate_media_url(url, resolver=fail_if_called)

    assert str(exc_info.value) == "Blocked media URL"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/file.jpg",
        "http://10.0.0.1/file.jpg",
        "http://172.16.0.1/file.jpg",
        "http://192.168.1.10/file.jpg",
        "http://169.254.169.254/latest/meta-data",
        "http://169.254.1.1/file.jpg",
        "http://100.64.0.1/file.jpg",
        "http://0.0.0.0/file.jpg",
        "http://224.0.0.1/file.jpg",
        "http://240.0.0.1/file.jpg",
        "http://[::1]/file.jpg",
        "http://[::]/file.jpg",
        "http://[fc00::1]/file.jpg",
        "http://[fe80::1]/file.jpg",
        "http://[ff02::1]/file.jpg",
        "http://[::ffff:127.0.0.1]/file.jpg",
    ],
)
async def test_validate_media_url_rejects_blocked_ip_literals(url):
    with pytest.raises(UnsafeMediaUrlError) as exc_info:
        await validate_media_url(url, resolver=resolver_for([PUBLIC_IPV4]))

    assert str(exc_info.value) == "Blocked media URL"
    assert "169.254.169.254/latest" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_validate_media_url_fails_closed_when_dns_raises():
    async def raising_resolver(host: str, port: int) -> Sequence[str]:
        raise OSError("resolver exploded for secret.example.com/token")

    with pytest.raises(UnsafeMediaUrlError) as exc_info:
        await validate_media_url("https://secret.example.com/file.jpg?bearer=top-secret", resolver=raising_resolver)

    assert str(exc_info.value) == "Blocked media URL"
    assert "secret.example.com" not in str(exc_info.value)
    assert "top-secret" not in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("addresses", [[], ["not-an-ip-address"]])
async def test_validate_media_url_fails_closed_for_empty_or_malformed_dns_answers(addresses):
    with pytest.raises(UnsafeMediaUrlError) as exc_info:
        await validate_media_url("https://media.example.com/file.jpg", resolver=resolver_for(addresses))

    assert str(exc_info.value) == "Blocked media URL"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "blocked_address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.1.1",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "240.0.0.1",
        "::1",
        "::",
        "fc00::1",
        "fe80::1",
        "ff02::1",
        "::ffff:127.0.0.1",
    ],
)
async def test_validate_media_url_fails_closed_for_mixed_public_and_blocked_dns_answers(blocked_address):
    with pytest.raises(UnsafeMediaUrlError) as exc_info:
        await validate_media_url(
            "https://media.example.com/path/private.jpg?token=do-not-leak",
            resolver=resolver_for([PUBLIC_IPV4, blocked_address]),
        )

    assert str(exc_info.value) == "Blocked media URL"
    assert "token=do-not-leak" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_validate_media_url_rejects_blocked_dns_answer_even_when_all_other_answers_are_public():
    with pytest.raises(UnsafeMediaUrlError):
        await validate_media_url(
            "https://media.example.com/file.jpg",
            resolver=resolver_for([PUBLIC_IPV4, PUBLIC_IPV6, "169.254.169.254"]),
        )
