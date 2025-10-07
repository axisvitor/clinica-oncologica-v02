#!/usr/bin/env python3
"""
Verification Script for P0-2: Ghost Message Duplication Fix

This script helps verify that the fix works correctly by:
1. Checking for duplicate messages in the database
2. Verifying status update synchronization
3. Analyzing message creation patterns
4. Validating Celery task assignments

Usage:
    python scripts/verify_p0_2_fix.py [--patient-id <uuid>] [--hours <int>]

Examples:
    # Check all messages in last 24 hours
    python scripts/verify_p0_2_fix.py

    # Check specific patient in last 6 hours
    python scripts/verify_p0_2_fix.py --patient-id abc123 --hours 6

    # Check all messages in last hour
    python scripts/verify_p0_2_fix.py --hours 1
"""
import sys
import argparse
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, '..')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings


class P02Verifier:
    """Verifier for P0-2 ghost message duplication fix."""

    def __init__(self):
        """Initialize database connection."""
        self.engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()

    def close(self):
        """Close database connection."""
        self.db.close()

    def check_duplicate_messages(
        self,
        patient_id: Optional[UUID] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Check for duplicate messages (same content, same patient, close timestamps).

        Args:
            patient_id: Optional patient filter
            hours: Hours to look back

        Returns:
            Dictionary with duplicate analysis
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        query = text("""
            WITH message_groups AS (
                SELECT
                    patient_id,
                    content,
                    direction,
                    COUNT(*) as count,
                    MIN(created_at) as first_created,
                    MAX(created_at) as last_created,
                    ARRAY_AGG(id::text ORDER BY created_at) as message_ids,
                    ARRAY_AGG(status::text ORDER BY created_at) as statuses
                FROM messages
                WHERE
                    direction = 'OUTBOUND'
                    AND created_at >= :cutoff
                    AND (:patient_id::uuid IS NULL OR patient_id = :patient_id::uuid)
                GROUP BY patient_id, content, direction
                HAVING COUNT(*) > 1
            )
            SELECT
                patient_id::text,
                content,
                count,
                first_created,
                last_created,
                message_ids,
                statuses,
                EXTRACT(EPOCH FROM (last_created - first_created)) as time_diff_seconds
            FROM message_groups
            ORDER BY last_created DESC;
        """)

        result = self.db.execute(
            query,
            {"cutoff": cutoff, "patient_id": str(patient_id) if patient_id else None}
        )

        duplicates = []
        for row in result:
            duplicates.append({
                "patient_id": row.patient_id,
                "content": row.content[:50] + "..." if len(row.content) > 50 else row.content,
                "count": row.count,
                "first_created": row.first_created,
                "last_created": row.last_created,
                "message_ids": row.message_ids,
                "statuses": row.statuses,
                "time_diff_seconds": row.time_diff_seconds
            })

        return {
            "total_duplicates": len(duplicates),
            "duplicates": duplicates,
            "analysis_period_hours": hours,
            "patient_filter": str(patient_id) if patient_id else "all"
        }

    def check_status_synchronization(
        self,
        patient_id: Optional[UUID] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Check if status updates are properly synchronized.

        Args:
            patient_id: Optional patient filter
            hours: Hours to look back

        Returns:
            Dictionary with synchronization analysis
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        query = text("""
            SELECT
                id::text,
                patient_id::text,
                content,
                status,
                scheduled_for,
                sent_at,
                delivered_at,
                read_at,
                created_at,
                message_metadata->>'celery_task_id' as task_id,
                whatsapp_id
            FROM messages
            WHERE
                direction = 'OUTBOUND'
                AND created_at >= :cutoff
                AND (:patient_id::uuid IS NULL OR patient_id = :patient_id::uuid)
            ORDER BY created_at DESC;
        """)

        result = self.db.execute(
            query,
            {"cutoff": cutoff, "patient_id": str(patient_id) if patient_id else None}
        )

        messages = []
        issues = []

        for row in result:
            message = {
                "id": row.id,
                "patient_id": row.patient_id,
                "content_preview": row.content[:50] + "..." if len(row.content) > 50 else row.content,
                "status": row.status,
                "scheduled_for": row.scheduled_for,
                "sent_at": row.sent_at,
                "delivered_at": row.delivered_at,
                "read_at": row.read_at,
                "created_at": row.created_at,
                "task_id": row.task_id,
                "whatsapp_id": row.whatsapp_id
            }

            messages.append(message)

            # Check for issues
            if row.status == 'SCHEDULED' and not row.task_id:
                issues.append({
                    "message_id": row.id,
                    "issue": "SCHEDULED status but no celery_task_id",
                    "severity": "high"
                })

            if row.status in ['SENT', 'DELIVERED', 'READ'] and not row.whatsapp_id:
                issues.append({
                    "message_id": row.id,
                    "issue": f"{row.status} status but no whatsapp_id",
                    "severity": "medium"
                })

            if row.sent_at and row.delivered_at and row.sent_at > row.delivered_at:
                issues.append({
                    "message_id": row.id,
                    "issue": "sent_at is after delivered_at (invalid timeline)",
                    "severity": "high"
                })

        return {
            "total_messages": len(messages),
            "total_issues": len(issues),
            "messages": messages,
            "issues": issues,
            "analysis_period_hours": hours
        }

    def analyze_message_creation_patterns(
        self,
        patient_id: Optional[UUID] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Analyze message creation patterns to detect anomalies.

        Args:
            patient_id: Optional patient filter
            hours: Hours to look back

        Returns:
            Dictionary with pattern analysis
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        query = text("""
            SELECT
                patient_id::text,
                direction,
                COUNT(*) as total_messages,
                COUNT(DISTINCT whatsapp_id) FILTER (WHERE whatsapp_id IS NOT NULL) as unique_whatsapp_ids,
                COUNT(*) FILTER (WHERE status = 'PENDING') as pending_count,
                COUNT(*) FILTER (WHERE status = 'SCHEDULED') as scheduled_count,
                COUNT(*) FILTER (WHERE status = 'SENT') as sent_count,
                COUNT(*) FILTER (WHERE status = 'DELIVERED') as delivered_count,
                COUNT(*) FILTER (WHERE status = 'READ') as read_count,
                COUNT(*) FILTER (WHERE status = 'FAILED') as failed_count
            FROM messages
            WHERE
                created_at >= :cutoff
                AND (:patient_id::uuid IS NULL OR patient_id = :patient_id::uuid)
            GROUP BY patient_id, direction
            ORDER BY total_messages DESC;
        """)

        result = self.db.execute(
            query,
            {"cutoff": cutoff, "patient_id": str(patient_id) if patient_id else None}
        )

        patterns = []
        anomalies = []

        for row in result:
            pattern = {
                "patient_id": row.patient_id,
                "direction": row.direction,
                "total_messages": row.total_messages,
                "unique_whatsapp_ids": row.unique_whatsapp_ids,
                "status_breakdown": {
                    "PENDING": row.pending_count,
                    "SCHEDULED": row.scheduled_count,
                    "SENT": row.sent_count,
                    "DELIVERED": row.delivered_count,
                    "READ": row.read_count,
                    "FAILED": row.failed_count
                }
            }

            patterns.append(pattern)

            # Detect anomalies
            if row.direction == 'OUTBOUND':
                # More messages than unique WhatsApp IDs (potential duplicates)
                if row.unique_whatsapp_ids > 0 and row.total_messages > row.unique_whatsapp_ids * 1.5:
                    anomalies.append({
                        "patient_id": row.patient_id,
                        "anomaly": "Potential duplicate messages",
                        "details": f"{row.total_messages} messages but only {row.unique_whatsapp_ids} unique WhatsApp IDs",
                        "severity": "high"
                    })

                # Too many PENDING messages
                if row.pending_count > 10:
                    anomalies.append({
                        "patient_id": row.patient_id,
                        "anomaly": "Too many PENDING messages",
                        "details": f"{row.pending_count} messages stuck in PENDING",
                        "severity": "medium"
                    })

        return {
            "patterns": patterns,
            "anomalies": anomalies,
            "analysis_period_hours": hours
        }

    def generate_report(
        self,
        patient_id: Optional[UUID] = None,
        hours: int = 24
    ) -> str:
        """
        Generate comprehensive verification report.

        Args:
            patient_id: Optional patient filter
            hours: Hours to look back

        Returns:
            Formatted report string
        """
        print(f"\n{'='*80}")
        print(f"P0-2 Ghost Message Duplication Fix - Verification Report")
        print(f"{'='*80}\n")
        print(f"Analysis Period: Last {hours} hours")
        if patient_id:
            print(f"Patient Filter: {patient_id}")
        else:
            print(f"Patient Filter: All patients")
        print(f"Report Generated: {datetime.utcnow().isoformat()}\n")

        # Check duplicates
        print(f"\n{'─'*80}")
        print("1. DUPLICATE MESSAGE DETECTION")
        print(f"{'─'*80}")
        duplicates = self.check_duplicate_messages(patient_id, hours)
        print(f"Total Duplicates Found: {duplicates['total_duplicates']}")

        if duplicates['total_duplicates'] > 0:
            print("\n⚠️  WARNING: Duplicate messages detected!\n")
            for dup in duplicates['duplicates'][:5]:  # Show first 5
                print(f"  Patient: {dup['patient_id']}")
                print(f"  Content: {dup['content']}")
                print(f"  Count: {dup['count']}")
                print(f"  Time Diff: {dup['time_diff_seconds']:.2f} seconds")
                print(f"  Message IDs: {', '.join(dup['message_ids'][:3])}...")
                print(f"  Statuses: {', '.join(dup['statuses'][:3])}...")
                print()
        else:
            print("✅ No duplicate messages found!")

        # Check status synchronization
        print(f"\n{'─'*80}")
        print("2. STATUS SYNCHRONIZATION CHECK")
        print(f"{'─'*80}")
        sync = self.check_status_synchronization(patient_id, hours)
        print(f"Total Messages Analyzed: {sync['total_messages']}")
        print(f"Total Issues Found: {sync['total_issues']}")

        if sync['total_issues'] > 0:
            print("\n⚠️  WARNING: Synchronization issues detected!\n")
            for issue in sync['issues'][:5]:  # Show first 5
                print(f"  Message ID: {issue['message_id']}")
                print(f"  Issue: {issue['issue']}")
                print(f"  Severity: {issue['severity']}")
                print()
        else:
            print("✅ No synchronization issues found!")

        # Analyze patterns
        print(f"\n{'─'*80}")
        print("3. MESSAGE CREATION PATTERN ANALYSIS")
        print(f"{'─'*80}")
        patterns = self.analyze_message_creation_patterns(patient_id, hours)
        print(f"Total Patterns Analyzed: {len(patterns['patterns'])}")
        print(f"Total Anomalies Found: {len(patterns['anomalies'])}")

        if patterns['anomalies']:
            print("\n⚠️  WARNING: Anomalies detected!\n")
            for anomaly in patterns['anomalies'][:5]:  # Show first 5
                print(f"  Patient: {anomaly['patient_id']}")
                print(f"  Anomaly: {anomaly['anomaly']}")
                print(f"  Details: {anomaly['details']}")
                print(f"  Severity: {anomaly['severity']}")
                print()
        else:
            print("✅ No anomalies found!")

        # Summary
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}\n")

        total_issues = (
            duplicates['total_duplicates'] +
            sync['total_issues'] +
            len(patterns['anomalies'])
        )

        if total_issues == 0:
            print("🎉 ALL CHECKS PASSED! P0-2 fix is working correctly.")
            print("\n✅ No duplicate messages")
            print("✅ Status synchronization working")
            print("✅ No anomalous patterns detected")
        else:
            print(f"⚠️  ISSUES DETECTED: {total_issues} total issues found")
            print(f"\n  - Duplicate messages: {duplicates['total_duplicates']}")
            print(f"  - Synchronization issues: {sync['total_issues']}")
            print(f"  - Pattern anomalies: {len(patterns['anomalies'])}")
            print("\n❌ P0-2 fix may need attention. Review issues above.")

        print(f"\n{'='*80}\n")

        return total_issues


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify P0-2 ghost message duplication fix"
    )
    parser.add_argument(
        "--patient-id",
        type=str,
        help="UUID of patient to filter by (optional)"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Hours to look back (default: 24)"
    )

    args = parser.parse_args()

    patient_id = UUID(args.patient_id) if args.patient_id else None

    verifier = P02Verifier()
    try:
        total_issues = verifier.generate_report(patient_id, args.hours)
        sys.exit(0 if total_issues == 0 else 1)
    finally:
        verifier.close()


if __name__ == "__main__":
    main()
