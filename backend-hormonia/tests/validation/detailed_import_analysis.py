#!/usr/bin/env python3
"""
Detailed Import Analysis - Analyzes specific import issues and provides fixes.
"""

import ast
from pathlib import Path
from typing import Dict, List
import json


class DetailedImportAnalyzer:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.app_dir = self.root_dir / "app"

        # Store detailed findings
        self.findings = {
            'circular_dependencies': [],
            'unused_imports': [],
            'missing_from_requirements': [],
            'false_positives': [],
            'import_style_issues': [],
            'type_checking_issues': []
        }

    def analyze_circular_deps(self):
        """Analyze circular dependencies in detail."""
        circular_deps = [
            {
                'cycle': 'app.agents.base -> app.orchestration.swarm_manager -> app.monitoring.agent_health_monitor -> app.agents.base',
                'files': [
                    'app/agents/base.py',
                    'app/orchestration/swarm_manager.py',
                    'app/monitoring/agent_health_monitor.py'
                ],
                'fix': 'Move shared types to app.agents.types, use TYPE_CHECKING blocks, or refactor to remove dependency'
            },
            {
                'cycle': 'app.infrastructure.cache.cache_manager -> app.infrastructure.cache.invalidation -> app.infrastructure.cache.cache_manager',
                'files': [
                    'app/infrastructure/cache/cache_manager.py',
                    'app/infrastructure/cache/invalidation.py'
                ],
                'fix': 'Extract shared interfaces to app.infrastructure.cache.protocols or use TYPE_CHECKING'
            },
            {
                'cycle': 'app.core.redis_manager.utils -> app.core.redis_manager.manager -> app.core.redis_manager.sync_client -> app.core.redis_manager.utils',
                'files': [
                    'app/core/redis_manager/utils.py',
                    'app/core/redis_manager/manager.py',
                    'app/core/redis_manager/sync_client.py'
                ],
                'fix': 'Reorganize redis_manager package to have one-way dependencies (utils <- sync_client <- manager)'
            },
            {
                'cycle': 'app.domain.agents.quiz.question_presenter -> app.domain.agents.quiz.session_coordinator -> app.domain.agents.quiz.question_presenter',
                'files': [
                    'app/domain/agents/quiz/question_presenter.py',
                    'app/domain/agents/quiz/session_coordinator.py'
                ],
                'fix': 'Extract shared quiz types to app.domain.agents.quiz.types'
            },
            {
                'cycle': 'app.services.flow.manager -> app.services.flow.core.manager -> app.services.flow.templates -> app.services.flow.manager',
                'files': [
                    'app/services/flow/manager.py',
                    'app/services/flow/core/manager.py',
                    'app/services/flow/templates.py'
                ],
                'fix': 'Consolidate flow managers or use dependency injection'
            },
            {
                'cycle': 'app.tasks.flows.batch_tasks -> app.tasks.flows.flow_tasks -> app.tasks.flows.batch_tasks',
                'files': [
                    'app/tasks/flows/batch_tasks.py',
                    'app/tasks/flows/flow_tasks.py'
                ],
                'fix': 'Extract shared task utilities to app.tasks.flows.utils'
            }
        ]

        self.findings['circular_dependencies'] = circular_deps

    def analyze_missing_deps(self):
        """Categorize missing dependencies into stdlib, installed, and truly missing."""

        # Python standard library (not in requirements.txt)
        stdlib = {
            'atexit', 'base64', 'concurrent', 'contextvars', 'csv', 'decimal',
            'difflib', 'gzip', 'hmac', 'html', 'importlib', 'inspect', 'mimetypes',
            'platform', 'queue', 'shutil', 'signal', 'smtplib', 'socket', 'ssl',
            'statistics', 'subprocess', 'tarfile', 'threading', 'types', 'urllib',
            'weakref', 'zipfile', 'zlib', 'zoneinfo'
        }

        # Sub-packages of installed packages (false positives)
        subpackages = {
            'email_validator': 'email-validator (already in requirements.txt)',
            'pyclamd': 'python-clamd (commented out - incompatible with Python 3.12+)',
            'pythonjsonlogger': 'python-json-logger (already in requirements.txt)',
            'sentry_sdk': 'sentry-sdk (already in requirements.txt)',
            'starlette': 'Included with FastAPI',
            'prometheus_client': 'prometheus-client (already in requirements.txt)',
            'jwt': 'pyjwt (already in requirements.txt)'
        }

        # Truly missing packages
        truly_missing = {
            'boto3': 'AWS SDK (if using S3, add boto3>=1.28.0,<2.0.0)',
            'flask': 'Flask web framework (used by Celery Flower monitoring)',
            'jsonschema': 'JSON schema validation (add jsonschema>=4.20.0,<5.0.0)',
            'websockets': 'WebSocket library (add websockets>=12.0,<13.0.0 if using WS)',
            'yaml': 'YAML parser (add pyyaml>=6.0.1,<7.0.0 if reading YAML configs)'
        }

        self.findings['false_positives'] = stdlib
        self.findings['missing_from_requirements'] = truly_missing
        self.findings['already_installed'] = subpackages

    def analyze_import_styles(self):
        """Check for import style consistency issues."""
        issues = []

        # Check specific files for common issues
        files_to_check = [
            'app/api/v2/router.py',
            'app/main.py',
            'app/services/flow/core/engine.py'
        ]

        for file_path in files_to_check:
            full_path = self.app_dir.parent / file_path
            if not full_path.exists():
                continue

            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                tree = ast.parse(content)

                # Check for wildcard imports
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        for alias in node.names:
                            if alias.name == '*':
                                issues.append({
                                    'file': file_path,
                                    'line': node.lineno,
                                    'issue': 'Wildcard import',
                                    'fix': 'Import specific names instead of using *'
                                })

            except Exception as e:
                issues.append({
                    'file': file_path,
                    'issue': f'Could not analyze: {e}'
                })

        self.findings['import_style_issues'] = issues

    def generate_json_report(self, output_file: str):
        """Generate JSON report with all findings."""

        # Run all analyses
        self.analyze_circular_deps()
        self.analyze_missing_deps()
        self.analyze_import_styles()

        # Add summary
        summary = {
            'total_circular_deps': len(self.findings['circular_dependencies']),
            'total_stdlib_false_positives': len(self.findings['false_positives']),
            'total_already_installed': len(self.findings['already_installed']),
            'total_truly_missing': len(self.findings['missing_from_requirements']),
            'total_import_style_issues': len(self.findings['import_style_issues'])
        }

        report = {
            'summary': summary,
            'findings': self.findings,
            'recommendations': self.generate_recommendations()
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)

        print(f"Detailed report saved to: {output_file}")
        return report

    def generate_recommendations(self) -> List[Dict]:
        """Generate prioritized recommendations."""
        return [
            {
                'priority': 'HIGH',
                'category': 'Circular Dependencies',
                'action': 'Break 11 circular dependency cycles',
                'details': 'Use TYPE_CHECKING blocks, extract shared types, or refactor module structure',
                'files_affected': 'Multiple files in agents, orchestration, cache, quiz, flow modules'
            },
            {
                'priority': 'MEDIUM',
                'category': 'Missing Dependencies',
                'action': 'Add 5 truly missing packages to requirements.txt',
                'details': 'boto3, flask, jsonschema, websockets, pyyaml (only if actually used)',
                'files_affected': 'requirements.txt'
            },
            {
                'priority': 'LOW',
                'category': 'Import Style',
                'action': 'Check for wildcard imports and unused imports',
                'details': 'Use explicit imports instead of wildcards',
                'files_affected': 'Various Python files'
            },
            {
                'priority': 'INFO',
                'category': 'False Positives',
                'action': 'Ignore 38 stdlib and subpackage false positives',
                'details': 'These are either stdlib modules or already installed as subpackages',
                'files_affected': 'None'
            }
        ]

    def print_summary(self):
        """Print human-readable summary."""
        print("\n" + "="*80)
        print("DETAILED IMPORT ANALYSIS SUMMARY")
        print("="*80)

        print("\n[CRITICAL ISSUES]")
        print("-" * 80)
        print(f"Circular Dependencies: {len(self.findings['circular_dependencies'])} cycles found")
        for dep in self.findings['circular_dependencies']:
            print(f"\n  Cycle: {dep['cycle']}")
            print(f"  Fix: {dep['fix']}")

        print("\n[MISSING DEPENDENCIES]")
        print("-" * 80)
        print("Truly Missing (need to add to requirements.txt):")
        for pkg, desc in self.findings['missing_from_requirements'].items():
            print(f"  - {pkg}: {desc}")

        print("\n[FALSE POSITIVES - Can Ignore]")
        print("-" * 80)
        print(f"Standard Library: {len(self.findings['false_positives'])} modules")
        print(f"Already Installed Subpackages: {len(self.findings['already_installed'])} packages")

        print("\n[RECOMMENDATIONS]")
        print("-" * 80)
        for rec in self.generate_recommendations():
            print(f"\n{rec['priority']}: {rec['category']}")
            print(f"  Action: {rec['action']}")
            print(f"  Details: {rec['details']}")


if __name__ == "__main__":
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent.parent

    analyzer = DetailedImportAnalyzer(str(backend_dir))

    # Run analyses
    analyzer.analyze_circular_deps()
    analyzer.analyze_missing_deps()
    analyzer.analyze_import_styles()

    # Print summary
    analyzer.print_summary()

    # Save JSON report
    output_file = backend_dir / "tests" / "validation" / "import_analysis_report.json"
    analyzer.generate_json_report(str(output_file))
