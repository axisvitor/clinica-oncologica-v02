from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v2.routers.quiz_sessions import delete_quiz, update_quiz
from app.core.exceptions import ForbiddenError
from app.models.patient import Patient
from app.models.quiz import QuizSession
from app.schemas.v2.quiz import QuizV2Update


@dataclass
class _FakeQuery:
    model: object
    quiz: object | None
    patient: object | None

    def get(self, _id):
        if self.model is QuizSession:
            return self.quiz
        if self.model is Patient:
            return self.patient
        return None


class _FakeDB:
    def __init__(self, quiz: object | None, patient: object | None):
        self._quiz = quiz
        self._patient = patient
        self.committed = False
        self.deleted = False
        self.refreshed = False

    def query(self, model):
        return _FakeQuery(model=model, quiz=self._quiz, patient=self._patient)

    def commit(self):
        self.committed = True

    def refresh(self, _obj):
        self.refreshed = True

    def delete(self, _obj):
        self.deleted = True


def _build_quiz():
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        patient_id=uuid4(),
        quiz_template_id=uuid4(),
        status="started",
        created_at=now,
        updated_at=now,
        started_at=now,
        completed_at=None,
        score=None,
        max_score=None,
        passed=None,
    )


@pytest.mark.asyncio
async def test_update_quiz_blocks_orphan_session_for_non_admin():
    quiz = _build_quiz()
    db = _FakeDB(quiz=quiz, patient=None)

    with pytest.raises(ForbiddenError):
        await update_quiz(
            quiz_id=str(quiz.id),
            quiz_data=QuizV2Update(status="completed"),
            db=db,
            current_user={"id": str(uuid4()), "role": "doctor"},
        )

    assert db.committed is False


@pytest.mark.asyncio
async def test_delete_quiz_blocks_orphan_session_for_non_admin():
    quiz = _build_quiz()
    db = _FakeDB(quiz=quiz, patient=None)

    with pytest.raises(ForbiddenError):
        await delete_quiz(
            quiz_id=str(quiz.id),
            db=db,
            current_user={"id": str(uuid4()), "role": "doctor"},
        )

    assert db.deleted is False
    assert db.committed is False


@pytest.mark.asyncio
async def test_update_quiz_allows_admin_for_orphan_session():
    quiz = _build_quiz()
    db = _FakeDB(quiz=quiz, patient=None)

    payload = QuizV2Update(status="completed")
    result = await update_quiz(
        quiz_id=str(quiz.id),
        quiz_data=payload,
        db=db,
        current_user={"id": str(uuid4()), "role": "admin"},
    )

    assert result["status"] == "completed"
    assert db.committed is True
    assert db.refreshed is True
