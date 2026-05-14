#!/usr/bin/env python3
"""Synthetic WuzAPI/Gemini HTTP stubs for M015 provider runtime proof.

The stub is deliberately small and deterministic. It exists to prove that the
backend and Taskiq worker call configured network endpoints without touching live
providers or persisting provider payloads. Durable observations are reduced to
scenario names, endpoint classes, status classes, hashes, and redaction verdicts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit

from redaction import validate_no_sensitive_evidence


DEFAULT_TIMEOUT_DELAY_SECONDS = 2.0
SAFE_HEADER_NAMES = frozenset({"token", "authorization", "cookie", "set-cookie"})


@dataclass(frozen=True)
class StubResponse:
    """Provider-stub response plus sanitized observation metadata."""

    status_code: int
    body: dict[str, Any]
    headers: dict[str, str]
    delay_seconds: float
    observation: dict[str, Any]


def _header_value(headers: Mapping[str, str], name: str) -> str | None:
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return None


def _header_present(headers: Mapping[str, str], name: str) -> bool:
    value = _header_value(headers, name)
    return bool(value and value.strip())


def _request_body_hash(body: bytes) -> str | None:
    if not body:
        return None
    return hashlib.sha256(body).hexdigest()


def _status_class(status_code: int) -> str:
    return f"{status_code // 100}xx"


def provider_for_path(path: str) -> str:
    """Return the provider family for a request path."""

    split = urlsplit(path)
    lowered = split.path.lower()
    if "generatecontent" in lowered or lowered.startswith(("/v1", "/v1beta", "/gemini")):
        return "gemini"
    if lowered.startswith(("/chat/", "/session/", "/message/", "/webhook/", "/wuzapi/")):
        return "wuzapi"
    return "unknown"


def endpoint_name_for_path(path: str) -> str:
    """Return a stable endpoint class without persisting query strings."""

    lowered = urlsplit(path).path.lower()
    if "generatecontent" in lowered:
        return "generate_content"
    if lowered.endswith("/chat/send/text") or lowered == "/chat/send/text":
        return "send_text"
    if lowered.endswith("/session/status") or lowered == "/session/status":
        return "session_status"
    if lowered.endswith("/session/connect") or lowered == "/session/connect":
        return "session_connect"
    if lowered.endswith("/session/qr") or lowered == "/session/qr":
        return "session_qr"
    return "generic"


def scenario_from_request(path: str, headers: Mapping[str, str]) -> str:
    """Resolve deterministic scenario from query string or header."""

    split = urlsplit(path)
    query = parse_qs(split.query)
    raw = (query.get("scenario") or [None])[0] or _header_value(headers, "X-M015-Scenario") or "success"
    scenario = raw.strip().lower().replace("-", "_")
    aliases = {
        "ok": "success",
        "2xx": "success",
        "400": "client_error",
        "4xx": "client_error",
        "provider_4xx": "client_error",
        "429": "rate_limited",
        "rate_limit": "rate_limited",
        "500": "server_error",
        "5xx": "server_error",
        "provider_5xx": "server_error",
        "duplicate": "duplicate_or_replay",
        "replay": "duplicate_or_replay",
    }
    return aliases.get(scenario, scenario)


def _response_body(provider: str, endpoint: str, scenario: str, status_code: int) -> dict[str, Any]:
    """Return synthetic provider response body. This body is not persisted."""

    if provider == "gemini" and status_code < 400:
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "m015 synthetic gemini response"}],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 3,
                "candidatesTokenCount": 4,
                "totalTokenCount": 7,
            },
        }
    if provider == "wuzapi" and status_code < 400:
        if endpoint == "session_status":
            return {"connected": True, "loggedIn": True, "status": "connected"}
        return {
            "success": True,
            "message": "m015 synthetic wuzapi response",
            "messageId": "m015-synthetic-message",
        }
    return {
        "success": False,
        "error": f"m015_synthetic_{scenario}",
        "status_class": _status_class(status_code),
    }


def _scenario_status(provider: str, scenario: str, headers: Mapping[str, str]) -> tuple[int, float, str]:
    if provider == "unknown":
        return 404, 0.0, "unknown_endpoint"
    if provider == "wuzapi" and not _header_present(headers, "Token"):
        return 401, 0.0, "missing_token_header"
    if scenario == "success":
        return 200, 0.0, "success"
    if scenario == "client_error":
        return 400, 0.0, "client_error"
    if scenario == "rate_limited":
        return 429, 0.0, "rate_limited"
    if scenario == "server_error":
        return 503, 0.0, "server_error"
    if scenario == "timeout":
        return 504, DEFAULT_TIMEOUT_DELAY_SECONDS, "timeout"
    if scenario == "duplicate_or_replay":
        return 409, 0.0, "duplicate_or_replay"
    return 400, 0.0, "unknown_scenario"


def build_observation(
    *,
    method: str,
    path: str,
    headers: Mapping[str, str],
    body: bytes,
    scenario: str,
    status_code: int,
    reason: str,
) -> dict[str, Any]:
    """Build redaction-safe observation for durable evidence."""

    provider = provider_for_path(path)
    endpoint = endpoint_name_for_path(path)
    observation: dict[str, Any] = {
        "provider": provider,
        "endpoint": endpoint,
        "method": method.upper(),
        "scenario": scenario,
        "status_code": status_code,
        "status_class": _status_class(status_code),
        "reason": reason,
        "token_header_present": _header_present(headers, "Token"),
        "authorization_header_present": _header_present(headers, "Authorization"),
        "cookie_header_present": _header_present(headers, "Cookie"),
        "headers_redacted": True,
        "request_body_present": bool(body),
        "request_body_sha256": _request_body_hash(body),
        "raw_headers_persisted": False,
        "raw_request_body_persisted": False,
        "redaction_validated": True,
    }
    validate_no_sensitive_evidence(observation)
    return observation


def build_stub_response(method: str, path: str, headers: Mapping[str, str], body: bytes = b"") -> StubResponse:
    """Return deterministic stub response and sanitized observation."""

    provider = provider_for_path(path)
    endpoint = endpoint_name_for_path(path)
    scenario = scenario_from_request(path, headers)
    status_code, delay_seconds, reason = _scenario_status(provider, scenario, headers)
    body_payload = _response_body(provider, endpoint, reason, status_code)
    observation = build_observation(
        method=method,
        path=path,
        headers=headers,
        body=body,
        scenario=reason,
        status_code=status_code,
        reason=reason,
    )
    response = StubResponse(
        status_code=status_code,
        body=body_payload,
        headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        delay_seconds=delay_seconds,
        observation=observation,
    )
    validate_no_sensitive_evidence(asdict(response))
    return response


def append_observation_jsonl(path: str | Path, observation: Mapping[str, Any]) -> None:
    """Append one redaction-validated observation JSON line."""

    validate_no_sensitive_evidence(observation)
    line = json.dumps(observation, sort_keys=True, ensure_ascii=False)
    validate_no_sensitive_evidence(line)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


class ProviderStubHandler(BaseHTTPRequestHandler):
    """HTTP handler used by the Docker provider-stub service."""

    server_version = "M015ProviderStub/1.0"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        self._handle()

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        self._handle()

    def _handle(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else b""
        response = build_stub_response(self.command, self.path, self.headers, body)
        observations_path = os.environ.get("M015_PROVIDER_STUB_OBSERVATIONS")
        if observations_path:
            append_observation_jsonl(observations_path, response.observation)
        if response.delay_seconds:
            time.sleep(response.delay_seconds)
        payload = json.dumps(response.body, sort_keys=True).encode("utf-8")
        self.send_response(response.status_code)
        for key, value in response.headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            # Timeout scenarios intentionally let clients fail closed before the
            # delayed synthetic response is written. Avoid noisy tracebacks while
            # preserving the already-recorded redaction-safe observation.
            return


def serve(host: str, port: int) -> None:
    httpd = ThreadingHTTPServer((host, port), ProviderStubHandler)
    httpd.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="M015 synthetic provider stub")
    parser.add_argument("--host", default=os.environ.get("M015_PROVIDER_STUB_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("M015_PROVIDER_STUB_PORT", "18089")))
    args = parser.parse_args()
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
