#!/usr/bin/env python3
"""M015 DB seam probe.

Runs inside the backend image on the isolated Docker Compose network.  It proves
that the synthetic runtime can use strict PostgreSQL TLS, applies the real
Alembic graph as the non-superuser application role, verifies FastAPI database
readiness through the application runtime, proves sensitive-table RLS allow/deny
semantics, and writes redaction-validated evidence artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg.rows import dict_row

from redaction import RedactionError, sanitize_text, write_validated_json, write_validated_text


SENSITIVE_TABLES = (
    "patients",
    "messages",
    "quiz_sessions",
    "quiz_responses",
    "lgpd_audit_logs",
    "lgpd_data_access_requests",
    "consents",
)

OUTPUT_DIR = Path(os.getenv("M015_EVIDENCE_OUTPUT_DIR", "/m015-evidence-output"))
EVIDENCE_JSON = OUTPUT_DIR / "db-seam-evidence.json"
SUMMARY_MD = OUTPUT_DIR / "db-seam-summary.md"
BACKEND_ROOT = Path(os.getenv("M015_BACKEND_ROOT", "/app"))
PROBE_COMMAND = "python /m015-runtime/db_seam.py"
RUNNER_COMMAND = "./scripts/security/verify-m015-runtime-security.sh --seam db"


@dataclass
class PhaseError(RuntimeError):
    phase: str
    failure_class: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return f"{self.phase}:{self.failure_class}: {self.message}"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Probe:
    def __init__(self) -> None:
        self.correlation_id = os.getenv("M015_CORRELATION_ID", f"m015-{uuid.uuid4()}")
        self.events: list[dict[str, Any]] = []
        self.started_at = utc_now()
        self.app_conninfo = self._required_env("M015_DATABASE_PSQL_CONN")
        self.denied_conninfo = self._required_env("M015_RLS_DENIED_PSQL_CONN")
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
            "seam": "db",
            "phase": phase,
            "status": status,
            "message": safe_message,
        }
        if extra:
            event["details"] = extra
        self.events.append(event)
        print(
            f"[{event['timestamp']}] correlation_id={self.correlation_id} seam=db "
            f"phase={phase} status={status} {safe_message}",
            flush=True,
        )

    def connect_app(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.app_conninfo,
            autocommit=True,
            row_factory=dict_row,
            application_name="m015_db_seam_probe",
            connect_timeout=5,
        )

    def connect_denied(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.denied_conninfo,
            autocommit=True,
            row_factory=dict_row,
            application_name="m015_db_seam_denied_probe",
            connect_timeout=5,
        )

    def wait_for_tls_postgres(self, timeout_seconds: int = 90) -> dict[str, Any]:
        self.event("tls", "started", "waiting for PostgreSQL verify-full TLS as synthetic app role")
        deadline = time.monotonic() + timeout_seconds
        last_error = "not-attempted"
        while time.monotonic() < deadline:
            try:
                with self.connect_app() as conn:
                    with conn.cursor() as cur:
                        cur.execute("select current_user as user_name, inet_server_addr()::text as server_addr")
                        row = cur.fetchone()
                        if row and row["user_name"] == "hormonia_app":
                            self.event("tls", "ready", "PostgreSQL accepted verify-full TLS connection")
                            return {"current_user": row["user_name"], "server_addr_class": "compose_network"}
            except Exception as exc:  # pragma: no cover - exercised by runtime harness
                last_error = sanitize_text(type(exc).__name__, max_chars=120)
            time.sleep(2)
        raise PhaseError(
            "tls",
            "postgres_tls_handshake_failure",
            "verify-full TLS connection to PostgreSQL did not become ready",
            {"last_error_class": last_error},
        )

    def run_alembic_upgrade(self) -> dict[str, Any]:
        self.event("migrations", "started", "running Alembic upgrade head as synthetic non-superuser app role")
        env = os.environ.copy()
        env["DATABASE_URL"] = self.database_url
        env["ALEMBIC_AUTOCOMMIT"] = "1"
        command = [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"]
        started = time.monotonic()
        result = subprocess.run(
            command,
            cwd=BACKEND_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=420,
            check=False,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        combined = sanitize_text((result.stdout or "") + "\n" + (result.stderr or ""), max_chars=4000)
        offending_revision = self._extract_revision(combined)
        if result.returncode != 0:
            raise PhaseError(
                "migrations",
                "migration_failure",
                "Alembic upgrade head failed under the synthetic app role",
                {
                    "command": "python -m alembic -c alembic.ini upgrade head",
                    "exit_code": result.returncode,
                    "duration_ms": duration_ms,
                    "offending_revision": offending_revision,
                    "output_tail": sanitize_text(combined, max_chars=1200),
                },
            )

        heads = self._alembic_heads()
        current = self._current_revisions()
        if not current:
            raise PhaseError("migrations", "migration_current_missing", "alembic_version is empty after upgrade head")
        missing_heads = sorted(set(heads) - set(current))
        if missing_heads:
            raise PhaseError(
                "migrations",
                "migration_head_mismatch",
                "database current revisions do not include all Alembic heads",
                {"expected_heads": heads, "current_revisions": current, "missing_heads": missing_heads},
            )
        self.event("migrations", "ready", "Alembic head is applied as synthetic app role")
        return {
            "command": "python -m alembic -c alembic.ini upgrade head",
            "exit_code": result.returncode,
            "duration_ms": duration_ms,
            "expected_heads": heads,
            "current_revisions": current,
            "offending_revision": offending_revision,
            "output_tail": sanitize_text(combined, max_chars=1200),
            "ran_as_role": "hormonia_app",
            "superuser_bypass": False,
        }

    @staticmethod
    def _extract_revision(text: str) -> str | None:
        patterns = (
            r"revision(?: identified by)? ['\"]?([0-9a-f]{6,32})",
            r"Running upgrade\s+[^>]+->\s+([0-9a-f]{6,32})",
            r"Revision ID:\s*([0-9a-f]{6,32})",
        )
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _alembic_heads(self) -> list[str]:
        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        script = ScriptDirectory.from_config(config)
        return sorted(script.get_heads())

    def _current_revisions(self) -> list[str]:
        with self.connect_app() as conn:
            with conn.cursor() as cur:
                cur.execute("select version_num from alembic_version order by version_num")
                return [str(row["version_num"]) for row in cur.fetchall()]

    def verify_api_runtime_health(self, timeout_seconds: int = 120) -> dict[str, Any]:
        self.event("readiness", "started", "checking FastAPI health and DB-backed readiness through app runtime")
        health = self._wait_for_json_endpoint("/health", timeout_seconds, expected_status={"healthy"})
        readiness = self._wait_for_json_endpoint("/health/ready", timeout_seconds, expected_status={"ready", "healthy"})
        self.event("readiness", "ready", "FastAPI health and DB-backed readiness endpoints passed")
        return {
            "health_endpoint": {"path": "/health", "status": health.get("status"), "version": health.get("version")},
            "readiness_endpoint": {
                "path": "/health/ready",
                "status": readiness.get("status"),
                "database_dependency_status": readiness.get("dependencies", {}).get("database", {}).get("status"),
                "session_auth_status": readiness.get("dependencies", {}).get("session_auth", {}).get("status"),
            },
            "database_tls_runtime_check": "FastAPI readiness used the application DATABASE_URL configured for verify-full TLS; DSN not persisted.",
        }

    def _wait_for_json_endpoint(
        self,
        path: str,
        timeout_seconds: int,
        *,
        expected_status: set[str],
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        last_error = "not-attempted"
        url = f"http://api:8080{path}"
        while time.monotonic() < deadline:
            try:
                request = urllib.request.Request(
                    url,
                    headers={"X-Forwarded-Proto": "https", "Host": "api"},
                    method="GET",
                )
                with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - internal compose URL
                    payload = json.loads(response.read().decode("utf-8"))
                status = str(payload.get("status"))
                if status in expected_status:
                    return payload
                last_error = f"unexpected_status:{status}"
            except urllib.error.HTTPError as exc:  # pragma: no cover - runtime harness path
                body = sanitize_text(exc.read().decode("utf-8", errors="replace"), max_chars=240)
                last_error = f"http_{exc.code}:{body}"
            except Exception as exc:  # pragma: no cover - runtime harness path
                last_error = sanitize_text(type(exc).__name__, max_chars=160)
            time.sleep(2)
        failure_class = "api_runtime_tls_readiness_failure" if path.endswith("/ready") else "api_health_failure"
        raise PhaseError(
            "readiness",
            failure_class,
            f"FastAPI endpoint {path} did not report the expected status",
            {"endpoint": path, "last_error_class": sanitize_text(last_error, max_chars=300)},
        )

    def collect_tls_evidence(self) -> dict[str, Any]:
        self.event("tls", "started", "collecting pg_stat_ssl evidence for current probe connection")
        with self.connect_app() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select s.ssl, s.version as protocol, s.cipher, current_user as user_name
                    from pg_stat_ssl s
                    where s.pid = pg_backend_pid()
                    """
                )
                ssl_row = cur.fetchone()
                cur.execute("show ssl")
                ssl_setting = cur.fetchone()["ssl"]
                cur.execute("show server_version")
                server_version = cur.fetchone()["server_version"]
                cur.execute("select version() as version_text")
                version_text = cur.fetchone()["version_text"]
        if not ssl_row or not ssl_row["ssl"]:
            raise PhaseError("tls", "tls_not_negotiated", "pg_stat_ssl did not report ssl=true for the probe connection")
        protocol = str(ssl_row.get("protocol") or "")
        if protocol not in {"TLSv1.2", "TLSv1.3"}:
            raise PhaseError("tls", "tls_protocol_too_weak", "TLS protocol is missing or below TLSv1.2", {"protocol": protocol})
        cipher = str(ssl_row.get("cipher") or "")
        if not cipher:
            raise PhaseError("tls", "tls_cipher_missing", "pg_stat_ssl did not report a negotiated cipher")
        if str(ssl_setting).lower() != "on":
            raise PhaseError("tls", "postgres_ssl_disabled", "SHOW ssl did not return on", {"show_ssl": ssl_setting})
        self.event("tls", "ready", "pg_stat_ssl confirmed TLS protocol and cipher")
        return {
            "result": "passed",
            "show_ssl": "on",
            "protocol": protocol,
            "cipher": cipher,
            "current_user": ssl_row["user_name"],
            "postgres_server_version": server_version,
            "postgres_version_class": self._version_class(version_text),
            "connection_scope": "current_probe_backend_pid",
        }

    @staticmethod
    def _version_class(version_text: str) -> str:
        # Keep useful version evidence without persisting build host/compiler paths.
        match = re.match(r"(PostgreSQL\s+\S+)", version_text)
        return match.group(1) if match else "PostgreSQL unknown"

    def collect_catalog_evidence(self) -> dict[str, Any]:
        self.event("rls", "started", "checking sensitive-table catalog RLS posture")
        table_results: dict[str, Any] = {}
        with self.connect_app() as conn:
            for table in SENSITIVE_TABLES:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        select c.relname, c.relrowsecurity, c.relforcerowsecurity
                        from pg_class c
                        join pg_namespace n on n.oid = c.relnamespace
                        where n.nspname = 'public' and c.relname = %s and c.relkind in ('r', 'p')
                        """,
                        (table,),
                    )
                    catalog = cur.fetchone()
                    if not catalog:
                        table_results[table] = {
                            "exists": False,
                            "status": "not_present_in_current_alembic_head",
                            "relrowsecurity": None,
                            "relforcerowsecurity": None,
                            "public_privileges_revoked": None,
                            "policy_names": [],
                            "policy_roles": [],
                        }
                        continue
                    cur.execute(
                        """
                        select
                          exists(
                            select 1
                            from aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) acl
                            where acl.grantee = 0 and acl.privilege_type = 'SELECT'
                          ) as public_select,
                          exists(
                            select 1
                            from aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) acl
                            where acl.grantee = 0 and acl.privilege_type = 'INSERT'
                          ) as public_insert,
                          exists(
                            select 1
                            from aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) acl
                            where acl.grantee = 0 and acl.privilege_type = 'UPDATE'
                          ) as public_update,
                          exists(
                            select 1
                            from aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) acl
                            where acl.grantee = 0 and acl.privilege_type = 'DELETE'
                          ) as public_delete
                        from pg_class c
                        join pg_namespace n on n.oid = c.relnamespace
                        where n.nspname = 'public' and c.relname = %s and c.relkind in ('r', 'p')
                        """,
                        (table,),
                    )
                    public_privileges = cur.fetchone()
                    cur.execute(
                        """
                        select policyname, cmd, roles
                        from pg_policies
                        where schemaname = 'public' and tablename = %s
                        order by policyname
                        """,
                        (table,),
                    )
                    policies = cur.fetchall()

                expected_policy = f"rls_{table}_current_user_all"
                policy_names = [row["policyname"] for row in policies]
                policy_roles = sorted({role for row in policies for role in (row.get("roles") or [])})
                public_revoked = not any(bool(value) for value in public_privileges.values())
                table_results[table] = {
                    "exists": True,
                    "relrowsecurity": bool(catalog["relrowsecurity"]),
                    "relforcerowsecurity": bool(catalog["relforcerowsecurity"]),
                    "public_privileges_revoked": public_revoked,
                    "policy_names": policy_names,
                    "policy_roles": policy_roles,
                }
                if not catalog["relrowsecurity"] or not catalog["relforcerowsecurity"]:
                    raise PhaseError("rls", "rls_catalog_not_forced", f"RLS is not enabled and forced for {table}")
                if not public_revoked:
                    raise PhaseError("rls", "rls_public_privileges_present", f"PUBLIC still has table privileges on {table}")
                if expected_policy not in policy_names or "hormonia_app" not in policy_roles:
                    raise PhaseError("rls", "rls_policy_missing", f"expected app-role RLS policy is missing for {table}")
        present_tables = [table for table, data in table_results.items() if data.get("exists")]
        missing_tables = [table for table, data in table_results.items() if not data.get("exists")]
        if not present_tables:
            raise PhaseError("rls", "rls_catalog_no_sensitive_tables", "no sensitive tables exist in current Alembic head")
        self.event(
            "rls",
            "ready",
            "catalog shows forced RLS, revoked PUBLIC privileges, and app-role policies for existing sensitive tables; absent tables recorded",
        )
        return {
            "result": "passed",
            "tables": table_results,
            "present_tables": present_tables,
            "missing_tables": missing_tables,
        }

    def insert_synthetic_patient(self) -> dict[str, Any]:
        self.event("rls", "started", "inserting one synthetic non-PHI patient as app role")
        patient_id = uuid.uuid4()
        sentinel = f"M015_SYNTHETIC_NON_PHI_{self.correlation_id}_{patient_id.hex[:12]}"
        sentinel_hash = hashlib.sha256(f"{patient_id}:{sentinel}".encode("utf-8")).hexdigest()
        metadata = {
            "m015_synthetic": True,
            "correlation_hash": hashlib.sha256(self.correlation_id.encode("utf-8")).hexdigest()[:16],
        }
        with self.connect_app() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into patients (id, name, flow_state, current_day, metadata)
                    values (%s, %s, %s, %s, %s::jsonb)
                    returning id::text
                    """,
                    (str(patient_id), sentinel, "onboarding", 0, json.dumps(metadata, sort_keys=True)),
                )
                inserted = cur.fetchone()
        if not inserted:
            raise PhaseError("rls", "rls_allow_insert_missing", "app-role synthetic patient insert returned no row")
        self.event("rls", "ready", "app role inserted synthetic patient; evidence stores only hash/correlation")
        return {
            "insert_result": "allowed",
            "insert_role": "hormonia_app",
            "synthetic_patient_id_hash": sentinel_hash,
            "synthetic_payload_policy": "generated UUID plus non-PHI sentinel; raw row value not persisted",
            "patient_id": str(patient_id),
        }

    def prove_denied_role(self, patient_id: str) -> dict[str, Any]:
        self.event("rls", "started", "granting table privileges to denied role and proving RLS default deny")
        with self.connect_app() as conn:
            with conn.cursor() as cur:
                cur.execute("grant usage on schema public to m015_rls_denied")
                cur.execute("grant select, insert, update, delete on all tables in schema public to m015_rls_denied")
                cur.execute("grant usage, select on all sequences in schema public to m015_rls_denied")

        denied_patient_id = uuid.uuid4()
        denied_sentinel = f"M015_DENIED_SYNTHETIC_NON_PHI_{self.correlation_id}_{denied_patient_id.hex[:12]}"
        privilege_row: dict[str, Any]
        denied_select_count = -1
        denied_insert: dict[str, Any]
        with self.connect_denied() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                      current_user as current_user,
                      has_table_privilege(current_user, 'public.patients', 'SELECT') as can_select,
                      has_table_privilege(current_user, 'public.patients', 'INSERT') as can_insert,
                      has_schema_privilege(current_user, 'public', 'USAGE') as can_use_schema
                    """
                )
                privilege_row = dict(cur.fetchone() or {})
                if not (privilege_row.get("can_select") and privilege_row.get("can_insert") and privilege_row.get("can_use_schema")):
                    raise PhaseError(
                        "rls",
                        "rls_denied_privilege_setup_failed",
                        "denied role lacks schema/table grants, so RLS deny proof would be inconclusive",
                        {"privileges": privilege_row},
                    )
                cur.execute("select count(*)::int as visible_rows from patients where id = %s", (patient_id,))
                denied_select_count = int((cur.fetchone() or {}).get("visible_rows", -1))
                if denied_select_count != 0:
                    raise PhaseError(
                        "rls",
                        "rls_denied_select_unexpected_allow",
                        "denied role could see the synthetic patient despite having no matching RLS policy",
                        {"visible_rows": denied_select_count},
                    )
                try:
                    cur.execute(
                        """
                        insert into patients (id, name, flow_state, current_day, metadata)
                        values (%s, %s, %s, %s, %s::jsonb)
                        """,
                        (
                            str(denied_patient_id),
                            denied_sentinel,
                            "onboarding",
                            0,
                            json.dumps({"m015_denied_probe": True}, sort_keys=True),
                        ),
                    )
                except psycopg.Error as exc:
                    primary = sanitize_text(getattr(exc.diag, "message_primary", "") or str(exc), max_chars=240)
                    if "row-level security" not in primary.lower():
                        raise PhaseError(
                            "rls",
                            "rls_denied_insert_not_rls",
                            "denied role insert failed for a reason other than RLS",
                            {"sqlstate": exc.sqlstate, "message_class": primary},
                        ) from exc
                    denied_insert = {
                        "result": "blocked_by_rls",
                        "sqlstate": exc.sqlstate,
                        "message_class": "row-level security policy",
                    }
                else:
                    raise PhaseError(
                        "rls",
                        "rls_denied_insert_unexpected_allow",
                        "denied role inserted a patient despite having no matching RLS policy",
                    )
        self.event("rls", "ready", "denied role had table grants but RLS blocked select visibility and insert")
        return {
            "result": "passed",
            "denied_role": "m015_rls_denied",
            "privilege_probe": privilege_row,
            "select_probe": {"result": "blocked_by_rls", "visible_rows": denied_select_count},
            "insert_probe": denied_insert,
        }

    def collect_service_versions(self, tls_evidence: dict[str, Any], api_evidence: dict[str, Any]) -> dict[str, Any]:
        return {
            "postgres_image": os.getenv("M015_POSTGRES_IMAGE", "postgres:16-alpine"),
            "dragonfly_image": os.getenv("M015_DRAGONFLY_IMAGE", "docker.dragonflydb.io/dragonflydb/dragonfly:latest"),
            "backend_image_context": "backend-hormonia/Dockerfile",
            "postgres_server_version": tls_evidence.get("postgres_server_version"),
            "postgres_version_class": tls_evidence.get("postgres_version_class"),
            "fastapi_version": api_evidence.get("health_endpoint", {}).get("version"),
            "python_runtime": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        }

    def build_evidence(
        self,
        *,
        migration_evidence: dict[str, Any],
        tls_evidence: dict[str, Any],
        api_evidence: dict[str, Any],
        catalog_evidence: dict[str, Any],
        synthetic_fixture: dict[str, Any],
        deny_evidence: dict[str, Any],
    ) -> dict[str, Any]:
        fixture_without_raw_id = {k: v for k, v in synthetic_fixture.items() if k != "patient_id"}
        return {
            "schema_version": 1,
            "command": RUNNER_COMMAND,
            "probe_command": PROBE_COMMAND,
            "correlation_id": self.correlation_id,
            "seam": "db",
            "started_at": self.started_at,
            "completed_at": utc_now(),
            "phase_events": self.events,
            "service_versions": self.collect_service_versions(tls_evidence, api_evidence),
            "migrations": migration_evidence,
            "tls": tls_evidence,
            "api_runtime": api_evidence,
            "rls": {
                "catalog": catalog_evidence,
                "allow_probe": fixture_without_raw_id,
                "deny_probe": deny_evidence,
            },
            "redaction": {
                "result": "passed",
                "guardrail": "evidence and summary validated before atomic write",
            },
            "teardown": {
                "result": "pending_runner_teardown",
                "timestamp": None,
                "notes": "Runner trap updates this field after compose down unless --keep-stack is used.",
            },
            "non_goals": [
                "S02 cache/Redis runtime abuse seam is not proven by this DB seam.",
                "S03 provider/webhook runtime seam is not proven by this DB seam.",
                "S04 file/artifact runtime seam is not proven by this DB seam.",
                "S05 cross-seam evidence aggregation is not proven by this DB seam.",
            ],
        }

    def write_artifacts(self, evidence: dict[str, Any]) -> None:
        self.event("evidence", "started", "validating and writing DB seam evidence artifacts")
        summary = render_summary(evidence)
        try:
            write_validated_json(EVIDENCE_JSON, evidence)
            write_validated_text(SUMMARY_MD, summary)
        except RedactionError as exc:
            # Ensure a failed redaction pass cannot leave a new green summary.
            SUMMARY_MD.unlink(missing_ok=True)
            raise PhaseError(
                "evidence",
                "redaction_hit",
                "evidence redaction guard rejected persisted output",
                {"findings": list(exc.findings)},
            ) from exc
        self.event("evidence", "ready", "DB seam evidence JSON and summary passed redaction validation")

    def run(self) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        EVIDENCE_JSON.unlink(missing_ok=True)
        SUMMARY_MD.unlink(missing_ok=True)
        self.event("setup", "ready", "DB seam probe bootstrapped inside backend image")
        self.wait_for_tls_postgres()
        migration_evidence = self.run_alembic_upgrade()
        api_evidence = self.verify_api_runtime_health()
        tls_evidence = self.collect_tls_evidence()
        catalog_evidence = self.collect_catalog_evidence()
        synthetic_fixture = self.insert_synthetic_patient()
        deny_evidence = self.prove_denied_role(str(synthetic_fixture["patient_id"]))
        evidence = self.build_evidence(
            migration_evidence=migration_evidence,
            tls_evidence=tls_evidence,
            api_evidence=api_evidence,
            catalog_evidence=catalog_evidence,
            synthetic_fixture=synthetic_fixture,
            deny_evidence=deny_evidence,
        )
        self.write_artifacts(evidence)


def render_summary(evidence: dict[str, Any]) -> str:
    tls = evidence["tls"]
    migrations = evidence["migrations"]
    api_runtime = evidence["api_runtime"]
    rls = evidence["rls"]
    catalog_tables = rls["catalog"]["tables"]
    deny_probe = rls["deny_probe"]
    table_lines = "\n".join(
        f"- `{table}`: exists={data['exists']}, status={data.get('status', 'present')}, "
        f"rls={data['relrowsecurity']}, "
        f"force={data['relforcerowsecurity']}, public_revoked={data['public_privileges_revoked']}, "
        f"policies={', '.join(data['policy_names'])}"
        for table, data in catalog_tables.items()
    )
    non_goals = "\n".join(f"- {item}" for item in evidence["non_goals"])
    return f"""# M015 DB Seam Evidence Summary

- Command: `{evidence['command']}`
- Probe command: `{evidence['probe_command']}`
- Correlation ID: `{evidence['correlation_id']}`
- Started: `{evidence['started_at']}`
- Completed: `{evidence['completed_at']}`
- Redaction: `{evidence['redaction']['result']}`
- Teardown: `{evidence['teardown']['result']}`

## Migration Proof

- Command: `{migrations['command']}`
- Exit code: `{migrations['exit_code']}`
- Duration: `{migrations['duration_ms']} ms`
- Expected heads: `{', '.join(migrations['expected_heads'])}`
- Current revisions: `{', '.join(migrations['current_revisions'])}`
- Ran as role: `{migrations['ran_as_role']}`
- Superuser bypass: `{migrations['superuser_bypass']}`

## FastAPI Runtime Proof

- `/health` status: `{api_runtime['health_endpoint']['status']}`
- `/health/ready` status: `{api_runtime['readiness_endpoint']['status']}`
- Database dependency: `{api_runtime['readiness_endpoint']['database_dependency_status']}`
- Runtime DB TLS posture: `{api_runtime['database_tls_runtime_check']}`

## TLS Proof

- PostgreSQL SSL setting: `{tls['show_ssl']}`
- Current connection SSL: `{tls['result']}`
- Protocol: `{tls['protocol']}`
- Cipher: `{tls['cipher']}`
- Evidence scope: `{tls['connection_scope']}`

## RLS Catalog Proof

{table_lines}

## RLS Allow/Deny Proof

- App role insert: `{rls['allow_probe']['insert_result']}`
- Synthetic patient evidence: `{rls['allow_probe']['synthetic_patient_id_hash']}`
- Denied role: `{deny_probe['denied_role']}`
- Denied select: `{deny_probe['select_probe']['result']}` with visible rows `{deny_probe['select_probe']['visible_rows']}`
- Denied insert: `{deny_probe['insert_probe']['result']}` with SQLSTATE `{deny_probe['insert_probe']['sqlstate']}`

## Service Versions

- PostgreSQL image: `{evidence['service_versions']['postgres_image']}`
- Dragonfly image: `{evidence['service_versions']['dragonfly_image']}`
- Backend image context: `{evidence['service_versions']['backend_image_context']}`
- PostgreSQL server: `{evidence['service_versions']['postgres_version_class']}`
- FastAPI app version: `{evidence['service_versions']['fastapi_version']}`
- Python runtime: `{evidence['service_versions']['python_runtime']}`

## Non-goals

{non_goals}
"""


def main() -> int:
    try:
        Probe().run()
    except PhaseError as exc:
        detail = exc.details or {}
        safe_detail = sanitize_text(json.dumps(detail, sort_keys=True, default=str), max_chars=1200)
        print(
            f"[{utc_now()}] correlation_id={os.getenv('M015_CORRELATION_ID', 'unknown')} seam=db "
            f"phase={exc.phase} status=failed failure_class={exc.failure_class} "
            f"message={sanitize_text(exc.message, max_chars=600)} details={safe_detail}",
            file=sys.stderr,
            flush=True,
        )
        return 1
    except Exception as exc:  # pragma: no cover - safety net for runtime harness
        print(
            f"[{utc_now()}] correlation_id={os.getenv('M015_CORRELATION_ID', 'unknown')} seam=db "
            f"phase=unknown status=failed failure_class=unexpected_probe_error "
            f"message={sanitize_text(type(exc).__name__, max_chars=200)}",
            file=sys.stderr,
            flush=True,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
