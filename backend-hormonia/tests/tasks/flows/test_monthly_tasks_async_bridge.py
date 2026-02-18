"""Focused regressions for monthly flow task async bridging."""

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from uuid import uuid4


def _scoped_session(db):
    @contextmanager
    def _ctx():
        yield db

    return _ctx()


def test_process_monthly_quizzes_uses_run_async_with_processing_timeout():
    from app.tasks.flows.monthly_tasks import process_monthly_quizzes

    process_monthly_quizzes.max_retries = None

    db = Mock()
    quiz_trigger_service = Mock()
    quiz_trigger_service.check_and_trigger_monthly_quizzes.return_value = "monthly-coro"
    expected_results = {
        "total_patients": 1,
        "quizzes_sent": 1,
        "failed": 0,
        "skipped": 0,
        "results": [],
    }

    with patch(
        "app.tasks.flows.monthly_tasks.get_scoped_session",
        return_value=_scoped_session(db),
    ), patch(
        "app.domain.quizzes.integration.flow_integration.utils.get_quiz_trigger_service",
        return_value=quiz_trigger_service,
    ), patch(
        "app.tasks.flows.monthly_tasks.run_async", return_value=expected_results
    ) as run_async_mock, patch(
        "app.config.settings.tasks.QUIZ_PROCESSING_TIMEOUT", 33
    ), patch(
        "app.config.settings.tasks.QUIZ_MAX_RETRIES", 7
    ):
        result = process_monthly_quizzes.run(limit=25)

    assert result == expected_results
    quiz_trigger_service.check_and_trigger_monthly_quizzes.assert_called_once_with(
        limit=25
    )
    run_async_mock.assert_called_once_with("monthly-coro", timeout=33)


def test_generate_quiz_report_uses_run_async_with_report_timeout():
    from app.tasks.flows.monthly_tasks import generate_quiz_report

    generate_quiz_report.max_retries = None

    session_id = str(uuid4())
    report_id = uuid4()
    fixed_now = datetime(2026, 1, 10, 14, 0, tzinfo=timezone.utc)

    db = Mock()
    report_generator = Mock()
    report_generator.generate_quiz_report.return_value = "report-coro"

    with patch(
        "app.tasks.flows.monthly_tasks.get_scoped_session",
        return_value=_scoped_session(db),
    ), patch(
        "app.services.reporting.quiz_report_generator.get_quiz_report_generator",
        return_value=report_generator,
    ), patch(
        "app.tasks.flows.monthly_tasks.run_async", return_value=report_id
    ) as run_async_mock, patch(
        "app.tasks.flows.monthly_tasks.now_sao_paulo", return_value=fixed_now
    ), patch(
        "app.config.settings.tasks.QUIZ_REPORT_TIMEOUT", 44
    ), patch(
        "app.config.settings.tasks.QUIZ_MAX_RETRIES", 7
    ):
        result = generate_quiz_report.run(session_id=session_id)

    assert result["status"] == "success"
    assert result["session_id"] == session_id
    assert result["report_id"] == str(report_id)
    assert result["generated_at"] == fixed_now.isoformat()
    run_async_mock.assert_called_once_with("report-coro", timeout=44)
