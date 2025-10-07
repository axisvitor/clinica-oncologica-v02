#!/bin/bash
# Migration script for Railway deployment
# Safely adds SENDING status to existing database

set -e

echo "🔄 Running database migrations..."

# Direct SQL approach - add SENDING status if not exists
python -c "
from sqlalchemy import create_engine, text
import os

engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    # Add SENDING status if it doesn't exist
    conn.execute(text(\"\"\"
        DO \$\$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'messagestatus'
                AND e.enumlabel = 'sending'
            ) THEN
                ALTER TYPE messagestatus ADD VALUE 'sending' AFTER 'scheduled';
                RAISE NOTICE 'Added SENDING status to messagestatus enum';
            ELSE
                RAISE NOTICE 'SENDING status already exists';
            END IF;
        END
        \$\$;
    \"\"\"))
    conn.commit()
    print('✅ SENDING status verified/added successfully')
"

if [ $? -eq 0 ]; then
    echo "✅ Migrations completed successfully"
    exit 0
else
    echo "❌ Migration failed"
    exit 1
fi
