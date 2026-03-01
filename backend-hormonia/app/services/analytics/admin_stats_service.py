"""
Admin statistics service for system monitoring.
Provides real-time metrics for CPU, memory, disk, users, and database.
"""

import psutil
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, text
from typing import Dict, Any

from app.models.user import User
from app.models.patient import Patient
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class AdminStatsService:
    """Service for collecting system, user, and database statistics."""

    def __init__(self, db: Any):
        """
        Initialize admin stats service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get system-level metrics using psutil.

        Returns:
            Dict with CPU, memory, disk usage percentages and uptime seconds

        Raises:
            Exception: If psutil fails to collect metrics
        """
        try:
            # CPU usage (non-blocking, 0.1s interval)
            cpu_percent = psutil.cpu_percent(interval=0.1)

            # Memory usage
            memory_info = psutil.virtual_memory()
            memory_percent = memory_info.percent

            # Disk usage (root partition)
            disk_info = psutil.disk_usage("/")
            disk_percent = disk_info.percent

            # System uptime
            boot_time = psutil.boot_time()
            uptime_seconds = int((datetime.now().timestamp() - boot_time))

            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_percent": round(memory_percent, 2),
                "disk_percent": round(disk_percent, 2),
                "uptime_seconds": uptime_seconds,
            }
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            # Return fallback metrics if psutil fails
            return {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "disk_percent": 0.0,
                "uptime_seconds": 0,
            }

    def get_user_metrics(self) -> Dict[str, Any]:
        """
        Get user statistics from database.

        Returns:
            Dict with total users, active users, and role distribution

        Raises:
            Exception: If database query fails
        """
        try:
            # Total users
            total_users = self.db.query(User).count()

            # Active users (users with recent activity - last 24 hours)
            # Since we don't have last_login field, we'll use last_firebase_sync as proxy
            yesterday = now_sao_paulo() - timedelta(days=1)
            active_now = (
                self.db.query(User)
                .filter(User.firebase_last_sign_in >= yesterday)
                .count()
            )

            # Users by role
            role_counts = (
                self.db.query(User.role, func.count(User.id)).group_by(User.role).all()
            )

            # Convert role enum to string and create dict
            by_role = {}
            for role, count in role_counts:
                # role is UserRole enum, get the string value
                role_str = role.value if hasattr(role, "value") else str(role)
                by_role[role_str] = count

            return {"total": total_users, "active_now": active_now, "by_role": by_role}
        except Exception as e:
            logger.error(f"Failed to collect user metrics: {e}")
            raise

    def get_database_metrics(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dict with total records, patients, users, and active connections

        Raises:
            Exception: If database query fails
        """
        try:
            # Count users
            total_users = self.db.query(User).count()

            # Count patients
            total_patients = self.db.query(Patient).count()

            # Total records (sum of main tables)
            total_records = total_users + total_patients

            # Active database connections from pg_stat_activity
            try:
                result = self.db.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                )
                connections = result.scalar() or 0
            except Exception as e:
                logger.warning(f"Could not query pg_stat_activity: {e}")
                # Fallback: assume at least 1 connection (current)
                connections = 1

            return {
                "total_records": total_records,
                "total_patients": total_patients,
                "total_users": total_users,
                "connections": connections,
            }
        except Exception as e:
            logger.error(f"Failed to collect database metrics: {e}")
            raise

    def get_all_stats(self) -> Dict[str, Any]:
        """
        Get all system statistics in one call.

        Returns:
            Dict with system, users, database metrics and timestamp

        Raises:
            Exception: If any metric collection fails
        """
        return {
            "system": self.get_system_metrics(),
            "users": self.get_user_metrics(),
            "database": self.get_database_metrics(),
            "timestamp": now_sao_paulo().isoformat(),
        }
