"""Flow integrity recovery and health-check mixin."""

import logging
from typing import Any

from app.models.flow import PatientFlowState
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class FlowIntegrityRecoveryMixin:
    """Recovery and health-check methods for flow integrity."""

    async def repair_flow_integrity(self, flow_state: PatientFlowState) -> dict[str, Any]:
        """
        Attempt to repair flow integrity issues.

        Args:
            flow_state: Flow state to repair

        Returns:
            dict: Repair results
        """
        try:
            repair_results = {
                "flow_id": str(flow_state.id),
                "patient_id": str(flow_state.patient_id),
                "repairs_applied": [],
                "warnings": [],
                "success": True,
            }

            if flow_state.state_data:
                expected_checksum = self._generate_flow_checksum(flow_state)
                stored_checksum = flow_state.state_data.get("integrity_checksum")

                if not stored_checksum or stored_checksum != expected_checksum:
                    flow_state.state_data["integrity_checksum"] = expected_checksum
                    flow_state.state_data["checksum_repaired"] = now_sao_paulo().isoformat()
                    repair_results["repairs_applied"].append("integrity_checksum_updated")

                if "status" not in flow_state.state_data:
                    flow_state.state_data["status"] = "active"
                    repair_results["repairs_applied"].append("status_field_added")

                if "last_updated" not in flow_state.state_data:
                    flow_state.state_data["last_updated"] = now_sao_paulo().isoformat()
                    repair_results["repairs_applied"].append("last_updated_field_added")

            max_step = self._get_max_step_for_flow(flow_state.flow_type)
            if flow_state.current_step > max_step:
                flow_state.current_step = max_step
                repair_results["repairs_applied"].append("current_step_capped")
                repair_results["warnings"].append(
                    f"Step was above maximum ({max_step}), capped to max"
                )

            if flow_state.current_step < 1:
                flow_state.current_step = 1
                repair_results["repairs_applied"].append("current_step_minimum_enforced")
                repair_results["warnings"].append("Step was below 1, set to minimum")

            if repair_results["repairs_applied"]:
                self.db.commit()
                logger.info(
                    f"Applied {len(repair_results['repairs_applied'])} repairs to flow {flow_state.id}"
                )

            return repair_results

        except Exception as e:
            logger.error(f"Flow integrity repair failed: {e}")
            self.db.rollback()
            return {
                "flow_id": str(flow_state.id),
                "patient_id": str(flow_state.patient_id),
                "success": False,
                "error": str(e),
                "repairs_applied": [],
                "warnings": [],
            }

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on flow integrity service.

        Returns:
            dict: Health status
        """
        try:
            results = {
                "service": "FlowIntegrityService",
                "timestamp": now_sao_paulo().isoformat(),
                "healthy": True,
                "checks": {},
            }

            try:
                self.db.execute("SELECT 1")
                results["checks"]["database"] = {"healthy": True, "connected": True}
            except Exception as e:
                results["checks"]["database"] = {"healthy": False, "error": str(e)}
                results["healthy"] = False

            try:
                count = self.db.query(PatientFlowState).count()
                results["checks"]["repositories"] = {
                    "healthy": True,
                    "flow_states_accessible": count >= 0,
                }
            except Exception as e:
                results["checks"]["repositories"] = {"healthy": False, "error": str(e)}
                results["healthy"] = False

            return results

        except Exception as e:
            logger.error(f"Flow integrity health check failed: {e}")
            return {
                "service": "FlowIntegrityService",
                "timestamp": now_sao_paulo().isoformat(),
                "healthy": False,
                "error": str(e),
            }
