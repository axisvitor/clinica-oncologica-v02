#!/usr/bin/env python3
"""
Firebase Custom Claims Fix Script
Adds required custom claims to admin user for Railway production deployment

Usage:
    python scripts/fix_firebase_custom_claims.py

Requirements:
    - Firebase Admin SDK credentials in environment
    - FIREBASE_ADMIN_PROJECT_ID
    - FIREBASE_ADMIN_PRIVATE_KEY
    - FIREBASE_ADMIN_CLIENT_EMAIL
"""

import os
import sys
import json
import firebase_admin
from firebase_admin import credentials, auth
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings


def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    print("🔧 Initializing Firebase Admin SDK...")

    settings = get_settings()

    # Create credentials from environment
    cred_dict = {
        "type": "service_account",
        "project_id": settings.FIREBASE_ADMIN_PROJECT_ID,
        "private_key": settings.FIREBASE_ADMIN_PRIVATE_KEY,
        "client_email": settings.FIREBASE_ADMIN_CLIENT_EMAIL,
        "token_uri": "https://oauth2.googleapis.com/token",
    }

    cred = credentials.Certificate(cred_dict)

    try:
        firebase_admin.initialize_app(cred)
        print(f"✅ Firebase initialized for project: {settings.FIREBASE_ADMIN_PROJECT_ID}")
        return True
    except ValueError as e:
        if "already exists" in str(e):
            print("✅ Firebase already initialized")
            return True
        raise


def set_custom_claims(uid: str, email: str, role: str = "admin"):
    """
    Set custom claims for a Firebase user

    Args:
        uid: Firebase user UID
        email: User email (for display)
        role: Primary role (default: admin)
    """
    print(f"\n👤 Setting custom claims for: {email} (UID: {uid})")

    # Define custom claims structure
    custom_claims = {
        "role": role,
        "roles": [role, "super_admin"] if role == "admin" else [role],
        "permissions": ["read", "write", "delete", "admin"] if role == "admin" else ["read"],
        "email_verified": True,
        "system": "neoplasias-litoral",
        "created_by": "admin_script",
    }

    try:
        # Set custom claims
        auth.set_custom_user_claims(uid, custom_claims)
        print(f"✅ Custom claims set successfully")

        # Verify the claims were set
        user = auth.get_user(uid)
        print(f"\n📋 Verified custom claims:")
        print(json.dumps(user.custom_claims, indent=2))

        return True

    except auth.UserNotFoundError:
        print(f"❌ User not found: {uid}")
        return False
    except Exception as e:
        print(f"❌ Error setting custom claims: {e}")
        return False


def list_users():
    """List all Firebase users and their custom claims"""
    print("\n📋 Listing all Firebase users:")
    print("-" * 80)

    try:
        page = auth.list_users()
        users_found = 0

        for user in page.users:
            users_found += 1
            claims = user.custom_claims or {}
            role = claims.get('role', 'NO ROLE')

            print(f"\n👤 {user.email or 'No email'}")
            print(f"   UID: {user.uid}")
            print(f"   Role: {role}")
            print(f"   Email Verified: {user.email_verified}")
            print(f"   Custom Claims: {json.dumps(claims, indent=6)}")

        print(f"\n✅ Total users found: {users_found}")
        return users_found

    except Exception as e:
        print(f"❌ Error listing users: {e}")
        return 0


def main():
    """Main execution"""
    print("=" * 80)
    print("Firebase Custom Claims Fix Script")
    print("=" * 80)

    # Initialize Firebase
    if not initialize_firebase():
        print("❌ Failed to initialize Firebase")
        sys.exit(1)

    # Admin user from Railway logs
    admin_uid = "xrqu2gDVL6eGfyNUiwxJlwVBbb73"
    admin_email = "admin@neoplasiaslitoral.com"

    print(f"\n🎯 Target user:")
    print(f"   Email: {admin_email}")
    print(f"   UID: {admin_uid}")

    # Set custom claims
    success = set_custom_claims(admin_uid, admin_email, role="admin")

    if success:
        print("\n" + "=" * 80)
        print("✅ SUCCESS - Custom claims updated!")
        print("=" * 80)
        print("\n📝 Next steps:")
        print("1. User must log out and log back in for changes to take effect")
        print("2. Verify in Railway logs that authentication succeeds (200 instead of 401)")
        print("3. Test endpoints:")
        print("   - GET /api/v1/auth/me")
        print("   - GET /api/v1/auth/notifications")
        print("   - GET /api/v1/analytics/dashboard")
        print("\n🔄 Optional: List all users to verify")

        response = input("\nList all Firebase users? (y/N): ")
        if response.lower() == 'y':
            list_users()
    else:
        print("\n" + "=" * 80)
        print("❌ FAILED - Could not set custom claims")
        print("=" * 80)
        print("\n📋 Listing all users for debugging:")
        list_users()
        sys.exit(1)


if __name__ == "__main__":
    main()
