#!/usr/bin/env python3
"""
Check the messages table schema to identify missing columns.
"""
import os
import sys
sys.path.append('.')

from app.core.database import get_db_service_role
from sqlalchemy import text

def check_messages_schema():
    """Check the messages table schema."""
    db = next(get_db_service_role())
    
    try:
        # Check if delivery_status column exists
        result = db.execute(text('''
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'messages' 
            AND table_schema = 'public'
            ORDER BY ordinal_position;
        '''))
        
        columns = result.fetchall()
        print('Messages table columns:')
        for col in columns:
            print(f'  {col[0]} - {col[1]} (nullable: {col[2]})')
        
        # Check specifically for delivery_status
        has_delivery_status = any(col[0] == 'delivery_status' for col in columns)
        print(f'\ndelivery_status column exists: {has_delivery_status}')
        
        # Check if DeliveryStatus enum exists
        result = db.execute(text('''
            SELECT enumlabel 
            FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = 'deliverystatus'
            ORDER BY e.enumsortorder;
        '''))
        
        enum_values = result.fetchall()
        print(f'\nDeliveryStatus enum exists: {len(enum_values) > 0}')
        if enum_values:
            print('DeliveryStatus enum values:')
            for val in enum_values:
                print(f'  {val[0]}')
        
        # Check alembic version
        result = db.execute(text('SELECT version_num FROM alembic_version;'))
        version = result.fetchone()
        print(f'\nCurrent alembic version: {version[0] if version else "None"}')
        
    except Exception as e:
        print(f'Error: {e}')
    finally:
        db.close()

if __name__ == '__main__':
    check_messages_schema()