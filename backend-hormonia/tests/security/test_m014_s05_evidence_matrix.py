from __future__ import annotations

import re
from pathlib import Path


MATRIX_PATH = Path("backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md")


REQUIRED_REQUIREMENTS = ("R012", "R013", "R014", "R015", "R017", "R018")

REQUIRED_SURFACES = (
    "CSRF",
    "Password reset replay",
    "webhook replay",
    "Duplicate patient oracle",
    "X-Forwarded-For",
    "ADK",
    "PHI-bearing backend GETs",
    "Public quiz frontend lane",
    "Upload stored-XSS",
    "generated report/export artifacts",
    "Unsafe generated report/export URLs",
    "JWT validation",
    "Staff auth",
    "Session revocation semantics",
    "Production deployment secret posture",
    "DB TLS and RLS posture",
    "R018 risk",
)

REQUIRED_COMMAND_REFERENCES = (
    "test_m014_s01_rate_limit_fail_closed.py",
    "test_m014_s01_csrf_fail_closed.py",
    "test_m014_s01_password_reset_replay.py",
    "test_m014_s01_webhook_replay.py",
    "test_m014_s01_duplicate_oracle.py",
    "test_m014_s02_adk_auth_session_ownership.py",
    "test_m014_s03_cache_headers.py",
    "persistencePolicy.test.ts",
    "quiz-progress-storage.test.tsx",
    "no-phi-local-storage.test.tsx",
    "test_m014_s04_active_content_validation.py",
    "test_m014_s04_upload_xss_private_serving.py",
    "test_m014_s04_private_artifact_serving.py",
    "test_m014_s04_report_artifact_serving.py",
    "test_m014_s05_jwt_config_posture.py",
    "test_m014_s05_evidence_matrix.py",
)

REQUIRED_EVIDENCE_IDS = (
    "3b14ac02-38eb-48c5-8303-f9cf467b5d54",
    "9efe8dad-808b-46fe-8c62-633744214262",
    "a7192f1b-7943-4c8a-be7a-121e377a621f",
    "09a0a6b5-5a04-498d-a850-d6b6d5be1f31",
    "0bece41c-9df5-473b-8c3e-50082f6bd878",
    "55eacbb1-957e-4ddb-93b3-dcf1cadf6eff",
    "cba439b4-eb1a-4141-883f-7426323e29fb",
    "d6c102d6-e4cb-494f-ab66-259ddd31b4e7",
    "a59f3ea2-74e1-46bb-a4f6-23c22a6fa564",
)

UNSAFE_SENTINELS = (
    "TODO",
    "TBD",
    "dev-insecure-secret-key",
    "must-be-changed",
    "Current key starts",
    "AIza",
    "session_token=",
    "csrf_token=",
    "Cookie:",
    "Authorization: Bearer",
    "sk-",
    "postgresql://user:pass@",
    "postgresql+psycopg://user:pass@",
    "C:\\",
    "/tmp/",
    "patient@example.com",
    "5511999999999",
)


def _matrix_text() -> str:
    assert MATRIX_PATH.exists(), f"Missing evidence matrix: {MATRIX_PATH}"
    text = MATRIX_PATH.read_text(encoding="utf-8")
    assert text.strip(), "Evidence matrix must not be empty"
    return text


def test_m014_matrix_has_required_rows_and_requirements() -> None:
    text = _matrix_text()

    row_ids = re.findall(r"\| M014-\d+ \|", text)
    assert len(row_ids) >= 17

    for requirement in REQUIRED_REQUIREMENTS:
        assert requirement in text

    for surface in REQUIRED_SURFACES:
        assert surface in text

    assert "Closed" in text
    assert "Deferred" in text
    assert "Not applicable" in text
    assert "M015/R014" in text


def test_m014_matrix_references_verification_commands_and_evidence() -> None:
    text = _matrix_text()

    for command_reference in REQUIRED_COMMAND_REFERENCES:
        assert command_reference in text

    for evidence_id in REQUIRED_EVIDENCE_IDS:
        assert evidence_id in text

    assert "PYTHONPATH=backend-hormonia python -m pytest" in text
    assert "npm --prefix frontend-hormonia test" in text
    assert "npm --prefix quiz-mensal-interface test" in text


def test_m014_matrix_keeps_runtime_deferrals_explicit() -> None:
    text = _matrix_text()

    assert "Production-like DB+queue+WuzAPI/Gemini harness" in text
    assert "Live JWT/session revocation across multiple worker processes" in text
    assert "Live database TLS negotiation and RLS policy enforcement" in text
    assert "Production CDN/browser/object-storage rendering of private artifacts" in text
    assert "Production exploitation or real PHI data" in text
    assert "Treating local git-ignored files as committed secrets" in text


def test_m014_matrix_has_no_placeholders_or_sensitive_sentinels() -> None:
    text = _matrix_text()

    for unsafe in UNSAFE_SENTINELS:
        assert unsafe not in text
