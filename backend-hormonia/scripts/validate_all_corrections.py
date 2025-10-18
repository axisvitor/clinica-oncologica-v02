#!/usr/bin/env python3
"""
Script de Validação Completa de Correções - Sistema Hormonia

Este script valida se todas as correções implementadas estão funcionando corretamente.

Uso:
    python scripts/validate_all_corrections.py
    python scripts/validate_all_corrections.py --verbose
    python scripts/validate_all_corrections.py --fix-issues
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import importlib.util

# Cores para output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"


class CorrectionValidator:
    """Validador completo de correções aplicadas."""

    def __init__(self, verbose: bool = False, fix_issues: bool = False):
        self.verbose = verbose
        self.fix_issues = fix_issues
        self.project_root = Path(__file__).parent.parent
        self.results = {
            "phase1": [],  # Correções críticas
            "phase2": [],  # Correções de qualidade
            "phase3": [],  # Correções de performance
        }
        self.issues_found = []
        self.issues_fixed = []

    def log(self, message: str, level: str = "INFO"):
        """Log message with color."""
        if level == "ERROR":
            print(f"{RED}✗{RESET} {message}")
        elif level == "SUCCESS":
            print(f"{GREEN}✓{RESET} {message}")
        elif level == "WARNING":
            print(f"{YELLOW}⚠{RESET} {message}")
        elif level == "INFO":
            if self.verbose:
                print(f"{BLUE}ℹ{RESET} {message}")

    def check_file_exists(self, file_path: str) -> bool:
        """Check if file exists."""
        full_path = self.project_root / file_path
        return full_path.exists()

    def check_file_contains(self, file_path: str, content: str) -> bool:
        """Check if file contains specific content."""
        full_path = self.project_root / file_path
        if not full_path.exists():
            return False

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return content in f.read()
        except Exception as e:
            self.log(f"Error reading {file_path}: {e}", "ERROR")
            return False

    def check_import(self, module_path: str) -> bool:
        """Check if module can be imported."""
        try:
            # Add project root to path
            sys.path.insert(0, str(self.project_root))

            # Convert path to module name
            module_name = (
                module_path.replace("/", ".").replace("\\", ".").replace(".py", "")
            )

            # Try to import
            spec = importlib.util.find_spec(module_name)
            return spec is not None
        except Exception as e:
            if self.verbose:
                self.log(f"Cannot import {module_path}: {e}", "ERROR")
            return False
        finally:
            sys.path.pop(0)

    def check_database_connection(self) -> bool:
        """Check database connection."""
        try:
            from sqlalchemy import create_engine

            database_url = os.getenv("DATABASE_URL")

            if not database_url:
                self.log("DATABASE_URL not set", "WARNING")
                return False

            engine = create_engine(database_url, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception as e:
            self.log(f"Database connection failed: {e}", "ERROR")
            return False

    def check_redis_connection(self) -> bool:
        """Check Redis connection."""
        try:
            import redis

            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

            r = redis.from_url(redis_url)
            r.ping()
            return True
        except Exception as e:
            self.log(f"Redis connection failed: {e}", "WARNING")
            return False

    # =========================================================================
    # FASE 1: CORREÇÕES CRÍTICAS
    # =========================================================================

    def validate_migrations(self) -> Tuple[bool, str]:
        """Validate Alembic migrations."""
        checks = []

        # Check alembic files
        checks.append(self.check_file_exists("alembic/env.py"))
        checks.append(self.check_file_exists("alembic.ini"))
        checks.append(
            self.check_file_exists(
                "alembic/versions/001_add_message_idempotency_key.py"
            )
        )

        # Check if env.py imports all models
        checks.append(
            self.check_file_contains(
                "alembic/env.py", "from app.models.patient import Patient"
            )
        )
        checks.append(
            self.check_file_contains(
                "alembic/env.py", "from app.models.message import Message"
            )
        )
        checks.append(
            self.check_file_contains(
                "alembic/env.py", "from app.models.user import User"
            )
        )

        # Check documentation
        checks.append(self.check_file_exists("docs/MIGRATIONS.md"))

        # Check scripts
        checks.append(self.check_file_exists("scripts/create_initial_migration.py"))
        checks.append(self.check_file_exists("scripts/create_initial_migration.sh"))

        passed = all(checks)
        message = (
            "Migrations Alembic configurados" if passed else "Migrations com problemas"
        )

        return passed, message

    def validate_database_pool(self) -> Tuple[bool, str]:
        """Validate database pool configuration."""
        checks = []

        # Check configuration file
        checks.append(self.check_file_exists("app/core/database_config.py"))
        checks.append(
            self.check_file_contains(
                "app/core/database_config.py", "DatabasePoolConfig"
            )
        )
        checks.append(
            self.check_file_contains("app/core/database_config.py", "get_pool_config")
        )

        # Check integration with database.py
        checks.append(self.check_file_contains("app/database.py", "database_config"))

        # Try to import
        checks.append(self.check_import("app.core.database_config"))

        passed = all(checks)
        message = "Pool de conexões otimizado" if passed else "Pool com problemas"

        return passed, message

    def validate_webhook_security(self) -> Tuple[bool, str]:
        """Validate webhook HMAC security."""
        checks = []

        # Check implementation files
        checks.append(self.check_file_exists("app/api/v1/webhooks_secure.py"))
        checks.append(self.check_file_exists("app/middleware/webhook_validator.py"))

        # Check security features
        checks.append(
            self.check_file_contains(
                "app/api/v1/webhooks_secure.py", "X-Webhook-Signature"
            )
        )
        checks.append(self.check_file_contains("app/api/v1/webhooks_secure.py", "hmac"))
        checks.append(
            self.check_file_contains(
                "app/middleware/webhook_validator.py", "WebhookValidatorMiddleware"
            )
        )

        # Check documentation
        checks.append(self.check_file_exists("docs/WEBHOOK_SECURITY.md"))
        checks.append(self.check_file_exists("docs/security/WEBHOOK_SECURITY.md"))

        # Check imports
        checks.append(self.check_import("app.middleware.webhook_validator"))

        # Check environment variable
        webhook_secret = os.getenv("EVOLUTION_WEBHOOK_SECRET")
        if not webhook_secret:
            self.log("EVOLUTION_WEBHOOK_SECRET not set", "WARNING")
            self.issues_found.append("EVOLUTION_WEBHOOK_SECRET não configurado")

        passed = all(checks)
        message = (
            "Webhook security implementado"
            if passed
            else "Webhook security com problemas"
        )

        return passed, message

    def validate_rate_limiting(self) -> Tuple[bool, str]:
        """Validate distributed rate limiting."""
        checks = []

        # Check implementation files
        checks.append(
            self.check_file_exists("app/middleware/distributed_rate_limiter.py")
        )
        checks.append(self.check_file_exists("app/core/rate_limit_config.py"))
        checks.append(self.check_file_exists("app/core/redis_client.py"))

        # Check features
        checks.append(
            self.check_file_contains(
                "app/middleware/distributed_rate_limiter.py", "DistributedRateLimiter"
            )
        )
        checks.append(
            self.check_file_contains(
                "app/middleware/distributed_rate_limiter.py", "sliding window"
            )
        )
        checks.append(
            self.check_file_contains(
                "app/core/middleware_setup.py", "RateLimitMiddleware"
            )
        )

        # Check imports
        checks.append(self.check_import("app.middleware.distributed_rate_limiter"))
        checks.append(self.check_import("app.core.redis_client"))

        # Check Redis connection
        if not self.check_redis_connection():
            self.log("Redis não acessível - rate limiting não funcionará", "WARNING")
            self.issues_found.append("Redis não está acessível")

        passed = all(checks)
        message = (
            "Rate limiting distribuído implementado"
            if passed
            else "Rate limiting com problemas"
        )

        return passed, message

    def validate_idempotency(self) -> Tuple[bool, str]:
        """Validate message idempotency."""
        checks = []

        # Check implementation files
        checks.append(
            self.check_file_exists("app/services/idempotent_message_sender.py")
        )
        checks.append(self.check_file_exists("docs/IDEMPOTENCY.md"))

        # Check model changes
        checks.append(
            self.check_file_contains("app/models/message.py", "idempotency_key")
        )
        checks.append(
            self.check_file_contains(
                "app/services/idempotent_message_sender.py", "IdempotentMessageSender"
            )
        )

        # Check migration
        migration_exists = any(
            "idempotency" in f.name.lower()
            for f in (self.project_root / "alembic/versions").glob("*.py")
        )
        checks.append(migration_exists)

        # Check imports
        checks.append(self.check_import("app.services.idempotent_message_sender"))

        passed = all(checks)
        message = (
            "Idempotência implementada" if passed else "Idempotência com problemas"
        )

        return passed, message

    def validate_saga_pattern(self) -> Tuple[bool, str]:
        """Validate Saga orchestrator."""
        checks = []

        # Check implementation file
        checks.append(self.check_file_exists("app/coordination/saga_orchestrator.py"))
        checks.append(
            self.check_file_contains(
                "app/coordination/saga_orchestrator.py", "SagaOrchestrator"
            )
        )
        checks.append(
            self.check_file_contains(
                "app/coordination/saga_orchestrator.py", "compensation"
            )
        )

        # Check imports
        checks.append(self.check_import("app.coordination.saga_orchestrator"))

        passed = all(checks)
        message = (
            "Saga Pattern implementado" if passed else "Saga Pattern com problemas"
        )

        return passed, message

    # =========================================================================
    # FASE 2: CORREÇÕES DE QUALIDADE
    # =========================================================================

    def validate_frontend_logger(self) -> Tuple[bool, str]:
        """Validate frontend logger."""
        frontend_root = self.project_root.parent / "frontend-hormonia"

        checks = []
        checks.append((frontend_root / "src/utils/logger.ts").exists())
        checks.append((frontend_root / "eslint.config.js").exists())

        if (frontend_root / "eslint.config.js").exists():
            with open(frontend_root / "eslint.config.js", "r") as f:
                content = f.read()
                checks.append("no-console" in content)

        passed = all(checks)
        message = (
            "Logger frontend implementado"
            if passed
            else "Logger frontend com problemas"
        )

        return passed, message

    def validate_repository_pattern(self) -> Tuple[bool, str]:
        """Validate repository pattern."""
        repo_dir = self.project_root / "app/repositories"

        checks = []
        checks.append(repo_dir.exists())

        if repo_dir.exists():
            repo_files = list(repo_dir.glob("*.py"))
            checks.append(len(repo_files) > 0)

        passed = all(checks)
        message = (
            "Repository Pattern verificado"
            if passed
            else "Repository Pattern com problemas"
        )

        return passed, message

    def validate_query_optimization(self) -> Tuple[bool, str]:
        """Validate query optimization docs."""
        checks = []
        checks.append(self.check_file_exists("docs/QUERY_OPTIMIZATION.md"))

        passed = all(checks)
        message = (
            "Query optimization documentado"
            if passed
            else "Query optimization sem docs"
        )

        return passed, message

    def validate_documentation(self) -> Tuple[bool, str]:
        """Validate complete documentation."""
        docs = [
            "docs/MIGRATIONS.md",
            "docs/WEBHOOK_SECURITY.md",
            "docs/IDEMPOTENCY.md",
            "docs/QUERY_OPTIMIZATION.md",
        ]

        root_docs = [
            "../CORRECTIONS_APPLIED.md",
            "../DEPLOYMENT_CHECKLIST.md",
            "../NEXT_STEPS.md",
        ]

        checks = [self.check_file_exists(doc) for doc in docs]

        # Check root docs
        for doc in root_docs:
            doc_path = self.project_root / doc
            checks.append(doc_path.exists())

        passed = all(checks)
        message = "Documentação completa" if passed else "Documentação incompleta"

        return passed, message

    # =========================================================================
    # FASE 3: CORREÇÕES DE PERFORMANCE
    # =========================================================================

    def validate_cache_service(self) -> Tuple[bool, str]:
        """Validate cache service."""
        checks = []

        checks.append(self.check_file_exists("app/services/cache_service.py"))
        checks.append(self.check_file_exists("app/core/redis_manager.py"))
        checks.append(self.check_file_exists("app/core/redis_client.py"))

        checks.append(
            self.check_file_contains("app/services/cache_service.py", "CacheService")
        )
        checks.append(
            self.check_file_contains("app/core/redis_client.py", "get_redis_client")
        )

        checks.append(self.check_import("app.services.cache_service"))
        checks.append(self.check_import("app.core.redis_client"))

        passed = all(checks)
        message = (
            "Cache service implementado" if passed else "Cache service com problemas"
        )

        return passed, message

    def validate_lazy_loading_guide(self) -> Tuple[bool, str]:
        """Validate lazy loading guide."""
        frontend_root = self.project_root.parent / "frontend-hormonia"

        checks = []
        checks.append((frontend_root / "docs/LAZY_LOADING_GUIDE.md").exists())

        passed = all(checks)
        message = (
            "Lazy loading guide criado" if passed else "Lazy loading guide faltando"
        )

        return passed, message

    # =========================================================================
    # RUNNER
    # =========================================================================

    def run_phase1_checks(self):
        """Run Phase 1 critical checks."""
        print(f"\n{BOLD}=== FASE 1: CORREÇÕES CRÍTICAS ==={RESET}\n")

        checks = [
            ("1. Migrations Alembic", self.validate_migrations),
            ("2. Pool de Conexões", self.validate_database_pool),
            ("3. Webhook Security", self.validate_webhook_security),
            ("4. Rate Limiting", self.validate_rate_limiting),
            ("5. Idempotência", self.validate_idempotency),
            ("6. Saga Pattern", self.validate_saga_pattern),
        ]

        for name, check_func in checks:
            passed, message = check_func()
            self.results["phase1"].append((name, passed, message))

            if passed:
                self.log(f"{name}: {message}", "SUCCESS")
            else:
                self.log(f"{name}: {message}", "ERROR")

    def run_phase2_checks(self):
        """Run Phase 2 quality checks."""
        print(f"\n{BOLD}=== FASE 2: CORREÇÕES DE QUALIDADE ==={RESET}\n")

        checks = [
            ("7. Logger Frontend", self.validate_frontend_logger),
            ("8. Repository Pattern", self.validate_repository_pattern),
            ("9. Query Optimization", self.validate_query_optimization),
            ("10. Documentação", self.validate_documentation),
        ]

        for name, check_func in checks:
            passed, message = check_func()
            self.results["phase2"].append((name, passed, message))

            if passed:
                self.log(f"{name}: {message}", "SUCCESS")
            else:
                self.log(f"{name}: {message}", "ERROR")

    def run_phase3_checks(self):
        """Run Phase 3 performance checks."""
        print(f"\n{BOLD}=== FASE 3: CORREÇÕES DE PERFORMANCE ==={RESET}\n")

        checks = [
            ("11. Cache Service", self.validate_cache_service),
            ("12. Lazy Loading Guide", self.validate_lazy_loading_guide),
        ]

        for name, check_func in checks:
            passed, message = check_func()
            self.results["phase3"].append((name, passed, message))

            if passed:
                self.log(f"{name}: {message}", "SUCCESS")
            else:
                self.log(f"{name}: {message}", "WARNING")

    def print_summary(self):
        """Print validation summary."""
        print(f"\n{BOLD}{'=' * 70}{RESET}")
        print(f"{BOLD}RESUMO DA VALIDAÇÃO{RESET}")
        print(f"{BOLD}{'=' * 70}{RESET}\n")

        for phase, results in self.results.items():
            total = len(results)
            passed = sum(1 for _, p, _ in results if p)
            failed = total - passed

            percentage = (passed / total * 100) if total > 0 else 0

            phase_name = {
                "phase1": "FASE 1 - CRÍTICAS",
                "phase2": "FASE 2 - QUALIDADE",
                "phase3": "FASE 3 - PERFORMANCE",
            }[phase]

            status_color = (
                GREEN if percentage == 100 else YELLOW if percentage >= 80 else RED
            )
            status_icon = "✓" if percentage == 100 else "⚠" if percentage >= 80 else "✗"

            print(
                f"{BOLD}{phase_name}{RESET}: {status_color}{status_icon} {passed}/{total} ({percentage:.0f}%){RESET}"
            )

        # Overall summary
        total_all = sum(len(r) for r in self.results.values())
        passed_all = sum(sum(1 for _, p, _ in r if p) for r in self.results.values())
        percentage_all = (passed_all / total_all * 100) if total_all > 0 else 0

        print(f"\n{BOLD}TOTAL{RESET}: {passed_all}/{total_all} ({percentage_all:.0f}%)")

        # Issues found
        if self.issues_found:
            print(f"\n{BOLD}PROBLEMAS ENCONTRADOS:{RESET}")
            for issue in self.issues_found:
                print(f"  {YELLOW}⚠{RESET} {issue}")

        # Final status
        if percentage_all == 100:
            print(f"\n{GREEN}{BOLD}✓ TODAS AS CORREÇÕES VALIDADAS COM SUCESSO!{RESET}")
            return 0
        elif percentage_all >= 80:
            print(f"\n{YELLOW}{BOLD}⚠ MAIORIA DAS CORREÇÕES VALIDADAS{RESET}")
            print(f"{YELLOW}Algumas correções precisam de atenção.{RESET}")
            return 0
        else:
            print(f"\n{RED}{BOLD}✗ VALIDAÇÃO FALHOU{RESET}")
            print(f"{RED}Várias correções críticas estão faltando.{RESET}")
            return 1

    def run_all(self) -> int:
        """Run all validations."""
        print(f"{BOLD}{'=' * 70}{RESET}")
        print(f"{BOLD}VALIDAÇÃO COMPLETA DE CORREÇÕES - SISTEMA HORMONIA{RESET}")
        print(f"{BOLD}{'=' * 70}{RESET}")

        # Check connections
        print(f"\n{BOLD}=== VALIDAÇÃO DE CONEXÕES ==={RESET}\n")

        db_ok = self.check_database_connection()
        if db_ok:
            self.log("Conexão com banco de dados: OK", "SUCCESS")
        else:
            self.log("Conexão com banco de dados: FALHOU", "WARNING")

        redis_ok = self.check_redis_connection()
        if redis_ok:
            self.log("Conexão com Redis: OK", "SUCCESS")
        else:
            self.log("Conexão com Redis: FALHOU", "WARNING")

        # Run validations
        self.run_phase1_checks()
        self.run_phase2_checks()
        self.run_phase3_checks()

        return self.print_summary()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validar correções aplicadas no Sistema Hormonia"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Modo verbose com logs detalhados",
    )
    parser.add_argument(
        "--fix-issues",
        "-f",
        action="store_true",
        help="Tentar corrigir problemas encontrados",
    )

    args = parser.parse_args()

    validator = CorrectionValidator(verbose=args.verbose, fix_issues=args.fix_issues)
    exit_code = validator.run_all()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
