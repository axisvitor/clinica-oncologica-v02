from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
HARNESS_DIR = REPO_ROOT / "scripts" / "security" / "m015-runtime"
PROVIDER_TASK = HARNESS_DIR / "m015_provider_security_taskiq.py"
PROVIDER_SEAM = HARNESS_DIR / "provider_seam.py"
PROVIDER_STUB = HARNESS_DIR / "provider_stub.py"

sys.path.insert(0, str(HARNESS_DIR))
from redaction import RedactionError, validate_no_sensitive_evidence  # noqa: E402
import m015_provider_security_taskiq as provider_task  # noqa: E402


def _sample_http_result(provider: str, endpoint: str, scenario: str, status_code: int) -> dict[str, object]:
    return provider_task.HttpOutcome(
        provider=provider,
        endpoint=endpoint,
        scenario=scenario,
        status_code=status_code,
        error_class=None,
        duration_ms=12,
    ).to_evidence()


def test_provider_task_bootstraps_backend_before_broker_import() -> None:
    text = PROVIDER_TASK.read_text(encoding="utf-8")
    backend_bootstrap = '_BACKEND_ROOT = Path(os.getenv("M015_BACKEND_ROOT", "/app"))'
    broker_import = "from app.taskiq_broker import broker"

    assert backend_bootstrap in text
    assert "sys.path.insert(0, str(_BACKEND_ROOT))" in text
    assert text.index(backend_bootstrap) < text.index(broker_import)


def test_provider_seam_entrypoint_delegates_to_task_module() -> None:
    text = PROVIDER_SEAM.read_text(encoding="utf-8")
    assert "from m015_provider_security_taskiq import main" in text
    assert "raise SystemExit(main())" in text


def test_provider_task_uses_app_clients_and_configured_stub_boundaries() -> None:
    text = PROVIDER_TASK.read_text(encoding="utf-8")

    assert "from app.integrations.wuzapi.client import WuzAPIClient" in text
    assert "from app.ai.client import GeminiClient" in text
    assert "WHATSAPP_WUZAPI_BASE_URL" in text
    assert "AI_GEMINI_BASE_URL" in text
    assert "M015_PROVIDER_STUB_URL" in text
    assert "raw_provider_body_persisted" in text
    assert "raw_prompt_persisted" in text
    assert "token_values_persisted" in text
    assert "provider_payload" not in text
    assert "raw_payload" not in text
    assert "wait_result(timeout=180" in text
    assert "build_provider_failure_summary" in text


def test_provider_evidence_shape_is_redaction_safe(tmp_path, monkeypatch) -> None:
    evidence_json = tmp_path / "provider-seam-evidence.json"
    summary_md = tmp_path / "provider-seam-summary.md"
    monkeypatch.setattr(provider_task, "EVIDENCE_JSON", evidence_json)
    monkeypatch.setattr(provider_task, "SUMMARY_MD", summary_md)

    worker_result = {
        "worker_boundary": "taskiq",
        "correlation_id_hash": "a" * 64,
        "checked_at": "2026-05-14T00:00:00Z",
        "wuzapi": _sample_http_result("wuzapi", "send_text", "success", 200),
        "gemini": {
            "provider": "gemini",
            "endpoint": "generate_content",
            "scenario": "config_boundary",
            "configured_base_url": True,
            "client_initialized": True,
            "status_class": "configured",
            "raw_prompt_persisted": False,
            "token_values_persisted": False,
        },
        "redaction": {
            "raw_provider_bodies_persisted": False,
            "raw_prompts_persisted": False,
            "token_values_persisted": False,
        },
    }

    evidence = provider_task.build_provider_evidence(
        correlation_id="m015-provider-test",
        started_at="2026-05-14T00:00:00Z",
        events=[{"phase": "provider-probe", "status": "ready", "message": "synthetic"}],
        wuzapi_results=[
            _sample_http_result("wuzapi", "send_text", "success", 200),
            _sample_http_result("wuzapi", "send_text", "server_error", 503),
            _sample_http_result("wuzapi", "send_text", "duplicate_or_replay", 409),
        ],
        gemini_results=[
            _sample_http_result("gemini", "generate_content", "success", 200),
            _sample_http_result("gemini", "generate_content", "server_error", 503),
        ],
        worker_result=worker_result,
    )

    assert evidence["seam"] == "provider"
    assert evidence["result"] == "passed"
    assert evidence["provider_probe"]["worker"]["worker_boundary"] == "taskiq"
    assert "private_artifact_app_route_proof_deferred_to_s04" in evidence["non_goals"]
    assert evidence_json.exists()
    assert summary_md.exists()
    validate_no_sensitive_evidence(evidence)
    validate_no_sensitive_evidence(evidence_json.read_text(encoding="utf-8"))
    validate_no_sensitive_evidence(summary_md.read_text(encoding="utf-8"))

    serialized = json.dumps(evidence, sort_keys=True)
    assert "Authorization:" not in serialized
    assert "Cookie:" not in serialized
    assert "Token:" not in serialized
    assert "patient_name" not in serialized
    assert "provider_payload" not in serialized
    assert "raw_payload" not in serialized


def test_provider_http_outcome_redaction_flags_are_false() -> None:
    outcome = provider_task.HttpOutcome(
        provider="gemini",
        endpoint="generate_content",
        scenario="timeout",
        status_code=None,
        error_class="TimeoutError",
        duration_ms=1000,
    ).to_evidence()

    assert outcome["status_class"] == "network_error"
    assert outcome["raw_provider_body_persisted"] is False
    assert outcome["raw_prompt_persisted"] is False
    assert outcome["token_values_persisted"] is False
    validate_no_sensitive_evidence(outcome)


def test_redaction_still_rejects_raw_provider_payload_shapes() -> None:
    with pytest.raises(RedactionError):
        validate_no_sensitive_evidence({"provider_payload": {"patient_name": "Maria Silva"}})


def test_provider_stub_module_has_network_real_scenarios() -> None:
    text = PROVIDER_STUB.read_text(encoding="utf-8")

    for scenario in ("success", "client_error", "server_error", "timeout", "duplicate_or_replay"):
        assert scenario in text
    assert "ThreadingHTTPServer" in text
    assert "append_observation_jsonl" in text
    assert "BrokenPipeError" in text
    assert "ConnectionResetError" in text
