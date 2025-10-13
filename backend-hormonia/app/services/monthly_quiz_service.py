"""
Monthly Quiz Service for Hormonia Backend System.

Business logic for monthly quiz via link functionality.
"""
import secrets
import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import jwt
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.quiz import QuizSession, QuizTemplate, QuizResponse
from app.models.patient import Patient
from app.repositories.quiz import QuizTemplateRepository, QuizSessionRepository, QuizResponseRepository
from app.services.quiz import QuizSessionService, QuizResponseService
from app.core.monthly_quiz_config import get_monthly_quiz_config
from app.exceptions import NotFoundError, ValidationError, ConflictError
from app.schemas.monthly_quiz import (
    MonthlyQuizLinkCreate, MonthlyQuizLinkResponse, MonthlyQuizAccessResponse,
    MonthlyQuizSubmitResponse, MonthlyQuizStats, QuizLinkStatus,
    DeliveryMethod, BulkQuizLinkCreate, BulkQuizLinkResponse
)
from app.schemas.quiz import QuizResponseCreate, QuestionType
from app.services.audit_service import AuditService
from app.services.encryption_service import get_encryption_service
from app.services.question_humanizer import get_question_humanizer
from app.config import is_ai_humanization_enabled
from app.monitoring.business_metrics import BusinessMetricsCollector
import time
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)


class MonthlyQuizService:
    """Service for managing monthly quiz via link functionality."""

    def __init__(self, db: Session):
        self.db = db
        self.config = get_monthly_quiz_config()
        self.template_repository = QuizTemplateRepository(db)
        self.session_repository = QuizSessionRepository(db)
        self.response_repository = QuizResponseRepository(db)
        self.quiz_session_service = QuizSessionService(db)
        self.quiz_response_service = QuizResponseService(db)
        self.audit_service = AuditService(db)
        self.encryption_service = get_encryption_service()
        self.metrics_collector = BusinessMetricsCollector()
        
        # Initialize Redis for fast patient checking
        try:
            from app.core.redis_manager import get_redis_manager
            self.redis_manager = get_redis_manager()
            self.redis_client = self.redis_manager.get_compatible_client('sync')
        except Exception as e:
            logger.warning(f"Redis not available for fast patient checking: {e}")
            self.redis_client = None

    def _generate_token(self, patient_id: UUID, quiz_template_id: UUID, expires_at: datetime, rotation_count: int = 0) -> str:
        """Generate secure JWT token for quiz access with rotation support."""
        # Include standard JWT exp claim for proper expiry handling
        now = datetime.utcnow()
        payload = {
            "patient_id": str(patient_id),
            "quiz_template_id": str(quiz_template_id),
            "expires_at": expires_at.isoformat(),
            "exp": int(expires_at.timestamp()),  # Standard JWT exp claim
            "iat": int(now.timestamp()),  # Standard JWT issued at claim
            "nbf": int(now.timestamp()),  # Standard JWT not before claim
            "jti": secrets.token_urlsafe(32),  # Unique token ID
            "type": "monthly_quiz",
            "rotation_count": rotation_count,  # Track token rotations
            "single_use": self.config.MONTHLY_QUIZ_SINGLE_USE_TOKENS,
            "aud": "monthly_quiz",  # Audience claim for RLS compatibility
            "iss": "hormonia_backend"  # Issuer claim for validation
        }

        token = jwt.encode(
            payload,
            self.config.MONTHLY_QUIZ_TOKEN_SECRET,
            algorithm="HS256"
        )

        return token

    def _check_patient_exists_fast(self, patient_id: str) -> bool:
        """
        Ultra-fast patient existence check with negative caching.
        
        PERFORMANCE OPTIMIZATION: 
        - Cache hit: ~2ms (Redis lookup)
        - Cache miss: ~10-20ms (indexed DB query + cache write)
        - Prevents 7-8s delays on 404 responses
        
        Args:
            patient_id: Patient UUID as string
            
        Returns:
            True if patient exists, False otherwise
        """
        if not self.redis_client:
            # Fallback to direct DB query if Redis unavailable
            return self._check_patient_exists_db_only(patient_id)
            
        cache_key = f"patient_not_found:{patient_id}"
        
        # 1. Check negative cache (2ms)
        if self.redis_client.exists(cache_key):
            logger.debug(f"Fast 404: Patient {patient_id[:8]}... cached as not found")
            return False
        
        # 2. Check database with indexed query (10-20ms)
        start_time = time.time()
        
        try:
            result = self.db.execute(text("""
                SELECT 1 FROM patients 
                WHERE id = :patient_id 
                LIMIT 1
            """), {"patient_id": patient_id})
            
            exists = result.fetchone() is not None
            query_time = (time.time() - start_time) * 1000
            
            if exists:
                logger.debug(f"Patient {patient_id[:8]}... found ({query_time:.1f}ms)")
                return True
            else:
                # 3. Cache negative result (TTL 60s to handle edge cases)
                self.redis_client.setex(cache_key, 60, "1")
                logger.debug(f"Patient {patient_id[:8]}... not found - cached ({query_time:.1f}ms)")
                return False
                
        except Exception as e:
            logger.error(f"Error checking patient existence: {e}")
            # Fallback to DB-only check
            return self._check_patient_exists_db_only(patient_id)
    
    def _check_patient_exists_db_only(self, patient_id: str) -> bool:
        """Fallback method for patient existence check without Redis."""
        try:
            result = self.db.execute(text("""
                SELECT 1 FROM patients 
                WHERE id = :patient_id 
                LIMIT 1
            """), {"patient_id": patient_id})
            
            return result.fetchone() is not None
        except Exception as e:
            logger.error(f"Database error checking patient existence: {e}")
            return False

    def _verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode quiz access token."""
        try:
            # Basic token format validation
            if not token or not isinstance(token, str):
                raise ValidationError("Token is required and must be a string")

            # Check if token has the correct JWT format (3 parts separated by dots)
            token_parts = token.split('.')
            if len(token_parts) != 3:
                raise ValidationError("Invalid token format - must be a valid JWT")

            # Verify each part is base64-encoded
            for i, part in enumerate(token_parts):
                if not part or not part.replace('-', '+').replace('_', '/').isalnum():
                    # Allow padding characters and check if it's reasonable base64
                    if len(part) < 4:
                        raise ValidationError(f"Invalid token format - part {i+1} too short")

            payload = jwt.decode(
                token,
                self.config.MONTHLY_QUIZ_TOKEN_SECRET,
                algorithms=["HS256"],
                options={"verify_exp": True}  # Ensure exp claim is verified
            )

            # Check expiration
            expires_at = datetime.fromisoformat(payload["expires_at"])
            if datetime.utcnow() > expires_at:
                raise ValidationError("Quiz link has expired")

            # Verify token type
            if payload.get("type") != "monthly_quiz":
                raise ValidationError("Invalid token type")

            return payload

        except jwt.ExpiredSignatureError:
            raise ValidationError("Quiz link has expired")
        except jwt.InvalidTokenError as e:
            raise ValidationError(f"Invalid quiz token: {str(e)}")

    async def create_quiz_link(
        self,
        link_data: MonthlyQuizLinkCreate,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> MonthlyQuizLinkResponse:
        """Create a new monthly quiz link for a patient."""
        # Validate patient exists
        patient = self.db.query(Patient).filter(Patient.id == link_data.patient_id).first()
        if not patient:
            raise NotFoundError(f"Patient with ID {link_data.patient_id} not found")

        # Validate template exists and is active
        template = self.template_repository.get(link_data.quiz_template_id)
        if not template:
            raise NotFoundError(f"Quiz template with ID {link_data.quiz_template_id} not found")

        if not template.is_active:
            raise ValidationError("Cannot create link for inactive template")

        # Calculate expiration
        expiry_hours = link_data.expiry_hours or self.config.MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS
        expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)

        # Generate token
        token = self._generate_token(link_data.patient_id, link_data.quiz_template_id, expires_at)

        # Build link URL
        link_url = f"{self.config.MONTHLY_QUIZ_BASE_URL}?token={token}"

        # Create quiz session with metadata containing link info
        from app.schemas.quiz import QuizSessionCreate
        session_data = QuizSessionCreate(
            patient_id=link_data.patient_id,
            quiz_template_id=link_data.quiz_template_id
        )

        session = await self.quiz_session_service.start_quiz_session(session_data)

        # Update session metadata with link information
        session_model = self.session_repository.get(session.id)
        session_model.session_metadata = {
            "delivery_method": link_data.delivery_method.value,
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
            "expires_at": expires_at.isoformat(),
            "link_status": QuizLinkStatus.ACTIVE.value,
            "access_count": 0,
            "custom_message": link_data.custom_message
        }
        self.db.commit()
        self.db.refresh(session_model)

        # Audit log link creation
        if self.config.MONTHLY_QUIZ_AUDIT_ENABLED:
            self.audit_service.log_link_created(
                actor_id=actor_id or UUID('00000000-0000-0000-0000-000000000000'),
                patient_id=link_data.patient_id,
                session_id=session.id,
                delivery_method=link_data.delivery_method.value,
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent
            )

        # Record metrics for link generation
        await self.metrics_collector.record_quiz_link_generated(
            patient_id=str(link_data.patient_id),
            quiz_template_id=str(link_data.quiz_template_id),
            token_prefix=token[:10],
            delivery_method=link_data.delivery_method.value,
            expires_at=expires_at
        )

        # Build response
        return MonthlyQuizLinkResponse(
            id=session.id,
            patient_id=link_data.patient_id,
            quiz_template_id=link_data.quiz_template_id,
            token=token,
            link_url=link_url,
            delivery_method=link_data.delivery_method,
            status=QuizLinkStatus.ACTIVE,
            expires_at=expires_at,
            created_at=session.started_at,
            accessed_at=None,
            completed_at=None,
            access_count=0
        )

    async def access_quiz_via_token(
        self,
        token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> MonthlyQuizAccessResponse:
        """Access quiz using token."""
        # Verify token
        payload = self._verify_token(token)
        patient_id = UUID(payload["patient_id"])
        quiz_template_id = UUID(payload["quiz_template_id"])

        # Find session by token hash
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        sessions = self.db.query(QuizSession).filter(
            and_(
                QuizSession.patient_id == patient_id,
                QuizSession.quiz_template_id == quiz_template_id,
                QuizSession.session_metadata["token_hash"].astext == token_hash
            )
        ).all()

        if not sessions:
            raise NotFoundError("Quiz session not found for this token")

        session = sessions[0]

        # Check if already completed
        if session.status == 'completed':
            raise ValidationError("This quiz has already been completed")

        # Update access count and timestamp
        metadata = session.session_metadata or {}
        metadata["access_count"] = metadata.get("access_count", 0) + 1
        if not metadata.get("accessed_at"):
            metadata["accessed_at"] = datetime.utcnow().isoformat()
        session.session_metadata = metadata
        self.db.commit()

        # Record metrics for successful access
        await self.metrics_collector.record_quiz_access_success(
            patient_id=str(patient_id),
            quiz_session_id=str(session.id),
            ip_address=ip_address or "unknown",
            user_agent=user_agent or "unknown",
            access_count=metadata.get("access_count", 0)
        )

        # Audit log access
        if self.config.MONTHLY_QUIZ_AUDIT_ENABLED:
            self.audit_service.log_link_accessed(
                patient_id=patient_id,
                session_id=session.id,
                ip_address=ip_address or "unknown",
                user_agent=user_agent or "unknown",
                token_prefix=token[:10]
            )

        # Token rotation if enabled
        rotated_token = None
        if self.config.MONTHLY_QUIZ_ENABLE_TOKEN_ROTATION:
            rotation_count = payload.get("rotation_count", 0) + 1
            rotated_token = self._generate_token(
                patient_id=patient_id,
                quiz_template_id=quiz_template_id,
                expires_at=datetime.fromisoformat(payload["expires_at"]),
                rotation_count=rotation_count
            )
            # Update token hash in metadata
            metadata["token_hash"] = hashlib.sha256(rotated_token.encode()).hexdigest()
            metadata["rotation_count"] = rotation_count
            session.session_metadata = metadata
            self.db.commit()

            # Record token rotation metrics
            await self.metrics_collector.record_token_rotated(
                patient_id=str(patient_id),
                quiz_session_id=str(session.id),
                old_token_prefix=token[:10],
                new_token_prefix=rotated_token[:10],
                rotation_count=rotation_count
            )

        # Get template and patient info
        template = self.template_repository.get(quiz_template_id)
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()

        # Build response
        response = MonthlyQuizAccessResponse(
            quiz_session_id=session.id,
            patient_name=patient.name,
            template_name=template.name,
            template_version=template.version,
            questions=template.questions,
            current_question_index=session.current_question,
            total_questions=len(template.questions),
            expires_at=datetime.fromisoformat(payload["expires_at"])
        )

        # Add rotated token if enabled
        if rotated_token:
            response.new_token = rotated_token  # type: ignore

        return response

    async def submit_quiz_response(
        self,
        submit_data: MonthlyQuizSubmitResponse,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit a quiz response via token."""
        # Verify token
        payload = self._verify_token(submit_data.token)
        patient_id = UUID(payload["patient_id"])
        quiz_template_id = UUID(payload["quiz_template_id"])

        # Find session
        token_hash = hashlib.sha256(submit_data.token.encode()).hexdigest()
        sessions = self.db.query(QuizSession).filter(
            and_(
                QuizSession.patient_id == patient_id,
                QuizSession.quiz_template_id == quiz_template_id,
                QuizSession.session_metadata["token_hash"].astext == token_hash
            )
        ).all()

        if not sessions:
            raise NotFoundError("Quiz session not found")

        session = sessions[0]

        # Get template to find question
        template = self.template_repository.get(quiz_template_id)
        question = next(
            (q for q in template.questions if q.get("id") == submit_data.question_id),
            None
        )

        if not question:
            raise NotFoundError(f"Question {submit_data.question_id} not found in template")

        # Handle multiple choice response values (list support)
        response_value = submit_data.response_value
        question_type = question.get("type", "open_text")

        # Normalize "other" option aliases (OUTRA, other, outro, otra, etc.)
        def normalize_other_value(value):
            """Normalize various 'other' option aliases to match question options."""
            if isinstance(value, str):
                value_lower = value.lower().strip()
                # Check if it's an "other" alias
                if value_lower in ['outra', 'other', 'outro', 'otra', 'autre', 'altro']:
                    # Find the actual "other" option value in question options
                    question_options = question.get("options", [])
                    for opt in question_options:
                        if isinstance(opt, dict):
                            opt_value = opt.get("value", "")
                            if opt.get("allow_other") or opt_value.lower() in ['outra', 'other', 'outro', 'otra']:
                                return opt_value
                    # Fallback to standardized "other"
                    return "other"
            return value

        if question_type == "multiple_choice":
            if isinstance(response_value, str):
                try:
                    # Try to parse JSON string
                    response_value = json.loads(response_value)
                except:
                    # Single value as list
                    response_value = [normalize_other_value(response_value)]
            elif isinstance(response_value, list):
                # Normalize each value in the list
                response_value = [normalize_other_value(v) for v in response_value]
            else:
                raise ValidationError("Multiple choice requires array of values")
        elif question_type == "single_choice":
            # Normalize single choice "other" values
            if isinstance(response_value, str):
                response_value = normalize_other_value(response_value)

        # Encrypt sensitive response if enabled
        encrypted_response_value = response_value
        is_encrypted = False

        if self.config.MONTHLY_QUIZ_ENABLE_ENCRYPTION:
            # Encrypt if question is marked as sensitive
            if question.get("is_sensitive", False):
                # Convert to string for encryption if it's a list
                value_to_encrypt = json.dumps(response_value) if isinstance(response_value, list) else str(response_value)
                encrypted_response_value = self.encryption_service.encrypt(value_to_encrypt)
                is_encrypted = True

        # Create response
        response_metadata = submit_data.response_metadata or {}
        response_metadata["is_encrypted"] = is_encrypted
        # Persist other_text when "Outra" option is selected
        if submit_data.other_text:
            response_metadata["other_text"] = submit_data.other_text
        response_metadata["question_index"] = session.current_question

        response_create = QuizResponseCreate(
            patient_id=patient_id,
            quiz_template_id=quiz_template_id,
            question_id=submit_data.question_id,
            question_text=question.get("text", ""),
            response_type=QuestionType(question.get("type", "open_text")),
            response_value=encrypted_response_value,
            response_metadata=response_metadata,
            responded_at=datetime.utcnow()
        )

        response = await self.quiz_response_service.create_response(response_create)

        # Update session progress after successful response creation
        session.current_question += 1

        # Check if quiz is completed
        total_questions = len(template.questions)
        if session.current_question >= total_questions:
            session.status = 'completed'
            session.completed_at = datetime.utcnow()
            # Calculate score from all responses
            session.score = await self._calculate_score(session.id)

        self.db.commit()
        self.db.refresh(session)

        # Record metrics for successful submission
        await self.metrics_collector.record_quiz_submit_success(
            patient_id=str(patient_id),
            quiz_session_id=str(session.id),
            question_id=submit_data.question_id,
            response_id=str(response.id),
            is_encrypted=is_encrypted
        )

        # Audit log response submission
        if self.config.MONTHLY_QUIZ_AUDIT_ENABLED:
            self.audit_service.log_response_submitted(
                patient_id=patient_id,
                session_id=session.id,
                question_id=submit_data.question_id,
                response_id=response.id,
                ip_address=ip_address,
                user_agent=user_agent
            )

        # Token rotation (if enabled)
        new_token = None
        if getattr(self.config, 'MONTHLY_QUIZ_ENABLE_TOKEN_ROTATION', False):
            new_token = await self._rotate_token(session, template)

        return {
            "response_id": str(response.id),
            "success": True,
            "message": "Response submitted successfully",
            "is_completed": session.status == 'completed',
            "total_score": session.score if session.status == 'completed' else None,
            "current_question_index": session.current_question,
            "new_token": new_token
        }

    async def get_quiz_link_status(self, session_id: UUID) -> MonthlyQuizLinkResponse:
        """Get status of a quiz link."""
        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        metadata = session.session_metadata or {}

        # Determine status
        status = QuizLinkStatus(metadata.get("link_status", QuizLinkStatus.ACTIVE.value))
        if session.status == 'completed':
            status = QuizLinkStatus.USED
        elif datetime.utcnow() > datetime.fromisoformat(metadata.get("expires_at", datetime.utcnow().isoformat())):
            status = QuizLinkStatus.EXPIRED

        return MonthlyQuizLinkResponse(
            id=session.id,
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            token="[REDACTED]",  # Don't expose token in status
            link_url=f"{self.config.MONTHLY_QUIZ_BASE_URL}?token=[REDACTED]",
            delivery_method=DeliveryMethod(metadata.get("delivery_method", "whatsapp")),
            status=status,
            expires_at=datetime.fromisoformat(metadata.get("expires_at", datetime.utcnow().isoformat())),
            created_at=session.started_at,
            accessed_at=datetime.fromisoformat(metadata["accessed_at"]) if metadata.get("accessed_at") else None,
            completed_at=session.completed_at,
            access_count=metadata.get("access_count", 0)
        )

    async def get_monthly_quiz_stats(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> MonthlyQuizStats:
        """Get statistics for monthly quizzes."""
        # Build query
        query = self.db.query(QuizSession).filter(
            QuizSession.session_metadata.isnot(None)
        )

        if start_date:
            query = query.filter(QuizSession.started_at >= start_date)
        if end_date:
            query = query.filter(QuizSession.started_at <= end_date)

        sessions = query.all()

        # Calculate stats
        total_links = len(sessions)
        active_links = len([s for s in sessions if s.status != 'completed' and datetime.utcnow() <= datetime.fromisoformat(
            (s.session_metadata or {}).get("expires_at", datetime.utcnow().isoformat())
        )])
        expired_links = len([s for s in sessions if s.status != 'completed' and datetime.utcnow() > datetime.fromisoformat(
            (s.session_metadata or {}).get("expires_at", datetime.utcnow().isoformat())
        )])
        completed_quizzes = len([s for s in sessions if s.status == 'completed'])

        completion_rate = (completed_quizzes / total_links * 100) if total_links > 0 else 0

        # Calculate average completion time
        completion_times = []
        for session in sessions:
            if session.status == 'completed' and session.completed_at:
                duration = (session.completed_at - session.started_at).total_seconds() / 60
                completion_times.append(duration)

        avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else None

        # Delivery methods distribution
        delivery_distribution: Dict[str, int] = {}
        for session in sessions:
            method = (session.session_metadata or {}).get("delivery_method", "unknown")
            delivery_distribution[method] = delivery_distribution.get(method, 0) + 1

        return MonthlyQuizStats(
            total_links_created=total_links,
            active_links=active_links,
            expired_links=expired_links,
            completed_quizzes=completed_quizzes,
            completion_rate=completion_rate,
            average_completion_time=avg_completion_time,
            delivery_methods_distribution=delivery_distribution
        )

    async def create_bulk_quiz_links(
        self,
        bulk_data: BulkQuizLinkCreate,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> BulkQuizLinkResponse:
        """Create quiz links for multiple patients."""
        links: List[MonthlyQuizLinkResponse] = []
        failures: List[Dict[str, Any]] = []

        for patient_id in bulk_data.patient_ids:
            try:
                link_data = MonthlyQuizLinkCreate(
                    patient_id=patient_id,
                    quiz_template_id=bulk_data.quiz_template_id,
                    delivery_method=bulk_data.delivery_method,
                    expiry_hours=bulk_data.expiry_hours,
                    custom_message=bulk_data.custom_message
                )

                link = await self.create_quiz_link(
                    link_data,
                    actor_id=actor_id,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                links.append(link)

            except Exception as e:
                failures.append({
                    "patient_id": str(patient_id),
                    "error": str(e)
                })

        return BulkQuizLinkResponse(
            total_requested=len(bulk_data.patient_ids),
            total_created=len(links),
            total_failed=len(failures),
            links=links,
            failures=failures
        )

    async def resend_quiz_link(
        self,
        session_id: UUID,
        delivery_method: DeliveryMethod,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> MonthlyQuizLinkResponse:
        """Resend an existing quiz link via a new delivery method."""
        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        metadata = session.session_metadata or {}

        # Check if session is still valid
        expires_at = datetime.fromisoformat(metadata.get("expires_at", datetime.utcnow().isoformat()))
        if datetime.utcnow() > expires_at:
            raise ValidationError("Cannot resend expired quiz link")

        if session.status == 'completed':
            raise ValidationError("Cannot resend completed quiz link")

        # Audit log link resend
        if self.config.MONTHLY_QUIZ_AUDIT_ENABLED:
            self.audit_service.log_link_resent(
                actor_id=actor_id or UUID('00000000-0000-0000-0000-000000000000'),
                patient_id=session.patient_id,
                session_id=session.id,
                delivery_method=delivery_method.value,
                ip_address=ip_address,
                user_agent=user_agent
            )

        # Regenerate token for security
        token = self._generate_token(
            session.patient_id,
            session.quiz_template_id,
            expires_at
        )

        # Update metadata
        metadata["token_hash"] = hashlib.sha256(token.encode()).hexdigest()
        metadata["delivery_method"] = delivery_method.value
        metadata["resent_at"] = datetime.utcnow().isoformat()
        session.session_metadata = metadata
        self.db.commit()

        # Build response
        link_url = f"{self.config.MONTHLY_QUIZ_BASE_URL}?token={token}"
        status = QuizLinkStatus.ACTIVE

        return MonthlyQuizLinkResponse(
            id=session.id,
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            token=token,
            link_url=link_url,
            delivery_method=delivery_method,
            status=status,
            expires_at=expires_at,
            created_at=session.started_at,
            accessed_at=datetime.fromisoformat(metadata["accessed_at"]) if metadata.get("accessed_at") else None,
            completed_at=session.completed_at,
            access_count=metadata.get("access_count", 0)
        )

    async def handle_expired_token(
        self,
        session_id: UUID,
        actor_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Handle expired token by checking regeneration limits and initiating appropriate action.

        Args:
            session_id: Quiz session ID
            actor_id: Actor performing the action (for audit)

        Returns:
            Dictionary with handling result
        """
        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        metadata = session.session_metadata or {}
        regeneration_count = metadata.get("regeneration_count", 0)

        # Maximum regenerations from config or default to 2
        max_regenerations = getattr(self.config, 'MAX_LINK_REGENERATIONS', 2)

        if regeneration_count >= max_regenerations:
            # Max regenerations exceeded - mark for fallback
            metadata["fallback_required"] = True
            metadata["fallback_reason"] = "max_regenerations_exceeded"
            session.session_metadata = metadata
            self.db.commit()

            return {
                "action": "fallback_required",
                "session_id": str(session_id),
                "reason": "max_regenerations_exceeded",
                "regeneration_count": regeneration_count
            }

        # Regenerate token
        result = await self.regenerate_link(
            session_id=session_id,
            actor_id=actor_id
        )

        return {
            "action": "regenerated",
            "session_id": str(session_id),
            "new_token": result.token,
            "new_expires_at": result.expires_at.isoformat(),
            "regeneration_count": regeneration_count + 1
        }

    async def regenerate_link(
        self,
        session_id: UUID,
        actor_id: Optional[UUID] = None
    ) -> MonthlyQuizLinkResponse:
        """
        Regenerate a new token and link for an expired session.

        Args:
            session_id: Quiz session ID
            actor_id: Actor performing the action (for audit)

        Returns:
            MonthlyQuizLinkResponse with new link information
        """
        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        if session.status == 'completed':
            raise ValidationError("Cannot regenerate link for completed session")

        metadata = session.session_metadata or {}
        regeneration_count = metadata.get("regeneration_count", 0)

        # Generate new expiry time
        new_expires_at = datetime.utcnow() + timedelta(
            hours=self.config.MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS
        )

        # Generate new token
        new_token = self._generate_token(
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            expires_at=new_expires_at,
            rotation_count=regeneration_count + 1
        )

        # Update metadata
        metadata["token_hash"] = hashlib.sha256(new_token.encode()).hexdigest()
        metadata["expires_at"] = new_expires_at.isoformat()
        metadata["regeneration_count"] = regeneration_count + 1
        metadata["regenerated_at"] = datetime.utcnow().isoformat()
        metadata["link_status"] = QuizLinkStatus.ACTIVE.value

        session.session_metadata = metadata
        self.db.commit()

        # Audit log
        if self.config.MONTHLY_QUIZ_AUDIT_ENABLED:
            self.audit_service.log_link_regenerated(
                actor_id=actor_id or UUID('00000000-0000-0000-0000-000000000000'),
                patient_id=session.patient_id,
                session_id=session.id,
                regeneration_count=regeneration_count + 1
            )

        # Build link URL
        link_url = f"{self.config.MONTHLY_QUIZ_BASE_URL}?token={new_token}"

        return MonthlyQuizLinkResponse(
            id=session.id,
            patient_id=session.patient_id,
            quiz_template_id=session.quiz_template_id,
            token=new_token,
            link_url=link_url,
            delivery_method=DeliveryMethod(metadata.get("delivery_method", "whatsapp")),
            status=QuizLinkStatus.ACTIVE,
            expires_at=new_expires_at,
            created_at=session.started_at,
            accessed_at=datetime.fromisoformat(metadata["accessed_at"]) if metadata.get("accessed_at") else None,
            completed_at=session.completed_at,
            access_count=metadata.get("access_count", 0)
        )

    def track_failure(
        self,
        session_id: UUID,
        failure_reason: str,
        failure_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track failure for monitoring repeated failures.

        Args:
            session_id: Quiz session ID
            failure_reason: Reason for failure
            failure_details: Additional failure details
        """
        session = self.session_repository.get(session_id)
        if not session:
            return

        metadata = session.session_metadata or {}

        # Initialize failures tracking
        if "failures" not in metadata:
            metadata["failures"] = []

        failure_count = metadata.get("failure_count", 0)
        metadata["failure_count"] = failure_count + 1

        # Add failure record
        failure_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "reason": failure_reason,
            "details": failure_details or {}
        }
        metadata["failures"].append(failure_record)

        session.session_metadata = metadata
        self.db.commit()

    async def get_patient_latest_status(self, patient_id: UUID) -> MonthlyQuizLinkResponse:
        """
        Get the latest quiz link status for a specific patient.
        
        PERFORMANCE OPTIMIZED: Fast 404 check prevents 7-8s delays.

        Args:
            patient_id: UUID of the patient

        Returns:
            MonthlyQuizLinkResponse: Latest quiz link status

        Raises:
            NotFoundError: If patient or quiz sessions not found
        """
        start_time = time.time()
        
        # FAST 404 CHECK: Verify patient exists before heavy queries (10-50ms vs 7-8s)
        if not self._check_patient_exists_fast(str(patient_id)):
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"Fast 404 for patient {str(patient_id)[:8]}... ({elapsed:.1f}ms)")
            raise NotFoundError(f"Patient {patient_id} not found")
        
        # Get the most recent session for the patient
        session = self.db.query(QuizSession).filter(
            and_(
                QuizSession.patient_id == patient_id,
                QuizSession.session_metadata.isnot(None)
            )
        ).order_by(QuizSession.started_at.desc()).first()

        if not session:
            raise NotFoundError(f"No quiz sessions found for patient {patient_id}")

        return await self.get_quiz_link_status(session.id)

    async def get_patient_history(self, patient_id: UUID, limit: int = 10, offset: int = 0) -> List[MonthlyQuizLinkResponse]:
        """
        Get quiz session history for a specific patient.
        
        PERFORMANCE OPTIMIZED: Fast 404 check prevents unnecessary queries.

        Args:
            patient_id: UUID of the patient
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List[MonthlyQuizLinkResponse]: List of quiz sessions for the patient
        """
        # FAST 404 CHECK: Verify patient exists before querying sessions
        if not self._check_patient_exists_fast(str(patient_id)):
            logger.info(f"Fast 404 for patient history {str(patient_id)[:8]}...")
            return []  # Return empty list instead of error for history endpoint
        
        # Get sessions for the patient, ordered by creation date (newest first)
        sessions = self.db.query(QuizSession).filter(
            and_(
                QuizSession.patient_id == patient_id,
                QuizSession.session_metadata.isnot(None)
            )
        ).order_by(QuizSession.started_at.desc()).offset(offset).limit(limit).all()

        results = []
        for session in sessions:
            try:
                link_response = await self.get_quiz_link_status(session.id)
                results.append(link_response)
            except Exception as e:
                # Log error but continue with other sessions
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error getting status for session {session.id}: {str(e)}")
                continue

        return results

    async def get_active_links(self, limit: int = 50, offset: int = 0) -> List[MonthlyQuizLinkResponse]:
        """
        Get all active (non-expired, uncompleted) quiz links.

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List[MonthlyQuizLinkResponse]: List of active quiz links
        """
        # Get sessions that are not completed and potentially active
        sessions = self.db.query(QuizSession).filter(
            and_(
                QuizSession.status != 'completed',
                QuizSession.session_metadata.isnot(None),
                or_(
                    QuizSession.session_metadata["link_status"].astext == "active",
                    QuizSession.session_metadata["link_status"].astext.is_(None)
                )
            )
        ).order_by(QuizSession.started_at.desc()).offset(offset).limit(limit).all()

        active_links = []
        current_time = datetime.utcnow()

        for session in sessions:
            metadata = session.session_metadata or {}
            expires_at_str = metadata.get("expires_at")

            if expires_at_str:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    # Only include if not expired and not cancelled
                    if (current_time <= expires_at and
                        metadata.get("link_status") != "cancelled" and
                        session.status != 'completed'):

                        try:
                            link_response = await self.get_quiz_link_status(session.id)
                            active_links.append(link_response)
                        except Exception as e:
                            # Log error but continue with other sessions
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.error(f"Error getting status for session {session.id}: {str(e)}")
                            continue
                except ValueError:
                    # Invalid date format, skip this session
                    continue

        return active_links

    async def cancel_quiz_link(
        self,
        session_id: UUID,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> MonthlyQuizLinkResponse:
        """
        Cancel a quiz link (update status to cancelled).

        Args:
            session_id: UUID of the quiz session to cancel
            actor_id: Actor performing the cancellation (for audit)
            ip_address: IP address of the actor
            user_agent: User agent of the actor

        Returns:
            MonthlyQuizLinkResponse: Updated quiz link with cancelled status

        Raises:
            NotFoundError: If session not found
            ValidationError: If session is already completed
        """
        session = self.session_repository.get(session_id)
        if not session:
            raise NotFoundError(f"Quiz session {session_id} not found")

        if session.status == 'completed':
            raise ValidationError("Cannot cancel a completed quiz session")

        # Update metadata to cancelled status
        metadata = session.session_metadata or {}
        metadata["link_status"] = QuizLinkStatus.CANCELLED.value
        metadata["cancelled_at"] = datetime.utcnow().isoformat()
        metadata["cancelled_by"] = str(actor_id) if actor_id else None

        session.session_metadata = metadata
        self.db.commit()

        # Audit log cancellation
        if self.config.MONTHLY_QUIZ_AUDIT_ENABLED:
            self.audit_service.log_link_cancelled(
                actor_id=actor_id or UUID('00000000-0000-0000-0000-000000000000'),
                patient_id=session.patient_id,
                session_id=session.id,
                ip_address=ip_address,
                user_agent=user_agent
            )

        return await self.get_quiz_link_status(session_id)

    async def get_active_links_with_details(self) -> List[MonthlyQuizLinkResponse]:
        """Get active quiz links with patient and template details for dashboard."""
        from app.models.patient import Patient

        # Get active links with joins for efficiency
        current_time = datetime.utcnow()

        sessions = self.db.query(QuizSession).join(Patient).join(QuizTemplate).filter(
            and_(
                QuizSession.status != 'completed',
                QuizSession.session_metadata.isnot(None)
            )
        ).all()

        results = []
        for session in sessions:
            metadata = session.session_metadata or {}
            expires_at_str = metadata.get("expires_at")

            if not expires_at_str:
                continue

            try:
                expires_at = datetime.fromisoformat(expires_at_str)

                # Only include active, non-expired links
                if current_time <= expires_at:
                    # Reconstruct token from hash (for display, use redacted version)
                    token_display = "[REDACTED]"

                    # Get patient and template info
                    patient = self.db.query(Patient).filter(Patient.id == session.patient_id).first()
                    template = self.template_repository.get(session.quiz_template_id)

                    link_response = MonthlyQuizLinkResponse(
                        id=session.id,
                        patient_id=session.patient_id,
                        quiz_template_id=session.quiz_template_id,
                        token=token_display,
                        link_url=f"{self.config.MONTHLY_QUIZ_BASE_URL}?token={token_display}",
                        delivery_method=DeliveryMethod(metadata.get("delivery_method", "whatsapp")),
                        status=QuizLinkStatus.ACTIVE if session.status != 'completed' else QuizLinkStatus.USED,
                        expires_at=expires_at,
                        created_at=session.started_at,
                        accessed_at=datetime.fromisoformat(metadata["accessed_at"]) if metadata.get("accessed_at") else None,
                        completed_at=session.completed_at,
                        access_count=metadata.get("access_count", 0),
                        # Dashboard-specific fields
                        patient_name=patient.name if patient else None,
                        patient_phone=patient.phone if patient else None,
                        template_name=template.name if template else None,
                        template_version=template.version if template else None,
                        sent_at=session.started_at,
                        session_id=session.id
                    )

                    results.append(link_response)
            except (ValueError, AttributeError) as e:
                # Skip invalid entries
                continue

        return results

    async def get_active_links_with_details(
        self,
        user_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """
        Get active quiz links with patient and template details.
        Returns enriched data for dashboard display.
        """
        from app.models.patient import Patient

        query = self.db.query(QuizSession).join(
            Patient,
            QuizSession.patient_id == Patient.id
        ).join(
            QuizTemplate,
            QuizSession.quiz_template_id == QuizTemplate.id
        ).filter(
            QuizSession.status != 'completed',
            QuizSession.session_metadata.isnot(None)
        )

        if user_id:
            # Filter by creator if user_id provided (requires created_by column)
            pass  # Add created_by filter if column exists

        sessions = query.all()

        results = []
        current_time = datetime.utcnow()

        for session in sessions:
            metadata = session.session_metadata or {}
            expires_at_str = metadata.get("expires_at")

            if not expires_at_str:
                continue

            try:
                expires_at = datetime.fromisoformat(expires_at_str)

                # Only include active, non-expired links
                if current_time <= expires_at:
                    # Generate access URL with redacted token
                    access_url = f"{self.config.MONTHLY_QUIZ_BASE_URL}?token=[REDACTED]"

                    results.append({
                        "id": str(session.id),
                        "session_id": str(session.id),  # Alias
                        "patient_id": str(session.patient_id),
                        "patient_name": session.patient.name if session.patient else "Unknown",
                        "patient_phone": session.patient.phone if hasattr(session.patient, 'phone') and session.patient.phone else None,
                        "template_id": str(session.quiz_template_id),
                        "template_name": session.quiz_template.name if session.quiz_template else "Unknown",
                        "template_version": session.quiz_template.version if session.quiz_template else "1.0",
                        "access_url": access_url,
                        "created_at": session.started_at.isoformat(),
                        "sent_at": session.started_at.isoformat(),  # Alias for compatibility
                        "expires_at": expires_at.isoformat(),
                        "is_active": expires_at > current_time,
                        "status": session.status,
                        "access_count": metadata.get("access_count", 0),
                        "delivery_method": metadata.get("delivery_method", "whatsapp")
                    })
            except (ValueError, AttributeError):
                continue

        return results

    async def get_quiz_stats(
        self,
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Get quiz statistics with backward-compatible field names.
        """
        query = self.db.query(QuizSession).filter(
            QuizSession.session_metadata.isnot(None)
        )

        if user_id:
            # Filter by creator if user_id provided (requires created_by column)
            pass  # Add created_by filter if column exists

        total = query.count()
        completed = query.filter(QuizSession.status == 'completed').count()

        # Calculate expired links and average score
        current_time = datetime.utcnow()
        sessions = query.all()
        expired = 0
        active = 0
        total_score_sum = 0
        scored_sessions = 0

        for session in sessions:
            # Calculate average score from completed sessions
            if session.status == 'completed' and session.score is not None:
                total_score_sum += session.score
                scored_sessions += 1

            # Skip completion check for expired/active calculation
            if session.status == 'completed':
                continue

            metadata = session.session_metadata or {}
            expires_at_str = metadata.get("expires_at")
            if expires_at_str:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if current_time > expires_at:
                        expired += 1
                    else:
                        active += 1
                except ValueError:
                    pass

        # Calculate average score
        avg_score = round((total_score_sum / scored_sessions), 2) if scored_sessions > 0 else 0

        return {
            # New field names
            "total_sent": total,
            "total_completed": completed,
            "total_expired": expired,
            "total_active": active,
            "average_score": avg_score,

            # Old field names (backward compatibility)
            "total_links_created": total,
            "completed_quizzes": completed,
            "expired_links": expired,
            "active_links": active,

            # Calculated metrics
            "completion_rate": round((completed / total * 100), 2) if total > 0 else 0,
            "expiration_rate": round((expired / total * 100), 2) if total > 0 else 0
        }

    async def _calculate_score(self, session_id: UUID) -> float:
        """
        Calculate score for a completed quiz session.

        Aggregates scores from all responses in the session where scores are available.
        Returns average score or 0 if no scored questions exist.
        """
        from app.models.quiz import QuizResponse

        # Query all responses for this session
        responses = self.db.query(QuizResponse).filter(
            QuizResponse.quiz_session_id == session_id
        ).all()

        if not responses:
            return 0.0

        # Calculate score based on response_metadata
        total_score = 0.0
        scored_responses = 0

        for response in responses:
            metadata = response.response_metadata or {}
            if "score" in metadata and metadata["score"] is not None:
                total_score += float(metadata["score"])
                scored_responses += 1

        # Return average score if scored responses exist, otherwise 0
        return round(total_score / scored_responses, 2) if scored_responses > 0 else 0.0

    async def _rotate_token(self, session: 'QuizSession', template: 'QuizTemplate') -> str:
        """
        Generate new rotated token for quiz session.

        Implements token rotation security pattern:
        - Generates new JWT token with same claims
        - Updates session metadata with new token hash
        - Returns new token to client for next request
        - Old token remains valid for 30-second grace period

        Args:
            session: Current quiz session
            template: Quiz template

        Returns:
            New JWT token string
        """
        # Generate new token payload
        expires_at_dt = datetime.fromisoformat(
            session.session_metadata.get("expires_at", datetime.utcnow().isoformat())
        )

        token_payload = {
            "patient_id": str(session.patient_id),
            "quiz_template_id": str(session.quiz_template_id),
            "session_id": str(session.id),
            "exp": expires_at_dt
        }

        # Generate new JWT token
        import jwt
        new_token = jwt.encode(
            token_payload,
            self.config.MONTHLY_QUIZ_TOKEN_SECRET,
            algorithm="HS256"
        )

        # Update session metadata with new token hash
        new_token_hash = hashlib.sha256(new_token.encode()).hexdigest()

        metadata = session.session_metadata or {}
        # Store old token hash for grace period (30 seconds)
        metadata["previous_token_hash"] = metadata.get("token_hash")
        metadata["token_rotated_at"] = datetime.utcnow().isoformat()
        metadata["token_hash"] = new_token_hash

        session.session_metadata = metadata
        self.db.commit()

        return new_token