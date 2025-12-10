#!/bin/bash
set -e

# entrypoint.sh - Master entrypoint for Backend Services

# Function to run API
run_api() {
    echo "🚀 Starting FastAPI Backend..."
    exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info
}

# Function to run Celery Worker
run_worker() {
    echo "👷 Starting Celery Worker..."
    exec celery -A app.celery_app worker \
        --loglevel=info \
        --concurrency=${CELERY_WORKER_CONCURRENCY:-4} \
        --max-tasks-per-child=${CELERY_WORKER_MAX_TASKS_PER_CHILD:-1000} \
        --time-limit=${CELERY_WORKER_TIME_LIMIT:-300} \
        --soft-time-limit=${CELERY_WORKER_SOFT_TIME_LIMIT:-240} \
        --queues=${CELERY_QUEUES:-celery,flows,quiz,maintenance,monitoring} \
        --pool=prefork 
        # removed autoscale to prevent issues in some container envs, can be added back via args if needed
}

# Function to run Celery Beat
run_beat() {
    echo "⏰ Starting Celery Beat..."
    rm -f /tmp/celerybeat.pid
    exec celery -A app.celery_app beat \
        --loglevel=info \
        --pidfile=/tmp/celerybeat.pid \
        --schedule=/tmp/celerybeat-schedule
}

# Main Dispatcher
# Check the first argument passed to the container
command="$1"

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
    *)
        # If no known command, or if it looks like a shell command, execute it
        # This allows running 'python script.py' or 'bash' for debugging
        if [ -z "$command" ]; then
            # Default to API if empty
            run_api
        else
            echo "🔧 Executing custom command: $@"
            exec "$@"
        fi
        ;;
esac
