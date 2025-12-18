"""
HIPAA Audit Repository - Phase 3 Sprint 1

This repository handles database operations for audit logs including:
- Integrity verification
- Archival management
- Raw SQL execution for PostgreSQL functions

HIPAA Compliance:
- § 164.312(c)(1) - Integrity verification
- § 164.316(b)(2)(i) - Archival & retention
"""

from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class AuditRepository:
    """
    Repository for audit log database operations.
    """

    def __init__(self, db: AsyncSession):
        """Initialize repository with database session."""
        self.db = db

    async def verify_integrity(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Verify audit log integrity using the PostgreSQL verify_audit_log_integrity function.

        Args:
            start_date: Start date for verification range (optional)
            end_date: End date for verification range (optional)

        Returns:
            Dictionary with verification results
        """
        # Call PostgreSQL function
        if start_date and end_date:
            query = text("""
                SELECT * FROM verify_audit_log_integrity(
                    :start_timestamp,
                    :end_timestamp
                )
            """)
            result = await self.db.execute(
                query, {"start_timestamp": start_date, "end_timestamp": end_date}
            )
        else:
            query = text("SELECT * FROM verify_audit_log_integrity()")
            result = await self.db.execute(query)

        row = result.fetchone()

        if row:
            return {
                "total_checked": row[0],
                "valid_count": row[1],
                "invalid_count": row[2],
                "chain_breaks": row[3],
                "invalid_log_ids": row[4] or [],
                "integrity_score": round((row[1] / row[0] * 100), 2)
                if row[0] > 0
                else 100.0,
                "has_tampering": row[2] > 0 or row[3] > 0,
            }
        else:
            return {
                "total_checked": 0,
                "valid_count": 0,
                "invalid_count": 0,
                "chain_breaks": 0,
                "invalid_log_ids": [],
                "integrity_score": 100.0,
                "has_tampering": False,
            }

    async def archive_old_logs(self) -> int:
        """
        Archive audit logs older than 1 year using the PostgreSQL archive_old_audit_logs function.

        Returns:
            Number of logs archived
        """
        query = text("SELECT archive_old_audit_logs()")
        result = await self.db.execute(query)
        await self.db.commit()

        archived_count = result.scalar()
        return archived_count or 0

    async def get_retention_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about audit log retention and archival.

        Returns:
            Dictionary with retention statistics
        """
        # Count logs in main table
        main_query = text("""
            SELECT
                COUNT(*) as total_logs,
                COUNT(*) FILTER (WHERE archived = true) as archived_logs,
                COUNT(*) FILTER (WHERE archive_eligible_at < NOW()) as eligible_for_archive,
                MIN(created_at) as oldest_log,
                MAX(created_at) as newest_log
            FROM audit_logs
        """)
        main_result = await self.db.execute(main_query)
        main_row = main_result.fetchone()

        # Count logs in archive table
        archive_query = text("""
            SELECT COUNT(*) as archive_count
            FROM audit_logs_archive
        """)
        archive_result = await self.db.execute(archive_query)
        archive_row = archive_result.fetchone()

        return {
            "main_table": {
                "total_logs": main_row[0] if main_row else 0,
                "archived_logs": main_row[1] if main_row else 0,
                "eligible_for_archive": main_row[2] if main_row else 0,
                "oldest_log": main_row[3].isoformat()
                if main_row and main_row[3]
                else None,
                "newest_log": main_row[4].isoformat()
                if main_row and main_row[4]
                else None,
            },
            "archive_table": {"total_logs": archive_row[0] if archive_row else 0},
            "total_system_logs": (main_row[0] if main_row else 0)
            + (archive_row[0] if archive_row else 0),
        }

    async def get_disk_usage_estimate(self) -> Dict[str, Any]:
        """
        Estimate disk usage for audit logs.

        Returns:
            Dictionary with disk usage estimates
        """
        query = text("""
            SELECT
                pg_size_pretty(pg_total_relation_size('audit_logs')) as main_table_size,
                pg_size_pretty(pg_total_relation_size('audit_logs_archive')) as archive_table_size,
                pg_total_relation_size('audit_logs') as main_table_bytes,
                pg_total_relation_size('audit_logs_archive') as archive_table_bytes
        """)
        result = await self.db.execute(query)
        row = result.fetchone()

        if row:
            total_bytes = row[2] + row[3]
            return {
                "main_table_size": row[0],
                "archive_table_size": row[1],
                "total_size": f"{total_bytes / (1024**3):.2f} GB",
                "main_table_bytes": row[2],
                "archive_table_bytes": row[3],
                "total_bytes": total_bytes,
            }
        else:
            return {
                "main_table_size": "0 bytes",
                "archive_table_size": "0 bytes",
                "total_size": "0.00 GB",
                "main_table_bytes": 0,
                "archive_table_bytes": 0,
                "total_bytes": 0,
            }

    async def get_index_health(self) -> Dict[str, Any]:
        """
        Check the health of audit log indexes.

        Returns:
            Dictionary with index health information
        """
        query = text("""
            SELECT
                schemaname,
                tablename,
                indexname,
                pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size,
                idx_scan as scans,
                idx_tup_read as tuples_read,
                idx_tup_fetch as tuples_fetched
            FROM pg_stat_user_indexes
            WHERE tablename IN ('audit_logs', 'audit_logs_archive')
            ORDER BY pg_relation_size(indexname::regclass) DESC
        """)
        result = await self.db.execute(query)
        rows = result.fetchall()

        indexes = []
        for row in rows:
            indexes.append(
                {
                    "schema": row[0],
                    "table": row[1],
                    "index_name": row[2],
                    "size": row[3],
                    "scans": row[4],
                    "tuples_read": row[5],
                    "tuples_fetched": row[6],
                    "efficiency": round((row[6] / row[5] * 100), 2)
                    if row[5] > 0
                    else 0.0,
                }
            )

        return {"indexes": indexes, "total_indexes": len(indexes)}

    async def check_immutability_rules(self) -> Dict[str, Any]:
        """
        Verify that immutability rules are in place.

        Returns:
            Dictionary with immutability rule status
        """
        query = text("""
            SELECT
                COUNT(*) FILTER (WHERE rulename = 'audit_logs_no_update') as has_update_rule,
                COUNT(*) FILTER (WHERE rulename = 'audit_logs_no_delete') as has_delete_rule
            FROM pg_rules
            WHERE tablename = 'audit_logs'
        """)
        result = await self.db.execute(query)
        row = result.fetchone()

        return {
            "update_rule_active": row[0] > 0 if row else False,
            "delete_rule_active": row[1] > 0 if row else False,
            "fully_immutable": (row[0] > 0 and row[1] > 0) if row else False,
        }

    async def get_checksum_coverage(self) -> Dict[str, Any]:
        """
        Get statistics about checksum coverage.

        Returns:
            Dictionary with checksum coverage statistics
        """
        query = text("""
            SELECT
                COUNT(*) as total_logs,
                COUNT(*) FILTER (WHERE checksum IS NOT NULL) as logs_with_checksum,
                COUNT(*) FILTER (WHERE checksum IS NOT NULL AND previous_checksum IS NOT NULL) as logs_with_chain,
                COUNT(*) FILTER (WHERE integrity_verified = false) as unverified_logs
            FROM audit_logs
        """)
        result = await self.db.execute(query)
        row = result.fetchone()

        if row:
            total = row[0]
            with_checksum = row[1]
            with_chain = row[2]
            unverified = row[3]

            return {
                "total_logs": total,
                "logs_with_checksum": with_checksum,
                "logs_with_chain": with_chain,
                "unverified_logs": unverified,
                "checksum_coverage": round((with_checksum / total * 100), 2)
                if total > 0
                else 0.0,
                "chain_coverage": round((with_chain / total * 100), 2)
                if total > 0
                else 0.0,
            }
        else:
            return {
                "total_logs": 0,
                "logs_with_checksum": 0,
                "logs_with_chain": 0,
                "unverified_logs": 0,
                "checksum_coverage": 0.0,
                "chain_coverage": 0.0,
            }
