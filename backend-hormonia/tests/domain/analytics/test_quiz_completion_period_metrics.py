from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.domain.analytics.metrics_collector import MetricsCollector
from app.domain.analytics.report_builder import ReportBuilder
from app.models.quiz import QuizResponse
from app.schemas.report import PatientAnalytics
from app.utils.timezone import now_sao_paulo


def _build_query_spy():
    query = MagicMock()
    query._filters = []

    def _filter(*args):
        query._filters.extend(args)
        return query

    query.filter.side_effect = _filter
    query.count.return_value = 0
    query.scalar.return_value = 0
    query.all.return_value = []
    return query


def test_get_system_metrics_uses_responded_at_for_completed_quizzes():
    db = MagicMock()
    queries = []

    def _query_side_effect(entity, *args, **kwargs):
        query = _build_query_spy()
        query._entity = entity
        queries.append(query)
        return query

    db.query.side_effect = _query_side_effect

    collector = MetricsCollector(db)
    collector.get_system_metrics(start_date=None, end_date=None)

    quiz_queries = [q for q in queries if q._entity is QuizResponse]
    assert len(quiz_queries) >= 2
    for query in quiz_queries:
        filters_sql = " ".join(str(f) for f in query._filters)
        assert "responded_at" in filters_sql
        assert "created_at" not in filters_sql


def test_add_quiz_metrics_counts_responses_by_responded_at_window():
    db = MagicMock()
    query = _build_query_spy()
    query.all.return_value = [
        SimpleNamespace(responded_at=now_sao_paulo()),
        SimpleNamespace(responded_at=now_sao_paulo()),
    ]
    db.query.return_value = query

    collector = MetricsCollector(db)
    analytics = PatientAnalytics(
        patient_id=uuid4(),
        patient_name="Paciente",
        treatment_type="Hormonioterapia",
        current_day=10,
    )

    collector._add_quiz_metrics(
        analytics=analytics,
        patient_id=uuid4(),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    filters_sql = " ".join(str(f) for f in query._filters)
    assert "responded_at" in filters_sql
    assert "created_at" not in filters_sql
    assert analytics.quizzes_completed == 2
    assert analytics.quiz_completion_rate > 0


def test_get_quizzes_completed_last_days_filters_by_responded_at():
    db = MagicMock()
    query = _build_query_spy()
    db.query.return_value = query

    collector = MetricsCollector(db)
    collector.get_quizzes_completed_last_days(days=7, doctor_id=None)

    filters_sql = " ".join(str(f) for f in query._filters)
    assert "responded_at" in filters_sql
    assert "created_at" not in filters_sql


def test_report_builder_quiz_trends_uses_responded_at_period():
    db = MagicMock()
    query = _build_query_spy()
    query.all.return_value = [SimpleNamespace(), SimpleNamespace()]
    db.query.return_value = query

    builder = ReportBuilder(db=db, metrics_collector=MagicMock())
    result = builder._analyze_quiz_trends(
        patient_id=None,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    filters_sql = " ".join(str(f) for f in query._filters)
    assert "responded_at" in filters_sql
    assert "created_at" not in filters_sql
    assert result["total_completions"] == 2
