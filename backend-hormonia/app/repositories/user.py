from typing import Optional, List

from sqlalchemy.orm import Session, selectinload

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model with eager loading optimization"""

    def __init__(self, db: Session):
        super().__init__(db, User)

    def get_by_email(self, email: str, eager_load: bool = False) -> Optional[User]:
        """
        Get user by email with optional eager loading.

        Args:
            email: User email address
            eager_load: Enable eager loading of relationships (default: False for single user)

        Returns:
            User or None if not found
        """
        query = self.db.query(User).filter(User.email == email)

        if eager_load:
            # Load patients relationship for doctor users
            query = query.options(selectinload(User.patients))

        return query.first()

    def get_by_firebase_uid(self, firebase_uid: str) -> Optional[User]:
        """
        Get user by Firebase UID.

        Args:
            firebase_uid: Firebase user ID

        Returns:
            User or None if not found
        """
        return self.db.query(User).filter(User.firebase_uid == firebase_uid).first()

    def get_active_users(
        self, skip: int = 0, limit: int = 100, eager_load: bool = True
    ) -> List[User]:
        """
        Get all active users with eager loading enabled by default.

        PERFORMANCE OPTIMIZATION: Eager loading prevents N+1 queries when accessing
        user relationships (patients for doctors).

        Relationships loaded when eager_load=True:
        - patients: Doctor's patients (selectinload - 1:many)

        Args:
            skip: Pagination offset
            limit: Maximum records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of active users with relationships pre-loaded
        """
        query = self.db.query(User).filter(User.is_active)

        if eager_load:
            # PERFORMANCE: Eager load patients relationship to prevent N+1 queries
            query = query.options(selectinload(User.patients))

        return query.offset(skip).limit(limit).all()
