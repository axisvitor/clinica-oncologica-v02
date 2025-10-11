#!/usr/bin/env python3
"""
RLS Policy Verification Script

This script verifies that all critical tables have proper RLS policies
before and after the migration is applied.

Usage:
    python verify_rls_policies.py [--check-before | --check-after]
"""

import asyncio
import asyncpg
import os
import sys
from typing import List, Dict, Any

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from app.config import settings


CRITICAL_TABLES = [
    'patients', 'messages', 'quiz_sessions', 'quiz_responses',
    'medical_reports', 'audit_logs', 'appointments', 'medications',
    'treatments', 'consents', 'notifications', 'sessions',
    'alerts', 'flow_analytics', 'flow_messages', 'user_sync_log',
    'webhook_events', 'whatsapp_delivery_failures'
]


async def get_db_connection():
    """Get database connection."""
    database_url = os.getenv("DATABASE_URL") or settings.DATABASE_URL

    # Handle postgres:// vs postgresql:// URL format
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    return await asyncpg.connect(database_url)


async def check_rls_status(conn) -> Dict[str, Any]:
    """Check RLS status for all critical tables."""

    # Check which tables have RLS enabled
    rls_query = """
        SELECT
            t.tablename,
            c.relrowsecurity as rls_enabled,
            c.relforcerowsecurity as rls_forced
        FROM pg_tables t
        JOIN pg_class c ON c.relname = t.tablename
        WHERE t.schemaname = 'public'
        AND t.tablename = ANY($1)
        ORDER BY t.tablename;
    """

    rls_status = await conn.fetch(rls_query, CRITICAL_TABLES)

    # Check policies for each table
    policy_query = """
        SELECT
            tablename,
            COUNT(*) as policy_count,
            ARRAY_AGG(policyname ORDER BY policyname) as policies
        FROM pg_policies
        WHERE schemaname = 'public'
        AND tablename = ANY($1)
        GROUP BY tablename
        ORDER BY tablename;
    """

    policy_status = await conn.fetch(policy_query, CRITICAL_TABLES)

    return {
        'rls_status': rls_status,
        'policy_status': policy_status
    }


async def analyze_security_status(status_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze the security status and identify vulnerabilities."""

    rls_status = {row['tablename']: row for row in status_data['rls_status']}
    policy_status = {row['tablename']: row for row in status_data['policy_status']}

    analysis = {
        'total_tables': len(CRITICAL_TABLES),
        'tables_with_rls': 0,
        'tables_with_policies': 0,
        'vulnerable_tables': [],
        'secure_tables': [],
        'missing_rls': [],
        'missing_policies': []
    }

    for table in CRITICAL_TABLES:
        rls_info = rls_status.get(table)
        policy_info = policy_status.get(table)

        has_rls = rls_info and rls_info['rls_enabled']
        has_policies = policy_info and policy_info['policy_count'] > 0

        if has_rls:
            analysis['tables_with_rls'] += 1
        else:
            analysis['missing_rls'].append(table)

        if has_policies:
            analysis['tables_with_policies'] += 1
        else:
            analysis['missing_policies'].append(table)

        # A table is vulnerable if it has RLS enabled but no policies
        if has_rls and not has_policies:
            analysis['vulnerable_tables'].append(table)
        elif has_rls and has_policies:
            analysis['secure_tables'].append(table)

    return analysis


def print_security_report(analysis: Dict[str, Any], status_data: Dict[str, Any]):
    """Print a comprehensive security report."""

    print("=" * 80)
    print("🔒 RLS SECURITY STATUS REPORT")
    print("=" * 80)

    print(f"\n📊 SUMMARY:")
    print(f"  Total critical tables: {analysis['total_tables']}")
    print(f"  Tables with RLS enabled: {analysis['tables_with_rls']}")
    print(f"  Tables with policies: {analysis['tables_with_policies']}")
    print(f"  Secure tables: {len(analysis['secure_tables'])}")
    print(f"  Vulnerable tables: {len(analysis['vulnerable_tables'])}")

    if analysis['vulnerable_tables']:
        print(f"\n🚨 CRITICAL VULNERABILITY DETECTED!")
        print(f"  Tables with RLS enabled but NO policies:")
        for table in analysis['vulnerable_tables']:
            print(f"    ❌ {table}")
        print(f"\n  These tables are COMPLETELY INACCESSIBLE due to RLS without policies!")

    if analysis['missing_rls']:
        print(f"\n⚠️  Tables without RLS:")
        for table in analysis['missing_rls']:
            print(f"    🔓 {table}")

    if analysis['missing_policies']:
        print(f"\n📝 Tables without policies:")
        for table in analysis['missing_policies']:
            print(f"    📄 {table}")

    if analysis['secure_tables']:
        print(f"\n✅ Properly secured tables:")
        for table in analysis['secure_tables']:
            policy_info = next((p for p in status_data['policy_status'] if p['tablename'] == table), None)
            if policy_info:
                print(f"    🛡️  {table} ({policy_info['policy_count']} policies)")

    print("\n" + "=" * 80)

    # Security score
    security_score = (len(analysis['secure_tables']) / analysis['total_tables']) * 100
    print(f"🔒 SECURITY SCORE: {security_score:.1f}%")

    if security_score < 100:
        print("🚨 IMMEDIATE ACTION REQUIRED: Apply RLS migration to fix vulnerabilities!")
    else:
        print("✅ All critical tables are properly secured!")

    print("=" * 80)


async def main():
    """Main verification function."""

    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']:
        print(__doc__)
        sys.exit(0)

    check_type = "current status"
    if len(sys.argv) > 1:
        if sys.argv[1] == '--check-before':
            check_type = "pre-migration status"
        elif sys.argv[1] == '--check-after':
            check_type = "post-migration status"

    print(f"🔍 Checking RLS {check_type}...")

    try:
        conn = await get_db_connection()

        try:
            status_data = await check_rls_status(conn)
            analysis = await analyze_security_status(status_data)

            print_security_report(analysis, status_data)

            # Exit with error code if vulnerabilities found
            if analysis['vulnerable_tables']:
                sys.exit(1)
            else:
                sys.exit(0)

        finally:
            await conn.close()

    except Exception as e:
        print(f"❌ Error checking RLS status: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())