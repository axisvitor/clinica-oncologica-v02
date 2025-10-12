#!/usr/bin/env python3
"""
Debug Patients Endpoint
Test the patients endpoint directly to identify the 500 error.
"""

import os
import sys
import psycopg
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment variables."""
    db_url = (
        os.getenv('DATABASE_URL') or 
        os.getenv('POSTGRES_URL') or 
        os.getenv('DB_URL') or
        os.getenv('SUPABASE_DB_URL')
    )
    
    if not db_url:
        print("❌ No database URL found in environment variables")
        return None
    
    return db_url

def debug_patients_endpoint():
    """Debug the patients endpoint by testing database queries directly."""
    
    print("🔍 DEBUGGING PATIENTS ENDPOINT")
    print("=" * 40)
    
    db_url = get_database_url()
    if not db_url:
        return False
    
    try:
        print(f"🔌 Connecting to database...")
        
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                print("✅ Connected to database")
                
                # 1. Test basic patients query
                print("\n📋 Testing basic patients query...")
                try:
                    cur.execute("""
                        SELECT id, name, phone, email, treatment_type, flow_state, created_at
                        FROM patients 
                        ORDER BY created_at DESC 
                        LIMIT 20
                    """)
                    patients = cur.fetchall()
                    print(f"✅ Found {len(patients)} patients")
                    
                    if patients:
                        print("Sample patient data:")
                        for i, patient in enumerate(patients[:3]):
                            print(f"  {i+1}. ID: {patient[0]}, Name: {patient[1]}, Phone: {patient[2]}")
                
                except Exception as e:
                    print(f"❌ Basic patients query failed: {e}")
                    return False
                
                # 2. Test users table (for doctor lookup)
                print("\n👨‍⚕️ Testing users table...")
                try:
                    cur.execute("SELECT id, email, full_name, role FROM users LIMIT 5")
                    users = cur.fetchall()
                    print(f"✅ Found {len(users)} users")
                    
                    if users:
                        print("Sample user data:")
                        for i, user in enumerate(users[:3]):
                            print(f"  {i+1}. ID: {user[0]}, Email: {user[1]}, Role: {user[3]}")
                
                except Exception as e:
                    print(f"❌ Users query failed: {e}")
                    return False
                
                # 3. Test join query (patients with doctor info)
                print("\n🔗 Testing patients-users join...")
                try:
                    cur.execute("""
                        SELECT 
                            p.id, p.name, p.phone, p.email, p.treatment_type, 
                            p.flow_state, p.created_at, u.full_name as doctor_name
                        FROM patients p
                        LEFT JOIN users u ON p.doctor_id = u.id
                        ORDER BY p.created_at DESC 
                        LIMIT 10
                    """)
                    joined_data = cur.fetchall()
                    print(f"✅ Join query returned {len(joined_data)} records")
                    
                    if joined_data:
                        print("Sample joined data:")
                        for i, record in enumerate(joined_data[:2]):
                            print(f"  {i+1}. Patient: {record[1]}, Doctor: {record[7] or 'No doctor'}")
                
                except Exception as e:
                    print(f"❌ Join query failed: {e}")
                    return False
                
                # 4. Test pagination query
                print("\n📄 Testing pagination query...")
                try:
                    page = 1
                    size = 20
                    offset = (page - 1) * size
                    
                    # Count total
                    cur.execute("SELECT COUNT(*) FROM patients")
                    total = cur.fetchone()[0]
                    
                    # Get paginated results
                    cur.execute("""
                        SELECT id, name, phone, email, treatment_type, flow_state, created_at
                        FROM patients 
                        ORDER BY created_at DESC 
                        LIMIT %s OFFSET %s
                    """, (size, offset))
                    
                    paginated_results = cur.fetchall()
                    print(f"✅ Pagination: {len(paginated_results)} records (total: {total})")
                
                except Exception as e:
                    print(f"❌ Pagination query failed: {e}")
                    return False
                
                # 5. Test specific doctor filter
                print("\n👨‍⚕️ Testing doctor filter...")
                try:
                    # Get first doctor ID
                    cur.execute("SELECT id FROM users WHERE role = 'doctor' LIMIT 1")
                    doctor_result = cur.fetchone()
                    
                    if doctor_result:
                        doctor_id = doctor_result[0]
                        cur.execute("""
                            SELECT COUNT(*) FROM patients WHERE doctor_id = %s
                        """, (doctor_id,))
                        doctor_patients = cur.fetchone()[0]
                        print(f"✅ Doctor {doctor_id} has {doctor_patients} patients")
                    else:
                        print("⚠️  No doctors found in users table")
                
                except Exception as e:
                    print(f"❌ Doctor filter failed: {e}")
                    return False
                
                # 6. Test enum values
                print("\n🔢 Testing enum values...")
                try:
                    cur.execute("""
                        SELECT DISTINCT flow_state FROM patients
                    """)
                    flow_states = cur.fetchall()
                    print(f"✅ Flow states in use: {[fs[0] for fs in flow_states]}")
                
                except Exception as e:
                    print(f"❌ Enum test failed: {e}")
                    return False
                
                return True
                
    except Exception as e:
        print(f"\n❌ Database connection failed: {e}")
        logger.error(f"Database error: {e}", exc_info=True)
        return False

def main():
    """Run the debug test."""
    
    success = debug_patients_endpoint()
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 DATABASE QUERIES WORKING!")
        print()
        print("✅ All database queries executed successfully")
        print("✅ Data structure is correct")
        print("✅ The issue is likely in the application code, not the database")
        print()
        print("Next steps:")
        print("  1. Check ServiceProvider initialization")
        print("  2. Check authentication middleware")
        print("  3. Check dependency injection")
    else:
        print("❌ DATABASE QUERIES FAILED")
        print("The issue is in the database structure or connectivity.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())