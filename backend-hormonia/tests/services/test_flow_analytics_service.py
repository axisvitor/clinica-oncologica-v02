
import pytest
from unittest.mock import MagicMock, Mock
from uuid import uuid4
from datetime import datetime, timedelta
from app.services.analytics.flow_analytics import FlowAnalyticsService, EngagementMetrics
from app.models.message import MessageDirection
from app.models.flow import PatientFlowState, FlowTemplateVersion, FlowKind

@pytest.fixture
def mock_db_session():
    return MagicMock()

@pytest.fixture
def service(mock_db_session):
    return FlowAnalyticsService(mock_db_session)

@pytest.mark.asyncio
async def test_calculate_engagement_metrics_basic(service, mock_db_session):
    # Mock DB result for sent/received counts
    # Result tuple: (sent_count, received_count)
    mock_result = MagicMock()
    mock_result.sent = 10
    mock_result.received = 4
    
    # Configure mock execute return
    mock_db_session.execute.return_value.first.return_value = mock_result
    
    metrics = await service.calculate_engagement_metrics(patient_id=uuid4())
    
    assert metrics.total_messages_sent == 10
    assert metrics.total_responses_received == 4
    assert metrics.response_rate == 0.4  # 4/10
    assert metrics.engagement_score == 4.0 # 0.4 * 10

@pytest.mark.asyncio
async def test_get_flow_performance_metrics_found(service, mock_db_session):
    # Mock FlowKind query
    mock_kind = MagicMock()
    mock_kind.id = uuid4()
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_kind
    
    # Mock Aggregation Result
    # (total, active, completed, dropped)
    mock_result = MagicMock()
    mock_result.total = 100
    mock_result.active = 20
    mock_result.completed = 70
    mock_result.dropped = 10
    
    # Configure execute return for the second query
    mock_db_session.execute.return_value.first.return_value = mock_result
    
    metrics = await service.get_flow_performance_metrics(flow_type="onboarding")
    
    assert metrics["flow_type"] == "onboarding"
    assert metrics["overview"]["total_started"] == 100
    assert metrics["overview"]["completed"] == 70
    assert metrics["overview"]["completion_rate"] == 0.7
    assert metrics["overview"]["drop_off_rate"] == 0.1

@pytest.mark.asyncio
async def test_get_flow_performance_metrics_not_found(service, mock_db_session):
    # Mock FlowKind not found
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    
    metrics = await service.get_flow_performance_metrics(flow_type="nonexistent")
    
    assert "error" in metrics
    assert metrics["error"] == "Flow type not found"
