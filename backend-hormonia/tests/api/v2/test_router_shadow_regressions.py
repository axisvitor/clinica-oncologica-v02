"""Regression tests for API v2 route shadowing and duplication fixes."""

from __future__ import annotations

from collections import defaultdict

from starlette.routing import Match

from app.api.v2.router import api_v2_router


def _iter_api_routes():
    for route in api_v2_router.routes:
        if not hasattr(route, "path") or not hasattr(route, "methods"):
            continue
        methods = sorted(
            method for method in route.methods if method not in {"HEAD", "OPTIONS"}
        )
        if not methods:
            continue
        yield route, methods


def _first_full_match(path: str, method: str):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": method,
        "path": path,
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
        "http_version": "1.1",
    }
    for route in api_v2_router.routes:
        if not hasattr(route, "matches"):
            continue
        match_result, _ = route.matches(scope)
        if match_result == Match.FULL:
            return route.path
    return None


def test_messages_conversation_route_registered_once():
    target_path = "/api/v2/messages/conversations/{patient_id}"
    matches = []
    for route, methods in _iter_api_routes():
        if route.path == target_path and "GET" in methods:
            matches.append(route)
    assert len(matches) == 1


def test_static_routes_not_shadowed():
    expected_matches = {
        ("/api/v2/patients/export", "GET"): "/api/v2/patients/export",
        ("/api/v2/patients/check-email", "GET"): "/api/v2/patients/check-email",
        ("/api/v2/patients/deleted", "GET"): "/api/v2/patients/deleted",
        ("/api/v2/patients/stats", "GET"): "/api/v2/patients/stats",
        ("/api/v2/webhooks/events", "GET"): "/api/v2/webhooks/events",
        ("/api/v2/webhooks/stats", "GET"): "/api/v2/webhooks/stats",
        ("/api/v2/webhooks/failed", "GET"): "/api/v2/webhooks/failed",
        ("/api/v2/tasks/bulk/cancel", "POST"): "/api/v2/tasks/bulk/cancel",
        ("/api/v2/roles/statistics", "GET"): "/api/v2/roles/statistics",
        ("/api/v2/quiz-extensions/monthly/schedule", "GET"): "/api/v2/quiz-extensions/monthly/schedule",
        ("/api/v2/quiz-extensions/monthly/templates", "GET"): "/api/v2/quiz-extensions/monthly/templates",
    }
    for (path, method), expected_route_path in expected_matches.items():
        assert _first_full_match(path, method) == expected_route_path


def test_whatsapp_routes_use_single_v2_prefix():
    paths = [route.path for route, _ in _iter_api_routes()]
    assert not any("/api/v2/api/v2/whatsapp/" in path for path in paths)


def test_whatsapp_statistics_route_not_shadowed_by_chat_history():
    assert (
        _first_full_match("/api/v2/whatsapp/messages/demo/statistics", "GET")
        == "/api/v2/whatsapp/messages/{instance_name}/statistics"
    )
    assert (
        _first_full_match("/api/v2/whatsapp/messages/demo/abc123", "GET")
        == "/api/v2/whatsapp/messages/{instance_name}/{chat_id}"
    )


def test_no_exact_duplicate_route_method_pairs():
    bucket: dict[tuple[str, tuple[str, ...]], int] = defaultdict(int)
    for route, methods in _iter_api_routes():
        bucket[(route.path, tuple(methods))] += 1

    duplicates = [key for key, count in bucket.items() if count > 1]
    assert duplicates == []
