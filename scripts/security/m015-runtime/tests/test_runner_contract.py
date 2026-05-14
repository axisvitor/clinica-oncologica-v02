#!/usr/bin/env python3
"""Contract tests for the M015 synthetic runtime runner.

These tests intentionally avoid Docker so they can validate fail-closed CLI
behavior and static Compose guarantees in ordinary development environments.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
RUNNER = ROOT / "scripts" / "security" / "verify-m015-runtime-security.sh"
COMPOSE_FILE = ROOT / "scripts" / "security" / "m015-runtime" / "docker-compose.yml"
GITIGNORE = ROOT / ".gitignore"


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
        self.assertEqual(result.stdout.strip(), "db")

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
        for service in ("postgres:", "dragonfly:", "api:", "worker:", "db-probe:"):
            self.assertIn(service, text)
        self.assertNotIn("env_file", text)
        self.assertNotIn("wuzapi:", text)
        self.assertNotIn("beat:", text)
        self.assertIn("../../../backend-hormonia", text)
        self.assertIn("ssl=on", text)
        self.assertIn("sslmode=verify-full", text)

    def test_runtime_scratch_is_ignored_but_harness_is_not(self) -> None:
        gitignore = GITIGNORE.read_text(encoding="utf-8")
        self.assertIn(".m015-runtime/", gitignore)
        self.assertNotIn("scripts/security/m015-runtime/", gitignore)


if __name__ == "__main__":
    unittest.main(verbosity=2)
