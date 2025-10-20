#!/usr/bin/env python3
"""
QW-016: Comprehensive Services Analysis Script
===============================================

Analyzes all services in backend-hormonia/app/services/ to:
- Map dependencies and imports
- Identify duplications
- Calculate metrics (LOC, complexity)
- Find orphaned services
- Generate consolidation recommendations

Usage:
    python scripts/analyze_services_complete.py
    python scripts/analyze_services_complete.py --output REVIEW-2025/services-analysis.md
"""

import ast
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple

# ============================================================================
# DATA MODELS
# ============================================================================


@dataclass
class ServiceInfo:
    """Information about a service file."""

    path: Path
    name: str
    lines_of_code: int
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    internal_imports: List[str] = field(default_factory=list)
    external_imports: List[str] = field(default_factory=list)
    dependencies: Set[str] = field(default_factory=set)
    is_used_by: Set[str] = field(default_factory=set)
    complexity_score: int = 0
    has_docstring: bool = False
    has_tests: bool = False


@dataclass
class DuplicationGroup:
    """Group of services with similar names/purposes."""

    base_name: str
    services: List[str]
    recommendation: str


# ============================================================================
# AST ANALYZER
# ============================================================================


class ServiceAnalyzer(ast.NodeVisitor):
    """Analyzes a Python service file using AST."""

    def __init__(self):
        self.classes = []
        self.functions = []
        self.imports = []
        self.internal_imports = []
        self.external_imports = []
        self.has_docstring = False
        self.complexity = 0

    def visit_ClassDef(self, node: ast.ClassDef):
        """Extract class definitions."""
        self.classes.append(node.name)
        if ast.get_docstring(node):
            self.has_docstring = True
        self.complexity += 1
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Extract function definitions."""
        self.functions.append(node.name)
        if ast.get_docstring(node):
            self.has_docstring = True
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Extract async function definitions."""
        self.functions.append(f"async {node.name}")
        if ast.get_docstring(node):
            self.has_docstring = True
        self.complexity += 1
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        """Extract import statements."""
        for alias in node.names:
            self.imports.append(alias.name)
            if alias.name.startswith("app."):
                self.internal_imports.append(alias.name)
            else:
                self.external_imports.append(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Extract from...import statements."""
        if node.module:
            self.imports.append(node.module)
            if node.module.startswith("app."):
                self.internal_imports.append(node.module)
            else:
                self.external_imports.append(node.module)

    def visit_If(self, node: ast.If):
        """Count complexity from if statements."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For):
        """Count complexity from for loops."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While):
        """Count complexity from while loops."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try):
        """Count complexity from try/except blocks."""
        self.complexity += len(node.handlers)
        self.generic_visit(node)


# ============================================================================
# FILE SCANNER
# ============================================================================


def analyze_file(file_path: Path) -> ServiceInfo:
    """Analyze a single Python service file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Count lines of code (non-empty, non-comment)
        lines = content.split("\n")
        loc = sum(
            1 for line in lines if line.strip() and not line.strip().startswith("#")
        )

        # Parse AST
        tree = ast.parse(content)
        analyzer = ServiceAnalyzer()
        analyzer.visit(tree)

        # Extract module docstring
        has_docstring = ast.get_docstring(tree) is not None

        # Create ServiceInfo
        service_name = file_path.stem

        return ServiceInfo(
            path=file_path,
            name=service_name,
            lines_of_code=loc,
            classes=analyzer.classes,
            functions=analyzer.functions,
            imports=analyzer.imports,
            internal_imports=analyzer.internal_imports,
            external_imports=analyzer.external_imports,
            complexity_score=analyzer.complexity,
            has_docstring=has_docstring or analyzer.has_docstring,
        )

    except Exception as e:
        print(f"⚠️  Error analyzing {file_path}: {e}")
        return ServiceInfo(path=file_path, name=file_path.stem, lines_of_code=0)


def scan_services_directory(services_dir: Path) -> List[ServiceInfo]:
    """Scan all Python files in services directory."""
    services = []

    for py_file in services_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue

        service = analyze_file(py_file)
        services.append(service)

    return services


# ============================================================================
# DEPENDENCY MAPPER
# ============================================================================


def map_dependencies(services: List[ServiceInfo]) -> None:
    """Map dependencies between services."""
    service_map = {s.name: s for s in services}

    for service in services:
        for import_path in service.internal_imports:
            # Extract service name from import path
            # e.g., "app.services.patient" -> "patient"
            if ".services." in import_path:
                parts = import_path.split(".services.")
                if len(parts) > 1:
                    dep_name = parts[1].split(".")[0]
                    if dep_name in service_map:
                        service.dependencies.add(dep_name)
                        service_map[dep_name].is_used_by.add(service.name)


# ============================================================================
# DUPLICATION DETECTOR
# ============================================================================


def find_duplications(services: List[ServiceInfo]) -> List[DuplicationGroup]:
    """Find services with similar names (potential duplications)."""
    groups = defaultdict(list)

    # Group by base name patterns
    patterns = [
        (r"^ai_?(.*)$", "ai"),
        (r"^cache_?(.*)$", "cache"),
        (r"^flow_?(.*)$", "flow"),
        (r"^message_?(.*)$", "message"),
        (r"^quiz_?(.*)$", "quiz"),
        (r"^websocket_?(.*)$", "websocket"),
        (r"^monitoring_?(.*)$", "monitoring"),
        (r"^analytics_?(.*)$", "analytics"),
        (r"^audit_?(.*)$", "audit"),
        (r"^alert_?(.*)$", "alert"),
        (r"^patient_?(.*)$", "patient"),
        (r"^treatment_?(.*)$", "treatment"),
        (r"^appointment_?(.*)$", "appointment"),
        (r"^notification_?(.*)$", "notification"),
        (r"^report_?(.*)$", "report"),
        (r"^ab_testing_?(.*)$", "ab_testing"),
    ]

    for service in services:
        name = service.name
        matched = False

        for pattern, base_name in patterns:
            if re.match(pattern, name):
                groups[base_name].append(name)
                matched = True
                break

        if not matched:
            groups[name].append(name)

    # Create duplication groups (only where count > 1)
    duplications = []
    recommendations = {
        "ai": "Consolidate into single ai_service.py with internal cache",
        "cache": "Create unified cache_service.py with pluggable strategies",
        "flow": "Create flow/ module with flow_service.py, flow_engine.py, flow_analytics.py",
        "message": "Create messaging/ module with message_service.py and message_scheduler.py",
        "quiz": "Create quiz/ module with quiz_service.py, quiz_analytics.py, quiz_templates.py",
        "websocket": "Consolidate into single websocket_service.py",
        "monitoring": "Create monitoring/ module with monitoring_service.py and health_check.py",
        "analytics": "Consolidate analytics logic into analytics_service.py",
        "audit": "Create single audit_service.py with audit_log and audit_trail functionality",
        "alert": "Consolidate into alert_service.py with processor and escalation",
        "patient": "Review if patient_service.py needs separation or can be consolidated",
        "treatment": "Consolidate treatment-related services",
        "appointment": "Consolidate appointment-related services",
        "notification": "Create notification/ module",
        "report": "Consolidate report generation services",
        "ab_testing": "Create ab_testing/ module with clear separation of concerns",
    }

    for base_name, service_names in groups.items():
        if len(service_names) > 1:
            duplications.append(
                DuplicationGroup(
                    base_name=base_name,
                    services=sorted(service_names),
                    recommendation=recommendations.get(
                        base_name, f"Review and consolidate {base_name} services"
                    ),
                )
            )

    return sorted(duplications, key=lambda x: len(x.services), reverse=True)


# ============================================================================
# ORPHAN DETECTOR
# ============================================================================


def find_orphans(services: List[ServiceInfo]) -> List[ServiceInfo]:
    """Find services that are never imported/used."""
    return [s for s in services if len(s.is_used_by) == 0]


# ============================================================================
# REPORT GENERATOR
# ============================================================================


def generate_markdown_report(
    services: List[ServiceInfo],
    duplications: List[DuplicationGroup],
    orphans: List[ServiceInfo],
) -> str:
    """Generate comprehensive Markdown report."""

    # Calculate metrics
    total_services = len(services)
    total_loc = sum(s.lines_of_code for s in services)
    avg_loc = total_loc // total_services if total_services > 0 else 0
    total_complexity = sum(s.complexity_score for s in services)
    services_with_docs = sum(1 for s in services if s.has_docstring)
    doc_coverage = (
        (services_with_docs / total_services * 100) if total_services > 0 else 0
    )

    report = []
    report.append("# 🔍 COMPREHENSIVE SERVICES ANALYSIS")
    report.append("## Backend Hormonia - Services Deep Dive")
    report.append("")
    report.append("---")
    report.append("")
    report.append("## 📊 EXECUTIVE SUMMARY")
    report.append("")
    report.append(f"**Total Services:** {total_services}")
    report.append(f"**Total Lines of Code:** {total_loc:,}")
    report.append(f"**Average LOC per Service:** {avg_loc}")
    report.append(f"**Total Complexity Score:** {total_complexity}")
    report.append(
        f"**Documentation Coverage:** {doc_coverage:.1f}% ({services_with_docs}/{total_services})"
    )
    report.append(f"**Duplication Groups Found:** {len(duplications)}")
    report.append(f"**Orphaned Services:** {len(orphans)}")
    report.append("")
    report.append("---")
    report.append("")

    # Top services by LOC
    report.append("## 📈 TOP 20 SERVICES BY SIZE")
    report.append("")
    report.append("| Rank | Service | LOC | Classes | Functions | Complexity |")
    report.append("|------|---------|-----|---------|-----------|------------|")

    top_services = sorted(services, key=lambda s: s.lines_of_code, reverse=True)[:20]
    for i, service in enumerate(top_services, 1):
        report.append(
            f"| {i} | `{service.name}` | {service.lines_of_code} | "
            f"{len(service.classes)} | {len(service.functions)} | {service.complexity_score} |"
        )

    report.append("")
    report.append("---")
    report.append("")

    # Duplication groups
    report.append("## 🔄 DUPLICATION GROUPS (CONSOLIDATION OPPORTUNITIES)")
    report.append("")

    for group in duplications:
        report.append(
            f"### {group.base_name.upper()} Services ({len(group.services)} files)"
        )
        report.append("")
        report.append("**Files:**")
        for service_name in group.services:
            service = next((s for s in services if s.name == service_name), None)
            if service:
                report.append(
                    f"- `{service_name}.py` ({service.lines_of_code} LOC, "
                    f"{service.complexity_score} complexity)"
                )
        report.append("")
        report.append(f"**💡 Recommendation:** {group.recommendation}")
        report.append("")

    report.append("---")
    report.append("")

    # Orphaned services
    report.append("## 🏝️ ORPHANED SERVICES (NEVER IMPORTED)")
    report.append("")
    report.append(
        "These services are never imported by other services. Consider removing or documenting if they're entry points."
    )
    report.append("")

    if orphans:
        report.append("| Service | LOC | Complexity | Has Docs |")
        report.append("|---------|-----|------------|----------|")
        for service in sorted(orphans, key=lambda s: s.lines_of_code, reverse=True):
            docs_icon = "✅" if service.has_docstring else "❌"
            report.append(
                f"| `{service.name}` | {service.lines_of_code} | "
                f"{service.complexity_score} | {docs_icon} |"
            )
    else:
        report.append("✅ No orphaned services found!")

    report.append("")
    report.append("---")
    report.append("")

    # Most complex services
    report.append("## 🧩 MOST COMPLEX SERVICES")
    report.append("")
    report.append(
        "Services with highest complexity scores (candidates for refactoring):"
    )
    report.append("")
    report.append("| Rank | Service | Complexity | LOC | Classes | Functions |")
    report.append("|------|---------|------------|-----|---------|-----------|")

    complex_services = sorted(services, key=lambda s: s.complexity_score, reverse=True)[
        :15
    ]
    for i, service in enumerate(complex_services, 1):
        report.append(
            f"| {i} | `{service.name}` | {service.complexity_score} | "
            f"{service.lines_of_code} | {len(service.classes)} | {len(service.functions)} |"
        )

    report.append("")
    report.append("---")
    report.append("")

    # Services without documentation
    report.append("## 📝 SERVICES LACKING DOCUMENTATION")
    report.append("")
    undocumented = [s for s in services if not s.has_docstring]
    report.append(f"**Total:** {len(undocumented)} services without docstrings")
    report.append("")

    if undocumented:
        report.append("| Service | LOC | Complexity |")
        report.append("|---------|-----|------------|")
        for service in sorted(
            undocumented, key=lambda s: s.lines_of_code, reverse=True
        )[:30]:
            report.append(
                f"| `{service.name}` | {service.lines_of_code} | {service.complexity_score} |"
            )

    report.append("")
    report.append("---")
    report.append("")

    # Dependency analysis
    report.append("## 🔗 DEPENDENCY ANALYSIS")
    report.append("")
    report.append("### Most Depended Upon Services")
    report.append("")
    report.append("Services that are imported/used by many other services:")
    report.append("")

    most_used = sorted(services, key=lambda s: len(s.is_used_by), reverse=True)[:15]
    if most_used:
        report.append("| Service | Used By (count) | LOC |")
        report.append("|---------|-----------------|-----|")
        for service in most_used:
            report.append(
                f"| `{service.name}` | {len(service.is_used_by)} | {service.lines_of_code} |"
            )

    report.append("")
    report.append("### Services with Most Dependencies")
    report.append("")
    report.append("Services that depend on many other services:")
    report.append("")

    most_deps = sorted(services, key=lambda s: len(s.dependencies), reverse=True)[:15]
    if most_deps:
        report.append("| Service | Dependencies (count) | LOC |")
        report.append("|---------|---------------------|-----|")
        for service in most_deps:
            report.append(
                f"| `{service.name}` | {len(service.dependencies)} | {service.lines_of_code} |"
            )

    report.append("")
    report.append("---")
    report.append("")

    # Recommendations
    report.append("## 🎯 CONSOLIDATION ROADMAP")
    report.append("")
    report.append("### Phase 1: Low-Risk Consolidations (Week 5)")
    report.append("")
    report.append("1. **AI Services (6 → 1)**")
    report.append(
        "   - Consolidate: ai.py, ai_cache.py, ai_cache_service.py, ai_redis_cache.py, ai_batch_processor.py"
    )
    report.append(
        "   - Target: `ai_service.py` with internal cache and batch processing"
    )
    report.append("")
    report.append("2. **Cache Services (6 → 1)**")
    report.append(
        "   - Consolidate: cache.py, cache_service.py, cache_invalidation.py, unified_cache.py, template_cache.py, analytics_cache.py"
    )
    report.append("   - Target: `cache_service.py` with pluggable strategies")
    report.append("")
    report.append("3. **Alert Services (3 → 1)**")
    report.append(
        "   - Consolidate: alert.py, alert_processor.py, critical_error_escalation.py"
    )
    report.append("   - Target: `alert_service.py` with processor and escalation")
    report.append("")
    report.append("### Phase 2: Medium-Risk Consolidations (Week 6)")
    report.append("")
    report.append("4. **Flow Services (15 → 4)**")
    report.append("   - Create module: `app/services/flow/`")
    report.append(
        "   - Files: flow_service.py, flow_engine.py, flow_analytics.py, flow_templates.py"
    )
    report.append("")
    report.append("5. **Message Services (8 → 2)**")
    report.append("   - Create module: `app/services/messaging/`")
    report.append("   - Files: message_service.py, message_scheduler.py")
    report.append("")
    report.append("6. **Quiz Services (12 → 3)**")
    report.append("   - Create module: `app/services/quiz/`")
    report.append("   - Files: quiz_service.py, quiz_analytics.py, quiz_templates.py")
    report.append("")
    report.append("### Phase 3: High-Risk Consolidations (Week 7-8)")
    report.append("")
    report.append("7. **Audit Services (3 → 1)**")
    report.append("8. **Monitoring Services (8 → 2)**")
    report.append("9. **Analytics Services (5 → 2)**")
    report.append("10. **WebSocket Services (5 → 1)**")
    report.append("")
    report.append("### Expected Results")
    report.append("")
    report.append(f"- **Before:** {total_services} services")
    report.append("- **After:** ~35-40 services")
    report.append(
        f"- **Reduction:** ~{total_services - 35} services ({(total_services - 35) / total_services * 100:.0f}%)"
    )
    report.append("- **Maintainability:** Significantly improved")
    report.append("- **Code Duplication:** Eliminated")
    report.append("")
    report.append("---")
    report.append("")
    report.append("## ✅ NEXT ACTIONS")
    report.append("")
    report.append("1. **Review this analysis** with tech lead")
    report.append("2. **Prioritize consolidation groups** based on risk/impact")
    report.append("3. **Create baseline tests** before starting consolidation")
    report.append("4. **Create feature branch** for consolidation work")
    report.append("5. **Start with Phase 1** (low-risk consolidations)")
    report.append("")
    report.append("---")
    report.append("")
    report.append("**Generated by:** `scripts/analyze_services_complete.py` (QW-016)")
    report.append(
        f"**Date:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    return "\n".join(report)


# ============================================================================
# MAIN
# ============================================================================


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze backend services comprehensively"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="REVIEW-2025/QW-016-SERVICES-ANALYSIS.md",
        help="Output markdown file path",
    )
    parser.add_argument(
        "--services-dir",
        "-s",
        default="backend-hormonia/app/services",
        help="Services directory path",
    )

    args = parser.parse_args()

    # Resolve paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    services_dir = project_root / args.services_dir
    output_path = project_root / args.output

    print("🔍 Comprehensive Services Analysis")
    print("=" * 60)
    print(f"Services directory: {services_dir}")
    print(f"Output file: {output_path}")
    print()

    # Scan services
    print("📂 Scanning services directory...")
    services = scan_services_directory(services_dir)
    print(f"✅ Found {len(services)} services")
    print()

    # Map dependencies
    print("🔗 Mapping dependencies...")
    map_dependencies(services)
    print("✅ Dependencies mapped")
    print()

    # Find duplications
    print("🔄 Finding duplication groups...")
    duplications = find_duplications(services)
    print(f"✅ Found {len(duplications)} duplication groups")
    print()

    # Find orphans
    print("🏝️  Finding orphaned services...")
    orphans = find_orphans(services)
    print(f"✅ Found {len(orphans)} orphaned services")
    print()

    # Generate report
    print("📝 Generating Markdown report...")
    report = generate_markdown_report(services, duplications, orphans)

    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ Report generated: {output_path}")
    print()

    # Summary
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"Total Services: {len(services)}")
    print(f"Total LOC: {sum(s.lines_of_code for s in services):,}")
    print(f"Duplication Groups: {len(duplications)}")
    print(f"Orphaned Services: {len(orphans)}")
    print(
        f"Documentation Coverage: {sum(1 for s in services if s.has_docstring) / len(services) * 100:.1f}%"
    )
    print()
    print("🎯 Next: Review the report and plan consolidation strategy")


if __name__ == "__main__":
    main()
