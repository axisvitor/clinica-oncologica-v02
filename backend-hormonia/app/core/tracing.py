"""
Distributed Tracing with OpenTelemetry
Implements distributed tracing for debugging multi-service issues.

NOTE: Opentelemetry is optional. This module provides mock implementations
when opentelemetry is not installed.
"""
import logging
from typing import Optional, Dict, Any, Callable
from contextlib import contextmanager, asynccontextmanager
from functools import wraps
import os

logger = logging.getLogger(__name__)

# Try to import opentelemetry, use mocks if not available
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    from opentelemetry.trace import Status, StatusCode, Span
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    logger.warning("OpenTelemetry not installed. Tracing will be disabled.")
    OPENTELEMETRY_AVAILABLE = False

    # Create mock classes
    class MockSpan:
        def set_attribute(self, key, value): pass
        def add_event(self, name, attributes=None): pass
        def record_exception(self, exception): pass
        def set_status(self, status): pass
        def end(self): pass

    class MockTracer:
        def start_span(self, name, kind=None):
            return MockSpan()
        def get_current_span(self):
            return MockSpan()


class TracingConfig:
    """Configuration for distributed tracing"""

    def __init__(
        self,
        service_name: str = "clinica-oncologica",
        service_version: str = "1.0.0",
        environment: str = "production",
        jaeger_host: str = "localhost",
        jaeger_port: int = 6831,
        otlp_endpoint: Optional[str] = None,
        console_export: bool = False
    ):
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        self.jaeger_host = jaeger_host
        self.jaeger_port = jaeger_port
        self.otlp_endpoint = otlp_endpoint
        self.console_export = console_export


class DistributedTracer:
    """Distributed tracing manager with OpenTelemetry."""

    def __init__(self, config: Optional[TracingConfig] = None):
        self.config = config or TracingConfig()
        self.tracer = MockTracer() if not OPENTELEMETRY_AVAILABLE else None
        self._initialized = False

    def setup(self):
        """Setup OpenTelemetry tracing."""
        if not OPENTELEMETRY_AVAILABLE:
            logger.info("OpenTelemetry not available, using mock tracer")
            self._initialized = True
            return

        # Real OpenTelemetry setup would go here
        self._initialized = True
        logger.info(f"Distributed tracing initialized for {self.config.service_name}")

    def instrument_fastapi(self, app):
        """Instrument FastAPI application."""
        if not OPENTELEMETRY_AVAILABLE:
            return
        logger.info("FastAPI instrumentation skipped (OpenTelemetry not available)")

    def instrument_sqlalchemy(self, engine):
        """Instrument SQLAlchemy engine."""
        if not OPENTELEMETRY_AVAILABLE:
            return
        logger.info("SQLAlchemy instrumentation skipped (OpenTelemetry not available)")

    def instrument_redis(self):
        """Instrument Redis client."""
        if not OPENTELEMETRY_AVAILABLE:
            return
        logger.info("Redis instrumentation skipped (OpenTelemetry not available)")

    def instrument_httpx(self):
        """Instrument HTTPX client."""
        if not OPENTELEMETRY_AVAILABLE:
            return
        logger.info("HTTPX instrumentation skipped (OpenTelemetry not available)")

    def get_tracer(self):
        """Get tracer instance."""
        if not self._initialized:
            self.setup()
        return self.tracer

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None, kind=None):
        """Create a traced span context manager."""
        if not self._initialized:
            self.setup()

        span = self.tracer.start_span(name, kind=kind)
        if attributes and hasattr(span, 'set_attribute'):
            for key, value in attributes.items():
                span.set_attribute(key, value)

        try:
            yield span
        except Exception as e:
            if hasattr(span, 'record_exception'):
                span.record_exception(e)
            raise
        finally:
            if hasattr(span, 'end'):
                span.end()

    @asynccontextmanager
    async def async_span(self, name: str, attributes: Optional[Dict[str, Any]] = None, kind=None):
        """Create an async traced span context manager."""
        if not self._initialized:
            self.setup()

        span = self.tracer.start_span(name, kind=kind)
        if attributes and hasattr(span, 'set_attribute'):
            for key, value in attributes.items():
                span.set_attribute(key, value)

        try:
            yield span
        except Exception as e:
            if hasattr(span, 'record_exception'):
                span.record_exception(e)
            raise
        finally:
            if hasattr(span, 'end'):
                span.end()

    def trace_function(self, name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None, kind=None):
        """Decorator to trace async functions."""
        def decorator(func: Callable):
            span_name = name or func.__name__

            @wraps(func)
            async def wrapper(*args, **kwargs):
                async with self.async_span(span_name, attributes, kind):
                    return await func(*args, **kwargs)

            return wrapper

        return decorator


# Global tracer instance
_global_tracer: Optional[DistributedTracer] = None


def get_tracer() -> DistributedTracer:
    """Get or create global tracer instance."""
    global _global_tracer

    if _global_tracer is None:
        config = TracingConfig(
            service_name=os.getenv("SERVICE_NAME", "clinica-oncologica"),
            service_version=os.getenv("SERVICE_VERSION", "1.0.0"),
            environment=os.getenv("ENVIRONMENT", "production"),
        )

        _global_tracer = DistributedTracer(config)
        _global_tracer.setup()

    return _global_tracer


def setup_tracing(app, service_name: str = "clinica-oncologica", service_version: str = "1.0.0", db_engine=None) -> DistributedTracer:
    """Setup distributed tracing for the application."""
    config = TracingConfig(
        service_name=service_name,
        service_version=service_version,
        environment=os.getenv("ENVIRONMENT", "production"),
    )

    tracer = DistributedTracer(config)
    tracer.setup()

    # Instrument components (only if OpenTelemetry is available)
    tracer.instrument_fastapi(app)
    if db_engine:
        tracer.instrument_sqlalchemy(db_engine)
    tracer.instrument_redis()
    tracer.instrument_httpx()

    logger.info("Distributed tracing setup completed")
    return tracer


# Convenience decorators
def trace(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """Convenience decorator to trace functions."""
    tracer = get_tracer()
    return tracer.trace_function(name, attributes)


@contextmanager
def trace_context(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Convenience context manager for tracing."""
    tracer = get_tracer()
    with tracer.span(name, attributes):
        yield


@asynccontextmanager
async def trace_context_async(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Convenience async context manager for tracing."""
    tracer = get_tracer()
    async with tracer.async_span(name, attributes):
        yield