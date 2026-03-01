from __future__ import annotations

from uuid import uuid4

from app.repositories.alert import AlertRepository
from app.repositories.appointment import AppointmentRepository
from app.repositories.notification import NotificationRepository


class _FakeQuery:
    def __init__(self):
        self.filters = []

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def order_by(self, *args, **kwargs):
        return self

    def options(self, *args, **kwargs):
        return self

    def offset(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        return []

    def count(self):
        return 0


class _FakeDB:
    def __init__(self):
        self.last_query = None

    def query(self, *_args, **_kwargs):
        self.last_query = _FakeQuery()
        return self.last_query


def _contains_python_bool(node) -> bool:
    if isinstance(node, bool):
        return True
    get_children = getattr(node, "get_children", None)
    if callable(get_children):
        return any(_contains_python_bool(child) for child in get_children())
    return False


def test_alert_repository_unacknowledged_filter_uses_sql_expression():
    db = _FakeDB()
    repo = AlertRepository(db)

    repo.get_unacknowledged(eager_load=False)

    assert db.last_query is not None
    assert db.last_query.filters
    assert not _contains_python_bool(db.last_query.filters[0])


def test_notification_repository_unread_filter_uses_sql_expression():
    db = _FakeDB()
    repo = NotificationRepository(db)

    repo.get_unread(user_id=uuid4(), eager_load=False)

    assert db.last_query is not None
    assert db.last_query.filters
    assert not _contains_python_bool(db.last_query.filters[0])


def test_appointment_repository_pending_reminders_filter_uses_sql_expression():
    db = _FakeDB()
    repo = AppointmentRepository(db)

    repo.get_pending_reminders(eager_load=False)

    assert db.last_query is not None
    assert db.last_query.filters
    assert not _contains_python_bool(db.last_query.filters[0])
