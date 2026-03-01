"""
Production-specific configuration for Railway deployment.
Optimized settings for performance, security, and monitoring.
"""

import os
from typing import Dict, Any

# Railway-specific environment detection
IS_RAILWAY = os.getenv('RAILWAY_ENVIRONMENT') is not None
IS_PRODUCTION = os.getenv('ENVIRONMENT') == 'production'


def _is_truthy(value: str | None) -> bool:
    """Parse common truthy environment values."""
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on"})


# Prefer canonical REDIS_ENABLE_SSL, fallback to legacy REDIS_SSL for compatibility.
REDIS_SSL_ENABLED = _is_truthy(os.getenv('REDIS_ENABLE_SSL')) or _is_truthy(os.getenv('REDIS_SSL'))

# Production database configuration
DATABASE_CONFIG = {
    'pool_size': 20,
    'max_overflow': 30,
    'pool_timeout': 30,
    'pool_recycle': 3600,  # 1 hour
    'pool_pre_ping': True,
    'echo': False,
    'echo_pool': False,
    'connect_args': {
        'connect_timeout': 10,
        'command_timeout': 30,
        'server_settings': {
            'application_name': 'hormonia_backend',
            'jit': 'off'  # Disable JIT for better predictability
        }
    }
}

# Redis configuration for production
REDIS_CONFIG = {
    'socket_timeout': 10,
    'socket_connect_timeout': 5,
    'socket_keepalive': True,
    'socket_keepalive_options': {},
    'max_connections': 50,
    'retry_on_timeout': True,
    'health_check_interval': 30,
    'decode_responses': True,
    'ssl_cert_reqs': 'required' if REDIS_SSL_ENABLED else 'none'
}

# Gunicorn configuration
GUNICORN_CONFIG = {
    'bind': f"0.0.0.0:{os.getenv('PORT', '8000')}",
    'workers': int(os.getenv('WEB_CONCURRENCY', '4')),
    'worker_class': 'uvicorn.workers.UvicornWorker',
    'worker_connections': 1000,
    'max_requests': 1000,
    'max_requests_jitter': 50,
    'timeout': 120,
    'keepalive': 2,
    'preload_app': True,
    'worker_tmp_dir': '/dev/shm',
    'accesslog': '-',
    'errorlog': '-',
    'loglevel': 'info',
    'capture_output': True,
    'enable_stdio_inheritance': True
}

# Security headers for production
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' https:; connect-src 'self' https:",
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()'
}

# Rate limiting configuration
RATE_LIMIT_CONFIG = {
    'default_limit': 100,  # requests per minute
    'default_window': 60,  # seconds
    'auth_limit': 5,       # login attempts per minute
    'api_limit': 200,      # API calls per minute
    'webhook_limit': 1000, # webhook calls per minute
    'storage_backend': 'redis',
    'strategy': 'moving-window'
}

# Monitoring configuration
MONITORING_CONFIG = {
    'enabled': True,
    'debug': False,
    'sample_rate': 0.1,  # 10% sampling in production
    'metrics_retention_days': 30,
    'alert_thresholds': {
        'error_rate': 0.05,      # 5% error rate
        'response_time_p95': 2.0, # 2 seconds
        'cpu_usage': 80,          # 80% CPU
        'memory_usage': 85,       # 85% memory
        'disk_usage': 90          # 90% disk
    }
}

# Caching configuration
CACHE_CONFIG = {
    'default_timeout': 300,    # 5 minutes
    'long_timeout': 3600,      # 1 hour
    'session_timeout': 1800,   # 30 minutes
    'key_prefix': 'hormonia:',
    'version': 1
}

# File upload configuration
UPLOAD_CONFIG = {
    'max_file_size': 10 * 1024 * 1024,  # 10MB
    'allowed_extensions': {
        'images': {'jpg', 'jpeg', 'png', 'gif', 'webp'},
        'documents': {'pdf', 'doc', 'docx', 'txt'},
        'audio': {'mp3', 'wav', 'ogg', 'm4a'},
        'video': {'mp4', 'avi', 'mov', 'wmv'}
    },
    'upload_folder': os.getenv('UPLOAD_DIR', 'uploads'),
    'serve_files': False  # Use CDN in production
}

# Background task configuration
CELERY_CONFIG = {
    'task_always_eager': False,
    'task_eager_propagates': True,
    'task_serializer': 'json',
    'result_serializer': 'json',
    'accept_content': ['json'],
    'timezone': 'America/Sao_Paulo',
    'enable_utc': True,
    'task_track_started': True,
    'task_time_limit': 30 * 60,  # 30 minutes
    'task_soft_time_limit': 25 * 60,  # 25 minutes
    'worker_prefetch_multiplier': 1,
    'worker_max_tasks_per_child': 1000,
    'worker_disable_rate_limits': False,
    'beat_schedule': {}
}

# API configuration
API_CONFIG = {
    'max_page_size': 100,
    'default_page_size': 20,
    'enable_swagger': False,  # Disable in production
    'enable_redoc': False,    # Disable in production
    'cors_max_age': 86400,    # 24 hours
    'request_timeout': 30,    # seconds
    'response_timeout': 30    # seconds
}

def get_production_config() -> Dict[str, Any]:
    """Get complete production configuration."""
    return {
        'database': DATABASE_CONFIG,
        'redis': REDIS_CONFIG,
        'gunicorn': GUNICORN_CONFIG,
        'security_headers': SECURITY_HEADERS,
        'rate_limiting': RATE_LIMIT_CONFIG,
        'monitoring': MONITORING_CONFIG,
        'caching': CACHE_CONFIG,
        'uploads': UPLOAD_CONFIG,
        'celery': CELERY_CONFIG,
        'api': API_CONFIG,
        'is_railway': IS_RAILWAY,
        'is_production': IS_PRODUCTION
    }

def apply_production_optimizations():
    """Apply production-specific optimizations."""
    import logging

    # Configure production logging
    if IS_PRODUCTION:
        # Reduce log level for third-party libraries
        logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
        logging.getLogger('httpx').setLevel(logging.WARNING)

        # Set application log level
        logging.getLogger('app').setLevel(logging.INFO)

    # Set environment variables for optimal performance
    os.environ.setdefault('PYTHONUNBUFFERED', '1')
    os.environ.setdefault('PYTHONDONTWRITEBYTECODE', '1')

    # Railway-specific optimizations
    if IS_RAILWAY:
        # Use Railway's recommended worker count
        if not os.getenv('WEB_CONCURRENCY'):
            import multiprocessing
            workers = min(multiprocessing.cpu_count(), 4)
            os.environ['WEB_CONCURRENCY'] = str(workers)

# Apply optimizations when module is imported
apply_production_optimizations()
