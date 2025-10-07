#!/bin/bash
# Migration script for Railway deployment
# This script runs Alembic migrations before starting the application

set -e  # Exit on error

echo "🔄 Running database migrations..."

# Run Alembic upgrade
python -m alembic upgrade head

if [ $? -eq 0 ]; then
    echo "✅ Migrations completed successfully"
    exit 0
else
    echo "❌ Migration failed"
    exit 1
fi
