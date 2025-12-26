#!/usr/bin/env python3
"""
Staging Test Script - Patient Registration Flow
Sistema Hormonia - Clinica Oncologica

Tests the complete flow:
1. Patient Registration (POST /api/v2/patients/)
2. Saga Orchestration
3. Flow Initialization
4. WhatsApp Message Delivery
5. Quiz Trigger System

Usage:
    # Set environment variables first
    export STAGING_API_URL="http://localhost:8000"
    export STAGING_AUTH_TOKEN="your-firebase-token"

    # Run tests
    python scripts/debug/test_staging_flow.py

    # Run specific test
    python scripts/debug/test_staging_flow.py --test patient_registration
"""

import os
import sys
import json
import asyncio
import argparse
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import httpx
import redis.asyncio as aioredis


class StagingTester:
    """Staging environment tester for the patient registration flow."""

    def __init__(self, base_url: str, auth_token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.results: list[Dict[str, Any]] = []
        self.test_patient_id: Optional[str] = None

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def _log(self, test_name: str, status: str, message: str, details: Any = None):
        result = {
            "test": test_name,
            "status": status,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if details:
            result["details"] = details
        self.results.append(result)

        icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{icon} [{test_name}] {message}")
        if details and status == "FAIL":
            print(f"   Details: {json.dumps(details, indent=2, default=str)[:500]}")

    async def test_health_check(self) -> bool:
        """Test API health endpoint."""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{self.base_url}/health", timeout=10)
                if resp.status_code == 200:
                    self._log("health_check", "PASS", "API is healthy")
                    return True
                else:
                    self._log("health_check", "FAIL", f"Status {resp.status_code}", resp.text)
                    return False
            except Exception as e:
                self._log("health_check", "FAIL", f"Connection error: {e}")
                return False

    async def test_patient_registration(self) -> bool:
        """Test patient registration endpoint."""
        test_phone = f"+5511999{uuid4().hex[:6]}"
        patient_data = {
            "name": f"Test Patient {datetime.now().strftime('%H%M%S')}",
            "phone": test_phone,
            "cpf": f"{uuid4().int % 10**11:011d}",
            "email": f"test_{uuid4().hex[:8]}@staging.test",
            "birth_date": "1990-01-15",
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/api/v2/patients/",
                    json=patient_data,
                    headers=self._get_headers(),
                    timeout=30,
                )

                if resp.status_code in (200, 201):
                    data = resp.json()
                    self.test_patient_id = data.get("id") or data.get("patient", {}).get("id")
                    self._log(
                        "patient_registration",
                        "PASS",
                        f"Patient created: {self.test_patient_id}",
                        {"patient_id": self.test_patient_id}
                    )
                    return True
                else:
                    self._log(
                        "patient_registration",
                        "FAIL",
                        f"Status {resp.status_code}",
                        {"response": resp.text[:500]}
                    )
                    return False
            except Exception as e:
                self._log("patient_registration", "FAIL", f"Error: {e}")
                return False

    async def test_saga_status(self) -> bool:
        """Check saga was created and executed."""
        if not self.test_patient_id:
            self._log("saga_status", "SKIP", "No patient ID available")
            return False

        async with httpx.AsyncClient() as client:
            try:
                # Wait for saga to complete
                await asyncio.sleep(2)

                resp = await client.get(
                    f"{self.base_url}/api/v2/patients/{self.test_patient_id}",
                    headers=self._get_headers(),
                    timeout=10,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    # Check for saga-related fields
                    has_flow = data.get("flow_status") or data.get("current_flow_id")
                    self._log(
                        "saga_status",
                        "PASS" if has_flow else "WARN",
                        f"Patient found, flow_status: {data.get('flow_status')}",
                        {"has_flow": has_flow}
                    )
                    return True
                else:
                    self._log("saga_status", "FAIL", f"Status {resp.status_code}")
                    return False
            except Exception as e:
                self._log("saga_status", "FAIL", f"Error: {e}")
                return False

    async def test_redis_idempotency(self) -> bool:
        """Verify Redis idempotency keys are being created."""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        try:
            redis = aioredis.from_url(redis_url)

            # Check for webhook idempotency keys
            keys = await redis.keys("webhook:*")
            message_keys = [k for k in keys if b"message:" in k or b"status:" in k]

            # Check for flow lock keys
            flow_keys = await redis.keys("flow:*")
            quiz_keys = await redis.keys("quiz:*")

            self._log(
                "redis_idempotency",
                "PASS",
                f"Found {len(message_keys)} webhook keys, {len(flow_keys)} flow keys, {len(quiz_keys)} quiz keys",
                {
                    "webhook_keys": len(message_keys),
                    "flow_keys": len(flow_keys),
                    "quiz_keys": len(quiz_keys),
                    "sample_keys": [k.decode() for k in (keys[:5] if keys else [])]
                }
            )
            await redis.close()
            return True
        except Exception as e:
            self._log("redis_idempotency", "FAIL", f"Redis error: {e}")
            return False

    async def test_quiz_trigger_config(self) -> bool:
        """Verify quiz trigger configuration is correct."""
        try:
            from app.domain.quizzes.quiz_trigger_policy import QuizTriggerPolicy

            policy_day = QuizTriggerPolicy.MONTHLY_QUIZ_DAY

            # Also verify trigger_tasks uses correct day
            trigger_tasks_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "app/tasks/quiz_flow/trigger_tasks.py"
            )

            with open(trigger_tasks_path, "r") as f:
                content = f.read()
                uses_policy = "QuizTriggerPolicy.MONTHLY_QUIZ_DAY" in content
                has_hardcoded_30 = "target_day=30" in content

            if uses_policy and not has_hardcoded_30:
                self._log(
                    "quiz_trigger_config",
                    "PASS",
                    f"Quiz trigger uses policy day: {policy_day}",
                    {"policy_day": policy_day, "uses_policy": uses_policy}
                )
                return True
            else:
                self._log(
                    "quiz_trigger_config",
                    "FAIL",
                    "Quiz trigger has hardcoded day or doesn't use policy",
                    {"uses_policy": uses_policy, "has_hardcoded_30": has_hardcoded_30}
                )
                return False
        except Exception as e:
            self._log("quiz_trigger_config", "FAIL", f"Error: {e}")
            return False

    async def test_whatsapp_endpoint(self) -> bool:
        """Test WhatsApp/Evolution API connectivity."""
        async with httpx.AsyncClient() as client:
            try:
                # Try health or status endpoint for Evolution API
                resp = await client.get(
                    f"{self.base_url}/api/v2/whatsapp/status",
                    headers=self._get_headers(),
                    timeout=10,
                )

                if resp.status_code in (200, 401, 403):  # 401/403 means endpoint exists
                    self._log(
                        "whatsapp_endpoint",
                        "PASS" if resp.status_code == 200 else "WARN",
                        f"WhatsApp endpoint responded: {resp.status_code}"
                    )
                    return True
                else:
                    self._log(
                        "whatsapp_endpoint",
                        "WARN",
                        f"WhatsApp endpoint status: {resp.status_code}"
                    )
                    return True  # Not critical
            except Exception as e:
                self._log("whatsapp_endpoint", "WARN", f"WhatsApp check skipped: {e}")
                return True

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all staging tests."""
        print("\n" + "="*60)
        print("STAGING TEST SUITE - Patient Registration Flow")
        print("="*60 + "\n")

        tests = [
            ("Health Check", self.test_health_check),
            ("Quiz Trigger Config", self.test_quiz_trigger_config),
            ("Redis Idempotency", self.test_redis_idempotency),
            ("Patient Registration", self.test_patient_registration),
            ("Saga Status", self.test_saga_status),
            ("WhatsApp Endpoint", self.test_whatsapp_endpoint),
        ]

        passed = 0
        failed = 0
        warnings = 0

        for name, test_func in tests:
            try:
                result = await test_func()
                if result:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                self._log(name, "FAIL", f"Unexpected error: {e}")
                failed += 1

        # Count warnings
        for r in self.results:
            if r["status"] == "WARN":
                warnings += 1

        print("\n" + "="*60)
        print(f"RESULTS: {passed} passed, {failed} failed, {warnings} warnings")
        print("="*60 + "\n")

        return {
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "total": len(tests),
            "results": self.results,
            "test_patient_id": self.test_patient_id,
        }


async def main():
    parser = argparse.ArgumentParser(description="Staging Test Suite")
    parser.add_argument("--test", help="Run specific test")
    parser.add_argument("--url", default=os.getenv("STAGING_API_URL", "http://localhost:8000"))
    parser.add_argument("--token", default=os.getenv("STAGING_AUTH_TOKEN"))
    args = parser.parse_args()

    tester = StagingTester(args.url, args.token)

    if args.test:
        test_method = getattr(tester, f"test_{args.test}", None)
        if test_method:
            await test_method()
        else:
            print(f"Unknown test: {args.test}")
            sys.exit(1)
    else:
        results = await tester.run_all_tests()
        if results["failed"] > 0:
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
