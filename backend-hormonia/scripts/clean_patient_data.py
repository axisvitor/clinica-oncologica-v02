"""
Script to safely clean patient data from the database.
This script removes ONLY patient-related data, preserving:
- Users (doctors/admins)
- Flow templates and configurations
- Quiz templates
- System configurations
- Admin data
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

import psycopg

def clean_patient_data():
    """Clean patient data safely."""
    
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("✗ DATABASE_URL not found in environment")
        return
    
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    
    print("=" * 70)
    print("PATIENT DATA CLEANUP SCRIPT")
    print("=" * 70)
    print("\nThis script will DELETE the following data:")
    print("  ✗ All patients")
    print("  ✗ Patient flow states")
    print("  ✗ Patient onboarding sagas")
    print("  ✗ Messages (WhatsApp)")
    print("  ✗ Message status events")
    print("  ✗ Quiz sessions and responses")
    print("  ✗ Medical reports")
    print("  ✗ Appointments")
    print("  ✗ Alerts")
    print("  ✗ Contacts related to patients")
    print("  ✗ Flow analytics")
    print("  ✗ Notifications related to patients")
    print("\nThis script will PRESERVE:")
    print("  ✓ Users (doctors/admins)")
    print("  ✓ Flow templates and versions")
    print("  ✓ Quiz templates")
    print("  ✓ System configurations")
    print("  ✓ Admin users and permissions")
    print("  ✓ Audit logs")
    print("=" * 70)
    
    # Ask for confirmation
    confirmation = input("\nType 'DELETE PATIENT DATA' to confirm: ")
    
    if confirmation != "DELETE PATIENT DATA":
        print("\n✗ Operation cancelled. No data was deleted.")
        return
    
    print(f"\nConnecting to database...")
    
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                print("\n" + "=" * 70)
                print("STARTING DATA CLEANUP")
                print("=" * 70)
                
                # Count records before deletion
                print("\n📊 Counting records before deletion...")
                
                tables_to_clean = [
                    "notifications",
                    "flow_analytics",
                    "contacts",
                    "alerts",
                    "appointments",
                    "medical_reports",
                    "quiz_responses",
                    "quiz_sessions",
                    "message_status_events",
                    "messages",
                    "patient_onboarding_saga",
                    "patient_flow_states",
                    "patients"
                ]
                
                counts_before = {}
                for table in tables_to_clean:
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cur.fetchone()[0]
                        counts_before[table] = count
                        print(f"  {table}: {count} records")
                    except Exception as e:
                        print(f"  {table}: Error counting - {e}")
                        counts_before[table] = 0
                
                # Delete data in correct order (respecting foreign keys)
                print("\n🗑️  Deleting data...")
                
                # 1. Delete notifications related to patients
                print("\n1. Deleting notifications related to patients...")
                cur.execute("DELETE FROM notifications WHERE related_patient_id IS NOT NULL")
                deleted = cur.rowcount
                print(f"   ✓ Deleted {deleted} patient-related notifications")
                
                # 2. Delete flow analytics
                print("\n2. Deleting flow analytics...")
                cur.execute("DELETE FROM flow_analytics WHERE patient_id IS NOT NULL")
                deleted = cur.rowcount
                print(f"   ✓ Deleted {deleted} flow analytics records")
                
                # 3. Delete contacts related to patients
                print("\n3. Deleting contacts related to patients...")
                cur.execute("DELETE FROM contacts WHERE related_patient_id IS NOT NULL")
                deleted = cur.rowcount
                print(f"   ✓ Deleted {deleted} patient contacts")
                
                # 4. Delete alerts
                print("\n4. Deleting alerts...")
                cur.execute("DELETE FROM alerts")
                deleted = cur.rowcount
                print(f"   ✓ Deleted {deleted} alerts")
                
                # 5. Delete appointments
                print("\n5. Deleting appointments...")
                cur.execute("DELETE FROM appointments")
                deleted = cur.rowcount
                print(f"   ✓ Deleted {deleted} appointments")
                
                # 6. Delete medical reports
                print("\n6. Deleting medical reports...")
                cur.execute("DELETE FROM medical_reports")
                deleted = cur.rowcount
                print(f"   ✓ Deleted {deleted} medical reports")
                
                # 7. Delete quiz responses
                print("\n7. Deleting quiz responses...")
                cur.execute("DELETE FROM quiz_responses")
                deleted = cur.rowcount
                print(f"   ✓ Deleted {deleted} quiz responses")
                
                # 8. Delete quiz sessions
                print("\n8. Deleting quiz sessions...")
                cur.execute("DELETE FROM quiz_sessions")
                deleted = cur.rowcount
                print(f"   ✓ Deleted {deleted} quiz sessions")
                
                # 9. Delete message status events
                print("\n9. Deleting message status events...")
                cur.execute("DELETE FROM message_status_events")
                deleted = cur.rowcount
                print(f"   ✓ Deleted {deleted} message status events")
                
                # 10. Delete messages
                print("\n10. Deleting messages...")
                cur.execute("DELETE FROM messages")
                deleted = cur.rowcount
                print(f"   ✓ Deleted {deleted} messages")
                
                # 11. Delete patient onboarding sagas
                print("\n11. Deleting patient onboarding sagas...")
                cur.execute("DELETE FROM patient_onboarding_saga")
                deleted = cur.rowcount
                print(f"   ✓ Deleted {deleted} onboarding sagas")
                
                # 12. Delete patient flow states
                print("\n12. Deleting patient flow states...")
                cur.execute("DELETE FROM patient_flow_states")
                deleted = cur.rowcount
                print(f"   ✓ Deleted {deleted} flow states")
                
                # 13. Finally, delete patients
                print("\n13. Deleting patients...")
                cur.execute("DELETE FROM patients")
                deleted = cur.rowcount
                print(f"   ✓ Deleted {deleted} patients")
                
                # Commit the transaction
                conn.commit()
                print("\n✓ All changes committed to database")
                
                # Verify deletion
                print("\n📊 Verifying deletion...")
                all_clean = True
                for table in tables_to_clean:
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cur.fetchone()[0]
                        if count > 0:
                            print(f"  ⚠ {table}: {count} records remaining")
                            all_clean = False
                        else:
                            print(f"  ✓ {table}: clean (0 records)")
                    except Exception as e:
                        print(f"  ✗ {table}: Error verifying - {e}")
                
                # Summary
                print("\n" + "=" * 70)
                print("CLEANUP SUMMARY")
                print("=" * 70)
                
                total_deleted = sum(counts_before.values())
                print(f"\nTotal records deleted: {total_deleted}")
                print("\nRecords deleted by table:")
                for table, count in counts_before.items():
                    if count > 0:
                        print(f"  - {table}: {count}")
                
                if all_clean:
                    print("\n✓ All patient data successfully cleaned!")
                else:
                    print("\n⚠ Some records may remain. Check the verification above.")
                
                print("\n" + "=" * 70)
                
    except Exception as e:
        print(f"\n✗ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
        print("\n⚠ Transaction was rolled back. No data was deleted.")

if __name__ == "__main__":
    clean_patient_data()
