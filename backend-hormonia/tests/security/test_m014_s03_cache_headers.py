from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from app.middleware import cache_middleware as cache_middleware_module
from app.middleware.cache_middleware import CacheMiddleware


class FakeCacheManager:
    def __init__(self):
        self.entries = {}
        self.get_calls = []
        self.set_calls = []

    def get(self, namespace, *, key_parts):
        self.get_calls.append((namespace, tuple(key_parts)))
        return self.entries.get((namespace, tuple(key_parts)))

    def set(self, namespace, value, *, key_parts, ttl_override=None):
        self.set_calls.append((namespace, tuple(key_parts), ttl_override))
        self.entries[(namespace, tuple(key_parts))] = value


def _build_client(monkeypatch, fake_cache):
    monkeypatch.setattr(cache_middleware_module, "get_cache_manager", lambda: fake_cache)

    app = FastAPI()
    call_counts = {"public_static": 0}

    @app.get("/safe")
    async def safe_response():
        return {"ok": True}

    @app.get("/api/v2/patients")
    async def patients_response():
        return {"count": 0}

    @app.get("/api/v2/quiz-extensions/monthly/public/current")
    async def public_quiz_current():
        return {"available": True}

    @app.get("/api/v2/quiz-extensions/access")
    async def public_quiz_access_get():
        return {"available": True}

    @app.get("/sets-cookie")
    async def set_cookie_response(response: Response):
        response.set_cookie("session", "opaque", httponly=True, samesite="lax")
        return {"ok": True}

    @app.get("/public-static")
    async def public_static_response():
        call_counts["public_static"] += 1
        return {"kind": "static", "calls": call_counts["public_static"]}

    app.add_middleware(CacheMiddleware, default_ttl=60, exclude_patterns=[])
    client = TestClient(app)
    return client, call_counts


def _assert_no_store(response):
    cache_control = response.headers.get("cache-control", "").lower()
    assert "no-store" in cache_control
    assert "public" not in cache_control
    assert response.headers.get("pragma") == "no-cache"
    assert response.headers.get("expires") == "0"
    assert "etag" not in response.headers
    assert "x-cache" not in response.headers


def test_cookie_only_session_get_bypasses_cache_and_removes_validators(monkeypatch):
    fake_cache = FakeCacheManager()
    client, _ = _build_client(monkeypatch, fake_cache)

    response = client.get(
        "/safe",
        cookies={"session": "opaque"},
        headers={"If-None-Match": '"legacy-validator"'},
    )

    assert response.status_code == 200
    _assert_no_store(response)
    assert fake_cache.get_calls == []
    assert fake_cache.set_calls == []


def test_authorization_header_is_no_store_for_any_auth_scheme(monkeypatch):
    fake_cache = FakeCacheManager()
    client, _ = _build_client(monkeypatch, fake_cache)

    response = client.get("/safe", headers={"Authorization": "Basic opaque"})

    assert response.status_code == 200
    _assert_no_store(response)
    assert fake_cache.get_calls == []
    assert fake_cache.set_calls == []


def test_token_query_param_is_no_store_and_never_hits_cache(monkeypatch):
    fake_cache = FakeCacheManager()
    client, _ = _build_client(monkeypatch, fake_cache)

    response = client.get("/safe?access_token=opaque")

    assert response.status_code == 200
    _assert_no_store(response)
    assert fake_cache.get_calls == []
    assert fake_cache.set_calls == []


def test_phi_path_prefix_is_no_store_without_cookie_or_bearer(monkeypatch):
    fake_cache = FakeCacheManager()
    client, _ = _build_client(monkeypatch, fake_cache)

    response = client.get("/api/v2/patients")

    assert response.status_code == 200
    _assert_no_store(response)
    assert fake_cache.get_calls == []
    assert fake_cache.set_calls == []


def test_public_quiz_session_paths_are_no_store_without_http_cache(monkeypatch):
    fake_cache = FakeCacheManager()
    client, _ = _build_client(monkeypatch, fake_cache)

    current = client.get("/api/v2/quiz-extensions/monthly/public/current")
    access = client.get("/api/v2/quiz-extensions/access")

    assert current.status_code == 200
    assert access.status_code == 200
    _assert_no_store(current)
    _assert_no_store(access)
    assert fake_cache.get_calls == []
    assert fake_cache.set_calls == []


def test_response_set_cookie_is_no_store_and_not_written_to_http_cache(monkeypatch):
    fake_cache = FakeCacheManager()
    client, _ = _build_client(monkeypatch, fake_cache)

    response = client.get("/sets-cookie")

    assert response.status_code == 200
    assert "set-cookie" in response.headers
    _assert_no_store(response)
    assert fake_cache.set_calls == []


def test_non_phi_static_get_still_records_miss_then_hit(monkeypatch):
    fake_cache = FakeCacheManager()
    client, call_counts = _build_client(monkeypatch, fake_cache)

    first = client.get("/public-static")
    second = client.get("/public-static")

    assert first.status_code == 200
    assert first.headers.get("x-cache") == "MISS"
    assert "public" in first.headers.get("cache-control", "").lower()
    assert "etag" in first.headers
    assert second.status_code == 200
    assert second.headers.get("x-cache") == "HIT"
    assert second.json() == first.json()
    assert call_counts["public_static"] == 1
    assert len(fake_cache.set_calls) == 1
    assert len(fake_cache.get_calls) == 2
