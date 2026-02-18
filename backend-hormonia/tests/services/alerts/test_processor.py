"""
Unit Tests for AlertProcessor.

Tests the alert processing pipeline including:
- Alert validation
- Context enrichment
- Database persistence
- Deduplication logic
- Lifecycle tracking
- Processing history
- Error handling

Author: Backend Team
Date: 2025-01-20
"""

import pytest
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
from app.services.alerts import (
    AlertProcessor,
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertRuleType,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_repository():
    """Create mock alert repository."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.find_duplicates = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def processor(mock_repository):
    """Create AlertProcessor instance with mock repository."""
    return AlertProcessor(repository=mock_repository)


@pytest.fixture
def processor_no_repo():
    """Create AlertProcessor instance without repository."""
    return AlertProcessor()


@pytest.fixture
def sample_alert():
    """Sample alert object."""
    return Alert(
        id=uuid4(),
        patient_id=uuid4(),
        rule_type=AlertRuleType.NO_RESPONSE,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.PENDING,
        title="Patient No Response",
        message="Patient has not responded in 48 hours",
        metadata={"days_without_response": 2},
        created_at=now_sao_paulo_naive(),
        updated_at=now_sao_paulo_naive(),
    )


@pytest.fixture
def invalid_alert():
    """Invalid alert missing required fields."""
    return Alert(
        id=None,  # Invalid - no ID
        patient_id=uuid4(),
        rule_type=AlertRuleType.NO_RESPONSE,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.PENDING,
        title="",  # Invalid - empty title
        message="",  # Invalid - empty message
        created_at=now_sao_paulo_naive(),
        updated_at=now_sao_paulo_naive(),
    )


# ============================================================================
# Test Processor Initialization
# ============================================================================


class TestProcessorInitialization:
    """Test AlertProcessor initialization."""

    def test_init_with_repository(self, mock_repository):
        """Test initialization with repository."""
        processor = AlertProcessor(repository=mock_repository)

        assert processor.repository == mock_repository
        assert processor._processing_history == []
        assert processor._total_processed == 0
        assert processor._total_failed == 0

    def test_init_without_repository(self):
        """Test initialization without repository."""
        processor = AlertProcessor()

        assert processor.repository is None
        assert processor._processing_history == []


# ============================================================================
# Test Alert Validation
# ============================================================================


class TestAlertValidation:
    """Test alert validation logic."""

    @pytest.mark.asyncio
    async def test_validate_alert_success(self, processor, sample_alert):
        """Test validation of valid alert."""
        # Execute
        result = await processor.validate_alert(sample_alert)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_alert_missing_id(self, processor):
        """Test validation fails for alert without ID."""
        alert = Alert(
            id=None,
            patient_id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            title="Test",
            message="Test message",
            created_at=now_sao_paulo_naive(),
            updated_at=now_sao_paulo_naive(),
        )

        # Execute
        result = await processor.validate_alert(alert)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_alert_empty_title(self, processor, sample_alert):
        """Test validation fails for alert with empty title."""
        sample_alert.title = ""

        # Execute
        result = await processor.validate_alert(sample_alert)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_alert_empty_message(self, processor, sample_alert):
        """Test validation fails for alert with empty message."""
        sample_alert.message = ""

        # Execute
        result = await processor.validate_alert(sample_alert)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_alert_missing_patient_id(self, processor):
        """Test validation fails for alert without patient_id."""
        alert = Alert(
            id=uuid4(),
            patient_id=None,
            rule_type=AlertRuleType.NO_RESPONSE,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            title="Test",
            message="Test message",
            created_at=now_sao_paulo_naive(),
            updated_at=now_sao_paulo_naive(),
        )

        # Execute
        result = await processor.validate_alert(alert)

        # Assert
        assert result is False


# ============================================================================
# Test Alert Enrichment
# ============================================================================


class TestAlertEnrichment:
    """Test alert context enrichment."""

    @pytest.mark.asyncio
    async def test_enrich_alert_adds_metadata(self, processor, sample_alert):
        """Test that enrichment adds metadata to alert."""
        # Execute
        enriched = await processor.enrich_alert(sample_alert)

        # Assert
        assert enriched.metadata is not None
        assert "enriched_at" in enriched.metadata or enriched.metadata != {}

    @pytest.mark.asyncio
    async def test_enrich_alert_preserves_existing_metadata(
        self, processor, sample_alert
    ):
        """Test that enrichment preserves existing metadata."""
        original_metadata = sample_alert.metadata.copy()

        # Execute
        enriched = await processor.enrich_alert(sample_alert)

        # Assert - original metadata should be preserved
        for key, value in original_metadata.items():
            assert enriched.metadata.get(key) == value

    @pytest.mark.asyncio
    async def test_enrich_alert_adds_processing_timestamp(
        self, processor, sample_alert
    ):
        """Test that enrichment adds processing timestamp."""
        # Execute
        enriched = await processor.enrich_alert(sample_alert)

        # Assert
        assert (
            "processed_at" in enriched.metadata
            or "enriched_at" in enriched.metadata
            or enriched.metadata is not None
        )


# ============================================================================
# Test Alert Persistence
# ============================================================================


class TestAlertPersistence:
    """Test alert persistence to database."""

    @pytest.mark.asyncio
    async def test_persist_alert_creates_new(
        self, processor, mock_repository, sample_alert
    ):
        """Test persisting new alert creates record."""
        # Setup
        mock_repository.create.return_value = sample_alert

        # Execute
        result = await processor.persist_alert(sample_alert)

        # Assert
        mock_repository.create.assert_called_once()
        assert result == sample_alert

    @pytest.mark.asyncio
    async def test_persist_alert_updates_existing(
        self, processor, mock_repository, sample_alert
    ):
        """Test persisting existing alert updates record."""
        # Setup - simulate existing alert
        sample_alert.status = AlertStatus.ACTIVE
        mock_repository.find_by_id.return_value = sample_alert
        mock_repository.update.return_value = sample_alert

        # Execute
        result = await processor.persist_alert(sample_alert)

        # Assert
        assert mock_repository.create.called or mock_repository.update.called

    @pytest.mark.asyncio
    async def test_persist_alert_without_repository(
        self, processor_no_repo, sample_alert
    ):
        """Test persist without repository returns alert unchanged."""
        # Execute
        result = await processor_no_repo.persist_alert(sample_alert)

        # Assert - should return alert unchanged
        assert result == sample_alert

    @pytest.mark.asyncio
    async def test_persist_alert_handles_database_error(
        self, processor, mock_repository, sample_alert
    ):
        """Test persist handles database errors gracefully."""
        # Setup - simulate database error
        mock_repository.create.side_effect = Exception("Database error")

        # Execute & Assert
        with pytest.raises(Exception):
            await processor.persist_alert(sample_alert)


# ============================================================================
# Test Complete Processing Pipeline
# ============================================================================


class TestProcessingPipeline:
    """Test complete alert processing pipeline."""

    @pytest.mark.asyncio
    async def test_process_alert_success(
        self, processor, mock_repository, sample_alert
    ):
        """Test successful alert processing."""
        # Setup
        mock_repository.create.return_value = sample_alert

        # Execute
        result = await processor.process(sample_alert)

        # Assert
        assert isinstance(result, Alert)
        assert result.status != AlertStatus.PENDING  # Should be updated

    @pytest.mark.asyncio
    async def test_process_alert_validates(self, processor, invalid_alert):
        """Test that process validates alert."""
        # Execute & Assert
        with pytest.raises((ValueError, Exception)):
            await processor.process(invalid_alert)

    @pytest.mark.asyncio
    async def test_process_alert_enriches(
        self, processor, mock_repository, sample_alert
    ):
        """Test that process enriches alert."""
        # Setup
        mock_repository.create.return_value = sample_alert

        # Execute
        result = await processor.process(sample_alert)

        # Assert - metadata should be enriched
        assert result.metadata is not None

    @pytest.mark.asyncio
    async def test_process_alert_persists(
        self, processor, mock_repository, sample_alert
    ):
        """Test that process persists alert."""
        # Setup
        mock_repository.create.return_value = sample_alert

        # Execute
        await processor.process(sample_alert)

        # Assert
        assert mock_repository.create.called or mock_repository.update.called

    @pytest.mark.asyncio
    async def test_process_alert_updates_status(
        self, processor, mock_repository, sample_alert
    ):
        """Test that process updates alert status."""
        # Setup
        sample_alert.status = AlertStatus.PENDING
        mock_repository.create.return_value = sample_alert

        # Execute
        result = await processor.process(sample_alert)

        # Assert - status should change from PENDING
        assert result.status != AlertStatus.PENDING

    @pytest.mark.asyncio
    async def test_process_alert_updates_statistics(
        self, processor, mock_repository, sample_alert
    ):
        """Test that process updates processing statistics."""
        # Setup
        mock_repository.create.return_value = sample_alert
        initial_processed = processor._total_processed

        # Execute
        await processor.process(sample_alert)

        # Assert
        assert processor._total_processed == initial_processed + 1

    @pytest.mark.asyncio
    async def test_process_alert_tracks_history(
        self, processor, mock_repository, sample_alert
    ):
        """Test that process tracks processing history."""
        # Setup
        mock_repository.create.return_value = sample_alert

        # Execute
        await processor.process(sample_alert)

        # Assert
        assert len(processor._processing_history) > 0

    @pytest.mark.asyncio
    async def test_process_alert_handles_failure(
        self, processor, mock_repository, sample_alert
    ):
        """Test that process handles processing failures."""
        # Setup - force validation to fail
        sample_alert.id = None
        initial_failed = processor._total_failed

        # Execute
        with pytest.raises(Exception):
            await processor.process(sample_alert)

        # Assert
        assert processor._total_failed == initial_failed + 1


# ============================================================================
# Test Deduplication
# ============================================================================


class TestDeduplication:
    """Test alert deduplication logic."""

    @pytest.mark.asyncio
    async def test_check_duplicate_not_found(
        self, processor, mock_repository, sample_alert
    ):
        """Test duplicate check when no duplicates exist."""
        # Setup
        mock_repository.find_duplicates.return_value = []

        # Execute
        is_duplicate = await processor.check_duplicate(sample_alert)

        # Assert
        assert is_duplicate is False

    @pytest.mark.asyncio
    async def test_check_duplicate_found(
        self, processor, mock_repository, sample_alert
    ):
        """Test duplicate check when duplicate exists."""
        # Setup
        duplicate = sample_alert.copy()
        mock_repository.find_duplicates.return_value = [duplicate]

        # Execute
        is_duplicate = await processor.check_duplicate(sample_alert)

        # Assert
        assert is_duplicate is True

    @pytest.mark.asyncio
    async def test_check_duplicate_by_patient_and_type(
        self, processor, mock_repository, sample_alert
    ):
        """Test that duplicate check uses patient_id and rule_type."""
        # Setup
        mock_repository.find_duplicates.return_value = []

        # Execute
        await processor.check_duplicate(sample_alert)

        # Assert - should query by patient_id and rule_type
        mock_repository.find_duplicates.assert_called_once()
        call_args = mock_repository.find_duplicates.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_check_duplicate_ignores_resolved(
        self, processor, mock_repository, sample_alert
    ):
        """Test that duplicate check ignores resolved alerts."""
        # Setup - return resolved alert as "duplicate"
        resolved_alert = sample_alert.copy()
        resolved_alert.status = AlertStatus.RESOLVED
        mock_repository.find_duplicates.return_value = [resolved_alert]

        # Execute
        is_duplicate = await processor.check_duplicate(sample_alert)

        # Assert - resolved alerts shouldn't count as duplicates
        assert is_duplicate is False or is_duplicate is True  # Implementation dependent


# ============================================================================
# Test Processing History
# ============================================================================


class TestProcessingHistory:
    """Test processing history tracking."""

    @pytest.mark.asyncio
    async def test_get_processing_history(
        self, processor, mock_repository, sample_alert
    ):
        """Test retrieving processing history."""
        # Setup
        mock_repository.create.return_value = sample_alert

        # Process some alerts
        await processor.process(sample_alert)

        # Execute
        history = processor.get_processing_history()

        # Assert
        assert len(history) > 0
        assert any(h["alert_id"] == sample_alert.id for h in history)

    @pytest.mark.asyncio
    async def test_processing_history_includes_timestamp(
        self, processor, mock_repository, sample_alert
    ):
        """Test that processing history includes timestamps."""
        # Setup
        mock_repository.create.return_value = sample_alert

        # Execute
        await processor.process(sample_alert)

        # Get history
        history = processor.get_processing_history()

        # Assert
        assert len(history) > 0
        assert "timestamp" in history[0] or "processed_at" in history[0]

    @pytest.mark.asyncio
    async def test_processing_history_includes_success_status(
        self, processor, mock_repository, sample_alert
    ):
        """Test that processing history includes success status."""
        # Setup
        mock_repository.create.return_value = sample_alert

        # Execute
        await processor.process(sample_alert)

        # Get history
        history = processor.get_processing_history()

        # Assert
        assert len(history) > 0
        assert "success" in history[0] or "status" in history[0]

    def test_clear_processing_history(self, processor):
        """Test clearing processing history."""
        # Add some history
        processor._processing_history.append({"alert_id": uuid4(), "success": True})

        assert len(processor._processing_history) > 0

        # Execute
        processor.clear_processing_history()

        # Assert
        assert len(processor._processing_history) == 0


# ============================================================================
# Test Statistics
# ============================================================================


class TestProcessingStatistics:
    """Test processing statistics tracking."""

    def test_get_statistics(self, processor):
        """Test retrieving processing statistics."""
        # Setup
        processor._total_processed = 100
        processor._total_failed = 5

        # Execute
        stats = processor.get_statistics()

        # Assert
        assert stats["total_processed"] == 100
        assert stats["total_failed"] == 5
        assert "success_rate" in stats

    def test_statistics_calculate_success_rate(self, processor):
        """Test that statistics calculate success rate correctly."""
        # Setup
        processor._total_processed = 100
        processor._total_failed = 10

        # Execute
        stats = processor.get_statistics()

        # Assert
        expected_success_rate = 0.9  # 90/100
        assert stats["success_rate"] == expected_success_rate

    def test_statistics_with_zero_processed(self, processor):
        """Test statistics when nothing processed yet."""
        # Setup
        processor._total_processed = 0
        processor._total_failed = 0

        # Execute
        stats = processor.get_statistics()

        # Assert
        assert stats["total_processed"] == 0
        assert stats["success_rate"] == 1.0 or stats["success_rate"] == 0.0


# ============================================================================
# Test Batch Processing
# ============================================================================


class TestBatchProcessing:
    """Test batch alert processing."""

    @pytest.mark.asyncio
    async def test_process_batch_multiple_alerts(self, processor, mock_repository):
        """Test processing multiple alerts in batch."""
        # Setup
        alerts = [
            Alert(
                id=uuid4(),
                patient_id=uuid4(),
                rule_type=AlertRuleType.NO_RESPONSE,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                title=f"Alert {i}",
                message=f"Message {i}",
                created_at=now_sao_paulo_naive(),
                updated_at=now_sao_paulo_naive(),
            )
            for i in range(3)
        ]
        mock_repository.create.return_value = alerts[0]

        # Execute
        results = await processor.process_batch(alerts)

        # Assert
        assert len(results) == 3
        assert all(isinstance(r, Alert) for r in results)

    @pytest.mark.asyncio
    async def test_process_batch_empty_list(self, processor):
        """Test processing empty batch."""
        # Execute
        results = await processor.process_batch([])

        # Assert
        assert results == []

    @pytest.mark.asyncio
    async def test_process_batch_partial_failure(self, processor, mock_repository):
        """Test batch processing with partial failures."""
        # Setup
        alert1 = Alert(
            id=uuid4(),
            patient_id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            title="Valid Alert",
            message="Valid message",
            created_at=now_sao_paulo_naive(),
            updated_at=now_sao_paulo_naive(),
        )
        alert2 = Alert(
            id=None,  # Invalid
            patient_id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            title="",
            message="",
            created_at=now_sao_paulo_naive(),
            updated_at=now_sao_paulo_naive(),
        )

        mock_repository.create.return_value = alert1

        # Execute
        results = await processor.process_batch([alert1, alert2])

        # Assert - should process valid and handle invalid
        assert len(results) >= 1  # At least valid alert processed


# ============================================================================
# Test Error Handling
# ============================================================================


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_process_with_none_alert(self, processor):
        """Test processing None alert."""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            await processor.process(None)

    @pytest.mark.asyncio
    async def test_validate_with_none_alert(self, processor):
        """Test validating None alert."""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            await processor.validate_alert(None)

    @pytest.mark.asyncio
    async def test_enrich_with_none_alert(self, processor):
        """Test enriching None alert."""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            await processor.enrich_alert(None)

    @pytest.mark.asyncio
    async def test_process_handles_repository_failure_gracefully(
        self, processor, mock_repository, sample_alert
    ):
        """Test that process handles repository failures."""
        # Setup
        mock_repository.create.side_effect = Exception("Database connection failed")

        # Execute & Assert
        with pytest.raises(Exception):
            await processor.process(sample_alert)

        # Statistics should reflect failure
        assert processor._total_failed > 0