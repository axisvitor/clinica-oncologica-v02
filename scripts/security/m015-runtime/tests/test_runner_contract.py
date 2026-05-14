#!/usr/bin/env python3
"""Contract tests for the M015 synthetic runtime runner.

These tests intentionally avoid Docker so they can validate fail-closed CLI
behavior and static Compose guarantees in ordinary development environments.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
RUNNER = ROOT / "scripts" / "security" / "verify-m015-runtime-security.sh"
COMPOSE_FILE = ROOT / "scripts" / "security" / "m015-runtime" / "docker-compose.yml"
GITIGNORE = ROOT / ".gitignore"

sys.path.insert(0, str(ROOT / "scripts" / "security" / "m015-runtime"))
from redaction import RedactionError, validate_no_sensitive_evidence  # noqa: E402


class M015RunnerContractTests(unittest.TestCase):
    def run_runner(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "M015_PROJECT_NAME": "m015-contract-test",
                "M015_API_PORT": "18180",
                "M015_POSTGRES_PORT": "15433",
            }
        )
        return subprocess.run(
            [str(RUNNER), *args],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_help_documents_db_seam_and_failure_closed_options(self) -> None:
        result = self.run_runner("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--seam db", result.stdout)
        self.assertIn("--list-seams", result.stdout)
        self.assertIn("--teardown-only", result.stdout)

    def test_list_seams_only_lists_implemented_db_seam(self) -> None:
        result = self.run_runner("--list-seams")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().splitlines(), ["db", "session"])

    def test_unknown_seam_fails_before_setup_phase(self) -> None:
        result = self.run_runner("--seam", "provider")
        self.assertNotEqual(result.returncode, 0)
        combined = result.stdout + result.stderr
        self.assertIn("unknown seam", combined.lower())
        self.assertNotIn("phase=setup", combined)

    def test_missing_seam_fails_closed(self) -> None:
        result = self.run_runner()
        self.assertNotEqual(result.returncode, 0)
        combined = result.stdout + result.stderr
        self.assertIn("--seam db", combined)
        self.assertNotIn("green", combined.lower())

    def test_compose_static_contract(self) -> None:
        text = COMPOSE_FILE.read_text(encoding="utf-8")
        for service in ("postgres:", "dragonfly:", "api:", "worker:", "db-probe:", "session-probe:"):
            self.assertIn(service, text)
        self.assertNotIn("env_file", text)
        self.assertNotIn("backend-hormonia/.env", text)
        self.assertNotIn("/mnt/c/", text)
        self.assertNotIn("wuzapi:", text)
        self.assertNotIn("gemini:", text)
        self.assertNotIn("GOOGLE_APPLICATION_CREDENTIALS", text)
        self.assertNotIn("firebase-adminsdk", text)
        self.assertNotIn("beat:", text)
        self.assertIn("../../../backend-hormonia", text)
        self.assertIn("build: *backend_build", text)
        self.assertIn("command: [\"python\", \"/m015-runtime/db_seam.py\"]", text)
        self.assertIn("command: [\"python\", \"/m015-runtime/session_seam.py\"]", text)
        self.assertIn("command: [\"taskiq\", \"worker\", \"app.taskiq_broker:broker\", \"app.tasks.m015_session_security_taskiq\"]", text)
        self.assertIn("./db_seam.py:/m015-runtime/db_seam.py:ro", text)
        self.assertIn("./session_seam.py:/m015-runtime/session_seam.py:ro", text)
        self.assertIn("./m015_session_security_taskiq.py:/app/app/tasks/m015_session_security_taskiq.py:ro", text)
        self.assertIn("./m015_session_security_taskiq.py:/m015-runtime/m015_session_security_taskiq.py:ro", text)
        self.assertIn("./redaction.py:/m015-runtime/redaction.py:ro", text)
        self.assertIn("../../../backend-hormonia/docs/reports/security/m015:/m015-evidence-output", text)
        self.assertIn("ssl=on", text)
        self.assertIn("sslmode=verify-full", text)
        runner_text = RUNNER.read_text(encoding="utf-8")
        self.assertIn("[Cc]ookie", runner_text)
        self.assertIn("[Ss]et-[Cc]ookie", runner_text)

    def test_runtime_scratch_is_ignored_but_harness_is_not(self) -> None:
        gitignore = GITIGNORE.read_text(encoding="utf-8")
        self.assertIn(".m015-runtime/", gitignore)
        self.assertNotIn("scripts/security/m015-runtime/", gitignore)

    def test_redaction_rejects_sensitive_evidence_shapes(self) -> None:
        sensitive_examples = [
            "postgresql://user:password@postgres:5432/app",
            "-----BEGIN PRIVATE KEY-----\nnot-real\n-----END PRIVATE KEY-----",
            "-----BEGIN CERTIFICATE-----\nnot-real\n-----END CERTIFICATE-----",
            "Authorization: Bearer token-value",
            "Cookie: session=abc",
            "ACCESS_TOKEN=secret-token",
            "firebase_admin service_account private_key_id client_x509_cert_url",
            "patient name: Maria Silva",
            "cpf=123.456.789-10",
            "email: person@example.com",
            "phone=+55 (11) 91234-5678",
            "/mnt/c/Users/example/private/file.txt",
            "/m015-certs/ca.crt",
            "stderr=ERROR SQL: insert into patients (name, cpf) values ('Maria Silva', 'x')",
        ]
        for value in sensitive_examples:
            with self.subTest(value=value):
                with self.assertRaises(RedactionError):
                    validate_no_sensitive_evidence({"value": value})

    def test_redaction_allows_sanitized_synthetic_evidence_shape(self) -> None:
        validate_no_sensitive_evidence(
            {
                "command": "./scripts/security/verify-m015-runtime-security.sh --seam db",
                "tls": {"protocol": "TLSv1.3", "cipher": "TLS_AES_256_GCM_SHA384"},
                "synthetic_patient_id_hash": "a" * 64,
                "contact": "synthetic@example.invalid",
                "path_policy": "generated CA mount; raw path omitted",
            }
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
