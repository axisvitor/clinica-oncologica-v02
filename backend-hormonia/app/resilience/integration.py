"""
Resilience Integration Module

Integrates all resilience patterns with the main application.
"""

import os
import logging
from typing import Optional
from flask import Flask

# Import all resilience components
from .circuit_breaker import OpenAICircuitBreaker
from .retry import RetryManager, database_retry, api_retry, openai_retry
from .health import (
    health_checker,
    DatabaseHealthCheck,
    OpenAIHealthCheck,
    DiskSpaceHealthCheck,
    MemoryHealthCheck,
    CPUHealthCheck,
    create_health_blueprint
)
from .rate_limit import create_rate_limit_middleware
from .metrics import metrics_collector, create_metrics_blueprint
from .config import config_manager, ResilienceConfig

logger = logging.getLogger(__name__)


class ResilienceManager:
    """
    Central manager for all resilience patterns

    Features:
    - Unified configuration
    - Component initialization
    - Health monitoring
    - Metrics collection
    - Integration with Flask
    """

    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        self.config: Optional[ResilienceConfig] = None

        # Component instances
        self.circuit_breaker: Optional[OpenAICircuitBreaker] = None
        self.rate_limit_middleware = None

        # Initialization status
        self._initialized = False

        if app:
            self.init_app(app)

    def init_app(self, app: Flask):
        """Initialize resilience patterns with Flask app"""
        self.app = app

        # Load configuration
        environment = app.config.get('ENVIRONMENT', 'development')
        self.config = config_manager.load_config(environment)

        logger.info(f"Initializing resilience patterns for {environment} environment")

        # Initialize components
        self._init_circuit_breakers()
        self._init_health_checks()
        self._init_rate_limiting()
        self._init_metrics()
        self._register_blueprints()

        # Start background services
        if self.config.metrics_enabled:
            metrics_collector.start_collection()

        self._initialized = True
        logger.info("Resilience patterns initialized successfully")

    def _init_circuit_breakers(self):
        """Initialize circuit breakers"""
        if not self.config:
            return

        # OpenAI circuit breaker
        self.circuit_breaker = OpenAICircuitBreaker(
            cache_ttl=1800.0  # 30 minutes cache
        )

        # Register with metrics collector
        metrics_collector.register_circuit_breaker('openai', self.circuit_breaker)

        logger.info("Circuit breakers initialized")

    def _init_health_checks(self):
        """Initialize health checks"""
        if not self.config or not self.config.health_check_enabled:
            return

        # Database health check
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            db_check = DatabaseHealthCheck(
                database_url=database_url,
                timeout=10.0,
                slow_query_threshold=1.0
            )
            health_checker.add_check(db_check)

        # OpenAI health check
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if openai_api_key:
            openai_check = OpenAIHealthCheck(
                api_key=openai_api_key,
                timeout=15.0
            )
            health_checker.add_check(openai_check)

        # System health checks
        disk_check = DiskSpaceHealthCheck(
            path="/",
            warning_threshold=80.0,
            critical_threshold=90.0
        )
        health_checker.add_check(disk_check)

        memory_check = MemoryHealthCheck(
            warning_threshold=80.0,
            critical_threshold=90.0
        )
        health_checker.add_check(memory_check)

        cpu_check = CPUHealthCheck(
            warning_threshold=80.0,
            critical_threshold=95.0,
            interval=1.0
        )
        health_checker.add_check(cpu_check)

        # Configure cache TTL
        health_checker.cache_ttl = self.config.health_check_cache_ttl

        # Register with metrics collector
        metrics_collector.register_health_checker('main', health_checker)

        logger.info("Health checks initialized")

    def _init_rate_limiting(self):
        """Initialize rate limiting"""
        if not self.config:
            return

        # Create rate limiting middleware
        self.rate_limit_middleware = create_rate_limit_middleware(
            app=self.app,
            default_requests_per_second=self.config.rate_limit.requests_per_second,
            default_burst_size=self.config.rate_limit.burst_size,
            enabled=True
        )

        # Register with metrics collector
        metrics_collector.register_rate_limiter('main', self.rate_limit_middleware.global_limiter)

        logger.info("Rate limiting initialized")

    def _init_metrics(self):
        """Initialize metrics collection"""
        if not self.config or not self.config.metrics_enabled:
            return

        # Configure metrics collector
        metrics_collector.retention_period = self.config.metrics_retention_hours * 3600
        metrics_collector.collection_interval = self.config.metrics_collection_interval

        logger.info("Metrics collection initialized")

    def _register_blueprints(self):
        """Register Flask blueprints"""
        if not self.app:
            return

        # Health check endpoints
        if self.config and self.config.health_check_enabled:
            health_bp = create_health_blueprint()
            self.app.register_blueprint(health_bp)

        # Metrics endpoints
        if self.config and self.config.metrics_enabled:
            metrics_bp = create_metrics_blueprint()
            self.app.register_blueprint(metrics_bp)

        logger.info("Flask blueprints registered")

    def get_circuit_breaker(self) -> Optional[OpenAICircuitBreaker]:
        """Get OpenAI circuit breaker instance"""
        return self.circuit_breaker

    def get_health_checker(self):
        """Get health checker instance"""
        return health_checker

    def get_metrics_collector(self):
        """Get metrics collector instance"""
        return metrics_collector

    def get_rate_limiter(self):
        """Get rate limiter middleware"""
        return self.rate_limit_middleware

    def is_healthy(self) -> bool:
        """Quick health check"""
        if not self._initialized:
            return False

        try:
            # Run a quick health check
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(health_checker.check_health())
                summary = result.get('summary', {})
                status = summary.get('status', 'unknown')
                return status in ['healthy', 'degraded']
            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def get_status(self) -> dict:
        """Get comprehensive status"""
        status = {
            'initialized': self._initialized,
            'environment': self.config.environment if self.config else 'unknown',
            'components': {}
        }

        if self._initialized:
            status['components'] = {
                'circuit_breaker': self.circuit_breaker is not None,
                'health_checks': self.config and self.config.health_check_enabled,
                'rate_limiting': self.rate_limit_middleware is not None,
                'metrics': self.config and self.config.metrics_enabled
            }

            # Get metrics if available
            if self.config and self.config.metrics_enabled:
                try:
                    current_metrics = metrics_collector.get_current_metrics()
                    status['metrics'] = current_metrics.to_dict()
                except Exception as e:
                    status['metrics_error'] = str(e)

        return status

    def shutdown(self):
        """Shutdown resilience services"""
        if self.config and self.config.metrics_enabled:
            metrics_collector.stop_collection()

        logger.info("Resilience patterns shut down")


# Global resilience manager instance
resilience_manager = ResilienceManager()


def init_resilience(app: Flask) -> ResilienceManager:
    """
    Initialize resilience patterns for Flask application

    Usage:
        from app.resilience import init_resilience

        app = Flask(__name__)
        resilience = init_resilience(app)
    """
    resilience_manager.init_app(app)
    return resilience_manager


def setup_resilience_decorators():
    """
    Setup common resilience decorators for the application

    Returns decorators that can be used throughout the app:
    - @database_retry: For database operations
    - @api_retry: For external API calls
    - @openai_retry: For OpenAI API calls
    """
    return {
        'database_retry': database_retry,
        'api_retry': api_retry,
        'openai_retry': openai_retry
    }


# Example usage patterns
"""
# In your Flask app initialization:
from app.resilience import init_resilience

app = Flask(__name__)
resilience = init_resilience(app)

# In your route handlers:
from app.resilience.rate_limit import rate_limit, user_rate_limit
from app.resilience.retry import openai_retry

@app.route('/api/generate')
@user_rate_limit(requests_per_second=5.0, burst_size=20)
@openai_retry(max_attempts=3)
def generate_text():
    # Your OpenAI API call here
    pass

# In your service classes:
from app.resilience import resilience_manager

class AIService:
    def __init__(self):
        self.circuit_breaker = resilience_manager.get_circuit_breaker()

    async def generate_response(self, prompt):
        return await self.circuit_breaker.acreate_chat_completion(
            messages=[{"role": "user", "content": prompt}]
        )
"""