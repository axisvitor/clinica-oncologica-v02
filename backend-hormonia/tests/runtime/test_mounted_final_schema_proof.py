from __future__ import annotations

import json
import os
from dataclasses import dataclass

import pytest
import requests


pytestmark = [pytest.mark.integration, pytest.mark.auth]


@dataclass(frozen=True)
class MountedProofConfig:
    base_url: str
    email: str
    password: str
    history: str
    timeout_seconds: float


@pytest.fixture(scope="session")
def mounted_proof_config() -> MountedProofConfig:
    base_url = os.getenv("MOUNTED_PROOF_BASE_URL", "").rstrip("/")
    email = os.getenv("MOUNTED_PROOF_EMAIL", "")
    password = os.getenv("MOUNTED_PROOF_PASSWORD", "")
    history = os.getenv("MOUNTED_PROOF_HISTORY", "mounted")
    timeout_seconds = float(os.getenv("MOUNTED_PROOF_TIMEOUT_SECONDS", "15"))

    if not base_url or not email or not password:
        pytest.skip(
            "mounted final-schema proof requires MOUNTED_PROOF_BASE_URL, "
            "MOUNTED_PROOF_EMAIL, and MOUNTED_PROOF_PASSWORD"
        )

    return MountedProofConfig(
        base_url=base_url,
        email=email,
        password=password,
        history=history,
        timeout_seconds=timeout_seconds,
    )


@pytest.fixture()
def live_session() -> requests.Session:
    session = requests.Session()
    try:
        yield session
    finally:
        session.close()


def _json_response(
    response: requests.Response,
    *,
    expected_status: int,
    assertion: str,
    config: MountedProofConfig,
) -> dict:
    assert response.status_code == expected_status, (
        f"{assertion} history={config.history} status={response.status_code} "
        f"body={response.text}"
    )
    try:
        return response.json()
    except ValueError as exc:
        raise AssertionError(
            f"{assertion} history={config.history} non_json_body={response.text}"
        ) from exc


def test_runtime_ready_surface(mounted_proof_config: MountedProofConfig) -> None:
    response = requests.get(
        f"{mounted_proof_config.base_url}/health/ready",
        timeout=mounted_proof_config.timeout_seconds,
    )
    payload = _json_response(
        response,
        expected_status=200,
        assertion="runtime_ready",
        config=mounted_proof_config,
    )

    dependencies = payload.get("dependencies") or []
    assert payload.get("status") == "ready", (
        f"runtime_ready history={mounted_proof_config.history} payload={payload}"
    )
    assert "session_auth" in dependencies, (
        f"runtime_ready history={mounted_proof_config.history} dependencies={dependencies}"
    )
    assert "firebase" not in dependencies, (
        f"runtime_ready history={mounted_proof_config.history} dependencies={dependencies}"
    )


def test_runtime_config_surface(mounted_proof_config: MountedProofConfig) -> None:
    response = requests.get(
        f"{mounted_proof_config.base_url}/api/v2/system/config",
        timeout=mounted_proof_config.timeout_seconds,
    )
    payload = _json_response(
        response,
        expected_status=200,
        assertion="runtime_config",
        config=mounted_proof_config,
    )

    assert all(not key.startswith("VITE_FIREBASE_") for key in payload.keys()), (
        f"runtime_config history={mounted_proof_config.history} keys={sorted(payload.keys())}"
    )
    assert "firebase" not in json.dumps(payload).lower(), (
        f"runtime_config history={mounted_proof_config.history} payload={payload}"
    )


def test_live_session_flow(
    mounted_proof_config: MountedProofConfig,
    live_session: requests.Session,
) -> None:
    login_response = live_session.post(
        f"{mounted_proof_config.base_url}/api/v2/auth/login",
        json={
            "email": mounted_proof_config.email,
            "password": mounted_proof_config.password,
            "remember_me": False,
        },
        timeout=mounted_proof_config.timeout_seconds,
    )
    login_payload = _json_response(
        login_response,
        expected_status=200,
        assertion="live_session_flow step=login",
        config=mounted_proof_config,
    )

    assert login_payload.get("valid") is True, (
        f"live_session_flow history={mounted_proof_config.history} step=login payload={login_payload}"
    )
    assert login_payload.get("user", {}).get("email") == mounted_proof_config.email, (
        f"live_session_flow history={mounted_proof_config.history} step=login payload={login_payload}"
    )
    assert login_payload.get("session_id"), (
        f"live_session_flow history={mounted_proof_config.history} step=login payload={login_payload}"
    )
    assert live_session.cookies, (
        f"live_session_flow history={mounted_proof_config.history} step=login cookie_jar_empty=true"
    )

    verify_response = live_session.get(
        f"{mounted_proof_config.base_url}/api/v2/auth/verify-session",
        timeout=mounted_proof_config.timeout_seconds,
    )
    verify_payload = _json_response(
        verify_response,
        expected_status=200,
        assertion="live_session_flow step=verify_session",
        config=mounted_proof_config,
    )

    assert verify_payload.get("user", {}).get("email") == mounted_proof_config.email, (
        f"live_session_flow history={mounted_proof_config.history} step=verify_session payload={verify_payload}"
    )
    assert verify_payload.get("valid") is True, (
        f"live_session_flow history={mounted_proof_config.history} step=verify_session payload={verify_payload}"
    )

    me_response = live_session.get(
        f"{mounted_proof_config.base_url}/api/v2/users/me",
        timeout=mounted_proof_config.timeout_seconds,
    )
    me_payload = _json_response(
        me_response,
        expected_status=200,
        assertion="live_session_flow step=users_me",
        config=mounted_proof_config,
    )

    assert me_payload.get("email") == mounted_proof_config.email, (
        f"live_session_flow history={mounted_proof_config.history} step=users_me payload={me_payload}"
    )
    assert me_payload.get("is_active") is True, (
        f"live_session_flow history={mounted_proof_config.history} step=users_me payload={me_payload}"
    )

    logout_response = live_session.delete(
        f"{mounted_proof_config.base_url}/api/v2/auth/logout",
        timeout=mounted_proof_config.timeout_seconds,
    )
    logout_payload = _json_response(
        logout_response,
        expected_status=200,
        assertion="live_session_flow step=logout",
        config=mounted_proof_config,
    )

    assert logout_payload == {"message": "Logged out successfully", "success": True}, (
        f"live_session_flow history={mounted_proof_config.history} step=logout payload={logout_payload}"
    )

    revoked_response = live_session.get(
        f"{mounted_proof_config.base_url}/api/v2/auth/verify-session",
        timeout=mounted_proof_config.timeout_seconds,
    )
    revoked_payload = _json_response(
        revoked_response,
        expected_status=401,
        assertion="live_session_flow step=verify_after_logout",
        config=mounted_proof_config,
    )

    assert revoked_payload.get("message") in {"Session cookie required", "Session expired"}, (
        f"live_session_flow history={mounted_proof_config.history} "
        f"step=verify_after_logout payload={revoked_payload}"
    )
