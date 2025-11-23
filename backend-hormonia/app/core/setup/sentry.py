"""
Sentry configuration and setup.
"""
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

def setup_sentry() -> None:
    """
    Initialize Sentry SDK for error tracking and performance monitoring.

    Sentry provides:
    - Automatic error capture and reporting
    - Performance monitoring and tracing
    - Release tracking
    - Environment-based configuration
    - Integration with FastAPI

    Configuration via environment variables:
    - SENTRY_DSN: Sentry project DSN (required)
    - ENVIRONMENT: Environment name (production, staging, development)
    - SENTRY_TRACES_SAMPLE_RATE: Performance monitoring sample rate (0.0-1.0)
    """
    sentry_dsn = settings.SENTRY_DSN if hasattr(settings, 'SENTRY_DSN') else None

    if not sentry_dsn:
        logger.info("⚠️  Sentry not configured (SENTRY_DSN not set)")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.redis import RedisIntegration

        # Determine environment
        environment = getattr(settings, 'ENVIRONMENT', 'development')

        # Configure sample rates based on environment
        traces_sample_rate = 0.1  # 10% in production
        if environment == 'development':
            traces_sample_rate = 1.0  # 100% in development
        elif environment == 'staging':
            traces_sample_rate = 0.5  # 50% in staging

        # Initialize Sentry
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=environment,
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=0.1,  # Profile 10% of transactions
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                RedisIntegration(),
            ],
            # Send default PII (Personally Identifiable Information)
            send_default_pii=False,  # Don't send PII for HIPAA compliance
            # Release tracking
            release=f"hormonia-backend@2.0.0",
            # Before send callback to filter sensitive data
            before_send=_sentry_before_send,
        )

        logger.info(f"✅ Sentry initialized (env: {environment}, traces: {traces_sample_rate*100}%)")

    except ImportError:
        logger.warning("⚠️  Sentry SDK not installed. Install with: pip install sentry-sdk[fastapi]")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Sentry: {e}")


def _sentry_before_send(event, hint):
    """
    Filter and sanitize events before sending to Sentry.

    This callback:
    - Removes sensitive data (passwords, tokens, PHI)
    - Filters out known non-critical errors
    - Adds custom context

    Args:
        event: Sentry event dictionary
        hint: Additional context about the event

    Returns:
        Modified event or None to drop the event
    """
    # Filter out health check errors
    if 'request' in event:
        url = event['request'].get('url', '')
        if '/health' in url or '/metrics' in url:
            return None  # Don't send health check errors

    # Remove sensitive headers
    if 'request' in event and 'headers' in event['request']:
        sensitive_headers = ['Authorization', 'Cookie', 'X-API-Key', 'X-CSRF-Token']
        for header in sensitive_headers:
            if header in event['request']['headers']:
                event['request']['headers'][header] = '[Filtered]'

    # Remove sensitive query parameters
    if 'request' in event and 'query_string' in event['request']:
        sensitive_params = ['token', 'api_key', 'password', 'secret']
        query_string = event['request'].get('query_string', '')
        for param in sensitive_params:
            if param in query_string.lower():
                event['request']['query_string'] = '[Filtered]'
                break

    return event
