"""
Tests for SummaryDataAggregator integration with flow responses and alert fixes.

Verifies:
- Flow response aggregation, formatting, and prompt context
- Alert aggregation uses description (not message) and extracts recommendation
- Prompt context includes flow_responses and flow_response_count
"""

import pytest
from datetime import date, datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ai.summary_data_aggregator import (
    AggregatedPatientData,
    SummaryDataAggregator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_aggregated_data(**overrides) -> AggregatedPatientData:
    """Create an AggregatedPatientData with sensible defaults, applying overrides."""
    defaults = dict(
        patient_id=uuid4(),
        patient_name="Maria Silva",
        treatment_type="Hormonal",
        treatment_phase="Fase 2",
        current_day=30,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
        quiz_count=0,
        quiz_responses=[],
        message_count=0,
        messages_summary=[],
        alert_count=0,
        alerts=[],
        flow_response_count=0,
        flow_responses=[],
        response_rate=0.0,
        avg_response_time_minutes=0.0,
        total_messages_sent=0,
        total_messages_received=0,
    )
    defaults.update(overrides)
    return AggregatedPatientData(**defaults)


def _make_flow_response_model(
    patient_id, day_number, response_text, responded_at, message_index=0
):
    """Create a mock PatientFlowResponse row."""
    obj = MagicMock()
    obj.patient_id = patient_id
    obj.day_number = day_number
    obj.message_index = message_index
    obj.response_text = response_text
    obj.responded_at = responded_at
    return obj


def _make_alert_model(
    patient_id,
    description,
    severity_value="high",
    alert_type="symptom_alert",
    data=None,
    created_at=None,
):
    """Create a mock Alert row."""
    obj = MagicMock()
    obj.patient_id = patient_id
    obj.description = description
    obj.alert_type = alert_type
    obj.data = data or {}
    obj.created_at = created_at or datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)
    # severity is an enum-like object with .value
    sev = MagicMock()
    sev.value = severity_value
    obj.severity = sev
    # Alert model does NOT have a .message attribute
    if hasattr(obj, "message"):
        del obj.message
    return obj


# ---------------------------------------------------------------------------
# AggregatedPatientData — flow response formatting
# ---------------------------------------------------------------------------


class TestFormatFlowResponses:
    """Tests for _format_flow_responses() on AggregatedPatientData."""

    def test_aggregate_flow_responses_formats_correctly(self):
        """Flow responses are formatted as '- [DD/MM/YYYY] Dia N: text'."""
        data = _make_aggregated_data(
            flow_response_count=2,
            flow_responses=[
                {
                    "day_number": 1,
                    "response_text": "Estou me sentindo bem hoje.",
                    "date": "01/01/2025",
                    "message_index": 0,
                },
                {
                    "day_number": 3,
                    "response_text": "Um pouco de náusea.",
                    "date": "03/01/2025",
                    "message_index": 0,
                },
            ],
        )
        result = data._format_flow_responses()
        assert "- [01/01/2025] Dia 1: Estou me sentindo bem hoje." in result
        assert "- [03/01/2025] Dia 3: Um pouco de náusea." in result

    def test_aggregate_flow_responses_empty(self):
        """Empty flow responses return the fallback message."""
        data = _make_aggregated_data(flow_response_count=0, flow_responses=[])
        result = data._format_flow_responses()
        assert result == "Nenhuma resposta de acompanhamento no período."

    def test_flow_responses_limited_to_20(self):
        """When > 20 responses exist, only the 20 most recent are shown."""
        responses = [
            {
                "day_number": i,
                "response_text": f"Resposta dia {i}",
                "date": f"{i:02d}/01/2025",
                "message_index": 0,
            }
            for i in range(1, 26)  # 25 responses
        ]
        data = _make_aggregated_data(
            flow_response_count=25,
            flow_responses=responses,
        )
        result = data._format_flow_responses()
        lines = result.strip().split("\n")
        # 20 response lines + 1 "... e mais N respostas anteriores" line
        assert len(lines) == 21
        assert "Dia 6:" in lines[0]  # Most recent 20 = items 6-25
        assert "Dia 25:" in lines[19]
        assert "... e mais 5 respostas anteriores" in lines[20]


# ---------------------------------------------------------------------------
# AggregatedPatientData — prompt context
# ---------------------------------------------------------------------------


class TestPromptContext:
    """Tests for to_prompt_context() including flow responses."""

    def test_prompt_context_includes_flow_responses(self):
        """to_prompt_context() has flow_responses key with formatted content."""
        data = _make_aggregated_data(
            flow_response_count=1,
            flow_responses=[
                {
                    "day_number": 1,
                    "response_text": "Tudo bem.",
                    "date": "01/01/2025",
                    "message_index": 0,
                },
            ],
        )
        ctx = data.to_prompt_context()
        assert "flow_responses" in ctx
        assert "Dia 1:" in ctx["flow_responses"]
        assert "Tudo bem." in ctx["flow_responses"]

    def test_prompt_context_includes_flow_response_count(self):
        """to_prompt_context() has flow_response_count key."""
        data = _make_aggregated_data(flow_response_count=5, flow_responses=[])
        ctx = data.to_prompt_context()
        assert "flow_response_count" in ctx
        assert ctx["flow_response_count"] == 5


# ---------------------------------------------------------------------------
# Alert aggregation fixes
# ---------------------------------------------------------------------------


class TestAlertAggregation:
    """Tests for fixed alert aggregation and formatting."""

    def test_alert_aggregation_uses_description_not_message(self):
        """Alert formatting uses description field, not message."""
        data = _make_aggregated_data(
            alert_count=1,
            alerts=[
                {
                    "date": "15/01/2025",
                    "severity": "high",
                    "description": "Dor severa reportada",
                    "title": "Alerta de Sintoma",
                    "recommendation": "",
                },
            ],
        )
        result = data._format_alerts()
        assert "Dor severa reportada" in result
        assert "Alerta de Sintoma" in result
        # Should NOT contain the word "message" as a field artifact
        assert "message" not in result.lower() or "mensag" in result.lower()

    def test_alert_aggregation_extracts_recommendation(self):
        """Alert formatting includes recommendation from JSONB data when present."""
        data = _make_aggregated_data(
            alert_count=1,
            alerts=[
                {
                    "date": "15/01/2025",
                    "severity": "critical",
                    "description": "Vômito persistente",
                    "title": "Náusea Severa",
                    "recommendation": "Avaliar antiemético imediatamente",
                },
            ],
        )
        result = data._format_alerts()
        assert "Vômito persistente" in result
        assert "Náusea Severa" in result
        assert "(Recomendação: Avaliar antiemético imediatamente)" in result

    def test_alert_formatting_without_recommendation(self):
        """Alert without recommendation does not include the parenthetical."""
        data = _make_aggregated_data(
            alert_count=1,
            alerts=[
                {
                    "date": "15/01/2025",
                    "severity": "low",
                    "description": "Leve desconforto",
                    "title": "Alerta",
                    "recommendation": "",
                },
            ],
        )
        result = data._format_alerts()
        assert "Recomendação:" not in result
        assert "Leve desconforto" in result


# ---------------------------------------------------------------------------
# SummaryDataAggregator — _aggregate_flow_responses DB query
# ---------------------------------------------------------------------------


class TestAggregateFlowResponsesDB:
    """Tests for SummaryDataAggregator._aggregate_flow_responses() DB interaction."""

    @pytest.mark.asyncio
    async def test_aggregate_flow_responses_formats_correctly(self):
        """DB rows are formatted into the expected dict structure."""
        patient_id = uuid4()
        mock_responses = [
            _make_flow_response_model(
                patient_id, 1, "Estou bem", datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc), 0
            ),
            _make_flow_response_model(
                patient_id, 2, "Dor leve", datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc), 1
            ),
        ]

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_responses
        mock_db.execute.return_value = mock_result

        aggregator = SummaryDataAggregator(db=mock_db)
        result = await aggregator._aggregate_flow_responses(
            patient_id, date(2025, 1, 1), date(2025, 1, 31)
        )

        assert result["count"] == 2
        assert len(result["responses"]) == 2
        assert result["responses"][0]["day_number"] == 1
        assert result["responses"][0]["response_text"] == "Estou bem"
        assert result["responses"][0]["date"] == "01/01/2025"
        assert result["responses"][1]["message_index"] == 1

    @pytest.mark.asyncio
    async def test_aggregate_flow_responses_empty(self):
        """Empty result set returns count 0 and empty list."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        aggregator = SummaryDataAggregator(db=mock_db)
        result = await aggregator._aggregate_flow_responses(
            uuid4(), date(2025, 1, 1), date(2025, 1, 31)
        )

        assert result["count"] == 0
        assert result["responses"] == []

    @pytest.mark.asyncio
    async def test_aggregate_flow_responses_respects_date_range(self):
        """The query filters by responded_at within [start_dt, end_dt]."""
        patient_id = uuid4()
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        aggregator = SummaryDataAggregator(db=mock_db)
        await aggregator._aggregate_flow_responses(
            patient_id, date(2025, 2, 1), date(2025, 2, 28)
        )

        # Verify execute was called (the query uses the date range)
        mock_db.execute.assert_called_once()
        # Extract the compiled query to verify date range is in the WHERE clause
        call_args = mock_db.execute.call_args
        query = call_args[0][0]
        # The query object should have PatientFlowResponse.responded_at comparisons
        query_str = str(query)
        assert "patient_flow_responses" in query_str
        assert "responded_at" in query_str


# ---------------------------------------------------------------------------
# SummaryDataAggregator — _aggregate_alerts DB query (fixed)
# ---------------------------------------------------------------------------


class TestAggregateAlertsDB:
    """Tests for fixed _aggregate_alerts() in SummaryDataAggregator."""

    @pytest.mark.asyncio
    async def test_alert_aggregation_uses_description_not_message(self):
        """Alert rows use .description, not .message (which doesn't exist on the model)."""
        patient_id = uuid4()
        mock_alert = _make_alert_model(
            patient_id=patient_id,
            description="Febre alta reportada",
            severity_value="high",
            alert_type="symptom_alert",
            data={},
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_alert]
        mock_db.execute.return_value = mock_result

        aggregator = SummaryDataAggregator(db=mock_db)
        result = await aggregator._aggregate_alerts(
            patient_id, date(2025, 1, 1), date(2025, 1, 31)
        )

        assert result["count"] == 1
        assert result["alerts"][0]["description"] == "Febre alta reportada"
        assert "message" not in result["alerts"][0]

    @pytest.mark.asyncio
    async def test_alert_aggregation_extracts_recommendation(self):
        """Alert aggregation extracts recommendation and rule_name from JSONB data."""
        patient_id = uuid4()
        mock_alert = _make_alert_model(
            patient_id=patient_id,
            description="Náusea persistente",
            severity_value="critical",
            alert_type="symptom_alert",
            data={
                "recommendation": "Prescrever ondansetrona",
                "rule_name": "Náusea Severa",
            },
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_alert]
        mock_db.execute.return_value = mock_result

        aggregator = SummaryDataAggregator(db=mock_db)
        result = await aggregator._aggregate_alerts(
            patient_id, date(2025, 1, 1), date(2025, 1, 31)
        )

        alert = result["alerts"][0]
        assert alert["title"] == "Náusea Severa"
        assert alert["recommendation"] == "Prescrever ondansetrona"
        assert alert["description"] == "Náusea persistente"
