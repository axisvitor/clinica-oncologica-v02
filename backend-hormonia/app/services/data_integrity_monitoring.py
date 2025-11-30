"""
Data Integrity Monitoring Service
Comprehensive monitoring and detection of data integrity issues across the system.
Combines all integrity validation services for centralized monitoring.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.exc import DatabaseError

from app.services.patient import PatientIntegrityService
from app.domain.flows.core import FlowIntegrityService
from app.repositories.message import MessageIntegrityService
from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.models.message import Message
from app.exceptions import ValidationError

logger = logging.getLogger(__name__)


class IntegrityIssueType(Enum):
    """Types of integrity issues that can be detected"""
    PATIENT_DUPLICATE = "patient_duplicate"
    PATIENT_ORPHANED = "patient_orphaned"
    FLOW_INCONSISTENT = "flow_inconsistent"
    FLOW_TRANSITION_INVALID = "flow_transition_invalid"
    MESSAGE_CORRUPTED = "message_corrupted"
    MESSAGE_OUT_OF_ORDER = "message_out_of_order"
    REFERENTIAL_BROKEN = "referential_broken"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    DATA_CORRUPTION = "data_corruption"


class IntegritySeverity(Enum):
    """Severity levels for integrity issues"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class IntegrityIssue:
    """Represents a data integrity issue"""
    id: str
    type: IntegrityIssueType
    severity: IntegritySeverity
    entity_type: str  # patient, flow, message
    entity_id: str
    description: str
    detected_at: datetime
    metadata: Dict[str, Any]
    resolution_status: str = "open"  # open, resolved, ignored
    resolution_notes: Optional[str] = None


class DataIntegrityMonitoringService:
    """
    Comprehensive data integrity monitoring service that coordinates
    all integrity validation services and provides centralized monitoring.
    """

    def __init__(self, db: Any):
        self.db = db
        self.patient_integrity = PatientIntegrityService(db)
        self.flow_integrity = FlowIntegrityService(db)
        self.message_integrity = MessageIntegrityService(db)
        self.detected_issues: List[IntegrityIssue] = []

    async def run_comprehensive_integrity_scan(self,
                                             limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Run comprehensive integrity scan across all data types.

        Args:
            limit: Optional limit on number of entities to scan

        Returns:
            Comprehensive integrity scan results
        """
        try:
            start_time = datetime.utcnow()
            self.detected_issues = []  # Reset issues list

            scan_results = {
                'scan_id': f"integrity_scan_{int(start_time.timestamp())}",
                'started_at': start_time.isoformat(),
                'completed_at': None,
                'total_duration_seconds': 0,
                'entities_scanned': {
                    'patients': 0,
                    'flows': 0,
                    'messages': 0
                },
                'issues_detected': {
                    'total': 0,
                    'by_type': {},
                    'by_severity': {},
                    'by_entity_type': {}
                },
                'scan_status': 'running',
                'details': []
            }

            logger.info(f"Starting comprehensive integrity scan (limit: {limit})")

            # Scan patients
            patient_results = await self._scan_patient_integrity(limit)
            scan_results['details'].append(patient_results)
            scan_results['entities_scanned']['patients'] = patient_results['entities_scanned']

            # Scan flows
            flow_results = await self._scan_flow_integrity(limit)
            scan_results['details'].append(flow_results)
            scan_results['entities_scanned']['flows'] = flow_results['entities_scanned']

            # Scan messages
            message_results = await self._scan_message_integrity(limit)
            scan_results['details'].append(message_results)
            scan_results['entities_scanned']['messages'] = message_results['entities_scanned']

            # Compile overall results
            total_issues = len(self.detected_issues)
            scan_results['issues_detected']['total'] = total_issues

            # Categorize issues
            by_type = {}
            by_severity = {}
            by_entity_type = {}

            for issue in self.detected_issues:
                # By type
                issue_type = issue.type.value
                by_type[issue_type] = by_type.get(issue_type, 0) + 1

                # By severity
                severity = issue.severity.value
                by_severity[severity] = by_severity.get(severity, 0) + 1

                # By entity type
                entity_type = issue.entity_type
                by_entity_type[entity_type] = by_entity_type.get(entity_type, 0) + 1

            scan_results['issues_detected']['by_type'] = by_type
            scan_results['issues_detected']['by_severity'] = by_severity
            scan_results['issues_detected']['by_entity_type'] = by_entity_type

            # Mark completion
            end_time = datetime.utcnow()
            scan_results['completed_at'] = end_time.isoformat()
            scan_results['total_duration_seconds'] = (end_time - start_time).total_seconds()
            scan_results['scan_status'] = 'completed'

            logger.info(f"Integrity scan completed: {total_issues} issues detected in "
                       f"{scan_results['total_duration_seconds']:.2f}s")

            return scan_results

        except Exception as e:
            logger.error(f"Comprehensive integrity scan failed: {e}")
            scan_results['scan_status'] = 'failed'
            scan_results['error'] = str(e)
            return scan_results

    async def _scan_patient_integrity(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Scan patient data integrity"""
        try:
            start_time = datetime.utcnow()

            # Get patients to scan
            query = self.db.query(Patient)
            if limit:
                query = query.limit(limit)
            patients = query.all()

            results = {
                'scan_type': 'patient_integrity',
                'started_at': start_time.isoformat(),
                'entities_scanned': len(patients),
                'issues_found': 0,
                'scan_details': []
            }

            for patient in patients:
                try:
                    # Check for duplicates
                    await self._check_patient_duplicates(patient)

                    # Validate data consistency
                    await self._validate_patient_data_consistency(patient)

                    # Check orphaned relationships
                    await self._check_patient_orphaned_relationships(patient)

                except Exception as e:
                    logger.error(f"Error scanning patient {patient.id}: {e}")

            results['issues_found'] = len([i for i in self.detected_issues
                                         if i.entity_type == 'patient'])
            results['completed_at'] = datetime.utcnow().isoformat()

            return results

        except Exception as e:
            logger.error(f"Patient integrity scan failed: {e}")
            raise

    async def _scan_flow_integrity(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Scan flow data integrity"""
        try:
            start_time = datetime.utcnow()

            # Get flows to scan
            query = self.db.query(PatientFlowState)
            if limit:
                query = query.limit(limit)
            flows = query.all()

            results = {
                'scan_type': 'flow_integrity',
                'started_at': start_time.isoformat(),
                'entities_scanned': len(flows),
                'issues_found': 0,
                'scan_details': []
            }

            for flow in flows:
                try:
                    # Validate flow consistency
                    await self.flow_integrity.validate_flow_consistency(flow)

                    # Check referential integrity
                    ref_issues = await self.flow_integrity.validate_referential_integrity(flow)
                    if ref_issues:
                        for issue_desc in ref_issues:
                            self._add_integrity_issue(
                                type=IntegrityIssueType.REFERENTIAL_BROKEN,
                                severity=IntegritySeverity.HIGH,
                                entity_type='flow',
                                entity_id=str(flow.id),
                                description=issue_desc,
                                metadata={'flow_type': flow.flow_type, 'patient_id': str(flow.patient_id)}
                            )

                except ValidationError as e:
                    self._add_integrity_issue(
                        type=IntegrityIssueType.FLOW_INCONSISTENT,
                        severity=IntegritySeverity.HIGH,
                        entity_type='flow',
                        entity_id=str(flow.id),
                        description=str(e),
                        metadata={'flow_type': flow.flow_type, 'patient_id': str(flow.patient_id)}
                    )
                except Exception as e:
                    logger.error(f"Error scanning flow {flow.id}: {e}")

            results['issues_found'] = len([i for i in self.detected_issues
                                         if i.entity_type == 'flow'])
            results['completed_at'] = datetime.utcnow().isoformat()

            return results

        except Exception as e:
            logger.error(f"Flow integrity scan failed: {e}")
            raise

    async def _scan_message_integrity(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Scan message data integrity"""
        try:
            start_time = datetime.utcnow()

            # Get unique patients to scan their conversations
            patient_query = self.db.query(Patient.id).distinct()
            if limit:
                patient_query = patient_query.limit(limit)
            patient_ids = [p.id for p in patient_query.all()]

            results = {
                'scan_type': 'message_integrity',
                'started_at': start_time.isoformat(),
                'entities_scanned': len(patient_ids),
                'issues_found': 0,
                'scan_details': []
            }

            for patient_id in patient_ids:
                try:
                    # Validate conversation integrity
                    conv_result = await self.message_integrity.validate_conversation_integrity(patient_id)

                    if not conv_result['overall_integrity']:
                        for issue_desc in conv_result['issues']:
                            severity = IntegritySeverity.MEDIUM
                            issue_type = IntegrityIssueType.MESSAGE_CORRUPTED

                            if 'checksum' in issue_desc.lower():
                                issue_type = IntegrityIssueType.CHECKSUM_MISMATCH
                                severity = IntegritySeverity.HIGH
                            elif 'chronological' in issue_desc.lower():
                                issue_type = IntegrityIssueType.MESSAGE_OUT_OF_ORDER
                                severity = IntegritySeverity.MEDIUM
                            elif 'orphaned' in issue_desc.lower():
                                issue_type = IntegrityIssueType.REFERENTIAL_BROKEN
                                severity = IntegritySeverity.CRITICAL

                            self._add_integrity_issue(
                                type=issue_type,
                                severity=severity,
                                entity_type='message',
                                entity_id=str(patient_id),
                                description=issue_desc,
                                metadata=conv_result
                            )

                except Exception as e:
                    logger.error(f"Error scanning messages for patient {patient_id}: {e}")

            results['issues_found'] = len([i for i in self.detected_issues
                                         if i.entity_type == 'message'])
            results['completed_at'] = datetime.utcnow().isoformat()

            return results

        except Exception as e:
            logger.error(f"Message integrity scan failed: {e}")
            raise

    async def _check_patient_duplicates(self, patient: Patient) -> None:
        """Check for patient duplicates"""
        try:
            # Check CPF duplicates
            if patient.cpf:
                cpf_duplicate = await self.patient_integrity._check_duplicate_cpf(patient.cpf)
                if cpf_duplicate and cpf_duplicate.id != patient.id:
                    self._add_integrity_issue(
                        type=IntegrityIssueType.PATIENT_DUPLICATE,
                        severity=IntegritySeverity.HIGH,
                        entity_type='patient',
                        entity_id=str(patient.id),
                        description=f"Duplicate CPF {patient.cpf} found with patient {cpf_duplicate.id}",
                        metadata={'duplicate_patient_id': str(cpf_duplicate.id), 'field': 'cpf'}
                    )

            # Check email duplicates
            if patient.email:
                email_duplicate = await self.patient_integrity._check_duplicate_email(patient.email)
                if email_duplicate and email_duplicate.id != patient.id:
                    self._add_integrity_issue(
                        type=IntegrityIssueType.PATIENT_DUPLICATE,
                        severity=IntegritySeverity.MEDIUM,
                        entity_type='patient',
                        entity_id=str(patient.id),
                        description=f"Duplicate email {patient.email} found with patient {email_duplicate.id}",
                        metadata={'duplicate_patient_id': str(email_duplicate.id), 'field': 'email'}
                    )

        except Exception as e:
            logger.error(f"Error checking patient duplicates for {patient.id}: {e}")

    async def _validate_patient_data_consistency(self, patient: Patient) -> None:
        """Validate patient data consistency"""
        try:
            # Check treatment date consistency
            if patient.treatment_start_date and patient.birth_date:
                if patient.treatment_start_date < patient.birth_date:
                    self._add_integrity_issue(
                        type=IntegrityIssueType.DATA_CORRUPTION,
                        severity=IntegritySeverity.HIGH,
                        entity_type='patient',
                        entity_id=str(patient.id),
                        description="Treatment start date is before birth date",
                        metadata={'treatment_start': patient.treatment_start_date.isoformat(),
                                'birth_date': patient.birth_date.isoformat()}
                    )

            # Check metadata consistency
            if patient.patient_data:
                required_fields = ['cpf'] if patient.cpf else []
                for field in required_fields:
                    if field not in patient.patient_data:
                        self._add_integrity_issue(
                            type=IntegrityIssueType.DATA_CORRUPTION,
                            severity=IntegritySeverity.LOW,
                            entity_type='patient',
                            entity_id=str(patient.id),
                            description=f"Missing required metadata field: {field}",
                            metadata={'missing_field': field}
                        )

        except Exception as e:
            logger.error(f"Error validating patient data consistency for {patient.id}: {e}")

    async def _check_patient_orphaned_relationships(self, patient: Patient) -> None:
        """Check for orphaned patient relationships"""
        try:
            # Check if doctor exists
            from app.models.user import User
            doctor = self.db.query(User).filter(User.id == patient.doctor_id).first()
            if not doctor:
                self._add_integrity_issue(
                    type=IntegrityIssueType.PATIENT_ORPHANED,
                    severity=IntegritySeverity.CRITICAL,
                    entity_type='patient',
                    entity_id=str(patient.id),
                    description=f"Patient references non-existent doctor {patient.doctor_id}",
                    metadata={'doctor_id': str(patient.doctor_id)}
                )

        except Exception as e:
            logger.error(f"Error checking orphaned relationships for patient {patient.id}: {e}")

    def _add_integrity_issue(self,
                           type: IntegrityIssueType,
                           severity: IntegritySeverity,
                           entity_type: str,
                           entity_id: str,
                           description: str,
                           metadata: Dict[str, Any]) -> None:
        """Add integrity issue to detected issues list"""
        issue = IntegrityIssue(
            id=f"{entity_type}_{entity_id}_{type.value}_{int(datetime.utcnow().timestamp())}",
            type=type,
            severity=severity,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            detected_at=datetime.utcnow(),
            metadata=metadata
        )
        self.detected_issues.append(issue)

    async def get_integrity_dashboard(self) -> Dict[str, Any]:
        """Get integrity monitoring dashboard data"""
        try:
            # Recent issues summary
            recent_issues = [i for i in self.detected_issues
                           if i.detected_at > datetime.utcnow() - timedelta(days=7)]

            # Severity distribution
            severity_counts = {}
            for issue in recent_issues:
                severity = issue.severity.value
                severity_counts[severity] = severity_counts.get(severity, 0) + 1

            # Entity type distribution
            entity_counts = {}
            for issue in recent_issues:
                entity_type = issue.entity_type
                entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1

            # System health score (0-100)
            total_entities = (
                self.db.query(Patient).count() +
                self.db.query(PatientFlowState).count() +
                self.db.query(Message).count()
            )

            if total_entities > 0:
                health_score = max(0, 100 - (len(recent_issues) / total_entities * 100))
            else:
                health_score = 100

            return {
                'last_updated': datetime.utcnow().isoformat(),
                'health_score': round(health_score, 2),
                'recent_issues': {
                    'total': len(recent_issues),
                    'by_severity': severity_counts,
                    'by_entity_type': entity_counts
                },
                'system_status': {
                    'total_entities': total_entities,
                    'integrity_status': 'healthy' if health_score > 90 else 'degraded' if health_score > 70 else 'critical'
                },
                'recommendations': self._generate_integrity_recommendations()
            }

        except Exception as e:
            logger.error(f"Error generating integrity dashboard: {e}")
            return {
                'error': str(e),
                'last_updated': datetime.utcnow().isoformat(),
                'health_score': 0
            }

    def _generate_integrity_recommendations(self) -> List[str]:
        """Generate recommendations based on detected issues"""
        recommendations = []

        # Count issues by type
        type_counts = {}
        for issue in self.detected_issues:
            issue_type = issue.type.value
            type_counts[issue_type] = type_counts.get(issue_type, 0) + 1

        # Generate specific recommendations
        if type_counts.get('patient_duplicate', 0) > 0:
            recommendations.append("Consider implementing automated duplicate patient merging")

        if type_counts.get('checksum_mismatch', 0) > 0:
            recommendations.append("Run checksum repair utility to fix data corruption")

        if type_counts.get('message_out_of_order', 0) > 0:
            recommendations.append("Review message timestamp synchronization")

        if type_counts.get('referential_broken', 0) > 0:
            recommendations.append("Execute referential integrity repair scripts")

        # General recommendations
        if len(self.detected_issues) > 10:
            recommendations.append("Schedule regular integrity monitoring scans")

        critical_issues = [i for i in self.detected_issues if i.severity == IntegritySeverity.CRITICAL]
        if critical_issues:
            recommendations.append("Address critical integrity issues immediately")

        return recommendations[:5]  # Limit to top 5 recommendations

    async def auto_repair_integrity_issues(self,
                                         issue_types: Optional[List[IntegrityIssueType]] = None,
                                         dry_run: bool = True) -> Dict[str, Any]:
        """
        Automatically repair integrity issues where possible.

        Args:
            issue_types: Specific issue types to repair (None for all)
            dry_run: If True, don't actually make changes

        Returns:
            Repair results summary
        """
        try:
            issues_to_repair = self.detected_issues
            if issue_types:
                issues_to_repair = [i for i in issues_to_repair if i.type in issue_types]

            repair_results = {
                'dry_run': dry_run,
                'total_issues': len(issues_to_repair),
                'repaired': 0,
                'failed': 0,
                'skipped': 0,
                'details': []
            }

            for issue in issues_to_repair:
                try:
                    if issue.type == IntegrityIssueType.CHECKSUM_MISMATCH:
                        # Repair checksum mismatches
                        if not dry_run:
                            if issue.entity_type == 'message':
                                await self.message_integrity.repair_conversation_integrity(
                                    UUID(issue.entity_id)
                                )
                        repair_results['repaired'] += 1
                        repair_results['details'].append(f"Repaired checksum for {issue.entity_type} {issue.entity_id}")

                    elif issue.type == IntegrityIssueType.PATIENT_DUPLICATE:
                        # Skip auto-repair for duplicates (requires manual review)
                        repair_results['skipped'] += 1
                        repair_results['details'].append(f"Skipped duplicate repair (manual review required): {issue.entity_id}")

                    else:
                        repair_results['skipped'] += 1
                        repair_results['details'].append(f"No auto-repair available for {issue.type.value}")

                except Exception as e:
                    repair_results['failed'] += 1
                    repair_results['details'].append(f"Failed to repair {issue.entity_id}: {str(e)}")
                    logger.error(f"Auto-repair failed for issue {issue.id}: {e}")

            logger.info(f"Auto-repair completed: {repair_results['repaired']} repaired, "
                       f"{repair_results['failed']} failed, {repair_results['skipped']} skipped")

            return repair_results

        except Exception as e:
            logger.error(f"Auto-repair process failed: {e}")
            return {
                'error': str(e),
                'dry_run': dry_run,
                'total_issues': 0,
                'repaired': 0,
                'failed': 0,
                'skipped': 0
            }


# Global service instance
_integrity_monitoring_service: Optional[DataIntegrityMonitoringService] = None


def get_integrity_monitoring_service(db: Any) -> DataIntegrityMonitoringService:
    """
    Get data integrity monitoring service instance.

    Args:
        db: Database session

    Returns:
        DataIntegrityMonitoringService instance
    """
    return DataIntegrityMonitoringService(db)
