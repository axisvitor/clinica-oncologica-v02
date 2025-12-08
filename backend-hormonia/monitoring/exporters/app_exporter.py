"""
Custom Prometheus Exporter for Clínica Hormonia
Exports 20+ application-specific metrics for monitoring
"""

import os
import time
from typing import Dict, List
from prometheus_client import start_http_server, Gauge, Counter, Histogram, Info
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily
import psycopg2
from redis import Redis
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Application Metrics
app_requests_total = Counter(
    'app_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

app_request_duration_seconds = Histogram(
    'app_request_duration_seconds',
    'HTTP request latency in seconds',
    ['endpoint'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
)

app_active_users_total = Gauge(
    'app_active_users_total',
    'Number of currently active users'
)

app_patient_onboarding_total = Counter(
    'app_patient_onboarding_total',
    'Total patient onboarding attempts',
    ['status']  # success, failed, pending
)

app_quiz_completion_rate = Gauge(
    'app_quiz_completion_rate',
    'Quiz completion rate (0-1)'
)

app_upload_bytes_total = Counter(
    'app_upload_bytes_total',
    'Total bytes uploaded',
    ['user_tier']  # free, pro, enterprise
)

# Security Metrics
app_security_scan_total = Counter(
    'app_security_scan_total',
    'Total security scans performed',
    ['scanner', 'result']  # clamav/mime, pass/fail
)

app_virus_detected_total = Counter(
    'app_virus_detected_total',
    'Total viruses detected in uploads'
)

app_mime_validation_failures_total = Counter(
    'app_mime_validation_failures_total',
    'Total MIME type validation failures'
)

app_blocked_extensions_total = Counter(
    'app_blocked_extensions_total',
    'Files blocked by extension',
    ['extension']
)

# Performance Metrics
app_db_query_duration_seconds = Histogram(
    'app_db_query_duration_seconds',
    'Database query duration in seconds',
    ['query'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0]
)

app_redis_operations_total = Counter(
    'app_redis_operations_total',
    'Total Redis operations',
    ['operation']  # get, set, delete, expire
)

app_celery_task_duration_seconds = Histogram(
    'app_celery_task_duration_seconds',
    'Celery task duration in seconds',
    ['task'],
    buckets=[1, 5, 10, 30, 60, 300, 600]
)

app_celery_queue_size = Gauge(
    'app_celery_queue_size',
    'Number of tasks in Celery queue',
    ['queue']
)

# Business Metrics
app_revenue_total = Counter(
    'app_revenue_total',
    'Total revenue in USD',
    ['tier']  # free, pro, enterprise
)

app_quota_usage_bytes = Gauge(
    'app_quota_usage_bytes',
    'Current quota usage in bytes',
    ['user', 'tier']
)

app_quota_limit_bytes = Gauge(
    'app_quota_limit_bytes',
    'Quota limit in bytes',
    ['tier']
)

app_notifications_sent_total = Counter(
    'app_notifications_sent_total',
    'Total notifications sent',
    ['channel']  # email, sms, whatsapp, push
)

app_sla_compliance_ratio = Gauge(
    'app_sla_compliance_ratio',
    'SLA compliance ratio (0-1)'
)

# Additional Metrics
app_quiz_completion_total = Counter(
    'app_quiz_completion_total',
    'Total quiz completions',
    ['status']  # completed, abandoned, timeout
)

app_whatsapp_messages_total = Counter(
    'app_whatsapp_messages_total',
    'Total WhatsApp messages sent',
    ['status']  # sent, delivered, failed
)

app_patient_risk_alerts_total = Counter(
    'app_patient_risk_alerts_total',
    'Patient risk alerts triggered',
    ['risk_level']  # low, medium, high, critical
)

app_api_rate_limit_hits_total = Counter(
    'app_api_rate_limit_hits_total',
    'API rate limit violations',
    ['endpoint', 'user_tier']
)


class HormoniaMetricsCollector:
    """Collects custom metrics from database and cache"""

    def __init__(self):
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_NAME', 'hormonia'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', '')
        }

        self.redis_config = {
            'host': os.getenv('REDIS_HOST', 'localhost'),
            'port': int(os.getenv('REDIS_PORT', 6379)),
            'db': int(os.getenv('REDIS_DB', 0))
        }

    def get_db_connection(self):
        """Get PostgreSQL database connection"""
        try:
            return psycopg2.connect(**self.db_config)
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return None

    def get_redis_connection(self):
        """Get Redis connection"""
        try:
            return Redis(**self.redis_config)
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return None

    def collect_database_metrics(self):
        """Collect metrics from PostgreSQL"""
        conn = self.get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()

            # Active users (last 1 hour)
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id)
                FROM user_activity
                WHERE last_seen > NOW() - INTERVAL '1 hour'
            """)
            active_users = cursor.fetchone()[0]
            app_active_users_total.set(active_users)

            # Quiz completion rate
            cursor.execute("""
                SELECT
                    COALESCE(
                        COUNT(CASE WHEN status = 'completed' THEN 1 END)::float /
                        NULLIF(COUNT(*), 0),
                        0
                    )
                FROM quiz_sessions
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)
            completion_rate = cursor.fetchone()[0]
            app_quiz_completion_rate.set(completion_rate)

            # Patient onboarding stats
            cursor.execute("""
                SELECT status, COUNT(*)
                FROM patient_onboarding
                WHERE created_at > NOW() - INTERVAL '7 days'
                GROUP BY status
            """)
            for status, count in cursor.fetchall():
                # Update counter (simulated increment)
                pass

            # Quota usage by tier
            cursor.execute("""
                SELECT u.tier, u.email, SUM(f.file_size)
                FROM users u
                LEFT JOIN file_uploads f ON u.id = f.user_id
                GROUP BY u.tier, u.email
            """)
            for tier, user, usage in cursor.fetchall():
                app_quota_usage_bytes.labels(user=user, tier=tier).set(usage or 0)

            cursor.close()

        except Exception as e:
            logger.error(f"Error collecting database metrics: {e}")
        finally:
            conn.close()

    def collect_redis_metrics(self):
        """Collect metrics from Redis"""
        redis = self.get_redis_connection()
        if not redis:
            return

        try:
            # Celery queue sizes
            for queue in ['celery', 'quiz_processing', 'notifications', 'ai_analysis']:
                try:
                    queue_size = redis.llen(queue)
                    app_celery_queue_size.labels(queue=queue).set(queue_size)
                except Exception as e:
                    logger.error(f"Error getting queue size for {queue}: {e}")

            # Cache hit rate (from Redis INFO)
            info = redis.info('stats')
            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)

        except Exception as e:
            logger.error(f"Error collecting Redis metrics: {e}")

    def collect_sla_metrics(self):
        """Calculate SLA compliance"""
        conn = self.get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()

            # Calculate uptime percentage (last 24h)
            cursor.execute("""
                SELECT
                    COALESCE(
                        1 - (SUM(downtime_seconds)::float / 86400),
                        1.0
                    )
                FROM system_health_checks
                WHERE checked_at > NOW() - INTERVAL '24 hours'
            """)
            sla_compliance = cursor.fetchone()[0]
            app_sla_compliance_ratio.set(sla_compliance)

            cursor.close()

        except Exception as e:
            logger.error(f"Error calculating SLA metrics: {e}")
        finally:
            conn.close()

    def collect_all_metrics(self):
        """Collect all custom metrics"""
        logger.info("Collecting custom metrics...")

        try:
            self.collect_database_metrics()
            self.collect_redis_metrics()
            self.collect_sla_metrics()
            logger.info("Metrics collection completed")
        except Exception as e:
            logger.error(f"Error in metrics collection: {e}")


def main():
    """Start the metrics exporter"""
    port = int(os.getenv('EXPORTER_PORT', 9100))
    interval = int(os.getenv('COLLECTION_INTERVAL', 60))

    # Start HTTP server to expose metrics
    start_http_server(port)
    logger.info(f"Metrics exporter started on port {port}")

    collector = HormoniaMetricsCollector()

    # Collect metrics periodically
    while True:
        try:
            collector.collect_all_metrics()
            time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Exporter stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(interval)


if __name__ == '__main__':
    main()
