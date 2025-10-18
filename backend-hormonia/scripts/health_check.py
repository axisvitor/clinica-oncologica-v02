#!/usr/bin/env python3
"""
Backend Health Check Script

Comprehensive health check for the backend application.
Checks environment variables, database connectivity, Redis, and core services.

Usage:
    python scripts/health_check.py
    python scripts/health_check.py --quick
    python scripts/health_check.py --verbose
"""

import sys
import os
import argparse
from typing import Dict, List, Tuple
from enum import Enum

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class HealthStatus(Enum):
    """Health check status"""

    OK = "✅"
    WARNING = "⚠️"
    ERROR = "❌"
    INFO = "ℹ️"


class HealthCheck:
    """Health check manager"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: List[Tuple[str, HealthStatus, str]] = []
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def add_result(self, name: str, status: HealthStatus, message: str):
        """Add a health check result"""
        self.results.append((name, status, message))
        if status == HealthStatus.ERROR:
            self.errors.append(f"{name}: {message}")
        elif status == HealthStatus.WARNING:
            self.warnings.append(f"{name}: {message}")

    def print_result(self, name: str, status: HealthStatus, message: str):
        """Print a single result"""
        print(f"{status.value} {name}: {message}")

    def check_env_vars(self) -> bool:
        """Check required environment variables"""
        print("\n🔍 Checking Environment Variables...")

        required_vars = [
            "DATABASE_URL",
            "REDIS_URL",
            "SECRET_KEY",
            "FIREBASE_CREDENTIALS",
        ]

        optional_vars = [
            "EVOLUTION_API_URL",
            "EVOLUTION_API_KEY",
            "GEMINI_API_KEY",
            "SENTRY_DSN",
        ]

        all_ok = True

        # Check required variables
        for var in required_vars:
            if os.getenv(var):
                self.add_result(var, HealthStatus.OK, "Set")
                if self.verbose:
                    self.print_result(var, HealthStatus.OK, "Set")
            else:
                self.add_result(var, HealthStatus.ERROR, "Missing")
                self.print_result(var, HealthStatus.ERROR, "Missing (REQUIRED)")
                all_ok = False

        # Check optional variables
        for var in optional_vars:
            if os.getenv(var):
                if self.verbose:
                    self.add_result(var, HealthStatus.OK, "Set")
                    self.print_result(var, HealthStatus.OK, "Set (optional)")
            else:
                self.add_result(var, HealthStatus.WARNING, "Not set")
                if self.verbose:
                    self.print_result(var, HealthStatus.WARNING, "Not set (optional)")

        if all_ok:
            print(f"{HealthStatus.OK.value} All required environment variables are set")
        else:
            print(
                f"{HealthStatus.ERROR.value} Some required environment variables are missing"
            )

        return all_ok

    def check_database(self) -> bool:
        """Check database connectivity"""
        print("\n🔍 Checking Database Connection...")

        try:
            from sqlalchemy import create_engine, text
            from app.core.config import get_settings

            settings = get_settings()

            # Create engine with timeout
            engine = create_engine(
                settings.database_url,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 5},
            )

            # Test connection
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()

            self.add_result("Database", HealthStatus.OK, "Connected successfully")
            self.print_result("Database", HealthStatus.OK, "Connected successfully")

            # Check if tables exist
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                )
                table_count = result.fetchone()[0]

                if table_count > 0:
                    self.add_result(
                        "Database Tables",
                        HealthStatus.OK,
                        f"{table_count} tables found",
                    )
                    if self.verbose:
                        self.print_result(
                            "Database Tables",
                            HealthStatus.OK,
                            f"{table_count} tables found",
                        )
                else:
                    self.add_result(
                        "Database Tables",
                        HealthStatus.WARNING,
                        "No tables found - run migrations",
                    )
                    self.print_result(
                        "Database Tables",
                        HealthStatus.WARNING,
                        "No tables found - run migrations",
                    )

            engine.dispose()
            return True

        except ImportError as e:
            self.add_result("Database", HealthStatus.ERROR, f"Import error: {str(e)}")
            self.print_result("Database", HealthStatus.ERROR, f"Import error: {str(e)}")
            return False
        except Exception as e:
            self.add_result(
                "Database", HealthStatus.ERROR, f"Connection failed: {str(e)}"
            )
            self.print_result(
                "Database", HealthStatus.ERROR, f"Connection failed: {str(e)}"
            )
            return False

    def check_redis(self) -> bool:
        """Check Redis connectivity"""
        print("\n🔍 Checking Redis Connection...")

        try:
            import redis
            from app.core.config import get_settings

            settings = get_settings()

            # Parse Redis URL
            redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )

            # Test connection
            redis_client.ping()

            self.add_result("Redis", HealthStatus.OK, "Connected successfully")
            self.print_result("Redis", HealthStatus.OK, "Connected successfully")

            # Check Redis info
            if self.verbose:
                info = redis_client.info("server")
                version = info.get("redis_version", "unknown")
                self.print_result("Redis Version", HealthStatus.INFO, version)

            redis_client.close()
            return True

        except ImportError as e:
            self.add_result("Redis", HealthStatus.ERROR, f"Import error: {str(e)}")
            self.print_result("Redis", HealthStatus.ERROR, f"Import error: {str(e)}")
            return False
        except Exception as e:
            self.add_result("Redis", HealthStatus.ERROR, f"Connection failed: {str(e)}")
            self.print_result(
                "Redis", HealthStatus.ERROR, f"Connection failed: {str(e)}"
            )
            return False

    def check_services(self) -> bool:
        """Check if core services can be imported"""
        print("\n🔍 Checking Core Services...")

        services_to_check = [
            ("app.main", "FastAPI app"),
            ("app.core.config", "Configuration"),
            ("app.core.database", "Database core"),
            ("app.core.exceptions", "Exception handling"),
            ("app.models", "Database models"),
            ("app.api.v1", "API v1 routers"),
        ]

        all_ok = True

        for module_name, description in services_to_check:
            try:
                __import__(module_name)
                self.add_result(description, HealthStatus.OK, "Import successful")
                if self.verbose:
                    self.print_result(description, HealthStatus.OK, "Import successful")
            except Exception as e:
                self.add_result(
                    description, HealthStatus.ERROR, f"Import failed: {str(e)}"
                )
                self.print_result(
                    description, HealthStatus.ERROR, f"Import failed: {str(e)}"
                )
                all_ok = False

        if all_ok:
            print(f"{HealthStatus.OK.value} All core services can be imported")
        else:
            print(f"{HealthStatus.ERROR.value} Some core services failed to import")

        return all_ok

    def check_migrations(self) -> bool:
        """Check if migrations are up to date"""
        print("\n🔍 Checking Migrations Status...")

        try:
            from alembic.config import Config
            from alembic import command
            from alembic.script import ScriptDirectory
            from alembic.runtime.migration import MigrationContext
            from sqlalchemy import create_engine
            from app.core.config import get_settings

            settings = get_settings()

            # Create alembic config
            alembic_cfg = Config("alembic.ini")
            script = ScriptDirectory.from_config(alembic_cfg)

            # Get current revision from database
            engine = create_engine(settings.database_url)
            with engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current_rev = context.get_current_revision()

            # Get head revision from scripts
            head_rev = script.get_current_head()

            if current_rev == head_rev:
                self.add_result(
                    "Migrations",
                    HealthStatus.OK,
                    f"Up to date (revision: {current_rev})",
                )
                self.print_result(
                    "Migrations",
                    HealthStatus.OK,
                    f"Up to date (revision: {current_rev[:8] if current_rev else 'none'})",
                )
            else:
                self.add_result(
                    "Migrations",
                    HealthStatus.WARNING,
                    f"Not up to date. Current: {current_rev}, Head: {head_rev}",
                )
                self.print_result(
                    "Migrations",
                    HealthStatus.WARNING,
                    f"Not up to date. Run 'alembic upgrade head'",
                )

            engine.dispose()
            return True

        except Exception as e:
            self.add_result(
                "Migrations", HealthStatus.WARNING, f"Check failed: {str(e)}"
            )
            if self.verbose:
                self.print_result(
                    "Migrations", HealthStatus.WARNING, f"Check failed: {str(e)}"
                )
            return False

    def check_python_version(self) -> bool:
        """Check Python version"""
        print("\n🔍 Checking Python Version...")

        major, minor = sys.version_info[:2]
        version_str = f"{major}.{minor}"

        if major == 3 and minor >= 10:
            self.add_result("Python Version", HealthStatus.OK, f"Python {version_str}")
            self.print_result(
                "Python Version", HealthStatus.OK, f"Python {version_str}"
            )
            return True
        else:
            self.add_result(
                "Python Version",
                HealthStatus.WARNING,
                f"Python {version_str} (recommend 3.10+)",
            )
            self.print_result(
                "Python Version",
                HealthStatus.WARNING,
                f"Python {version_str} (recommend 3.10+)",
            )
            return False

    def check_dependencies(self) -> bool:
        """Check if critical dependencies are installed"""
        print("\n🔍 Checking Dependencies...")

        critical_deps = [
            "fastapi",
            "sqlalchemy",
            "redis",
            "celery",
            "alembic",
            "pydantic",
        ]

        all_ok = True

        for dep in critical_deps:
            try:
                __import__(dep)
                if self.verbose:
                    self.add_result(f"Dependency: {dep}", HealthStatus.OK, "Installed")
                    self.print_result(
                        f"Dependency: {dep}", HealthStatus.OK, "Installed"
                    )
            except ImportError:
                self.add_result(
                    f"Dependency: {dep}", HealthStatus.ERROR, "Not installed"
                )
                self.print_result(
                    f"Dependency: {dep}", HealthStatus.ERROR, "Not installed"
                )
                all_ok = False

        if all_ok:
            print(f"{HealthStatus.OK.value} All critical dependencies are installed")
        else:
            print(f"{HealthStatus.ERROR.value} Some critical dependencies are missing")

        return all_ok

    def print_summary(self):
        """Print summary of all checks"""
        print("\n" + "=" * 60)
        print("📊 HEALTH CHECK SUMMARY")
        print("=" * 60)

        total = len(self.results)
        ok_count = sum(1 for _, status, _ in self.results if status == HealthStatus.OK)
        warning_count = len(self.warnings)
        error_count = len(self.errors)

        print(f"\nTotal Checks: {total}")
        print(f"{HealthStatus.OK.value} Passed: {ok_count}")
        print(f"{HealthStatus.WARNING.value} Warnings: {warning_count}")
        print(f"{HealthStatus.ERROR.value} Errors: {error_count}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")

        print("\n" + "=" * 60)

        if error_count == 0:
            if warning_count == 0:
                print("✅ ALL CHECKS PASSED - System is healthy!")
                return 0
            else:
                print("⚠️  SYSTEM OK WITH WARNINGS - Review warnings above")
                return 0
        else:
            print("❌ SYSTEM HAS ERRORS - Fix errors above before deploying")
            return 1

    def run_all_checks(self, quick: bool = False):
        """Run all health checks"""
        print("🏥 Backend Health Check")
        print("=" * 60)

        # Always run these
        self.check_python_version()
        self.check_env_vars()

        if not quick:
            self.check_dependencies()
            self.check_database()
            self.check_redis()
            self.check_services()
            self.check_migrations()
        else:
            print("\n⚡ Quick mode - skipping detailed checks")

        return self.print_summary()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Backend Health Check Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/health_check.py              # Full health check
  python scripts/health_check.py --quick      # Quick check (env vars only)
  python scripts/health_check.py --verbose    # Verbose output
        """,
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick check (skip database, Redis, and service checks)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    health_check = HealthCheck(verbose=args.verbose)
    exit_code = health_check.run_all_checks(quick=args.quick)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
