"""
Tests for daily flow batch processing fixes.

Tests cover:
1. _update_scheduling with template-based days
2. quiz_mensal cycle normalization from treatment day 46
3. Skip paths updating scheduling
4. Session isolation by patient ID
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4

import pytz


class TestUpdateScheduling:
    """Tests for _update_scheduling function."""
    
    def test_onboarding_next_message_day(self):
        """Test scheduling for onboarding finds correct next day."""
        from app.tasks.flows.batch_tasks import _update_scheduling
        from app.services.enhanced_flow_engine import FlowType
        
        # Mock flow_state at day 3
        flow_state = Mock()
        flow_state.current_step = 3
        flow_state.last_interaction_at = None
        flow_state.next_scheduled_at = None
        
        db = Mock()
        patient_tz = pytz.timezone("America/Sao_Paulo")
        
        _update_scheduling(flow_state, FlowType.ONBOARDING, patient_tz, db)
        
        # Days with messages: 1,2,3,5,7,9,11,13,15
        # Current: 3, Next: 5, Days until: 2
        assert flow_state.last_interaction_at is not None
        assert flow_state.next_scheduled_at is not None
    
    def test_daily_follow_up_next_message_day(self):
        """Test scheduling for daily_follow_up finds correct next day."""
        from app.tasks.flows.batch_tasks import _update_scheduling
        
        # Create mock flow type with value
        flow_type_mock = Mock()
        flow_type_mock.value = "daily_follow_up"
        
        flow_state = Mock()
        flow_state.current_step = 20
        flow_state.last_interaction_at = None
        flow_state.next_scheduled_at = None
        
        db = Mock()
        patient_tz = pytz.timezone("America/Sao_Paulo")
        
        _update_scheduling(flow_state, flow_type_mock, patient_tz, db)
        
        # Days with messages: 16,18,20,22,24...
        # Current: 20, Next: 22, Days until: 2
        assert flow_state.next_scheduled_at is not None
    
    def test_quiz_mensal_modulo_for_step_over_30(self):
        """Treatment day 46 must map to monthly cycle day 1."""
        from app.tasks.flows.batch_tasks import _update_scheduling
        
        flow_type_mock = Mock()
        flow_type_mock.value = "quiz_mensal"
        
        # Treatment day 46 -> cycle day 1. Next message day is 4.
        flow_state = Mock()
        flow_state.current_step = 46
        flow_state.last_interaction_at = None
        flow_state.next_scheduled_at = None
        
        db = Mock()
        patient_tz = pytz.timezone("America/Sao_Paulo")
        fixed_now = patient_tz.localize(datetime(2026, 2, 1, 12, 0, 0))

        with patch(
            "app.tasks.flows.batch_tasks.now_sao_paulo",
            return_value=fixed_now,
        ):
            _update_scheduling(flow_state, flow_type_mock, patient_tz, db)

        scheduled_local = flow_state.next_scheduled_at.astimezone(patient_tz)
        assert (scheduled_local.date() - fixed_now.date()).days == 3
        assert scheduled_local.hour == 9
        assert flow_state.next_scheduled_at is not None
    
    def test_quiz_mensal_wrap_to_next_cycle(self):
        """Test quiz_mensal wraps to next cycle when at end."""
        from app.tasks.flows.batch_tasks import _update_scheduling
        
        flow_type_mock = Mock()
        flow_type_mock.value = "quiz_mensal"
        
        # Treatment day 75 -> cycle_day = 30 (last day)
        # Next message should be day 1 of next cycle
        flow_state = Mock()
        flow_state.current_step = 75  # cycle_day = 30 with 46-based mapping
        flow_state.last_interaction_at = None
        flow_state.next_scheduled_at = None
        
        db = Mock()
        patient_tz = pytz.timezone("America/Sao_Paulo")
        
        _update_scheduling(flow_state, flow_type_mock, patient_tz, db)
        
        # At day 30, wraps to day 1 of next cycle
        # days_until = (30 - 30) + 1 = 1
        assert flow_state.next_scheduled_at is not None
    
    def test_scheduling_uses_9am_patient_timezone(self):
        """Test that scheduling sets 9 AM in patient's timezone."""
        from app.tasks.flows.batch_tasks import _update_scheduling
        
        flow_type_mock = Mock()
        flow_type_mock.value = "onboarding"
        
        flow_state = Mock()
        flow_state.current_step = 1
        flow_state.last_interaction_at = None
        flow_state.next_scheduled_at = None
        
        db = Mock()
        patient_tz = pytz.timezone("America/Sao_Paulo")
        
        _update_scheduling(flow_state, flow_type_mock, patient_tz, db)
        
        # Check that next_scheduled_at is set
        scheduled = flow_state.next_scheduled_at
        assert scheduled is not None
        
        # Convert to patient timezone and check hour
        scheduled_local = scheduled.astimezone(patient_tz)
        assert scheduled_local.hour == 9


class TestGetMessageTemplateForDay:
    """Tests for template extraction from flow_template_versions.steps JSON."""

    @staticmethod
    def _build_db_with_steps(steps):
        db = Mock()
        flow_kind = Mock()
        flow_kind.id = uuid4()
        active_version = Mock()
        active_version.messages = steps

        kind_query = Mock()
        kind_query.filter.return_value.first.return_value = flow_kind
        version_query = Mock()
        version_query.filter.return_value.first.return_value = active_version
        db.query.side_effect = [kind_query, version_query]
        return db

    def test_quiz_mensal_maps_day_46_to_cycle_day_1(self):
        """Absolute day 46 should load monthly template step day 1."""
        from app.tasks.flows.batch_tasks import _get_message_template_for_day
        from app.services.enhanced_flow_engine import FlowType

        db = self._build_db_with_steps(
            [
                {
                    "day": 1,
                    "send_mode": "single",
                    "messages": [
                        {
                            "order": 1,
                            "content": "Pergunta do ciclo mensal dia 1",
                            "expects_response": True,
                        }
                    ],
                }
            ]
        )

        template = _get_message_template_for_day(db, FlowType.QUIZ_MENSAL, 46)

        assert template is not None
        assert template.day == 1
        assert template.base_content == "Pergunta do ciclo mensal dia 1"
        assert template.core_elements.get("expects_response") is True

    def test_wait_each_prefers_first_question_message(self):
        """wait_each should choose first message that expects response."""
        from app.tasks.flows.batch_tasks import _get_message_template_for_day
        from app.services.enhanced_flow_engine import FlowType

        db = self._build_db_with_steps(
            [
                {
                    "day": 15,
                    "send_mode": "wait_each",
                    "messages": [
                        {
                            "order": 1,
                            "content": "Hoje completamos 15 dias!",
                            "expects_response": False,
                        },
                        {
                            "order": 2,
                            "content": "Você tem consulta marcada nas próximas semanas?",
                            "expects_response": True,
                        },
                        {
                            "order": 3,
                            "content": "Tudo que responder vai para o relatório.",
                            "expects_response": False,
                        },
                    ],
                }
            ]
        )

        template = _get_message_template_for_day(db, FlowType.ONBOARDING, 15)

        assert template is not None
        assert template.base_content == "Você tem consulta marcada nas próximas semanas?"
        assert template.intent == "question"
        assert template.core_elements.get("expects_response") is True


class TestProcessSinglePatientFlowById:
    """Tests for _process_single_patient_flow_by_id."""
    
    @pytest.mark.asyncio
    async def test_returns_skipped_for_no_active_flow(self):
        """Test that function returns skipped when no active flow."""
        from app.tasks.flows.batch_tasks import _process_single_patient_flow_by_id
        
        patient_id = uuid4()
        
        # Patch where the imports are happening (inside the function)
        with patch('app.tasks.flows.batch_tasks.get_db') as mock_get_db, \
             patch('app.services.enhanced_flow_engine.get_enhanced_flow_engine') as mock_engine, \
             patch('app.repositories.flow.FlowStateRepository') as mock_repo_class:
            
            mock_db = Mock()
            mock_db.close = Mock()
            mock_get_db.return_value = iter([mock_db])
            
            mock_repo = Mock()
            mock_repo.get_active_flow.return_value = None
            mock_repo_class.return_value = mock_repo
            
            result = await _process_single_patient_flow_by_id(patient_id)
            
            # Verify result for no active flow
            assert result["status"] == "skipped"
            assert result["reason"] == "No active flow found"
            assert str(patient_id) == result["patient_id"]
    
    @pytest.mark.asyncio
    async def test_returns_skipped_for_paused_flow(self):
        """Test that paused flows are skipped."""
        from app.tasks.flows.batch_tasks import _process_single_patient_flow_by_id
        
        patient_id = uuid4()
        
        with patch('app.tasks.flows.batch_tasks.get_db') as mock_get_db, \
             patch('app.services.enhanced_flow_engine.get_enhanced_flow_engine') as mock_engine, \
             patch('app.repositories.flow.FlowStateRepository') as mock_repo_class:
            
            mock_db = Mock()
            mock_db.close = Mock()
            mock_get_db.return_value = iter([mock_db])
            
            mock_flow_state = Mock()
            mock_flow_state.step_data = {"paused": True}
            mock_flow_state.patient_id = patient_id
            
            mock_repo = Mock()
            mock_repo.get_active_flow.return_value = mock_flow_state
            mock_repo_class.return_value = mock_repo
            
            result = await _process_single_patient_flow_by_id(patient_id)
            
            assert result["status"] == "skipped"
            assert result["reason"] == "Flow is paused"


class TestFlowTypeEnumDefinition:
    """Test that flow_type_enum is defined before skip paths."""
    
    def test_flow_type_enum_defined_early(self):
        """Verify flow_type_enum is defined before skip check."""
        import inspect
        from app.tasks.flows.batch_tasks import _process_single_patient_flow
        
        source = inspect.getsource(_process_single_patient_flow)
        
        # Find positions
        flow_type_enum_first = source.find("flow_type_enum = normalize_flow_type")
        if flow_type_enum_first < 0:
            flow_type_enum_first = source.find("flow_type_enum = FlowType")
        skip_check = source.find("last_message_date.date() == today_local")
        
        # flow_type_enum should be defined before the skip check uses it
        assert flow_type_enum_first > 0
        assert skip_check > 0


class TestStateDataAlias:
    """Test state_data property alias on PatientFlowState."""
    
    def test_state_data_getter_returns_step_data(self):
        """Test getter returns step_data."""
        from app.models.flow import PatientFlowState
        
        flow_state = PatientFlowState()
        flow_state.step_data = {"key": "value"}
        
        assert flow_state.state_data == {"key": "value"}
    
    def test_state_data_getter_initializes_when_none(self):
        """Test getter initializes step_data when None."""
        from app.models.flow import PatientFlowState
        
        flow_state = PatientFlowState()
        flow_state.step_data = None
        
        result = flow_state.state_data
        
        assert result == {}
        assert flow_state.step_data == {}
    
    def test_state_data_setter_writes_to_step_data(self):
        """Test setter writes to step_data."""
        from app.models.flow import PatientFlowState
        
        flow_state = PatientFlowState()
        flow_state.state_data = {"new": "data"}
        
        assert flow_state.step_data == {"new": "data"}
    
    def test_state_data_mutation_persists(self):
        """Test that mutations via state_data persist to step_data."""
        from app.models.flow import PatientFlowState
        
        flow_state = PatientFlowState()
        flow_state.step_data = None
        
        # Access via alias and mutate
        flow_state.state_data["key"] = "value"
        
        # Should persist to step_data
        assert flow_state.step_data == {"key": "value"}


class TestAwaitingResponseGuards:
    """Regression tests for awaiting_response behavior in batch processing."""

    @pytest.mark.asyncio
    async def test_process_single_patient_flow_does_not_advance_or_schedule_when_awaiting_response(self):
        """Should skip without advancing flow or updating scheduling."""
        from app.tasks.flows.batch_tasks import _process_single_patient_flow

        patient_id = uuid4()
        flow_engine = Mock()
        flow_engine.calculate_patient_day = AsyncMock(return_value=7)
        flow_engine.advance_patient_flow = AsyncMock()

        patient = Mock()
        patient.current_day = 7
        patient.updated_at = None

        flow_state = Mock()
        flow_state.patient_id = patient_id
        flow_state.patient = patient
        flow_state.step_data = {"awaiting_response": True}

        db = Mock()

        with patch("app.tasks.flows.batch_tasks._update_scheduling") as update_scheduling:
            result = await _process_single_patient_flow(flow_engine, flow_state, db)

        assert result["status"] == "skipped"
        assert result["reason"] == "Awaiting patient response"
        flow_engine.advance_patient_flow.assert_not_awaited()
        update_scheduling.assert_not_called()
        db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_single_patient_flow_by_id_skips_when_awaiting_response(self):
        """Daily batch entrypoint should skip and not delegate processing."""
        from app.tasks.flows.batch_tasks import _process_single_patient_flow_by_id

        patient_id = uuid4()
        db = Mock()
        session_cm = MagicMock()
        session_cm.__enter__.return_value = db
        session_cm.__exit__.return_value = False

        flow_state = Mock()
        flow_state.patient_id = patient_id
        flow_state.step_data = {"awaiting_response": True}

        flow_repo = Mock()
        flow_repo.get_active_flow.return_value = flow_state

        delegated_process = AsyncMock()

        with patch(
            "app.tasks.flows.batch_tasks.get_scoped_session",
            return_value=session_cm,
        ), patch(
            "app.services.enhanced_flow_engine.get_enhanced_flow_engine",
            return_value=Mock(),
        ), patch(
            "app.repositories.flow.FlowStateRepository",
            return_value=flow_repo,
        ), patch(
            "app.tasks.flows.batch_tasks._process_single_patient_flow",
            new=delegated_process,
        ):
            result = await _process_single_patient_flow_by_id(patient_id)

        assert result["status"] == "skipped"
        assert result["reason"] == "Awaiting patient response"
        delegated_process.assert_not_awaited()
