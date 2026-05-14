#!/usr/bin/env python3
"""M015 session seam Taskiq task and probe.

This file is mounted two ways by the M015 synthetic runtime stack:

* ``/app/app/tasks/m015_session_security_taskiq.py`` so the real Taskiq worker
  explicitly imports and registers the harness-only task.
* ``/m015-runtime/m015_session_security_taskiq.py`` so ``session_seam.py`` can
  create synthetic staff sessions, call the API with cookie-backed auth, queue a
  worker check, and write redaction-validated evidence.

The task intentionally accepts only synthetic session IDs and returns only
sanitized authorization facts.  PostgreSQL session rows are the authority;
Dragonfly/Redis data is treated as a stale-prone cache hint.
"""

from __future__ import annotations

import asyncio
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
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from redis.asyncio import Redis

# ``session_seam.py`` is executed from /m015-runtime, which makes that helper
# directory sys.path[0] instead of the backend root.  Add the mounted backend
# package path before importing the real Taskiq broker so the probe and worker
# exercise the same backend module surface.
_BACKEND_ROOT = Path(os.getenv("M015_BACKEND_ROOT", "/app"))
if _BACKEND_ROOT.exists():
    sys.path.insert(0, str(_BACKEND_ROOT))

# ``redaction.py`` is mounted beside this file for the probe container, but it is
# not present when the worker imports this module from ``app.tasks``.  Keep the
# worker import lightweight by falling back to local no-op writers outside the
# probe path.
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
EVIDENCE_JSON = OUTPUT_DIR / "session-seam-evidence.json"
SUMMARY_MD = OUTPUT_DIR / "session-seam-summary.md"
BACKEND_ROOT = _BACKEND_ROOT
RUNNER_COMMAND = "./scripts/security/verify-m015-runtime-security.sh --seam session"
TASK_NAME = "m015_session_security_authorization"
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "session_id")
CSRF_COOKIE_NAME = "csrf_token"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def hash_identifier(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def redis_url() -> str:
    return (
        os.getenv("TASKIQ_BROKER_URL")
        or os.getenv("REDIS_URL")
        or os.getenv("CELERY_BROKER_URL")
        or "redis://dragonfly:6379/0"
    )


def database_conninfo() -> str:
    value = os.getenv("M015_DATABASE_PSQL_CONN")
    if not value:
        raise RuntimeError("M015_DATABASE_PSQL_CONN is not configured for the session seam")
    return value


async def wait_for_dragonfly_gate(gate_key: str, timeout_seconds: float) -> str | None:
    """Wait until the probe opens a Dragonfly gate key before DB re-check."""

    client = Redis.from_url(redis_url(), decode_responses=True)
    deadline = time.monotonic() + timeout_seconds
    try:
        while time.monotonic() < deadline:
            value = await client.get(gate_key)
            if value:
                return None
            await asyncio.sleep(0.2)
        return "gate_timeout"
    except Exception:
        return "gate_unavailable"
    finally:
        await client.aclose()


def read_session_authority(session_id: str) -> tuple[bool, str]:
    """Return PostgreSQL-authoritative authorization for a synthetic session."""

    try:
        parsed_session_id = str(uuid.UUID(str(session_id)))
    except (TypeError, ValueError):
        return False, "invalid_session_id"

    try:
        with psycopg.connect(
            database_conninfo(),
            autocommit=True,
            row_factory=dict_row,
            application_name="m015_session_security_taskiq",
            connect_timeout=5,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                      s.is_active,
                      s.revoked_at is not null as revoked,
                      s.expires_at <= now() as expired,
                      u.is_active as user_active
                    from sessions s
                    join users u on u.id = s.user_id
                    where s.id = %s::uuid
                    """,
                    (parsed_session_id,),
                )
                row = cur.fetchone()
    except Exception:
        return False, "db_unavailable"

    if not row:
        return False, "missing_session"
    if not bool(row["user_active"]):
        return False, "inactive_user"
    if bool(row["is_active"]) and not bool(row["revoked"]) and not bool(row["expired"]):
        return True, "active_session"
    return False, "revoked_or_expired"


@broker.task(task_name=TASK_NAME)
async def check_m015_session_authorization(
    session_id: str,
    *,
    gate_key: str | None = None,
    gate_timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Taskiq worker boundary check for DB-authoritative staff sessions."""

    session_id_hash = hash_identifier(session_id)
    if gate_key:
        gate_reason = await wait_for_dragonfly_gate(gate_key, gate_timeout_seconds)
        if gate_reason:
            return {
                "allowed": False,
                "reason": gate_reason,
                "session_id_hash": session_id_hash,
                "checked_at": utc_now(),
                "worker_boundary": "taskiq",
            }

    allowed, reason = await asyncio.to_thread(read_session_authority, session_id)
    return {
        "allowed": allowed,
        "reason": reason,
        "session_id_hash": session_id_hash,
        "checked_at": utc_now(),
        "worker_boundary": "taskiq",
    }


@dataclass
class PhaseError(RuntimeError):
    phase: str
    failure_class: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return f"{self.phase}:{self.failure_class}: {self.message}"


@dataclass
class SyntheticSession:
    label: str
    user_id: str
    session_id: str
    user_id_hash: str
    session_id_hash: str


@dataclass
class SessionProbe:
    correlation_id: str = field(default_factory=lambda: os.getenv("M015_CORRELATION_ID", f"m015-{uuid.uuid4()}"))
    events: list[dict[str, Any]] = field(default_factory=list)
    started_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.app_conninfo = self._required_env("M015_DATABASE_PSQL_CONN")
        self.database_url = self._required_env("M015_DATABASE_URL")
        self.redis_url = redis_url()

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
            "seam": "session",
            "phase": phase,
            "status": status,
            "message": safe_message,
        }
        if extra:
            event["details"] = extra
        self.events.append(event)
        print(
            f"[{event['timestamp']}] correlation_id={self.correlation_id} seam=session "
            f"phase={phase} status={status} {safe_message}",
            flush=True,
        )

    def connect_app(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.app_conninfo,
            autocommit=True,
            row_factory=dict_row,
            application_name="m015_session_seam_probe",
            connect_timeout=5,
        )

    def run_alembic_upgrade(self) -> dict[str, Any]:
        self.event("setup", "started", "applying Alembic head for session seam synthetic data")
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
                "Alembic upgrade head failed before session seam probe",
                {"exit_code": result.returncode, "duration_ms": duration_ms, "output_tail": output_tail},
            )
        self.event("setup", "ready", "Alembic head available for session seam synthetic data")
        return {"exit_code": 0, "duration_ms": duration_ms, "output_tail": output_tail}

    def create_synthetic_session(
        self,
        label: str,
        *,
        active: bool = True,
        expires_in_seconds: int = 3600,
    ) -> SyntheticSession:
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        email = f"m015-{label}-{self.correlation_id[-8:]}@example.com"
        session_token = f"m015-{label}-{uuid.uuid4().hex}"
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in_seconds)
        with self.connect_app() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into users (
                      id, email, full_name, role, is_active, auth_provider,
                      email_verified, preferences, specialties, permissions
                    ) values (
                      %s::uuid, %s, %s, 'doctor', true, 'local', true,
                      '{}'::jsonb, '[]'::jsonb, '[]'::jsonb
                    )
                    """,
                    (user_id, email, "M015 Synthetic Staff"),
                )
                cur.execute(
                    """
                    insert into sessions (
                      id, user_id, session_token, ip_address, user_agent,
                      last_activity, expires_at, is_active, session_metadata
                    ) values (
                      %s::uuid, %s::uuid, %s, '127.0.0.1', 'm015-session-probe',
                      now(), %s, %s, %s::jsonb
                    )
                    """,
                    (
                        session_id,
                        user_id,
                        session_token,
                        expires_at,
                        active,
                        json.dumps({"m015_synthetic": True, "label": label}, sort_keys=True),
                    ),
                )
        synthetic = SyntheticSession(
            label=label,
            user_id=user_id,
            session_id=session_id,
            user_id_hash=hash_identifier(user_id),
            session_id_hash=hash_identifier(session_id),
        )
        return synthetic

    async def redis_client(self) -> Redis:
        return Redis.from_url(self.redis_url, decode_responses=True)

    async def seed_stale_session_cache(self, synthetic: SyntheticSession) -> None:
        client = await self.redis_client()
        try:
            payload = {
                "session_id": synthetic.session_id,
                "user_id": synthetic.user_id,
                "email": "stale-cache@example.invalid",
                "full_name": "Stale Synthetic Cache",
                "role": "admin",
                "is_active": True,
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "session_created_at": utc_now(),
                "max_age_seconds": 86400,
            }
            await client.setex(f"session:{synthetic.session_id}", 86400, json.dumps(payload, sort_keys=True))
        finally:
            await client.aclose()

    async def delete_session_cache(self, session_id: str) -> None:
        client = await self.redis_client()
        try:
            await client.delete(f"session:{session_id}", session_id)
        finally:
            await client.aclose()

    async def cache_exists(self, session_id: str) -> bool:
        client = await self.redis_client()
        try:
            return bool(await client.exists(f"session:{session_id}"))
        finally:
            await client.aclose()

    async def open_gate(self, gate_key: str) -> None:
        client = await self.redis_client()
        try:
            await client.setex(gate_key, 60, "open")
        finally:
            await client.aclose()

    def fetch_csrf_token(self) -> dict[str, str]:
        """Fetch a signed CSRF token/cookie pair for browser-equivalent DELETE probes."""
        headers = {
            "Host": "api",
            "User-Agent": "m015-session-probe",
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
            raise PhaseError(
                "revocation",
                "csrf_token_failure",
                f"CSRF token request failed with class {type(exc).__name__}",
            ) from exc

        if status_code != 200:
            raise PhaseError(
                "revocation",
                "csrf_token_failure",
                "CSRF token endpoint did not return success",
                {"status_code": status_code},
            )

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise PhaseError(
                "revocation",
                "csrf_token_failure",
                "CSRF token endpoint returned malformed JSON",
            ) from exc

        header_token = payload.get("csrf_token")
        cookie = SimpleCookie()
        cookie.load(set_cookie)
        cookie_token = cookie.get(CSRF_COOKIE_NAME)
        if not header_token or cookie_token is None or not cookie_token.value:
            raise PhaseError(
                "revocation",
                "csrf_token_failure",
                "CSRF token endpoint did not provide a double-submit token pair",
            )

        return {"header": str(header_token), "cookie": cookie_token.value}

    def revoke_session_in_db(self, session_id: str, reason: str = "M015 synthetic revocation") -> None:
        with self.connect_app() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update sessions
                    set is_active = false,
                        revoked_at = now(),
                        revocation_reason = %s,
                        updated_at = now()
                    where id = %s::uuid
                    """,
                    (reason, session_id),
                )

    def expire_session_in_db(self, session_id: str) -> None:
        with self.connect_app() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update sessions
                    set expires_at = now() - interval '5 minutes', updated_at = now()
                    where id = %s::uuid
                    """,
                    (session_id,),
                )

    def api_request(
        self,
        method: str,
        path: str,
        *,
        session_id: str | None = None,
        extra_headers: dict[str, str] | None = None,
        extra_cookies: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Host": "api",
            "User-Agent": "m015-session-probe",
            "X-Forwarded-Proto": "https",
            "X-Request-ID": self.correlation_id,
        }
        if extra_headers:
            headers.update(extra_headers)
        cookies: dict[str, str] = {}
        if session_id:
            cookies[SESSION_COOKIE_NAME] = session_id
        if extra_cookies:
            cookies.update(extra_cookies)
        if cookies:
            headers["Cookie"] = "; ".join(f"{name}={value}" for name, value in cookies.items())
        request = urllib.request.Request(
            f"http://api:8080{path}",
            headers=headers,
            method=method,
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - internal Compose URL.
                body = response.read().decode("utf-8", errors="replace")
                status_code = int(response.status)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            status_code = int(exc.code)
        except Exception as exc:
            raise PhaseError(
                "session-probe",
                "api_request_failure",
                f"API request failed with class {type(exc).__name__}",
            ) from exc
        duration_ms = int((time.monotonic() - started) * 1000)
        return {
            "status_code": status_code,
            "duration_ms": duration_ms,
            "body_class": self.classify_api_body(status_code, body),
        }

    @staticmethod
    def classify_api_body(status_code: int, body: str) -> str:
        if status_code == 200:
            return "authorized_profile"
        sanitized = sanitize_text(body, max_chars=300).lower()
        if "invalid or expired session" in sanitized:
            return "invalid_or_expired_session"
        if "session cookie required" in sanitized:
            return "session_cookie_required"
        if "database temporarily unavailable" in sanitized:
            return "database_temporarily_unavailable"
        return f"http_{status_code}"

    def prove_legacy_transports_denied(self) -> dict[str, Any]:
        self.event("session-probe", "started", "checking legacy header and bearer transports fail without a session cookie")
        header_response = self.api_request(
            "GET",
            "/api/v2/users/me",
            extra_headers={"X-Session-ID": "m015-legacy-header-denied"},
        )
        bearer_response = self.api_request(
            "GET",
            "/api/v2/users/me",
            extra_headers={"Authorization": "Bearer m015-legacy-bearer-denied"},
        )
        if header_response["status_code"] != 401 or bearer_response["status_code"] != 401:
            raise PhaseError(
                "session-probe",
                "legacy_transport_accepted",
                "legacy staff-session transports were accepted without the canonical cookie",
                {"header_response": header_response, "bearer_response": bearer_response},
            )
        if header_response["body_class"] != "session_cookie_required" or bearer_response["body_class"] != "session_cookie_required":
            raise PhaseError(
                "session-probe",
                "legacy_transport_wrong_failure_class",
                "legacy staff-session transports did not fail with the expected cookie-required class",
                {"header_response": header_response, "bearer_response": bearer_response},
            )
        self.event("session-probe", "ready", "legacy header and bearer transports were denied without a session cookie")
        return {
            "x_session_id": {
                "result": "denied",
                "status_code": header_response["status_code"],
                "reason": header_response["body_class"],
            },
            "bearer": {
                "result": "denied",
                "status_code": bearer_response["status_code"],
                "reason": bearer_response["body_class"],
            },
        }

    def prove_current_session(self) -> dict[str, Any]:
        self.event("session-probe", "started", "checking current cookie-backed session through FastAPI")
        synthetic = self.create_synthetic_session("current")
        asyncio.run(self.seed_stale_session_cache(synthetic))
        response = self.api_request("GET", "/api/v2/users/me", session_id=synthetic.session_id)
        if response["status_code"] != 200:
            raise PhaseError("session-probe", "api_auth_current_denied", "current synthetic session was denied", response)
        self.event("session-probe", "ready", "current cookie-backed session returned an authorized profile")
        return {
            "result": "allowed",
            "status_code": response["status_code"],
            "duration_ms": response["duration_ms"],
            "body_class": response["body_class"],
            "db_state": "active",
            "cache_state": "present",
            "session_id_hash": synthetic.session_id_hash,
        }

    def prove_cache_fallback(self) -> dict[str, Any]:
        self.event("cache-fallback", "started", "checking PostgreSQL fallback when Dragonfly session cache is missing")
        synthetic = self.create_synthetic_session("fallback")
        asyncio.run(self.delete_session_cache(synthetic.session_id))
        cache_before = asyncio.run(self.cache_exists(synthetic.session_id))
        response = self.api_request("GET", "/api/v2/users/me", session_id=synthetic.session_id)
        cache_after = asyncio.run(self.cache_exists(synthetic.session_id))
        if response["status_code"] != 200 or cache_before or not cache_after:
            raise PhaseError(
                "cache-fallback",
                "redis_fallback_failure",
                "cache miss did not fall back to PostgreSQL and rehydrate Dragonfly",
                {"response": response, "cache_before": cache_before, "cache_after": cache_after},
            )
        self.event("cache-fallback", "ready", "cache miss fell back to PostgreSQL and rehydrated Dragonfly")
        return {
            "result": "allowed_via_db_fallback",
            "status_code": response["status_code"],
            "duration_ms": response["duration_ms"],
            "body_class": response["body_class"],
            "cache_before": "missing",
            "cache_after": "present",
            "session_id_hash": synthetic.session_id_hash,
        }

    def prove_revoked_and_expired_fail_closed(self) -> dict[str, Any]:
        self.event("revocation", "started", "checking revoked and expired sessions fail closed despite stale Dragonfly cache")
        revoked = self.create_synthetic_session("revoked")
        asyncio.run(self.seed_stale_session_cache(revoked))
        self.revoke_session_in_db(revoked.session_id)
        revoked_response = self.api_request("GET", "/api/v2/users/me", session_id=revoked.session_id)
        revoked_cache_present = asyncio.run(self.cache_exists(revoked.session_id))

        expired = self.create_synthetic_session("expired")
        asyncio.run(self.seed_stale_session_cache(expired))
        self.expire_session_in_db(expired.session_id)
        expired_response = self.api_request("GET", "/api/v2/users/me", session_id=expired.session_id)
        expired_cache_present = asyncio.run(self.cache_exists(expired.session_id))

        if revoked_response["status_code"] != 401 or expired_response["status_code"] != 401:
            raise PhaseError(
                "revocation",
                "db_session_state_mismatch",
                "revoked or expired session was not denied with stale cache present",
                {"revoked": revoked_response, "expired": expired_response},
            )
        self.event("revocation", "ready", "revoked and expired DB states denied stale Dragonfly cache hits")
        return {
            "revoked_stale_cache": {
                "result": "denied",
                "reason": revoked_response["body_class"],
                "status_code": revoked_response["status_code"],
                "db_state": "revoked",
                "cache_state": "stale_present" if revoked_cache_present else "missing",
                "session_id_hash": revoked.session_id_hash,
            },
            "expired_stale_cache": {
                "result": "denied",
                "reason": expired_response["body_class"],
                "status_code": expired_response["status_code"],
                "db_state": "expired",
                "cache_state": "stale_present" if expired_cache_present else "missing",
                "session_id_hash": expired.session_id_hash,
            },
        }

    def prove_explicit_revocation_invalidates_cache(self) -> dict[str, Any]:
        self.event("revocation", "started", "checking explicit user revocation deletes Dragonfly session cache")
        synthetic = self.create_synthetic_session("explicit-revoke")
        asyncio.run(self.seed_stale_session_cache(synthetic))
        cache_before = asyncio.run(self.cache_exists(synthetic.session_id))
        csrf = self.fetch_csrf_token()
        revoke_response = self.api_request(
            "DELETE",
            f"/api/v2/users/sessions/{synthetic.session_id}",
            session_id=synthetic.session_id,
            extra_headers={"X-CSRF-Token": csrf["header"]},
            extra_cookies={CSRF_COOKIE_NAME: csrf["cookie"]},
        )
        cache_after = asyncio.run(self.cache_exists(synthetic.session_id))
        post_revoke_response = self.api_request("GET", "/api/v2/users/me", session_id=synthetic.session_id)
        if revoke_response["status_code"] != 200 or not cache_before or cache_after or post_revoke_response["status_code"] != 401:
            raise PhaseError(
                "revocation",
                "explicit_revocation_cache_failure",
                "explicit revocation did not invalidate Dragonfly and fail closed afterward",
                {
                    "revoke_response": revoke_response,
                    "post_revoke_response": post_revoke_response,
                    "cache_before": cache_before,
                    "cache_after": cache_after,
                },
            )
        self.event("revocation", "ready", "explicit user revocation removed Dragonfly cache and DB denied follow-up access")
        return {
            "result": "revoked_and_cache_invalidated",
            "revoke_status_code": revoke_response["status_code"],
            "post_revoke_status_code": post_revoke_response["status_code"],
            "post_revoke_reason": post_revoke_response["body_class"],
            "cache_before": "present",
            "cache_after": "missing",
            "session_id_hash": synthetic.session_id_hash,
        }

    async def prove_worker_rechecks_db(self) -> dict[str, Any]:
        self.event("worker", "started", "queueing Taskiq worker check behind a Dragonfly gate before DB revocation")
        synthetic = self.create_synthetic_session("worker")
        await self.seed_stale_session_cache(synthetic)
        gate_key = f"m015:session-gate:{self.correlation_id}:{synthetic.session_id_hash[:12]}"
        await broker.startup()
        try:
            queued_task = await check_m015_session_authorization.kiq(
                synthetic.session_id,
                gate_key=gate_key,
                gate_timeout_seconds=45.0,
            )
            self.revoke_session_in_db(synthetic.session_id, reason="M015 queued worker revocation")
            await self.open_gate(gate_key)
            result = await queued_task.wait_result(timeout=60, check_interval=0.5)
        except Exception as exc:
            raise PhaseError("worker", "taskiq_dispatch_or_result_failure", f"Taskiq worker proof failed with class {type(exc).__name__}") from exc
        finally:
            await broker.shutdown()

        if result.is_err:
            raise PhaseError("worker", "taskiq_task_error", "Taskiq task returned an error result")
        value = result.return_value
        if not isinstance(value, dict):
            raise PhaseError("worker", "taskiq_result_malformed", "Taskiq task returned a non-mapping result")
        expected_hash = synthetic.session_id_hash
        if value.get("allowed") is not False or value.get("reason") != "revoked_or_expired" or value.get("session_id_hash") != expected_hash:
            raise PhaseError(
                "worker",
                "worker_db_recheck_failed",
                "worker did not deny the queued session after PostgreSQL revocation",
                {"worker_result": value},
            )
        self.event("worker", "ready", "Taskiq worker denied queued work after re-reading PostgreSQL session state")
        return {
            "result": "denied_after_db_recheck",
            "allowed": False,
            "reason": value.get("reason"),
            "worker_boundary": value.get("worker_boundary"),
            "checked_at": value.get("checked_at"),
            "session_id_hash": value.get("session_id_hash"),
            "task_id_hash": hash_identifier(getattr(queued_task, "task_id", "unknown")),
            "cache_state": "stale_present",
            "db_state_before_gate": "revoked",
        }

    def build_summary(self, evidence: dict[str, Any]) -> str:
        session = evidence["session_probe"]
        lines = [
            "# M015 Session Seam Summary",
            "",
            f"- Correlation ID: `{self.correlation_id}`",
            "- Seam: `session`",
            f"- Verification result: `{evidence['result']}`",
            f"- Legacy header/Bearer transports: status `{session['legacy_transports']['x_session_id']['status_code']}`/`{session['legacy_transports']['bearer']['status_code']}`, reason `{session['legacy_transports']['x_session_id']['reason']}`",
            f"- Current session: status `{session['current_session']['status_code']}`, result `{session['current_session']['result']}`",
            f"- Cache fallback: `{session['cache_fallback']['result']}`, cache `{session['cache_fallback']['cache_before']}` -> `{session['cache_fallback']['cache_after']}`",
            f"- Revoked stale cache: status `{session['revoked_and_expired']['revoked_stale_cache']['status_code']}`, reason `{session['revoked_and_expired']['revoked_stale_cache']['reason']}`",
            f"- Expired stale cache: status `{session['revoked_and_expired']['expired_stale_cache']['status_code']}`, reason `{session['revoked_and_expired']['expired_stale_cache']['reason']}`",
            f"- Explicit revocation: `{session['explicit_revocation']['result']}`, cache after `{session['explicit_revocation']['cache_after']}`",
            f"- Worker: `{session['worker']['result']}`, reason `{session['worker']['reason']}`, boundary `{session['worker']['worker_boundary']}`",
            "- Teardown: `pending`",
            "",
            "All durable values are synthetic and redaction-validated; raw cookies, DSNs, session IDs, and provider payloads are omitted.",
            "Non-goals: live provider services, provider artifact seams, and real patient data/PHI are not exercised by this session seam.",
            "",
        ]
        return "\n".join(lines)

    def run(self) -> dict[str, Any]:
        migrations = self.run_alembic_upgrade()
        legacy_transports = self.prove_legacy_transports_denied()
        current = self.prove_current_session()
        fallback = self.prove_cache_fallback()
        revoked_and_expired = self.prove_revoked_and_expired_fail_closed()
        explicit_revocation = self.prove_explicit_revocation_invalidates_cache()
        worker = asyncio.run(self.prove_worker_rechecks_db())
        evidence = {
            "correlation_id": self.correlation_id,
            "seam": "session",
            "command": RUNNER_COMMAND,
            "result": "passed",
            "started_at": self.started_at,
            "completed_at": utc_now(),
            "events": self.events,
            "versions": {
                "postgres_image": os.getenv("M015_POSTGRES_IMAGE", "postgres:16-alpine"),
                "dragonfly_image": os.getenv("M015_DRAGONFLY_IMAGE", "docker.dragonflydb.io/dragonflydb/dragonfly:latest"),
                "api_base": "http://api:8080",
            },
            "setup": {"migrations": migrations},
            "session_probe": {
                "legacy_transports": legacy_transports,
                "current_session": current,
                "cache_fallback": fallback,
                "revoked_and_expired": revoked_and_expired,
                "explicit_revocation": explicit_revocation,
                "worker": worker,
            },
            "redaction": {"validated": True, "raw_cookie_headers_persisted": False, "raw_session_ids_persisted": False},
            "failure_classes": [
                "migration_failure",
                "api_request_failure",
                "legacy_transport_accepted",
                "legacy_transport_wrong_failure_class",
                "redis_fallback_failure",
                "db_session_state_mismatch",
                "explicit_revocation_cache_failure",
                "taskiq_dispatch_or_result_failure",
                "worker_db_recheck_failed",
                "redaction_denylist_hit",
            ],
            "non_goals": [
                "live_provider_services_not_started",
                "provider_artifact_seams_not_exercised",
                "no_real_patient_data_or_phi",
            ],
            "teardown": {"result": "pending", "timestamp": None, "notes": "runner will update after compose down"},
        }
        write_validated_json(EVIDENCE_JSON, evidence)
        write_validated_text(SUMMARY_MD, self.build_summary(evidence))
        self.event("evidence", "ready", "session seam evidence JSON and summary written with redaction validation")
        return evidence


def main() -> int:
    probe: SessionProbe | None = None
    try:
        probe = SessionProbe()
        probe.run()
        return 0
    except PhaseError as exc:
        if probe is not None:
            probe.event(exc.phase, "failed", f"failure_class={exc.failure_class} remediation={exc.message}")
            failure_payload = {
                "correlation_id": probe.correlation_id,
                "seam": "session",
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
        message = f"unexpected session seam failure class {type(exc).__name__}"
        if probe is not None:
            probe.event("evidence", "failed", f"failure_class=session_probe_unhandled remediation={message}")
        else:
            print(f"phase=evidence status=failed failure_class=session_probe_unhandled remediation={message}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
