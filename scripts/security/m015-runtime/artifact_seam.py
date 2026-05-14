#!/usr/bin/env python3
"""M015/S04 private artifact app-route runtime probe.

This helper is mounted into the M015 synthetic Compose stack for the `artifact`
seam.  T02 implements the upload app-route portion: create synthetic staff
sessions in PostgreSQL, call the running FastAPI app over HTTP with real cookie
sessions, upload private/public synthetic files, and record only sanitized route
outcomes.

Report/export cases and runner invocation are added by later S04 tasks.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from redis import Redis

_BACKEND_ROOT = Path(os.getenv("M015_BACKEND_ROOT", "/app"))
if _BACKEND_ROOT.exists():
    sys.path.insert(0, str(_BACKEND_ROOT))

_RUNTIME_HELPER_DIR = Path("/m015-runtime")
if _RUNTIME_HELPER_DIR.exists():
    sys.path.insert(0, str(_RUNTIME_HELPER_DIR))

try:  # pragma: no cover - exercised inside the synthetic Compose probe.
    from redaction import RedactionError, sanitize_text, write_validated_json, write_validated_text
except Exception:  # pragma: no cover - local/static import fallback.
    from redaction import RedactionError, sanitize_text, write_validated_json, write_validated_text  # type: ignore[no-redef]

OUTPUT_DIR = Path(os.getenv("M015_EVIDENCE_OUTPUT_DIR", "/m015-evidence-output"))
EVIDENCE_JSON = OUTPUT_DIR / "artifact-seam-evidence.json"
SUMMARY_MD = OUTPUT_DIR / "artifact-seam-summary.md"
BACKEND_ROOT = _BACKEND_ROOT
RUNNER_COMMAND = "./scripts/security/verify-m015-runtime-security.sh --seam artifact"
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "session_id")
CSRF_COOKIE_NAME = "csrf_token"
PRIVATE_UPLOAD_BYTES = b"M015 synthetic private upload body\n"
PUBLIC_UPLOAD_BYTES = b"M015 synthetic public upload body\n"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def hash_identifier(value: str | bytes) -> str:
    if isinstance(value, bytes):
        raw = value
    else:
        raw = str(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def status_class(status_code: int | None) -> str:
    if status_code is None:
        return "network_error"
    return f"{status_code // 100}xx"


def database_conninfo() -> str:
    value = os.getenv("M015_DATABASE_PSQL_CONN")
    if not value:
        raise RuntimeError("M015_DATABASE_PSQL_CONN is not configured for the artifact seam")
    return value


def redis_url() -> str:
    return os.getenv("REDIS_URL") or os.getenv("TASKIQ_BROKER_URL") or "redis://dragonfly:6379/0"


def reports_cache_key(endpoint: str, **params: Any) -> str:
    param_str = json.dumps(params, sort_keys=True, default=str)
    param_hash = hashlib.sha256(param_str.encode("utf-8")).hexdigest()[:32]
    return f"reports:v2:{endpoint}:{param_hash}"


def enhanced_cache_key(prefix: str, resource_id: str) -> str:
    return f"enhanced_reports:{prefix}:{resource_id}"


@dataclass
class PhaseError(RuntimeError):
    phase: str
    failure_class: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return f"{self.phase}:{self.failure_class}: {self.message}"


@dataclass(frozen=True)
class SyntheticSession:
    label: str
    role: str
    user_id: str
    session_id: str
    user_id_hash: str
    session_id_hash: str


@dataclass(frozen=True)
class HttpResult:
    status_code: int
    duration_ms: int
    headers: dict[str, str]
    body: bytes
    body_class: str


@dataclass
class ArtifactProbe:
    correlation_id: str = field(default_factory=lambda: os.getenv("M015_CORRELATION_ID", f"m015-{uuid.uuid4()}"))
    events: list[dict[str, Any]] = field(default_factory=list)
    started_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.app_conninfo = self._required_env("M015_DATABASE_PSQL_CONN")
        self.database_url = self._required_env("M015_DATABASE_URL")

    def _required_env(self, name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise PhaseError("setup", "missing-env", f"required probe environment variable {name} is not set")
        return value

    def event(self, phase: str, status: str, message: str, **extra: Any) -> None:
        safe_message = sanitize_text(message, max_chars=600)
        event = {
            "timestamp": utc_now(),
            "correlation_id": self.correlation_id,
            "seam": "artifact",
            "phase": phase,
            "status": status,
            "message": safe_message,
        }
        if extra:
            event["details"] = extra
        self.events.append(event)
        print(
            f"[{event['timestamp']}] correlation_id={self.correlation_id} seam=artifact "
            f"phase={phase} status={status} {safe_message}",
            flush=True,
        )

    def connect_app(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.app_conninfo,
            autocommit=True,
            row_factory=dict_row,
            application_name="m015_artifact_seam_probe",
            connect_timeout=5,
        )

    def redis_client(self) -> Redis:
        return Redis.from_url(redis_url(), decode_responses=True)

    def seed_cache_json(self, key: str, payload: dict[str, Any], *, ttl_seconds: int = 3600) -> None:
        client = self.redis_client()
        try:
            client.setex(key, ttl_seconds, json.dumps(payload, sort_keys=True, default=str))
        finally:
            client.close()

    def fetch_csrf_token(self) -> dict[str, str]:
        headers = {
            "Host": "api",
            "User-Agent": "m015-artifact-probe",
            "X-Forwarded-Proto": "https",
            "X-Request-ID": self.correlation_id,
        }
        request = urllib.request.Request(
            "http://api:8080/api/v2/auth/csrf-token",
            headers=headers,
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - internal Compose URL.
                body = response.read().decode("utf-8", errors="replace")
                status_code = int(response.status)
                set_cookie = response.headers.get("Set-Cookie", "")
        except Exception as exc:
            raise PhaseError("upload", "csrf_token_failure", f"CSRF token request failed with class {type(exc).__name__}") from exc
        if status_code != 200:
            raise PhaseError("upload", "csrf_token_failure", "CSRF token endpoint did not return success", {"status_code": status_code})
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise PhaseError("upload", "csrf_token_failure", "CSRF token endpoint returned malformed JSON") from exc
        token = payload.get("csrf_token")
        if not token or not set_cookie:
            raise PhaseError("upload", "csrf_token_failure", "CSRF token endpoint did not provide double-submit token material")
        cookie_value = ""
        for segment in set_cookie.split(";"):
            stripped = segment.strip()
            if stripped.startswith(f"{CSRF_COOKIE_NAME}="):
                cookie_value = stripped.split("=", 1)[1]
                break
        if not cookie_value:
            raise PhaseError("upload", "csrf_token_failure", "CSRF token cookie was missing")
        return {"header": str(token), "cookie": cookie_value}

    def run_alembic_upgrade(self) -> dict[str, Any]:
        self.event("setup", "started", "applying Alembic head for artifact seam synthetic data")
        env = os.environ.copy()
        env["DATABASE_URL"] = self.database_url
        env["ALEMBIC_AUTOCOMMIT"] = "1"
        started = time.monotonic()
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=BACKEND_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=420,
            check=False,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        output_tail = sanitize_text((result.stdout or "") + "\n" + (result.stderr or ""), max_chars=1200)
        if result.returncode != 0:
            raise PhaseError(
                "setup",
                "migration_failure",
                "Alembic upgrade head failed before artifact seam probe",
                {"exit_code": result.returncode, "duration_ms": duration_ms, "output_tail": output_tail},
            )
        self.event("setup", "ready", "Alembic head available for artifact seam synthetic data")
        return {"exit_code": 0, "duration_ms": duration_ms, "output_tail": output_tail}

    def create_synthetic_session(self, label: str, *, role: str = "doctor") -> SyntheticSession:
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        email = f"m015-artifact-{label}-{self.correlation_id[-8:]}@example.com"
        session_token = f"m015-artifact-{label}-{uuid.uuid4().hex}"
        expires_at = datetime.now(UTC) + timedelta(hours=1)
        with self.connect_app() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into users (
                      id, email, full_name, role, is_active, auth_provider,
                      email_verified, preferences, specialties, permissions
                    ) values (
                      %s::uuid, %s, %s, %s, true, 'local', true,
                      '{}'::jsonb, '[]'::jsonb, '[]'::jsonb
                    )
                    """,
                    (user_id, email, "M015 Synthetic Staff", role),
                )
                cur.execute(
                    """
                    insert into sessions (
                      id, user_id, session_token, ip_address, user_agent,
                      last_activity, expires_at, is_active, session_metadata
                    ) values (
                      %s::uuid, %s::uuid, %s, '127.0.0.1', 'm015-artifact-probe',
                      now(), %s, true, %s::jsonb
                    )
                    """,
                    (
                        session_id,
                        user_id,
                        session_token,
                        expires_at,
                        json.dumps({"m015_synthetic": True, "label": label, "role": role}, sort_keys=True),
                    ),
                )
        return SyntheticSession(
            label=label,
            role=role,
            user_id=user_id,
            session_id=session_id,
            user_id_hash=hash_identifier(user_id),
            session_id_hash=hash_identifier(session_id),
        )

    def api_request(
        self,
        method: str,
        path: str,
        *,
        session_id: str | None = None,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        extra_cookies: dict[str, str] | None = None,
        timeout_seconds: float = 15.0,
    ) -> HttpResult:
        request_headers = {
            "Host": "api",
            "User-Agent": "m015-artifact-probe",
            "X-Forwarded-Proto": "https",
            "X-Request-ID": self.correlation_id,
        }
        if headers:
            request_headers.update(headers)
        cookies: dict[str, str] = {}
        if session_id:
            cookies[SESSION_COOKIE_NAME] = session_id
        if extra_cookies:
            cookies.update(extra_cookies)
        if cookies:
            request_headers["Cookie"] = "; ".join(f"{name}={value}" for name, value in cookies.items())
        request = urllib.request.Request(
            f"http://api:8080{path}",
            data=body,
            headers=request_headers,
            method=method,
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - internal Compose URL.
                response_body = response.read()
                status_code = int(response.status)
                response_headers = {key.lower(): value for key, value in response.headers.items()}
        except urllib.error.HTTPError as exc:
            response_body = exc.read()
            status_code = int(exc.code)
            response_headers = {key.lower(): value for key, value in exc.headers.items()}
        except Exception as exc:
            raise PhaseError(
                "artifact-probe",
                "api_request_failure",
                f"API request failed with class {type(exc).__name__}",
            ) from exc
        duration_ms = int((time.monotonic() - started) * 1000)
        return HttpResult(
            status_code=status_code,
            duration_ms=duration_ms,
            headers=response_headers,
            body=response_body,
            body_class=classify_body(status_code, response_body),
        )

    def upload_file(self, synthetic: SyntheticSession, *, public: bool, filename: str, content: bytes) -> dict[str, Any]:
        boundary = f"m015-artifact-{uuid.uuid4().hex}"
        csrf = self.fetch_csrf_token()
        body = build_multipart_body(boundary=boundary, field_name="file", filename=filename, content_type="text/plain", content=content)
        result = self.api_request(
            "POST",
            f"/api/v2/upload/?public={'true' if public else 'false'}&scan_virus=false&generate_thumbnail=false&generate_preview=false",
            session_id=synthetic.session_id,
            body=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "X-CSRF-Token": csrf["header"],
            },
            extra_cookies={CSRF_COOKIE_NAME: csrf["cookie"]},
            timeout_seconds=30.0,
        )
        if result.status_code != 201:
            raise PhaseError(
                "upload",
                "upload_create_failed",
                "synthetic upload create route did not return 201",
                {"status_code": result.status_code, "body_class": result.body_class},
            )
        try:
            payload = json.loads(result.body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise PhaseError("upload", "upload_create_malformed_json", "upload create response was not JSON") from exc
        return payload

    def prove_upload_routes(self) -> dict[str, Any]:
        self.event("upload", "started", "checking private/public upload app-route behavior through FastAPI")
        owner = self.create_synthetic_session("owner", role="doctor")
        foreign = self.create_synthetic_session("foreign", role="doctor")
        admin = self.create_synthetic_session("admin", role="admin")

        private_payload = self.upload_file(owner, public=False, filename="m015-private.txt", content=PRIVATE_UPLOAD_BYTES)
        public_payload = self.upload_file(owner, public=True, filename="m015-public.txt", content=PUBLIC_UPLOAD_BYTES)

        private_upload_id = str(private_payload.get("id") or "")
        public_upload_id = str(public_payload.get("id") or "")
        private_storage_path = str(private_payload.get("storage_path") or "")
        public_url = str(public_payload.get("url") or "")
        private_download_path = f"/api/v2/upload/{private_upload_id}/download"
        private_info_path = f"/api/v2/upload/{private_upload_id}"
        public_static_path = public_url if public_url.startswith("/") else "/uploads/missing-public-url"
        private_static_path = "/uploads/" + private_storage_path.lstrip("/")

        if not private_upload_id or not private_storage_path:
            raise PhaseError("upload", "upload_create_malformed_json", "private upload payload lacked expected ID/storage metadata")
        if not public_upload_id or not public_url.startswith("/uploads/"):
            raise PhaseError("upload", "public_upload_contract_mismatch", "public upload did not return a public static URL")

        private_url = str(private_payload.get("url") or "")
        private_download_url = str(private_payload.get("download_url") or "")
        if private_url.startswith("/uploads/") or private_download_url != private_download_path:
            raise PhaseError(
                "upload",
                "private_upload_url_leak",
                "private upload response did not use the gated API download route",
            )

        owner_download = self.api_request("GET", private_download_path, session_id=owner.session_id)
        admin_download = self.api_request("GET", private_download_path, session_id=admin.session_id)
        anonymous_download = self.api_request("GET", private_download_path)
        foreign_download = self.api_request("GET", private_download_path, session_id=foreign.session_id)
        owner_info = self.api_request("GET", private_info_path, session_id=owner.session_id)
        private_static = self.api_request("GET", private_static_path)
        public_static = self.api_request("GET", public_static_path)

        assert_expected("owner private download", owner_download, 200, expected_body=PRIVATE_UPLOAD_BYTES, require_safe_attachment=True)
        assert_expected("admin private download", admin_download, 200, expected_body=PRIVATE_UPLOAD_BYTES, require_safe_attachment=True)
        assert_denied("anonymous private download", anonymous_download, forbidden_statuses={401, 403, 404}, forbidden_body=PRIVATE_UPLOAD_BYTES, forbidden_text=private_storage_path)
        assert_denied("foreign private download", foreign_download, forbidden_statuses={403, 404}, forbidden_body=PRIVATE_UPLOAD_BYTES, forbidden_text=private_storage_path)
        assert_expected("owner upload info", owner_info, 200)
        assert_denied("private direct static", private_static, forbidden_statuses={401, 403, 404}, forbidden_body=PRIVATE_UPLOAD_BYTES, forbidden_text=private_storage_path)
        assert_expected("public direct static", public_static, 200, expected_body=PUBLIC_UPLOAD_BYTES)

        result = {
            "sessions": {
                "owner_user_hash": owner.user_id_hash,
                "foreign_user_hash": foreign.user_id_hash,
                "admin_user_hash": admin.user_id_hash,
                "raw_session_ids_persisted": False,
                "raw_cookie_headers_persisted": False,
            },
            "private_upload": {
                "upload_id_hash": hash_identifier(private_upload_id),
                "storage_path_hash": hash_identifier(private_storage_path),
                "response_url_gated": True,
                "response_url_static": False,
                "download_url_gated": True,
                "owner_download": summarize_http_result("private_upload_owner_download", owner_download, expected_body=PRIVATE_UPLOAD_BYTES),
                "admin_download": summarize_http_result("private_upload_admin_download", admin_download, expected_body=PRIVATE_UPLOAD_BYTES),
                "anonymous_download": summarize_http_result("private_upload_anonymous_download", anonymous_download, expected_body=PRIVATE_UPLOAD_BYTES),
                "foreign_download": summarize_http_result("private_upload_foreign_download", foreign_download, expected_body=PRIVATE_UPLOAD_BYTES),
                "owner_info": summarize_http_result("private_upload_owner_info", owner_info),
                "direct_static": summarize_http_result("private_upload_direct_static", private_static, expected_body=PRIVATE_UPLOAD_BYTES),
            },
            "public_upload": {
                "upload_id_hash": hash_identifier(public_upload_id),
                "public_url_hash": hash_identifier(public_url),
                "static_url_present": True,
                "direct_static": summarize_http_result("public_upload_direct_static", public_static, expected_body=PUBLIC_UPLOAD_BYTES),
            },
        }
        self.event("upload", "ready", "upload app-route probe recorded gated private and public-static outcomes")
        return result

    def prove_report_routes(self) -> dict[str, Any]:
        self.event("report", "started", "checking report/export app-route behavior through FastAPI")
        owner = self.create_synthetic_session("report-owner", role="doctor")
        foreign = self.create_synthetic_session("report-foreign", role="doctor")
        admin = self.create_synthetic_session("report-admin", role="admin")

        base_report_id = str(uuid.uuid4())
        builder_id = str(uuid.uuid4())
        export_unsafe_id = str(uuid.uuid4())
        export_fallback_id = str(uuid.uuid4())
        linked_report_id = str(uuid.uuid4())
        unsafe_download_url = "/uploads/private/m015-report.pdf"

        self.seed_cache_json(
            reports_cache_key("report", report_id=base_report_id),
            {
                "id": base_report_id,
                "status": "completed",
                "format": "json",
                "generated_by": owner.user_id,
                "patient_ids": [],
                "data": {"summary": "M015 synthetic report body", "count": 1},
            },
        )
        self.seed_cache_json(
            enhanced_cache_key("builder", builder_id),
            {
                "id": builder_id,
                "created_by": owner.user_id,
                "patient_ids": [],
                "data": [{"summary": "M015 synthetic builder body", "count": 1}],
            },
        )
        self.seed_cache_json(
            enhanced_cache_key("report", linked_report_id),
            {
                "id": linked_report_id,
                "created_by": owner.user_id,
                "patient_ids": [],
                "data": [{"summary": "M015 synthetic export-linked report", "count": 1}],
            },
        )
        self.seed_cache_json(
            enhanced_cache_key("export", export_unsafe_id),
            {
                "export_id": export_unsafe_id,
                "report_id": linked_report_id,
                "created_by": owner.user_id,
                "status": "completed",
                "formats": ["pdf"],
                "download_urls": {"pdf": unsafe_download_url},
                "file_sizes": {"pdf": 128},
            },
        )
        self.seed_cache_json(
            enhanced_cache_key("export", export_fallback_id),
            {
                "export_id": export_fallback_id,
                "report_id": linked_report_id,
                "created_by": owner.user_id,
                "status": "completed",
                "formats": ["pdf", "html"],
                "download_urls": {},
                "file_sizes": {"pdf": 128, "html": 64},
            },
        )

        base_path = f"/api/v2/reports/{base_report_id}/download?format_override=json"
        builder_path = f"/api/v2/enhanced-reports/builder/{builder_id}/download?format=csv"
        unsafe_status_path = f"/api/v2/enhanced-reports/export/{export_unsafe_id}"
        unsafe_download_path = f"/api/v2/enhanced-reports/export/{export_unsafe_id}/download?format=pdf"
        fallback_pdf_path = f"/api/v2/enhanced-reports/export/{export_fallback_id}/download?format=pdf"
        fallback_html_path = f"/api/v2/enhanced-reports/export/{export_fallback_id}/download?format=html"

        base_owner = self.api_request("GET", base_path, session_id=owner.session_id)
        base_admin = self.api_request("GET", base_path, session_id=admin.session_id)
        base_anonymous = self.api_request("GET", base_path)
        base_foreign = self.api_request("GET", base_path, session_id=foreign.session_id)
        builder_owner = self.api_request("GET", builder_path, session_id=owner.session_id)
        builder_admin = self.api_request("GET", builder_path, session_id=admin.session_id)
        builder_foreign = self.api_request("GET", builder_path, session_id=foreign.session_id)
        unsafe_status = self.api_request("GET", unsafe_status_path, session_id=owner.session_id)
        unsafe_download = self.api_request("GET", unsafe_download_path, session_id=owner.session_id)
        fallback_pdf = self.api_request("GET", fallback_pdf_path, session_id=owner.session_id)
        fallback_html = self.api_request("GET", fallback_html_path, session_id=owner.session_id)

        assert_expected("base report owner download", base_owner, 200, require_safe_attachment=True)
        assert_expected("base report admin download", base_admin, 200, require_safe_attachment=True)
        assert_denied("base report anonymous download", base_anonymous, forbidden_statuses={401, 403, 404}, forbidden_body=b"M015 synthetic report body", forbidden_text=base_report_id)
        assert_denied("base report foreign download", base_foreign, forbidden_statuses={403, 404}, forbidden_body=b"M015 synthetic report body", forbidden_text=base_report_id)
        assert_expected("builder owner download", builder_owner, 200, require_safe_attachment=True)
        assert_expected("builder admin download", builder_admin, 200, require_safe_attachment=True)
        assert_denied("builder foreign download", builder_foreign, forbidden_statuses={403, 404}, forbidden_body=b"M015 synthetic builder body", forbidden_text=builder_id)
        assert_expected("unsafe export status", unsafe_status, 200)
        assert_export_status_sanitized(unsafe_status, forbidden_text=unsafe_download_url)
        assert_denied("unsafe export download", unsafe_download, forbidden_statuses={404}, forbidden_body=b"M015 synthetic", forbidden_text=unsafe_download_url)
        assert_expected("fallback pdf export download", fallback_pdf, 200, require_safe_attachment=True)
        assert_expected("fallback html export download", fallback_html, 200, require_safe_attachment=True)

        result = {
            "sessions": {
                "owner_user_hash": owner.user_id_hash,
                "foreign_user_hash": foreign.user_id_hash,
                "admin_user_hash": admin.user_id_hash,
                "raw_session_ids_persisted": False,
                "raw_cookie_headers_persisted": False,
            },
            "base_report": {
                "report_id_hash": hash_identifier(base_report_id),
                "owner_download": summarize_http_result("base_report_owner_download", base_owner),
                "admin_download": summarize_http_result("base_report_admin_download", base_admin),
                "anonymous_download": summarize_http_result("base_report_anonymous_download", base_anonymous),
                "foreign_download": summarize_http_result("base_report_foreign_download", base_foreign),
            },
            "enhanced_builder": {
                "builder_id_hash": hash_identifier(builder_id),
                "owner_download": summarize_http_result("enhanced_builder_owner_download", builder_owner),
                "admin_download": summarize_http_result("enhanced_builder_admin_download", builder_admin),
                "foreign_download": summarize_http_result("enhanced_builder_foreign_download", builder_foreign),
            },
            "enhanced_export": {
                "unsafe_export_id_hash": hash_identifier(export_unsafe_id),
                "fallback_export_id_hash": hash_identifier(export_fallback_id),
                "unsafe_url_hash": hash_identifier(unsafe_download_url),
                "unsafe_status": summarize_http_result("enhanced_export_unsafe_status", unsafe_status),
                "unsafe_download": summarize_http_result("enhanced_export_unsafe_download", unsafe_download),
                "unsafe_download_urls_withheld": True,
                "unsafe_download_redirected": False,
                "fallback_pdf": summarize_http_result("enhanced_export_fallback_pdf", fallback_pdf),
                "fallback_html": summarize_http_result("enhanced_export_fallback_html", fallback_html),
                "raw_download_urls_persisted": False,
            },
        }
        self.event("report", "ready", "report/export app-route probe recorded ownership, unsafe-url, and fallback outcomes")
        return result

    def build_summary(self, evidence: dict[str, Any]) -> str:
        upload = evidence["artifact_probe"]["upload"]
        report = evidence["artifact_probe"].get("report", {})
        private = upload["private_upload"]
        public = upload["public_upload"]
        base_report = report.get("base_report", {})
        enhanced_export = report.get("enhanced_export", {})
        lines = [
            "# M015 Artifact Seam Summary",
            "",
            f"- Correlation ID: `{self.correlation_id}`",
            "- Seam: `artifact`",
            f"- Verification result: `{evidence['result']}`",
            f"- Private upload URL gated: `{private['response_url_gated']}`",
            f"- Owner/admin private download: `{private['owner_download']['status_code']}`/`{private['admin_download']['status_code']}`",
            f"- Anonymous/foreign private download: `{private['anonymous_download']['status_code']}`/`{private['foreign_download']['status_code']}`",
            f"- Private direct static: `{private['direct_static']['status_code']}`",
            f"- Public direct static: `{public['direct_static']['status_code']}`",
            f"- Base report owner/admin download: `{base_report.get('owner_download', {}).get('status_code', 'pending')}`/`{base_report.get('admin_download', {}).get('status_code', 'pending')}`",
            f"- Enhanced export unsafe URLs withheld: `{enhanced_export.get('unsafe_download_urls_withheld', 'pending')}`; unsafe redirect `{enhanced_export.get('unsafe_download_redirected', 'pending')}`",
            "- Teardown: `pending`",
            "",
            "All durable values are synthetic and redaction-validated; raw cookies, session IDs, upload/report bytes, private paths, raw download URLs, DSNs, and PHI are omitted.",
            "Non-goals: final all-seam matrix closure, live providers, production systems/data, browser/frontend flows, CDN/object-storage, and broad DAST/fuzzing are not exercised by this artifact seam.",
            "",
        ]
        return "\n".join(lines)

    def run(self) -> dict[str, Any]:
        migrations = self.run_alembic_upgrade()
        upload = self.prove_upload_routes()
        report = self.prove_report_routes()
        evidence = {
            "correlation_id": self.correlation_id,
            "seam": "artifact",
            "command": RUNNER_COMMAND,
            "result": "passed",
            "started_at": self.started_at,
            "completed_at": utc_now(),
            "events": self.events,
            "versions": {
                "postgres_image": os.getenv("M015_POSTGRES_IMAGE", "postgres:16-alpine"),
                "dragonfly_image": os.getenv("M015_DRAGONFLY_IMAGE", "docker.dragonflydb.io/dragonflydb/dragonfly:latest"),
                "api_base": "http://api:8080",
                "artifact_scope": "upload_report_export_app_routes",
            },
            "setup": {"migrations": migrations},
            "artifact_probe": {"upload": upload, "report": report},
            "redaction": {
                "validated": True,
                "raw_cookie_headers_persisted": False,
                "raw_session_ids_persisted": False,
                "raw_private_paths_persisted": False,
                "raw_uploaded_bytes_persisted": False,
                "raw_report_bytes_persisted": False,
                "raw_download_urls_persisted": False,
            },
            "failure_classes": [
                "migration_failure",
                "upload_create_failed",
                "private_upload_url_leak",
                "upload_route_unexpected_status",
                "upload_route_body_leak",
                "upload_static_private_exposed",
                "report_cache_seed_failure",
                "report_route_unexpected_status",
                "export_status_unsafe_url_leak",
                "export_status_malformed_json",
                "redaction_denylist_hit",
            ],
            "non_goals": [
                "final_all_seam_matrix_closure_deferred_to_s05",
                "live_provider_credentials_not_used",
                "no_real_patient_data_or_phi",
                "browser_frontend_flows_not_exercised",
                "cdn_object_storage_not_exercised",
            ],
            "teardown": {"result": "pending", "timestamp": None, "notes": "runner will update after compose down"},
        }
        write_validated_json(EVIDENCE_JSON, evidence)
        write_validated_text(SUMMARY_MD, self.build_summary(evidence))
        self.event("evidence", "ready", "artifact upload evidence JSON and summary written with redaction validation")
        return evidence


def build_multipart_body(*, boundary: str, field_name: str, filename: str, content_type: str, content: bytes) -> bytes:
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8")
    footer = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return header + content + footer


def classify_body(status_code: int, body: bytes) -> str:
    if status_code in {200, 201}:
        return "success_body"
    text = sanitize_text(body.decode("utf-8", errors="replace"), max_chars=300).lower()
    if "not authenticated" in text or "session cookie required" in text or "invalid or expired session" in text:
        return "not_authenticated"
    if "forbidden" in text:
        return "forbidden"
    if "not found" in text:
        return "not_found"
    return f"http_{status_code}"


def header_flags(headers: dict[str, str]) -> dict[str, bool]:
    content_disposition = headers.get("content-disposition", "")
    cache_control = headers.get("cache-control", "")
    return {
        "content_disposition_attachment": content_disposition.lower().startswith("attachment"),
        "x_content_type_options_nosniff": headers.get("x-content-type-options", "").lower() == "nosniff",
        "cache_control_no_store": "no-store" in cache_control.lower(),
        "location_present": bool(headers.get("location")),
        "set_cookie_present": "set-cookie" in headers,
        "raw_header_values_persisted": False,
    }


def summarize_http_result(route_label: str, result: HttpResult, *, expected_body: bytes | None = None) -> dict[str, Any]:
    body_matches = None if expected_body is None else result.body == expected_body
    return {
        "route": route_label,
        "status_code": result.status_code,
        "status_class": status_class(result.status_code),
        "duration_ms": result.duration_ms,
        "body_class": result.body_class,
        "body_sha256": hash_identifier(result.body) if result.status_code in {200, 201} else None,
        "body_matches_expected": body_matches,
        "body_size": len(result.body),
        "headers": header_flags(result.headers),
        "raw_body_persisted": False,
        "raw_headers_persisted": False,
        "raw_private_paths_persisted": False,
    }


def assert_expected(
    label: str,
    result: HttpResult,
    expected_status: int,
    *,
    expected_body: bytes | None = None,
    require_safe_attachment: bool = False,
) -> None:
    if result.status_code != expected_status:
        raise PhaseError(
            "upload",
            "upload_route_unexpected_status",
            f"{label} returned unexpected status",
            {"status_code": result.status_code, "expected_status": expected_status, "body_class": result.body_class},
        )
    if expected_body is not None and result.body != expected_body:
        raise PhaseError("upload", "upload_route_unexpected_body", f"{label} did not return expected synthetic bytes")
    if require_safe_attachment:
        flags = header_flags(result.headers)
        if not (
            flags["content_disposition_attachment"]
            and flags["x_content_type_options_nosniff"]
            and flags["cache_control_no_store"]
        ):
            raise PhaseError("upload", "upload_route_unsafe_headers", f"{label} did not return safe attachment headers")


def assert_export_status_sanitized(result: HttpResult, *, forbidden_text: str) -> None:
    text = result.body.decode("utf-8", errors="ignore")
    if forbidden_text in text or "/uploads" in text.lower():
        raise PhaseError("report", "export_status_unsafe_url_leak", "export status exposed unsafe private/static download URL")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PhaseError("report", "export_status_malformed_json", "export status response was not JSON") from exc
    if payload.get("download_urls") not in ({}, None):
        raise PhaseError("report", "export_status_unsafe_url_leak", "export status retained unsafe download URLs")


def assert_denied(
    label: str,
    result: HttpResult,
    *,
    forbidden_statuses: set[int],
    forbidden_body: bytes,
    forbidden_text: str,
) -> None:
    if result.status_code not in forbidden_statuses:
        raise PhaseError(
            "upload",
            "upload_route_unexpected_status",
            f"{label} returned unexpected status",
            {"status_code": result.status_code, "expected_statuses": sorted(forbidden_statuses), "body_class": result.body_class},
        )
    text = result.body.decode("utf-8", errors="ignore")
    if forbidden_body and forbidden_body in result.body:
        raise PhaseError("upload", "upload_route_body_leak", f"{label} exposed private upload bytes")
    if forbidden_text and forbidden_text in text:
        raise PhaseError("upload", "upload_route_path_leak", f"{label} exposed private storage path")
    if result.headers.get("location"):
        raise PhaseError("upload", "upload_route_private_redirect", f"{label} returned a redirect location")


def main() -> int:
    probe: ArtifactProbe | None = None
    try:
        probe = ArtifactProbe()
        probe.run()
        return 0
    except PhaseError as exc:
        if probe is not None:
            probe.event(exc.phase, "failed", f"failure_class={exc.failure_class} remediation={exc.message}")
            failure_payload = {
                "correlation_id": probe.correlation_id,
                "seam": "artifact",
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
            except (RedactionError, Exception):
                pass
        else:
            print(f"phase=setup status=failed failure_class={exc.failure_class} remediation={exc.message}", flush=True)
        return 1
    except Exception as exc:  # pragma: no cover - runtime harness defensive path.
        message = f"unexpected artifact seam failure class {type(exc).__name__}"
        if probe is not None:
            probe.event("evidence", "failed", f"failure_class=artifact_probe_unhandled remediation={message}")
        else:
            print(f"phase=evidence status=failed failure_class=artifact_probe_unhandled remediation={message}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
