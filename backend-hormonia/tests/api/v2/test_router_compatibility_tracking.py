import ast
from pathlib import Path


ROUTER_PATH = Path(__file__).resolve().parents[3] / "app/api/v2/router.py"


def _iter_router_calls(tree: ast.AST, attr_name: str):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr == attr_name:
            yield node


def _get_keyword(call: ast.Call, name: str):
    return next((keyword for keyword in call.keywords if keyword.arg == name), None)


def _literal_str(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    raise AssertionError(f"Expected string literal, got: {ast.dump(node)}")


def _extract_methods(call: ast.Call) -> tuple[str, ...]:
    methods_keyword = _get_keyword(call, "methods")
    if methods_keyword is None:
        return ()
    assert isinstance(methods_keyword.value, ast.List), "methods must be a list literal"
    methods = [_literal_str(method_node) for method_node in methods_keyword.value.elts]
    return tuple(sorted(methods))


def test_compatibility_tracking_dependency_removed_from_router() -> None:
    tree = ast.parse(ROUTER_PATH.read_text(encoding="utf-8"))

    names = [
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    ]
    assert "build_compat_route_tracking_dependency" not in names


def test_legacy_add_api_route_aliases_removed() -> None:
    tree = ast.parse(ROUTER_PATH.read_text(encoding="utf-8"))

    legacy_aliases = {
        ("/patients", ("GET",)),
        ("/patients", ("POST",)),
        ("/physicians", ("GET",)),
        ("/roles", ("GET",)),
    }

    found: set[tuple[str, tuple[str, ...]]] = set()
    for add_route_call in _iter_router_calls(tree, "add_api_route"):
        if not add_route_call.args:
            continue
        route_path = _literal_str(add_route_call.args[0])
        methods = _extract_methods(add_route_call)
        alias_key = (route_path, methods)
        if alias_key in legacy_aliases:
            found.add(alias_key)

    assert found == set()


def test_legacy_notifications_auth_prefix_removed() -> None:
    tree = ast.parse(ROUTER_PATH.read_text(encoding="utf-8"))

    prefixes: set[str] = set()
    for include_call in _iter_router_calls(tree, "include_router"):
        prefix_keyword = _get_keyword(include_call, "prefix")
        if prefix_keyword is None:
            continue
        prefixes.add(_literal_str(prefix_keyword.value))

    assert "/auth/notifications" not in prefixes
