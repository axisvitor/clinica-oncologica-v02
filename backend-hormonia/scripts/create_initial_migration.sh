#!/bin/bash
# Script to create initial Alembic migration
# CRITICAL FIX: Generate initial schema migration for all models

set -e

echo "🔧 Creating Initial Alembic Migration..."
echo "=========================================="

# Navigate to backend directory
cd "$(dirname "$0")/.."

# Check if alembic is installed
if ! command -v alembic &> /dev/null; then
    echo "❌ Error: Alembic not installed. Install with: pip install alembic"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "alembic.ini" ]; then
    echo "❌ Error: alembic.ini not found. Are you in the backend directory?"
    exit 1
fi

# Check database connection
echo "📡 Testing database connection..."
python -c "from app.database import test_connection; result = test_connection(); print('✅ Database connection:', result['status'])"

if [ $? -ne 0 ]; then
    echo "❌ Error: Database connection failed. Check your DATABASE_URL environment variable."
    exit 1
fi

# Create the initial migration
echo "🚀 Generating initial migration..."
alembic revision --autogenerate -m "Initial schema with all models"

echo ""
echo "✅ Initial migration created successfully!"
echo ""
echo "📋 Next steps:"
echo "   1. Review the generated migration in alembic/versions/"
echo "   2. Test the migration: alembic upgrade head"
echo "   3. Test rollback: alembic downgrade -1"
echo "   4. Commit the migration file to git"
echo ""
echo "⚠️  IMPORTANT: Always review auto-generated migrations before applying!"
