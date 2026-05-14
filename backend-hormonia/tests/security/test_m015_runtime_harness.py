from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest
from psycopg.conninfo import conninfo_to_dict

from app.db.migrations import MigrationBootstrapError, resolve_migration_database_url


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
RUNNER = REPO_ROOT / "scripts" / "security" / "verify-m015-runtime-security.sh"
HARNESS_DIR = REPO_ROOT / "scripts" / "security" / "m015-runtime"
COMPOSE_FILE = HARNESS_DIR / "docker-compose.yml"
DB_SEAM_HELPER = HARNESS_DIR / "db_seam.py"
HARNESS_README = HARNESS_DIR / "README.md"
SESSION_SEAM_HELPER = HARNESS_DIR / "session_seam.py"
SESSION_TASKIQ_HELPER = HARNESS_DIR / "m015_session_security_taskiq.py"
DB_EVIDENCE_JSON = BACKEND_ROOT / "docs" / "reports" / "security" / "m015" / "db-seam-evidence.json"
DB_SUMMARY_MD = BACKEND_ROOT / "docs" / "reports" / "security" / "m015" / "db-seam-summary.md"
SESSION_EVIDENCE_JSON = BACKEND_ROOT / "docs" / "reports" / "security" / "m015" / "session-seam-evidence.json"
SESSION_SUMMARY_MD = BACKEND_ROOT / "docs" / "reports" / "security" / "m015" / "session-seam-summary.md"

sys.path.insert(0, str(HARNESS_DIR))
from redaction import RedactionError, redaction_findings, validate_no_sensitive_evidence  # noqa: E402


def _query_params(url: str) -> dict[str, str]:
    return dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))


def _run_runner(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "M015_PROJECT_NAME": "m015-contract-test",
            "M015_API_PORT": "18180",
            "M015_POSTGRES_PORT": "15433",
        }
    )
    return subprocess.run(  # noqa: S603 - test invokes the committed harness entrypoint directly.
        [str(RUNNER), *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_runner_help_and_list_seams_are_static_and_fail_closed() -> None:
    help_result = _run_runner("--help")
    assert help_result.returncode == 0, help_result.stderr
    assert "--seam db" in help_result.stdout
    assert "--list-seams" in help_result.stdout
    assert "--teardown-only" in help_result.stdout

    list_result = _run_runner("--list-seams")
    assert list_result.returncode == 0, list_result.stderr
    assert list_result.stdout.strip().splitlines() == ["db", "session"]


def test_runner_rejects_missing_or_unknown_seams_before_setup() -> None:
    missing_result = _run_runner()
    missing_output = missing_result.stdout + missing_result.stderr
    assert missing_result.returncode != 0
    assert "--seam db" in missing_output
    assert "phase=setup" not in missing_output
    assert "green" not in missing_output.lower()

    unknown_result = _run_runner("--seam", "provider")
    unknown_output = unknown_result.stdout + unknown_result.stderr
    assert unknown_result.returncode != 0
    assert "unknown seam" in unknown_output.lower()
    assert "phase=setup" not in unknown_output


def test_m015_compose_is_isolated_from_live_providers_and_project_env_files() -> None:
    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")

    for service in ("postgres:", "dragonfly:", "api:", "worker:", "db-probe:", "session-probe:"):
        assert service in compose_text
    assert "env_file" not in compose_text
    assert "backend-hormonia/.env" not in compose_text
    assert "/mnt/c/" not in compose_text
    assert "wuzapi:" not in compose_text
    assert "gemini:" not in compose_text
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in compose_text
    assert "firebase-adminsdk" not in compose_text
    assert "WHATSAPP_ENABLE_SERVICE: ${WHATSAPP_ENABLE_SERVICE:-false}" in compose_text
    assert "AI_LANGCHAIN_ENABLE_TRACING_V2: ${AI_LANGCHAIN_ENABLE_TRACING_V2:-false}" in compose_text
    assert "build: *backend_build" in compose_text
    assert "command: [\"python\", \"/m015-runtime/db_seam.py\"]" in compose_text
    assert "command: [\"python\", \"/m015-runtime/session_seam.py\"]" in compose_text
    assert "command: [\"taskiq\", \"worker\", \"app.taskiq_broker:broker\", \"app.tasks.m015_session_security_taskiq\"]" in compose_text
    assert "./db_seam.py:/m015-runtime/db_seam.py:ro" in compose_text
    assert "./session_seam.py:/m015-runtime/session_seam.py:ro" in compose_text
    assert "./m015_session_security_taskiq.py:/app/app/tasks/m015_session_security_taskiq.py:ro" in compose_text
    assert "./m015_session_security_taskiq.py:/m015-runtime/m015_session_security_taskiq.py:ro" in compose_text
    assert "./redaction.py:/m015-runtime/redaction.py:ro" in compose_text


def test_evidence_paths_are_repo_relative_and_container_mounted() -> None:
    runner_text = RUNNER.read_text(encoding="utf-8")
    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")
    db_seam_text = DB_SEAM_HELPER.read_text(encoding="utf-8")
    session_seam_text = SESSION_SEAM_HELPER.read_text(encoding="utf-8")

    assert 'RUNTIME_DIR=".m015-runtime"' in runner_text
    assert "[Cc]ookie" in runner_text
    assert "[Ss]et-[Cc]ookie" in runner_text
    assert 'DB_EVIDENCE_OUTPUT_DIR="backend-hormonia/docs/reports/security/m015"' in runner_text
    assert 'DB_EVIDENCE_JSON="${DB_EVIDENCE_OUTPUT_DIR}/db-seam-evidence.json"' in runner_text
    assert 'DB_SUMMARY_MD="${DB_EVIDENCE_OUTPUT_DIR}/db-seam-summary.md"' in runner_text
    assert 'SESSION_EVIDENCE_JSON="${SESSION_EVIDENCE_OUTPUT_DIR}/session-seam-evidence.json"' in runner_text
    assert 'SESSION_SUMMARY_MD="${SESSION_EVIDENCE_OUTPUT_DIR}/session-seam-summary.md"' in runner_text
    assert "M015_EVIDENCE_OUTPUT_DIR=/m015-evidence-output" in runner_text
    assert "../../../backend-hormonia/docs/reports/security/m015:/m015-evidence-output" in compose_text
    assert 'OUTPUT_DIR = Path(os.getenv("M015_EVIDENCE_OUTPUT_DIR", "/m015-evidence-output"))' in db_seam_text
    assert 'EVIDENCE_JSON = OUTPUT_DIR / "db-seam-evidence.json"' in db_seam_text
    assert 'SUMMARY_MD = OUTPUT_DIR / "db-seam-summary.md"' in db_seam_text
    assert "from m015_session_security_taskiq import main" in session_seam_text


def test_session_probe_uses_users_cookie_contract_and_redacted_artifact_shape() -> None:
    taskiq_text = SESSION_TASKIQ_HELPER.read_text(encoding="utf-8")

    assert '"/api/v2/users/me"' in taskiq_text
    assert 'f"/api/v2/users/sessions/{synthetic.session_id}"' in taskiq_text
    assert '"/api/v2/auth/me"' not in taskiq_text
    assert '"/api/v2/auth/sessions/' not in taskiq_text
    assert 'headers["Cookie"] = f"{SESSION_COOKIE_NAME}={session_id}"' in taskiq_text
    assert 'extra_headers={"X-Session-ID": "m015-legacy-header-denied"}' in taskiq_text
    assert 'extra_headers={"Authorization": "Bearer m015-legacy-bearer-denied"}' in taskiq_text
    assert 'EVIDENCE_JSON = OUTPUT_DIR / "session-seam-evidence.json"' in taskiq_text
    assert 'SUMMARY_MD = OUTPUT_DIR / "session-seam-summary.md"' in taskiq_text
    assert '"raw_cookie_headers_persisted": False' in taskiq_text
    assert '"raw_session_ids_persisted": False' in taskiq_text
    assert '"provider_artifact_seams_not_exercised"' in taskiq_text

    validate_no_sensitive_evidence(
        {
            "command": "./scripts/security/verify-m015-runtime-security.sh --seam session",
            "session_probe": {
                "legacy_transports": {
                    "x_session_id": {"result": "denied", "status_code": 401, "reason": "session_cookie_required"},
                    "bearer": {"result": "denied", "status_code": 401, "reason": "session_cookie_required"},
                },
                "current_session": {"result": "allowed", "status_code": 200, "session_id_hash": "a" * 64},
                "cache_fallback": {"result": "allowed_via_db_fallback", "cache_before": "missing", "cache_after": "present"},
                "worker": {"result": "denied_after_db_recheck", "reason": "revoked_or_expired"},
            },
            "redaction": {"validated": True, "raw_cookie_headers_persisted": False, "raw_session_ids_persisted": False},
            "non_goals": ["live_provider_services_not_started", "provider_artifact_seams_not_exercised"],
        }
    )


def test_migration_url_canonicalizes_asyncpg_tls_aliases_for_psycopg() -> None:
    resolved = resolve_migration_database_url(
        {
            "DATABASE_URL": "postgresql+psycopg://user:secret@postgres:5432/app"
            "?sslmode=verify-full&sslrootcert=/m015-certs/ca.crt"
            "&sslminversion=TLSv1.2&sslmaxversion=TLSv1.3&application_name=m015_db_seam"
        },
        None,
    )

    query = _query_params(resolved)
    assert query["sslmode"] == "verify-full"
    assert query["sslrootcert"] == "/m015-certs/ca.crt"
    assert query["ssl_min_protocol_version"] == "TLSv1.2"
    assert query["ssl_max_protocol_version"] == "TLSv1.3"
    assert query["application_name"] == "m015_db_seam"
    assert "sslminversion" not in query
    assert "sslmaxversion" not in query

    # psycopg itself parses plain libpq URIs; SQLAlchemy owns the +psycopg
    # driver token before handing options to psycopg.
    libpq_uri = resolved.replace("postgresql+psycopg://", "postgresql://", 1)
    parsed = conninfo_to_dict(libpq_uri)
    assert parsed["sslmode"] == "verify-full"
    assert parsed["sslrootcert"] == "/m015-certs/ca.crt"
    assert parsed["ssl_min_protocol_version"] == "TLSv1.2"
    assert parsed["ssl_max_protocol_version"] == "TLSv1.3"


def test_migration_url_rejects_unknown_tls_options_without_leaking_dsn() -> None:
    secret_url = (
        "postgresql+psycopg://user:super-secret@postgres:5432/app"
        "?sslmode=verify-full&sslrootcert=/private/ca.crt&sslinvalidoption=1"
    )

    with pytest.raises(MigrationBootstrapError) as exc_info:
        resolve_migration_database_url({"DATABASE_URL": secret_url}, None)

    error_text = str(exc_info.value)
    assert "unsupported PostgreSQL TLS query option" in error_text
    assert "super-secret" not in error_text
    assert "/private/ca.crt" not in error_text
    assert secret_url not in error_text


def test_m015_harness_uses_psycopg_compatible_tls_minimum_key() -> None:
    runner_text = RUNNER.read_text(encoding="utf-8")
    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")
    readme_text = HARNESS_README.read_text(encoding="utf-8")

    assert "sslminversion" not in runner_text
    assert "sslminversion" not in compose_text
    assert "sslminversion" not in readme_text
    assert "ssl_min_protocol_version=TLSv1.2" in runner_text
    assert "ssl_min_protocol_version=TLSv1.2" in compose_text
    assert "ssl_min_protocol_version=TLSv1.2" in readme_text
    assert "sslmode=verify-full" in runner_text
    assert "sslmode=verify-full" in compose_text
    assert "sslrootcert=/m015-certs/ca.crt" in runner_text
    assert "sslrootcert=/m015-certs/ca.crt" in compose_text


@pytest.mark.parametrize(
    ("payload", "expected_finding"),
    [
        ({"value": "postgresql://user:password@postgres:5432/app"}, "credentialed_url"),
        ({"value": "-----BEGIN PRIVATE KEY-----\nnot-real\n-----END PRIVATE KEY-----"}, "private_key_block"),
        ({"value": "-----BEGIN CERTIFICATE-----\nnot-real\n-----END CERTIFICATE-----"}, "certificate_block"),
        ({"value": "Authorization: Bearer token-value"}, "authorization_header"),
        ({"value": "Set-Cookie: session=abc"}, "cookie_header"),
        ({"value": "ACCESS_TOKEN=secret-token"}, "secret_assignment"),
        ({"value": "firebase_admin service_account private_key_id client_x509_cert_url"}, "firebase_service_account_material"),
        ({"value": "cpf=123.456.789-10"}, "cpf_like_value"),
        ({"value": "email: person@real-clinic.example.com"}, "real_email_like_value"),
        ({"value": "phone=+55 (11) 91234-5678"}, "br_phone_like_value"),
        ({"value": "patient name: Maria Silva"}, "raw_patient_or_provider_payload"),
        ({"value": "/mnt/c/Users/example/private/file.txt"}, "raw_windows_mount_path"),
        ({"value": "/m015-certs/ca.crt"}, "runtime_cert_path"),
        ({"value": "stderr=ERROR SQL: insert into patients (name, cpf) values ('Maria Silva', 'x')"}, "raw_sql_stderr"),
    ],
)
def test_evidence_redaction_rejects_denylisted_sensitive_shapes(payload: object, expected_finding: str) -> None:
    findings = redaction_findings(payload)
    assert expected_finding in findings
    with pytest.raises(RedactionError):
        validate_no_sensitive_evidence(payload)


def test_evidence_redaction_allows_sanitized_synthetic_evidence_shape() -> None:
    validate_no_sensitive_evidence(
        {
            "command": "./scripts/security/verify-m015-runtime-security.sh --seam db",
            "tls": {"protocol": "TLSv1.3", "cipher": "TLS_AES_256_GCM_SHA384"},
            "rls": {
                "allow_probe": {
                    "insert_result": "allowed",
                    "synthetic_patient_id_hash": "a" * 64,
                    "synthetic_payload_policy": "generated UUID plus non-PHI sentinel; raw row value not persisted",
                },
                "deny_probe": {
                    "select_probe": {"result": "blocked_by_rls", "visible_rows": 0},
                    "insert_probe": {"result": "blocked_by_rls", "sqlstate": "42501"},
                },
            },
            "contact": "synthetic@example.invalid",
            "path_policy": "generated CA mount; raw path omitted",
        }
    )


def test_existing_runtime_seam_artifacts_are_redaction_clean_when_present() -> None:
    paths = (DB_EVIDENCE_JSON, DB_SUMMARY_MD, SESSION_EVIDENCE_JSON, SESSION_SUMMARY_MD)
    missing = [path for path in paths if not path.exists()]
    if missing:
        pytest.skip("runtime seam artifacts are produced by the Docker verification gate")

    for path in paths:
        validate_no_sensitive_evidence(path.read_text(encoding="utf-8"))
