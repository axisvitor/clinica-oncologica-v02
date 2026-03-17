"""Focused regressions for monthly flow task async bridging (Taskiq version)."""

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest


def _scoped_session(db):
    @contextmanager
    def _ctx():
        yield db

    return _ctx()


@pytest.mark.asyncio
async def test_process_monthly_quizzes_calls_trigger_service():
    from app.tasks.flows_taskiq import process_monthly_quizzes

    db = Mock()
    quiz_trigger_service = Mock()
    quiz_trigger_service.check_and_trigger_monthly_quizzes = AsyncMock(
        return_value={
            "total_patients": 1,
            "quizzes_sent": 1,
            "failed": 0,
            "skipped": 0,
            "results": [],
        }
    )

    mock_async_db = AsyncMock()

    with patch(
        "app.tasks.flows_taskiq.get_scoped_session",
        return_value=_scoped_session(db),
    ) as _gs, patch(
        "app.domain.quizzes.integration.flow_integration.utils.get_quiz_trigger_service",
        return_value=quiz_trigger_service,
    ):
        # Inline lazy imports inside flows_taskiq.process_monthly_quizzes
        with patch("app.database.get_scoped_session", return_value=_scoped_session(db)):
            result = await process_monthly_quizzes.fn(limit=25, db=mock_async_db)

    assert result["total_patients"] == 1
    assert result["quizzes_sent"] == 1
    quiz_trigger_service.check_and_trigger_monthly_quizzes.assert_awaited_once_with(
        limit=25
    )


@pytest.mark.asyncio
async def test_generate_quiz_report_returns_success_with_report_id():
    from app.tasks.flows_taskiq import generate_quiz_report

    session_id = str(uuid4())
    report_id = uuid4()
    fixed_now = datetime(2026, 1, 10, 14, 0, tzinfo=timezone.utc)

    db = Mock()
    report_generator = Mock()
    report_generator.generate_quiz_report = AsyncMock(return_value=report_id)
    mock_async_db = AsyncMock()

    with patch(
        "app.database.get_scoped_session",
        return_value=_scoped_session(db),
    ), patch(
        "app.services.reporting.quiz_report_generator.get_quiz_report_generator",
        return_value=report_generator,
    ), patch(
        "app.tasks.flows_taskiq.now_sao_paulo", return_value=fixed_now
    ):
        result = await generate_quiz_report.fn(session_id=session_id, db=mock_async_db)

    assert result["status"] == "success"
    assert result["session_id"] == session_id
    assert result["report_id"] == str(report_id)
    assert result["generated_at"] == fixed_now.isoformat()
