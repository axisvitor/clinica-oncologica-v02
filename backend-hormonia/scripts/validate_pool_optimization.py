#!/usr/bin/env python3
"""
Pool Optimization Validation Script

Validates database and Redis pool configurations to ensure
optimizations are correctly applied.

Usage:
    python scripts/validate_pool_optimization.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from typing import Dict, Any, List
from datetime import datetime
import json


class PoolOptimizationValidator:
    """Validates pool optimization implementation."""

    def __init__(self):
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "checks_passed": 0,
            "checks_failed": 0,
            "checks": []
        }

    def add_check(self, name: str, passed: bool, message: str, details: Dict[str, Any] = None):
        """Add validation check result."""
        self.results["checks"].append({
            "name": name,
            "passed": passed,
            "message": message,
            "details": details or {}
        })

        if passed:
            self.results["checks_passed"] += 1
            print(f"✅ {name}: {message}")
        else:
            self.results["checks_failed"] += 1
            print(f"❌ {name}: {message}")

        if details:
            print(f"   Details: {json.dumps(details, indent=2)}")

    def validate_database_settings(self):
        """Validate database pool configuration."""
        print("\n🔍 Validating Database Pool Settings...")

        try:
            from app.config import settings

            # Check pool size
            pool_size = settings.DATABASE_POOL_SIZE
            if pool_size >= 50:
                self.add_check(
                    "Database Pool Size",
                    True,
                    f"Pool size is {pool_size} (optimal: ≥50)",
                    {"pool_size": pool_size, "recommended": 50}
                )
            else:
                self.add_check(
                    "Database Pool Size",
                    False,
                    f"Pool size is {pool_size} (should be ≥50 to fix 92% utilization)",
                    {"pool_size": pool_size, "recommended": 50}
                )

            # Check overflow
            overflow = settings.DATABASE_POOL_MAX_OVERFLOW
            if overflow <= 20:
                self.add_check(
                    "Database Pool Overflow",
                    True,
                    f"Overflow is {overflow} (optimal: ≤20 for predictability)",
                    {"overflow": overflow, "recommended": 20}
                )
            else:
                self.add_check(
                    "Database Pool Overflow",
                    False,
                    f"Overflow is {overflow} (should be ≤20 for better predictability)",
                    {"overflow": overflow, "recommended": 20}
                )

            # Check recycle time
            recycle = settings.DATABASE_POOL_RECYCLE_SECONDS
            if recycle <= 1800:
                self.add_check(
                    "Database Pool Recycle Time",
                    True,
                    f"Recycle time is {recycle}s (optimal: ≤1800s to prevent stale SSL)",
                    {"recycle_seconds": recycle, "recommended": 1800}
                )
            else:
                self.add_check(
                    "Database Pool Recycle Time",
                    False,
                    f"Recycle time is {recycle}s (should be ≤1800s to prevent stale SSL connections)",
                    {"recycle_seconds": recycle, "recommended": 1800}
                )

            # Check pre-ping
            pre_ping = settings.DATABASE_POOL_PRE_PING
            if pre_ping:
                self.add_check(
                    "Database Pool Pre-Ping",
                    True,
                    "Pre-ping is enabled (prevents SSL errors)",
                    {"pre_ping": pre_ping}
                )
            else:
                self.add_check(
                    "Database Pool Pre-Ping",
                    False,
                    "Pre-ping is disabled (should be enabled to prevent SSL errors)",
                    {"pre_ping": pre_ping}
                )

            # Check reset on return
            reset_mode = settings.DATABASE_POOL_RESET_ON_RETURN
            if reset_mode == "commit":
                self.add_check(
                    "Database Pool Reset Mode",
                    True,
                    f"Reset mode is '{reset_mode}' (optimal: cleans state)",
                    {"reset_mode": reset_mode}
                )
            else:
                self.add_check(
                    "Database Pool Reset Mode",
                    False,
                    f"Reset mode is '{reset_mode}' (recommended: 'commit')",
                    {"reset_mode": reset_mode, "recommended": "commit"}
                )

        except Exception as e:
            self.add_check(
                "Database Settings Import",
                False,
                f"Failed to import settings: {str(e)}"
            )

    def validate_redis_settings(self):
        """Validate Redis pool configuration."""
        print("\n🔍 Validating Redis Pool Settings...")

        try:
            from app.config import settings

            # Check pool size
            pool_size = settings.REDIS_POOL_MAX_CONNECTIONS
            if pool_size <= 20:
                self.add_check(
                    "Redis Pool Size",
                    True,
                    f"Pool size is {pool_size} (optimal: ≤20, Redis needs less than DB)",
                    {"pool_size": pool_size, "recommended": 20}
                )
            else:
                self.add_check(
                    "Redis Pool Size",
                    False,
                    f"Pool size is {pool_size} (should be ≤20, Redis needs fewer connections)",
                    {"pool_size": pool_size, "recommended": 20}
                )

            # Check socket timeout
            socket_timeout = settings.REDIS_SOCKET_TIMEOUT_SECONDS
            if socket_timeout <= 5.0:
                self.add_check(
                    "Redis Socket Timeout",
                    True,
                    f"Socket timeout is {socket_timeout}s (optimal: ≤5s for SSL)",
                    {"timeout_seconds": socket_timeout, "recommended": 5.0}
                )
            else:
                self.add_check(
                    "Redis Socket Timeout",
                    False,
                    f"Socket timeout is {socket_timeout}s (should be ≤5s, SSL should be fast)",
                    {"timeout_seconds": socket_timeout, "recommended": 5.0}
                )

            # Check connect timeout
            connect_timeout = settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS
            if connect_timeout <= 2.0:
                self.add_check(
                    "Redis Connect Timeout",
                    True,
                    f"Connect timeout is {connect_timeout}s (optimal: ≤2s)",
                    {"timeout_seconds": connect_timeout, "recommended": 2.0}
                )
            else:
                self.add_check(
                    "Redis Connect Timeout",
                    False,
                    f"Connect timeout is {connect_timeout}s (should be ≤2s for quick connection)",
                    {"timeout_seconds": connect_timeout, "recommended": 2.0}
                )

            # Check SSL warmup
            warmup_enabled = getattr(settings, 'REDIS_SSL_CONNECTION_POOL_WARMUP', False)
            if warmup_enabled:
                self.add_check(
                    "Redis SSL Pool Warmup",
                    True,
                    "SSL pool warmup is enabled (amortizes SSL handshake cost)",
                    {"warmup_enabled": warmup_enabled}
                )
            else:
                self.add_check(
                    "Redis SSL Pool Warmup",
                    False,
                    "SSL pool warmup is disabled (should enable to reduce first-request latency)",
                    {"warmup_enabled": warmup_enabled}
                )

            # Check health check
            health_check = getattr(settings, 'REDIS_ENABLE_HEALTH_CHECK', False)
            if health_check:
                self.add_check(
                    "Redis Health Check",
                    True,
                    "Health check is enabled (maintains connection validity)",
                    {"health_check_enabled": health_check}
                )
            else:
                self.add_check(
                    "Redis Health Check",
                    False,
                    "Health check is disabled (should enable for connection validation)",
                    {"health_check_enabled": health_check}
                )

        except Exception as e:
            self.add_check(
                "Redis Settings Import",
                False,
                f"Failed to import settings: {str(e)}"
            )

    async def validate_database_pool_runtime(self):
        """Validate database pool at runtime."""
        print("\n🔍 Validating Database Pool Runtime...")

        try:
            from app.database import get_pool_status, connection_manager

            # Check service role engine
            service_pool = get_pool_status(use_service_role=True)

            pool_size = service_pool.get('pool_size', 0)
            checked_out = service_pool.get('checked_out', 0)
            utilization = (checked_out / pool_size * 100) if pool_size > 0 else 0

            self.add_check(
                "Database Pool Initialized",
                True,
                f"Pool initialized with {pool_size} connections",
                service_pool
            )

            if utilization < 85:
                self.add_check(
                    "Database Pool Utilization",
                    True,
                    f"Pool utilization is {utilization:.1f}% (healthy: <85%)",
                    {"utilization": utilization, "threshold": 85}
                )
            elif utilization < 92:
                self.add_check(
                    "Database Pool Utilization",
                    True,
                    f"Pool utilization is {utilization:.1f}% (warning: 85-92%)",
                    {"utilization": utilization, "threshold": 92}
                )
            else:
                self.add_check(
                    "Database Pool Utilization",
                    False,
                    f"Pool utilization is {utilization:.1f}% (critical: ≥92%)",
                    {"utilization": utilization, "threshold": 92}
                )

        except Exception as e:
            self.add_check(
                "Database Pool Runtime Check",
                False,
                f"Failed to check pool runtime: {str(e)}"
            )

    async def validate_redis_pool_runtime(self):
        """Validate Redis pool at runtime."""
        print("\n🔍 Validating Redis Pool Runtime...")

        try:
            from app.core.redis_manager import get_redis_manager

            manager = get_redis_manager()

            # Test connection
            client = await manager.get_async_client()
            await client.ping()

            self.add_check(
                "Redis Connection",
                True,
                "Successfully connected to Redis",
                {}
            )

            # Get pool stats
            pool_stats = await manager.get_pool_stats_async()

            if pool_stats.get('status') == 'healthy':
                self.add_check(
                    "Redis Pool Status",
                    True,
                    "Pool is healthy",
                    pool_stats
                )
            else:
                self.add_check(
                    "Redis Pool Status",
                    False,
                    f"Pool status: {pool_stats.get('status')}",
                    pool_stats
                )

        except Exception as e:
            self.add_check(
                "Redis Pool Runtime Check",
                False,
                f"Failed to check pool runtime: {str(e)}"
            )

    def validate_performance_module(self):
        """Validate performance settings module exists."""
        print("\n🔍 Validating Performance Module...")

        try:
            from app.config.settings.performance import PerformanceSettings

            settings = PerformanceSettings()

            # Check critical methods exist
            methods = [
                'get_database_pool_size',
                'get_pool_utilization_status',
                'get_cache_ttl_for_data_type'
            ]

            for method in methods:
                if hasattr(settings, method):
                    self.add_check(
                        f"Performance Method: {method}",
                        True,
                        f"Method '{method}' exists",
                        {}
                    )
                else:
                    self.add_check(
                        f"Performance Method: {method}",
                        False,
                        f"Method '{method}' missing",
                        {}
                    )

            # Test pool size calculation
            pool_size = settings.get_database_pool_size(worker_count=8)
            expected = 8 * 4  # workers * connections_per_worker
            if pool_size == expected:
                self.add_check(
                    "Dynamic Pool Sizing",
                    True,
                    f"Pool sizing formula works: 8 workers = {pool_size} connections",
                    {"workers": 8, "pool_size": pool_size}
                )
            else:
                self.add_check(
                    "Dynamic Pool Sizing",
                    False,
                    f"Pool sizing incorrect: expected {expected}, got {pool_size}",
                    {"workers": 8, "expected": expected, "actual": pool_size}
                )

        except ImportError as e:
            self.add_check(
                "Performance Module Import",
                False,
                f"Failed to import PerformanceSettings: {str(e)}"
            )
        except Exception as e:
            self.add_check(
                "Performance Module Validation",
                False,
                f"Validation error: {str(e)}"
            )

    async def run_all_validations(self):
        """Run all validation checks."""
        print("=" * 80)
        print("🚀 Pool Optimization Validation")
        print("=" * 80)

        # Configuration checks
        self.validate_database_settings()
        self.validate_redis_settings()
        self.validate_performance_module()

        # Runtime checks
        await self.validate_database_pool_runtime()
        await self.validate_redis_pool_runtime()

        # Summary
        print("\n" + "=" * 80)
        print("📊 Validation Summary")
        print("=" * 80)
        print(f"✅ Checks Passed: {self.results['checks_passed']}")
        print(f"❌ Checks Failed: {self.results['checks_failed']}")
        print(f"📈 Success Rate: {self.results['checks_passed'] / (self.results['checks_passed'] + self.results['checks_failed']) * 100:.1f}%")

        if self.results['checks_failed'] == 0:
            print("\n🎉 All validations passed! Pool optimization is correctly configured.")
            return 0
        else:
            print(f"\n⚠️  {self.results['checks_failed']} validation(s) failed. Please review the configuration.")
            return 1

    def save_results(self, output_file: str = "pool_validation_results.json"):
        """Save validation results to JSON file."""
        output_path = Path(__file__).parent.parent / output_file

        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\n💾 Results saved to: {output_path}")


async def main():
    """Main validation entry point."""
    validator = PoolOptimizationValidator()

    try:
        exit_code = await validator.run_all_validations()
        validator.save_results()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ Validation failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
