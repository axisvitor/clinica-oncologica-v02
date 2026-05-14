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
NOTIFICATIONS_PROFILE_CONTRACT_MIGRATION = (
    BACKEND_ROOT / "alembic" / "versions" / "m015_s02_notifications_profile_contract.py"
)
DB_EVIDENCE_JSON = BACKEND_ROOT / "docs" / "reports" / "security" / "m015" / "db-seam-evidence.json"
DB_SUMMARY_MD = BACKEND_ROOT / "docs" / "reports" / "security" / "m015" / "db-seam-summary.md"
SESSION_EVIDENCE_JSON = BACKEND_ROOT / "docs" / "reports" / "security" / "m015" / "session-seam-evidence.json"
SESSION_SUMMARY_MD = BACKEND_ROOT / "docs" / "reports" / "security" / "m015" / "session-seam-summary.md"
PROVIDER_EVIDENCE_JSON = BACKEND_ROOT / "docs" / "reports" / "security" / "m015" / "provider-seam-evidence.json"
PROVIDER_SUMMARY_MD = BACKEND_ROOT / "docs" / "reports" / "security" / "m015" / "provider-seam-summary.md"

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
    assert "provider" in help_result.stdout
    assert "artifact" in help_result.stdout
    assert "--list-seams" in help_result.stdout
    assert "--teardown-only" in help_result.stdout

    list_result = _run_runner("--list-seams")
    assert list_result.returncode == 0, list_result.stderr
    assert list_result.stdout.strip().splitlines() == ["db", "session", "provider", "artifact"]


def test_runner_has_single_terminal_entrypoint_without_trailing_fragments() -> None:
    lines = RUNNER.read_text(encoding="utf-8").splitlines()

    assert lines[-1] == 'main "$@"'
    assert lines.count('main "$@"') == 1
    assert not any(line.startswith("nknown seam") for line in lines)


def test_runner_unknown_seams_fail_closed_and_no_filter_is_all_seam_contract() -> None:
    runner_text = RUNNER.read_text(encoding="utf-8")
    assert "ALL_SEAMS=(db session provider artifact)" in runner_text
    assert "run_all_seams()" in runner_text
    assert "no seam selected" not in runner_text

    unknown_result = _run_runner("--seam", "not-a-seam")
    unknown_output = unknown_result.stdout + unknown_result.stderr
    assert unknown_result.returncode != 0
    assert "unknown seam" in unknown_output.lower()
    assert "phase=setup" not in unknown_output


def test_m015_compose_is_isolated_from_live_providers_and_project_env_files() -> None:
    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")

    for service in (
        "postgres:",
        "dragonfly:",
        "api:",
        "worker:",
        "db-probe:",
        "session-probe:",
        "provider-stub:",
        "provider-worker:",
        "provider-probe:",
        "artifact-probe:",
    ):
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
    assert "WHATSAPP_WUZAPI_BASE_URL: ${WHATSAPP_WUZAPI_BASE_URL:-http://provider-stub:18089}" in compose_text
    assert "AI_GEMINI_BASE_URL: ${AI_GEMINI_BASE_URL:-http://provider-stub:18089}" in compose_text
    assert "build: *backend_build" in compose_text
    assert "command: [\"python\", \"/m015-runtime/db_seam.py\"]" in compose_text
    assert "command: [\"python\", \"/m015-runtime/session_seam.py\"]" in compose_text
    assert "command: [\"python\", \"/m015-runtime/provider_stub.py\", \"--host\", \"0.0.0.0\", \"--port\", \"18089\"]" in compose_text
    assert "command: [\"python\", \"/m015-runtime/provider_seam.py\"]" in compose_text
    assert "command: [\"python\", \"/m015-runtime/artifact_seam.py\"]" in compose_text
    assert "command: [\"taskiq\", \"worker\", \"app.taskiq_broker:broker\", \"app.tasks.m015_session_security_taskiq\"]" in compose_text
    assert "command: [\"taskiq\", \"worker\", \"app.taskiq_broker:broker\", \"app.tasks.m015_provider_security_taskiq\"]" in compose_text
    worker_section = compose_text.split("  worker:", 1)[1].split("  db-probe:", 1)[0]
    provider_worker_section = compose_text.split("  provider-worker:", 1)[1].split("  provider-probe:", 1)[0]
    provider_probe_section = compose_text.split("  provider-probe:", 1)[1].split("  artifact-probe:", 1)[0]
    artifact_probe_section = compose_text.split("  artifact-probe:", 1)[1].split("\nvolumes:", 1)[0]
    provider_broker = "TASKIQ_BROKER_URL: ${M015_PROVIDER_TASKIQ_BROKER_URL:-redis://dragonfly:6379/4}"
    assert "M015_DATABASE_PSQL_CONN" in worker_section
    assert provider_broker in provider_worker_section
    assert provider_broker in provider_probe_section
    assert provider_broker not in worker_section
    assert "M015_DATABASE_PSQL_CONN" in artifact_probe_section
    assert "M015_EVIDENCE_OUTPUT_DIR" in artifact_probe_section
    assert "provider-stub" not in artifact_probe_section
    assert "M015_PROVIDER_STUB_URL" not in artifact_probe_section
    assert "TASKIQ_BROKER_URL" not in artifact_probe_section
    assert "./db_seam.py:/m015-runtime/db_seam.py:ro" in compose_text
    assert "./session_seam.py:/m015-runtime/session_seam.py:ro" in compose_text
    assert "./m015_session_security_taskiq.py:/app/app/tasks/m015_session_security_taskiq.py:ro" in compose_text
    assert "./m015_session_security_taskiq.py:/m015-runtime/m015_session_security_taskiq.py:ro" in compose_text
    assert "./provider_stub.py:/m015-runtime/provider_stub.py:ro" in compose_text
    assert "./provider_seam.py:/m015-runtime/provider_seam.py:ro" in compose_text
    assert "./m015_provider_security_taskiq.py:/app/app/tasks/m015_provider_security_taskiq.py:ro" in compose_text
    assert "./m015_provider_security_taskiq.py:/m015-runtime/m015_provider_security_taskiq.py:ro" in compose_text
    assert "./artifact_seam.py:/m015-runtime/artifact_seam.py:ro" in compose_text
    assert "./redaction.py:/m015-runtime/redaction.py:ro" in compose_text


def test_provider_worker_readiness_waits_for_taskiq_listener() -> None:
    runner_text = RUNNER.read_text(encoding="utf-8")

    assert "provider_worker_listener_ready()" in runner_text
    assert "compose_cmd logs --no-color --tail=200 provider-worker" in runner_text
    assert "Listening started." in runner_text
    assert "provider-worker-not-ready" in runner_text
    assert "provider worker Taskiq listener is ready" in runner_text
    assert 'log_phase "redaction" "ready" "provider seam durable artifacts passed denylist validation without raw provider data"' in runner_text


def test_artifact_seam_dispatches_runtime_probe_and_records_redaction_phases() -> None:
    runner_text = RUNNER.read_text(encoding="utf-8")
    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "run_artifact_probe()" in runner_text
    assert "compose_cmd run --rm -T artifact-probe" in runner_text
    assert 'artifact) run_artifact_probe ;;' in runner_text
    assert "artifact-seam-evidence.json" in runner_text
    assert "artifact-seam-summary.md" in runner_text
    assert 'log_phase "redaction" "ready" "artifact seam durable artifacts passed denylist validation without raw private artifact data"' in runner_text
    assert "artifact-probe:" in compose_text
    assert "command: [\"python\", \"/m015-runtime/artifact_seam.py\"]" in compose_text


def test_runner_teardown_includes_tools_profile_services() -> None:
    runner_text = RUNNER.read_text(encoding="utf-8")

    assert "compose_cmd --profile tools down --volumes --remove-orphans" in runner_text
    assert "compose_cmd --profile tools down --remove-orphans" in runner_text
    assert "including tools-profile services" in runner_text


def test_evidence_paths_are_repo_relative_and_container_mounted() -> None:
    runner_text = RUNNER.read_text(encoding="utf-8")
    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")
    db_seam_text = DB_SEAM_HELPER.read_text(encoding="utf-8")
    session_seam_text = SESSION_SEAM_HELPER.read_text(encoding="utf-8")

    assert 'RUNTIME_DIR=".m015-runtime"' in runner_text
    assert "[Cc]ookie" in runner_text
    assert "[Tt]oken" in runner_text
    assert "[Ss]et-[Cc]ookie" in runner_text
    assert 'DB_EVIDENCE_OUTPUT_DIR="backend-hormonia/docs/reports/security/m015"' in runner_text
    assert 'DB_EVIDENCE_JSON="${DB_EVIDENCE_OUTPUT_DIR}/db-seam-evidence.json"' in runner_text
    assert 'DB_SUMMARY_MD="${DB_EVIDENCE_OUTPUT_DIR}/db-seam-summary.md"' in runner_text
    assert 'SESSION_EVIDENCE_JSON="${SESSION_EVIDENCE_OUTPUT_DIR}/session-seam-evidence.json"' in runner_text
    assert 'SESSION_SUMMARY_MD="${SESSION_EVIDENCE_OUTPUT_DIR}/session-seam-summary.md"' in runner_text
    assert 'PROVIDER_EVIDENCE_JSON="${PROVIDER_EVIDENCE_OUTPUT_DIR}/provider-seam-evidence.json"' in runner_text
    assert 'PROVIDER_SUMMARY_MD="${PROVIDER_EVIDENCE_OUTPUT_DIR}/provider-seam-summary.md"' in runner_text
    assert 'PROVIDER_STUB_OBSERVATIONS_JSONL="${PROVIDER_EVIDENCE_OUTPUT_DIR}/provider-stub-observations.jsonl"' in runner_text
    assert 'ARTIFACT_EVIDENCE_JSON="${ARTIFACT_EVIDENCE_OUTPUT_DIR}/artifact-seam-evidence.json"' in runner_text
    assert 'ARTIFACT_SUMMARY_MD="${ARTIFACT_EVIDENCE_OUTPUT_DIR}/artifact-seam-summary.md"' in runner_text
    assert "provider stub observation log reset for fresh sanitized run" in runner_text
    assert "M015_EVIDENCE_OUTPUT_DIR=/m015-evidence-output" in runner_text
    assert "../../../backend-hormonia/docs/reports/security/m015:/m015-evidence-output" in compose_text
    assert 'OUTPUT_DIR = Path(os.getenv("M015_EVIDENCE_OUTPUT_DIR", "/m015-evidence-output"))' in db_seam_text
    assert 'EVIDENCE_JSON = OUTPUT_DIR / "db-seam-evidence.json"' in db_seam_text
    assert 'SUMMARY_MD = OUTPUT_DIR / "db-seam-summary.md"' in db_seam_text
    assert "from m015_session_security_taskiq import main" in session_seam_text


def test_notifications_profile_contract_migration_covers_users_me_joinedload_columns() -> None:
    migration_text = NOTIFICATIONS_PROFILE_CONTRACT_MIGRATION.read_text(encoding="utf-8")

    assert 'down_revision = "m013_s04_upload_deleted_at"' in migration_text
    for required_column in (
        "notification_type",
        "priority",
        "title",
        "message",
        "action_url",
        "action_label",
        "notification_metadata",
        "read_at",
        "is_archived",
        "archived_at",
        "expires_at",
    ):
        assert f'"{required_column}"' in migration_text
    assert "notificationtype" in migration_text
    assert "notificationpriority" in migration_text


def test_session_probe_bootstraps_backend_path_before_taskiq_import() -> None:
    taskiq_text = SESSION_TASKIQ_HELPER.read_text(encoding="utf-8")
    backend_bootstrap = '_BACKEND_ROOT = Path(os.getenv("M015_BACKEND_ROOT", "/app"))'
    broker_import = "from app.taskiq_broker import broker"

    assert backend_bootstrap in taskiq_text
    assert "sys.path.insert(0, str(_BACKEND_ROOT))" in taskiq_text
    assert taskiq_text.index(backend_bootstrap) < taskiq_text.index(broker_import)


def test_session_probe_uses_response_model_accepted_synthetic_staff_email_domain() -> None:
    taskiq_text = SESSION_TASKIQ_HELPER.read_text(encoding="utf-8")

    assert '@example.com"' in taskiq_text
    assert '"raw_session_ids_persisted": False' in taskiq_text
    assert '"raw_cookie_headers_persisted": False' in taskiq_text


def test_session_probe_uses_users_cookie_contract_and_redacted_artifact_shape() -> None:
    taskiq_text = SESSION_TASKIQ_HELPER.read_text(encoding="utf-8")

    assert '"/api/v2/users/me"' in taskiq_text
    assert 'f"/api/v2/users/sessions/{synthetic.session_id}"' in taskiq_text
    assert '"/api/v2/auth/me"' not in taskiq_text
    assert '"/api/v2/auth/sessions/' not in taskiq_text
    assert "/api/v2/auth/csrf-token" in taskiq_text
    assert 'headers["Cookie"] = "; ".join(f"{name}={value}" for name, value in cookies.items())' in taskiq_text
    assert 'extra_headers={"X-CSRF-Token": csrf["header"]}' in taskiq_text
    assert 'extra_cookies={CSRF_COOKIE_NAME: csrf["cookie"]}' in taskiq_text
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


def test_m015_generated_ca_extensions_are_python_ssl_strict_compatible() -> None:
    runner_text = RUNNER.read_text(encoding="utf-8")

    assert '-addext "basicConstraints=critical,CA:TRUE"' in runner_text
    assert '-addext "keyUsage=critical,keyCertSign,cRLSign"' in runner_text


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
        ({"value": "Token: provider-token-value"}, "secret_assignment"),
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
    paths = (
        DB_EVIDENCE_JSON,
        DB_SUMMARY_MD,
        SESSION_EVIDENCE_JSON,
        SESSION_SUMMARY_MD,
        PROVIDER_EVIDENCE_JSON,
        PROVIDER_SUMMARY_MD,
    )
    missing = [path for path in paths if not path.exists()]
    if missing:
        pytest.skip("runtime seam artifacts are produced by the Docker verification gate")

    for path in paths:
        validate_no_sensitive_evidence(path.read_text(encoding="utf-8"))
