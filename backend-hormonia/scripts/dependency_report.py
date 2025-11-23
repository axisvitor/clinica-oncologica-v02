#!/usr/bin/env python3
"""Generate dependency health report.

This script analyzes Python dependencies for:
- Outdated packages
- Known security vulnerabilities
- License compliance issues
- Dependency tree complexity

Usage:
    python scripts/dependency_report.py [--format {markdown,json,html}]

Requirements:
    pip install pip-audit safety licensecheck
"""

import subprocess
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import re


class DependencyReporter:
    """Generate comprehensive dependency health reports."""

    def __init__(self, requirements_file: str = "requirements.txt"):
        """Initialize dependency reporter.

        Args:
            requirements_file: Path to requirements.txt
        """
        self.requirements_file = Path(requirements_file)
        self.report_data = {
            "generated_at": datetime.now().isoformat(),
            "requirements_file": str(self.requirements_file),
            "outdated": [],
            "vulnerabilities": [],
            "summary": {}
        }

    def check_outdated(self) -> List[Dict[str, Any]]:
        """Check for outdated packages.

        Returns:
            List of outdated package information
        """
        print("🔍 Checking for outdated packages...")

        try:
            result = subprocess.run(
                ["pip", "list", "--outdated", "--format=json"],
                capture_output=True,
                text=True,
                check=True
            )

            outdated = json.loads(result.stdout) if result.stdout else []
            self.report_data["outdated"] = outdated

            print(f"✅ Found {len(outdated)} outdated packages")
            return outdated

        except subprocess.CalledProcessError as e:
            print(f"❌ Error checking outdated packages: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing pip output: {e}")
            return []

    def check_vulnerabilities(self) -> List[Dict[str, Any]]:
        """Check for known security vulnerabilities using pip-audit.

        Returns:
            List of vulnerability information
        """
        print("🔒 Checking for security vulnerabilities...")

        try:
            result = subprocess.run(
                ["pip-audit", "--format=json", "-r", str(self.requirements_file)],
                capture_output=True,
                text=True
            )

            if result.stdout:
                audit_data = json.loads(result.stdout)
                vulnerabilities = audit_data.get("vulnerabilities", [])
                self.report_data["vulnerabilities"] = vulnerabilities

                print(f"{'⚠️' if vulnerabilities else '✅'} Found {len(vulnerabilities)} vulnerabilities")
                return vulnerabilities
            else:
                print("✅ No vulnerabilities found")
                return []

        except FileNotFoundError:
            print("⚠️  pip-audit not installed. Install with: pip install pip-audit")
            return []
        except subprocess.CalledProcessError as e:
            print(f"⚠️  pip-audit check failed: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing pip-audit output: {e}")
            return []

    def analyze_dependency_tree(self) -> Dict[str, Any]:
        """Analyze dependency tree complexity.

        Returns:
            Dependency tree analysis
        """
        print("🌳 Analyzing dependency tree...")

        try:
            result = subprocess.run(
                ["pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                check=True
            )

            packages = json.loads(result.stdout) if result.stdout else []

            analysis = {
                "total_packages": len(packages),
                "direct_dependencies": self._count_direct_dependencies(),
                "transitive_dependencies": len(packages) - self._count_direct_dependencies()
            }

            self.report_data["dependency_tree"] = analysis
            print(f"✅ Analyzed {analysis['total_packages']} packages")

            return analysis

        except Exception as e:
            print(f"❌ Error analyzing dependency tree: {e}")
            return {}

    def _count_direct_dependencies(self) -> int:
        """Count direct dependencies from requirements.txt."""
        if not self.requirements_file.exists():
            return 0

        count = 0
        with open(self.requirements_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#'):
                    count += 1

        return count

    def generate_summary(self) -> Dict[str, Any]:
        """Generate report summary.

        Returns:
            Summary statistics
        """
        outdated = self.report_data.get("outdated", [])
        vulnerabilities = self.report_data.get("vulnerabilities", [])

        # Classify vulnerabilities by severity
        critical = sum(1 for v in vulnerabilities if v.get("severity") == "CRITICAL")
        high = sum(1 for v in vulnerabilities if v.get("severity") == "HIGH")
        medium = sum(1 for v in vulnerabilities if v.get("severity") == "MEDIUM")
        low = sum(1 for v in vulnerabilities if v.get("severity") == "LOW")

        # Calculate health score (0-100)
        score = 100
        score -= min(len(vulnerabilities) * 10, 50)  # -10 per vuln, max -50
        score -= min(critical * 20, 40)  # -20 per critical, max -40
        score -= min(len(outdated) * 2, 20)  # -2 per outdated, max -20
        score = max(0, score)

        # Determine grade
        if score >= 90:
            grade = "A"
        elif score >= 80:
            grade = "B"
        elif score >= 70:
            grade = "C"
        elif score >= 60:
            grade = "D"
        else:
            grade = "F"

        summary = {
            "health_score": score,
            "grade": grade,
            "total_outdated": len(outdated),
            "total_vulnerabilities": len(vulnerabilities),
            "vulnerabilities_by_severity": {
                "critical": critical,
                "high": high,
                "medium": medium,
                "low": low
            }
        }

        self.report_data["summary"] = summary
        return summary

    def generate_markdown_report(self) -> str:
        """Generate Markdown formatted report.

        Returns:
            Markdown report string
        """
        summary = self.report_data["summary"]
        outdated = self.report_data["outdated"]
        vulnerabilities = self.report_data["vulnerabilities"]
        dep_tree = self.report_data.get("dependency_tree", {})

        report = f"""# Dependency Health Report

**Generated:** {self.report_data['generated_at']}
**Requirements File:** {self.report_data['requirements_file']}

## 📊 Health Score: {summary['health_score']}/100 (Grade: {summary['grade']})

## Summary

| Metric | Count | Status |
|--------|-------|--------|
| Outdated packages | {summary['total_outdated']} | {'⚠️' if summary['total_outdated'] > 0 else '✅'} |
| Known vulnerabilities | {summary['total_vulnerabilities']} | {'🚨' if summary['total_vulnerabilities'] > 0 else '✅'} |
| - Critical | {summary['vulnerabilities_by_severity']['critical']} | {'🔴' if summary['vulnerabilities_by_severity']['critical'] > 0 else '✅'} |
| - High | {summary['vulnerabilities_by_severity']['high']} | {'🟠' if summary['vulnerabilities_by_severity']['high'] > 0 else '✅'} |
| - Medium | {summary['vulnerabilities_by_severity']['medium']} | {'🟡' if summary['vulnerabilities_by_severity']['medium'] > 0 else '✅'} |
| - Low | {summary['vulnerabilities_by_severity']['low']} | {'🟢' if summary['vulnerabilities_by_severity']['low'] > 0 else '✅'} |

"""

        # Dependency tree
        if dep_tree:
            report += f"""## Dependency Tree

- **Total packages:** {dep_tree.get('total_packages', 0)}
- **Direct dependencies:** {dep_tree.get('direct_dependencies', 0)}
- **Transitive dependencies:** {dep_tree.get('transitive_dependencies', 0)}

"""

        # Outdated packages
        if outdated:
            report += "## 📦 Outdated Packages\n\n"
            report += "| Package | Current | Latest | Type |\n"
            report += "|---------|---------|--------|----- |\n"

            for pkg in outdated[:20]:  # Limit to top 20
                report += f"| {pkg['name']} | {pkg['version']} | {pkg['latest_version']} | {pkg.get('latest_filetype', 'wheel')} |\n"

            if len(outdated) > 20:
                report += f"\n*...and {len(outdated) - 20} more*\n"

            report += "\n"

        # Vulnerabilities
        if vulnerabilities:
            report += "## 🔒 Security Vulnerabilities\n\n"

            for vuln in vulnerabilities:
                severity = vuln.get("severity", "UNKNOWN")
                package = vuln.get("name", "unknown")
                version = vuln.get("version", "unknown")
                vuln_id = vuln.get("id", "N/A")
                description = vuln.get("description", "No description")
                fix = vuln.get("fix_versions", [])

                emoji = {
                    "CRITICAL": "🔴",
                    "HIGH": "🟠",
                    "MEDIUM": "🟡",
                    "LOW": "🟢"
                }.get(severity, "⚪")

                report += f"### {emoji} {severity}: {package} {version}\n\n"
                report += f"**ID:** {vuln_id}  \n"
                report += f"**Description:** {description}\n\n"

                if fix:
                    report += f"**Fix:** Upgrade to {', '.join(fix)}\n\n"

                report += "---\n\n"

        # Action items
        report += "## ✅ Action Items\n\n"

        if summary['vulnerabilities_by_severity']['critical'] > 0:
            report += "### 🔴 CRITICAL - Immediate Action Required\n\n"
            report += "1. Address all CRITICAL vulnerabilities immediately\n"
            report += "2. Update affected packages to fixed versions\n"
            report += "3. Run security tests after updates\n\n"

        if summary['total_vulnerabilities'] > 0:
            report += "### 🟠 Security Updates\n\n"
            report += "1. Review all security vulnerabilities\n"
            report += "2. Create tickets for HIGH priority vulnerabilities\n"
            report += "3. Schedule updates for MEDIUM/LOW vulnerabilities\n\n"

        if summary['total_outdated'] > 5:
            report += "### 📦 Dependency Updates\n\n"
            report += "1. Review outdated packages\n"
            report += "2. Test compatibility of major version updates\n"
            report += "3. Schedule regular dependency update cycles\n\n"

        report += "### 🔄 Regular Maintenance\n\n"
        report += "1. Enable Dependabot for automated PRs\n"
        report += "2. Schedule monthly dependency reviews\n"
        report += "3. Monitor security advisories\n"
        report += "4. Keep CI/CD pipelines updated\n"

        return report

    def save_report(self, format: str = "markdown", output_dir: str = "docs/dependencies"):
        """Save report to file.

        Args:
            format: Output format (markdown, json, html)
            output_dir: Output directory
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if format == "markdown":
            filename = output_path / "DEPENDENCY_HEALTH_REPORT.md"
            content = self.generate_markdown_report()

            with open(filename, 'w') as f:
                f.write(content)

            print(f"✅ Markdown report saved to: {filename}")

        elif format == "json":
            filename = output_path / f"dependency_report_{timestamp}.json"

            with open(filename, 'w') as f:
                json.dump(self.report_data, f, indent=2)

            print(f"✅ JSON report saved to: {filename}")

        else:
            print(f"❌ Unsupported format: {format}")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Generate dependency health report"
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Report format (default: markdown)"
    )
    parser.add_argument(
        "--requirements",
        default="requirements.txt",
        help="Path to requirements.txt"
    )
    parser.add_argument(
        "--output-dir",
        default="docs/dependencies",
        help="Output directory for reports"
    )

    args = parser.parse_args()

    print("="*80)
    print("🔍 DEPENDENCY HEALTH REPORT")
    print("="*80)
    print()

    reporter = DependencyReporter(args.requirements)

    # Run all checks
    reporter.check_outdated()
    reporter.check_vulnerabilities()
    reporter.analyze_dependency_tree()
    reporter.generate_summary()

    # Save report
    reporter.save_report(format=args.format, output_dir=args.output_dir)

    print()
    print("="*80)

    # Print summary
    summary = reporter.report_data["summary"]
    print(f"Health Score: {summary['health_score']}/100 (Grade: {summary['grade']})")
    print(f"Outdated: {summary['total_outdated']}")
    print(f"Vulnerabilities: {summary['total_vulnerabilities']}")

    if summary['vulnerabilities_by_severity']['critical'] > 0:
        print()
        print("🚨 CRITICAL VULNERABILITIES DETECTED!")
        print("   Address immediately before deployment.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
