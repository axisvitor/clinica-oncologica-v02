#!/usr/bin/env python3
"""
Migration Dependency Chain Analyzer

This script analyzes Alembic migration files to detect:
1. Revision structure and dependencies
2. Broken dependency chains
3. Non-existent parent migrations
4. Duplicate revisions
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

class MigrationAnalyzer:
    def __init__(self, versions_path: str):
        self.versions_path = Path(versions_path)
        self.migrations: Dict[str, Dict] = {}
        self.revision_to_file: Dict[str, str] = {}

    def parse_migration_file(self, file_path: Path) -> Optional[Dict]:
        """Parse a migration file to extract revision information."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract revision
            revision_match = re.search(r"revision\s*=\s*['\"]([^'\"]+)['\"]", content)
            if not revision_match:
                return None

            revision = revision_match.group(1)

            # Extract down_revision
            down_revision_match = re.search(r"down_revision\s*=\s*(.+)", content)
            down_revision = None
            if down_revision_match:
                down_rev_text = down_revision_match.group(1).strip()
                if down_rev_text == 'None':
                    down_revision = None
                elif down_rev_text.startswith('('):
                    # Multiple parents (merge migration)
                    parents = re.findall(r"['\"]([^'\"]+)['\"]", down_rev_text)
                    down_revision = tuple(parents)
                else:
                    # Single parent
                    parent_match = re.search(r"['\"]([^'\"]+)['\"]", down_rev_text)
                    if parent_match:
                        down_revision = parent_match.group(1)

            # Extract branch_labels
            branch_labels_match = re.search(r"branch_labels\s*=\s*(.+)", content)
            branch_labels = None
            if branch_labels_match:
                branch_text = branch_labels_match.group(1).strip()
                if branch_text != 'None':
                    branch_labels = branch_text

            # Extract depends_on
            depends_on_match = re.search(r"depends_on\s*=\s*(.+)", content)
            depends_on = None
            if depends_on_match:
                depends_text = depends_on_match.group(1).strip()
                if depends_text != 'None':
                    depends_on = depends_text

            return {
                'revision': revision,
                'down_revision': down_revision,
                'branch_labels': branch_labels,
                'depends_on': depends_on,
                'file_path': str(file_path),
                'file_name': file_path.name
            }

        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return None

    def analyze_migrations(self):
        """Analyze all migration files in the versions directory."""
        print(f"Analyzing migrations in: {self.versions_path}")

        # Parse all migration files
        for file_path in self.versions_path.glob("*.py"):
            if file_path.name.startswith('__'):
                continue

            migration_info = self.parse_migration_file(file_path)
            if migration_info:
                revision = migration_info['revision']
                self.migrations[revision] = migration_info
                self.revision_to_file[revision] = file_path.name

        print(f"Found {len(self.migrations)} migrations")
        return self.analyze_dependency_chain()

    def analyze_dependency_chain(self) -> Dict:
        """Analyze the dependency chain for issues."""
        issues = {
            'missing_parents': [],
            'duplicate_revisions': [],
            'orphaned_migrations': [],
            'circular_dependencies': [],
            'merge_conflicts': []
        }

        all_revisions = set(self.migrations.keys())

        # Check for missing parent migrations
        for revision, info in self.migrations.items():
            down_rev = info['down_revision']
            if down_rev:
                if isinstance(down_rev, tuple):
                    # Merge migration with multiple parents
                    for parent in down_rev:
                        if parent not in all_revisions:
                            issues['missing_parents'].append({
                                'migration': revision,
                                'file': info['file_name'],
                                'missing_parent': parent
                            })
                else:
                    # Single parent
                    if down_rev not in all_revisions:
                        issues['missing_parents'].append({
                            'migration': revision,
                            'file': info['file_name'],
                            'missing_parent': down_rev
                        })

        # Check for duplicate revision IDs
        revision_counts = {}
        for revision in all_revisions:
            if revision in revision_counts:
                revision_counts[revision] += 1
            else:
                revision_counts[revision] = 1

        for revision, count in revision_counts.items():
            if count > 1:
                files = [info['file_name'] for rev, info in self.migrations.items() if rev == revision]
                issues['duplicate_revisions'].append({
                    'revision': revision,
                    'count': count,
                    'files': files
                })

        # Find orphaned migrations (no children)
        child_revisions = set()
        for revision, info in self.migrations.items():
            down_rev = info['down_revision']
            if down_rev:
                if isinstance(down_rev, tuple):
                    child_revisions.update(down_rev)
                else:
                    child_revisions.add(down_rev)

        for revision in all_revisions:
            if revision not in child_revisions and self.migrations[revision]['down_revision'] is not None:
                issues['orphaned_migrations'].append({
                    'revision': revision,
                    'file': self.migrations[revision]['file_name']
                })

        return issues

    def print_migration_tree(self):
        """Print the migration dependency tree."""
        print("\n=== Migration Dependency Tree ===")

        # Find root migrations (no parents)
        roots = []
        for revision, info in self.migrations.items():
            if info['down_revision'] is None:
                roots.append(revision)

        print(f"Root migrations: {roots}")

        # Find merge migrations
        merges = []
        for revision, info in self.migrations.items():
            if isinstance(info['down_revision'], tuple):
                merges.append({
                    'revision': revision,
                    'file': info['file_name'],
                    'parents': info['down_revision']
                })

        if merges:
            print(f"\nMerge migrations ({len(merges)}):")
            for merge in merges:
                print(f"  {merge['revision']} ({merge['file']})")
                print(f"    Merges: {', '.join(merge['parents'])}")

    def generate_report(self, issues: Dict):
        """Generate a comprehensive analysis report."""
        print("\n" + "="*60)
        print("MIGRATION DEPENDENCY CHAIN ANALYSIS REPORT")
        print("="*60)

        # Summary
        total_issues = sum(len(issue_list) for issue_list in issues.values())
        print(f"\nSUMMARY:")
        print(f"Total migrations analyzed: {len(self.migrations)}")
        print(f"Total issues found: {total_issues}")

        # Missing parents
        if issues['missing_parents']:
            print(f"\n🚨 CRITICAL: Missing Parent Migrations ({len(issues['missing_parents'])})")
            for issue in issues['missing_parents']:
                print(f"  Migration: {issue['migration']} ({issue['file']})")
                print(f"  Missing parent: {issue['missing_parent']}")
                print()

        # Duplicate revisions
        if issues['duplicate_revisions']:
            print(f"\n🚨 CRITICAL: Duplicate Revision IDs ({len(issues['duplicate_revisions'])})")
            for issue in issues['duplicate_revisions']:
                print(f"  Revision: {issue['revision']}")
                print(f"  Found in {issue['count']} files: {', '.join(issue['files'])}")
                print()

        # Orphaned migrations
        if issues['orphaned_migrations']:
            print(f"\n⚠️  WARNING: Orphaned Migrations ({len(issues['orphaned_migrations'])})")
            print("  These migrations have no children (may be the head):")
            for issue in issues['orphaned_migrations']:
                print(f"    {issue['revision']} ({issue['file']})")

        # Print migration tree
        self.print_migration_tree()

        return total_issues == 0

def main():
    versions_path = r"c:\Meu Projetos\clinica-oncologica-v02\backend-hormonia\alembic\versions"

    if not os.path.exists(versions_path):
        print(f"Error: Versions path not found: {versions_path}")
        sys.exit(1)

    analyzer = MigrationAnalyzer(versions_path)
    issues = analyzer.analyze_migrations()
    is_healthy = analyzer.generate_report(issues)

    if is_healthy:
        print("\n✅ Migration dependency chain is healthy!")
        sys.exit(0)
    else:
        print("\n❌ Migration dependency chain has issues that need attention!")
        sys.exit(1)

if __name__ == "__main__":
    main()