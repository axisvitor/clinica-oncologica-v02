"""
App Routers - Session-based and Quiz authentication modules

This package contains specialized authentication routers:
- auth_session: Session-based authentication with Firebase + Redis
- quiz_auth: Quiz-specific authentication with httpOnly cookies
"""

from app.routers import auth_session, quiz_auth

__all__ = ["auth_session", "quiz_auth"]
