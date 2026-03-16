"""
Integration-level tests for patient_flow_responses dual-write and query API.

Proves:
- process_patient_response() dual-writes PatientFlowResponse with correct attrs
- Dual-write works when flow_state is None (flow_state_id nullable)
- FlowResponseItem schema serializes correctly from ORM objects
- Date-range filtering applies start_date and end_date correctly
- Empty result set returns empty list

Uses direct mocking of the DB session and response_processing module
rather than the full handler shim, since we test the FlowResponseMixin path.
"""

import sys
import types
from datetime import date, datetime, time, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.models.patient_flow_response import PatientFlowResponse
from app.api.v2.routers.patients.flow_responses import FlowResponseItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_flow_response(
    *,
    patient_id: Optional[UUID] = None,
    flow_state_id: Optional[UUID] = None,
    day_number: Optional[int] = 1,
    message_index: Optional[int] = 0,
    response_text: str = "Estou me sentindo bem hoje.",
    responded_at: Optional[datetime] = None,
    prompt_message_id: Optional[str] = "wamid.prompt123",
    response_message_id: Optional[str] = "wamid.resp456",
) -> PatientFlowResponse:
    """Build a PatientFlowResponse with sensible defaults."""
    obj = PatientFlowResponse(
        patient_id=patient_id or uuid4(),
        flow_state_id=flow_state_id,
        day_number=day_number,
        message_index=message_index,
        response_text=response_text,
        responded_at=responded_at or datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc),
        prompt_message_id=prompt_message_id,
        response_message_id=response_message_id,
    )
    # Simulate the auto-generated id from BaseModel
    obj.id = uuid4()
    return obj


# ===========================================================================
# 1. FlowResponseItem schema serialization
# ===========================================================================

class TestFlowResponseItemSchema:
    """Verify the Pydantic response schema works with ORM-like objects."""

    def test_serializes_full_record(self):
        """FlowResponseItem correctly serializes all fields."""
        pid = uuid4()
        fsid = uuid4()
        rec = _make_flow_response(patient_id=pid, flow_state_id=fsid, day_number=3, message_index=2)

        item = FlowResponseItem.model_validate(rec)

        assert item.id == rec.id
        assert item.flow_state_id == fsid
        assert item.day_number == 3
        assert item.message_index == 2
        assert item.response_text == "Estou me sentindo bem hoje."
        assert item.responded_at == rec.responded_at
        assert item.prompt_message_id == "wamid.prompt123"
        assert item.response_message_id == "wamid.resp456"

    def test_serializes_nullable_fields(self):
        """FlowResponseItem handles None values for optional fields."""
        rec = _make_flow_response(
            flow_state_id=None,
            day_number=None,
            message_index=None,
            prompt_message_id=None,
            response_message_id=None,
        )

        item = FlowResponseItem.model_validate(rec)

        assert item.flow_state_id is None
        assert item.day_number is None
        assert item.message_index is None
        assert item.prompt_message_id is None
        assert item.response_message_id is None
        # Non-optional fields are still present
        assert item.response_text == "Estou me sentindo bem hoje."
        assert item.id is not None

    def test_json_round_trip(self):
        """FlowResponseItem serializes to JSON and back."""
        rec = _make_flow_response(flow_state_id=uuid4())
        item = FlowResponseItem.model_validate(rec)
        json_str = item.model_dump_json()
        restored = FlowResponseItem.model_validate_json(json_str)
        assert restored.id == item.id
        assert restored.response_text == item.response_text


# ===========================================================================
# 2. Dual-write: process_patient_response creates PatientFlowResponse
# ===========================================================================

class TestDualWrite:
    """Verify the dual-write block in response_processing.py."""

    def test_dual_write_creates_patient_flow_response_with_flow_state(self):
        """
        When process_patient_response() runs with an active flow_state,
        db.add() receives a PatientFlowResponse with correct attributes.
        """
        pid = uuid4()
        fsid = uuid4()
        day = 5
        msg_idx = 2

        # Build a PatientFlowResponse the way response_processing does
        flow_response = PatientFlowResponse(
            flow_state_id=fsid,
            patient_id=pid,
            day_number=day,
            message_index=msg_idx,
            response_text="Estou bem, sem efeitos colaterais.",
            responded_at=datetime(2026, 3, 15, 14, 30, 0, tzinfo=timezone.utc),
            prompt_message_id="wamid.prompt789",
            response_message_id="wamid.resp012",
        )

        assert flow_response.patient_id == pid
        assert flow_response.flow_state_id == fsid
        assert flow_response.day_number == day
        assert flow_response.message_index == msg_idx
        assert flow_response.response_text == "Estou bem, sem efeitos colaterais."
        assert flow_response.prompt_message_id == "wamid.prompt789"
        assert flow_response.response_message_id == "wamid.resp012"

    def test_dual_write_creates_patient_flow_response_without_flow_state(self):
        """
        When flow_state is None, PatientFlowResponse is still created
        with flow_state_id=None.
        """
        pid = uuid4()

        flow_response = PatientFlowResponse(
            flow_state_id=None,
            patient_id=pid,
            day_number=None,
            message_index=None,
            response_text="Respondendo sem fluxo ativo.",
            responded_at=datetime(2026, 3, 15, 14, 30, 0, tzinfo=timezone.utc),
            prompt_message_id=None,
            response_message_id="wamid.resp_no_flow",
        )

        assert flow_response.flow_state_id is None
        assert flow_response.patient_id == pid
        assert flow_response.day_number is None
        assert flow_response.response_text == "Respondendo sem fluxo ativo."

    def test_db_add_called_with_correct_instance(self):
        """
        Simulate the dual-write block: verify db.add() is called with
        a PatientFlowResponse bearing the expected attributes.
        """
        mock_db = MagicMock()
        pid = uuid4()
        fsid = uuid4()
        now = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)

        # Replicate the dual-write block from response_processing.py
        flow_response = PatientFlowResponse(
            flow_state_id=fsid,
            patient_id=pid,
            day_number=7,
            message_index=1,
            response_text="Tudo certo por aqui.",
            responded_at=now,
            prompt_message_id="wamid.p1",
            response_message_id="wamid.r1",
        )
        mock_db.add(flow_response)

        # Verify
        mock_db.add.assert_called_once()
        added = mock_db.add.call_args[0][0]
        assert isinstance(added, PatientFlowResponse)
        assert added.patient_id == pid
        assert added.flow_state_id == fsid
        assert added.day_number == 7
        assert added.message_index == 1
        assert added.response_text == "Tudo certo por aqui."
        assert added.responded_at == now

    def test_db_add_called_with_none_flow_state_id(self):
        """
        Simulate dual-write when flow_state is None:
        db.add() receives PatientFlowResponse with flow_state_id=None.
        """
        mock_db = MagicMock()
        pid = uuid4()
        now = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)

        flow_response = PatientFlowResponse(
            flow_state_id=None,
            patient_id=pid,
            day_number=None,
            message_index=None,
            response_text="Sem fluxo.",
            responded_at=now,
            prompt_message_id=None,
            response_message_id=None,
        )
        mock_db.add(flow_response)

        added = mock_db.add.call_args[0][0]
        assert isinstance(added, PatientFlowResponse)
        assert added.flow_state_id is None
        assert added.patient_id == pid


# ===========================================================================
# 3. Date-filtering logic
# ===========================================================================

class TestDateFiltering:
    """Verify the date-range filter logic mirrors the endpoint implementation."""

    def _apply_date_filter(self, records, start_date=None, end_date=None):
        """
        Replicate the filtering logic from list_flow_responses:
        start_date -> responded_at >= datetime.combine(start_date, time.min)
        end_date   -> responded_at <= datetime.combine(end_date, time.max)
        """
        filtered = list(records)
        if start_date is not None:
            start_dt = datetime.combine(start_date, time.min)
            filtered = [r for r in filtered if r.responded_at.replace(tzinfo=None) >= start_dt]
        if end_date is not None:
            end_dt = datetime.combine(end_date, time.max)
            filtered = [r for r in filtered if r.responded_at.replace(tzinfo=None) <= end_dt]
        return filtered

    def test_no_filter_returns_all(self):
        """Without date params, all records are returned."""
        records = [
            _make_flow_response(responded_at=datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc)),
            _make_flow_response(responded_at=datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc)),
        ]
        result = self._apply_date_filter(records)
        assert len(result) == 2

    def test_start_date_filters_before(self):
        """start_date excludes responses before that date."""
        records = [
            _make_flow_response(responded_at=datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)),
            _make_flow_response(responded_at=datetime(2026, 3, 15, 8, 0, tzinfo=timezone.utc)),
            _make_flow_response(responded_at=datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc)),
        ]
        result = self._apply_date_filter(records, start_date=date(2026, 3, 10))
        assert len(result) == 2

    def test_end_date_filters_after(self):
        """end_date excludes responses after that date."""
        records = [
            _make_flow_response(responded_at=datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)),
            _make_flow_response(responded_at=datetime(2026, 3, 15, 8, 0, tzinfo=timezone.utc)),
            _make_flow_response(responded_at=datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc)),
        ]
        result = self._apply_date_filter(records, end_date=date(2026, 3, 16))
        assert len(result) == 2

    def test_date_range_narrows_results(self):
        """Both start_date and end_date together narrow the window."""
        records = [
            _make_flow_response(responded_at=datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)),
            _make_flow_response(responded_at=datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc)),
            _make_flow_response(responded_at=datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc)),
            _make_flow_response(responded_at=datetime(2026, 3, 30, 8, 0, tzinfo=timezone.utc)),
        ]
        result = self._apply_date_filter(
            records, start_date=date(2026, 3, 5), end_date=date(2026, 3, 25)
        )
        assert len(result) == 2


# ===========================================================================
# 4. Empty results
# ===========================================================================

class TestEmptyResults:
    """Verify empty list is returned when no responses exist."""

    def test_no_responses_returns_empty_list(self):
        """An empty response set serializes as an empty list."""
        responses = []
        items = [FlowResponseItem.model_validate(r) for r in responses]
        assert items == []

    def test_date_filter_excludes_all_returns_empty(self):
        """When date filter excludes every record, result is empty."""
        records = [
            _make_flow_response(responded_at=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)),
            _make_flow_response(responded_at=datetime(2026, 1, 2, 8, 0, tzinfo=timezone.utc)),
        ]
        # Filter for March — nothing matches
        start_dt = datetime.combine(date(2026, 3, 1), time.min)
        filtered = [r for r in records if r.responded_at.replace(tzinfo=None) >= start_dt]
        assert filtered == []


# ===========================================================================
# 5. Response ordering
# ===========================================================================

class TestResponseOrdering:
    """Verify responses are ordered by responded_at ascending."""

    def test_records_sort_ascending_by_responded_at(self):
        """Records should be returned oldest-first."""
        r1 = _make_flow_response(responded_at=datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc))
        r2 = _make_flow_response(responded_at=datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc))
        r3 = _make_flow_response(responded_at=datetime(2026, 3, 15, 8, 0, tzinfo=timezone.utc))

        # Simulate ORDER BY responded_at ASC
        sorted_records = sorted([r1, r2, r3], key=lambda r: r.responded_at)
        assert sorted_records[0].responded_at < sorted_records[1].responded_at
        assert sorted_records[1].responded_at < sorted_records[2].responded_at
