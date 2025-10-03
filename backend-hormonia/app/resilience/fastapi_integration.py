"""
FastAPI Integration for Resilience Patterns

Adapts the resilience patterns for FastAPI instead of Flask.
"""

import asyncio
import time
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import JSONResponse
import logging

# Import resilience components
from .circuit_breaker import OpenAICircuitBreaker
from .retry import RetryManager, database_retry, api_retry, openai_retry
from .health import (
    health_checker,
    DatabaseHealthCheck,
    OpenAIHealthCheck,
    DiskSpaceHealthCheck,
    MemoryHealthCheck,
    CPUHealthCheck
)
from .rate_limit import RateLimiter, RateLimitConfig, RateLimitStrategy
from .metrics import metrics_collector
from .config import config_manager, ResilienceConfig

logger = logging.getLogger(__name__)


class FastAPIResilienceManager:
    """
    FastAPI-specific resilience manager

    Features:
    - FastAPI middleware integration
    - Dependency injection support
    - Async-first design
    - Compatible with existing patterns
    """

    def __init__(self, app: Optional[FastAPI] = None):
        self.app = app
        self.config: Optional[ResilienceConfig] = None

        # Component instances
        self.circuit_breaker: Optional[OpenAICircuitBreaker] = None
        self.rate_limiter: Optional[RateLimiter] = None

        # Initialization status
        self._initialized = False

        if app:
            self.init_app(app)

    def init_app(self, app: FastAPI):
        """Initialize resilience patterns with FastAPI app"""
        self.app = app

        # Load configuration
        environment = getattr(app.state, 'environment', 'development')
        self.config = config_manager.load_config(environment)

        logger.info(f"Initializing FastAPI resilience patterns for {environment}")

        # Initialize components
        self._init_circuit_breakers()
        self._init_health_checks()
        self._init_rate_limiting()
        self._init_metrics()
        self._register_routes()
        self._register_middleware()

        # Start background services
        if self.config.metrics_enabled:
            metrics_collector.start_collection()

        self._initialized = True
        logger.info("FastAPI resilience patterns initialized successfully")

    def _init_circuit_breakers(self):
        """Initialize circuit breakers"""
        if not self.config:
            return

        # OpenAI circuit breaker
        self.circuit_breaker = OpenAICircuitBreaker(cache_ttl=1800.0)

        # Register with metrics collector
        metrics_collector.register_circuit_breaker('openai', self.circuit_breaker)

        logger.info("Circuit breakers initialized")

    def _init_health_checks(self):
        """Initialize health checks"""
        if not self.config or not self.config.health_check_enabled:
            return

        # Similar to Flask version but adapted for FastAPI
        import os

        # Database health check
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            db_check = DatabaseHealthCheck(
                database_url=database_url,
                timeout=10.0,
                slow_query_threshold=1.0
            )
            health_checker.add_check(db_check)

        # System health checks
        disk_check = DiskSpaceHealthCheck()
        health_checker.add_check(disk_check)

        memory_check = MemoryHealthCheck()
        health_checker.add_check(memory_check)

        cpu_check = CPUHealthCheck()
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

        # Create rate limiter
        self.rate_limiter = RateLimiter(
            config=self.config.rate_limit,
            name="fastapi_main"
        )

        # Register with metrics collector
        metrics_collector.register_rate_limiter('main', self.rate_limiter)

        logger.info("Rate limiting initialized")

    def _init_metrics(self):
        """Initialize metrics collection"""
        if not self.config or not self.config.metrics_enabled:
            return

        # Configure metrics collector
        metrics_collector.retention_period = self.config.metrics_retention_hours * 3600
        metrics_collector.collection_interval = self.config.metrics_collection_interval

        logger.info("Metrics collection initialized")

    def _register_routes(self):
        """Register FastAPI routes"""
        if not self.app:
            return

        # Health check routes
        if self.config and self.config.health_check_enabled:
            self._register_health_routes()

        # Metrics routes
        if self.config and self.config.metrics_enabled:
            self._register_metrics_routes()

        logger.info("FastAPI routes registered")

    def _register_health_routes(self):
        """Register health check routes"""
        @self.app.get("/health")
        async def health_status():
            """Main health endpoint"""
            try:
                result = await health_checker.check_health()

                # Determine status code
                summary = result.get('summary', {})
                status_value = summary.get('status', 'unknown')

                status_code = 200 if status_value in ['healthy', 'degraded'] else 503

                return JSONResponse(content=result, status_code=status_code)

            except Exception as e:
                return JSONResponse(
                    content={
                        'error': f'Health check failed: {str(e)}',
                        'summary': {'status': 'unhealthy', 'health_percentage': 0.0}
                    },
                    status_code=503
                )

        @self.app.get("/health/live")
        async def liveness_probe():
            """Kubernetes liveness probe"""
            return {"status": "alive", "timestamp": time.time()}

        @self.app.get("/health/ready")
        async def readiness_probe():
            """Kubernetes readiness probe"""
            try:
                result = await health_checker.check_health()
                summary = result.get('summary', {})
                status_value = summary.get('status', 'unknown')

                if status_value in ['healthy', 'degraded']:
                    return JSONResponse(
                        content={
                            'status': 'ready',
                            'health_status': status_value,
                            'health_percentage': summary.get('health_percentage', 0.0)
                        },
                        status_code=200
                    )
                else:
                    return JSONResponse(
                        content={
                            'status': 'not_ready',
                            'health_status': status_value,
                            'health_percentage': summary.get('health_percentage', 0.0)
                        },
                        status_code=503
                    )

            except Exception as e:
                return JSONResponse(
                    content={'status': 'not_ready', 'error': str(e)},
                    status_code=503
                )

        @self.app.get("/health/check/{check_name}")
        async def specific_health_check(check_name: str):
            """Specific health check endpoint"""
            try:
                result = await health_checker.check_health(check_name)

                if 'error' in result:
                    return JSONResponse(content=result, status_code=404)

                # Determine status code from check result
                check_result = result.get('checks', {}).get(check_name, {})
                status_value = check_result.get('status', 'unknown')

                status_code = 200 if status_value in ['healthy', 'degraded'] else 503
                return JSONResponse(content=result, status_code=status_code)

            except Exception as e:
                return JSONResponse(
                    content={
                        'error': f'Health check failed: {str(e)}',
                        'check_name': check_name
                    },
                    status_code=503
                )

    def _register_metrics_routes(self):
        """Register metrics routes"""
        @self.app.get("/metrics")
        async def get_current_metrics():
            """Get current resilience metrics"""
            try:
                current_metrics = metrics_collector.get_current_metrics()
                return {"status": "success", "data": current_metrics.to_dict()}
            except Exception as e:
                return JSONResponse(
                    content={"status": "error", "error": str(e)},
                    status_code=500
                )

        @self.app.get("/metrics/history")
        async def get_metrics_history(minutes: Optional[int] = None):
            """Get historical metrics"""
            try:
                history = metrics_collector.get_metrics_history(last_n_minutes=minutes)
                return {
                    "status": "success",
                    "data": {
                        "history": [m.to_dict() for m in history],
                        "count": len(history),
                        "time_range_minutes": minutes
                    }
                }
            except Exception as e:
                return JSONResponse(
                    content={"status": "error", "error": str(e)},
                    status_code=500
                )

        @self.app.get("/metrics/export")
        async def export_metrics(format: str = "json"):
            """Export metrics in various formats"""
            try:
                if format not in ['json', 'prometheus']:
                    return JSONResponse(
                        content={
                            'status': 'error',
                            'error': 'Unsupported format. Use: json, prometheus'
                        },
                        status_code=400
                    )

                exported_data = metrics_collector.export_metrics(format)

                if format == 'prometheus':
                    from fastapi.responses import PlainTextResponse
                    return PlainTextResponse(exported_data)
                else:
                    return {
                        "status": "success",
                        "format": format,
                        "data": exported_data
                    }
            except Exception as e:
                return JSONResponse(
                    content={"status": "error", "error": str(e)},
                    status_code=500
                )

    def _register_middleware(self):
        """Register FastAPI middleware"""
        if not self.app or not self.rate_limiter:
            return

        @self.app.middleware("http")
        async def rate_limit_middleware(request: Request, call_next):
            """Rate limiting middleware"""
            # Record start time for metrics
            start_time = time.time()

            try:
                # Check if route should be bypassed
                if self._should_bypass_route(request.url.path):
                    response = await call_next(request)
                    return response

                # Check rate limit
                result = self.rate_limiter.check_rate_limit()

                if not result.allowed:
                    # Create rate limit response
                    response_data = {
                        'error': 'Rate limit exceeded',
                        'rate_limit': {
                            'limit': result.limit,
                            'remaining': result.remaining,
                            'reset_time': result.reset_time,
                            'retry_after': result.retry_after
                        }
                    }

                    response = JSONResponse(content=response_data, status_code=429)

                    # Add rate limit headers
                    for header, value in result.headers.items():
                        response.headers[header] = value

                    return response

                # Process request
                response = await call_next(request)

                # Add rate limit headers to successful response
                for header, value in result.headers.items():
                    response.headers[header] = value

                # Record response time for metrics
                duration = time.time() - start_time
                metrics_collector.record_response_time(duration)

                return response

            except Exception as e:
                logger.error(f"Rate limit middleware error: {str(e)}")
                # Don't block requests on middleware errors
                response = await call_next(request)
                return response

        logger.info("Rate limiting middleware registered")

    def _should_bypass_route(self, path: str) -> bool:
        """Check if route should bypass rate limiting"""
        bypass_patterns = [
            '/health',
            '/metrics',
            '/docs',
            '/redoc',
            '/openapi.json'
        ]

        for pattern in bypass_patterns:
            if path.startswith(pattern):
                return True

        return False

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
        """Get rate limiter instance"""
        return self.rate_limiter

    async def is_healthy(self) -> bool:
        """Quick health check"""
        if not self._initialized:
            return False

        try:
            result = await health_checker.check_health()
            summary = result.get('summary', {})
            status = summary.get('status', 'unknown')
            return status in ['healthy', 'degraded']

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
                'rate_limiting': self.rate_limiter is not None,
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

        logger.info("FastAPI resilience patterns shut down")


# Global FastAPI resilience manager instance
fastapi_resilience_manager = FastAPIResilienceManager()


def init_resilience(app: FastAPI) -> FastAPIResilienceManager:
    """
    Initialize resilience patterns for FastAPI application

    Usage:
        from app.resilience.fastapi_integration import init_resilience

        app = FastAPI()
        resilience = init_resilience(app)
    """
    fastapi_resilience_manager.init_app(app)
    return fastapi_resilience_manager


# FastAPI dependency injection support
async def get_circuit_breaker() -> OpenAICircuitBreaker:
    """FastAPI dependency for circuit breaker"""
    if not fastapi_resilience_manager.circuit_breaker:
        raise HTTPException(status_code=503, detail="Circuit breaker not initialized")
    return fastapi_resilience_manager.circuit_breaker


async def get_health_checker():
    """FastAPI dependency for health checker"""
    return health_checker


async def get_metrics_collector():
    """FastAPI dependency for metrics collector"""
    return metrics_collector


# Decorator for FastAPI routes with resilience patterns
def with_rate_limit(requests_per_second: float = 10.0, burst_size: int = 50):
    """FastAPI route decorator for rate limiting"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Rate limiting logic would be handled by middleware
            # This decorator is for documentation/configuration purposes
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def with_circuit_breaker(func):
    """FastAPI route decorator for circuit breaker"""
    async def wrapper(*args, **kwargs):
        circuit_breaker = await get_circuit_breaker()
        return await circuit_breaker.acall_with_cache(func, *args, **kwargs)
    return wrapper


# Example usage patterns for FastAPI
"""
# In your FastAPI app initialization:
from app.resilience.fastapi_integration import init_resilience

app = FastAPI()
resilience = init_resilience(app)

# In your route handlers:
from app.resilience.fastapi_integration import get_circuit_breaker
from app.resilience.retry import openai_retry

@app.post("/api/generate")
@with_rate_limit(requests_per_second=5.0, burst_size=20)
async def generate_text(
    request: GenerateRequest,
    circuit_breaker: OpenAICircuitBreaker = Depends(get_circuit_breaker)
):
    # Use circuit breaker for OpenAI API calls
    response = await circuit_breaker.acreate_chat_completion(
        messages=[{"role": "user", "content": request.prompt}]
    )
    return response

# In your service classes:
from app.resilience.fastapi_integration import fastapi_resilience_manager

class AIService:
    def __init__(self):
        self.circuit_breaker = fastapi_resilience_manager.get_circuit_breaker()

    async def generate_response(self, prompt: str):
        return await self.circuit_breaker.acreate_chat_completion(
            messages=[{"role": "user", "content": prompt}]
        )
"""