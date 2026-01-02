from app.core.database import SessionLocal
from app.models.user import User

def list_users():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print(f"Found {len(users)} users:")
        for user in users:
            print(f"ID: {user.id} | Email: {user.email} | Active: {user.is_active} | Role: {user.role} | Firebase UID: {user.firebase_uid}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    list_users()
