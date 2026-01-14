from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime, timezone
import hashlib
import logging

from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, func, or_

from app.models.message import Message, MessageDirection, MessageStatus, MessageType
from app.repositories.base import BaseRepository
from app.exceptions import ValidationError

logger = logging.getLogger(__name__)


class MessageRepository(BaseRepository[Message]):
    def __init__(self, db: Session):
        super().__init__(db, Message)
        # Initialize integrity service
        # MessageIntegrityService is defined in this file
        self.integrity_service = MessageIntegrityService(db)

    def list_v2(
        self,
        filters: Dict,
        cursor_data: Optional[Dict] = None,
        limit: int = 20,
        sort_order: str = "desc",
        eager_load: bool = False,
    ) -> List[Message]:
        """
        List messages with cursor pagination and advanced filters.
        """
        query = self.db.query(Message)

        if eager_load:
            query = query.options(joinedload(Message.patient))

        criteria = []

        if filters.get("patient_id"):
            criteria.append(Message.patient_id == filters["patient_id"])

        if filters.get("status"):
            criteria.append(Message.status == filters["status"])

        if filters.get("type"):
            criteria.append(Message.type == filters["type"])

        if filters.get("direction"):
            criteria.append(Message.direction == filters["direction"])

        if filters.get("start_date"):
            criteria.append(Message.created_at >= filters["start_date"])

        if filters.get("end_date"):
            criteria.append(Message.created_at <= filters["end_date"])

        # Cursor Pagination
        if cursor_data and "id" in cursor_data:
            from uuid import UUID

            cid = UUID(cursor_data["id"])
            cdate = cursor_data["created_at"]
            # Assuming cdate is datetime object or handled before calling
            if isinstance(cdate, str):
                cdate = datetime.fromisoformat(cdate.replace("Z", "+00:00"))

            if sort_order == "desc":
                criteria.append(
                    or_(
                        Message.created_at < cdate,
                        and_(Message.created_at == cdate, Message.id < cid),
                    )
                )
            else:
                criteria.append(
                    or_(
                        Message.created_at > cdate,
                        and_(Message.created_at == cdate, Message.id > cid),
                    )
                )

        if criteria:
            query = query.filter(and_(*criteria))

        if sort_order == "desc":
            query = query.order_by(Message.created_at.desc(), Message.id.desc())
        else:
            query = query.order_by(Message.created_at.asc(), Message.id.asc())

        return query.limit(limit + 1).all()

    def get_by_patient(
        self, patient_id: UUID, skip: int = 0, limit: int = 100, eager_load: bool = True
    ) -> List[Message]:
        """
        Get messages by patient with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default to prevent N+1 queries.

        Relationships loaded when eager_load=True:
        - patient: Patient information (joinedload - 1:1)

        Args:
            patient_id: UUID of the patient
            skip: Pagination offset
            limit: Maximum records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of messages with relationships pre-loaded
        """
        query = (
            self.db.query(Message)
            .filter(Message.patient_id == patient_id)
            .order_by(Message.created_at.desc())
        )

        if eager_load:
            query = query.options(joinedload(Message.patient))

        return query.offset(skip).limit(limit).all()

    def get_by_whatsapp_id(self, whatsapp_id: str) -> Optional[Message]:
        """Get message by WhatsApp ID"""
        return self.db.query(Message).filter(Message.whatsapp_id == whatsapp_id).first()

    def get_by_idempotency_key(self, patient_id: UUID, idempotency_key: str) -> Optional[Message]:
        """
        Get message by idempotency key for duplicate detection.
        
        Used to prevent duplicate inbound messages from being stored.
        
        Args:
            patient_id: UUID of the patient
            idempotency_key: SHA256 hash of content + whatsapp_id
            
        Returns:
            Existing message if duplicate, None otherwise
        """
        return (
            self.db.query(Message)
            .filter(
                Message.patient_id == patient_id,
                Message.idempotency_key == idempotency_key
            )
            .first()
        )

    def get_pending_messages(
        self,
        skip: int = 0,
        limit: int = 100,
        patient_id: Optional[UUID] = None,
        eager_load: bool = True,
    ) -> List[Message]:
        """
        Get pending messages for sending with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default for patient relationship.

        Args:
            skip: Pagination offset
            limit: Maximum records to return
            patient_id: Optional patient filter
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of pending messages with relationships pre-loaded
        """
        query = (
            self.db.query(Message)
            .filter(Message.status == MessageStatus.PENDING)
            .filter(Message.direction == MessageDirection.OUTBOUND)
        )

        if patient_id:
            query = query.filter(Message.patient_id == patient_id)

        if eager_load:
            query = query.options(joinedload(Message.patient))

        return (
            query.order_by(Message.scheduled_for.asc()).offset(skip).limit(limit).all()
        )

    def get_scheduled_messages(
        self, before_time: datetime, skip: int = 0, limit: int = 100
    ) -> List[Message]:
        """Get messages scheduled before a specific time"""
        return (
            self.db.query(Message)
            .filter(Message.status == MessageStatus.PENDING)
            .filter(Message.scheduled_for <= before_time)
            .order_by(Message.scheduled_for.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_recent_follow_up_message_time(
        self, patient_id: UUID, since: datetime, limit: int = 20
    ) -> Optional[datetime]:
        """
        Get the most recent follow-up message time for a patient since a timestamp.

        Args:
            patient_id: Patient UUID
            since: Lower bound for message creation time
            limit: Max messages to scan (ordered by newest first)

        Returns:
            Datetime for the latest follow-up message or None
        """
        query = (
            self.db.query(Message)
            .filter(Message.patient_id == patient_id)
            .filter(Message.direction == MessageDirection.OUTBOUND)
            .filter(Message.created_at >= since)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )

        def _normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
            if value and value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value

        for message in query.all():
            metadata = message.message_metadata or {}
            if metadata.get("follow_up_type"):
                candidate = message.sent_at or message.scheduled_for or message.created_at
                return _normalize_datetime(candidate)

        return None

    def get_conversation_history(
        self, patient_id: UUID, skip: int = 0, limit: int = 50, eager_load: bool = True
    ) -> List[Message]:
        """
        Get conversation history for a patient with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default.

        Args:
            patient_id: UUID of the patient
            skip: Pagination offset
            limit: Maximum records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of messages ordered chronologically with relationships pre-loaded
        """
        query = (
            self.db.query(Message)
            .filter(Message.patient_id == patient_id)
            .order_by(Message.created_at.asc())
        )

        if eager_load:
            query = query.options(joinedload(Message.patient))

        return query.offset(skip).limit(limit).all()

    def get_failed_messages(
        self, skip: int = 0, limit: int = 100, eager_load: bool = True
    ) -> List[Message]:
        """
        Get failed messages for retry processing with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default.

        Args:
            skip: Pagination offset
            limit: Maximum records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of failed messages with relationships pre-loaded
        """
        query = (
            self.db.query(Message)
            .filter(Message.status == MessageStatus.FAILED)
            .filter(Message.direction == MessageDirection.OUTBOUND)
            .order_by(Message.created_at.desc())
        )

        if eager_load:
            query = query.options(joinedload(Message.patient))

        return query.offset(skip).limit(limit).all()

    def get_by_status(
        self,
        status: MessageStatus,
        skip: int = 0,
        limit: int = 100,
        eager_load: bool = True,
    ) -> List[Message]:
        """
        Get messages by status with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default.

        Args:
            status: Message status to filter by
            skip: Pagination offset
            limit: Maximum records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of messages with relationships pre-loaded
        """
        query = (
            self.db.query(Message)
            .filter(Message.status == status)
            .order_by(Message.created_at.desc())
        )

        if eager_load:
            query = query.options(joinedload(Message.patient))

        return query.offset(skip).limit(limit).all()

    def count_by_patient(self, patient_id: UUID) -> int:
        """Count total messages for a patient"""
        from sqlalchemy import func

        return (
            self.db.query(func.count(Message.id))
            .filter(Message.patient_id == patient_id)
            .scalar()
        ) or 0

    def count_conversation_history(self, patient_id: UUID) -> int:
        """Count total messages in a patient's conversation"""
        return self.count_by_patient(patient_id)

    def count_pending_messages(self, patient_id: Optional[UUID] = None) -> int:
        """Count total pending messages"""
        from sqlalchemy import func

        query = (
            self.db.query(func.count(Message.id))
            .filter(Message.status == MessageStatus.PENDING)
            .filter(Message.direction == MessageDirection.OUTBOUND)
        )
        if patient_id:
            query = query.filter(Message.patient_id == patient_id)
        return query.scalar() or 0

    def count_failed_messages(self, patient_id: Optional[UUID] = None) -> int:
        """Count total failed messages"""
        from sqlalchemy import func

        query = (
            self.db.query(func.count(Message.id))
            .filter(Message.status == MessageStatus.FAILED)
            .filter(Message.direction == MessageDirection.OUTBOUND)
        )
        if patient_id:
            query = query.filter(Message.patient_id == patient_id)
        return query.scalar() or 0

    def count_by_status(
        self, status: MessageStatus, patient_id: Optional[UUID] = None
    ) -> int:
        """Count messages by status"""
        from sqlalchemy import func

        query = self.db.query(func.count(Message.id)).filter(Message.status == status)
        if patient_id:
            query = query.filter(Message.patient_id == patient_id)
        return query.scalar() or 0

    def get_message_statistics(
        self,
        patient_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """
        Get message statistics aggregated at database level.

        PERFORMANCE FIX #3: Uses database aggregation instead of loading all messages
        """
        query = self.db.query(Message.status, func.count(Message.id).label("count"))

        if patient_id:
            query = query.filter(Message.patient_id == patient_id)

        if start_date:
            query = query.filter(Message.created_at >= start_date)

        if end_date:
            query = query.filter(Message.created_at <= end_date)

        results = query.group_by(Message.status).all()

        # Initialize all statuses with 0
        statistics = {status.value: 0 for status in MessageStatus}

        # Update with actual counts
        for status, count in results:
            statistics[status.value] = count

        return statistics

    def get_messages_with_filters(
        self,
        skip: int = 0,
        limit: int = 100,
        patient_id: Optional[UUID] = None,
        status: Optional[MessageStatus] = None,
        message_type: Optional[MessageType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        eager_load: bool = False,
    ) -> List[Message]:
        """
        Get messages with comprehensive filtering at database level.

        PERFORMANCE FIX #2: All filtering done at database level, not client-side.
        This prevents loading unnecessary data and eliminates N+1 queries.
        """
        query = self.db.query(Message)

        # PERFORMANCE: Eager load patient relationship if requested
        if eager_load:
            query = query.options(joinedload(Message.patient))

        # Build filter conditions (all executed at database level)
        filters = []

        if patient_id:
            filters.append(Message.patient_id == patient_id)

        if status:
            filters.append(Message.status == status)

        if message_type:
            filters.append(Message.type == message_type)

        if start_date:
            filters.append(Message.created_at >= start_date)

        if end_date:
            filters.append(Message.created_at <= end_date)

        # Apply all filters
        if filters:
            query = query.filter(and_(*filters))

        # Order by created_at and apply pagination
        return query.order_by(Message.created_at.desc()).offset(skip).limit(limit).all()

    def count_messages_with_filters(
        self,
        patient_id: Optional[UUID] = None,
        status: Optional[MessageStatus] = None,
        message_type: Optional[MessageType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """
        Count messages with filters (efficient query without loading data).

        PERFORMANCE FIX #2: Uses COUNT at database level for efficiency.
        """
        query = self.db.query(func.count(Message.id))

        # Build filter conditions
        filters = []

        if patient_id:
            filters.append(Message.patient_id == patient_id)

        if status:
            filters.append(Message.status == status)

        if message_type:
            filters.append(Message.type == message_type)

        if start_date:
            filters.append(Message.created_at >= start_date)

        if end_date:
            filters.append(Message.created_at <= end_date)

        # Apply all filters
        if filters:
            query = query.filter(and_(*filters))

        return query.scalar() or 0

    async def create_with_integrity_check(self, message_data: Dict) -> Message:
        """Create message with integrity validation"""
        try:
            # FIX #3: Validate message integrity before creation
            await self.integrity_service.validate_message_creation(message_data)

            # Generate integrity checksum
            message_data["integrity_checksum"] = (
                self.integrity_service.generate_message_checksum(message_data)
            )

            # Create message
            message = Message(**message_data)
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)

            logger.info(f"Message created with integrity validation: {message.id}")
            return message

        except ValidationError:
            raise
        except IntegrityError as e:
            logger.error(f"Message integrity constraint violation: {e}")
            self.db.rollback()
            raise ValidationError(
                "Message creation failed due to integrity constraints"
            )
        except Exception as e:
            logger.error(f"Unexpected error during message creation: {e}")
            self.db.rollback()
            raise

    async def validate_conversation_integrity(self, patient_id: UUID) -> Dict[str, any]:
        """Validate integrity of entire conversation for a patient"""
        try:
            return await self.integrity_service.validate_conversation_integrity(
                patient_id
            )
        except Exception as e:
            logger.error(f"Conversation integrity validation failed: {e}")
            raise


class MessageIntegrityService:
    """FIX #3: Service for message data integrity validation"""

    def __init__(self, db: Session):
        self.db = db

    async def validate_message_creation(self, message_data: Dict) -> None:
        """Validate message data before creation"""
        try:
            # Validate required fields
            required_fields = ["patient_id", "direction", "type", "content"]
            for field in required_fields:
                if field not in message_data or not message_data[field]:
                    raise ValidationError(
                        f"Required field '{field}' is missing or empty"
                    )

            # Validate patient exists
            from app.models.patient import Patient

            patient = (
                self.db.query(Patient)
                .filter(Patient.id == message_data["patient_id"])
                .first()
            )
            if not patient:
                raise ValidationError(f"Patient {message_data['patient_id']} not found")

            # Validate content completeness
            content = message_data["content"]
            if not content or len(content.strip()) == 0:
                raise ValidationError("Message content cannot be empty")

            # Validate content length
            if len(content) > 4096:  # WhatsApp message limit
                raise ValidationError(
                    "Message content exceeds maximum length (4096 characters)"
                )

            # Validate message direction and status consistency
            direction = message_data.get("direction")
            status = message_data.get("status", MessageStatus.PENDING)

            if (
                direction == MessageDirection.INBOUND
                and status == MessageStatus.PENDING
            ):
                raise ValidationError("Inbound messages cannot have PENDING status")

            # Validate chronological order
            await self._validate_chronological_order(message_data)

            logger.info(
                f"Message validation passed for patient {message_data['patient_id']}"
            )

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Message validation error: {e}")
            raise ValidationError(f"Message validation failed: {str(e)}")

    async def _validate_chronological_order(self, message_data: Dict) -> None:
        """Validate message chronological order"""
        try:
            patient_id = message_data["patient_id"]
            message_timestamp = message_data.get("created_at", datetime.now(timezone.utc))

            # Get the most recent message for this patient
            latest_message = (
                self.db.query(Message)
                .filter(Message.patient_id == patient_id)
                .order_by(Message.created_at.desc())
                .first()
            )

            if latest_message:
                # Allow messages created within 1 minute of each other (clock skew tolerance)
                time_diff = abs(
                    (message_timestamp - latest_message.created_at).total_seconds()
                )
                if time_diff > 60:  # More than 1 minute
                    if message_timestamp < latest_message.created_at:
                        logger.warning(
                            f"Message timestamp {message_timestamp} is before latest message {latest_message.created_at} "
                            f"for patient {patient_id}"
                        )
                        # Don't fail validation but log the issue

        except Exception as e:
            logger.error(f"Chronological order validation error: {e}")
            # Don't fail on chronological validation errors, just log them

    def generate_message_checksum(self, message_data: Dict) -> str:
        """Generate integrity checksum for message data"""
        try:
            # Include critical fields in checksum
            checksum_fields = {
                "patient_id": str(message_data.get("patient_id", "")),
                "direction": message_data.get("direction", ""),
                "type": message_data.get("type", ""),
                "content": message_data.get("content", ""),
                "created_at": message_data.get(
                    "created_at", datetime.now(timezone.utc)
                ).isoformat(),
            }

            # Sort fields for consistent hashing
            checksum_string = "|".join(
                f"{k}:{v}" for k, v in sorted(checksum_fields.items())
            )
            return hashlib.sha256(checksum_string.encode("utf-8")).hexdigest()

        except Exception as e:
            logger.error(f"Message checksum generation failed: {e}")
            return ""

    async def validate_conversation_integrity(self, patient_id: UUID) -> Dict[str, any]:
        """Validate integrity of entire conversation for a patient"""
        try:
            # Get all messages for patient
            messages = (
                self.db.query(Message)
                .filter(Message.patient_id == patient_id)
                .order_by(Message.created_at.asc())
                .all()
            )

            validation_result = {
                "patient_id": str(patient_id),
                "total_messages": len(messages),
                "issues": [],
                "checksum_mismatches": 0,
                "chronological_issues": 0,
                "orphaned_messages": 0,
                "overall_integrity": True,
            }

            if not messages:
                return validation_result

            # Validate checksums
            for message in messages:
                if (
                    hasattr(message, "integrity_checksum")
                    and message.integrity_checksum
                ):
                    expected_checksum = self.generate_message_checksum(
                        {
                            "patient_id": message.patient_id,
                            "direction": message.direction,
                            "type": message.type,
                            "content": message.content,
                            "created_at": message.created_at,
                        }
                    )

                    if message.integrity_checksum != expected_checksum:
                        validation_result["checksum_mismatches"] += 1
                        validation_result["issues"].append(
                            f"Checksum mismatch for message {message.id}"
                        )
                        validation_result["overall_integrity"] = False

            # Validate chronological order
            for i in range(1, len(messages)):
                if messages[i].created_at < messages[i - 1].created_at:
                    validation_result["chronological_issues"] += 1
                    validation_result["issues"].append(
                        f"Chronological order issue: message {messages[i].id} is out of order"
                    )
                    validation_result["overall_integrity"] = False

            # Check for orphaned messages (missing patient)
            from app.models.patient import Patient

            patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
            if not patient:
                validation_result["orphaned_messages"] = len(messages)
                validation_result["issues"].append(
                    f"All {len(messages)} messages are orphaned (patient not found)"
                )
                validation_result["overall_integrity"] = False

            # Validate message flow consistency
            flow_issues = await self._validate_message_flow_consistency(messages)
            validation_result["issues"].extend(flow_issues)

            if flow_issues:
                validation_result["overall_integrity"] = False

            if validation_result["overall_integrity"]:
                logger.info(
                    f"Conversation integrity validation passed for patient {patient_id}"
                )
            else:
                logger.warning(
                    f"Conversation integrity issues found for patient {patient_id}: {validation_result['issues']}"
                )

            return validation_result

        except Exception as e:
            logger.error(f"Conversation integrity validation error: {e}")
            return {
                "patient_id": str(patient_id),
                "error": str(e),
                "overall_integrity": False,
            }

    async def _validate_message_flow_consistency(
        self, messages: List[Message]
    ) -> List[str]:
        """Validate message flow consistency within conversation"""
        issues = []

        try:
            # Check for balanced conversation (not too many outbound without response)
            inbound_count = sum(
                1 for msg in messages if msg.direction == MessageDirection.INBOUND
            )
            outbound_count = sum(
                1 for msg in messages if msg.direction == MessageDirection.OUTBOUND
            )

            if outbound_count > 0:
                response_rate = inbound_count / outbound_count
                if response_rate < 0.1:  # Less than 10% response rate
                    issues.append(f"Low patient response rate: {response_rate:.2%}")

            # Check for message sequences that don't make sense
            consecutive_outbound = 0
            for message in messages:
                if message.direction == MessageDirection.OUTBOUND:
                    consecutive_outbound += 1
                    if (
                        consecutive_outbound > 5
                    ):  # More than 5 consecutive outbound messages
                        issues.append(
                            f"Too many consecutive outbound messages detected (>{consecutive_outbound})"
                        )
                        break
                else:
                    consecutive_outbound = 0

            # Check for missing required metadata
            for message in messages:
                if message.direction == MessageDirection.OUTBOUND:
                    metadata = getattr(message, "message_metadata", {})
                    if not metadata or "flow_context" not in metadata:
                        issues.append(
                            f"Missing flow context for outbound message {message.id}"
                        )

        except Exception as e:
            logger.error(f"Message flow consistency validation error: {e}")
            issues.append(f"Flow consistency validation error: {str(e)}")

        return issues

    async def repair_conversation_integrity(self, patient_id: UUID) -> Dict[str, any]:
        """Attempt to repair conversation integrity issues"""
        try:
            # Get validation results first
            validation_result = await self.validate_conversation_integrity(patient_id)

            if validation_result["overall_integrity"]:
                return {
                    "patient_id": str(patient_id),
                    "repairs_needed": False,
                    "message": "Conversation integrity is already intact",
                }

            repairs_made = []

            # Repair checksum mismatches
            if validation_result["checksum_mismatches"] > 0:
                messages = (
                    self.db.query(Message)
                    .filter(Message.patient_id == patient_id)
                    .all()
                )

                for message in messages:
                    correct_checksum = self.generate_message_checksum(
                        {
                            "patient_id": message.patient_id,
                            "direction": message.direction,
                            "type": message.type,
                            "content": message.content,
                            "created_at": message.created_at,
                        }
                    )

                    if (
                        hasattr(message, "integrity_checksum")
                        and message.integrity_checksum != correct_checksum
                    ):
                        message.integrity_checksum = correct_checksum
                        repairs_made.append(
                            f"Updated checksum for message {message.id}"
                        )

                self.db.commit()

            logger.info(
                f"Conversation integrity repair completed for patient {patient_id}: {len(repairs_made)} repairs made"
            )

            return {
                "patient_id": str(patient_id),
                "repairs_needed": True,
                "repairs_made": repairs_made,
                "message": f"Completed {len(repairs_made)} integrity repairs",
            }

        except Exception as e:
            logger.error(f"Conversation integrity repair failed: {e}")
            self.db.rollback()
            return {
                "patient_id": str(patient_id),
                "error": str(e),
                "repairs_needed": True,
                "repairs_made": [],
            }
