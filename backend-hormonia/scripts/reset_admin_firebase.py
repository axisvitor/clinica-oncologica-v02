import os
import sys

# Add parent dir to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings

def reset_admin_firebase():
    print(f"Connecting to DB: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else '...'}")
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Find the user
        email = "admin@neoplasiaslitoral.com"
        result = conn.execute(text("SELECT id, email, firebase_uid FROM users WHERE email = :email"), {"email": email}).fetchone()
        
        if not result:
            print(f"User {email} NOT FOUND!")
            return
            
        print(f"User found: {result.email}, Current Firebase UID: {result.firebase_uid}")
        
        if result.firebase_uid:
            print("Resetting firebase_uid...")
            conn.execute(text("UPDATE users SET firebase_uid = NULL, auth_provider = 'local' WHERE email = :email"), {"email": email})
            conn.commit()
            print("SUCCESS: firebase_uid cleared. You can now login to re-link.")
        else:
            print("firebase_uid is already NULL. Nothing to do.")

if __name__ == "__main__":
    reset_admin_firebase()
