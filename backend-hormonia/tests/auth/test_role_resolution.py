"""
Role resolution helper tests.
"""

from app.dependencies.auth_dependencies import _resolve_user_role
from app.models.user import UserRole


def test_resolve_role_from_firebase_claims_admin():
    role = _resolve_user_role(
        firebase_custom_claims={"role": "admin"},
        db_role=UserRole.DOCTOR,
    )
    assert role == UserRole.ADMIN


def test_resolve_role_from_firebase_claims_doctor():
    role = _resolve_user_role(
        firebase_custom_claims={"role": "doctor"},
        db_role=UserRole.ADMIN,
    )
    assert role == UserRole.DOCTOR


def test_resolve_role_from_firebase_roles_list():
    role = _resolve_user_role(
        firebase_custom_claims={"roles": ["doctor", "admin"]},
        db_role=UserRole.ADMIN,
    )
    assert role == UserRole.DOCTOR


def test_resolve_role_falls_back_to_db_admin():
    role = _resolve_user_role(
        firebase_custom_claims={},
        db_role=UserRole.ADMIN,
    )
    assert role == UserRole.ADMIN


def test_resolve_role_falls_back_to_db_doctor():
    role = _resolve_user_role(
        firebase_custom_claims=None,
        db_role=UserRole.DOCTOR,
    )
    assert role == UserRole.DOCTOR


def test_invalid_firebase_role_falls_back_to_db():
    role = _resolve_user_role(
        firebase_custom_claims={"role": "superuser"},
        db_role=UserRole.ADMIN,
    )
    assert role == UserRole.ADMIN


def test_missing_role_defaults_to_doctor():
    role = _resolve_user_role()
    assert role == UserRole.DOCTOR
