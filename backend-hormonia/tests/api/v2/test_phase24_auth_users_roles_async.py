import inspect

from fastapi import params

from app.api.v2.routers import auth, users
from app.api.v2.routers.roles import endpoints as role_endpoints
from app.core.database.async_engine import get_async_db


def _db_dependency_name(fn) -> str | None:
    signature = inspect.signature(fn)
    db_param = signature.parameters.get("db")
    if not db_param:
        return None
    default = db_param.default
    if not isinstance(default, params.Depends):
        return None
    dependency = default.dependency
    return getattr(dependency, "__name__", None)


def _route_contract(router):
    return {
        (route.path, frozenset(route.methods))
        for route in router.routes
        if getattr(route, "path", None) and getattr(route, "methods", None)
    }


def test_auth_users_roles_async_handlers_use_get_async_db():
    modules = (auth, users, role_endpoints)
    migrated_handlers = []

    for module in modules:
        for _, fn in inspect.getmembers(module, inspect.iscoroutinefunction):
            if fn.__module__ != module.__name__:
                continue
            dependency_name = _db_dependency_name(fn)
            if dependency_name is None:
                continue
            migrated_handlers.append(f"{module.__name__}.{fn.__name__}")
            assert dependency_name == get_async_db.__name__, (
                f"{module.__name__}.{fn.__name__} must depend on get_async_db"
            )

    assert migrated_handlers


def test_auth_users_roles_async_handlers_do_not_use_sync_query_chaining():
    modules = (auth, users, role_endpoints)
    for module in modules:
        source = inspect.getsource(module)
        assert "db.query(" not in source, f"sync query chaining found in {module.__name__}"


def test_auth_users_roles_modules_do_not_import_sync_get_db_dependency():
    modules = (auth, users, role_endpoints)
    for module in modules:
        source = inspect.getsource(module)
        assert "Depends(get_db)" not in source, f"sync get_db dependency found in {module.__name__}"


def test_auth_users_roles_route_contracts_remain_available():
    auth_contract = _route_contract(auth.router)
    users_contract = _route_contract(users.router)
    roles_contract = _route_contract(role_endpoints.router)

    expected_auth = {
        ("/firebase/verify", frozenset({"POST"})),
        ("/login", frozenset({"POST"})),
        ("/verify-session", frozenset({"GET"})),
        ("/logout", frozenset({"DELETE"})),
        ("/logout-all", frozenset({"DELETE"})),
        ("/health", frozenset({"GET"})),
        ("/profile", frozenset({"PUT"})),
        ("/password", frozenset({"PUT"})),
        ("/avatar", frozenset({"POST"})),
    }
    expected_users = {
        ("/me", frozenset({"GET"})),
        ("/preferences", frozenset({"GET"})),
        ("/preferences", frozenset({"PATCH"})),
        ("/preferences", frozenset({"PUT"})),
        ("/sessions", frozenset({"GET"})),
        ("/sessions/{session_id}", frozenset({"DELETE"})),
    }
    expected_roles = {
        ("/", frozenset({"GET"})),
        ("/{user_id:uuid}", frozenset({"GET"})),
        ("/{user_id}/assign", frozenset({"POST"})),
        ("/{user_id}/revoke", frozenset({"DELETE"})),
        ("/bulk-assign", frozenset({"POST"})),
        ("/statistics", frozenset({"GET"})),
        ("/permissions/{role}", frozenset({"GET"})),
        ("/validate", frozenset({"POST"})),
    }

    assert expected_auth.issubset(auth_contract)
    assert expected_users.issubset(users_contract)
    assert expected_roles.issubset(roles_contract)
