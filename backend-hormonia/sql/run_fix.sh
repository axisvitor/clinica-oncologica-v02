#!/bin/bash

# Script to run the migration fix directly on PostgreSQL
# Usage: ./run_fix.sh

echo "🔧 Applying migration fixes directly to PostgreSQL..."
echo "======================================================================"

# Check if .env file exists
if [ ! -f "../.env" ]; then
    echo "❌ Error: .env file not found in backend-hormonia directory"
    echo "Please ensure your .env file exists with DATABASE_URL"
    exit 1
fi

# Source the .env file to get DATABASE_URL
source ../.env

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ Error: DATABASE_URL not found in .env file"
    echo "Please set DATABASE_URL in your .env file"
    exit 1
fi

echo "📡 Connecting to database..."
echo "🔧 Executing migration fixes..."

# Execute the SQL file
psql "$DATABASE_URL" -f fix_migration_issues.sql

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Migration fixes applied successfully!"
    echo "🎉 Your database is now ready to use."
    echo ""
    echo "Next steps:"
    echo "1. Start your backend application"
    echo "2. The migrations should now work correctly"
    echo "3. If you still have issues, check the application logs"
else
    echo ""
    echo "❌ Error applying migration fixes"
    echo "Please check the error messages above"
    exit 1
fi