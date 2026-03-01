from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.user import UserRole
from app.services.enhanced_quiz_service import EnhancedQuizService
from app.services.quiz.quiz_engine import QuizReportGenerator
from app.services.quiz.quiz_service import (
    QuizResponseService,
    QuizSessionService,
    QuizTemplateService,
)


@dataclass
class _FakeScalarResult:
    values: list

    def unique(self):
        return self

    def all(self):
        return list(self.values)


@dataclass
class _FakeResult:
    scalar_rows: list | None = None
    scalar_value: int | None = None

    def scalars(self):
        return _FakeScalarResult(self.scalar_rows or [])

    def scalar_one_or_none(self):
        rows = self.scalar_rows or []
        return rows[0] if rows else None

    def scalar_one(self):
        if self.scalar_value is None:
            raise AssertionError("scalar_value not configured")
        return self.scalar_value


class _QueueAsyncSession:
    def __init__(self, responses: list[_FakeResult]):
        self._responses = list(responses)
        self.execute_calls = []

    async def execute(self, statement):
        self.execute_calls.append(statement)
        if not self._responses:
            raise AssertionError("Unexpected execute call with no queued response")
        return self._responses.pop(0)

    def query(self, *args, **kwargs):
        raise AssertionError("sync db.query should not be used")


@pytest.mark.asyncio
async def test_template_get_uses_async_get_and_preserves_result():
    template_id = uuid4()
    template = SimpleNamespace(id=template_id, name="monthly", version="1.0")
    db = SimpleNamespace(
        get=AsyncMock(return_value=template),
        execute=AsyncMock(),
    )

    service = QuizTemplateService(db=db, repository=MagicMock())
    result = await service.get_template(template_id)

    assert result is template
    db.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_session_retrieval_uses_async_execute_path():
    patient_id = uuid4()
    active_session = SimpleNamespace(id=uuid4(), patient_id=patient_id, status="started")
    db = _QueueAsyncSession([_FakeResult(scalar_rows=[active_session])])

    service = QuizSessionService(db=db, repository=MagicMock())
    found = await service.get_active_session_async(patient_id)

    assert found is active_session
    assert len(db.execute_calls) == 1


@pytest.mark.asyncio
async def test_response_retrieval_uses_async_execute_path():
    session_id = uuid4()
    responses = [
        SimpleNamespace(question_id="q1", responded_at=datetime.now(timezone.utc)),
        SimpleNamespace(question_id="q2", responded_at=datetime.now(timezone.utc)),
    ]
    db = _QueueAsyncSession([_FakeResult(scalar_rows=responses)])

    service = QuizResponseService(db=db, repository=MagicMock())
    result = await service.get_session_responses_async(session_id)

    assert [item.question_id for item in result] == ["q1", "q2"]
    assert len(db.execute_calls) == 1


@pytest.mark.asyncio
async def test_patient_session_pagination_uses_async_count_and_fetch():
    patient_id = uuid4()
    sessions = [SimpleNamespace(id=uuid4(), patient_id=patient_id, status="started")]
    db = _QueueAsyncSession(
        [
            _FakeResult(scalar_value=1),
            _FakeResult(scalar_rows=sessions),
        ]
    )

    service = QuizSessionService(db=db, repository=MagicMock())
    rows, total = await service.get_patient_sessions_async(patient_id, limit=10, skip=0)

    assert total == 1
    assert len(rows) == 1
    assert rows[0].patient_id == patient_id
    assert len(db.execute_calls) == 2


@pytest.mark.asyncio
async def test_report_generation_uses_async_lookup_and_payload_shape():
    session_id = uuid4()
    session = SimpleNamespace(
        id=session_id,
        patient_id=uuid4(),
        template=SimpleNamespace(name="Template A"),
        responses=[],
        completed_at=None,
        status="started",
    )
    db = _QueueAsyncSession([_FakeResult(scalar_rows=[session])])
    scorer = MagicMock()
    scorer.calculate_session_score.return_value = {
        "total_questions": 3,
        "correct_answers": 2,
        "percentage": 66.67,
    }

    service = QuizReportGenerator(db=db, scorer=scorer, analyzer=MagicMock())
    report = await service.generate_session_report_async(session_id)

    assert report["session_id"] == str(session_id)
    assert report["template_name"] == "Template A"
    assert report["score_data"]["correct_answers"] == 2
    assert "status" in report
    assert len(db.execute_calls) == 1


@pytest.mark.asyncio
async def test_enhanced_quiz_analytics_runs_with_async_execute_and_contract_fields():
    template = SimpleNamespace(id=uuid4(), name="Pain", category="pain_assessment")
    sessions = [
        SimpleNamespace(
            status="completed",
            score=8.5,
            time_spent_seconds=180,
            quiz_template=template,
            quiz_template_id=template.id,
            created_at=datetime(2026, 2, 10, tzinfo=timezone.utc),
        ),
        SimpleNamespace(
            status="started",
            score=None,
            time_spent_seconds=None,
            quiz_template=template,
            quiz_template_id=template.id,
            created_at=datetime(2026, 2, 11, tzinfo=timezone.utc),
        ),
    ]
    db = _QueueAsyncSession([_FakeResult(scalar_rows=sessions)])

    service = EnhancedQuizService(db)
    service._get_cached_result = AsyncMock(return_value=None)
    service._set_cached_result = AsyncMock()

    analytics = await service.get_quiz_analytics(
        start_date=None,
        end_date=None,
        category=None,
        include_trends=False,
        role_enum=UserRole.ADMIN,
        user_uuid=None,
    )

    assert analytics.total_sessions == 2
    assert analytics.completed_sessions == 1
    assert "pain_assessment" in analytics.category_breakdown
    assert analytics.top_templates[0]["template_name"] == "Pain"
    assert len(db.execute_calls) == 1
