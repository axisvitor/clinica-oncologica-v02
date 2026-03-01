from unittest.mock import patch

import pytest

from app.middleware.lgpd_middleware import LGPDMiddleware, PATIENT_ENDPOINTS


async def _invoke_middleware(path: str) -> None:
    async def app_stub(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"OK"})

    middleware = LGPDMiddleware(app_stub, enable_db_logging=False)
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "client": ("127.0.0.1", 1234),
        "state": {},
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        return None

    await middleware(scope, receive, send)


def _patient_access_logs(mock_logger) -> list[dict]:
    logs = []
    for call in mock_logger.info.call_args_list:
        args, kwargs = call
        if args and args[0] == "LGPD: Patient data access":
            logs.append(kwargs.get("extra", {}))
    return logs


def test_patient_endpoints_excludes_legacy_v1_prefix() -> None:
    assert "/patients" in PATIENT_ENDPOINTS
    assert "/api/v2/patients" in PATIENT_ENDPOINTS
    assert "/api/v1/patients" not in PATIENT_ENDPOINTS


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/patients", "/api/v2/patients"])
async def test_logs_patient_access_for_supported_paths(path: str) -> None:
    with patch("app.middleware.lgpd_middleware.logger") as mock_logger:
        await _invoke_middleware(path)

        access_logs = _patient_access_logs(mock_logger)
        assert len(access_logs) == 1
        assert access_logs[0]["path"] == path
        assert access_logs[0]["status_code"] == 200


@pytest.mark.asyncio
async def test_does_not_log_patient_access_for_legacy_v1_path() -> None:
    with patch("app.middleware.lgpd_middleware.logger") as mock_logger:
        await _invoke_middleware("/api/v1/patients")

        assert _patient_access_logs(mock_logger) == []
