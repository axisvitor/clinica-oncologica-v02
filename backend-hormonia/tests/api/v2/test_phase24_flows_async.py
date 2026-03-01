import inspect
import re
from pathlib import Path

from app.api.v2.routers import flow_templates, flows


def _route_contract(router):
    return {
        (route.path, frozenset(route.methods))
        for route in router.routes
        if getattr(route, "path", None) and getattr(route, "methods", None)
    }


def _normalize_api_path(path: str) -> str:
    normalized = re.sub(r"\{[^}]+\}", "{param}", path)
    return normalized.split("?")[0]


def _extract_paths_from_test_source(filename: str) -> set[str]:
    source = Path(__file__).with_name(filename).read_text(encoding="utf-8")
    return {
        _normalize_api_path(match)
        for match in re.findall(r"/api/v2/flows[^\"'\s,)]*", source)
    }


def test_phase24_api03_files_include_async_dependency_wiring():
    flow_source = inspect.getsource(flows)
    templates_source = inspect.getsource(flow_templates)

    assert "Depends(get_async_db)" in flow_source
    assert "Depends(get_async_db)" in templates_source


def test_flow_router_uses_async_dependencies():
    flow_source = inspect.getsource(flows)

    assert "async_db: AsyncSession = Depends(get_async_db)" in flow_source
    assert "db=Depends(get_db)" not in flow_source
    assert "db.query(" not in flow_source


def test_phase24_api03_flow_sections_routes_present():
    flow_contract = _route_contract(flows.router)
    expected_by_section = {
        "analytics": {
            ("/analytics", frozenset({"GET"})),
            ("/analytics/export", frozenset({"GET"})),
        },
        "state": {
            ("/", frozenset({"GET"})),
            ("/{patient_id}/state", frozenset({"GET"})),
            ("/{patient_id}/history", frozenset({"GET"})),
        },
        "templates": {
            ("/templates", frozenset({"GET"})),
            ("/templates", frozenset({"POST"})),
            ("/templates/{template_id}", frozenset({"GET"})),
            ("/templates/{template_id}", frozenset({"PUT"})),
            ("/templates/{template_id}", frozenset({"DELETE"})),
        },
        "advanced": {
            ("/{patient_id}/advance", frozenset({"POST"})),
            ("/{patient_id}/pause", frozenset({"POST"})),
            ("/{patient_id}/resume", frozenset({"POST"})),
            ("/start", frozenset({"POST"})),
            ("/{patient_id}/response", frozenset({"POST"})),
        },
    }

    for expected in expected_by_section.values():
        assert expected.issubset(flow_contract)


def test_phase24_api03_flow_template_routes_present():
    contract = _route_contract(flow_templates.router)
    expected = {
        ("/flows", frozenset({"GET"})),
        ("/flows", frozenset({"POST"})),
        ("/flows/{template_id}", frozenset({"GET"})),
        ("/flows/{template_id}", frozenset({"PUT"})),
        ("/flows/{template_id}", frozenset({"DELETE"})),
        ("/flows/{template_id}/duplicate", frozenset({"POST"})),
        ("/flow-kinds", frozenset({"GET"})),
        ("/flow-kinds", frozenset({"POST"})),
    }
    assert expected.issubset(contract)


def test_flow_templates_router_has_no_sync_query_chains():
    source = inspect.getsource(flow_templates)

    assert "db.query(" not in source
    assert "Depends(get_async_db)" in source


def test_flow_templates_router_write_ops_are_async():
    source = inspect.getsource(flow_templates)

    for op in ["commit", "flush", "refresh", "rollback", "delete"]:
        assert re.search(r"(?<!await )db\\." + op + r"\(", source) is None


def test_flow_templates_router_uses_select_execute_pattern():
    source = inspect.getsource(flow_templates)

    assert "await db.execute(" in source
    assert "select(" in source


def test_phase24_api03_contract_parity_with_existing_flow_tests():
    contract_paths = {
        _normalize_api_path(f"/api/v2/flows{path}")
        for path, _methods in _route_contract(flows.router)
    }
    parity_required = {
        _normalize_api_path(path)
        for path in {
            "/api/v2/flows/analytics",
            "/api/v2/flows/{patient_id}/state",
            "/api/v2/flows/{patient_id}/history",
            "/api/v2/flows/templates",
            "/api/v2/flows/templates/{template_id}",
            "/api/v2/flows/{patient_id}/advance",
            "/api/v2/flows/{patient_id}/pause",
            "/api/v2/flows/{patient_id}/resume",
            "/api/v2/flows/start",
            "/api/v2/flows/{patient_id}/response",
        }
    }

    legacy_paths = _extract_paths_from_test_source("test_flows.py")
    legacy_paths.update(_extract_paths_from_test_source("test_flows_advance.py"))

    assert parity_required.issubset(contract_paths)
    assert parity_required.issubset(legacy_paths)
