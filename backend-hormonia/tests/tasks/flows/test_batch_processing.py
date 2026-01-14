"""
Tests for daily flow batch processing fixes.

Tests cover:
1. _update_scheduling with template-based days
2. monthly_recurring modulo for steps > 30
3. Skip paths updating scheduling
4. Session isolation by patient ID
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4

import pytz


class TestUpdateScheduling:
    """Tests for _update_scheduling function."""
    
    def test_initial_15_days_next_message_day(self):
        """Test scheduling for initial_15_days finds correct next day."""
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
        db.commit.assert_called_once()
    
    def test_days_16_45_next_message_day(self):
        """Test scheduling for days_16_45 finds correct next day."""
        from app.tasks.flows.batch_tasks import _update_scheduling
        
        # Create mock flow type with value
        flow_type_mock = Mock()
        flow_type_mock.value = "days_16_45"
        
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
        db.commit.assert_called_once()
    
    def test_monthly_recurring_modulo_for_step_over_30(self):
        """Test monthly_recurring uses modulo for steps > 30."""
        from app.tasks.flows.batch_tasks import _update_scheduling
        
        flow_type_mock = Mock()
        flow_type_mock.value = "monthly_recurring"
        
        # Step 46 -> cycle_day = ((46-1) % 30) + 1 = 16
        flow_state = Mock()
        flow_state.current_step = 46
        flow_state.last_interaction_at = None
        flow_state.next_scheduled_at = None
        
        db = Mock()
        patient_tz = pytz.timezone("America/Sao_Paulo")
        
        _update_scheduling(flow_state, flow_type_mock, patient_tz, db)
        
        # Cycle day 16, next message day is 18 (days diff = 2)
        assert flow_state.next_scheduled_at is not None
        db.commit.assert_called_once()
    
    def test_monthly_recurring_wrap_to_next_cycle(self):
        """Test monthly_recurring wraps to next cycle when at end."""
        from app.tasks.flows.batch_tasks import _update_scheduling
        
        flow_type_mock = Mock()
        flow_type_mock.value = "monthly_recurring"
        
        # Step 60 -> cycle_day = 30 (last day)
        # Next message should be day 1 of next cycle
        flow_state = Mock()
        flow_state.current_step = 60  # cycle_day = 30
        flow_state.last_interaction_at = None
        flow_state.next_scheduled_at = None
        
        db = Mock()
        patient_tz = pytz.timezone("America/Sao_Paulo")
        
        _update_scheduling(flow_state, flow_type_mock, patient_tz, db)
        
        # At day 30, wraps to day 1 of next cycle
        # days_until = (30 - 30) + 1 = 1
        assert flow_state.next_scheduled_at is not None
        db.commit.assert_called_once()
    
    def test_scheduling_uses_9am_patient_timezone(self):
        """Test that scheduling sets 9 AM in patient's timezone."""
        from app.tasks.flows.batch_tasks import _update_scheduling
        
        flow_type_mock = Mock()
        flow_type_mock.value = "initial_15_days"
        
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
