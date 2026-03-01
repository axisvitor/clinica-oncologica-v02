"""
ReminderHandler - Main orchestration for patient reminder requests.

Refactored from 1364 lines into modular components:
- models.py: Dataclasses
- patterns.py: Regex patterns and constants
- extractors.py: Intent extraction (AI + rules)
- scheduler.py: Schedule resolution and duration
- messages.py: Portuguese message templates
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import func, select

from app.domain.messaging.core import MessageService
from app.ai.client import GeminiClient
from app.models.flow import PatientFlowState
from app.models.message import Message, MessageDirection, MessageStatus, MessageType
from app.models.patient import Patient
from app.utils.timezone import SAO_PAULO_TZ_NAME

from .extractors import (
    extract_date_local,
    extract_duration_info,
    extract_intent,
    extract_interval_days,
    extract_time_local,
    get_missing_fields as resolve_missing_fields,
    infer_recurrence_from_duration,
    infer_reminder_text,
    normalize_text,
    safe_int,
)
from .messages import (
    build_clarification_message,
    build_confirmation_message,
    build_limit_message,
    build_reminder_content,
)
from .models import DurationInfo, ReminderHandlingResult, ReminderIntent
from .patterns import MAX_ACTIVE_REMINDERS, MAX_HISTORY_ENTRIES, SAO_PAULO_PYTZ_TZ
from .scheduler import (
    duration_from_intent,
    duration_from_pending,
    merge_duration_info,
    resolve_duration_settings,
    resolve_schedule,
)

logger = logging.getLogger(__name__)


class ReminderHandler:
    """Orchestrates reminder request processing from patient messages."""

    def __init__(self, db: Any, gemini_client: Optional[GeminiClient] = None) -> None:
        self.db = db
        self.gemini_client = gemini_client
        self.message_service = MessageService(db)

    async def handle_response(
        self,
        patient: Patient,
        response_text: str,
        flow_state: Optional[PatientFlowState],
        state_data: Optional[Dict[str, Any]],
        response_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ReminderHandlingResult]:
        """
        Process patient response for reminder requests.

        Args:
            patient: Patient model instance
            response_text: The patient's message text
            flow_state: Current flow state (optional)
            state_data: Mutable state data dict
            response_context: Additional context about the response

        Returns:
            ReminderHandlingResult or None if no reminder intent
        """
        state_data = {} if state_data is None else state_data
        pending = state_data.get("pending_reminder")
        last_outbound = self._get_last_outbound_message(patient.id)
        conversation_history = self._get_recent_conversation(patient.id)
        local_now, tz_name = self._get_local_now()

        intent = await extract_intent(
            gemini_client=self.gemini_client,
            message_text=response_text,
            last_outbound=last_outbound,
            pending=pending,
            conversation_history=conversation_history,
            timezone_name=tz_name,
            local_now=local_now,
        )

        if intent.declined:
            cleared = bool(state_data.pop("pending_reminder", None))
            return ReminderHandlingResult(action="declined", commit_needed=cleared)

        if not intent.is_request and not pending:
            return None

        return self._process_reminder_request(
            patient=patient,
            response_text=response_text,
            intent=intent,
            pending=pending,
            state_data=state_data,
            last_outbound=last_outbound,
            local_now=local_now,
            response_context=response_context,
        )

    def _process_reminder_request(
        self,
        patient: Patient,
        response_text: str,
        intent: ReminderIntent,
        pending: Optional[Dict[str, Any]],
        state_data: Dict[str, Any],
        last_outbound: Optional[str],
        local_now: datetime,
        response_context: Optional[Dict[str, Any]],
    ) -> ReminderHandlingResult:
        """Process a confirmed reminder request."""
        pending = pending or {}
        normalized_response = normalize_text(response_text)
        reminder_id = pending.get("reminder_id") or str(uuid4())

        # Merge intent with pending data
        reminder_text = intent.reminder_text or pending.get("reminder_text")
        time_local = intent.time_local or pending.get("time_local")
        date_local = intent.date_local or pending.get("date_local")
        weekday = intent.weekday if intent.weekday is not None else pending.get("weekday")
        interval_days = (
            intent.interval_days
            if intent.interval_days is not None
            else safe_int(pending.get("interval_days"))
        )
        recurrence = (intent.recurrence or pending.get("recurrence") or "none").strip() or "none"
        duration_info = merge_duration_info(
            duration_from_intent(intent),
            duration_from_pending(pending),
        )

        last_question = pending.get("last_question") or last_outbound

        # Try to infer missing fields from context
        if not reminder_text:
            reminder_text = infer_reminder_text(last_question)

        if not time_local:
            time_local = extract_time_local(response_text, normalized=normalized_response)

        if not date_local:
            date_local = extract_date_local(
                response_text,
                local_now,
                normalized=normalized_response,
            )

        if interval_days is None:
            interval_days = extract_interval_days(response_text, normalized=normalized_response)

        if not duration_info.has_value():
            duration_info = merge_duration_info(
                duration_info,
                extract_duration_info(
                    response_text,
                    local_now,
                    normalized=normalized_response,
                ),
            )

        if interval_days and recurrence != "interval":
            recurrence = "interval"

        if recurrence == "none" and duration_info.has_value():
            recurrence = infer_recurrence_from_duration(duration_info)

        # Check for missing fields
        missing_text, missing_time, missing_interval, missing_duration = self._get_missing_fields(
            reminder_text=reminder_text,
            time_local=time_local,
            recurrence=recurrence,
            interval_days=interval_days,
            duration_info=duration_info,
        )

        # Handle numeric-only responses
        if missing_text or missing_time or missing_interval or missing_duration:
            pending_missing = set(pending.get("missing_fields") or [])
            if self._is_number_only(response_text):
                if (
                    not duration_info.has_value()
                    and "duration" in pending_missing
                    and "interval_days" not in pending_missing
                ):
                    duration_info = DurationInfo(occurrences=int(response_text.strip()))
                elif (
                    interval_days is None
                    and "interval_days" in pending_missing
                    and "duration" not in pending_missing
                ):
                    interval_days = int(response_text.strip())

            missing_text, missing_time, missing_interval, missing_duration = self._get_missing_fields(
                reminder_text=reminder_text,
                time_local=time_local,
                recurrence=recurrence,
                interval_days=interval_days,
                duration_info=duration_info,
            )

        # If still missing fields, ask for clarification
        if missing_text or missing_time or missing_interval or missing_duration:
            state_data["pending_reminder"] = self._build_pending_reminder(
                reminder_id=reminder_id,
                reminder_text=reminder_text,
                time_local=time_local,
                date_local=date_local,
                recurrence=recurrence,
                interval_days=interval_days,
                weekday=weekday,
                duration_info=duration_info,
                response_text=response_text,
                source=intent.source,
                last_question=last_question,
                response_context=response_context,
                now_local=local_now,
                missing_fields=self._collect_missing_fields(
                    missing_text=missing_text,
                    missing_time=missing_time,
                    missing_interval=missing_interval,
                    missing_duration=missing_duration,
                ),
            )
            clarification = build_clarification_message(
                missing_text=missing_text,
                missing_time=missing_time,
                missing_interval=missing_interval,
                missing_duration=missing_duration,
            )
            return ReminderHandlingResult(
                action="pending",
                follow_up_message=clarification,
                reminder_id=reminder_id,
                commit_needed=True,
            )

        # Resolve schedule
        scheduled_for, local_dt, tz_name = resolve_schedule(
            time_local=time_local,
            date_local=date_local,
            weekday=weekday,
        )
        if not scheduled_for or not local_dt or not tz_name:
            missing_time = True
            clarification = build_clarification_message(
                missing_text=not reminder_text,
                missing_time=missing_time,
                missing_interval=recurrence == "interval" and not interval_days,
                missing_duration=recurrence != "none" and not duration_info.has_value(),
            )
            state_data["pending_reminder"] = self._build_pending_reminder(
                reminder_id=reminder_id,
                reminder_text=reminder_text,
                time_local=time_local,
                date_local=date_local,
                recurrence=recurrence,
                interval_days=interval_days,
                weekday=weekday,
                duration_info=duration_info,
                response_text=response_text,
                source=intent.source,
                last_question=last_question,
                response_context=response_context,
                now_local=local_now,
                missing_fields=["time_local"],
            )
            return ReminderHandlingResult(
                action="pending",
                follow_up_message=clarification,
                reminder_id=reminder_id,
                commit_needed=True,
            )

        # Check reminder limit
        if self._has_reached_reminder_limit(patient.id):
            if pending:
                state_data.pop("pending_reminder", None)
            return ReminderHandlingResult(
                action="limit_reached",
                follow_up_message=build_limit_message(MAX_ACTIVE_REMINDERS),
                commit_needed=bool(pending),
            )

        # Resolve duration settings
        reminder_remaining, reminder_end_at = resolve_duration_settings(
            local_dt=local_dt,
            duration_info=duration_info,
        )
        metadata = self._build_reminder_metadata(
            reminder_id=reminder_id,
            reminder_text=reminder_text,
            recurrence=recurrence,
            interval_days=interval_days,
            timezone_name=tz_name,
            time_local=time_local,
            date_local=local_dt.date().isoformat(),
            weekday=weekday,
            reminder_remaining=reminder_remaining,
            reminder_end_at=reminder_end_at,
            response_context=response_context,
            source=intent.source,
        )
        content = build_reminder_content(patient.name, reminder_text)

        # Schedule the message
        self.message_service.schedule_message(
            patient_id=patient.id,
            content=content,
            scheduled_for=scheduled_for,
            message_type=MessageType.TEXT,
            message_metadata=metadata,
            auto_commit=False,
        )

        # Update state
        state_data.pop("pending_reminder", None)
        self._append_reminder_history(
            state_data=state_data,
            reminder_id=reminder_id,
            reminder_text=reminder_text,
            recurrence=recurrence,
            scheduled_for=scheduled_for,
            source=intent.source,
            now_local=local_now,
        )

        confirmation = build_confirmation_message(
            recurrence=recurrence,
            interval_days=interval_days,
            duration_info=duration_info,
        )
        return ReminderHandlingResult(
            action="scheduled",
            follow_up_message=confirmation,
            scheduled_for=scheduled_for,
            reminder_id=reminder_id,
            commit_needed=True,
        )

    # ---- Database Queries ----

    def _get_last_outbound_message(self, patient_id: Any) -> Optional[str]:
        """Get the last outbound message to this patient."""
        message = (
            self.db.query(Message)
            .filter(
                Message.patient_id == patient_id,
                Message.direction == MessageDirection.OUTBOUND,
                Message.status.in_(
                    [MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ]
                ),
            )
            .order_by(Message.created_at.desc())
            .first()
        )
        return message.content if message else None

    def _get_recent_conversation(self, patient_id: Any, limit: int = 6) -> List[Dict[str, str]]:
        """Get recent conversation history."""
        messages = (
            self.db.query(Message)
            .filter(
                Message.patient_id == patient_id,
                (
                    (Message.direction == MessageDirection.INBOUND)
                    | (
                        (Message.direction == MessageDirection.OUTBOUND)
                        & Message.status.in_(
                            [
                                MessageStatus.SENT,
                                MessageStatus.DELIVERED,
                                MessageStatus.READ,
                            ]
                        )
                    )
                ),
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )
        history: List[Dict[str, str]] = []
        for message in reversed(messages):
            text = (message.content or "").strip()
            if not text:
                continue
            role = "clinic" if message.direction == MessageDirection.OUTBOUND else "patient"
            history.append({"role": role, "text": text})
        return history

    def _get_local_now(self) -> tuple[datetime, str]:
        """Get current local time and timezone name."""
        return datetime.now(SAO_PAULO_PYTZ_TZ), SAO_PAULO_TZ_NAME

    def _has_reached_reminder_limit(self, patient_id: Any) -> bool:
        """Check if patient has reached max active reminders (with row-level lock)."""
        reminder_id_expr = Message.message_metadata["reminder_id"].astext
        # Use SELECT ... FOR UPDATE to reduce race conditions across reminders
        rows = (
            self.db.execute(
                select(reminder_id_expr)
                .where(
                    Message.patient_id == patient_id,
                    Message.direction == MessageDirection.OUTBOUND,
                    Message.status.in_([MessageStatus.PENDING, MessageStatus.SCHEDULED]),
                    Message.message_metadata["follow_up_type"].astext == "custom_reminder",
                )
                .with_for_update(skip_locked=True)
            )
            .all()
        )
        active_ids = {row[0] for row in rows if row and row[0]}
        return len(active_ids) >= MAX_ACTIVE_REMINDERS

    # ---- State Builders ----

    def _build_pending_reminder(
        self,
        reminder_id: str,
        reminder_text: Optional[str],
        time_local: Optional[str],
        date_local: Optional[str],
        recurrence: str,
        interval_days: Optional[int],
        weekday: Optional[int],
        duration_info: DurationInfo,
        response_text: str,
        source: str,
        last_question: Optional[str],
        response_context: Optional[Dict[str, Any]],
        now_local: datetime,
        missing_fields: List[str],
    ) -> Dict[str, Any]:
        """Build pending reminder data structure."""
        return {
            "reminder_id": reminder_id,
            "requested_at": now_local.isoformat(),
            "reminder_text": reminder_text,
            "time_local": time_local,
            "date_local": date_local,
            "recurrence": recurrence,
            "interval_days": interval_days,
            "weekday": weekday,
            "duration_occurrences": duration_info.occurrences,
            "duration_days": duration_info.days,
            "duration_weeks": duration_info.weeks,
            "duration_months": duration_info.months,
            "duration_end_date": duration_info.end_date,
            "last_response": response_text,
            "source": source,
            "last_question": last_question,
            "response_context": response_context,
            "missing_fields": missing_fields,
        }

    def _append_reminder_history(
        self,
        state_data: Dict[str, Any],
        reminder_id: str,
        reminder_text: str,
        recurrence: str,
        scheduled_for: datetime,
        source: str,
        now_local: datetime,
    ) -> None:
        """Append to reminder history (limited to MAX_HISTORY_ENTRIES)."""
        history = list(state_data.get("reminder_history", []))
        history.append(
            {
                "reminder_id": reminder_id,
                "reminder_text": reminder_text,
                "recurrence": recurrence,
                "scheduled_for": scheduled_for.isoformat(),
                "created_at": now_local.isoformat(),
                "source": source,
            }
        )
        state_data["reminder_history"] = history[-MAX_HISTORY_ENTRIES:]

    def _build_reminder_metadata(
        self,
        reminder_id: str,
        reminder_text: str,
        recurrence: str,
        interval_days: Optional[int],
        timezone_name: str,
        time_local: str,
        date_local: str,
        weekday: Optional[int],
        reminder_remaining: Optional[int],
        reminder_end_at: Optional[datetime],
        response_context: Optional[Dict[str, Any]],
        source: str,
    ) -> Dict[str, Any]:
        """Build message metadata for scheduled reminder."""
        return {
            "source": "patient_reminder",
            "follow_up_type": "custom_reminder",
            "reminder_id": reminder_id,
            "reminder_text": reminder_text,
            "reminder_recurrence": recurrence,
            "reminder_interval_days": interval_days,
            "reminder_timezone": timezone_name,
            "reminder_time_local": time_local,
            "reminder_date_local": date_local,
            "reminder_weekday": weekday,
            "reminder_sequence": 1,
            "reminder_remaining": reminder_remaining,
            "reminder_end_at": reminder_end_at.isoformat() if reminder_end_at else None,
            "reminder_source": source,
            "response_context": response_context,
        }

    # ---- Helpers ----

    def _get_missing_fields(
        self,
        reminder_text: Optional[str],
        time_local: Optional[str],
        recurrence: str,
        interval_days: Optional[int],
        duration_info: DurationInfo,
    ) -> tuple[bool, bool, bool, bool]:
        """Determine which required fields are missing."""
        return resolve_missing_fields(
            reminder_text=reminder_text,
            time_local=time_local,
            recurrence=recurrence,
            interval_days=interval_days,
            duration_info=duration_info,
        )

    def _collect_missing_fields(
        self,
        missing_text: bool,
        missing_time: bool,
        missing_interval: bool,
        missing_duration: bool,
    ) -> List[str]:
        """Collect list of missing field names."""
        missing_fields: List[str] = []
        if missing_text:
            missing_fields.append("reminder_text")
        if missing_time:
            missing_fields.append("time_local")
        if missing_interval:
            missing_fields.append("interval_days")
        if missing_duration:
            missing_fields.append("duration")
        return missing_fields

    def _is_number_only(self, text: str) -> bool:
        """Check if text is just a number (1-3 digits)."""
        return text.strip().isdigit() and len(text.strip()) <= 3
