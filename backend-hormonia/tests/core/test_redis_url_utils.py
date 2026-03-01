"""Tests for Redis URL normalization helpers."""

from app.core.redis_manager.utils import build_redis_url_for_db


def test_build_redis_url_for_db_preserves_auth_host_and_query() -> None:
    url = "rediss://default:secret@cache.example.com:6379/0?ssl_cert_reqs=required"
    updated = build_redis_url_for_db(url, 3)
    assert updated == "rediss://default:secret@cache.example.com:6379/3?ssl_cert_reqs=required"


def test_build_redis_url_for_db_overrides_path_even_without_db() -> None:
    url = "redis://localhost:6379"
    updated = build_redis_url_for_db(url, 2)
    assert updated == "redis://localhost:6379/2"


def test_build_redis_url_for_db_keeps_unparseable_input() -> None:
    url = "localhost:6379"
    updated = build_redis_url_for_db(url, 1)
    assert updated == url
