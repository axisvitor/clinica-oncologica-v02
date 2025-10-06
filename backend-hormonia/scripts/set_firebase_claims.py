#!/usr/bin/env python3
"""
Firebase Custom Claims Script - Windows Compatible (No Emojis)
Sets required custom claims for admin user

Usage:
    python scripts/set_firebase_claims.py
"""

import os
import sys
import json
import firebase_admin
from firebase_admin import credentials, auth
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    print(f"[LOAD] Environment from: {env_path}")
    load_dotenv(env_path)
else:
    print(f"[WARN] No .env file at: {env_path}")


def validate_environment():
    """Validate required environment variables"""
    print("[CHECK] Validating environment variables...")

    required_vars = [
        'FIREBASE_ADMIN_PROJECT_ID',
        'FIREBASE_ADMIN_PRIVATE_KEY',
        'FIREBASE_ADMIN_CLIENT_EMAIL'
    ]

    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(var)
        else:
            display_value = value[:50] + "..." if len(value) > 50 else value
            print(f"   [OK] {var}: {display_value}")

    if missing:
        print(f"\n[ERROR] Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        return False

    print("[SUCCESS] All required environment variables are set")
    return True


def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    print("\n[INIT] Initializing Firebase Admin SDK...")

    project_id = os.getenv('FIREBASE_ADMIN_PROJECT_ID')
    private_key = os.getenv('FIREBASE_ADMIN_PRIVATE_KEY')
    client_email = os.getenv('FIREBASE_ADMIN_CLIENT_EMAIL')

    cred_dict = {
        "type": "service_account",
        "project_id": project_id,
        "private_key": private_key,
        "client_email": client_email,
        "token_uri": "https://oauth2.googleapis.com/token",
    }

    cred = credentials.Certificate(cred_dict)

    try:
        firebase_admin.initialize_app(cred)
        print(f"[SUCCESS] Firebase initialized for project: {project_id}")
        return True
    except ValueError as e:
        if "already exists" in str(e):
            print("[SUCCESS] Firebase already initialized")
            return True
        print(f"[ERROR] Firebase initialization error: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False


def set_custom_claims(uid, email, role="admin"):
    """Set custom claims for Firebase user"""
    print(f"\n[USER] Setting custom claims for: {email} (UID: {uid})")

    custom_claims = {
        "role": role,
        "roles": [role, "super_admin"] if role == "admin" else [role],
        "permissions": ["read", "write", "delete", "admin"] if role == "admin" else ["read"],
        "email_verified": True,
        "system": "neoplasias-litoral",
        "created_by": "admin_script",
    }

    try:
        auth.set_custom_user_claims(uid, custom_claims)
        print(f"[SUCCESS] Custom claims set successfully")

        user = auth.get_user(uid)
        print(f"\n[INFO] Verified custom claims:")
        print(json.dumps(user.custom_claims, indent=2))

        return True

    except auth.UserNotFoundError:
        print(f"[ERROR] User not found: {uid}")
        return False
    except Exception as e:
        print(f"[ERROR] Error setting custom claims: {e}")
        return False


def list_users():
    """List all Firebase users"""
    print("\n[INFO] Listing all Firebase users:")
    print("-" * 80)

    try:
        page = auth.list_users()
        users_found = 0

        for user in page.users:
            users_found += 1
            claims = user.custom_claims or {}
            role = claims.get('role', 'NO ROLE')

            print(f"\n[USER] {user.email or 'No email'}")
            print(f"   UID: {user.uid}")
            print(f"   Role: {role}")
            print(f"   Email Verified: {user.email_verified}")
            print(f"   Custom Claims: {json.dumps(claims, indent=6)}")

        print(f"\n[SUCCESS] Total users found: {users_found}")
        return users_found

    except Exception as e:
        print(f"[ERROR] Error listing users: {e}")
        return 0


def main():
    """Main execution"""
    print("=" * 80)
    print("Firebase Custom Claims Fix Script")
    print("=" * 80)

    if not validate_environment():
        print("\n[ERROR] Environment validation failed")
        sys.exit(1)

    if not initialize_firebase():
        print("[ERROR] Failed to initialize Firebase")
        sys.exit(1)

    # Admin user from Railway logs
    admin_uid = "xrqu2gDVL6eGfyNUiwxJlwVBbb73"
    admin_email = "admin@neoplasiaslitoral.com"

    print(f"\n[TARGET] User:")
    print(f"   Email: {admin_email}")
    print(f"   UID: {admin_uid}")

    success = set_custom_claims(admin_uid, admin_email, role="admin")

    if success:
        print("\n" + "=" * 80)
        print("[SUCCESS] Custom claims updated!")
        print("=" * 80)
        print("\n[NOTE] Next steps:")
        print("1. User must log out and log back in")
        print("2. Update Railway DATABASE_URL:")
        print("   DATABASE_URL=postgresql+psycopg://postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@...")
        print("3. Wait for Railway redeploy (~2-3 minutes)")
        print("4. Verify auth succeeds (200 instead of 401)")
        print("\n[OPTIONAL] List all users? (y/N): ", end="")

        response = input()
        if response.lower() == 'y':
            list_users()
    else:
        print("\n" + "=" * 80)
        print("[ERROR] FAILED - Could not set custom claims")
        print("=" * 80)
        print("\n[INFO] Listing all users for debugging:")
        list_users()
        sys.exit(1)


if __name__ == "__main__":
    main()
