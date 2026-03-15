"""Unit proof for canonical admin stats user-activity metrics."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from app.models.user import User, UserRole
from app.services.analytics.admin_stats_service import AdminStatsService
from app.utils.timezone import now_sao_paulo


def _seed_user(*, email: str, role: UserRole, last_login=None, firebase_last_sign_in=None) -> User:
    return User(
        id=uuid4(),
        email=email,
        full_name=email.split("@")[0].replace(".", " ").title(),
        role=role,
        is_active=True,
        last_login=last_login,
        firebase_last_sign_in=firebase_last_sign_in,
    )


def test_get_user_metrics_counts_recent_canonical_last_login_activity(db_session):
    baseline_metrics = AdminStatsService(db_session).get_user_metrics()
    now = now_sao_paulo()
    users = [
        _seed_user(
            email="active.admin@example.com",
            role=UserRole.ADMIN,
            last_login=now - timedelta(hours=2),
        ),
        _seed_user(
            email="inactive.doctor@example.com",
            role=UserRole.DOCTOR,
            last_login=now - timedelta(days=2),
        ),
        _seed_user(
            email="never-logged-in@example.com",
            role=UserRole.DOCTOR,
            last_login=None,
        ),
    ]
    db_session.add_all(users)
    db_session.commit()

    metrics = AdminStatsService(db_session).get_user_metrics()

    assert metrics["total"] == baseline_metrics["total"] + 3
    assert metrics["active_now"] == baseline_metrics["active_now"] + 1, (
        "canonical_profile surface=admin_stats canonical_active_users_missing=true"
    )
    assert metrics["by_role"].get("admin", 0) == baseline_metrics["by_role"].get("admin", 0) + 1
    assert metrics["by_role"].get("doctor", 0) == baseline_metrics["by_role"].get("doctor", 0) + 2


def test_get_user_metrics_ignores_legacy_login_mirror_without_canonical_last_login(db_session):
    now = now_sao_paulo()
    db_session.add(
        _seed_user(
            email="legacy-only@example.com",
            role=UserRole.DOCTOR,
            last_login=None,
            firebase_last_sign_in=now - timedelta(hours=1),
        )
    )
    db_session.commit()

    metrics = AdminStatsService(db_session).get_user_metrics()

    assert metrics["active_now"] == 0, (
        "canonical_profile surface=admin_stats canonical_last_login_not_required=true"
    )
