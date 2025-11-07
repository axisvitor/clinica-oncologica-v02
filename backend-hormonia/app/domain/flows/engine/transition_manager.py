"""
Transition manager for flow state transitions.
Handles state transitions with distributed locking and condition evaluation.
"""
from typing import Any, Dict
from datetime import datetime
import logging
from sqlalchemy.orm import Session

from app.models.flow import PatientFlowState
from app.services.state_machine import StateMachine, StateTransition, TransitionResult
from app.utils.distributed_lock import async_flow_state_lock, LockAcquisitionError, LockTimeoutError
from app.utils.db_retry import with_db_retry

logger = logging.getLogger(__name__)


class TransitionManager:
    """Manages flow state transitions with distributed locking."""

    def __init__(self, db: Session):
        self.db = db

    @with_db_retry(max_retries=3)
    async def handle_transition_result(
        self,
        flow_state: PatientFlowState,
        transition: StateTransition,
        context: dict[str, Any],
        state_machine: StateMachine,
        step_executor = None
    ) -> dict[str, Any]:
        """
        Handle the result of a state transition with distributed locking.

        Uses distributed locks to prevent race conditions between concurrent
        flow state updates and message scheduling operations.
        """
        result = {
            "status": transition.result.value,
            "message": transition.message,
            "patient_id": str(flow_state.patient_id),
            "flow_id": str(flow_state.id),
            "from_step": transition.from_step,
            "to_step": transition.to_step,
            "conditions_evaluated": transition.conditions_evaluated,
            "timestamp": transition.timestamp
        }

        # Acquire distributed lock for flow state transition
        try:
            async with async_flow_state_lock(flow_state.patient_id, timeout=30) as lock:
                logger.debug(f"Acquired flow state lock for patient {flow_state.patient_id}")

                if transition.result == TransitionResult.SUCCESS:
                    # Update flow state
                    flow_state.current_step = transition.to_step
                    flow_state.state_data = flow_state.state_data or {}
                    flow_state.state_data["last_transition"] = {
                        "timestamp": transition.timestamp.isoformat(),
                        "from_step": transition.from_step,
                        "to_step": transition.to_step,
                        "conditions": transition.conditions_evaluated
                    }

                    self.db.commit()
                    result["current_step"] = transition.to_step

                    # Schedule next step actions (async) - still protected by lock
                    next_step = state_machine.get_current_step(transition.to_step)
                    if next_step and step_executor:
                        await step_executor.schedule_step(flow_state, next_step, transition.timestamp)

                elif transition.result == TransitionResult.FLOW_COMPLETED:
                    # Mark flow as completed
                    flow_state.completed_at = transition.timestamp
                    flow_state.state_data = flow_state.state_data or {}
                    flow_state.state_data["completion"] = {
                        "timestamp": transition.timestamp.isoformat(),
                        "final_step": transition.from_step,
                        "auto_completion": True
                    }

                    self.db.commit()
                    result["completed_at"] = transition.timestamp

                elif transition.result == TransitionResult.CONDITION_NOT_MET:
                    # Log the failed transition attempt
                    flow_state.state_data = flow_state.state_data or {}
                    flow_state.state_data["failed_transitions"] = flow_state.state_data.get("failed_transitions", [])
                    flow_state.state_data["failed_transitions"].append({
                        "timestamp": transition.timestamp.isoformat(),
                        "from_step": transition.from_step,
                        "to_step": transition.to_step,
                        "reason": "conditions_not_met",
                        "conditions": transition.conditions_evaluated
                    })

                    self.db.commit()

                # Log lock metrics for monitoring
                lock_metrics = lock.get_metrics()
                if lock_metrics.get("contention_count", 0) > 0:
                    logger.info(
                        f"Flow state lock contention detected: "
                        f"{lock_metrics['contention_count']} contentions, "
                        f"avg wait: {lock_metrics['average_wait_time']:.3f}s"
                    )

        except LockTimeoutError as e:
            logger.error(
                f"Lock timeout during flow transition for patient {flow_state.patient_id}: {e}"
            )
            result["status"] = "lock_timeout"
            result["error"] = str(e)

        except LockAcquisitionError as e:
            logger.error(
                f"Failed to acquire lock for flow transition for patient {flow_state.patient_id}: {e}"
            )
            result["status"] = "lock_failed"
            result["error"] = str(e)

        return result
