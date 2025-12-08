"""
Check for duplicate patients in the database before running migration.
This script verifies phone, email, and CPF uniqueness per doctor.
"""
from sqlalchemy import create_engine, text
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings


def check_duplicates():
    """Check for duplicate patients across phone, email, and CPF fields."""
    try:
        engine = create_engine(str(settings.DATABASE_URL))

        queries = [
            (
                "Phone duplicates per doctor",
                """
                SELECT doctor_id, phone, COUNT(*) as count
                FROM patients
                WHERE deleted_at IS NULL
                GROUP BY doctor_id, phone
                HAVING COUNT(*) > 1
                """
            ),
            (
                "Email duplicates per doctor",
                """
                SELECT doctor_id, email, COUNT(*) as count
                FROM patients
                WHERE deleted_at IS NULL AND email IS NOT NULL
                GROUP BY doctor_id, email
                HAVING COUNT(*) > 1
                """
            ),
            (
                "CPF duplicates per doctor",
                """
                SELECT doctor_id, cpf, COUNT(*) as count
                FROM patients
                WHERE deleted_at IS NULL AND cpf IS NOT NULL
                GROUP BY doctor_id, cpf
                HAVING COUNT(*) > 1
                """
            )
        ]

        all_clear = True

        for query_name, query in queries:
            with engine.connect() as conn:
                result = list(conn.execute(text(query)))
                if result:
                    print(f"⚠️  {query_name} found duplicates:")
                    for row in result:
                        print(f"   Doctor ID: {row[0]}, Value: {row[1]}, Count: {row[2]}")
                    all_clear = False
                else:
                    print(f"✅ {query_name}: No duplicates found")

        if all_clear:
            print("\n✅ ALL CHECKS PASSED - Database is ready for migration")
            return 0
        else:
            print("\n⚠️  DUPLICATES FOUND - Please resolve before running migration")
            return 1

    except Exception as e:
        print(f"❌ Error checking duplicates: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(check_duplicates())
