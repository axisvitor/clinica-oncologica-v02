#!/bin/bash
# Smart migration script - detects database state and applies appropriate fix
set -e

echo "🔄 Checking database state..."

# Check if messagestatus enum exists and handle accordingly
python -c "
from sqlalchemy import create_engine, text
import os
import sys

engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    # Check if messagestatus enum exists
    result = conn.execute(text('''
        SELECT EXISTS (
            SELECT 1 FROM pg_type WHERE typname = ''messagestatus''
        );
    '''))
    enum_exists = result.scalar()

    if not enum_exists:
        print('❌ messagestatus enum does NOT exist')
        print('🔧 Database schema incomplete - need to run Alembic')
        sys.exit(2)  # Signal: need full Alembic migrations

    # Enum exists - check for SENDING value
    result = conn.execute(text('''
        SELECT EXISTS (
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = ''messagestatus''
            AND e.enumlabel = ''sending''
        );
    '''))
    sending_exists = result.scalar()

    if sending_exists:
        print('✅ SENDING status already exists')
        sys.exit(0)

    # Add SENDING value
    print('➕ Adding SENDING status to messagestatus enum...')
    conn.execute(text('''
        ALTER TYPE messagestatus ADD VALUE ''sending'' AFTER ''scheduled'';
    '''))
    conn.commit()
    print('✅ SENDING status added successfully')
    sys.exit(0)
"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 2 ]; then
    echo "🔧 Running full Alembic migrations..."
    python -m alembic upgrade head

    if [ $? -eq 0 ]; then
        echo "✅ Alembic migrations completed"
        exit 0
    else
        echo "❌ Alembic failed"
        exit 1
    fi
elif [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Migration completed successfully"
    exit 0
else
    echo "❌ Migration check failed"
    exit 1
fi
