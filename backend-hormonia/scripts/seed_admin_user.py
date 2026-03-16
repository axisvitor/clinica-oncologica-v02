#!/usr/bin/env python3
"""
Seed script: create an admin/doctor user for local development.

Usage:
    cd backend-hormonia
    source .venv/bin/activate
    python -m scripts.seed_admin_user

Idempotent — skips creation if the user already exists.
"""

import sys
import os

# Add the backend-hormonia directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load .env before importing app modules
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from app.database import SessionLocal
from app.models.user import User, UserRole, AuthProvider
from app.utils.security import get_password_hash
from app.utils.timezone import now_sao_paulo

# Seed credentials (local dev only — never use in production)
SEED_EMAIL = "admin@hormonia.dev"
SEED_PASSWORD = "Admin@1234"
SEED_FULL_NAME = "Dr. Admin Hormonia"
SEED_ROLE = UserRole.ADMIN


def seed_admin_user() -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == SEED_EMAIL).first()
        if existing:
            print(f"✅ Seed user already exists: {SEED_EMAIL} (id={existing.id})")
            # Ensure the user has a password and is active
            changed = False
            if not existing.hashed_password:
                existing.hashed_password = get_password_hash(SEED_PASSWORD)
                changed = True
                print("   → Set missing hashed_password")
            if not existing.is_active:
                existing.is_active = True
                changed = True
                print("   → Activated user")
            if existing.is_locked:
                existing.is_locked = False
                existing.locked_until = None
                existing.failed_login_attempts = 0
                changed = True
                print("   → Unlocked user")
            if changed:
                db.commit()
                print("   → Changes committed")
            return

        now = now_sao_paulo()
        user = User(
            email=SEED_EMAIL,
            hashed_password=get_password_hash(SEED_PASSWORD),
            full_name=SEED_FULL_NAME,
            role=SEED_ROLE,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
            email_verified=True,
            display_name=SEED_FULL_NAME,
            specialty="Oncologia",
            specialties=["Oncologia"],
            last_login=now,
            auth_created_at=now,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"✅ Seed user created: {SEED_EMAIL} (id={user.id}, role={user.role.value})")
        print(f"   Password: {SEED_PASSWORD}")
    except Exception as exc:
        db.rollback()
        print(f"❌ Failed to seed user: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin_user()
