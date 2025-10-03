"""
Audit Cleanup Job

Scheduled job to clean up old audit trail records (> 90 days).
Runs daily at 2 AM via APScheduler.

Related migrations:
- create_audit_retention_functions (migration #51)
"""

import logging
from datetime import datetime
from typing import Dict, Any

from app.core.database_direct import execute_sql

logger = logging.getLogger(__name__)


class AuditCleanupJob:
    """Job to clean up old audit trail and audit_log_entries records"""

    @staticmethod
    async def run() -> Dict[str, Any]:
        """
        Execute audit cleanup by calling Supabase stored procedure.

        Returns:
            Dict containing cleanup results:
            - table_name: Name of cleaned table
            - deleted_count: Number of records deleted
            - space_before: Size before cleanup
            - space_after: Size after cleanup
        """
        try:
            logger.info("Starting audit cleanup job at %s", datetime.now())

            # Call the Supabase stored procedure
            result = await execute_sql(
                "SELECT * FROM cleanup_all_audit_tables();"
            )

            # Log results
            total_deleted = 0
            for row in result:
                table_name = row.get("table_name", "unknown")
                deleted = row.get("deleted_count", 0)
                space_before = row.get("space_before", "unknown")
                space_after = row.get("space_after", "unknown")

                total_deleted += deleted

                logger.info(
                    "Cleaned %s: %d records deleted, size %s -> %s",
                    table_name,
                    deleted,
                    space_before,
                    space_after,
                )

            logger.info(
                "Audit cleanup completed successfully. Total deleted: %d records",
                total_deleted,
            )

            # Return summary
            return {
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "total_deleted": total_deleted,
                "details": result,
            }

        except Exception as e:
            logger.error("Audit cleanup failed: %s", str(e), exc_info=True)
            return {
                "success": False,
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }

    @staticmethod
    async def run_vacuum() -> None:
        """
        Run VACUUM on audit tables to reclaim space after cleanup.

        Should be called after cleanup to physically reclaim disk space.
        """
        try:
            logger.info("Running VACUUM on audit tables...")

            await execute_sql("VACUUM ANALYZE public.audit_trail;")
            await execute_sql("VACUUM ANALYZE public.audit_log_entries;")

            logger.info("VACUUM completed successfully")

        except Exception as e:
            logger.error("VACUUM failed: %s", str(e), exc_info=True)

    @staticmethod
    async def get_stats() -> Dict[str, Any]:
        """
        Get current audit tables statistics.

        Returns:
            Dict containing:
            - table_name: Name of audit table
            - total_records: Total number of records
            - old_records: Records older than 90 days
            - table_size: Current size of table
        """
        try:
            query = """
            SELECT
              'audit_trail' as table_name,
              COUNT(*) as total_records,
              COUNT(*) FILTER (WHERE created_at < NOW() - INTERVAL '90 days') as old_records,
              pg_size_pretty(pg_total_relation_size('public.audit_trail')) as table_size
            FROM public.audit_trail
            UNION ALL
            SELECT
              'audit_log_entries',
              COUNT(*),
              COUNT(*) FILTER (WHERE timestamp < NOW() - INTERVAL '90 days'),
              pg_size_pretty(pg_total_relation_size('public.audit_log_entries'))
            FROM public.audit_log_entries;
            """

            result = await execute_sql(query)
            return {"success": True, "stats": result}

        except Exception as e:
            logger.error("Failed to get audit stats: %s", str(e))
            return {"success": False, "error": str(e)}
