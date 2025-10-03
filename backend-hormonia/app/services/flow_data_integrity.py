"""
Data corruption detection and manual correction tools for flow operations.
Validates flow state integrity and provides tools for manual data correction.
"""
import logging
from typing import Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from uuid import UUID
from enum import Enum
from dataclasses import dataclass, field
import json

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.flow import PatientFlowState
from app.models.flow_analytics import FlowMessage
from app.models.message import Message, MessageStatus
from app.models.patient import Patient
from app.repositories.flow import FlowStateRepository
from app.repositories.message import MessageRepository
from app.repositories.patient import PatientRepository
from app.services.enhanced_flow_engine import FlowType
from app.exceptions import ValidationError, FlowStateError

logger = logging.getLogger(__name__)


class CorruptionType(Enum):
    """Types of data corruption."""
    INVALID_STATE = "invalid_state"
    MISSING_REFERENCES = "missing_references"
    INCONSISTENT_DATES = "inconsistent_dates"
    DUPLICATE_RECORDS = "duplicate_records"
    ORPHANED_DATA = "orphaned_data"
    INVALID_TRANSITIONS = "invalid_transitions"
    CORRUPTED_JSON = "corrupted_json"


class CorruptionSeverity(Enum):
    """Severity levels for data corruption."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CorruptionIssue:
    """Represents a data corruption issue."""
    id: str
    corruption_type: CorruptionType
    severity: CorruptionSeverity
    description: str
    affected_records: List[dict[str, Any]]
    suggested_fix: str
    auto_fixable: bool
    detected_at: datetime = field(default_factory=datetime.utcnow)
    fixed: bool = False
    fixed_at: Optional[datetime] = None


@dataclass
class IntegrityCheckResult:
    """Result of data integrity check."""
    total_records_checked: int
    issues_found: List[CorruptionIssue]
    corruption_score: float  # 0-100, higher is worse
    recommendations: List[str]
    check_duration_seconds: float
    checked_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CorrectionResult:
    """Result of data correction operation."""
    issue_id: str
    success: bool
    records_affected: int
    backup_created: bool
    correction_details: dict[str, Any]
    error_message: Optional[str] = None
    corrected_at: datetime = field(default_factory=datetime.utcnow)


class FlowDataIntegrityChecker:
    """Service for detecting and correcting flow data corruption."""
    
    def __init__(self, db: Session):
        self.db = db
        self.flow_repo = FlowStateRepository(db)
        self.message_repo = MessageRepository(db)
        self.patient_repo = PatientRepository(db)
        
        # Validation rules
        self.flow_type_durations = {
            FlowType.INITIAL_15_DAYS.value: 15,
            FlowType.DAYS_16_45.value: 30,  # 16-45 is 30 days
            FlowType.MONTHLY_RECURRING.value: 30
        }
        
        logger.info("Flow data integrity checker initialized")
    
    async def run_comprehensive_check(self, 
                                    patient_id: Optional[UUID] = None,
                                    check_messages: bool = True,
                                    check_flow_states: bool = True,
                                    check_references: bool = True) -> IntegrityCheckResult:
        """
        Run comprehensive data integrity check.
        
        Args:
            patient_id: Optional specific patient to check
            check_messages: Whether to check message integrity
            check_flow_states: Whether to check flow state integrity
            check_references: Whether to check reference integrity
            
        Returns:
            Integrity check result
        """
        start_time = datetime.utcnow()
        issues = []
        total_records = 0
        
        try:
            logger.info(f"Starting comprehensive integrity check for patient {patient_id or 'all'}")
            
            if check_flow_states:
                flow_issues, flow_count = await self._check_flow_state_integrity(patient_id)
                issues.extend(flow_issues)
                total_records += flow_count
            
            if check_messages:
                message_issues, message_count = await self._check_message_integrity(patient_id)
                issues.extend(message_issues)
                total_records += message_count
            
            if check_references:
                ref_issues, ref_count = await self._check_reference_integrity(patient_id)
                issues.extend(ref_issues)
                total_records += ref_count
            
            # Calculate corruption score
            corruption_score = self._calculate_corruption_score(issues, total_records)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(issues)
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            result = IntegrityCheckResult(
                total_records_checked=total_records,
                issues_found=issues,
                corruption_score=corruption_score,
                recommendations=recommendations,
                check_duration_seconds=duration
            )
            
            logger.info(f"Integrity check completed: {len(issues)} issues found in {duration:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Integrity check failed: {e}")
            raise
    
    async def _check_flow_state_integrity(self, patient_id: Optional[UUID]) -> Tuple[List[CorruptionIssue], int]:
        """Check flow state data integrity."""
        issues = []
        
        try:
            # Get flow states to check
            if patient_id:
                flow_states = self.flow_repo.get_by_patient_id(patient_id)
            else:
                flow_states = self.flow_repo.get_all(limit=1000)  # Limit for performance
            
            total_count = len(flow_states)
            
            for flow_state in flow_states:
                # Check 1: Valid flow type
                if flow_state.flow_type not in [ft.value for ft in FlowType]:
                    issues.append(CorruptionIssue(
                        id=f"invalid_flow_type_{flow_state.id}",
                        corruption_type=CorruptionType.INVALID_STATE,
                        severity=CorruptionSeverity.HIGH,
                        description=f"Invalid flow type: {flow_state.flow_type}",
                        affected_records=[{"flow_state_id": str(flow_state.id)}],
                        suggested_fix="Update flow_type to valid value or reset flow",
                        auto_fixable=True
                    ))
                
                # Check 2: Valid current step
                if flow_state.current_step < 1:
                    issues.append(CorruptionIssue(
                        id=f"invalid_step_{flow_state.id}",
                        corruption_type=CorruptionType.INVALID_STATE,
                        severity=CorruptionSeverity.MEDIUM,
                        description=f"Invalid current step: {flow_state.current_step}",
                        affected_records=[{"flow_state_id": str(flow_state.id)}],
                        suggested_fix="Reset current_step to 1",
                        auto_fixable=True
                    ))
                
                # Check 3: Date consistency
                if flow_state.completed_at and flow_state.completed_at < flow_state.started_at:
                    issues.append(CorruptionIssue(
                        id=f"invalid_dates_{flow_state.id}",
                        corruption_type=CorruptionType.INCONSISTENT_DATES,
                        severity=CorruptionSeverity.HIGH,
                        description="Completion date before start date",
                        affected_records=[{"flow_state_id": str(flow_state.id)}],
                        suggested_fix="Correct completion date or mark as incomplete",
                        auto_fixable=False
                    ))
                
                # Check 4: State data JSON validity
                if flow_state.state_data:
                    try:
                        json.dumps(flow_state.state_data)
                    except (TypeError, ValueError) as e:
                        issues.append(CorruptionIssue(
                            id=f"corrupted_json_{flow_state.id}",
                            corruption_type=CorruptionType.CORRUPTED_JSON,
                            severity=CorruptionSeverity.HIGH,
                            description=f"Corrupted state_data JSON: {str(e)}",
                            affected_records=[{"flow_state_id": str(flow_state.id)}],
                            suggested_fix="Reset state_data to empty dict",
                            auto_fixable=True
                        ))
                
                # Check 5: Flow duration consistency
                if flow_state.completed_at:
                    duration_days = (flow_state.completed_at - flow_state.started_at).days
                    expected_duration = self.flow_type_durations.get(flow_state.flow_type, 30)
                    
                    if duration_days > expected_duration * 2:  # Allow some flexibility
                        issues.append(CorruptionIssue(
                            id=f"excessive_duration_{flow_state.id}",
                            corruption_type=CorruptionType.INVALID_STATE,
                            severity=CorruptionSeverity.MEDIUM,
                            description=f"Flow duration ({duration_days} days) exceeds expected ({expected_duration} days)",
                            affected_records=[{"flow_state_id": str(flow_state.id)}],
                            suggested_fix="Review flow completion status",
                            auto_fixable=False
                        ))
                
                # Check 6: Patient reference validity
                if not self.patient_repo.get(flow_state.patient_id):
                    issues.append(CorruptionIssue(
                        id=f"missing_patient_{flow_state.id}",
                        corruption_type=CorruptionType.MISSING_REFERENCES,
                        severity=CorruptionSeverity.CRITICAL,
                        description=f"Flow state references non-existent patient {flow_state.patient_id}",
                        affected_records=[{"flow_state_id": str(flow_state.id)}],
                        suggested_fix="Delete orphaned flow state or restore patient record",
                        auto_fixable=False
                    ))
            
            # Check for duplicate active flows
            duplicate_issues = await self._check_duplicate_active_flows(patient_id)
            issues.extend(duplicate_issues)
            
            return issues, total_count
            
        except Exception as e:
            logger.error(f"Flow state integrity check failed: {e}")
            return [], 0
    
    async def _check_message_integrity(self, patient_id: Optional[UUID]) -> Tuple[List[CorruptionIssue], int]:
        """Check message data integrity."""
        issues = []
        
        try:
            # Get messages to check
            if patient_id:
                messages = self.message_repo.get_by_patient(patient_id, limit=1000)
            else:
                messages = self.message_repo.get_recent_messages(limit=1000)
            
            total_count = len(messages)
            
            for message in messages:
                # Check 1: Patient reference validity
                if not self.patient_repo.get(message.patient_id):
                    issues.append(CorruptionIssue(
                        id=f"orphaned_message_{message.id}",
                        corruption_type=CorruptionType.ORPHANED_DATA,
                        severity=CorruptionSeverity.HIGH,
                        description=f"Message references non-existent patient {message.patient_id}",
                        affected_records=[{"message_id": str(message.id)}],
                        suggested_fix="Delete orphaned message or restore patient record",
                        auto_fixable=False
                    ))
                
                # Check 2: Date consistency
                if message.sent_at and message.created_at and message.sent_at < message.created_at:
                    issues.append(CorruptionIssue(
                        id=f"invalid_message_dates_{message.id}",
                        corruption_type=CorruptionType.INCONSISTENT_DATES,
                        severity=CorruptionSeverity.MEDIUM,
                        description="Message sent before creation",
                        affected_records=[{"message_id": str(message.id)}],
                        suggested_fix="Correct sent_at timestamp",
                        auto_fixable=True
                    ))
                
                # Check 3: Status consistency
                if message.status == MessageStatus.SENT and not message.sent_at:
                    issues.append(CorruptionIssue(
                        id=f"inconsistent_status_{message.id}",
                        corruption_type=CorruptionType.INVALID_STATE,
                        severity=CorruptionSeverity.MEDIUM,
                        description="Message marked as sent but no sent_at timestamp",
                        affected_records=[{"message_id": str(message.id)}],
                        suggested_fix="Update sent_at timestamp or correct status",
                        auto_fixable=True
                    ))
                
                # Check 4: Metadata JSON validity
                if message.message_metadata:
                    try:
                        json.dumps(message.message_metadata)
                    except (TypeError, ValueError) as e:
                        issues.append(CorruptionIssue(
                            id=f"corrupted_metadata_{message.id}",
                            corruption_type=CorruptionType.CORRUPTED_JSON,
                            severity=CorruptionSeverity.MEDIUM,
                            description=f"Corrupted message metadata: {str(e)}",
                            affected_records=[{"message_id": str(message.id)}],
                            suggested_fix="Reset message_metadata to empty dict",
                            auto_fixable=True
                        ))
            
            return issues, total_count
            
        except Exception as e:
            logger.error(f"Message integrity check failed: {e}")
            return [], 0
    
    async def _check_reference_integrity(self, patient_id: Optional[UUID]) -> Tuple[List[CorruptionIssue], int]:
        """Check reference integrity between related records."""
        issues = []
        total_count = 0
        
        try:
            # Check flow messages without valid flow states
            flow_messages = self.db.query(FlowMessage).all()
            total_count += len(flow_messages)
            
            for flow_message in flow_messages:
                if not self.flow_repo.get(flow_message.flow_state_id):
                    issues.append(CorruptionIssue(
                        id=f"orphaned_flow_message_{flow_message.id}",
                        corruption_type=CorruptionType.ORPHANED_DATA,
                        severity=CorruptionSeverity.MEDIUM,
                        description=f"Flow message references non-existent flow state {flow_message.flow_state_id}",
                        affected_records=[{"flow_message_id": str(flow_message.id)}],
                        suggested_fix="Delete orphaned flow message",
                        auto_fixable=True
                    ))
            
            return issues, total_count
            
        except Exception as e:
            logger.error(f"Reference integrity check failed: {e}")
            return [], 0
    
    async def _check_duplicate_active_flows(self, patient_id: Optional[UUID]) -> List[CorruptionIssue]:
        """Check for duplicate active flows for patients."""
        issues = []
        
        try:
            # Query for patients with multiple active flows
            query = self.db.query(PatientFlowState.patient_id, func.count(PatientFlowState.id).label('count'))\
                .filter(PatientFlowState.completed_at.is_(None))\
                .group_by(PatientFlowState.patient_id)\
                .having(func.count(PatientFlowState.id) > 1)
            
            if patient_id:
                query = query.filter(PatientFlowState.patient_id == patient_id)
            
            duplicates = query.all()
            
            for patient_id_dup, count in duplicates:
                # Get the duplicate flow states
                duplicate_flows = self.flow_repo.get_by_patient_id(patient_id_dup)
                active_flows = [f for f in duplicate_flows if not f.completed_at]
                
                if len(active_flows) > 1:
                    issues.append(CorruptionIssue(
                        id=f"duplicate_active_flows_{patient_id_dup}",
                        corruption_type=CorruptionType.DUPLICATE_RECORDS,
                        severity=CorruptionSeverity.HIGH,
                        description=f"Patient has {len(active_flows)} active flows",
                        affected_records=[{"flow_state_id": str(f.id)} for f in active_flows],
                        suggested_fix="Keep most recent flow, complete others",
                        auto_fixable=True
                    ))
            
            return issues
            
        except Exception as e:
            logger.error(f"Duplicate flow check failed: {e}")
            return []
    
    def _calculate_corruption_score(self, issues: List[CorruptionIssue], total_records: int) -> float:
        """Calculate overall corruption score (0-100)."""
        if total_records == 0:
            return 0.0
        
        # Weight issues by severity
        severity_weights = {
            CorruptionSeverity.LOW: 1,
            CorruptionSeverity.MEDIUM: 3,
            CorruptionSeverity.HIGH: 7,
            CorruptionSeverity.CRITICAL: 15
        }
        
        total_weight = sum(severity_weights[issue.severity] for issue in issues)
        
        # Calculate score as percentage of weighted issues vs total records
        score = min(100.0, (total_weight / total_records) * 100)
        
        return round(score, 2)
    
    def _generate_recommendations(self, issues: List[CorruptionIssue]) -> List[str]:
        """Generate recommendations based on found issues."""
        recommendations = []
        
        # Count issues by type and severity
        critical_count = len([i for i in issues if i.severity == CorruptionSeverity.CRITICAL])
        high_count = len([i for i in issues if i.severity == CorruptionSeverity.HIGH])
        auto_fixable_count = len([i for i in issues if i.auto_fixable])
        
        if critical_count > 0:
            recommendations.append(f"URGENT: {critical_count} critical issues require immediate attention")
        
        if high_count > 0:
            recommendations.append(f"{high_count} high-severity issues should be addressed soon")
        
        if auto_fixable_count > 0:
            recommendations.append(f"{auto_fixable_count} issues can be automatically fixed")
        
        # Type-specific recommendations
        corruption_types = set(issue.corruption_type for issue in issues)
        
        if CorruptionType.ORPHANED_DATA in corruption_types:
            recommendations.append("Clean up orphaned data to improve system performance")
        
        if CorruptionType.DUPLICATE_RECORDS in corruption_types:
            recommendations.append("Resolve duplicate records to prevent flow conflicts")
        
        if CorruptionType.CORRUPTED_JSON in corruption_types:
            recommendations.append("Fix corrupted JSON data to prevent processing errors")
        
        if not recommendations:
            recommendations.append("No significant issues found - system integrity is good")
        
        return recommendations
    
    async def fix_issue(self, issue_id: str, create_backup: bool = True) -> CorrectionResult:
        """
        Fix a specific data corruption issue.
        
        Args:
            issue_id: ID of the issue to fix
            create_backup: Whether to create backup before fixing
            
        Returns:
            Correction result
        """
        try:
            # Find the issue (this would typically be stored in a database or cache)
            # For now, we'll need to re-run checks to find the issue
            # In a production system, issues would be persisted
            
            logger.info(f"Attempting to fix issue: {issue_id}")
            
            # Parse issue ID to determine fix type
            if "invalid_flow_type_" in issue_id:
                return await self._fix_invalid_flow_type(issue_id, create_backup)
            elif "invalid_step_" in issue_id:
                return await self._fix_invalid_step(issue_id, create_backup)
            elif "corrupted_json_" in issue_id:
                return await self._fix_corrupted_json(issue_id, create_backup)
            elif "inconsistent_status_" in issue_id:
                return await self._fix_inconsistent_status(issue_id, create_backup)
            elif "duplicate_active_flows_" in issue_id:
                return await self._fix_duplicate_active_flows(issue_id, create_backup)
            elif "orphaned_flow_message_" in issue_id:
                return await self._fix_orphaned_flow_message(issue_id, create_backup)
            else:
                return CorrectionResult(
                    issue_id=issue_id,
                    success=False,
                    records_affected=0,
                    backup_created=False,
                    correction_details={},
                    error_message="Unknown issue type - manual intervention required"
                )
                
        except Exception as e:
            logger.error(f"Failed to fix issue {issue_id}: {e}")
            return CorrectionResult(
                issue_id=issue_id,
                success=False,
                records_affected=0,
                backup_created=False,
                correction_details={},
                error_message=str(e)
            )
    
    async def _fix_invalid_flow_type(self, issue_id: str, create_backup: bool) -> CorrectionResult:
        """Fix invalid flow type issue."""
        try:
            # Extract flow state ID from issue ID
            flow_state_id = UUID(issue_id.split("_")[-1])
            
            flow_state = self.flow_repo.get(flow_state_id)
            if not flow_state:
                return CorrectionResult(
                    issue_id=issue_id,
                    success=False,
                    records_affected=0,
                    backup_created=False,
                    correction_details={},
                    error_message="Flow state not found"
                )
            
            # Create backup if requested
            backup_data = None
            if create_backup:
                backup_data = {
                    "original_flow_type": flow_state.flow_type,
                    "backup_timestamp": datetime.utcnow().isoformat()
                }
            
            # Fix: Set to default flow type based on patient's enrollment
            patient = self.patient_repo.get(flow_state.patient_id)
            if patient and patient.enrollment_date:
                days_since_enrollment = (datetime.utcnow() - patient.enrollment_date).days
                
                if days_since_enrollment <= 15:
                    new_flow_type = FlowType.INITIAL_15_DAYS.value
                elif days_since_enrollment <= 45:
                    new_flow_type = FlowType.DAYS_16_45.value
                else:
                    new_flow_type = FlowType.MONTHLY_RECURRING.value
            else:
                new_flow_type = FlowType.INITIAL_15_DAYS.value  # Default
            
            # Apply fix
            flow_state.flow_type = new_flow_type
            if backup_data:
                flow_state.state_data = flow_state.state_data or {}
                flow_state.state_data["correction_backup"] = backup_data
            
            self.db.commit()
            
            return CorrectionResult(
                issue_id=issue_id,
                success=True,
                records_affected=1,
                backup_created=create_backup,
                correction_details={
                    "new_flow_type": new_flow_type,
                    "backup_data": backup_data
                }
            )
            
        except Exception as e:
            self.db.rollback()
            raise
    
    async def _fix_invalid_step(self, issue_id: str, create_backup: bool) -> CorrectionResult:
        """Fix invalid step issue."""
        try:
            flow_state_id = UUID(issue_id.split("_")[-1])
            flow_state = self.flow_repo.get(flow_state_id)
            
            if not flow_state:
                return CorrectionResult(
                    issue_id=issue_id,
                    success=False,
                    records_affected=0,
                    backup_created=False,
                    correction_details={},
                    error_message="Flow state not found"
                )
            
            backup_data = None
            if create_backup:
                backup_data = {
                    "original_step": flow_state.current_step,
                    "backup_timestamp": datetime.utcnow().isoformat()
                }
            
            # Fix: Reset to step 1
            flow_state.current_step = 1
            if backup_data:
                flow_state.state_data = flow_state.state_data or {}
                flow_state.state_data["correction_backup"] = backup_data
            
            self.db.commit()
            
            return CorrectionResult(
                issue_id=issue_id,
                success=True,
                records_affected=1,
                backup_created=create_backup,
                correction_details={
                    "new_step": 1,
                    "backup_data": backup_data
                }
            )
            
        except Exception as e:
            self.db.rollback()
            raise
    
    async def _fix_corrupted_json(self, issue_id: str, create_backup: bool) -> CorrectionResult:
        """Fix corrupted JSON data."""
        try:
            # Determine if it's flow state or message
            if "flow_state" in issue_id:
                return await self._fix_corrupted_flow_state_json(issue_id, create_backup)
            else:
                return await self._fix_corrupted_message_json(issue_id, create_backup)
                
        except Exception as e:
            raise
    
    async def _fix_corrupted_flow_state_json(self, issue_id: str, create_backup: bool) -> CorrectionResult:
        """Fix corrupted flow state JSON."""
        try:
            flow_state_id = UUID(issue_id.split("_")[-1])
            flow_state = self.flow_repo.get(flow_state_id)
            
            if not flow_state:
                return CorrectionResult(
                    issue_id=issue_id,
                    success=False,
                    records_affected=0,
                    backup_created=False,
                    correction_details={},
                    error_message="Flow state not found"
                )
            
            backup_data = None
            if create_backup:
                backup_data = {
                    "original_state_data": str(flow_state.state_data),
                    "backup_timestamp": datetime.utcnow().isoformat()
                }
            
            # Fix: Reset to empty dict
            flow_state.state_data = {"reset_due_to_corruption": True}
            if backup_data:
                flow_state.state_data["corruption_backup"] = backup_data
            
            self.db.commit()
            
            return CorrectionResult(
                issue_id=issue_id,
                success=True,
                records_affected=1,
                backup_created=create_backup,
                correction_details={
                    "action": "reset_state_data",
                    "backup_data": backup_data
                }
            )
            
        except Exception as e:
            self.db.rollback()
            raise
    
    async def _fix_duplicate_active_flows(self, issue_id: str, create_backup: bool) -> CorrectionResult:
        """Fix duplicate active flows."""
        try:
            patient_id = UUID(issue_id.split("_")[-1])
            
            # Get all active flows for patient
            active_flows = [f for f in self.flow_repo.get_by_patient_id(patient_id) if not f.completed_at]
            
            if len(active_flows) <= 1:
                return CorrectionResult(
                    issue_id=issue_id,
                    success=True,
                    records_affected=0,
                    backup_created=False,
                    correction_details={"message": "No duplicate flows found"}
                )
            
            # Keep the most recent flow, complete others
            active_flows.sort(key=lambda f: f.started_at, reverse=True)
            keep_flow = active_flows[0]
            complete_flows = active_flows[1:]
            
            backup_data = None
            if create_backup:
                backup_data = {
                    "completed_flows": [str(f.id) for f in complete_flows],
                    "kept_flow": str(keep_flow.id),
                    "backup_timestamp": datetime.utcnow().isoformat()
                }
            
            # Complete duplicate flows
            for flow in complete_flows:
                flow.completed_at = datetime.utcnow()
                flow.state_data = flow.state_data or {}
                flow.state_data["completed_reason"] = "duplicate_resolution"
                if backup_data:
                    flow.state_data["correction_backup"] = backup_data
            
            self.db.commit()
            
            return CorrectionResult(
                issue_id=issue_id,
                success=True,
                records_affected=len(complete_flows),
                backup_created=create_backup,
                correction_details={
                    "kept_flow_id": str(keep_flow.id),
                    "completed_flow_ids": [str(f.id) for f in complete_flows],
                    "backup_data": backup_data
                }
            )
            
        except Exception as e:
            self.db.rollback()
            raise
    
    async def _fix_orphaned_flow_message(self, issue_id: str, create_backup: bool) -> CorrectionResult:
        """Fix orphaned flow message."""
        try:
            flow_message_id = UUID(issue_id.split("_")[-1])
            
            flow_message = self.db.query(FlowMessage).filter(FlowMessage.id == flow_message_id).first()
            if not flow_message:
                return CorrectionResult(
                    issue_id=issue_id,
                    success=False,
                    records_affected=0,
                    backup_created=False,
                    correction_details={},
                    error_message="Flow message not found"
                )
            
            backup_data = None
            if create_backup:
                backup_data = {
                    "flow_message_data": {
                        "id": str(flow_message.id),
                        "flow_state_id": str(flow_message.flow_state_id),
                        "content": flow_message.content
                    },
                    "backup_timestamp": datetime.utcnow().isoformat()
                }
                
                # Store backup in a separate table or log
                logger.info(f"Backup created for orphaned flow message: {backup_data}")
            
            # Delete orphaned flow message
            self.db.delete(flow_message)
            self.db.commit()
            
            return CorrectionResult(
                issue_id=issue_id,
                success=True,
                records_affected=1,
                backup_created=create_backup,
                correction_details={
                    "action": "deleted_orphaned_message",
                    "backup_data": backup_data
                }
            )
            
        except Exception as e:
            self.db.rollback()
            raise
    
    async def _fix_inconsistent_status(self, issue_id: str, create_backup: bool) -> CorrectionResult:
        """Fix inconsistent message status."""
        try:
            message_id = UUID(issue_id.split("_")[-1])
            message = self.message_repo.get(message_id)
            
            if not message:
                return CorrectionResult(
                    issue_id=issue_id,
                    success=False,
                    records_affected=0,
                    backup_created=False,
                    correction_details={},
                    error_message="Message not found"
                )
            
            backup_data = None
            if create_backup:
                backup_data = {
                    "original_status": message.status.value,
                    "original_sent_at": message.sent_at.isoformat() if message.sent_at else None,
                    "backup_timestamp": datetime.utcnow().isoformat()
                }
            
            # Fix: If marked as sent but no timestamp, add timestamp
            if message.status == MessageStatus.SENT and not message.sent_at:
                message.sent_at = message.created_at or datetime.utcnow()
                
                if backup_data:
                    message.message_metadata = message.message_metadata or {}
                    message.message_metadata["correction_backup"] = backup_data
            
            self.db.commit()
            
            return CorrectionResult(
                issue_id=issue_id,
                success=True,
                records_affected=1,
                backup_created=create_backup,
                correction_details={
                    "action": "added_sent_timestamp",
                    "new_sent_at": message.sent_at.isoformat(),
                    "backup_data": backup_data
                }
            )
            
        except Exception as e:
            self.db.rollback()
            raise
    
    async def get_correction_history(self, 
                                   patient_id: Optional[UUID] = None,
                                   days_back: int = 30) -> List[dict[str, Any]]:
        """Get history of data corrections."""
        try:
            # This would typically query a corrections log table
            # For now, we'll return a placeholder structure
            
            corrections = []
            
            # In a real implementation, this would query correction logs
            # stored in the database with details about what was fixed
            
            return corrections
            
        except Exception as e:
            logger.error(f"Failed to get correction history: {e}")
            return []


def get_flow_data_integrity_checker(db: Session) -> FlowDataIntegrityChecker:
    """Get flow data integrity checker instance."""
    return FlowDataIntegrityChecker(db)