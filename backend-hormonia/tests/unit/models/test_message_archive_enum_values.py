from __future__ import annotations

from app.models.message_archive import MessageArchive


def test_message_archive_uses_canonical_lowercase_enums() -> None:
    assert MessageArchive.__table__.c.direction.type.enums == [
        "inbound",
        "outbound",
    ]
    assert MessageArchive.__table__.c.type.type.enums == [
        "text",
        "image",
        "audio",
        "video",
        "document",
        "button",
        "list",
        "media",
        "location",
        "quiz_intro",
        "quiz_question",
        "quiz_encouragement",
        "quiz_completion",
        "monthly_quiz_link",
        "monthly_quiz_reminder",
        "monthly_quiz_expired",
        "monthly_quiz_completed",
    ]
    assert MessageArchive.__table__.c.status.type.enums == [
        "pending",
        "scheduled",
        "sending",
        "sent",
        "delivered",
        "read",
        "failed",
        "cancelled",
    ]
    assert MessageArchive.__table__.c.delivery_status.type.enums == [
        "scheduled",
        "queued",
        "sending",
        "sent",
        "delivered",
        "read",
        "failed",
        "cancelled",
    ]
