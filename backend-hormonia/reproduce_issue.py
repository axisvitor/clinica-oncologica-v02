
import sys
import os
import traceback

# Add current directory to path
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.models.user import User, UserRole

from app.api.v2.routers.admin.utils import _serialize_user
from app.api.v2.dependencies import create_cursor
import uuid

def reproduction():
    try:
        print("Testing create_cursor with UUID...")
        test_uuid = uuid.uuid4()
        try:
            cursor = create_cursor(test_uuid)
            print(f"Cursor created: {cursor}")
        except Exception as e:
            print(f"create_cursor FAILED: {e}")
            # traceback.print_exc()

        print("Connecting to DB...")
        db = SessionLocal()
        print("Connected.")
        
        print("Querying users with role=doctor...")
        query = db.query(User)
        role = "doctor"
        role_enum = UserRole(role.lower())
        query = query.filter(User.role == role_enum)
        
        print("Executing query...")
        users = query.all()
        print(f"Found {len(users)} users.")
        
        for user in users:
            print(f"Serializing User: {user.email}")
            serialized = _serialize_user(user)
            print(f"Serialized: {serialized}")
                
        db.close()
        print("Success!")
        
    except Exception:
        print("Caught exception!")
        traceback.print_exc()

if __name__ == "__main__":
    reproduction()
