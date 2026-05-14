#!/usr/bin/env python3
"""Contract tests for M015 synthetic provider stubs."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from provider_stub import (
    append_observation_jsonl,
    build_stub_response,
    endpoint_name_for_path,
    provider_for_path,
    scenario_from_request,
)
from redaction import RedactionError, validate_no_sensitive_evidence


class ProviderStubContractTests(unittest.TestCase):
    def test_classifies_wuzapi_and_gemini_paths_without_query_values(self) -> None:
        self.assertEqual(provider_for_path("/chat/send/text?scenario=success"), "wuzapi")
        self.assertEqual(endpoint_name_for_path("/chat/send/text?scenario=success"), "send_text")
        self.assertEqual(provider_for_path("/v1beta/models/gemini:generateContent"), "gemini")
        self.assertEqual(endpoint_name_for_path("/v1beta/models/gemini:generateContent"), "generate_content")
        self.assertEqual(provider_for_path("/not-a-provider"), "unknown")

    def test_resolves_scenario_aliases_from_query_or_header(self) -> None:
        self.assertEqual(scenario_from_request("/chat/send/text?scenario=5xx", {"Token": "x"}), "server_error")
        self.assertEqual(
            scenario_from_request("/chat/send/text", {"Token": "x", "X-M015-Scenario": "replay"}),
            "duplicate_or_replay",
        )
        self.assertEqual(scenario_from_request("/chat/send/text", {"Token": "x"}), "success")

    def test_wuzapi_success_observation_omits_token_and_raw_body(self) -> None:
        body = b'{"patient_name":"Maria Silva","phone":"+55 (11) 91234-5678","message":"secret"}'
        response = build_stub_response(
            "POST",
            "/chat/send/text?scenario=success",
            {"Token": "super-secret-provider-token", "Cookie": "session=secret"},
            body,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.observation["provider"], "wuzapi")
        self.assertEqual(response.observation["endpoint"], "send_text")
        self.assertTrue(response.observation["token_header_present"])
        self.assertTrue(response.observation["cookie_header_present"])
        self.assertTrue(response.observation["request_body_present"])
        self.assertEqual(len(response.observation["request_body_sha256"]), 64)
        self.assertFalse(response.observation["raw_headers_persisted"])
        self.assertFalse(response.observation["raw_request_body_persisted"])
        validate_no_sensitive_evidence(asdict(response))
        serialized = json.dumps(asdict(response), sort_keys=True)
        self.assertNotIn("super-secret-provider-token", serialized)
        self.assertNotIn("Maria Silva", serialized)
        self.assertNotIn("91234", serialized)
        self.assertNotIn("Cookie:", serialized)

    def test_wuzapi_requires_token_header_but_does_not_persist_missing_header_value(self) -> None:
        response = build_stub_response("POST", "/chat/send/text", {}, b"{}")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.observation["reason"], "missing_token_header")
        self.assertFalse(response.observation["token_header_present"])
        validate_no_sensitive_evidence(asdict(response))

    def test_provider_scenarios_return_deterministic_status_classes(self) -> None:
        scenarios = {
            "client_error": (400, "client_error"),
            "rate_limited": (429, "rate_limited"),
            "server_error": (503, "server_error"),
            "timeout": (504, "timeout"),
            "duplicate_or_replay": (409, "duplicate_or_replay"),
        }
        for scenario, (status_code, reason) in scenarios.items():
            with self.subTest(scenario=scenario):
                response = build_stub_response(
                    "POST",
                    f"/chat/send/text?scenario={scenario}",
                    {"Token": "synthetic-token"},
                    b"{}",
                )
                self.assertEqual(response.status_code, status_code)
                self.assertEqual(response.observation["reason"], reason)
                if scenario == "timeout":
                    self.assertGreater(response.delay_seconds, 0)
                validate_no_sensitive_evidence(asdict(response))

    def test_gemini_success_response_is_synthetic_and_redaction_safe(self) -> None:
        response = build_stub_response(
            "POST",
            "/v1beta/models/gemini-3-flash-preview:generateContent",
            {"Authorization": "Bearer secret-api-key"},
            b'{"contents":[{"parts":[{"text":"cpf=123.456.789-10"}]}]}',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.observation["provider"], "gemini")
        self.assertEqual(response.observation["endpoint"], "generate_content")
        self.assertTrue(response.observation["authorization_header_present"])
        validate_no_sensitive_evidence(asdict(response))
        serialized = json.dumps(asdict(response), sort_keys=True)
        self.assertIn("m015 synthetic gemini response", serialized)
        self.assertNotIn("secret-api-key", serialized)
        self.assertNotIn("123.456.789-10", serialized)

    def test_observation_append_writes_only_redaction_validated_jsonl(self) -> None:
        response = build_stub_response("GET", "/session/status", {"Token": "synthetic-token"})
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "observations.jsonl"
            append_observation_jsonl(path, response.observation)
            line = path.read_text(encoding="utf-8").strip()
            parsed = json.loads(line)
            self.assertEqual(parsed["endpoint"], "session_status")
            validate_no_sensitive_evidence(parsed)

    def test_observation_append_rejects_sensitive_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "observations.jsonl"
            with self.assertRaises(RedactionError):
                append_observation_jsonl(
                    path,
                    {"raw_header": "Authorization: Bearer secret-token", "endpoint": "send_text"},
                )
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
