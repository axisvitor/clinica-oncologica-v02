#!/usr/bin/env python3
"""
Script de Verificação de Correções - Sistema Hormonia

Verifica se todas as correções críticas e de qualidade foram aplicadas corretamente.

Uso:
    python scripts/verify_corrections.py
    python scripts/verify_corrections.py --verbose
    python scripts/verify_corrections.py --category critical
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
import importlib.util

# Cores para output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


class CorrectionVerifier:
    """Verificador de correções aplicadas."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.root_dir = Path(__file__).parent.parent
        self.results: Dict[str, List[Tuple[str, bool, str]]] = {
            "critical": [],
            "quality": [],
            "performance": [],
        }

    def log(self, message: str, level: str = "INFO"):
        """Log message with color."""
        if level == "ERROR":
            print(f"{RED}✗ {message}{RESET}")
        elif level == "SUCCESS":
            print(f"{GREEN}✓ {message}{RESET}")
        elif level == "WARNING":
            print(f"{YELLOW}⚠ {message}{RESET}")
        elif level == "INFO":
            if self.verbose:
                print(f"{BLUE}ℹ {message}{RESET}")

    def check_file_exists(self, file_path: str) -> bool:
        """Check if file exists."""
        full_path = self.root_dir / file_path
        exists = full_path.exists()
        if self.verbose:
            status = "EXISTS" if exists else "MISSING"
            self.log(f"File {file_path}: {status}")
        return exists

    def check_file_contains(self, file_path: str, content: str) -> bool:
        """Check if file contains specific content."""
        full_path = self.root_dir / file_path
        if not full_path.exists():
            return False

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                file_content = f.read()
                return content in file_content
        except Exception as e:
            if self.verbose:
                self.log(f"Error reading {file_path}: {e}", "ERROR")
            return False

    def check_import(self, module_path: str) -> bool:
        """Check if module can be imported."""
        try:
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

    # ======================================================================
    # FASE 1: CORREÇÕES CRÍTICAS
    # ======================================================================

    def verify_migrations(self) -> Tuple[bool, str]:
        """Verify Alembic migrations configuration."""
        checks = [
            self.check_file_exists("alembic/env.py"),
            self.check_file_exists("alembic.ini"),
            self.check_file_exists("scripts/create_initial_migration.py"),
            self.check_file_exists("scripts/create_initial_migration.sh"),
            self.check_file_exists("docs/MIGRATIONS.md"),
            self.check_file_contains(
                "alembic/env.py", "from app.models.patient import Patient"
            ),
            self.check_file_contains(
                "alembic/env.py", "from app.models.message import Message"
            ),
        ]

        passed = all(checks)
        message = (
            "Migrations Alembic configurado corretamente"
            if passed
            else "Migrations Alembic com problemas"
        )
        return passed, message

    def verify_database_pool(self) -> Tuple[bool, str]:
        """Verify database pool configuration."""
        checks = [
            self.check_file_exists("app/core/database_config.py"),
            self.check_file_contains(
                "app/core/database_config.py", "DatabasePoolConfig"
            ),
            self.check_file_contains("app/core/database_config.py", "get_pool_config"),
            self.check_file_contains("app/database.py", "database_config"),
        ]

        passed = all(checks)
        message = (
            "Pool de conexões configurado dinamicamente"
            if passed
            else "Pool de conexões com problemas"
        )
        return passed, message

    def verify_webhook_security(self) -> Tuple[bool, str]:
        """Verify webhook HMAC validation."""
        checks = [
            self.check_file_exists("app/api/v1/webhooks_secure.py"),
            self.check_file_exists("app/middleware/webhook_validator.py"),
            self.check_file_exists("docs/WEBHOOK_SECURITY.md"),
            self.check_file_contains(
                "app/api/v1/webhooks_secure.py", "X-Webhook-Signature"
            ),
            self.check_file_contains("app/api/v1/webhooks_secure.py", "hmac"),
            self.check_file_contains(
                "app/middleware/webhook_validator.py", "WebhookValidatorMiddleware"
            ),
        ]

        passed = all(checks)
        message = (
            "Validação HMAC de webhooks implementada"
            if passed
            else "Webhooks sem validação completa"
        )
        return passed, message

    def verify_rate_limiting(self) -> Tuple[bool, str]:
        """Verify distributed rate limiting."""
        checks = [
            self.check_file_exists("app/middleware/distributed_rate_limiter.py"),
            self.check_file_exists("app/core/rate_limit_config.py"),
            self.check_file_exists("app/core/redis_client.py"),
            self.check_file_contains(
                "app/middleware/distributed_rate_limiter.py", "DistributedRateLimiter"
            ),
            self.check_file_contains(
                "app/middleware/distributed_rate_limiter.py", "sliding window"
            ),
            self.check_file_contains(
                "app/core/middleware_setup.py", "RateLimitMiddleware"
            ),
        ]

        passed = all(checks)
        message = (
            "Rate limiting distribuído com Redis"
            if passed
            else "Rate limiting com problemas"
        )
        return passed, message

    def verify_idempotency(self) -> Tuple[bool, str]:
        """Verify message idempotency."""
        checks = [
            self.check_file_exists("app/services/idempotent_message_sender.py"),
            self.check_file_exists("docs/IDEMPOTENCY.md"),
            self.check_file_contains("app/models/message.py", "idempotency_key"),
            self.check_file_contains(
                "app/services/idempotent_message_sender.py", "IdempotentMessageSender"
            ),
            # Check for migration file
            any(
                "idempotency" in f.name.lower()
                for f in (self.root_dir / "alembic/versions").glob("*.py")
            )
            if (self.root_dir / "alembic/versions").exists()
            else False,
        ]

        passed = all(checks)
        message = (
            "Idempotência de mensagens implementada"
            if passed
            else "Idempotência com problemas"
        )
        return passed, message

    def verify_saga_pattern(self) -> Tuple[bool, str]:
        """Verify saga orchestrator."""
        checks = [
            self.check_file_exists("app/coordination/saga_orchestrator.py"),
            self.check_file_contains(
                "app/coordination/saga_orchestrator.py", "SagaOrchestrator"
            ),
            self.check_file_contains(
                "app/coordination/saga_orchestrator.py", "compensation"
            ),
        ]

        passed = all(checks)
        message = (
            "Saga Pattern implementado" if passed else "Saga Pattern com problemas"
        )
        return passed, message

    # ======================================================================
    # FASE 2: CORREÇÕES DE QUALIDADE
    # ======================================================================

    def verify_logger_frontend(self) -> Tuple[bool, str]:
        """Verify frontend logger implementation."""
        frontend_root = self.root_dir.parent / "frontend-hormonia"

        checks = [
            (frontend_root / "src/utils/logger.ts").exists(),
            (frontend_root / "eslint.config.js").exists(),
        ]

        if all(checks):
            # Check ESLint config
            eslint_path = frontend_root / "eslint.config.js"
            try:
                with open(eslint_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    has_no_console = "no-console" in content
                    checks.append(has_no_console)
            except Exception:
                checks.append(False)

        passed = all(checks)
        message = (
            "Logger frontend e ESLint configurados"
            if passed
            else "Logger frontend com problemas"
        )
        return passed, message

    def verify_repositories(self) -> Tuple[bool, str]:
        """Verify repository pattern implementation."""
        repo_dir = self.root_dir / "app/repositories"

        checks = [
            repo_dir.exists(),
            len(list(repo_dir.glob("*.py"))) > 0 if repo_dir.exists() else False,
        ]

        passed = all(checks)
        message = (
            "Repository pattern implementado"
            if passed
            else "Repositories com problemas"
        )
        return passed, message

    def verify_query_optimization(self) -> Tuple[bool, str]:
        """Verify query optimization documentation."""
        checks = [
            self.check_file_exists("docs/QUERY_OPTIMIZATION.md"),
        ]

        passed = all(checks)
        message = (
            "Documentação de otimização de queries"
            if passed
            else "Docs de queries ausente"
        )
        return passed, message

    # ======================================================================
    # FASE 3: CORREÇÕES DE PERFORMANCE
    # ======================================================================

    def verify_cache_service(self) -> Tuple[bool, str]:
        """Verify cache service implementation."""
        checks = [
            self.check_file_exists("app/services/cache_service.py"),
            self.check_file_exists("app/core/redis_manager.py"),
            self.check_file_exists("app/core/redis_client.py"),
            self.check_file_contains("app/services/cache_service.py", "CacheService"),
            self.check_file_contains("app/core/redis_client.py", "get_redis_client"),
        ]

        passed = all(checks)
        message = (
            "Cache service com Redis implementado"
            if passed
            else "Cache service com problemas"
        )
        return passed, message

    def verify_lazy_loading_guide(self) -> Tuple[bool, str]:
        """Verify lazy loading guide."""
        frontend_root = self.root_dir.parent / "frontend-hormonia"

        checks = [
            (frontend_root / "docs/LAZY_LOADING_GUIDE.md").exists(),
        ]

        passed = all(checks)
        message = (
            "Guia de lazy loading criado" if passed else "Guia de lazy loading ausente"
        )
        return passed, message

    # ======================================================================
    # RUNNER
    # ======================================================================

    def run_critical_checks(self):
        """Run all critical checks."""
        print(f"\n{BOLD}=== FASE 1: CORREÇÕES CRÍTICAS ==={RESET}\n")

        checks = [
            ("1. Migrations Alembic", self.verify_migrations),
            ("2. Pool de Conexões", self.verify_database_pool),
            ("3. Validação HMAC Webhooks", self.verify_webhook_security),
            ("4. Rate Limiting Distribuído", self.verify_rate_limiting),
            ("5. Idempotência de Mensagens", self.verify_idempotency),
            ("6. Saga Pattern", self.verify_saga_pattern),
        ]

        for name, check_func in checks:
            passed, message = check_func()
            self.results["critical"].append((name, passed, message))

            if passed:
                self.log(f"{name}: {message}", "SUCCESS")
            else:
                self.log(f"{name}: {message}", "ERROR")

    def run_quality_checks(self):
        """Run all quality checks."""
        print(f"\n{BOLD}=== FASE 2: CORREÇÕES DE QUALIDADE ==={RESET}\n")

        checks = [
            ("7. Logger Frontend", self.verify_logger_frontend),
            ("8. Repository Pattern", self.verify_repositories),
            ("9. Otimização de Queries", self.verify_query_optimization),
        ]

        for name, check_func in checks:
            passed, message = check_func()
            self.results["quality"].append((name, passed, message))

            if passed:
                self.log(f"{name}: {message}", "SUCCESS")
            else:
                self.log(f"{name}: {message}", "ERROR")

    def run_performance_checks(self):
        """Run all performance checks."""
        print(f"\n{BOLD}=== FASE 3: CORREÇÕES DE PERFORMANCE ==={RESET}\n")

        checks = [
            ("11. Cache Service", self.verify_cache_service),
            ("12. Lazy Loading Guide", self.verify_lazy_loading_guide),
        ]

        for name, check_func in checks:
            passed, message = check_func()
            self.results["performance"].append((name, passed, message))

            if passed:
                self.log(f"{name}: {message}", "SUCCESS")
            else:
                self.log(f"{name}: {message}", "WARNING")

    def print_summary(self):
        """Print verification summary."""
        print(f"\n{BOLD}{'=' * 60}{RESET}")
        print(f"{BOLD}RESUMO DA VERIFICAÇÃO{RESET}")
        print(f"{BOLD}{'=' * 60}{RESET}\n")

        for category, results in self.results.items():
            total = len(results)
            passed = sum(1 for _, p, _ in results if p)
            failed = total - passed

            percentage = (passed / total * 100) if total > 0 else 0

            status_color = (
                GREEN if percentage == 100 else YELLOW if percentage >= 80 else RED
            )
            status_icon = "✓" if percentage == 100 else "⚠" if percentage >= 80 else "✗"

            print(
                f"{BOLD}{category.upper()}{RESET}: {status_color}{status_icon} {passed}/{total} ({percentage:.0f}%){RESET}"
            )

        # Overall summary
        total_all = sum(len(r) for r in self.results.values())
        passed_all = sum(sum(1 for _, p, _ in r if p) for r in self.results.values())
        percentage_all = (passed_all / total_all * 100) if total_all > 0 else 0

        print(f"\n{BOLD}TOTAL{RESET}: {passed_all}/{total_all} ({percentage_all:.0f}%)")

        if percentage_all == 100:
            print(
                f"\n{GREEN}{BOLD}✓ TODAS AS CORREÇÕES VERIFICADAS COM SUCESSO!{RESET}"
            )
            return 0
        elif percentage_all >= 80:
            print(f"\n{YELLOW}{BOLD}⚠ MAIORIA DAS CORREÇÕES APLICADAS{RESET}")
            print(f"{YELLOW}Algumas correções podem precisar de atenção.{RESET}")
            return 0
        else:
            print(f"\n{RED}{BOLD}✗ ALGUMAS CORREÇÕES CRÍTICAS FALTANDO{RESET}")
            print(f"{RED}Por favor, revise as correções marcadas como falhadas.{RESET}")
            return 1

    def run_all(self, category: str = "all") -> int:
        """Run all verifications."""
        print(f"{BOLD}{'=' * 60}{RESET}")
        print(f"{BOLD}VERIFICAÇÃO DE CORREÇÕES - SISTEMA HORMONIA{RESET}")
        print(f"{BOLD}{'=' * 60}{RESET}")

        if category in ("all", "critical"):
            self.run_critical_checks()

        if category in ("all", "quality"):
            self.run_quality_checks()

        if category in ("all", "performance"):
            self.run_performance_checks()

        return self.print_summary()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verificar correções aplicadas no Sistema Hormonia"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Modo verbose com logs detalhados",
    )
    parser.add_argument(
        "--category",
        "-c",
        choices=["all", "critical", "quality", "performance"],
        default="all",
        help="Categoria de correções para verificar",
    )

    args = parser.parse_args()

    verifier = CorrectionVerifier(verbose=args.verbose)
    exit_code = verifier.run_all(category=args.category)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
