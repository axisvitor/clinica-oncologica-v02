"""Regression tests for the scoped runtime-residue verifier."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[3]
    / ".gsd"
    / "milestones"
    / "M004"
    / "slices"
    / "S01"
    / "verify-runtime-residue.sh"
)


def _write_file(repo_root: Path, relative_path: str, content: str) -> None:
    target = repo_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _fixture_allowlist() -> dict:
    return {
        "schema_version": 1,
        "scope_defaults": {
            "backend": {
                "extensions": [".py"],
                "exclude": [
                    "backend-hormonia/tests/**",
                    "backend-hormonia/app/models/**",
                    "backend-hormonia/app/schemas/**",
                ],
            },
            "frontend": {
                "extensions": [".ts", ".tsx"],
                "exclude": [
                    "frontend-hormonia/tests/**",
                    "frontend-hormonia/src/**/__tests__/**",
                ],
            },
        },
        "categories": [
            {
                "id": "firebase_uid",
                "matchers": [{"type": "literal", "pattern": "firebase_uid"}],
                "scopes": {
                    "backend": {
                        "roots": ["backend-hormonia/app"],
                        "approved": [
                            {
                                "path": "backend-hormonia/app/api/v2/routers/auth.py",
                                "anchors": [
                                    {
                                        "type": "literal",
                                        "pattern": 'user_payload["firebase_uid"] = user.firebase_uid',
                                        "label": "auth_uid_anchor",
                                    }
                                ],
                            }
                        ],
                    }
                },
            },
            {
                "id": "root_legacy_session",
                "matchers": [{"type": "literal", "pattern": "/session"}],
                "scopes": {
                    "backend": {
                        "roots": ["backend-hormonia/app"],
                        "approved": [
                            {
                                "path": "backend-hormonia/app/core/router_registry.py",
                                "anchors": [
                                    {
                                        "type": "literal",
                                        "pattern": "Session authentication endpoints registered (/session)",
                                        "label": "router_registry_anchor",
                                    }
                                ],
                            },
                            {
                                "path": "backend-hormonia/app/routers/auth_session.py",
                                "anchors": [
                                    {
                                        "type": "literal",
                                        "pattern": 'router = APIRouter(prefix="/session", tags=["Session Authentication"])',
                                        "label": "auth_session_anchor",
                                    }
                                ],
                            },
                        ],
                    }
                },
            },
            {
                "id": "x_session_id",
                "matchers": [{"type": "literal", "pattern": "X-Session-ID"}],
                "scopes": {
                    "backend": {
                        "roots": ["backend-hormonia/app"],
                        "approved": [
                            {
                                "path": "backend-hormonia/app/api/v2/routers/auth.py",
                                "anchors": [
                                    {
                                        "type": "literal",
                                        "pattern": 'header_id = request.headers.get("X-Session-ID")',
                                        "label": "auth_header_anchor",
                                    }
                                ],
                            }
                        ],
                    },
                    "frontend": {
                        "roots": ["frontend-hormonia/src"],
                        "approved": [
                            {
                                "path": "frontend-hormonia/src/lib/api-client/core.ts",
                                "anchors": [
                                    {
                                        "type": "literal",
                                        "pattern": "headers['X-Session-ID'] = token",
                                        "label": "frontend_header_anchor",
                                    }
                                ],
                            }
                        ],
                    },
                },
            },
            {
                "id": "session_bearer_fallback",
                "matchers": [
                    {"type": "literal", "pattern": "Bearer "},
                    {"type": "literal", "pattern": "Bearer <session_id>"},
                    {"type": "literal", "pattern": "Bearer session_id"},
                ],
                "scopes": {
                    "backend": {
                        "roots": ["backend-hormonia/app"],
                        "approved": [
                            {
                                "path": "backend-hormonia/app/api/v2/routers/auth.py",
                                "anchors": [
                                    {
                                        "type": "literal",
                                        "pattern": 'if auth_header and auth_header.startswith("Bearer "):',
                                        "label": "auth_bearer_anchor",
                                    }
                                ],
                            }
                        ],
                    },
                    "frontend": {
                        "roots": ["frontend-hormonia/src"],
                        "approved": [
                            {
                                "path": "frontend-hormonia/src/lib/api-client/core.ts",
                                "anchors": [
                                    {
                                        "type": "literal",
                                        "pattern": "headers['Authorization'] = `Bearer ${token}`",
                                        "label": "frontend_bearer_anchor",
                                    }
                                ],
                            }
                        ],
                    },
                },
            },
            {
                "id": "websocket_session_id_query",
                "matchers": [
                    {"type": "literal", "pattern": "query_session_id"},
                    {"type": "literal", "pattern": "searchParams.set('session_id'"},
                    {"type": "literal", "pattern": 'searchParams.set("session_id"'},
                ],
                "scopes": {
                    "backend": {
                        "roots": ["backend-hormonia/app"],
                        "approved": [
                            {
                                "path": "backend-hormonia/app/api/websockets.py",
                                "anchors": [
                                    {
                                        "type": "literal",
                                        "pattern": "query_session_id=query_session_id",
                                        "label": "backend_ws_query_anchor",
                                    }
                                ],
                            }
                        ],
                    },
                    "frontend": {
                        "roots": ["frontend-hormonia/src"],
                        "approved": [
                            {
                                "path": "frontend-hormonia/src/lib/websocket.ts",
                                "anchors": [
                                    {
                                        "type": "literal",
                                        "pattern": "url.searchParams.set('session_id', sessionFallback)",
                                        "label": "frontend_ws_query_anchor",
                                    }
                                ],
                            }
                        ],
                    },
                },
            },
            {
                "id": "firebase_narrative",
                "matchers": [{"type": "literal", "pattern": "Firebase"}],
                "scopes": {
                    "frontend": {
                        "roots": ["frontend-hormonia/src"],
                        "approved": [
                            {
                                "path": "frontend-hormonia/src/AdminApp.tsx",
                                "anchors": [
                                    {
                                        "type": "literal",
                                        "pattern": "AuthProvider (Firebase authentication)",
                                        "label": "admin_app_anchor",
                                    }
                                ],
                            }
                        ],
                    }
                },
            },
        ],
    }


def _write_base_fixture(repo_root: Path, *, allowlist_override: dict | None = None) -> Path:
    _write_file(
        repo_root,
        "backend-hormonia/app/api/v2/routers/auth.py",
        "def resolve(request, user):\n"
        "    user_payload = {}\n"
        '    user_payload["firebase_uid"] = user.firebase_uid\n'
        '    header_id = request.headers.get("X-Session-ID")\n'
        '    auth_header = request.headers.get("Authorization")\n'
        '    if auth_header and auth_header.startswith("Bearer "):\n'
        '        return auth_header.split(" ", 1)[1]\n'
        '    return header_id\n',
    )
    _write_file(
        repo_root,
        "backend-hormonia/app/core/router_registry.py",
        'logger.info("Session authentication endpoints registered (/session)")\n',
    )
    _write_file(
        repo_root,
        "backend-hormonia/app/routers/auth_session.py",
        'router = APIRouter(prefix="/session", tags=["Session Authentication"])\n',
    )
    _write_file(
        repo_root,
        "backend-hormonia/app/api/websockets.py",
        "def connect(query_session_id):\n"
        "    return resolve_session_id(query_session_id=query_session_id)\n",
    )
    _write_file(
        repo_root,
        "frontend-hormonia/src/lib/api-client/core.ts",
        "export function getSessionHeaders(token: string) {\n"
        "  const headers: Record<string, string> = {}\n"
        "  headers['Authorization'] = `Bearer ${token}`\n"
        "  headers['X-Session-ID'] = token\n"
        "  return headers\n"
        "}\n",
    )
    _write_file(
        repo_root,
        "frontend-hormonia/src/lib/websocket.ts",
        "export function buildWebSocketUrl(url: URL, sessionFallback: string) {\n"
        "  url.searchParams.set('session_id', sessionFallback)\n"
        "  return url.toString()\n"
        "}\n",
    )
    _write_file(
        repo_root,
        "frontend-hormonia/src/AdminApp.tsx",
        "/**\n"
        " * - AuthProvider (Firebase authentication)\n"
        " */\n"
        "export default function AdminApp() { return null }\n",
    )

    allowlist_path = repo_root / ".gsd" / "milestones" / "M004" / "slices" / "S01" / "runtime-residue-allowlist.json"
    allowlist_path.parent.mkdir(parents=True, exist_ok=True)
    allowlist = allowlist_override or _fixture_allowlist()
    allowlist_path.write_text(json.dumps(allowlist, indent=2), encoding="utf-8")
    return allowlist_path


def _run_guard(repo_root: Path, allowlist_path: Path, mode: str, scope: str) -> subprocess.CompletedProcess[str]:
    assert SCRIPT_PATH.exists(), f"Guard script not found: {SCRIPT_PATH}"
    env = os.environ.copy()
    env["RUNTIME_RESIDUE_REPO_ROOT"] = str(repo_root)
    env["RUNTIME_RESIDUE_ALLOWLIST"] = str(allowlist_path)
    return subprocess.run(
        ["bash", str(SCRIPT_PATH), mode, scope],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        env=env,
        check=False,
    )


def test_approved_compat_island_passes_check_and_report(tmp_path: Path) -> None:
    allowlist_path = _write_base_fixture(tmp_path)

    report = _run_guard(tmp_path, allowlist_path, "--report", "all")
    check = _run_guard(tmp_path, allowlist_path, "--check", "all")

    assert report.returncode == 0
    assert check.returncode == 0
    assert "category=firebase_uid file=backend-hormonia/app/api/v2/routers/auth.py" in report.stdout
    assert "category=x_session_id file=frontend-hormonia/src/lib/api-client/core.ts" in report.stdout
    assert "category=websocket_session_id_query file=backend-hormonia/app/api/websockets.py" in report.stdout
    assert "RESULT: --check all OK" in check.stdout


@pytest.mark.parametrize(
    ("category", "relative_path", "content"),
    [
        (
            "x_session_id",
            "backend-hormonia/app/new_header.py",
            'x_session_id = Header(None, alias="X-Session-ID")\n',
        ),
        (
            "session_bearer_fallback",
            "backend-hormonia/app/new_bearer.py",
            'if authorization and authorization.startswith("Bearer "):\n    return authorization\n',
        ),
        (
            "websocket_session_id_query",
            "frontend-hormonia/src/new_query.ts",
            "url.searchParams.set('session_id', sessionFallback)\n",
        ),
        (
            "firebase_narrative",
            "frontend-hormonia/src/new_narrative.tsx",
            "// Firebase handles token refresh automatically\n",
        ),
    ],
)
def test_unexpected_residue_fails_with_category_and_path(
    tmp_path: Path,
    category: str,
    relative_path: str,
    content: str,
) -> None:
    allowlist_path = _write_base_fixture(tmp_path)
    _write_file(tmp_path, relative_path, content)

    result = _run_guard(tmp_path, allowlist_path, "--check", "all")

    assert result.returncode == 1
    assert f"category={category}" in result.stdout
    assert relative_path in result.stdout
    assert "unexpected_file=" in result.stdout


def test_scope_handling_ignores_other_runtime_half(tmp_path: Path) -> None:
    allowlist_path = _write_base_fixture(tmp_path)
    _write_file(
        tmp_path,
        "frontend-hormonia/src/frontend_only_drift.ts",
        'headers["X-Session-ID"] = token\n',
    )

    backend_check = _run_guard(tmp_path, allowlist_path, "--check", "backend")
    frontend_check = _run_guard(tmp_path, allowlist_path, "--check", "frontend")
    backend_report = _run_guard(tmp_path, allowlist_path, "--report", "backend")

    assert backend_check.returncode == 0
    assert frontend_check.returncode == 1
    assert "frontend_only_drift.ts" not in backend_report.stdout
    assert "frontend_only_drift.ts" in frontend_check.stdout


def test_proof_only_boundary_passes_check_and_reports_separately(tmp_path: Path) -> None:
    base_allowlist = _fixture_allowlist()
    x_session_category = json.loads(
        json.dumps(
            next(
                category
                for category in base_allowlist["categories"]
                if category["id"] == "x_session_id"
            )
        )
    )
    x_session_category["scopes"]["backend"]["approved"] = []
    x_session_category["scopes"]["backend"]["proof_only"] = [
        {
            "path": "backend-hormonia/app/api/v2/routers/auth.py",
            "proof": "backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py::test_verify_session_rejects_legacy_transport_without_cookie",
            "anchors": [
                {
                    "type": "literal",
                    "pattern": 'header_id = request.headers.get("X-Session-ID")',
                    "label": "auth_header_proof_boundary",
                }
            ],
        }
    ]
    allowlist = {
        "schema_version": 1,
        "scope_defaults": base_allowlist["scope_defaults"],
        "categories": [x_session_category],
    }

    allowlist_path = _write_base_fixture(tmp_path, allowlist_override=allowlist)
    report = _run_guard(tmp_path, allowlist_path, "--report", "backend")
    check = _run_guard(tmp_path, allowlist_path, "--check", "backend")

    assert report.returncode == 0
    assert check.returncode == 0
    assert "[backend]" in report.stdout
    assert "  - no approved residue" in report.stdout
    assert "[backend-proof-only]" in report.stdout
    assert "category=x_session_id file=backend-hormonia/app/api/v2/routers/auth.py" in report.stdout
    assert "proof=backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py::test_verify_session_rejects_legacy_transport_without_cookie" in report.stdout


def test_moved_proof_boundary_reports_anchor_name(tmp_path: Path) -> None:
    base_allowlist = _fixture_allowlist()
    x_session_category = json.loads(
        json.dumps(
            next(
                category
                for category in base_allowlist["categories"]
                if category["id"] == "x_session_id"
            )
        )
    )
    x_session_category["scopes"]["backend"]["approved"] = []
    x_session_category["scopes"]["backend"]["proof_only"] = [
        {
            "path": "backend-hormonia/app/api/v2/routers/auth.py",
            "anchors": [
                {
                    "type": "literal",
                    "pattern": 'header_id = request.headers.get("X-Session-ID")',
                    "label": "auth_header_proof_boundary",
                }
            ],
        }
    ]
    allowlist = {
        "schema_version": 1,
        "scope_defaults": base_allowlist["scope_defaults"],
        "categories": [x_session_category],
    }

    allowlist_path = _write_base_fixture(tmp_path, allowlist_override=allowlist)
    _write_file(
        tmp_path,
        "backend-hormonia/app/api/v2/routers/auth.py",
        'def resolve(request, user):\n'
        '    legacy_header = request.headers.get("X-Session-ID")\n',
    )

    result = _run_guard(tmp_path, allowlist_path, "--check", "backend")

    assert result.returncode == 1
    assert "category=x_session_id" in result.stdout
    assert "moved_proof_boundary=backend-hormonia/app/api/v2/routers/auth.py" in result.stdout
    assert "anchor=auth_header_proof_boundary" in result.stdout


def test_moved_hotspot_reports_anchor_name(tmp_path: Path) -> None:
    allowlist_path = _write_base_fixture(tmp_path)
    _write_file(
        tmp_path,
        "frontend-hormonia/src/AdminApp.tsx",
        "// Firebase narrative still present but the approved anchor moved\n",
    )

    result = _run_guard(tmp_path, allowlist_path, "--check", "frontend")

    assert result.returncode == 1
    assert "category=firebase_narrative" in result.stdout
    assert "moved_hotspot=frontend-hormonia/src/AdminApp.tsx" in result.stdout
    assert "anchor=admin_app_anchor" in result.stdout
