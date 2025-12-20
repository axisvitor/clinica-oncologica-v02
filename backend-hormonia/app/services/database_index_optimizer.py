"""
Database Index Optimizer Service.
Analyzes queries and suggests/creates optimal database indexes for analytics performance.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text, inspect

from app.core.monitoring_logging import monitoring_logger


logger = logging.getLogger(__name__)


@dataclass
class IndexRecommendation:
    """Represents a database index recommendation."""

    table_name: str
    columns: List[str]
    index_type: str  # 'btree', 'hash', 'gin', 'gist'
    reason: str
    estimated_benefit: str  # 'high', 'medium', 'low'
    query_patterns: List[str]
    existing_index: Optional[str] = None


@dataclass
class IndexAnalysis:
    """Results of database index analysis."""

    existing_indexes: Dict[str, List[str]]
    missing_indexes: List[IndexRecommendation]
    redundant_indexes: List[str]
    performance_impact: Dict[str, Any]


class DatabaseIndexOptimizer:
    """
    Analyzes database queries and optimizes indexes for analytics performance.

    Features:
    - Analyze existing indexes
    - Identify missing indexes for common query patterns
    - Generate index creation SQL
    - Monitor index usage and effectiveness
    """

    # Common analytics query patterns and their optimal indexes
    ANALYTICS_INDEX_PATTERNS = {
        "messages_analytics": {
            "table": "messages",
            "indexes": [
                {
                    "columns": ["patient_id", "created_at"],
                    "reason": "Patient message timeline queries",
                    "type": "btree",
                },
                {
                    "columns": ["direction", "created_at"],
                    "reason": "Message direction filtering with date range",
                    "type": "btree",
                },
                {
                    "columns": ["created_at", "direction", "patient_id"],
                    "reason": "Composite index for engagement analytics",
                    "type": "btree",
                },
                {
                    "columns": ["status", "created_at"],
                    "reason": "Message status analytics",
                    "type": "btree",
                },
            ],
        },
        "patients_analytics": {
            "table": "patients",
            "indexes": [
                {
                    "columns": ["doctor_id", "created_at"],
                    "reason": "Doctor patient queries with date filtering",
                    "type": "btree",
                },
                {
                    "columns": ["treatment_type", "created_at"],
                    "reason": "Treatment distribution analytics",
                    "type": "btree",
                },
                {
                    "columns": ["flow_state", "doctor_id"],
                    "reason": "Active patient filtering by doctor",
                    "type": "btree",
                },
                {
                    "columns": ["current_day", "treatment_type"],
                    "reason": "Treatment progress analytics",
                    "type": "btree",
                },
            ],
        },
        "quiz_responses_analytics": {
            "table": "quiz_responses",
            "indexes": [
                {
                    "columns": ["patient_id", "created_at"],
                    "reason": "Patient quiz timeline",
                    "type": "btree",
                },
                {
                    "columns": ["responded_at", "patient_id"],
                    "reason": "Quiz completion analytics",
                    "type": "btree",
                },
                {
                    "columns": ["created_at", "responded_at"],
                    "reason": "Quiz response time analytics",
                    "type": "btree",
                },
            ],
        },
        "alerts_analytics": {
            "table": "alerts",
            "indexes": [
                {
                    "columns": ["patient_id", "created_at"],
                    "reason": "Patient alert timeline",
                    "type": "btree",
                },
                {
                    "columns": ["severity", "status", "created_at"],
                    "reason": "Alert severity and status analytics",
                    "type": "btree",
                },
                {
                    "columns": ["status", "created_at"],
                    "reason": "Alert status filtering with date",
                    "type": "btree",
                },
            ],
        },
    }

    def __init__(self, db: Any):
        """Initialize database index optimizer."""
        self.db = db
        self.engine = db.get_bind()
        self.inspector = inspect(self.engine)

        logger.info("Database Index Optimizer initialized")

    def analyze_indexes(self) -> IndexAnalysis:
        """
        Analyze current database indexes and identify optimization opportunities.

        Returns:
            IndexAnalysis with existing indexes, recommendations, and performance impact
        """
        try:
            logger.info("Starting database index analysis")

            # Get existing indexes
            existing_indexes = self._get_existing_indexes()

            # Identify missing indexes
            missing_indexes = self._identify_missing_indexes(existing_indexes)

            # Find redundant indexes
            redundant_indexes = self._find_redundant_indexes(existing_indexes)

            # Analyze performance impact
            performance_impact = self._analyze_performance_impact()

            analysis = IndexAnalysis(
                existing_indexes=existing_indexes,
                missing_indexes=missing_indexes,
                redundant_indexes=redundant_indexes,
                performance_impact=performance_impact,
            )

            monitoring_logger.log_system_event(
                event_type="database_index_analysis",
                message="Database index analysis completed",
                level="INFO",
                context={
                    "existing_indexes_count": sum(
                        len(indexes) for indexes in existing_indexes.values()
                    ),
                    "missing_indexes_count": len(missing_indexes),
                    "redundant_indexes_count": len(redundant_indexes),
                },
            )

            logger.info("Database index analysis completed")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing indexes: {e}")
            raise

    def create_recommended_indexes(
        self, recommendations: List[IndexRecommendation], dry_run: bool = True
    ) -> List[str]:
        """
        Create recommended indexes.

        Args:
            recommendations: List of index recommendations to implement
            dry_run: If True, only return SQL without executing

        Returns:
            List of SQL statements executed or that would be executed
        """
        try:
            sql_statements = []

            for rec in recommendations:
                # Generate index name
                index_name = self._generate_index_name(rec.table_name, rec.columns)

                # Generate SQL
                sql = self._generate_create_index_sql(
                    index_name, rec.table_name, rec.columns, rec.index_type
                )
                sql_statements.append(sql)

                if not dry_run:
                    try:
                        self.db.execute(text(sql))
                        self.db.commit()

                        monitoring_logger.log_system_event(
                            event_type="database_index_created",
                            message=f"Database index created: {index_name}",
                            level="INFO",
                            context={
                                "index_name": index_name,
                                "table_name": rec.table_name,
                                "columns": rec.columns,
                                "reason": rec.reason,
                            },
                        )

                        logger.info(
                            f"Created index: {index_name} on {rec.table_name}({', '.join(rec.columns)})"
                        )

                    except Exception as e:
                        logger.error(f"Error creating index {index_name}: {e}")
                        self.db.rollback()
                        continue

            return sql_statements

        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            raise

    def get_index_usage_stats(self) -> Dict[str, Any]:
        """
        Get index usage statistics from the database.

        Returns:
            Dictionary with index usage statistics
        """
        try:
            # PostgreSQL specific query for index usage stats
            usage_query = text("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    idx_tup_read,
                    idx_tup_fetch,
                    idx_scan
                FROM pg_stat_user_indexes 
                WHERE schemaname = 'public'
                ORDER BY idx_scan DESC;
            """)

            result = self.db.execute(usage_query)
            usage_stats = []

            for row in result:
                usage_stats.append(
                    {
                        "schema": row.schemaname,
                        "table": row.tablename,
                        "index": row.indexname,
                        "tuples_read": row.idx_tup_read,
                        "tuples_fetched": row.idx_tup_fetch,
                        "scans": row.idx_scan,
                    }
                )

            return {
                "usage_stats": usage_stats,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting index usage stats: {e}")
            return {}

    def analyze_slow_queries_for_indexes(
        self, slow_queries: List[str]
    ) -> List[IndexRecommendation]:
        """
        Analyze slow queries and recommend indexes.

        Args:
            slow_queries: List of slow query strings

        Returns:
            List of index recommendations based on slow queries
        """
        try:
            recommendations = []

            for query in slow_queries:
                query_recommendations = self._analyze_query_for_indexes(query)
                recommendations.extend(query_recommendations)

            # Deduplicate recommendations
            unique_recommendations = self._deduplicate_recommendations(recommendations)

            return unique_recommendations

        except Exception as e:
            logger.error(f"Error analyzing slow queries for indexes: {e}")
            return []

    def _get_existing_indexes(self) -> Dict[str, List[str]]:
        """Get existing indexes for all tables."""
        existing_indexes = {}

        try:
            # Get all table names
            tables = self.inspector.get_table_names()

            for table in tables:
                indexes = self.inspector.get_indexes(table)
                index_info = []

                for index in indexes:
                    index_info.append(
                        {
                            "name": index["name"],
                            "columns": index["column_names"],
                            "unique": index.get("unique", False),
                        }
                    )

                existing_indexes[table] = index_info

            return existing_indexes

        except Exception as e:
            logger.error(f"Error getting existing indexes: {e}")
            return {}

    def _identify_missing_indexes(
        self, existing_indexes: Dict[str, List[str]]
    ) -> List[IndexRecommendation]:
        """Identify missing indexes based on analytics patterns."""
        missing_indexes = []

        for pattern_name, pattern_config in self.ANALYTICS_INDEX_PATTERNS.items():
            table_name = pattern_config["table"]

            # Check if table exists
            if table_name not in existing_indexes:
                continue

            existing_table_indexes = existing_indexes[table_name]

            for index_config in pattern_config["indexes"]:
                columns = index_config["columns"]

                # Check if this index already exists
                if not self._index_exists(existing_table_indexes, columns):
                    recommendation = IndexRecommendation(
                        table_name=table_name,
                        columns=columns,
                        index_type=index_config["type"],
                        reason=index_config["reason"],
                        estimated_benefit="high",  # Analytics indexes are typically high benefit
                        query_patterns=[pattern_name],
                    )
                    missing_indexes.append(recommendation)

        return missing_indexes

    def _find_redundant_indexes(
        self, existing_indexes: Dict[str, List[str]]
    ) -> List[str]:
        """Find potentially redundant indexes."""
        redundant_indexes = []

        for table_name, indexes in existing_indexes.items():
            # Look for indexes that are prefixes of other indexes
            for i, index1 in enumerate(indexes):
                for j, index2 in enumerate(indexes):
                    if i != j and self._is_redundant_index(index1, index2):
                        redundant_indexes.append(f"{table_name}.{index1['name']}")

        return redundant_indexes

    def _analyze_performance_impact(self) -> Dict[str, Any]:
        """Analyze potential performance impact of missing indexes."""
        try:
            # Get table sizes
            size_query = text("""
                SELECT 
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
            """)

            result = self.db.execute(size_query)
            table_sizes = {}

            for row in result:
                table_sizes[row.tablename] = {
                    "size_pretty": row.size,
                    "size_bytes": row.size_bytes,
                }

            return {
                "table_sizes": table_sizes,
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Error analyzing performance impact: {e}")
            return {}

    def _index_exists(self, existing_indexes: List[Dict], columns: List[str]) -> bool:
        """Check if an index with the given columns already exists."""
        for index in existing_indexes:
            if index["columns"] == columns:
                return True
            # Also check if there's a more comprehensive index that covers these columns
            if (
                len(index["columns"]) > len(columns)
                and index["columns"][: len(columns)] == columns
            ):
                return True
        return False

    def _is_redundant_index(self, index1: Dict, index2: Dict) -> bool:
        """Check if index1 is redundant given index2."""
        cols1 = index1["columns"]
        cols2 = index2["columns"]

        # If index1 is a prefix of index2, it might be redundant
        if len(cols1) < len(cols2) and cols2[: len(cols1)] == cols1:
            return True

        return False

    def _generate_index_name(self, table_name: str, columns: List[str]) -> str:
        """Generate a consistent index name."""
        # Remove 's' from table name if it ends with 's' for brevity
        table_short = table_name.rstrip("s") if table_name.endswith("s") else table_name

        # Take first 3 characters of each column
        col_short = "_".join(col[:3] for col in columns)

        return f"idx_{table_short}_{col_short}"

    def _generate_create_index_sql(
        self, index_name: str, table_name: str, columns: List[str], index_type: str
    ) -> str:
        """Generate CREATE INDEX SQL statement."""
        columns_str = ", ".join(columns)

        if index_type == "btree":
            return f"CREATE INDEX {index_name} ON {table_name} ({columns_str});"
        else:
            return f"CREATE INDEX {index_name} ON {table_name} USING {index_type} ({columns_str});"

    def _analyze_query_for_indexes(self, query: str) -> List[IndexRecommendation]:
        """Analyze a single query and recommend indexes."""
        recommendations = []
        query_lower = query.lower()

        # Simple heuristics for index recommendations
        # In a production system, this would use query plan analysis

        # Look for WHERE clauses
        if "where" in query_lower:
            # Extract table and column patterns (simplified)
            if "messages" in query_lower and "created_at" in query_lower:
                recommendations.append(
                    IndexRecommendation(
                        table_name="messages",
                        columns=["created_at"],
                        index_type="btree",
                        reason="Date filtering in WHERE clause",
                        estimated_benefit="medium",
                        query_patterns=[query[:50] + "..."],
                    )
                )

        # Look for JOIN patterns
        if "join" in query_lower:
            if "patient" in query_lower and "message" in query_lower:
                recommendations.append(
                    IndexRecommendation(
                        table_name="messages",
                        columns=["patient_id"],
                        index_type="btree",
                        reason="JOIN with patients table",
                        estimated_benefit="high",
                        query_patterns=[query[:50] + "..."],
                    )
                )

        return recommendations

    def _deduplicate_recommendations(
        self, recommendations: List[IndexRecommendation]
    ) -> List[IndexRecommendation]:
        """Remove duplicate recommendations."""
        seen = set()
        unique_recommendations = []

        for rec in recommendations:
            key = (rec.table_name, tuple(rec.columns))
            if key not in seen:
                seen.add(key)
                unique_recommendations.append(rec)

        return unique_recommendations
