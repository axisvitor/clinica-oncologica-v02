from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest

from app.dependencies.auth_user_adapter import session_user_data_to_user
from artifact_seam import (
    HttpResult,
    PhaseError,
    PRIVATE_UPLOAD_BYTES,
    assert_denied,
    assert_expected,
    assert_export_status_sanitized,
    build_multipart_body,
    enhanced_cache_key,
    header_flags,
    reports_cache_key,
    summarize_http_result,
)
from redaction import RedactionError, redaction_findings, validate_no_sensitive_evidence


REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_HELPER = REPO_ROOT / "scripts" / "security" / "m015-runtime" / "artifact_seam.py"
COMPOSE_FILE = REPO_ROOT / "scripts" / "security" / "m015-runtime" / "docker-compose.yml"


def test_artifact_probe_uses_real_http_cookie_sessions_not_testclient_shortcuts() -> None:
    helper_text = ARTIFACT_HELPER.read_text(encoding="utf-8")
    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "urllib.request.Request" in helper_text
    assert "http://api:8080" in helper_text
    assert 'request_headers["Cookie"]' in helper_text
    assert "SESSION_COOKIE_NAME" in helper_text
    assert '"POST"' in helper_text
    assert '"/api/v2/upload/?public=' in helper_text
    assert "scan_virus=false" in helper_text
    assert "reports_cache_key(\"report\"" in helper_text
    assert '"/api/v2/reports/' in helper_text
    assert '"/api/v2/enhanced-reports/builder/' in helper_text
    assert '"/api/v2/enhanced-reports/export/' in helper_text
    assert "unsafe_download_urls_withheld" in helper_text
    assert "TestClient" not in helper_text
    assert "dependency_overrides" not in helper_text
    assert "Authorization" not in helper_text
    assert "Bearer" not in helper_text
    assert "artifact-probe:" in compose_text
    assert "./artifact_seam.py:/m015-runtime/artifact_seam.py:ro" in compose_text


def test_session_user_adapter_preserves_uuid_owner_comparison_contract() -> None:
    user_id = "11111111-1111-4111-8111-111111111111"

    user = session_user_data_to_user(
        {
            "id": user_id,
            "email": "owner@example.com",
            "full_name": "Owner",
            "role": "doctor",
            "is_active": True,
        }
    )

    assert user.id == UUID(user_id)


def test_multipart_builder_creates_file_part_without_logging_body() -> None:
    body = build_multipart_body(
        boundary="m015-boundary",
        field_name="file",
        filename="m015-private.txt",
        content_type="text/plain",
        content=PRIVATE_UPLOAD_BYTES,
    )

    assert b'Content-Disposition: form-data; name="file"; filename="m015-private.txt"' in body
    assert b"Content-Type: text/plain" in body
    assert body.endswith(b"\r\n--m015-boundary--\r\n")


def test_upload_result_summary_records_safe_booleans_and_hashes_only() -> None:
    result = HttpResult(
        status_code=200,
        duration_ms=17,
        headers={
            "content-disposition": 'attachment; filename="download.txt"',
            "x-content-type-options": "nosniff",
            "cache-control": "private, no-store",
        },
        body=PRIVATE_UPLOAD_BYTES,
        body_class="success_body",
    )

    summary = summarize_http_result("private_upload_owner_download", result, expected_body=PRIVATE_UPLOAD_BYTES)

    assert summary["status_code"] == 200
    assert summary["status_class"] == "2xx"
    assert summary["body_matches_expected"] is True
    assert summary["raw_body_persisted"] is False
    assert summary["raw_headers_persisted"] is False
    assert summary["raw_private_paths_persisted"] is False
    assert summary["headers"] == {
        "content_disposition_attachment": True,
        "x_content_type_options_nosniff": True,
        "cache_control_no_store": True,
        "location_present": False,
        "set_cookie_present": False,
        "raw_header_values_persisted": False,
    }
    serialized = json.dumps(summary, sort_keys=True)
    assert PRIVATE_UPLOAD_BYTES.decode("utf-8") not in serialized
    assert "attachment; filename" not in serialized
    validate_no_sensitive_evidence(summary)


def test_denied_upload_results_reject_private_bytes_paths_and_redirects() -> None:
    safe_denial = HttpResult(
        status_code=403,
        duration_ms=3,
        headers={},
        body=b'{"detail":"Forbidden"}',
        body_class="forbidden",
    )
    assert_denied(
        "foreign private download",
        safe_denial,
        forbidden_statuses={403, 404},
        forbidden_body=PRIVATE_UPLOAD_BYTES,
        forbidden_text="private/secret.txt",
    )

    with pytest.raises(PhaseError) as byte_leak:
        assert_denied(
            "foreign private download",
            HttpResult(403, 3, {}, PRIVATE_UPLOAD_BYTES, "forbidden"),
            forbidden_statuses={403, 404},
            forbidden_body=PRIVATE_UPLOAD_BYTES,
            forbidden_text="private/secret.txt",
        )
    assert byte_leak.value.failure_class == "upload_route_body_leak"

    with pytest.raises(PhaseError) as path_leak:
        assert_denied(
            "foreign private download",
            HttpResult(403, 3, {}, b"private/secret.txt", "forbidden"),
            forbidden_statuses={403, 404},
            forbidden_body=PRIVATE_UPLOAD_BYTES,
            forbidden_text="private/secret.txt",
        )
    assert path_leak.value.failure_class == "upload_route_path_leak"

    with pytest.raises(PhaseError) as redirect_leak:
        assert_denied(
            "foreign private download",
            HttpResult(403, 3, {"location": "/uploads/private/secret.txt"}, b"", "forbidden"),
            forbidden_statuses={403, 404},
            forbidden_body=PRIVATE_UPLOAD_BYTES,
            forbidden_text="private/secret.txt",
        )
    assert redirect_leak.value.failure_class == "upload_route_private_redirect"


def test_header_flags_store_header_presence_without_values() -> None:
    flags = header_flags(
        {
            "content-disposition": 'attachment; filename="secret.txt"',
            "x-content-type-options": "nosniff",
            "cache-control": "no-store",
            "set-cookie": "session=raw-value",
        }
    )

    assert flags["content_disposition_attachment"] is True
    assert flags["x_content_type_options_nosniff"] is True
    assert flags["cache_control_no_store"] is True
    assert flags["set_cookie_present"] is True
    assert flags["raw_header_values_persisted"] is False
    assert "secret.txt" not in json.dumps(flags, sort_keys=True)
    assert "raw-value" not in json.dumps(flags, sort_keys=True)
    validate_no_sensitive_evidence(flags)

def test_report_cache_key_helpers_match_router_shapes_without_raw_ids_in_evidence() -> None:
    report_id = "11111111-1111-4111-8111-111111111111"
    assert reports_cache_key("report", report_id=report_id).startswith("reports:v2:report:")
    assert report_id not in reports_cache_key("report", report_id=report_id)
    assert enhanced_cache_key("builder", report_id) == f"enhanced_reports:builder:{report_id}"
    assert enhanced_cache_key("export", report_id) == f"enhanced_reports:export:{report_id}"


def test_export_status_sanitizer_rejects_private_static_url_leaks() -> None:
    clean = HttpResult(
        status_code=200,
        duration_ms=4,
        headers={},
        body=b'{"download_urls": {}, "status": "completed"}',
        body_class="success_body",
    )
    assert_export_status_sanitized(clean, forbidden_text="/uploads/private/report.pdf")

    with pytest.raises(PhaseError) as leaked_text:
        assert_export_status_sanitized(
            HttpResult(
                status_code=200,
                duration_ms=4,
                headers={},
                body=b'{"download_urls": {"pdf": "/uploads/private/report.pdf"}}',
                body_class="success_body",
            ),
            forbidden_text="/uploads/private/report.pdf",
        )
    assert leaked_text.value.failure_class == "export_status_unsafe_url_leak"

    with pytest.raises(PhaseError) as retained_urls:
        assert_export_status_sanitized(
            HttpResult(
                status_code=200,
                duration_ms=4,
                headers={},
                body=b'{"download_urls": {"pdf": "/safe/report.pdf"}}',
                body_class="success_body",
            ),
            forbidden_text="/uploads/private/report.pdf",
        )
    assert retained_urls.value.failure_class == "export_status_unsafe_url_leak"


def test_public_static_expected_bytes_do_not_require_attachment_headers() -> None:
    public_static = HttpResult(
        status_code=200,
        duration_ms=5,
        headers={"content-type": "text/plain; charset=utf-8"},
        body=b"public bytes",
        body_class="success_body",
    )

    assert_expected("public direct static", public_static, 200, expected_body=b"public bytes")


def test_report_download_assertion_requires_safe_attachment_headers() -> None:
    safe = HttpResult(
        status_code=200,
        duration_ms=6,
        headers={
            "content-disposition": 'attachment; filename="report.csv"',
            "x-content-type-options": "nosniff",
            "cache-control": "no-store",
        },
        body=b"synthetic report bytes",
        body_class="success_body",
    )
    assert_expected("base report owner download", safe, 200, require_safe_attachment=True)

    unsafe = HttpResult(
        status_code=200,
        duration_ms=6,
        headers={"content-type": "text/html"},
        body=b"synthetic report bytes",
        body_class="success_body",
    )
    with pytest.raises(PhaseError) as exc_info:
        assert_expected("base report owner download", unsafe, 200, require_safe_attachment=True)
    assert exc_info.value.failure_class == "upload_route_unsafe_headers"


def test_report_export_evidence_shape_stores_status_booleans_and_hashes_only() -> None:
    report_summary = {
        "base_report": {
            "report_id_hash": "a" * 64,
            "owner_download": {"status_code": 200, "headers": {"content_disposition_attachment": True}},
        },
        "enhanced_export": {
            "unsafe_export_id_hash": "b" * 64,
            "unsafe_url_hash": "c" * 64,
            "unsafe_download_urls_withheld": True,
            "unsafe_download_redirected": False,
            "raw_download_urls_persisted": False,
        },
    }
    serialized = json.dumps(report_summary, sort_keys=True)
    assert "/uploads" not in serialized
    assert "report.pdf" not in serialized
    validate_no_sensitive_evidence(report_summary)

def test_artifact_redaction_rejects_raw_private_paths_download_urls_and_bytes() -> None:
    malicious_cases = [
        ({"value": "/uploads/private/report.pdf"}, "raw_private_artifact_path"),
        ({"value": "uploads/private/report.pdf"}, "raw_private_artifact_path"),
        ({"value": "/tmp/hormonia-m015-public-uploads/private/report.pdf"}, "raw_private_artifact_path"),
        ({"download_urls": {"pdf": "/uploads/private/report.pdf"}}, "raw_download_urls_mapping"),
        ({"value": "uploaded_bytes=M015-private-body"}, "raw_uploaded_or_report_bytes"),
        ({"value": "report_bytes=%PDF-1.4"}, "raw_uploaded_or_report_bytes"),
    ]

    for payload, expected_finding in malicious_cases:
        assert expected_finding in redaction_findings(payload)
        with pytest.raises(RedactionError):
            validate_no_sensitive_evidence(payload)


def test_artifact_evidence_and_summary_shapes_are_redaction_safe() -> None:
    evidence = {
        "correlation_id": "m015-test-correlation",
        "seam": "artifact",
        "command": "./scripts/security/verify-m015-runtime-security.sh --seam artifact",
        "result": "passed",
        "artifact_probe": {
            "upload": {
                "private_upload": {
                    "upload_id_hash": "a" * 64,
                    "storage_path_hash": "b" * 64,
                    "response_url_gated": True,
                    "direct_static": {
                        "route": "private_upload_direct_static",
                        "status_code": 404,
                        "status_class": "4xx",
                        "headers": {"location_present": False, "raw_header_values_persisted": False},
                        "raw_body_persisted": False,
                        "raw_private_paths_persisted": False,
                    },
                }
            },
            "report": {
                "base_report": {"report_id_hash": "c" * 64},
                "enhanced_export": {
                    "unsafe_url_hash": "d" * 64,
                    "unsafe_download_urls_withheld": True,
                    "unsafe_download_redirected": False,
                    "raw_download_urls_persisted": False,
                },
            },
        },
        "redaction": {
            "validated": True,
            "raw_cookie_headers_persisted": False,
            "raw_session_ids_persisted": False,
            "raw_private_paths_persisted": False,
            "raw_uploaded_bytes_persisted": False,
            "raw_report_bytes_persisted": False,
            "raw_download_urls_persisted": False,
        },
        "non_goals": ["final_all_seam_matrix_closure_deferred_to_s05", "cdn_object_storage_not_exercised"],
    }
    summary = """
# M015 Artifact Seam Summary

- Seam: `artifact`
- Verification result: `passed`
- Enhanced export unsafe URLs withheld: `True`; unsafe redirect `False`

All durable values are synthetic and redaction-validated; raw cookies, session IDs, upload/report bytes, private paths, raw download URLs, DSNs, and PHI are omitted.
Non-goals: final all-seam matrix closure, live providers, production systems/data, browser/frontend flows, CDN/object-storage, and broad DAST/fuzzing are not exercised by this artifact seam.
"""

    validate_no_sensitive_evidence(evidence)
    validate_no_sensitive_evidence(summary)
    serialized = json.dumps(evidence, sort_keys=True)
    assert "/uploads" not in serialized
    assert "Set-Cookie" not in serialized
    assert "Authorization" not in serialized
    assert "M015 synthetic" not in serialized

