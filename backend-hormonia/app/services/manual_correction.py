"""
Manual correction service for fixing corrupted flow data.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from uuid import UUID
import json

from redis import Redis

from app.models.flow import PatientFlowState
from app.agents.patient.flow_coordinator.constants import (
    ONBOARDING_END_DAY,
    DAILY_FOLLOWUP_END_DAY,
    compute_cycle_number,
)
from app.repositories.flow import FlowStateRepository
from app.services.data_corruption import DataCorruptionDetector
from app.services.enhanced_flow_engine import FlowType
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class ManualCorrectionService:
    """Service for manually correcting corrupted flow data."""

    def __init__(
        self,
        db: Any,
        redis: Redis,
        flow_repository: FlowStateRepository,
        corruption_detector: DataCorruptionDetector,
    ):
        self.db = db
        self.redis = redis
        self.flow_repository = flow_repository
        self.corruption_detector = corruption_detector

        # Available correction actions
        self.correction_actions = {
            "reset_to_calculated_day": self._reset_to_calculated_day,
            "update_flow_type": self._update_flow_type,
            "fix_enrollment_date": self._fix_enrollment_date,
            "repair_state_data": self._repair_state_data,
            "rebuild_message_sequence": self._rebuild_message_sequence,
            "reset_temporal_fields": self._reset_temporal_fields,
            "pause_for_investigation": self._pause_for_investigation,
            "reset_flow_completely": self._reset_flow_completely,
        }

    async def get_correction_recommendations(self, patient_id: UUID) -> Dict[str, Any]:
        """
        Get correction recommendations for a patient's flow issues.

        Args:
            patient_id: Patient to analyze

        Returns:
            Dictionary with recommendations and available actions
        """
        try:
            # Detect current issues
            issues = await self.corruption_detector.detect_flow_state_corruption(
                patient_id
            )

            if not issues:
                return {
                    "patient_id": str(patient_id),
                    "status": "healthy",
                    "issues": [],
                    "recommendations": [],
                }

            # Generate recommendations
            recommendations = []
            for issue in issues:
                recommendation = await self._generate_recommendation(issue, patient_id)
                if recommendation:
                    recommendations.append(recommendation)

            return {
                "patient_id": str(patient_id),
                "status": "requires_correction",
                "issues": issues,
                "recommendations": recommendations,
                "available_actions": list(self.correction_actions.keys()),
            }

        except Exception as e:
            logger.error(f"Error getting correction recommendations: {e}")
            return {"patient_id": str(patient_id), "status": "error", "error": str(e)}

    async def apply_correction(
        self, patient_id: UUID, action: str, parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Apply a specific correction action to a patient's flow.

        Args:
            patient_id: Patient to correct
            action: Correction action to apply
            parameters: Optional parameters for the action

        Returns:
            Result of the correction operation
        """
        try:
            # Validate action exists
            if action not in self.correction_actions:
                return {
                    "success": False,
                    "error": f"Unknown correction action: {action}",
                    "available_actions": list(self.correction_actions.keys()),
                }

            # Get current flow state
            flow_state = self.flow_repository.get_flow_state(patient_id)
            if not flow_state:
                return {
                    "success": False,
                    "error": f"No flow state found for patient {patient_id}",
                }

            # Create backup before correction
            backup_key = await self._create_correction_backup(patient_id, flow_state)

            # Apply correction
            correction_func = self.correction_actions[action]
            result = await correction_func(patient_id, flow_state, parameters or {})

            # Log correction
            await self._log_correction_applied(
                patient_id, action, parameters, result, backup_key
            )

            # Verify correction worked
            post_correction_issues = (
                await self.corruption_detector.detect_flow_state_corruption(patient_id)
            )

            result.update(
                {
                    "backup_key": backup_key,
                    "remaining_issues": post_correction_issues,
                    "correction_successful": len(post_correction_issues) == 0,
                }
            )

            return result

        except Exception as e:
            logger.error(
                f"Error applying correction {action} to patient {patient_id}: {e}"
            )
            return {
                "success": False,
                "error": str(e),
                "action": action,
                "patient_id": str(patient_id),
            }

    async def correct_flow_state(self, flow_id: UUID) -> bool:
        """Attempt to auto-correct a flow state by applying safe recommendations."""
        try:
            flow_state = (
                self.db.query(PatientFlowState)
                .filter(PatientFlowState.id == flow_id)
                .first()
            )
            if not flow_state:
                return False

            patient_id = flow_state.patient_id
            recommendations = await self.get_correction_recommendations(patient_id)
            for recommendation in recommendations.get("recommendations", []):
                if recommendation.get("automatic"):
                    await self.apply_correction(
                        patient_id,
                        recommendation["recommended_action"],
                        recommendation.get("parameters"),
                    )

            remaining = await self.corruption_detector.detect_flow_state_corruption(
                patient_id
            )
            return len(remaining) == 0
        except Exception as e:
            logger.error(f"Error auto-correcting flow state {flow_id}: {e}")
            return False

    async def apply_bulk_corrections(
        self, corrections: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Apply multiple corrections in bulk.

        Args:
            corrections: List of correction specifications

        Returns:
            Summary of bulk correction results
        """
        results = {
            "total_corrections": len(corrections),
            "successful": 0,
            "failed": 0,
            "details": [],
        }

        for correction in corrections:
            try:
                patient_id = UUID(correction["patient_id"])
                action = correction["action"]
                parameters = correction.get("parameters", {})

                result = await self.apply_correction(patient_id, action, parameters)

                if result.get("success", False):
                    results["successful"] += 1
                else:
                    results["failed"] += 1

                results["details"].append(
                    {"patient_id": str(patient_id), "action": action, "result": result}
                )

            except Exception as e:
                results["failed"] += 1
                results["details"].append(
                    {
                        "patient_id": correction.get("patient_id", "unknown"),
                        "action": correction.get("action", "unknown"),
                        "result": {"success": False, "error": str(e)},
                    }
                )

        return results

    async def _generate_recommendation(
        self, issue: Dict[str, Any], patient_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Generate correction recommendation for a specific issue."""
        issue_type = issue["type"]
        severity = issue.get("severity", "medium")

        if issue_type == "invalid_day_range":
            return {
                "issue_type": issue_type,
                "severity": severity,
                "recommended_action": "reset_to_calculated_day",
                "description": "Reset current day based on enrollment date",
                "automatic": True,
                "risk_level": "low",
            }

        elif issue_type == "flow_type_mismatch":
            return {
                "issue_type": issue_type,
                "severity": severity,
                "recommended_action": "update_flow_type",
                "description": f"Update flow type to {issue.get('expected_flow_type')}",
                "automatic": True,
                "risk_level": "low",
                "parameters": {"new_flow_type": issue.get("expected_flow_type")},
            }

        elif issue_type == "future_enrollment_date":
            return {
                "issue_type": issue_type,
                "severity": severity,
                "recommended_action": "fix_enrollment_date",
                "description": "Fix enrollment date to current date",
                "automatic": False,
                "risk_level": "medium",
            }

        elif issue_type == "missing_required_field":
            return {
                "issue_type": issue_type,
                "severity": severity,
                "recommended_action": "repair_state_data",
                "description": f"Add missing field: {issue.get('missing_field')}",
                "automatic": False,
                "risk_level": "low",
                "parameters": {"missing_field": issue.get("missing_field")},
            }

        elif issue_type == "missing_message_days":
            return {
                "issue_type": issue_type,
                "severity": severity,
                "recommended_action": "rebuild_message_sequence",
                "description": "Rebuild missing message sequence",
                "automatic": False,
                "risk_level": "medium",
            }

        elif issue_type in ["future_last_message", "overdue_next_message"]:
            return {
                "issue_type": issue_type,
                "severity": severity,
                "recommended_action": "reset_temporal_fields",
                "description": "Reset temporal fields to current time",
                "automatic": True,
                "risk_level": "low",
            }

        else:
            return {
                "issue_type": issue_type,
                "severity": severity,
                "recommended_action": "pause_for_investigation",
                "description": "Pause flow for manual investigation",
                "automatic": False,
                "risk_level": "high",
            }

    async def _reset_to_calculated_day(
        self, patient_id: UUID, flow_state: PatientFlowState, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Reset current day based on enrollment date."""
        try:
            if not flow_state.enrollment_date:
                return {
                    "success": False,
                    "error": "No enrollment date to calculate from",
                }

            # Calculate correct day
            days_since_enrollment = (
                now_sao_paulo() - flow_state.enrollment_date
            ).days + 1

            # Determine correct flow type and day
            if days_since_enrollment <= ONBOARDING_END_DAY:
                new_flow_type = FlowType.ONBOARDING.value
                new_day = days_since_enrollment
            elif days_since_enrollment <= DAILY_FOLLOWUP_END_DAY:
                new_flow_type = FlowType.DAILY_FOLLOW_UP.value
                new_day = days_since_enrollment
            else:
                new_flow_type = FlowType.QUIZ_MENSAL.value
                monthly_cycle, new_day = compute_cycle_number(days_since_enrollment)
                flow_state.monthly_cycle = monthly_cycle

            # Update flow state
            old_day = flow_state.current_day
            old_flow_type = flow_state.flow_type

            flow_state.current_day = new_day
            flow_state.flow_type = new_flow_type
            flow_state.updated_at = now_sao_paulo()

            self.db.commit()

            return {
                "success": True,
                "action": "reset_to_calculated_day",
                "changes": {
                    "old_day": old_day,
                    "new_day": new_day,
                    "old_flow_type": old_flow_type,
                    "new_flow_type": new_flow_type,
                    "days_since_enrollment": days_since_enrollment,
                },
            }

        except Exception as e:
            self.db.rollback()
            return {"success": False, "error": str(e)}

    async def _update_flow_type(
        self, patient_id: UUID, flow_state: PatientFlowState, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update flow type to correct value."""
        try:
            new_flow_type = parameters.get("new_flow_type")
            if not new_flow_type:
                return {"success": False, "error": "new_flow_type parameter required"}

            old_flow_type = flow_state.flow_type
            flow_state.flow_type = new_flow_type
            flow_state.updated_at = now_sao_paulo()

            self.db.commit()

            return {
                "success": True,
                "action": "update_flow_type",
                "changes": {
                    "old_flow_type": old_flow_type,
                    "new_flow_type": new_flow_type,
                },
            }

        except Exception as e:
            self.db.rollback()
            return {"success": False, "error": str(e)}

    async def _fix_enrollment_date(
        self, patient_id: UUID, flow_state: PatientFlowState, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fix invalid enrollment date."""
        try:
            # Use provided date or default to reasonable date
            new_enrollment_date = parameters.get("enrollment_date")

            if new_enrollment_date:
                if isinstance(new_enrollment_date, str):
                    new_enrollment_date = datetime.fromisoformat(new_enrollment_date)
            else:
                # Default to current date minus current day
                new_enrollment_date = now_sao_paulo() - timedelta(
                    days=flow_state.current_day - 1
                )

            old_enrollment_date = flow_state.enrollment_date
            flow_state.enrollment_date = new_enrollment_date
            flow_state.updated_at = now_sao_paulo()

            self.db.commit()

            return {
                "success": True,
                "action": "fix_enrollment_date",
                "changes": {
                    "old_enrollment_date": old_enrollment_date.isoformat()
                    if old_enrollment_date
                    else None,
                    "new_enrollment_date": new_enrollment_date.isoformat(),
                },
            }

        except Exception as e:
            self.db.rollback()
            return {"success": False, "error": str(e)}

    async def _repair_state_data(
        self, patient_id: UUID, flow_state: PatientFlowState, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Repair corrupted state data."""
        try:
            if not flow_state.state_data:
                flow_state.state_data = {}

            # Add missing required fields
            missing_field = parameters.get("missing_field")
            if missing_field:
                flow_kind = (
                    flow_state.flow_type.value
                    if hasattr(flow_state.flow_type, "value")
                    else str(flow_state.flow_type)
                )
                default_values = {
                    "last_template_used": None,
                    "message_count": 0,
                    "monthly_cycle": 1,
                    "last_quiz_date": None,
                    "current_flow_day": flow_state.current_day or 1,
                    "flow_kind": flow_kind,
                }

                if missing_field in default_values:
                    flow_state.state_data[missing_field] = default_values[missing_field]

            # Fix invalid field values
            if "message_count" in flow_state.state_data:
                if not isinstance(flow_state.state_data["message_count"], int):
                    flow_state.state_data["message_count"] = 0
                elif flow_state.state_data["message_count"] < 0:
                    flow_state.state_data["message_count"] = 0

            if "monthly_cycle" in flow_state.state_data:
                if not isinstance(flow_state.state_data["monthly_cycle"], int):
                    flow_state.state_data["monthly_cycle"] = 1
                elif flow_state.state_data["monthly_cycle"] < 1:
                    flow_state.state_data["monthly_cycle"] = 1

            flow_state.updated_at = now_sao_paulo()
            self.db.commit()

            return {
                "success": True,
                "action": "repair_state_data",
                "changes": {
                    "repaired_fields": [missing_field]
                    if missing_field
                    else ["message_count", "monthly_cycle"],
                    "current_state_data": flow_state.state_data,
                },
            }

        except Exception as e:
            self.db.rollback()
            return {"success": False, "error": str(e)}

    async def _rebuild_message_sequence(
        self, patient_id: UUID, flow_state: PatientFlowState, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Rebuild missing message sequence."""
        try:
            # This is a complex operation that should be done carefully
            # For now, we'll just log the need for manual intervention

            correction_task = {
                "task_type": "rebuild_message_sequence",
                "patient_id": str(patient_id),
                "flow_state_id": str(flow_state.id),
                "current_day": flow_state.current_day,
                "flow_type": flow_state.flow_type,
                "created_at": now_sao_paulo().isoformat(),
                "status": "pending_manual_review",
            }

            task_key = f"manual_tasks:rebuild_messages:{patient_id}"
            await self.redis.setex(task_key, 86400 * 7, json.dumps(correction_task))

            return {
                "success": True,
                "action": "rebuild_message_sequence",
                "message": "Task created for manual message sequence rebuild",
                "task_key": task_key,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _reset_temporal_fields(
        self, patient_id: UUID, flow_state: PatientFlowState, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Reset temporal fields to reasonable values."""
        try:
            changes = {}

            # Reset last_message_sent if it's in the future
            if (
                flow_state.last_message_sent
                and flow_state.last_message_sent > now_sao_paulo()
            ):
                changes["old_last_message_sent"] = (
                    flow_state.last_message_sent.isoformat()
                )
                flow_state.last_message_sent = now_sao_paulo() - timedelta(hours=1)
                changes["new_last_message_sent"] = (
                    flow_state.last_message_sent.isoformat()
                )

            # Reset next_message_due if it's too far overdue
            if (
                flow_state.next_message_due
                and flow_state.next_message_due < now_sao_paulo() - timedelta(days=2)
            ):
                changes["old_next_message_due"] = (
                    flow_state.next_message_due.isoformat()
                )
                flow_state.next_message_due = now_sao_paulo() + timedelta(hours=1)
                changes["new_next_message_due"] = (
                    flow_state.next_message_due.isoformat()
                )

            flow_state.updated_at = now_sao_paulo()
            self.db.commit()

            return {
                "success": True,
                "action": "reset_temporal_fields",
                "changes": changes,
            }

        except Exception as e:
            self.db.rollback()
            return {"success": False, "error": str(e)}

    async def _pause_for_investigation(
        self, patient_id: UUID, flow_state: PatientFlowState, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Pause flow for manual investigation."""
        try:
            reason = parameters.get(
                "reason", "Data corruption detected - requires investigation"
            )

            flow_state.is_paused = True
            flow_state.pause_reason = reason
            flow_state.updated_at = now_sao_paulo()

            self.db.commit()

            # Create investigation task
            investigation_task = {
                "task_type": "flow_investigation",
                "patient_id": str(patient_id),
                "reason": reason,
                "paused_at": now_sao_paulo().isoformat(),
                "status": "requires_investigation",
            }

            task_key = f"investigations:flow:{patient_id}"
            await self.redis.setex(task_key, 86400 * 7, json.dumps(investigation_task))

            return {
                "success": True,
                "action": "pause_for_investigation",
                "message": f"Flow paused for investigation: {reason}",
                "task_key": task_key,
            }

        except Exception as e:
            self.db.rollback()
            return {"success": False, "error": str(e)}

    async def _reset_flow_completely(
        self, patient_id: UUID, flow_state: PatientFlowState, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Completely reset flow state (nuclear option)."""
        try:
            # This is a destructive operation - create comprehensive backup first
            backup_data = {
                "flow_state": {
                    "id": str(flow_state.id),
                    "patient_id": str(flow_state.patient_id),
                    "flow_type": flow_state.flow_type,
                    "current_day": flow_state.current_day,
                    "enrollment_date": flow_state.enrollment_date.isoformat()
                    if flow_state.enrollment_date
                    else None,
                    "last_message_sent": flow_state.last_message_sent.isoformat()
                    if flow_state.last_message_sent
                    else None,
                    "next_message_due": flow_state.next_message_due.isoformat()
                    if flow_state.next_message_due
                    else None,
                    "state_data": flow_state.state_data,
                    "is_paused": flow_state.is_paused,
                    "pause_reason": flow_state.pause_reason,
                    "monthly_cycle": flow_state.monthly_cycle,
                }
            }

            # Reset to initial state
            flow_state.flow_type = FlowType.ONBOARDING.value
            flow_state.current_day = 1
            flow_state.enrollment_date = now_sao_paulo()
            flow_state.last_message_sent = None
            flow_state.next_message_due = None
            flow_state.state_data = {"message_count": 0, "last_template_used": None}
            flow_state.is_paused = False
            flow_state.pause_reason = None
            flow_state.monthly_cycle = None
            flow_state.updated_at = now_sao_paulo()

            self.db.commit()

            return {
                "success": True,
                "action": "reset_flow_completely",
                "message": "Flow completely reset to initial state",
                "backup_data": backup_data,
            }

        except Exception as e:
            self.db.rollback()
            return {"success": False, "error": str(e)}

    async def _create_correction_backup(
        self, patient_id: UUID, flow_state: PatientFlowState
    ) -> str:
        """Create backup before applying correction."""
        backup_data = {
            "patient_id": str(patient_id),
            "backup_created_at": now_sao_paulo().isoformat(),
            "flow_state": {
                "id": str(flow_state.id),
                "flow_type": flow_state.flow_type,
                "current_day": flow_state.current_day,
                "enrollment_date": flow_state.enrollment_date.isoformat()
                if flow_state.enrollment_date
                else None,
                "last_message_sent": flow_state.last_message_sent.isoformat()
                if flow_state.last_message_sent
                else None,
                "next_message_due": flow_state.next_message_due.isoformat()
                if flow_state.next_message_due
                else None,
                "state_data": flow_state.state_data,
                "is_paused": flow_state.is_paused,
                "pause_reason": flow_state.pause_reason,
                "monthly_cycle": flow_state.monthly_cycle,
            },
        }

        backup_key = f"correction_backup:{patient_id}:{now_sao_paulo().strftime('%Y%m%d_%H%M%S')}"
        await self.redis.setex(
            backup_key, 86400 * 30, json.dumps(backup_data)
        )  # Keep for 30 days

        return backup_key

    async def _log_correction_applied(
        self,
        patient_id: UUID,
        action: str,
        parameters: Dict[str, Any],
        result: Dict[str, Any],
        backup_key: str,
    ) -> None:
        """Log correction that was applied."""
        log_data = {
            "patient_id": str(patient_id),
            "action": action,
            "parameters": parameters,
            "result": result,
            "backup_key": backup_key,
            "applied_at": now_sao_paulo().isoformat(),
        }

        try:
            log_key = f"correction_log:{patient_id}:{now_sao_paulo().strftime('%Y%m%d_%H%M%S')}"
            await self.redis.setex(log_key, 86400 * 30, json.dumps(log_data))

            # Also add to daily summary
            daily_key = f"corrections_applied:{now_sao_paulo().strftime('%Y-%m-%d')}"
            await self.redis.lpush(daily_key, json.dumps(log_data))
            await self.redis.expire(daily_key, 86400 * 30)

        except Exception as e:
            logger.error(f"Error logging correction: {e}")

        logger.info(
            f"Applied correction {action} to patient {patient_id}: {result.get('success', False)}"
        )

    async def restore_from_backup(self, backup_key: str) -> Dict[str, Any]:
        """Restore flow state from backup."""
        try:
            backup_data = await self.redis.get(backup_key)
            if not backup_data:
                return {"success": False, "error": "Backup not found"}

            backup = json.loads(backup_data)
            patient_id = UUID(backup["patient_id"])

            # Get current flow state
            flow_state = self.flow_repository.get_flow_state(patient_id)
            if not flow_state:
                return {"success": False, "error": "Flow state not found"}

            # Restore from backup
            backup_flow_state = backup["flow_state"]
            flow_state.flow_type = backup_flow_state["flow_type"]
            flow_state.current_day = backup_flow_state["current_day"]
            flow_state.enrollment_date = (
                datetime.fromisoformat(backup_flow_state["enrollment_date"])
                if backup_flow_state["enrollment_date"]
                else None
            )
            flow_state.last_message_sent = (
                datetime.fromisoformat(backup_flow_state["last_message_sent"])
                if backup_flow_state["last_message_sent"]
                else None
            )
            flow_state.next_message_due = (
                datetime.fromisoformat(backup_flow_state["next_message_due"])
                if backup_flow_state["next_message_due"]
                else None
            )
            flow_state.state_data = backup_flow_state["state_data"]
            flow_state.is_paused = backup_flow_state["is_paused"]
            flow_state.pause_reason = backup_flow_state["pause_reason"]
            flow_state.monthly_cycle = backup_flow_state["monthly_cycle"]
            flow_state.updated_at = now_sao_paulo()

            self.db.commit()

            return {
                "success": True,
                "message": "Flow state restored from backup",
                "backup_key": backup_key,
                "restored_at": now_sao_paulo().isoformat(),
            }

        except Exception as e:
            self.db.rollback()
            return {"success": False, "error": str(e)}
