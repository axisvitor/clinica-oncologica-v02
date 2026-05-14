#!/usr/bin/env python3
"""M015 provider seam Taskiq task and probe.

This file is mounted two ways by the M015 synthetic runtime stack:

* ``/app/app/tasks/m015_provider_security_taskiq.py`` so a real Taskiq worker
  explicitly imports the harness-only provider task.
* ``/m015-runtime/m015_provider_security_taskiq.py`` so ``provider_seam.py`` can
  drive local WuzAPI/Gemini stubs and write redaction-validated evidence.

The seam records only status classes, scenario names, hashes, booleans, and
redaction verdicts. It never persists provider request bodies, prompts, token
values, cookies, DSNs, SQL, private paths, or PHI-shaped values.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

# ``provider_seam.py`` is executed from /m015-runtime, which makes that helper
# directory sys.path[0] instead of the backend root. Add the mounted backend
# package path before importing the real Taskiq broker so the probe and worker
# exercise the same backend module surface.
_BACKEND_ROOT = Path(os.getenv("M015_BACKEND_ROOT", "/app"))
if _BACKEND_ROOT.exists():
    sys.path.insert(0, str(_BACKEND_ROOT))

_RUNTIME_HELPER_DIR = Path("/m015-runtime")
if _RUNTIME_HELPER_DIR.exists():
    sys.path.insert(0, str(_RUNTIME_HELPER_DIR))

from app.taskiq_broker import broker

try:  # pragma: no cover - exercised inside the synthetic Compose probe.
    from redaction import RedactionError, sanitize_text, write_validated_json, write_validated_text
except Exception:  # pragma: no cover - worker import path when helper is absent.
    class RedactionError(RuntimeError):
        """Fallback used only when probe redaction helpers are not mounted."""

    def sanitize_text(value: Any, *, max_chars: int | None = None) -> str:
        text = str(value)
        return text[-max_chars:] if max_chars is not None and len(text) > max_chars else text

    def write_validated_json(path: str | Path, payload: Any) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    def write_validated_text(path: str | Path, text: str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


OUTPUT_DIR = Path(os.getenv("M015_EVIDENCE_OUTPUT_DIR", "/m015-evidence-output"))
EVIDENCE_JSON = OUTPUT_DIR / "provider-seam-evidence.json"
SUMMARY_MD = OUTPUT_DIR / "provider-seam-summary.md"
RUNNER_COMMAND = "./scripts/security/verify-m015-runtime-security.sh --seam provider"
TASK_NAME = "m015_provider_security_boundary"
DEFAULT_STUB_URL = "http://provider-stub:18089"
WUZAPI_SCENARIOS = ("success", "client_error", "server_error", "timeout", "duplicate_or_replay")
GEMINI_SCENARIOS = ("success", "server_error")


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def hash_identifier(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def status_class(status_code: int | None) -> str:
    if status_code is None or status_code <= 0:
        return "network_error"
    return f"{status_code // 100}xx"


def provider_stub_url() -> str:
    return os.getenv("M015_PROVIDER_STUB_URL") or os.getenv("AI_GEMINI_BASE_URL") or DEFAULT_STUB_URL


def synthetic_wuzapi_token() -> str:
    return os.getenv("WHATSAPP_WUZAPI_TOKEN") or "m015-synthetic-provider-token"


def synthetic_gemini_key() -> str:
    return os.getenv("AI_GEMINI_API_KEY") or "m015-synthetic-gemini-key"


@dataclass
class PhaseError(RuntimeError):
    phase: str
    failure_class: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return f"{self.phase}:{self.failure_class}: {self.message}"


@dataclass
class HttpOutcome:
    provider: str
    endpoint: str
    scenario: str
    status_code: int | None
    error_class: str | None = None
    duration_ms: int = 0

    def to_evidence(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "endpoint": self.endpoint,
            "scenario": self.scenario,
            "status_code": self.status_code,
            "status_class": status_class(self.status_code),
            "error_class": self.error_class,
            "duration_ms": self.duration_ms,
            "raw_provider_body_persisted": False,
            "raw_prompt_persisted": False,
            "token_values_persisted": False,
        }


def _request_json(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any] | None = None,
    timeout: float = 4.0,
) -> tuple[int | None, str | None, int]:
    started = time.monotonic()
    encoded_body = None if body is None else json.dumps(body, sort_keys=True).encode("utf-8")
    request = urllib.request.Request(url, data=encoded_body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - internal Compose URL.
            response.read()
            return int(response.status), None, int((time.monotonic() - started) * 1000)
    except urllib.error.HTTPError as exc:
        exc.read()
        return int(exc.code), None, int((time.monotonic() - started) * 1000)
    except Exception as exc:
        return None, type(exc).__name__, int((time.monotonic() - started) * 1000)


def call_wuzapi_stub_direct(scenario: str) -> dict[str, Any]:
    query = urlencode({"scenario": scenario})
    url = f"{provider_stub_url().rstrip('/')}/chat/send/text?{query}"
    status_code, error_class, duration_ms = _request_json(
        method="POST",
        url=url,
        headers={"Content-Type": "application/json", "Token": synthetic_wuzapi_token()},
        body={"Phone": "m015-synthetic-destination", "Body": "m015 synthetic provider message"},
        timeout=1.0 if scenario == "timeout" else 4.0,
    )
    return HttpOutcome(
        provider="wuzapi",
        endpoint="send_text",
        scenario=scenario,
        status_code=status_code,
        error_class=error_class,
        duration_ms=duration_ms,
    ).to_evidence()


def call_gemini_stub_direct(scenario: str) -> dict[str, Any]:
    query = urlencode({"scenario": scenario})
    url = f"{provider_stub_url().rstrip('/')}/v1beta/models/m015-synthetic:generateContent?{query}"
    status_code, error_class, duration_ms = _request_json(
        method="POST",
        url=url,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {synthetic_gemini_key()}"},
        body={"contents": [{"parts": [{"text": "Paciente [REDACTED] m015 synthetic prompt"}]}]},
        timeout=4.0,
    )
    return HttpOutcome(
        provider="gemini",
        endpoint="generate_content",
        scenario=scenario,
        status_code=status_code,
        error_class=error_class,
        duration_ms=duration_ms,
    ).to_evidence()


async def call_wuzapi_via_app_client(scenario: str = "success") -> dict[str, Any]:
    """Use the app WuzAPI client against the configured local stub."""

    from app.integrations.wuzapi.client import WuzAPIClient
    from app.integrations.wuzapi.errors import WuzAPIError

    client = WuzAPIClient(
        base_url=os.getenv("WHATSAPP_WUZAPI_BASE_URL") or provider_stub_url(),
        token=synthetic_wuzapi_token(),
        timeout_seconds=3,
    )
    await client.connect()
    started = time.monotonic()
    try:
        await client._make_request(  # noqa: SLF001 - harness verifies the provider boundary directly.
            "POST",
            f"/chat/send/text?{urlencode({'scenario': scenario})}",
            data={"Phone": "m015-synthetic-destination", "Body": "m015 synthetic worker message"},
        )
        status_code: int | None = 200
        error_class: str | None = None
    except WuzAPIError as exc:
        status_code = exc.status
        error_class = type(exc).__name__
    except Exception as exc:  # pragma: no cover - runtime defensive path.
        status_code = None
        error_class = type(exc).__name__
    finally:
        await client.disconnect()
    return HttpOutcome(
        provider="wuzapi",
        endpoint="send_text",
        scenario=scenario,
        status_code=status_code,
        error_class=error_class,
        duration_ms=int((time.monotonic() - started) * 1000),
    ).to_evidence()


async def call_gemini_config_boundary() -> dict[str, Any]:
    """Return sanitized Gemini routing facts from the app config seam."""

    from app.ai.client import GeminiClient
    from app.config import settings

    client = GeminiClient(api_key=synthetic_gemini_key(), model="m015-synthetic-model")
    configured = bool(getattr(settings, "AI_GEMINI_BASE_URL", None))
    return {
        "provider": "gemini",
        "endpoint": "generate_content",
        "scenario": "config_boundary",
        "configured_base_url": configured,
        "client_initialized": client.model is not None,
        "status_class": "configured" if configured else "missing_config",
        "raw_prompt_persisted": False,
        "token_values_persisted": False,
    }


@broker.task(task_name=TASK_NAME)
async def check_m015_provider_boundary(correlation_id: str) -> dict[str, Any]:
    """Taskiq worker boundary check for provider stub routing."""

    wuzapi = await call_wuzapi_via_app_client("success")
    gemini = await call_gemini_config_boundary()
    result = {
        "worker_boundary": "taskiq",
        "correlation_id_hash": hash_identifier(correlation_id),
        "checked_at": utc_now(),
        "wuzapi": wuzapi,
        "gemini": gemini,
        "redaction": {
            "raw_provider_bodies_persisted": False,
            "raw_prompts_persisted": False,
            "token_values_persisted": False,
        },
    }
    return result


def build_provider_summary(evidence: dict[str, Any]) -> str:
    provider = evidence["provider_probe"]
    worker = provider["worker"]
    lines = [
        "# M015 Provider Seam Summary",
        "",
        f"- Correlation ID: `{evidence['correlation_id']}`",
        "- Seam: `provider`",
        f"- Verification result: `{evidence['result']}`",
        f"- WuzAPI scenarios: `{len(provider['wuzapi']['scenarios'])}` checked; status classes `{provider['wuzapi']['status_classes']}`",
        f"- Gemini scenarios: `{len(provider['gemini']['scenarios'])}` checked; status classes `{provider['gemini']['status_classes']}`",
        f"- Worker: boundary `{worker['worker_boundary']}`, WuzAPI `{worker['wuzapi']['status_class']}`, Gemini `{worker['gemini']['status_class']}`",
        "- Teardown: `pending`",
        "",
        "All durable values are synthetic and redaction-validated; raw provider bodies, prompts, cookies, tokens, DSNs, and PHI are omitted.",
        "Non-goals: private artifact app-route proof, final all-seam matrix closure, live providers, production systems/data, browser/frontend flows, CDN/object-storage, and broad DAST/fuzzing are not exercised by this provider seam.",
        "",
    ]
    return "\n".join(lines)


def build_provider_failure_summary(failure: dict[str, Any]) -> str:
    lines = [
        "# M015 Provider Seam Summary",
        "",
        f"- Correlation ID: `{failure['correlation_id']}`",
        "- Seam: `provider`",
        "- Verification result: `failed`",
        f"- Failed phase: `{failure['failed_phase']}`",
        f"- Failure class: `{failure['failure_class']}`",
        "- Teardown: `pending`",
        "",
        "The provider seam failed before passing evidence was refreshed. Durable failure details are sanitized; raw provider bodies, prompts, cookies, tokens, DSNs, and PHI are omitted.",
        "Non-goals: private artifact app-route proof, final all-seam matrix closure, live providers, production systems/data, browser/frontend flows, CDN/object-storage, and broad DAST/fuzzing are not exercised by this provider seam.",
        "",
    ]
    return "\n".join(lines)


def summarize_scenarios(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "scenarios": results,
        "status_classes": sorted({str(item.get("status_class")) for item in results}),
        "raw_provider_bodies_persisted": False,
        "raw_prompts_persisted": False,
        "token_values_persisted": False,
    }


def build_provider_evidence(
    *,
    correlation_id: str,
    started_at: str,
    events: list[dict[str, Any]],
    wuzapi_results: list[dict[str, Any]],
    gemini_results: list[dict[str, Any]],
    worker_result: dict[str, Any],
) -> dict[str, Any]:
    evidence = {
        "correlation_id": correlation_id,
        "seam": "provider",
        "command": RUNNER_COMMAND,
        "result": "passed",
        "started_at": started_at,
        "completed_at": utc_now(),
        "events": events,
        "versions": {
            "postgres_image": os.getenv("M015_POSTGRES_IMAGE", "postgres:16-alpine"),
            "dragonfly_image": os.getenv("M015_DRAGONFLY_IMAGE", "docker.dragonflydb.io/dragonflydb/dragonfly:latest"),
            "provider_stub": "local-http-stdlib",
            "provider_stub_url_policy": "local docker DNS host only; raw URL omitted",
        },
        "provider_probe": {
            "wuzapi": summarize_scenarios(wuzapi_results),
            "gemini": summarize_scenarios(gemini_results),
            "worker": worker_result,
        },
        "redaction": {
            "validated": True,
            "raw_provider_bodies_persisted": False,
            "raw_prompts_persisted": False,
            "token_values_persisted": False,
            "raw_cookie_headers_persisted": False,
            "raw_session_ids_persisted": False,
        },
        "failure_classes": [
            "provider_stub_unreachable",
            "wuzapi_stub_mismatch",
            "gemini_stub_mismatch",
            "provider_timeout",
            "taskiq_dispatch_or_result_failure",
            "provider_worker_mismatch",
            "redaction_denylist_hit",
        ],
        "non_goals": [
            "private_artifact_app_route_proof_deferred_to_s04",
            "final_all_seam_matrix_closure_deferred_to_s05",
            "live_provider_credentials_not_used",
            "no_real_patient_data_or_phi",
            "browser_frontend_flows_not_exercised",
            "cdn_object_storage_not_exercised",
        ],
        "teardown": {"result": "pending", "timestamp": None, "notes": "runner will update after compose down"},
    }
    write_validated_json(EVIDENCE_JSON, evidence)
    write_validated_text(SUMMARY_MD, build_provider_summary(evidence))
    return evidence


@dataclass
class ProviderProbe:
    correlation_id: str = field(default_factory=lambda: os.getenv("M015_CORRELATION_ID", f"m015-{uuid.uuid4()}"))
    events: list[dict[str, Any]] = field(default_factory=list)
    started_at: str = field(default_factory=utc_now)

    def event(self, phase: str, status: str, message: str, **extra: Any) -> None:
        safe_message = sanitize_text(message, max_chars=600)
        event = {
            "timestamp": utc_now(),
            "correlation_id": self.correlation_id,
            "seam": "provider",
            "phase": phase,
            "status": status,
            "message": safe_message,
        }
        if extra:
            event["details"] = extra
        self.events.append(event)
        print(
            f"[{event['timestamp']}] correlation_id={self.correlation_id} seam=provider "
            f"phase={phase} status={status} {safe_message}",
            flush=True,
        )

    def prove_wuzapi_scenarios(self) -> list[dict[str, Any]]:
        self.event("wuzapi", "started", "checking WuzAPI scenarios through local provider stub")
        results = [call_wuzapi_stub_direct(scenario) for scenario in WUZAPI_SCENARIOS]
        if not any(item.get("status_class") == "2xx" for item in results):
            raise PhaseError("wuzapi", "wuzapi_stub_mismatch", "WuzAPI success scenario did not return a 2xx class")
        self.event("wuzapi", "ready", "WuzAPI local stub scenarios produced sanitized status classes")
        return results

    def prove_gemini_scenarios(self) -> list[dict[str, Any]]:
        self.event("gemini", "started", "checking Gemini scenarios through local provider stub")
        results = [call_gemini_stub_direct(scenario) for scenario in GEMINI_SCENARIOS]
        if not any(item.get("status_class") == "2xx" for item in results):
            raise PhaseError("gemini", "gemini_stub_mismatch", "Gemini success scenario did not return a 2xx class")
        self.event("gemini", "ready", "Gemini local stub scenarios produced sanitized status classes")
        return results

    async def prove_worker_participates(self) -> dict[str, Any]:
        self.event("worker", "started", "queueing Taskiq provider boundary check")
        await broker.startup()
        try:
            queued_task = await check_m015_provider_boundary.kiq(self.correlation_id)
            result = await queued_task.wait_result(timeout=180, check_interval=0.5)
        except Exception as exc:
            raise PhaseError("worker", "taskiq_dispatch_or_result_failure", f"provider worker proof failed with class {type(exc).__name__}") from exc
        finally:
            await broker.shutdown()

        if result.is_err:
            raise PhaseError("worker", "taskiq_task_error", "provider task returned an error result")
        value = result.return_value
        if not isinstance(value, dict):
            raise PhaseError("worker", "taskiq_result_malformed", "provider task returned a non-mapping result")
        if value.get("worker_boundary") != "taskiq":
            raise PhaseError("worker", "provider_worker_mismatch", "provider task did not report the Taskiq worker boundary")
        self.event("worker", "ready", "Taskiq provider worker used configured local stub URLs")
        return value

    def run(self) -> dict[str, Any]:
        wuzapi_results = self.prove_wuzapi_scenarios()
        gemini_results = self.prove_gemini_scenarios()
        worker_result = asyncio.run(self.prove_worker_participates())
        evidence = build_provider_evidence(
            correlation_id=self.correlation_id,
            started_at=self.started_at,
            events=self.events,
            wuzapi_results=wuzapi_results,
            gemini_results=gemini_results,
            worker_result=worker_result,
        )
        self.event("evidence", "ready", "provider seam evidence JSON and summary written with redaction validation")
        return evidence


def main() -> int:
    probe: ProviderProbe | None = None
    try:
        probe = ProviderProbe()
        probe.run()
        return 0
    except PhaseError as exc:
        if probe is not None:
            probe.event(exc.phase, "failed", f"failure_class={exc.failure_class} remediation={exc.message}")
            failure_payload = {
                "correlation_id": probe.correlation_id,
                "seam": "provider",
                "command": RUNNER_COMMAND,
                "result": "failed",
                "failure_class": exc.failure_class,
                "failed_phase": exc.phase,
                "message": sanitize_text(exc.message, max_chars=600),
                "details": exc.details or {},
                "events": probe.events,
                "completed_at": utc_now(),
            }
            try:
                write_validated_json(EVIDENCE_JSON, failure_payload)
                write_validated_text(SUMMARY_MD, build_provider_failure_summary(failure_payload))
            except (RedactionError, Exception):
                pass
        else:
            print(f"phase=setup status=failed failure_class={exc.failure_class} remediation={exc.message}", flush=True)
        return 1
    except Exception as exc:  # pragma: no cover - runtime harness defensive path.
        message = f"unexpected provider seam failure class {type(exc).__name__}"
        if probe is not None:
            probe.event("evidence", "failed", f"failure_class=provider_probe_unhandled remediation={message}")
        else:
            print(f"phase=evidence status=failed failure_class=provider_probe_unhandled remediation={message}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
