"""
Audit script to find all hardcoded TTL values in the codebase.

This script scans Python files for hardcoded TTL values and generates
a comprehensive report with recommendations for centralized configuration.

Usage:
    python scripts/audit_hardcoded_ttls.py
    python scripts/audit_hardcoded_ttls.py --output ttl_audit_report.json
"""

import ast
import re
import os
import json
import argparse
from typing import List, Dict, Any
from pathlib import Path


def find_hardcoded_ttls(directory: str) -> List[Dict[str, Any]]:
    """
    Find all hardcoded TTL values in Python files.

    Searches for patterns like:
    - ttl=3600
    - setex(key, 3600, value)
    - expire(key, 3600)
    - ex=3600
    - expires=3600

    Args:
        directory: Root directory to scan

    Returns:
        List of findings with file, line, TTL value, and context
    """
    ttl_patterns = [
        (r'ttl\s*=\s*(\d+)', 'ttl assignment'),
        (r'setex\([^,]+,\s*(\d+)', 'redis setex'),
        (r'expire\([^,]+,\s*(\d+)', 'redis expire'),
        (r'ex\s*=\s*(\d+)', 'ex parameter'),
        (r'expires\s*=\s*(\d+)', 'expires parameter'),
        (r'expiration\s*=\s*(\d+)', 'expiration assignment'),
        (r'timeout\s*=\s*(\d+)', 'timeout assignment'),
    ]

    results = []
    total_files = 0

    for root, dirs, files in os.walk(directory):
        # Skip virtual environments and cache directories
        dirs[:] = [d for d in dirs if d not in ['.venv', 'venv', '__pycache__', '.pytest_cache', 'node_modules']]

        for file in files:
            if file.endswith('.py'):
                total_files += 1
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    for pattern, pattern_type in ttl_patterns:
                        matches = re.finditer(pattern, content)
                        for match in matches:
                            ttl_value = int(match.group(1))

                            # Skip small values (likely not TTL, e.g., port numbers)
                            if ttl_value < 10:
                                continue

                            # Get line number and context
                            line_num = content[:match.start()].count('\n') + 1

                            # Get surrounding lines for context
                            lines = content.split('\n')
                            context_start = max(0, line_num - 3)
                            context_end = min(len(lines), line_num + 2)
                            context_lines = lines[context_start:context_end]

                            # Calculate human-readable duration
                            duration = _format_duration(ttl_value)

                            results.append({
                                'file': os.path.relpath(path, directory),
                                'line': line_num,
                                'ttl': ttl_value,
                                'duration': duration,
                                'pattern_type': pattern_type,
                                'context': match.group(0),
                                'code_snippet': '\n'.join(context_lines),
                                'suggested_config_key': _suggest_config_key(path, ttl_value)
                            })
                except Exception as e:
                    print(f"Error processing {path}: {e}")

    print(f"Scanned {total_files} Python files")
    return results


def _format_duration(seconds: int) -> str:
    """Convert seconds to human-readable duration."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m ({seconds}s)"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours}h ({seconds}s)"
    else:
        days = seconds // 86400
        return f"{days}d ({seconds}s)"


def _suggest_config_key(file_path: str, ttl_value: int) -> str:
    """
    Suggest a configuration key based on file path and TTL value.

    Examples:
        app/services/patient.py, 900 -> PATIENT_CACHE_TTL
        app/api/v2/auth.py, 3600 -> AUTH_TOKEN_TTL
    """
    file_lower = file_path.lower()

    # Common mappings
    if 'auth' in file_lower or 'session' in file_lower:
        if ttl_value >= 86400:
            return 'REFRESH_TOKEN_TTL'
        elif ttl_value >= 3600:
            return 'AUTH_TOKEN_TTL'
        else:
            return 'USER_SESSION_TTL'

    if 'patient' in file_lower:
        return 'PATIENT_CACHE_TTL'

    if 'quiz' in file_lower:
        if ttl_value >= 3600:
            return 'QUIZ_SESSION_TTL'
        else:
            return 'QUIZ_CACHE_TTL'

    if 'message' in file_lower or 'whatsapp' in file_lower:
        if ttl_value >= 3600:
            return 'MESSAGE_CACHE_TTL'
        else:
            return 'MESSAGE_STATS_TTL'

    if 'webhook' in file_lower:
        if 'idempotency' in file_lower or 'idem' in file_lower:
            return 'WEBHOOK_IDEMPOTENCY_TTL'
        else:
            return 'WEBHOOK_CACHE_TTL'

    if 'flow' in file_lower or 'template' in file_lower:
        return 'FLOW_TEMPLATE_TTL'

    if 'report' in file_lower or 'analytics' in file_lower:
        if 'analytics' in file_lower:
            return 'ANALYTICS_CACHE_TTL'
        else:
            return 'REPORT_CACHE_TTL'

    if 'saga' in file_lower:
        return 'SAGA_STATE_TTL'

    if 'lock' in file_lower:
        return 'DISTRIBUTED_LOCK_TTL'

    # Default based on duration
    if ttl_value >= 86400:
        return 'LONG_CACHE_TTL'
    elif ttl_value >= 3600:
        return 'MEDIUM_CACHE_TTL'
    else:
        return 'SHORT_CACHE_TTL'


def generate_report(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a comprehensive audit report.

    Args:
        findings: List of TTL findings

    Returns:
        Report dictionary with statistics and recommendations
    """
    # Group by file
    by_file = {}
    for finding in findings:
        file = finding['file']
        if file not in by_file:
            by_file[file] = []
        by_file[file].append(finding)

    # Group by suggested config key
    by_config_key = {}
    for finding in findings:
        key = finding['suggested_config_key']
        if key not in by_config_key:
            by_config_key[key] = []
        by_config_key[key].append(finding)

    # Calculate statistics
    total_findings = len(findings)
    unique_files = len(by_file)
    unique_ttl_values = len(set(f['ttl'] for f in findings))

    # Common TTL values
    ttl_counts = {}
    for finding in findings:
        ttl = finding['ttl']
        ttl_counts[ttl] = ttl_counts.get(ttl, 0) + 1

    most_common_ttls = sorted(
        ttl_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    return {
        'summary': {
            'total_findings': total_findings,
            'unique_files': unique_files,
            'unique_ttl_values': unique_ttl_values,
            'most_common_ttls': [
                {
                    'ttl': ttl,
                    'duration': _format_duration(ttl),
                    'count': count
                }
                for ttl, count in most_common_ttls
            ]
        },
        'by_file': {
            file: {
                'count': len(findings_list),
                'findings': findings_list
            }
            for file, findings_list in sorted(by_file.items())
        },
        'by_config_key': {
            key: {
                'count': len(findings_list),
                'suggested_ttl': max(f['ttl'] for f in findings_list),  # Use max for safety
                'findings': findings_list
            }
            for key, findings_list in sorted(by_config_key.items())
        },
        'recommendations': _generate_recommendations(by_config_key)
    }


def _generate_recommendations(by_config_key: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Generate configuration recommendations."""
    recommendations = []

    for config_key, findings_list in sorted(by_config_key.items()):
        ttl_values = [f['ttl'] for f in findings_list]
        max_ttl = max(ttl_values)
        min_ttl = min(ttl_values)

        recommendation = {
            'config_key': config_key,
            'suggested_value': max_ttl,  # Use max for safety
            'duration': _format_duration(max_ttl),
            'occurrences': len(findings_list),
            'files': list(set(f['file'] for f in findings_list)),
            'note': ''
        }

        # Add note if there are inconsistent values
        if max_ttl != min_ttl:
            recommendation['note'] = (
                f"Inconsistent values found: {min_ttl}-{max_ttl}s. "
                f"Using max value ({max_ttl}s) for safety."
            )

        recommendations.append(recommendation)

    return recommendations


def print_report(report: Dict[str, Any]) -> None:
    """Print a human-readable report to console."""
    print("\n" + "="*80)
    print("TTL AUDIT REPORT")
    print("="*80)

    # Summary
    summary = report['summary']
    print(f"\nSUMMARY:")
    print(f"  Total hardcoded TTLs found: {summary['total_findings']}")
    print(f"  Files affected: {summary['unique_files']}")
    print(f"  Unique TTL values: {summary['unique_ttl_values']}")

    print(f"\nMOST COMMON TTL VALUES:")
    for ttl_info in summary['most_common_ttls']:
        print(f"  {ttl_info['ttl']:>6}s ({ttl_info['duration']:>6}) - {ttl_info['count']} occurrences")

    # Recommendations
    print(f"\nCONFIGURATION RECOMMENDATIONS:")
    print(f"  Found {len(report['recommendations'])} distinct configuration keys")
    print(f"\n  Add to backend-hormonia/app/config/settings/cache.py:")
    print()

    for rec in report['recommendations']:
        print(f"    {rec['config_key']}: int = {rec['suggested_value']}  # {rec['duration']}")
        if rec['note']:
            print(f"    # NOTE: {rec['note']}")

    # Files with most findings
    print(f"\nFILES WITH MOST HARDCODED TTLs:")
    by_file = sorted(
        report['by_file'].items(),
        key=lambda x: x[1]['count'],
        reverse=True
    )[:10]

    for file, data in by_file:
        print(f"  {file}: {data['count']} findings")

    print("\n" + "="*80)
    print(f"Run with --output to save detailed JSON report")
    print("="*80 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Audit hardcoded TTL values in codebase'
    )
    parser.add_argument(
        '--directory',
        default='app',
        help='Directory to scan (default: app)'
    )
    parser.add_argument(
        '--output',
        help='Output JSON file path (optional)'
    )
    parser.add_argument(
        '--detailed',
        action='store_true',
        help='Show detailed findings in console'
    )

    args = parser.parse_args()

    print(f"Scanning directory: {args.directory}")
    findings = find_hardcoded_ttls(args.directory)

    if not findings:
        print("No hardcoded TTL values found!")
        return

    report = generate_report(findings)

    # Print console report
    print_report(report)

    # Print detailed findings if requested
    if args.detailed:
        print("\nDETAILED FINDINGS:")
        for file, data in sorted(report['by_file'].items()):
            print(f"\n{file}:")
            for finding in data['findings']:
                print(f"  Line {finding['line']}: {finding['ttl']}s ({finding['duration']}) - {finding['pattern_type']}")
                print(f"    Context: {finding['context']}")
                print(f"    Suggested key: {finding['suggested_config_key']}")

    # Save to JSON if output path provided
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        print(f"\nDetailed report saved to: {args.output}")


if __name__ == '__main__':
    main()
