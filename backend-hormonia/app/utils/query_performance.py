"""
FIX #5-6: Query Performance Monitoring and Index Management
Utilities for monitoring database performance and managing indexes.
"""
from typing import Dict, List, Optional, Any, NamedTuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from sqlalchemy import Engine, text, inspect
from sqlalchemy.orm import Session
import logging
import threading
import time
import hashlib
import json
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class QueryMetrics:
    """Query performance metrics."""
    query_hash: str
    query_text: str
    execution_count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    last_executed: Optional[datetime] = None
    parameters: List[Dict] = field(default_factory=list)
    
    def update(self, execution_time: float, params: Optional[Dict] = None):
        """Update metrics with new execution."""
        self.execution_count += 1
        self.total_time += execution_time
        self.min_time = min(self.min_time, execution_time)
        self.max_time = max(self.max_time, execution_time)
        self.avg_time = self.total_time / self.execution_count
        self.last_executed = datetime.utcnow()
        
        if params and len(self.parameters) < 10:  # Keep last 10 parameter sets
            self.parameters.append(params)


@dataclass
class SlowQuery:
    """Slow query record."""
    query_text: str
    execution_time: float
    parameters: Optional[Dict]
    timestamp: datetime
    stack_trace: Optional[str] = None


class QueryPerformanceMonitor:
    """FIX #5-6: Monitor and analyze database query performance."""
    
    def __init__(self, max_queries: int = 1000, max_slow_queries: int = 100):
        self.max_queries = max_queries
        self.max_slow_queries = max_slow_queries
        self.metrics: Dict[str, QueryMetrics] = {}
        self.slow_queries: deque = deque(maxlen=max_slow_queries)
        self.session_metrics = defaultdict(list)
        self.lock = threading.RLock()
        self.session_start_time = None
        
    def start_session(self):
        """Start monitoring a database session."""
        self.session_start_time = time.time()
        
    def end_session(self, session_duration: float):
        """End monitoring a database session."""
        with self.lock:
            self.session_metrics['durations'].append(session_duration)
            self.session_metrics['timestamps'].append(datetime.utcnow())
            
            # Keep only last 1000 sessions
            if len(self.session_metrics['durations']) > 1000:
                self.session_metrics['durations'] = self.session_metrics['durations'][-1000:]
                self.session_metrics['timestamps'] = self.session_metrics['timestamps'][-1000:]
    
    def record_query(self, query: str, execution_time: float, params: Optional[Dict] = None):
        """Record a query execution."""
        query_hash = self._hash_query(query)
        
        with self.lock:
            if query_hash not in self.metrics:
                if len(self.metrics) >= self.max_queries:
                    # Remove least recently used query
                    oldest_hash = min(self.metrics.keys(), 
                                     key=lambda k: self.metrics[k].last_executed or datetime.min)
                    del self.metrics[oldest_hash]
                
                self.metrics[query_hash] = QueryMetrics(
                    query_hash=query_hash,
                    query_text=self._normalize_query(query)
                )
            
            self.metrics[query_hash].update(execution_time, params)
    
    def record_slow_query(self, query: str, execution_time: float, params: Optional[Dict] = None):
        """Record a slow query."""
        slow_query = SlowQuery(
            query_text=self._normalize_query(query),
            execution_time=execution_time,
            parameters=params,
            timestamp=datetime.utcnow()
        )
        
        with self.lock:
            self.slow_queries.append(slow_query)
        
        logger.warning(f"Slow query detected: {execution_time:.2f}s - {query[:100]}...")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        with self.lock:
            # Query statistics
            total_queries = sum(m.execution_count for m in self.metrics.values())
            total_time = sum(m.total_time for m in self.metrics.values())
            
            # Top slow queries
            top_slow = sorted(self.metrics.values(), key=lambda m: m.avg_time, reverse=True)[:10]
            
            # Most frequent queries
            top_frequent = sorted(self.metrics.values(), key=lambda m: m.execution_count, reverse=True)[:10]
            
            # Session statistics
            session_durations = self.session_metrics.get('durations', [])
            avg_session_duration = sum(session_durations) / len(session_durations) if session_durations else 0
            
            # Recent slow queries
            recent_slow = list(self.slow_queries)[-10:]
            
            return {
                'summary': {
                    'total_queries_monitored': len(self.metrics),
                    'total_query_executions': total_queries,
                    'total_execution_time': total_time,
                    'average_query_time': total_time / total_queries if total_queries > 0 else 0,
                    'total_slow_queries': len(self.slow_queries),
                    'average_session_duration': avg_session_duration,
                    'total_sessions': len(session_durations)
                },
                'top_slow_queries': [
                    {
                        'query_hash': q.query_hash,
                        'query_text': q.query_text[:200] + '...' if len(q.query_text) > 200 else q.query_text,
                        'avg_time': q.avg_time,
                        'max_time': q.max_time,
                        'execution_count': q.execution_count
                    }
                    for q in top_slow
                ],
                'most_frequent_queries': [
                    {
                        'query_hash': q.query_hash,
                        'query_text': q.query_text[:200] + '...' if len(q.query_text) > 200 else q.query_text,
                        'execution_count': q.execution_count,
                        'avg_time': q.avg_time,
                        'total_time': q.total_time
                    }
                    for q in top_frequent
                ],
                'recent_slow_queries': [
                    {
                        'query_text': sq.query_text[:200] + '...' if len(sq.query_text) > 200 else sq.query_text,
                        'execution_time': sq.execution_time,
                        'timestamp': sq.timestamp.isoformat()
                    }
                    for sq in recent_slow
                ],
                'generated_at': datetime.utcnow().isoformat()
            }
    
    def get_query_suggestions(self) -> List[Dict[str, Any]]:
        """Get query optimization suggestions."""
        suggestions = []
        
        with self.lock:
            for query_hash, metrics in self.metrics.items():
                if metrics.avg_time > 1.0:  # Slow queries
                    suggestion = {
                        'query_hash': query_hash,
                        'query_text': metrics.query_text[:200],
                        'issue': 'slow_execution',
                        'avg_time': metrics.avg_time,
                        'suggestions': []
                    }
                    
                    # Analyze query for common issues
                    query_lower = metrics.query_text.lower()
                    
                    if 'select *' in query_lower:
                        suggestion['suggestions'].append('Avoid SELECT * - specify only needed columns')
                    
                    if 'order by' in query_lower and 'limit' not in query_lower:
                        suggestion['suggestions'].append('Add LIMIT to ORDER BY queries')
                    
                    if 'join' in query_lower and 'where' not in query_lower:
                        suggestion['suggestions'].append('Add WHERE clause to filter JOIN results')
                    
                    if 'like' in query_lower and query_lower.count('%') > 1:
                        suggestion['suggestions'].append('Consider full-text search instead of multiple LIKE operations')
                    
                    if 'in (' in query_lower:
                        suggestion['suggestions'].append('Consider using EXISTS or JOIN instead of large IN clauses')
                    
                    suggestions.append(suggestion)
        
        return suggestions
    
    def _hash_query(self, query: str) -> str:
        """Generate hash for query normalization."""
        normalized = self._normalize_query(query)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for comparison."""
        # Remove extra whitespace and normalize
        normalized = ' '.join(query.split())
        
        # Remove parameter values for better grouping
        # This is a simple approach - in production, use a proper SQL parser
        import re
        
        # Replace numeric values
        normalized = re.sub(r'\b\d+\b', '?', normalized)
        
        # Replace string literals
        normalized = re.sub(r"'[^']*'", "'?'", normalized)
        
        # Replace UUID patterns
        normalized = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '?', normalized, flags=re.IGNORECASE)
        
        return normalized


class IndexManager:
    """FIX #5: Manage database indexes for optimal performance."""
    
    def __init__(self, engine: Engine):
        self.engine = engine
        self.recommended_indexes: List[Dict] = []
        self.existing_indexes: Dict[str, List[str]] = {}
        
    def initialize(self):
        """Initialize index manager."""
        try:
            self._scan_existing_indexes()
            self._generate_index_recommendations()
            logger.info("Index manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize index manager: {e}")
    
    def _scan_existing_indexes(self):
        """Scan existing database indexes."""
        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            
            for table in tables:
                indexes = inspector.get_indexes(table)
                self.existing_indexes[table] = [
                    {
                        'name': idx['name'],
                        'columns': idx['column_names'],
                        'unique': idx['unique']
                    }
                    for idx in indexes
                ]
                
            logger.info(f"Scanned indexes for {len(tables)} tables")
            
        except Exception as e:
            logger.error(f"Failed to scan existing indexes: {e}")
    
    def _generate_index_recommendations(self):
        """Generate index recommendations based on common query patterns."""
        self.recommended_indexes = [
            {
                'table': 'patients',
                'columns': ['doctor_id', 'flow_state'],
                'type': 'composite',
                'reason': 'Common doctor dashboard queries'
            },
            {
                'table': 'patients',
                'columns': ['(patient_data->>cpf)', 'flow_state'],
                'type': 'composite_jsonb',
                'reason': 'CPF lookup with flow state filtering'
            },
            {
                'table': 'messages',
                'columns': ['patient_id', 'created_at'],
                'type': 'composite',
                'reason': 'Conversation history queries'
            },
            {
                'table': 'messages',
                'columns': ['status', 'direction'],
                'type': 'composite',
                'reason': 'Message status filtering'
            },
            {
                'table': 'messages',
                'columns': ['scheduled_for'],
                'type': 'partial',
                'condition': "status = 'pending'",
                'reason': 'Scheduled message processing'
            }
        ]
    
    def analyze_missing_indexes(self) -> List[Dict[str, Any]]:
        """Analyze which recommended indexes are missing."""
        missing_indexes = []
        
        for recommendation in self.recommended_indexes:
            table = recommendation['table']
            columns = recommendation['columns']
            
            # Check if similar index exists
            existing = self.existing_indexes.get(table, [])
            
            index_exists = False
            for existing_idx in existing:
                if set(existing_idx['columns']) == set(columns):
                    index_exists = True
                    break
            
            if not index_exists:
                missing_indexes.append({
                    'table': table,
                    'columns': columns,
                    'type': recommendation['type'],
                    'reason': recommendation['reason'],
                    'priority': self._calculate_index_priority(recommendation)
                })
        
        return sorted(missing_indexes, key=lambda x: x['priority'], reverse=True)
    
    def _calculate_index_priority(self, recommendation: Dict) -> int:
        """Calculate priority score for index creation."""
        priority = 0
        
        # High priority tables
        if recommendation['table'] in ['patients', 'messages']:
            priority += 50
        
        # High priority patterns
        if 'composite' in recommendation['type']:
            priority += 30
        
        if 'foreign_key' in recommendation.get('reason', '').lower():
            priority += 20
        
        return priority
    
    def get_index_usage_stats(self) -> Dict[str, Any]:
        """Get index usage statistics from PostgreSQL."""
        try:
            with self.engine.connect() as conn:
                # Query pg_stat_user_indexes for usage statistics
                stats_query = text("""
                    SELECT 
                        schemaname,
                        tablename,
                        indexname,
                        idx_tup_read,
                        idx_tup_fetch,
                        idx_scan
                    FROM pg_stat_user_indexes 
                    ORDER BY idx_scan DESC
                """)
                
                result = conn.execute(stats_query)
                stats = []
                
                for row in result:
                    stats.append({
                        'schema': row.schemaname,
                        'table': row.tablename,
                        'index': row.indexname,
                        'tuples_read': row.idx_tup_read,
                        'tuples_fetched': row.idx_tup_fetch,
                        'scans': row.idx_scan,
                        'efficiency': row.idx_tup_fetch / row.idx_tup_read if row.idx_tup_read > 0 else 0
                    })
                
                return {
                    'total_indexes': len(stats),
                    'unused_indexes': [s for s in stats if s['scans'] == 0],
                    'most_used_indexes': sorted(stats, key=lambda x: x['scans'], reverse=True)[:10],
                    'least_efficient_indexes': sorted([s for s in stats if s['scans'] > 0], 
                                                    key=lambda x: x['efficiency'])[:10]
                }
                
        except Exception as e:
            logger.error(f"Failed to get index usage stats: {e}")
            return {}
    
    def suggest_index_maintenance(self) -> List[Dict[str, Any]]:
        """Suggest index maintenance operations."""
        suggestions = []
        
        try:
            usage_stats = self.get_index_usage_stats()
            
            # Suggest removing unused indexes
            for unused_idx in usage_stats.get('unused_indexes', []):
                if not unused_idx['index'].endswith('_pkey'):  # Don't suggest removing primary keys
                    suggestions.append({
                        'type': 'remove_unused',
                        'index': unused_idx['index'],
                        'table': unused_idx['table'],
                        'reason': 'Index is never used',
                        'priority': 'low'
                    })
            
            # Suggest reindexing for low-efficiency indexes
            for inefficient_idx in usage_stats.get('least_efficient_indexes', []):
                if inefficient_idx['efficiency'] < 0.1:
                    suggestions.append({
                        'type': 'reindex',
                        'index': inefficient_idx['index'],
                        'table': inefficient_idx['table'],
                        'reason': f"Low efficiency: {inefficient_idx['efficiency']:.2%}",
                        'priority': 'medium'
                    })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Failed to generate index maintenance suggestions: {e}")
            return []


@contextmanager
def monitor_query_performance(db_session: Session, operation_name: str = "unknown"):
    """Context manager for monitoring query performance."""
    start_time = time.time()
    query_count_before = len(db_session.get_bind().pool.checkedout())
    
    try:
        yield
    finally:
        end_time = time.time()
        duration = end_time - start_time
        query_count_after = len(db_session.get_bind().pool.checkedout())
        
        logger.info(f"Operation '{operation_name}' completed in {duration:.2f}s, "
                   f"connection pool: {query_count_after - query_count_before} connections used")
        
        if duration > 2.0:  # Log slow operations
            logger.warning(f"Slow operation detected: '{operation_name}' took {duration:.2f}s")
