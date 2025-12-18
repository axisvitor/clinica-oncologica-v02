"""
Database Initialization Service for Hormonia Backend.

Handles:
- Database schema validation
- Migration status checking
- Index optimization
- Connection pool management
- Performance monitoring setup
"""

from typing import Dict, Any, Optional
from datetime import datetime

from sqlalchemy import text, inspect
from sqlalchemy.engine import Engine
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.database import get_engine
from app.utils.logging import get_logger

logger = get_logger(__name__)


class DatabaseInitializationError(Exception):
    """Custom exception for database initialization failures."""

    pass


class DatabaseInitializationService:
    """Comprehensive database initialization and validation service."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.engine: Optional[Engine] = None

    async def initialize_database(self) -> Dict[str, Any]:
        """Initialize and validate database with comprehensive checks."""
        self.logger.info("🔌 Initializing database system...")

        initialization_result = {
            "started_at": datetime.utcnow().isoformat(),
            "status": "initializing",
            "checks": {},
            "performance_metrics": {},
            "warnings": [],
            "errors": [],
        }

        try:
            # Get database engine
            self.engine = get_engine()

            # Perform initialization checks
            await self._check_connectivity(initialization_result)
            await self._check_schema_status(initialization_result)
            await self._check_migrations(initialization_result)
            await self._validate_indexes(initialization_result)
            await self._check_table_integrity(initialization_result)
            await self._assess_performance(initialization_result)
            await self._validate_constraints(initialization_result)

            initialization_result["status"] = "completed"
            initialization_result["completed_at"] = datetime.utcnow().isoformat()

            self.logger.info("✅ Database initialization completed successfully")

        except Exception as e:
            initialization_result["status"] = "failed"
            initialization_result["errors"].append(str(e))
            self.logger.error(f"❌ Database initialization failed: {e}")
            raise DatabaseInitializationError(f"Database initialization failed: {e}")

        return initialization_result

    async def _check_connectivity(self, result: Dict[str, Any]) -> None:
        """Check database connectivity and basic operations."""
        try:
            with self.engine.connect() as conn:
                # Test basic query
                test_result = conn.execute(text("SELECT 1 as test"))
                test_value = test_result.scalar()

                if test_value != 1:
                    raise DatabaseInitializationError("Basic connectivity test failed")

                # Test transaction capability
                with conn.begin():
                    conn.execute(text("SELECT NOW() as current_time"))

                # Get database version and info
                version_result = conn.execute(text("SELECT version() as db_version"))
                db_version = version_result.scalar()

                result["checks"]["connectivity"] = {
                    "status": "success",
                    "database_version": db_version,
                    "engine_url": self.engine.url.render_as_string(hide_password=True),
                    "pool_size": self.engine.pool.size(),
                    "checked_at": datetime.utcnow().isoformat(),
                }

            self.logger.info("✅ Database connectivity check passed")

        except Exception as e:
            result["checks"]["connectivity"] = {
                "status": "failed",
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat(),
            }
            raise

    async def _check_schema_status(self, result: Dict[str, Any]) -> None:
        """Check database schema and table existence."""
        try:
            inspector = inspect(self.engine)

            # Get list of all tables
            tables = inspector.get_table_names()

            # Define expected core tables
            expected_tables = [
                "users",
                "patients",
                "messages",
                "patient_flow_states",
                "quiz_templates",
                "quiz_responses",
                "medical_reports",
                "alerts",
                "flow_analytics",
                "audit_logs",
            ]

            missing_tables = [table for table in expected_tables if table not in tables]
            extra_tables = [
                table
                for table in tables
                if table not in expected_tables and not table.startswith("alembic")
            ]

            # Check table schemas for key tables
            table_schemas = {}
            for table in ["users", "patients", "messages"]:
                if table in tables:
                    columns = inspector.get_columns(table)
                    indexes = inspector.get_indexes(table)
                    foreign_keys = inspector.get_foreign_keys(table)

                    table_schemas[table] = {
                        "columns": len(columns),
                        "indexes": len(indexes),
                        "foreign_keys": len(foreign_keys),
                        "column_names": [col["name"] for col in columns],
                    }

            result["checks"]["schema"] = {
                "status": "success" if not missing_tables else "warning",
                "total_tables": len(tables),
                "expected_tables": len(expected_tables),
                "missing_tables": missing_tables,
                "extra_tables": extra_tables,
                "table_schemas": table_schemas,
                "checked_at": datetime.utcnow().isoformat(),
            }

            if missing_tables:
                result["warnings"].append(
                    f"Missing expected tables: {', '.join(missing_tables)}"
                )

            self.logger.info(f"✅ Schema check completed: {len(tables)} tables found")

        except Exception as e:
            result["checks"]["schema"] = {
                "status": "failed",
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat(),
            }
            raise

    async def _check_migrations(self, result: Dict[str, Any]) -> None:
        """Check Alembic migration status."""
        try:
            # Check if alembic_version table exists
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()

            if "alembic_version" not in tables:
                result["checks"]["migrations"] = {
                    "status": "warning",
                    "message": "Alembic version table not found - migrations may not be initialized",
                    "checked_at": datetime.utcnow().isoformat(),
                }
                result["warnings"].append("Migration system not initialized")
                return

            # Get current migration version
            with self.engine.connect() as conn:
                version_result = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                )
                current_version = version_result.scalar()

            # Try to get migration context (requires alembic.ini file)
            try:
                from pathlib import Path

                alembic_cfg_path = Path("alembic.ini")

                if alembic_cfg_path.exists():
                    alembic_cfg = Config(str(alembic_cfg_path))
                    script_dir = ScriptDirectory.from_config(alembic_cfg)

                    with self.engine.connect() as conn:
                        context = MigrationContext.configure(conn)
                        current_rev = context.get_current_revision()
                        head_rev = script_dir.get_current_head()

                        is_up_to_date = current_rev == head_rev

                        result["checks"]["migrations"] = {
                            "status": "success" if is_up_to_date else "warning",
                            "current_revision": current_rev,
                            "head_revision": head_rev,
                            "up_to_date": is_up_to_date,
                            "checked_at": datetime.utcnow().isoformat(),
                        }

                        if not is_up_to_date:
                            result["warnings"].append(
                                "Database migrations are not up to date"
                            )
                else:
                    result["checks"]["migrations"] = {
                        "status": "warning",
                        "message": "Alembic configuration file not found",
                        "current_version": current_version,
                        "checked_at": datetime.utcnow().isoformat(),
                    }
                    result["warnings"].append("Alembic configuration not found")

            except Exception as alembic_error:
                result["checks"]["migrations"] = {
                    "status": "warning",
                    "error": str(alembic_error),
                    "current_version": current_version,
                    "checked_at": datetime.utcnow().isoformat(),
                }
                result["warnings"].append(
                    f"Migration check incomplete: {str(alembic_error)}"
                )

            self.logger.info("✅ Migration status check completed")

        except Exception as e:
            result["checks"]["migrations"] = {
                "status": "failed",
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat(),
            }
            # Don't raise here - migrations check is not critical for operation
            self.logger.warning(f"Migration check failed: {e}")

    async def _validate_indexes(self, result: Dict[str, Any]) -> None:
        """Validate database indexes for performance."""
        try:
            inspector = inspect(self.engine)

            # Check indexes on key tables
            important_tables = ["users", "patients", "messages", "patient_flow_states"]
            index_analysis = {}

            for table in important_tables:
                if table in inspector.get_table_names():
                    indexes = inspector.get_indexes(table)
                    columns = inspector.get_columns(table)

                    # Analyze index coverage
                    indexed_columns = set()
                    for index in indexes:
                        indexed_columns.update(index["column_names"])

                    total_columns = len(columns)
                    indexed_count = len(indexed_columns)

                    index_analysis[table] = {
                        "total_indexes": len(indexes),
                        "total_columns": total_columns,
                        "indexed_columns": indexed_count,
                        "coverage_percent": (indexed_count / total_columns * 100)
                        if total_columns > 0
                        else 0,
                        "index_details": [
                            {
                                "name": idx["name"],
                                "columns": idx["column_names"],
                                "unique": idx["unique"],
                            }
                            for idx in indexes
                        ],
                    }

            result["checks"]["indexes"] = {
                "status": "success",
                "analysis": index_analysis,
                "checked_at": datetime.utcnow().isoformat(),
            }

            self.logger.info("✅ Index validation completed")

        except Exception as e:
            result["checks"]["indexes"] = {
                "status": "failed",
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat(),
            }
            # Don't raise - index check is not critical
            self.logger.warning(f"Index validation failed: {e}")

    async def _check_table_integrity(self, result: Dict[str, Any]) -> None:
        """Check table data integrity and constraints."""
        try:
            integrity_checks = {}

            # Check key tables exist and have data
            key_tables = ["users", "patients", "messages"]

            with self.engine.connect() as conn:
                for table in key_tables:
                    try:
                        # Check if table exists and get row count
                        count_result = conn.execute(
                            text(f"SELECT COUNT(*) FROM {table}")
                        )
                        row_count = count_result.scalar()

                        # Check for any obvious data issues
                        null_check = conn.execute(
                            text(f"SELECT COUNT(*) FROM {table} WHERE id IS NULL")
                        )
                        null_ids = null_check.scalar()

                        integrity_checks[table] = {
                            "exists": True,
                            "row_count": row_count,
                            "null_ids": null_ids,
                            "status": "healthy" if null_ids == 0 else "warning",
                        }

                        if null_ids > 0:
                            result["warnings"].append(
                                f"Table {table} has {null_ids} rows with NULL IDs"
                            )

                    except Exception as table_error:
                        integrity_checks[table] = {
                            "exists": False,
                            "error": str(table_error),
                            "status": "error",
                        }

            result["checks"]["integrity"] = {
                "status": "success",
                "table_checks": integrity_checks,
                "checked_at": datetime.utcnow().isoformat(),
            }

            self.logger.info("✅ Table integrity check completed")

        except Exception as e:
            result["checks"]["integrity"] = {
                "status": "failed",
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat(),
            }
            # Don't raise - integrity check is not critical for startup
            self.logger.warning(f"Table integrity check failed: {e}")

    async def _assess_performance(self, result: Dict[str, Any]) -> None:
        """Assess database performance metrics."""
        try:
            performance_metrics = {}

            with self.engine.connect() as conn:
                # Test query performance
                start_time = datetime.utcnow()
                conn.execute(text("SELECT 1"))
                simple_query_time = (
                    datetime.utcnow() - start_time
                ).total_seconds() * 1000

                # Test more complex query if tables exist
                try:
                    start_time = datetime.utcnow()
                    conn.execute(text("SELECT COUNT(*) FROM users"))
                    count_query_time = (
                        datetime.utcnow() - start_time
                    ).total_seconds() * 1000
                except Exception:
                    count_query_time = None  # Table may not exist yet

                # Get connection pool stats
                pool = self.engine.pool
                pool_stats = {
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "invalid": getattr(pool, "invalid", 0),
                }

                performance_metrics = {
                    "simple_query_ms": simple_query_time,
                    "count_query_ms": count_query_time,
                    "connection_pool": pool_stats,
                }

            result["performance_metrics"] = performance_metrics

            # Add warnings for slow performance
            if simple_query_time > 100:  # 100ms threshold
                result["warnings"].append(
                    f"Slow database response: {simple_query_time:.2f}ms for simple query"
                )

            self.logger.info(
                f"✅ Performance assessment completed: {simple_query_time:.2f}ms response time"
            )

        except Exception as e:
            result["performance_metrics"] = {"error": str(e)}
            self.logger.warning(f"Performance assessment failed: {e}")

    async def _validate_constraints(self, result: Dict[str, Any]) -> None:
        """Validate database constraints and foreign keys."""
        try:
            inspector = inspect(self.engine)
            constraint_analysis = {}

            # Check constraints on key tables
            key_tables = ["users", "patients", "messages"]

            for table in key_tables:
                if table in inspector.get_table_names():
                    foreign_keys = inspector.get_foreign_keys(table)
                    primary_keys = inspector.get_pk_constraint(table)
                    unique_constraints = inspector.get_unique_constraints(table)
                    check_constraints = inspector.get_check_constraints(table)

                    constraint_analysis[table] = {
                        "foreign_keys": len(foreign_keys),
                        "primary_key": primary_keys.get("name")
                        if primary_keys
                        else None,
                        "unique_constraints": len(unique_constraints),
                        "check_constraints": len(check_constraints),
                        "details": {
                            "fk_details": [
                                {
                                    "name": fk.get("name"),
                                    "constrained_columns": fk.get(
                                        "constrained_columns"
                                    ),
                                    "referred_table": fk.get("referred_table"),
                                }
                                for fk in foreign_keys
                            ]
                        },
                    }

            result["checks"]["constraints"] = {
                "status": "success",
                "analysis": constraint_analysis,
                "checked_at": datetime.utcnow().isoformat(),
            }

            self.logger.info("✅ Constraint validation completed")

        except Exception as e:
            result["checks"]["constraints"] = {
                "status": "failed",
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat(),
            }
            self.logger.warning(f"Constraint validation failed: {e}")

    async def get_database_status(self) -> Dict[str, Any]:
        """Get current database status without full initialization."""
        try:
            if not self.engine:
                self.engine = get_engine()

            status = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "basic_checks": {},
            }

            # Quick connectivity check
            with self.engine.connect() as conn:
                start_time = datetime.utcnow()
                conn.execute(text("SELECT 1"))
                response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                status["basic_checks"]["connectivity"] = {
                    "status": "healthy",
                    "response_time_ms": response_time,
                }

                # Quick table count check
                try:
                    user_count = conn.execute(
                        text("SELECT COUNT(*) FROM users")
                    ).scalar()
                    status["basic_checks"]["data_access"] = {
                        "status": "healthy",
                        "sample_count": user_count,
                    }
                except Exception:
                    status["basic_checks"]["data_access"] = {
                        "status": "warning",
                        "message": "Could not access user table",
                    }

            return status

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }


# Global service instance
_db_init_service = None


def get_database_initialization_service() -> DatabaseInitializationService:
    """Get database initialization service instance."""
    global _db_init_service
    if _db_init_service is None:
        _db_init_service = DatabaseInitializationService()
    return _db_init_service
