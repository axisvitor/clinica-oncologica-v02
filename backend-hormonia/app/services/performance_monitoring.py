"""
Performance monitoring and bottleneck detection service.
Implements comprehensive performance tracking and optimization recommendations.
"""
import logging
import asyncio
from typing import Any, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
import statistics
import json
from collections import defaultdict, deque

# from sqlalchemy.orm import
from sqlalchemy import text
from redis import Redis

from app.repositories.flow import FlowStateRepository
from app.models.flow import PatientFlowState
from app.models.flow_analytics import FlowMessage

logger = logging.getLogger(__name__)


class MetricType(Enum):
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    QUEUE_DEPTH = "queue_depth"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    DATABASE_CONNECTIONS = "database_connections"
    CACHE_HIT_RATE = "cache_hit_rate"


class BottleneckType(Enum):
    DATABASE_SLOW_QUERIES = "database_slow_queries"
    HIGH_MEMORY_USAGE = "high_memory_usage"
    QUEUE_BACKLOG = "queue_backlog"
    EXTERNAL_API_LATENCY = "external_api_latency"
    REDIS_MEMORY_PRESSURE = "redis_memory_pressure"
    CONCURRENT_PROCESSING_LIMIT = "concurrent_processing_limit"


@dataclass
class PerformanceMetric:
    """Performance metric data point."""
    metric_type: MetricType
    value: float
    component: str
    timestamp: datetime
    metadata: dict[str, Any]


@dataclass
class PerformanceBottleneck:
    """Detected performance bottleneck."""
    bottleneck_type: BottleneckType
    severity: str  # low, medium, high, critical
    description: str
    affected_components: List[str]
    recommendations: List[str]
    detected_at: datetime
    metrics: List[PerformanceMetric]


class PerformanceMonitoringService:
    """Service for monitoring system performance and detecting bottlenecks."""
    
    def __init__(self, db: Any, redis: Redis, flow_repository: FlowStateRepository):
        self.db = db
        self.redis = redis
        self.flow_repository = flow_repository
        
        # Performance thresholds
        self.thresholds = {
            'response_time_warning': 2.0,  # seconds
            'response_time_critical': 5.0,  # seconds
            'throughput_warning': 10,  # messages per minute
            'throughput_critical': 5,  # messages per minute
            'error_rate_warning': 0.05,  # 5%
            'error_rate_critical': 0.15,  # 15%
            'queue_depth_warning': 50,
            'queue_depth_critical': 200,
            'memory_usage_warning': 0.8,  # 80%
            'memory_usage_critical': 0.95,  # 95%
            'cache_hit_rate_warning': 0.7,  # 70%
            'cache_hit_rate_critical': 0.5,  # 50%
            'db_connections_warning': 80,
            'db_connections_critical': 95
        }
        
        # Metric collection intervals (in seconds)
        self.collection_intervals = {
            MetricType.RESPONSE_TIME: 30,
            MetricType.THROUGHPUT: 60,
            MetricType.ERROR_RATE: 60,
            MetricType.QUEUE_DEPTH: 30,
            MetricType.MEMORY_USAGE: 60,
            MetricType.CACHE_HIT_RATE: 120,
            MetricType.DATABASE_CONNECTIONS: 60
        }
    
    async def collect_performance_metrics(self) -> List[PerformanceMetric]:
        """Collect current performance metrics."""
        metrics = []
        
        try:
            # Response time metrics
            response_time_metrics = await self._collect_response_time_metrics()
            metrics.extend(response_time_metrics)
            
            # Throughput metrics
            throughput_metrics = await self._collect_throughput_metrics()
            metrics.extend(throughput_metrics)
            
            # Error rate metrics
            error_rate_metrics = await self._collect_error_rate_metrics()
            metrics.extend(error_rate_metrics)
            
            # Queue depth metrics
            queue_depth_metrics = await self._collect_queue_depth_metrics()
            metrics.extend(queue_depth_metrics)
            
            # Memory usage metrics
            memory_metrics = await self._collect_memory_usage_metrics()
            metrics.extend(memory_metrics)
            
            # Cache hit rate metrics
            cache_metrics = await self._collect_cache_hit_rate_metrics()
            metrics.extend(cache_metrics)
            
            # Database connection metrics
            db_metrics = await self._collect_database_connection_metrics()
            metrics.extend(db_metrics)
            
            # Store metrics in Redis for trend analysis
            await self._store_metrics(metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
            return []
    
    async def detect_bottlenecks(self) -> List[PerformanceBottleneck]:
        """Detect performance bottlenecks based on current metrics."""
        bottlenecks = []
        
        try:
            # Get recent metrics
            metrics = await self.collect_performance_metrics()
            
            # Analyze database performance
            db_bottlenecks = await self._analyze_database_performance(metrics)
            bottlenecks.extend(db_bottlenecks)
            
            # Analyze memory usage
            memory_bottlenecks = await self._analyze_memory_usage(metrics)
            bottlenecks.extend(memory_bottlenecks)
            
            # Analyze queue performance
            queue_bottlenecks = await self._analyze_queue_performance(metrics)
            bottlenecks.extend(queue_bottlenecks)
            
            # Analyze external API performance
            api_bottlenecks = await self._analyze_external_api_performance()
            bottlenecks.extend(api_bottlenecks)
            
            # Analyze Redis performance
            redis_bottlenecks = await self._analyze_redis_performance(metrics)
            bottlenecks.extend(redis_bottlenecks)
            
            # Analyze concurrent processing limits
            concurrency_bottlenecks = await self._analyze_concurrency_limits(metrics)
            bottlenecks.extend(concurrency_bottlenecks)
            
            return bottlenecks
            
        except Exception as e:
            logger.error(f"Error detecting bottlenecks: {e}")
            return []
    
    async def get_performance_report(self, time_range: timedelta) -> dict[str, Any]:
        """Generate comprehensive performance report."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - time_range
            
            # Get metrics for time range
            metrics = await self._get_metrics_for_range(start_time, end_time)
            
            # Calculate statistics
            stats = await self._calculate_performance_statistics(metrics)
            
            # Get bottlenecks
            bottlenecks = await self.detect_bottlenecks()
            
            # Get trends
            trends = await self._calculate_performance_trends(metrics)
            
            # Generate recommendations
            recommendations = await self._generate_performance_recommendations(stats, bottlenecks)
            
            return {
                'report_generated_at': datetime.utcnow().isoformat(),
                'time_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat(),
                    'duration_hours': time_range.total_seconds() / 3600
                },
                'statistics': stats,
                'bottlenecks': [
                    {
                        'type': b.bottleneck_type.value,
                        'severity': b.severity,
                        'description': b.description,
                        'affected_components': b.affected_components,
                        'recommendations': b.recommendations,
                        'detected_at': b.detected_at.isoformat()
                    }
                    for b in bottlenecks
                ],
                'trends': trends,
                'recommendations': recommendations,
                'health_score': await self._calculate_health_score(stats)
            }
            
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return {'error': str(e)}
    
    async def get_real_time_performance_dashboard(self) -> dict[str, Any]:
        """Get real-time performance dashboard data."""
        try:
            # Get current metrics
            current_metrics = await self.collect_performance_metrics()
            
            # Get recent trends (last hour)
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent_metrics = await self._get_metrics_for_range(one_hour_ago, datetime.utcnow())
            
            # Calculate dashboard data
            dashboard_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'current_metrics': {
                    metric.metric_type.value: {
                        'value': metric.value,
                        'component': metric.component,
                        'status': self._get_metric_status(metric),
                        'metadata': metric.metadata
                    }
                    for metric in current_metrics
                },
                'trends': await self._calculate_short_term_trends(recent_metrics),
                'active_bottlenecks': len(await self.detect_bottlenecks()),
                'system_health': await self._get_system_health_summary(),
                'alerts': await self._get_performance_alerts()
            }
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error getting performance dashboard: {e}")
            return {'error': str(e)}
    
    async def _collect_response_time_metrics(self) -> List[PerformanceMetric]:
        """Collect response time metrics."""
        metrics = []
        
        try:
            # Get recent response times from Redis
            response_times = await self.redis.lrange("response_times", 0, 99)
            
            if response_times:
                times = [float(t) for t in response_times]
                avg_response_time = statistics.mean(times)
                p95_response_time = statistics.quantiles(times, n=20)[18] if len(times) > 1 else times[0]
                
                metrics.append(PerformanceMetric(
                    metric_type=MetricType.RESPONSE_TIME,
                    value=avg_response_time,
                    component="api",
                    timestamp=datetime.utcnow(),
                    metadata={
                        'p95': p95_response_time,
                        'sample_count': len(times),
                        'min': min(times),
                        'max': max(times)
                    }
                ))
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting response time metrics: {e}")
            return []
    
    async def _collect_throughput_metrics(self) -> List[PerformanceMetric]:
        """Collect throughput metrics."""
        metrics = []
        
        try:
            # Get message count from last minute
            one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
            
            message_count = self.db.query(FlowMessage).filter(
                FlowMessage.sent_at >= one_minute_ago
            ).count()
            
            metrics.append(PerformanceMetric(
                metric_type=MetricType.THROUGHPUT,
                value=float(message_count),
                component="flow_processing",
                timestamp=datetime.utcnow(),
                metadata={
                    'messages_per_minute': message_count,
                    'time_window': '1_minute'
                }
            ))
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting throughput metrics: {e}")
            return []
    
    async def _collect_error_rate_metrics(self) -> List[PerformanceMetric]:
        """Collect error rate metrics."""
        metrics = []
        
        try:
            # Get error count from Redis
            error_count = await self.redis.llen("flow_errors")
            total_operations = await self.redis.get("total_operations")
            total_operations = int(total_operations) if total_operations else 1
            
            error_rate = error_count / max(total_operations, 1)
            
            metrics.append(PerformanceMetric(
                metric_type=MetricType.ERROR_RATE,
                value=error_rate,
                component="flow_processing",
                timestamp=datetime.utcnow(),
                metadata={
                    'error_count': error_count,
                    'total_operations': total_operations
                }
            ))
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting error rate metrics: {e}")
            return []
    
    async def _collect_queue_depth_metrics(self) -> List[PerformanceMetric]:
        """Collect queue depth metrics."""
        metrics = []
        
        try:
            # This would integrate with your actual queue system (Celery, etc.)
            # For now, return a placeholder
            queue_depth = 0
            
            metrics.append(PerformanceMetric(
                metric_type=MetricType.QUEUE_DEPTH,
                value=float(queue_depth),
                component="message_queue",
                timestamp=datetime.utcnow(),
                metadata={'queue_name': 'flow_processing'}
            ))
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting queue depth metrics: {e}")
            return []
    
    async def _collect_memory_usage_metrics(self) -> List[PerformanceMetric]:
        """Collect memory usage metrics."""
        metrics = []
        
        try:
            # Redis memory usage
            redis_info = await self.redis.info('memory')
            used_memory = redis_info.get('used_memory', 0)
            max_memory = redis_info.get('maxmemory', 0)
            
            if max_memory > 0:
                memory_usage = used_memory / max_memory
                
                metrics.append(PerformanceMetric(
                    metric_type=MetricType.MEMORY_USAGE,
                    value=memory_usage,
                    component="redis",
                    timestamp=datetime.utcnow(),
                    metadata={
                        'used_memory_mb': used_memory / (1024 * 1024),
                        'max_memory_mb': max_memory / (1024 * 1024)
                    }
                ))
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting memory usage metrics: {e}")
            return []
    
    async def _collect_cache_hit_rate_metrics(self) -> List[PerformanceMetric]:
        """Collect cache hit rate metrics."""
        metrics = []
        
        try:
            # Get cache statistics from Redis
            cache_hits = await self.redis.get("cache_hits") or 0
            cache_misses = await self.redis.get("cache_misses") or 0
            
            total_requests = int(cache_hits) + int(cache_misses)
            hit_rate = int(cache_hits) / max(total_requests, 1)
            
            metrics.append(PerformanceMetric(
                metric_type=MetricType.CACHE_HIT_RATE,
                value=hit_rate,
                component="redis",
                timestamp=datetime.utcnow(),
                metadata={
                    'cache_hits': int(cache_hits),
                    'cache_misses': int(cache_misses),
                    'total_requests': total_requests
                }
            ))
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting cache hit rate metrics: {e}")
            return []
    
    async def _collect_database_connection_metrics(self) -> List[PerformanceMetric]:
        """Collect database connection metrics."""
        metrics = []
        
        try:
            # Get database connection count
            result = self.db.execute(text("SELECT count(*) FROM pg_stat_activity"))
            connection_count = result.scalar()
            
            metrics.append(PerformanceMetric(
                metric_type=MetricType.DATABASE_CONNECTIONS,
                value=float(connection_count),
                component="database",
                timestamp=datetime.utcnow(),
                metadata={'active_connections': connection_count}
            ))
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting database connection metrics: {e}")
            return []
    
    async def _store_metrics(self, metrics: List[PerformanceMetric]) -> None:
        """Store metrics in Redis for trend analysis."""
        try:
            for metric in metrics:
                key = f"metrics:{metric.component}:{metric.metric_type.value}"
                
                metric_data = {
                    'value': metric.value,
                    'timestamp': metric.timestamp.isoformat(),
                    'metadata': metric.metadata
                }
                
                # Store in time series (keep last 1000 data points)
                await self.redis.lpush(key, json.dumps(metric_data))
                await self.redis.ltrim(key, 0, 999)
                await self.redis.expire(key, 86400 * 7)  # Keep for 7 days
                
        except Exception as e:
            logger.error(f"Error storing metrics: {e}")
    
    async def _get_metrics_for_range(self, start_time: datetime, end_time: datetime) -> List[PerformanceMetric]:
        """Get metrics for a specific time range."""
        metrics = []
        
        try:
            # Get all metric keys
            metric_keys = await self.redis.keys("metrics:*")
            
            for key in metric_keys:
                # Parse key to get component and metric type
                parts = key.decode().split(':')
                if len(parts) >= 3:
                    component = parts[1]
                    metric_type_str = parts[2]
                    
                    try:
                        metric_type = MetricType(metric_type_str)
                    except ValueError:
                        continue
                    
                    # Get metric data
                    metric_data_list = await self.redis.lrange(key, 0, -1)
                    
                    for data_str in metric_data_list:
                        try:
                            data = json.loads(data_str)
                            timestamp = datetime.fromisoformat(data['timestamp'])
                            
                            if start_time <= timestamp <= end_time:
                                metrics.append(PerformanceMetric(
                                    metric_type=metric_type,
                                    value=data['value'],
                                    component=component,
                                    timestamp=timestamp,
                                    metadata=data.get('metadata', {})
                                ))
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            
            return sorted(metrics, key=lambda x: x.timestamp)
            
        except Exception as e:
            logger.error(f"Error getting metrics for range: {e}")
            return []
    
    async def _analyze_database_performance(self, metrics: List[PerformanceMetric]) -> List[PerformanceBottleneck]:
        """Analyze database performance for bottlenecks."""
        bottlenecks = []
        
        try:
            # Check for slow queries
            db_metrics = [m for m in metrics if m.component == "database"]
            
            for metric in db_metrics:
                if metric.metric_type == MetricType.RESPONSE_TIME:
                    if metric.value > self.thresholds['response_time_critical']:
                        bottlenecks.append(PerformanceBottleneck(
                            bottleneck_type=BottleneckType.DATABASE_SLOW_QUERIES,
                            severity="critical",
                            description=f"Database response time is {metric.value:.2f}s, exceeding critical threshold",
                            affected_components=["database", "api"],
                            recommendations=[
                                "Review and optimize slow queries",
                                "Add database indexes for frequently queried columns",
                                "Consider database connection pooling optimization",
                                "Review database configuration parameters"
                            ],
                            detected_at=datetime.utcnow(),
                            metrics=[metric]
                        ))
            
            return bottlenecks
            
        except Exception as e:
            logger.error(f"Error analyzing database performance: {e}")
            return []
    
    async def _analyze_memory_usage(self, metrics: List[PerformanceMetric]) -> List[PerformanceBottleneck]:
        """Analyze memory usage for bottlenecks."""
        bottlenecks = []
        
        try:
            memory_metrics = [m for m in metrics if m.metric_type == MetricType.MEMORY_USAGE]
            
            for metric in memory_metrics:
                if metric.value > self.thresholds['memory_usage_critical']:
                    bottlenecks.append(PerformanceBottleneck(
                        bottleneck_type=BottleneckType.HIGH_MEMORY_USAGE,
                        severity="critical",
                        description=f"Memory usage is {metric.value:.1%}, exceeding critical threshold",
                        affected_components=[metric.component],
                        recommendations=[
                            "Review memory-intensive operations",
                            "Implement memory cleanup routines",
                            "Consider increasing available memory",
                            "Optimize data structures and caching strategies"
                        ],
                        detected_at=datetime.utcnow(),
                        metrics=[metric]
                    ))
            
            return bottlenecks
            
        except Exception as e:
            logger.error(f"Error analyzing memory usage: {e}")
            return []
    
    async def _analyze_queue_performance(self, metrics: List[PerformanceMetric]) -> List[PerformanceBottleneck]:
        """Analyze queue performance for bottlenecks."""
        bottlenecks = []
        
        try:
            queue_metrics = [m for m in metrics if m.metric_type == MetricType.QUEUE_DEPTH]
            
            for metric in queue_metrics:
                if metric.value > self.thresholds['queue_depth_critical']:
                    bottlenecks.append(PerformanceBottleneck(
                        bottleneck_type=BottleneckType.QUEUE_BACKLOG,
                        severity="critical",
                        description=f"Queue depth is {metric.value}, indicating processing backlog",
                        affected_components=["message_queue", "flow_processing"],
                        recommendations=[
                            "Increase worker processes",
                            "Optimize message processing logic",
                            "Review queue configuration",
                            "Consider horizontal scaling"
                        ],
                        detected_at=datetime.utcnow(),
                        metrics=[metric]
                    ))
            
            return bottlenecks
            
        except Exception as e:
            logger.error(f"Error analyzing queue performance: {e}")
            return []
    
    async def _analyze_external_api_performance(self) -> List[PerformanceBottleneck]:
        """Analyze external API performance."""
        bottlenecks = []
        
        try:
            # Check external API response times from Redis
            api_response_times = await self.redis.lrange("external_api_times", 0, 99)
            
            if api_response_times:
                times = [float(t) for t in api_response_times]
                avg_time = statistics.mean(times)
                
                if avg_time > 10.0:  # 10 seconds threshold
                    bottlenecks.append(PerformanceBottleneck(
                        bottleneck_type=BottleneckType.EXTERNAL_API_LATENCY,
                        severity="high",
                        description=f"External API average response time is {avg_time:.2f}s",
                        affected_components=["external_apis", "flow_processing"],
                        recommendations=[
                            "Implement API response caching",
                            "Add timeout and retry logic",
                            "Consider API rate limiting",
                            "Monitor external service status"
                        ],
                        detected_at=datetime.utcnow(),
                        metrics=[]
                    ))
            
            return bottlenecks
            
        except Exception as e:
            logger.error(f"Error analyzing external API performance: {e}")
            return []
    
    async def _analyze_redis_performance(self, metrics: List[PerformanceMetric]) -> List[PerformanceBottleneck]:
        """Analyze Redis performance for bottlenecks."""
        bottlenecks = []
        
        try:
            redis_metrics = [m for m in metrics if m.component == "redis"]
            
            for metric in redis_metrics:
                if metric.metric_type == MetricType.MEMORY_USAGE and metric.value > 0.9:
                    bottlenecks.append(PerformanceBottleneck(
                        bottleneck_type=BottleneckType.REDIS_MEMORY_PRESSURE,
                        severity="high",
                        description=f"Redis memory usage is {metric.value:.1%}",
                        affected_components=["redis", "caching"],
                        recommendations=[
                            "Review Redis memory configuration",
                            "Implement key expiration policies",
                            "Consider Redis clustering",
                            "Optimize data structures"
                        ],
                        detected_at=datetime.utcnow(),
                        metrics=[metric]
                    ))
            
            return bottlenecks
            
        except Exception as e:
            logger.error(f"Error analyzing Redis performance: {e}")
            return []
    
    async def _analyze_concurrency_limits(self, metrics: List[PerformanceMetric]) -> List[PerformanceBottleneck]:
        """Analyze concurrent processing limits."""
        bottlenecks = []
        
        try:
            # Check if we're hitting concurrency limits
            throughput_metrics = [m for m in metrics if m.metric_type == MetricType.THROUGHPUT]
            
            for metric in throughput_metrics:
                if metric.value < self.thresholds['throughput_critical']:
                    bottlenecks.append(PerformanceBottleneck(
                        bottleneck_type=BottleneckType.CONCURRENT_PROCESSING_LIMIT,
                        severity="medium",
                        description=f"Throughput is {metric.value} messages/minute, below expected levels",
                        affected_components=["flow_processing"],
                        recommendations=[
                            "Increase concurrent worker processes",
                            "Optimize processing algorithms",
                            "Review resource allocation",
                            "Consider async processing patterns"
                        ],
                        detected_at=datetime.utcnow(),
                        metrics=[metric]
                    ))
            
            return bottlenecks
            
        except Exception as e:
            logger.error(f"Error analyzing concurrency limits: {e}")
            return []
    
    async def _calculate_performance_statistics(self, metrics: List[PerformanceMetric]) -> dict[str, Any]:
        """Calculate performance statistics from metrics."""
        stats = {}
        
        try:
            # Group metrics by type
            metrics_by_type = defaultdict(list)
            for metric in metrics:
                metrics_by_type[metric.metric_type].append(metric.value)
            
            # Calculate statistics for each metric type
            for metric_type, values in metrics_by_type.items():
                if values:
                    stats[metric_type.value] = {
                        'mean': statistics.mean(values),
                        'median': statistics.median(values),
                        'min': min(values),
                        'max': max(values),
                        'std_dev': statistics.stdev(values) if len(values) > 1 else 0,
                        'count': len(values)
                    }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating performance statistics: {e}")
            return {}
    
    async def _calculate_performance_trends(self, metrics: List[PerformanceMetric]) -> dict[str, Any]:
        """Calculate performance trends."""
        trends = {}
        
        try:
            # Group metrics by type and calculate trends
            metrics_by_type = defaultdict(list)
            for metric in metrics:
                metrics_by_type[metric.metric_type].append((metric.timestamp, metric.value))
            
            for metric_type, time_values in metrics_by_type.items():
                if len(time_values) > 1:
                    # Sort by timestamp
                    time_values.sort(key=lambda x: x[0])
                    
                    # Calculate trend (simple linear regression slope)
                    values = [v for _, v in time_values]
                    n = len(values)
                    
                    if n > 1:
                        x_mean = (n - 1) / 2
                        y_mean = statistics.mean(values)
                        
                        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
                        denominator = sum((i - x_mean) ** 2 for i in range(n))
                        
                        slope = numerator / denominator if denominator != 0 else 0
                        
                        trends[metric_type.value] = {
                            'slope': slope,
                            'direction': 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'stable',
                            'recent_value': values[-1],
                            'previous_value': values[0],
                            'change_percent': ((values[-1] - values[0]) / values[0] * 100) if values[0] != 0 else 0
                        }
            
            return trends
            
        except Exception as e:
            logger.error(f"Error calculating performance trends: {e}")
            return {}
    
    async def _generate_performance_recommendations(self, stats: dict[str, Any], bottlenecks: List[PerformanceBottleneck]) -> List[str]:
        """Generate performance optimization recommendations."""
        recommendations = []
        
        try:
            # General recommendations based on statistics
            if 'response_time' in stats:
                avg_response_time = stats['response_time']['mean']
                if avg_response_time > self.thresholds['response_time_warning']:
                    recommendations.append("Consider implementing response caching to reduce average response times")
            
            if 'error_rate' in stats:
                error_rate = stats['error_rate']['mean']
                if error_rate > self.thresholds['error_rate_warning']:
                    recommendations.append("Implement better error handling and retry mechanisms")
            
            # Recommendations from bottlenecks
            for bottleneck in bottlenecks:
                recommendations.extend(bottleneck.recommendations)
            
            # Remove duplicates
            recommendations = list(set(recommendations))
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return []
    
    async def _calculate_health_score(self, stats: dict[str, Any]) -> float:
        """Calculate overall system health score (0-100)."""
        try:
            score = 100.0
            
            # Deduct points based on performance metrics
            if 'response_time' in stats:
                avg_response_time = stats['response_time']['mean']
                if avg_response_time > self.thresholds['response_time_critical']:
                    score -= 30
                elif avg_response_time > self.thresholds['response_time_warning']:
                    score -= 15
            
            if 'error_rate' in stats:
                error_rate = stats['error_rate']['mean']
                if error_rate > self.thresholds['error_rate_critical']:
                    score -= 25
                elif error_rate > self.thresholds['error_rate_warning']:
                    score -= 10
            
            if 'memory_usage' in stats:
                memory_usage = stats['memory_usage']['mean']
                if memory_usage > self.thresholds['memory_usage_critical']:
                    score -= 20
                elif memory_usage > self.thresholds['memory_usage_warning']:
                    score -= 10
            
            return max(0.0, score)
            
        except Exception as e:
            logger.error(f"Error calculating health score: {e}")
            return 50.0  # Default moderate score
    
    async def _calculate_short_term_trends(self, metrics: List[PerformanceMetric]) -> dict[str, Any]:
        """Calculate short-term trends for dashboard."""
        return await self._calculate_performance_trends(metrics)
    
    async def _get_system_health_summary(self) -> dict[str, Any]:
        """Get system health summary."""
        try:
            bottlenecks = await self.detect_bottlenecks()
            critical_bottlenecks = [b for b in bottlenecks if b.severity == "critical"]
            
            return {
                'status': 'critical' if critical_bottlenecks else 'healthy',
                'bottleneck_count': len(bottlenecks),
                'critical_issues': len(critical_bottlenecks)
            }
            
        except Exception as e:
            logger.error(f"Error getting system health summary: {e}")
            return {'status': 'unknown', 'error': str(e)}
    
    async def _get_performance_alerts(self) -> List[dict[str, Any]]:
        """Get current performance alerts."""
        alerts = []
        
        try:
            bottlenecks = await self.detect_bottlenecks()
            
            for bottleneck in bottlenecks:
                if bottleneck.severity in ['high', 'critical']:
                    alerts.append({
                        'type': bottleneck.bottleneck_type.value,
                        'severity': bottleneck.severity,
                        'description': bottleneck.description,
                        'detected_at': bottleneck.detected_at.isoformat()
                    })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting performance alerts: {e}")
            return []
    
    def _get_metric_status(self, metric: PerformanceMetric) -> str:
        """Get status of a metric based on thresholds."""
        try:
            if metric.metric_type == MetricType.RESPONSE_TIME:
                if metric.value > self.thresholds['response_time_critical']:
                    return 'critical'
                elif metric.value > self.thresholds['response_time_warning']:
                    return 'warning'
            elif metric.metric_type == MetricType.ERROR_RATE:
                if metric.value > self.thresholds['error_rate_critical']:
                    return 'critical'
                elif metric.value > self.thresholds['error_rate_warning']:
                    return 'warning'
            elif metric.metric_type == MetricType.MEMORY_USAGE:
                if metric.value > self.thresholds['memory_usage_critical']:
                    return 'critical'
                elif metric.value > self.thresholds['memory_usage_warning']:
                    return 'warning'
            
            return 'healthy'
            
        except Exception:
            return 'unknown'
