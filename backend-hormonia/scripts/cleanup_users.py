"""
Delete all users except admin@neoplasiaslitoral.com
Handles foreign key constraints by disabling triggers.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

ADMIN_EMAIL = "admin@neoplasiaslitoral.com"

with engine.connect() as conn:
    # List current users
    result = conn.execute(text("SELECT email, role FROM users"))
    users = [(row[0], row[1]) for row in result]
    
    print("Current users:")
    for email, role in users:
        status = "[KEEP]" if email == ADMIN_EMAIL else "[DELETE]"
        print(f"  {status} {email} ({role})")
    
    # Disable FK constraints
    conn.execute(text("SET session_replication_role = 'replica';"))
    
    # Delete all except admin
    result = conn.execute(
        text("DELETE FROM users WHERE email != :admin_email"),
        {"admin_email": ADMIN_EMAIL}
    )
    deleted = result.rowcount
    
    # Re-enable FK constraints
    conn.execute(text("SET session_replication_role = 'origin';"))
    
    conn.commit()
    
    print(f"\n✓ Deleted {deleted} users. Only {ADMIN_EMAIL} remains.")
