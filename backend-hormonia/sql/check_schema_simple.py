#!/usr/bin/env python3
"""
Simple script to check the messages table schema.
"""
import os
import sys
import psycopg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_messages_schema():
    """Check the messages table schema."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("DATABASE_URL not found in environment")
        return
    
    # Convert SQLAlchemy URL to psycopg format
    if database_url.startswith('postgresql+psycopg://'):
        database_url = database_url.replace('postgresql+psycopg://', 'postgresql://')
    
    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                # Check if delivery_status column exists
                cur.execute('''
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_name = 'messages' 
                    AND table_schema = 'public'
                    ORDER BY ordinal_position;
                ''')
                
                columns = cur.fetchall()
                print('Messages table columns:')
                for col in columns:
                    print(f'  {col[0]} - {col[1]} (nullable: {col[2]})')
                
                # Check specifically for delivery_status
                has_delivery_status = any(col[0] == 'delivery_status' for col in columns)
                print(f'\ndelivery_status column exists: {has_delivery_status}')
                
                # Check if DeliveryStatus enum exists
                cur.execute('''
                    SELECT enumlabel 
                    FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = 'deliverystatus'
                    ORDER BY e.enumsortorder;
                ''')
                
                enum_values = cur.fetchall()
                print(f'\nDeliveryStatus enum exists: {len(enum_values) > 0}')
                if enum_values:
                    print('DeliveryStatus enum values:')
                    for val in enum_values:
                        print(f'  {val[0]}')
                
                # Check alembic version
                cur.execute('SELECT version_num FROM alembic_version;')
                version = cur.fetchone()
                print(f'\nCurrent alembic version: {version[0] if version else "None"}')
                
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    check_messages_schema()