import inspect

from app.api.v2.routers.patients import crud as patients_crud
from app.api.v2.routers.patients import flow as patients_flow
from app.api.v2.routers.patients import import_export as patients_import_export
from app.api.v2.routers.patients import integrity as patients_integrity
from app.api.v2.routers.physicians import crud as physicians_crud


def _route_contract(router):
    return {
        (route.path, frozenset(route.methods))
        for route in router.routes
        if getattr(route, "path", None) and getattr(route, "methods", None)
    }


def test_phase24_api02_files_wire_async_dependency():
    modules = [
        patients_crud,
        patients_integrity,
        patients_import_export,
        patients_flow,
        physicians_crud,
    ]
    for module in modules:
        source = inspect.getsource(module)
        assert "Depends(get_async_db)" in source
        assert "Depends(get_db)" not in source


def test_phase24_api02_no_sync_query_calls_in_async_handlers():
    modules = [
        patients_crud,
        patients_integrity,
        patients_import_export,
        patients_flow,
        physicians_crud,
    ]
    for module in modules:
        source = inspect.getsource(module)
        assert "db.query(" not in source


def test_phase24_api02_import_export_routes_preserved():
    contract = _route_contract(patients_import_export.router)
    expected = {
        ("/export", frozenset({"GET"})),
        ("/import", frozenset({"POST"})),
        ("/import/validate", frozenset({"POST"})),
        ("/import/template", frozenset({"GET"})),
        ("/import/history", frozenset({"GET"})),
    }
    assert expected.issubset(contract)


def test_phase24_api02_physician_and_patient_routes_preserved():
    patient_contract = _route_contract(patients_crud.router)
    physician_contract = _route_contract(physicians_crud.router)

    assert ("/", frozenset({"GET"})) in patient_contract
    assert ("/{patient_id}", frozenset({"GET"})) in patient_contract
    assert ("/", frozenset({"GET"})) in physician_contract
    assert ("/{physician_id}", frozenset({"GET"})) in physician_contract
