#!/bin/bash
set -e

# =============================================================================
# ENTRYPOINT.SH - Master entrypoint for Backend Services (Railway Compatible)
# =============================================================================
# Supports: API, Worker, Beat, Migrations
# Environment: Railway, Docker, Local
# =============================================================================

echo "=============================================="
echo "🚀 Hormonia Backend Entrypoint"
echo "=============================================="
echo "Environment: ${APP_ENVIRONMENT:-development}"
echo "Service Type: ${SERVICE_TYPE:-api}"
echo "Port: ${PORT:-8000}"
echo "=============================================="

# Wait for dependencies function
wait_for_database() {
    echo "⏳ Waiting for database connection..."
    local max_attempts=30
    local attempt=1

    # Pre-flight check: Verify DATABASE_URL is set
    if [ -z "$DATABASE_URL" ]; then
        echo "❌ FATAL: DATABASE_URL environment variable is not set!"
        echo "   Please configure DATABASE_URL in Railway environment variables."
        echo "   Format: postgresql://user:password@host:port/database"
        return 1
    fi

    # Extract host for diagnostic purposes (mask password)
    DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^/:]+).*|\1|')
    echo "   Database host: $DB_HOST"

    while [ $attempt -le $max_attempts ]; do
        # Use lightweight psycopg connection test (no full app import)
        if python3 -c "
import os
import sys
import re

def normalize_database_url(url):
    '''
    Convert SQLAlchemy DATABASE_URL to standard PostgreSQL format.
    Handles: postgresql+psycopg://, postgresql+asyncpg://, etc.
    '''
    # Remove SQLAlchemy dialect suffix (e.g., +psycopg, +asyncpg, +psycopg2)
    url = re.sub(r'^postgresql\+\w+://', 'postgresql://', url)
    return url

try:
    import psycopg
    database_url = normalize_database_url(os.environ.get('DATABASE_URL', ''))

    # Connect with timeout
    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1')
            result = cur.fetchone()
            if result and result[0] == 1:
                sys.exit(0)
            else:
                print('Database query returned unexpected result')
                sys.exit(1)
except ImportError:
    # Fallback: try psycopg2
    try:
        import psycopg2
        database_url = normalize_database_url(os.environ.get('DATABASE_URL', ''))
        with psycopg2.connect(database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1')
                result = cur.fetchone()
                if result and result[0] == 1:
                    sys.exit(0)
        print('Database query returned unexpected result')
        sys.exit(1)
    except Exception as e:
        print(f'Connection failed (psycopg2): {e}')
        sys.exit(1)
except Exception as e:
    print(f'Connection failed: {e}')
    sys.exit(1)
" 2>&1; then
            echo "✓ Database connection established"
            return 0
        fi

        echo "  Attempt $attempt/$max_attempts - waiting 2s..."
        sleep 2
        ((attempt++))
    done

    echo "❌ Failed to connect to database after $max_attempts attempts"
    echo "   Please verify:"
    echo "   1. DATABASE_URL is correctly configured"
    echo "   2. Database server is reachable from Railway network"
    echo "   3. Security groups/firewall allow connections"
    echo "   4. Database credentials are correct"
    return 1
}

wait_for_redis() {
    echo "⏳ Waiting for Redis connection..."
    local max_attempts=15
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if python -c "
import redis
import os

redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
enable_ssl = os.environ.get('REDIS_ENABLE_SSL', 'false').lower() == 'true'
ssl_cert_reqs = os.environ.get('REDIS_SSL_CERT_REQS', 'required').lower()

# Configure connection
kwargs = {'socket_timeout': 5, 'socket_connect_timeout': 5}

if enable_ssl:
    # Convert redis:// to rediss:// for SSL
    if redis_url.startswith('redis://'):
        redis_url = 'rediss://' + redis_url[8:]

    # Use ssl_cert_reqs parameter (works universally with from_url() in redis-py 5.x and 6.x)
    kwargs['ssl_cert_reqs'] = ssl_cert_reqs
    print(f'Redis SSL: enabled with cert_reqs={ssl_cert_reqs}')

try:
    r = redis.from_url(redis_url, **kwargs)
    r.ping()
    exit(0)
except Exception as e:
    print(f'Redis not ready: {e}')
    exit(1)
" 2>/dev/null; then
            echo "✓ Redis connection established"
            return 0
        fi

        echo "  Attempt $attempt/$max_attempts - waiting 2s..."
        sleep 2
        ((attempt++))
    done

    echo "⚠️ Redis not available (some features may be degraded)"
    return 0  # Don't fail on Redis - app can work in degraded mode
}

# Run database migrations
run_migrations() {
    if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
        echo "📦 Running database migrations..."
        cd /app

        # Check if alembic is available
        if [ -f "alembic.ini" ]; then
            python -m alembic upgrade head
            echo "✓ Migrations completed"
        else
            echo "⚠️ Alembic not configured, skipping migrations"
        fi
    fi
}

# Function to run API
run_api() {
    echo "🌐 Starting FastAPI Backend API..."

    # Wait for dependencies
    wait_for_database || exit 1
    wait_for_redis

    # Run migrations if enabled
    run_migrations

    # Determine number of workers
    WORKERS=${WEB_CONCURRENCY:-1}

    # Use gunicorn in production for better performance
    if [ "${APP_ENVIRONMENT:-development}" = "production" ]; then
        echo "📊 Production mode - using Gunicorn with $WORKERS workers"
        exec gunicorn app.main:app \
            --bind 0.0.0.0:${PORT:-8000} \
            --workers $WORKERS \
            --worker-class uvicorn.workers.UvicornWorker \
            --timeout 120 \
            --keep-alive 5 \
            --access-logfile - \
            --error-logfile - \
            --log-level info
    else
        echo "🔧 Development mode - using Uvicorn"
        exec uvicorn app.main:app \
            --host 0.0.0.0 \
            --port ${PORT:-8000} \
            --log-level info
    fi
}

# Function to run Celery Worker
run_worker() {
    echo "👷 Starting Celery Worker..."

    # Wait for dependencies
    wait_for_database || exit 1
    wait_for_redis || exit 1  # Worker REQUIRES Redis

    exec celery -A app.celery_app worker \
        --loglevel=info \
        --concurrency=${CELERY_WORKER_CONCURRENCY:-2} \
        --max-tasks-per-child=${CELERY_WORKER_MAX_TASKS_PER_CHILD:-1000} \
        --time-limit=${CELERY_WORKER_TIME_LIMIT_SECONDS:-300} \
        --soft-time-limit=${CELERY_WORKER_SOFT_TIME_LIMIT_SECONDS:-240} \
        --queues=${CELERY_QUEUES:-celery,flows,quiz,maintenance,monitoring} \
        --pool=prefork \
        --without-gossip \
        --without-mingle
}

# Function to run Celery Beat
run_beat() {
    echo "⏰ Starting Celery Beat Scheduler..."

    # Wait for Redis only (beat doesn't need database directly)
    wait_for_redis || exit 1

    # Clean up old PID file
    rm -f /tmp/celerybeat.pid /tmp/celerybeat-schedule

    exec celery -A app.celery_app beat \
        --loglevel=info \
        --pidfile=/tmp/celerybeat.pid \
        --schedule=/tmp/celerybeat-schedule
}

# Function to run migrations only
run_migrate() {
    echo "📦 Running database migrations only..."
    wait_for_database || exit 1

    cd /app
    python -m alembic upgrade head
    echo "✓ Migrations completed successfully"
}

# Main Dispatcher
command="${1:-$SERVICE_TYPE}"
command="${command:-api}"

echo "🎯 Executing command: $command"
echo "=============================================="

case "$command" in
    api)
        run_api
        ;;
    worker)
        run_worker
        ;;
    beat)
        run_beat
        ;;
    migrate)
        run_migrate
        ;;
    shell)
        echo "🐚 Starting interactive shell..."
        exec /bin/bash
        ;;
    *)
        # If unknown command, try to execute it directly
        if [ -n "$command" ]; then
            echo "🔧 Executing custom command: $@"
            exec "$@"
        else
            # Default to API
            run_api
        fi
        ;;
esac
