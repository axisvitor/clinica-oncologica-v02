from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from evidence_matrix import MatrixFailure, build_matrix, validate_matrix
from redaction import validate_no_sensitive_evidence


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
HARNESS_DIR = REPO_ROOT / "scripts" / "security" / "m015-runtime"
RUNNER = REPO_ROOT / "scripts" / "security" / "verify-m015-runtime-security.sh"
README = HARNESS_DIR / "README.md"
MATRIX_HELPER = HARNESS_DIR / "evidence_matrix.py"
REPORT_DIR = BACKEND_ROOT / "docs" / "reports" / "security" / "m015"
MATRIX_JSON = REPORT_DIR / "m015-evidence-matrix.json"
MATRIX_MD = REPORT_DIR / "m015-evidence-matrix.md"

REQUIRED_REQUIREMENT_IDS = {"R012", "R013", "R014", "R015", "R017", "R018"}
REQUIRED_RUNTIME_ITEMS = {
    "db_tls_rls_runtime",
    "session_revocation_multi_process",
    "taskiq_worker_db_recheck",
    "provider_wuzapi_stub_boundary",
    "provider_gemini_stub_boundary",
    "private_upload_app_routes",
    "report_export_app_routes",
    "synthetic_only_no_live_providers",
    "redaction_safe_evidence",
    "strict_red_signal_closure",
}
REQUIRED_VALIDATOR_FAILURES = {
    "missing_required_row",
    "missing_evidence_artifact",
    "failed_seam_result",
    "stale_evidence_correlation",
    "placeholder_text",
    "unsafe_sensitive_content",
    "raw_download_url_leak",
    "unclassified_warning",
    "unresolved_red_signal",
}
SEAM_EVIDENCE = {
    "db": REPORT_DIR / "db-seam-evidence.json",
    "session": REPORT_DIR / "session-seam-evidence.json",
    "provider": REPORT_DIR / "provider-seam-evidence.json",
    "artifact": REPORT_DIR / "artifact-seam-evidence.json",
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_seam_runner_mode_is_declared_without_making_unknown_seams_safe() -> None:
    runner_text = RUNNER.read_text(encoding="utf-8")
    readme_text = README.read_text(encoding="utf-8")

    assert "ALL_SEAMS=(db session provider artifact)" in runner_text
    assert "run_all_seams()" in runner_text
    assert "matrix" in runner_text.lower()
    assert "unknown seam" in runner_text.lower()
    assert "no `--seam` filter" in readme_text or "no seam filter" in readme_text.lower()


def test_matrix_artifact_paths_and_helper_are_part_of_static_contract() -> None:
    runner_text = RUNNER.read_text(encoding="utf-8")
    readme_text = README.read_text(encoding="utf-8")

    assert MATRIX_HELPER.exists()
    assert "m015-evidence-matrix.json" in runner_text
    assert "m015-evidence-matrix.md" in runner_text
    assert "evidence_matrix.py" in runner_text
    assert "--validate" in runner_text
    assert "m015-evidence-matrix.json" in readme_text
    assert "m015-evidence-matrix.md" in readme_text


def test_matrix_helper_declares_required_rows_and_requirement_coverage() -> None:
    assert MATRIX_HELPER.exists()
    helper_text = MATRIX_HELPER.read_text(encoding="utf-8")

    for requirement_id in sorted(REQUIRED_REQUIREMENT_IDS):
        assert requirement_id in helper_text
    for item_id in sorted(REQUIRED_RUNTIME_ITEMS):
        assert item_id in helper_text


def test_matrix_validator_declares_false_green_failure_classes() -> None:
    assert MATRIX_HELPER.exists()
    helper_text = MATRIX_HELPER.read_text(encoding="utf-8")

    for failure_class in sorted(REQUIRED_VALIDATOR_FAILURES):
        assert failure_class in helper_text


@pytest.mark.parametrize("seam,evidence_path", sorted(SEAM_EVIDENCE.items()))
def test_existing_seam_evidence_inputs_are_present_passed_and_redaction_safe(seam: str, evidence_path: Path) -> None:
    assert evidence_path.exists(), seam
    payload = _read_json(evidence_path)

    assert payload.get("seam") == seam
    assert payload.get("result", "passed") == "passed"
    assert payload.get("correlation_id")
    validate_no_sensitive_evidence(payload)


def test_expected_matrix_shape_is_redaction_safe_and_complete() -> None:
    sample_matrix = {
        "milestone": "M015",
        "command": "./scripts/security/verify-m015-runtime-security.sh",
        "result": "passed",
        "validator": {"result": "passed", "failure_classes": sorted(REQUIRED_VALIDATOR_FAILURES)},
        "rows": [
            {
                "id": item_id,
                "requirement_ids": sorted(REQUIRED_REQUIREMENT_IDS if item_id == "strict_red_signal_closure" else ["R014"]),
                "source_seams": ["db", "session", "provider", "artifact"],
                "status": "fresh_evidence",
                "evidence_paths": ["backend-hormonia/docs/reports/security/m015/db-seam-evidence.json"],
                "correlation_ids": ["m015-synthetic-correlation"],
                "redaction_validated": True,
                "raw_sensitive_values_persisted": False,
            }
            for item_id in sorted(REQUIRED_RUNTIME_ITEMS)
        ],
        "non_goals": [
            "no_live_provider_credentials",
            "no_production_systems_or_phi",
            "no_browser_frontend_flows",
            "no_cdn_object_storage_claim",
            "no_broad_dast_or_exploitation",
        ],
    }

    assert {row["id"] for row in sample_matrix["rows"]} == REQUIRED_RUNTIME_ITEMS
    validate_no_sensitive_evidence(sample_matrix)


def _matrix_failure_class(matrix: dict) -> str:
    with pytest.raises(MatrixFailure) as exc_info:
        validate_matrix(matrix)
    return exc_info.value.failure_class


def _current_matrix() -> dict:
    return build_matrix(REPORT_DIR)


def test_matrix_validator_rejects_missing_required_rows() -> None:
    matrix = _current_matrix()
    matrix["rows"] = [row for row in matrix["rows"] if row["id"] != "db_tls_rls_runtime"]

    assert _matrix_failure_class(matrix) == "missing_required_row"


def test_matrix_validator_rejects_stale_or_missing_correlations() -> None:
    matrix = _current_matrix()
    matrix["rows"][0]["correlation_ids"] = []

    assert _matrix_failure_class(matrix) == "stale_evidence_correlation"


def test_matrix_validator_rejects_placeholders_and_unresolved_red_signals() -> None:
    placeholder_matrix = _current_matrix()
    placeholder_matrix["rows"][0]["notes"] = "TODO: fill this in later"
    assert _matrix_failure_class(placeholder_matrix) == "placeholder_text"

    unresolved_matrix = _current_matrix()
    unresolved_matrix["rows"][0]["status"] = "failed"
    assert _matrix_failure_class(unresolved_matrix) == "unresolved_red_signal"


def test_matrix_validator_rejects_raw_private_urls_and_sensitive_values() -> None:
    raw_url_matrix = _current_matrix()
    raw_url_matrix["rows"][0]["notes"] = "/uploads/private/report.pdf"
    assert _matrix_failure_class(raw_url_matrix) == "raw_download_url_leak"

    sensitive_matrix = _current_matrix()
    sensitive_matrix["rows"][0]["notes"] = "Cookie: session=raw-value"
    assert _matrix_failure_class(sensitive_matrix) == "unsafe_sensitive_content"


def test_matrix_validator_rejects_unclassified_warnings() -> None:
    matrix = _current_matrix()
    matrix["warnings"] = []

    assert _matrix_failure_class(matrix) == "unclassified_warning"


def test_matrix_builder_rejects_missing_or_failed_seam_evidence(tmp_path: Path) -> None:
    for evidence_path in SEAM_EVIDENCE.values():
        shutil.copy2(evidence_path, tmp_path / evidence_path.name)

    (tmp_path / "artifact-seam-evidence.json").unlink()
    with pytest.raises(MatrixFailure) as missing:
        build_matrix(tmp_path)
    assert missing.value.failure_class == "missing_evidence_artifact"

    shutil.copy2(REPORT_DIR / "artifact-seam-evidence.json", tmp_path / "artifact-seam-evidence.json")
    provider_payload = json.loads((tmp_path / "provider-seam-evidence.json").read_text(encoding="utf-8"))
    provider_payload["result"] = "failed"
    (tmp_path / "provider-seam-evidence.json").write_text(json.dumps(provider_payload), encoding="utf-8")

    with pytest.raises(MatrixFailure) as failed:
        build_matrix(tmp_path)
    assert failed.value.failure_class == "failed_seam_result"
