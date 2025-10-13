"""
Quiz and assessment services for Hormonia Backend System.
"""
import json
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.models.quiz import QuizTemplate, QuizResponse, QuizSession
from app.repositories.quiz import QuizTemplateRepository, QuizResponseRepository, QuizSessionRepository
from app.services.websocket_events import websocket_events
from app.schemas.websocket import WebSocketEventType
from app.schemas.quiz import (
    QuizTemplateCreate, QuizTemplateUpdate, QuizTemplateResponse,
    QuizResponseCreate, QuizResponseResponse, QuizValidationResult,
    QuizSessionCreate, QuizSessionResponse, QuizAnalytics,
    QuizQuestion, QuestionType, ValidationRule, PatientQuizAnalytics
)
from app.exceptions import NotFoundError, ValidationError, ConflictError
from app.services.quiz_response_utils import (
    normalize_other_value,
    serialize_response_value,
    deserialize_response_value,
    validate_multi_select_response,
    extract_other_text_requirement
)
from app.services.quiz_metrics import get_quiz_metrics_collector


class QuizTemplateService:
    """Service for managing quiz templates."""
    
    def __init__(self, db: Session):
        self.db = db
        self.template_repository = QuizTemplateRepository(db)
    
    def create_template(self, template_data: QuizTemplateCreate) -> QuizTemplateResponse:
        """Create a new quiz template."""
        # Validate template
        validation_result = self.validate_template(template_data.questions)
        if not validation_result.is_valid:
            raise ValidationError(f"Template validation failed: {', '.join(validation_result.errors)}")
        
        # Check if template with same name and version exists
        existing = self.template_repository.get_by_name_and_version(
            template_data.name, template_data.version
        )
        if existing:
            raise ConflictError(f"Template '{template_data.name}' version '{template_data.version}' already exists")
        
        # Create template
        template = QuizTemplate(
            name=template_data.name,
            version=template_data.version,
            questions=[q.dict() for q in template_data.questions],
            is_active=template_data.is_active
        )
        
        try:
            created_template = self.template_repository.create(template)
            self.db.commit()
            return QuizTemplateResponse.from_orm(created_template)
        except IntegrityError as e:
            self.db.rollback()
            raise ConflictError(f"Failed to create template: {str(e)}")
    
    def get_template(self, template_id: UUID) -> QuizTemplateResponse:
        """Get quiz template by ID."""
        template = self.template_repository.get(template_id)
        if not template:
            raise NotFoundError(f"Quiz template with ID {template_id} not found")
        return QuizTemplateResponse.from_orm(template)
    
    def get_templates(self, skip: int = 0, limit: int = 100, active_only: bool = True) -> tuple[List[QuizTemplateResponse], int]:
        """Get quiz templates with pagination."""
        if active_only:
            templates, total = self.template_repository.get_active_templates_with_count(skip=skip, limit=limit)
        else:
            templates, total = self.template_repository.get_all_with_count(skip=skip, limit=limit)
        
        return [QuizTemplateResponse.from_orm(template) for template in templates], total
    
    def get_template_by_name(self, name: str, version: Optional[str] = None) -> QuizTemplateResponse:
        """Get quiz template by name and optionally version."""
        if version:
            template = self.template_repository.get_by_name_and_version(name, version)
        else:
            template = self.template_repository.get_by_name(name)
        
        if not template:
            raise NotFoundError(f"Quiz template '{name}' not found")
        return QuizTemplateResponse.from_orm(template)
    
    def update_template(self, template_id: UUID, template_data: QuizTemplateUpdate) -> QuizTemplateResponse:
        """Update quiz template."""
        template = self.template_repository.get(template_id)
        if not template:
            raise NotFoundError(f"Quiz template with ID {template_id} not found")
        
        # Validate questions if provided
        if template_data.questions:
            validation_result = self.validate_template(template_data.questions)
            if not validation_result.is_valid:
                raise ValidationError(f"Template validation failed: {', '.join(validation_result.errors)}")
        
        # Update fields
        update_data = template_data.dict(exclude_unset=True)
        if 'questions' in update_data:
            update_data['questions'] = [q.dict() for q in template_data.questions]
        
        try:
            updated_template = self.template_repository.update(template, update_data)
            self.db.commit()
            return QuizTemplateResponse.from_orm(updated_template)
        except IntegrityError as e:
            self.db.rollback()
            raise ConflictError(f"Failed to update template: {str(e)}")
    
    def delete_template(self, template_id: UUID) -> bool:
        """Soft delete quiz template (deactivate)."""
        template = self.template_repository.get(template_id)
        if not template:
            raise NotFoundError(f"Quiz template with ID {template_id} not found")
        
        # Soft delete by deactivating
        updated_template = self.template_repository.update(template, {"is_active": False})
        self.db.commit()
        return True
    
    def create_template_version(self, template_id: UUID, new_version: str) -> QuizTemplateResponse:
        """Create a new version of an existing template."""
        original_template = self.template_repository.get(template_id)
        if not original_template:
            raise NotFoundError(f"Quiz template with ID {template_id} not found")
        
        # Check if new version already exists
        existing = self.template_repository.get_by_name_and_version(
            original_template.name, new_version
        )
        if existing:
            raise ConflictError(f"Template '{original_template.name}' version '{new_version}' already exists")
        
        # Create new version
        new_template = QuizTemplate(
            name=original_template.name,
            version=new_version,
            questions=original_template.questions,
            is_active=True
        )
        
        try:
            created_template = self.template_repository.create(new_template)
            self.db.commit()
            return QuizTemplateResponse.from_orm(created_template)
        except IntegrityError as e:
            self.db.rollback()
            raise ConflictError(f"Failed to create template version: {str(e)}")
    
    def get_template_versions(self, template_name: str) -> List[QuizTemplateResponse]:
        """Get all versions of a template."""
        templates = self.template_repository.get_all_versions(template_name)
        return [QuizTemplateResponse.from_orm(template) for template in templates]
    
    def validate_template(self, questions: List[QuizQuestion]) -> QuizValidationResult:
        """Validate quiz template questions."""
        errors = []
        warnings = []
        
        if not questions:
            errors.append("Template must have at least one question")
            return QuizValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        question_ids = set()
        
        for i, question in enumerate(questions):
            # Check for duplicate question IDs
            if question.id in question_ids:
                errors.append(f"Duplicate question ID '{question.id}' found")
            question_ids.add(question.id)
            
            # Validate question text
            if not question.text.strip():
                errors.append(f"Question {i+1} has empty text")
            
            # Validate question type specific requirements
            if question.type == QuestionType.MULTIPLE_CHOICE:
                if not question.options or len(question.options) == 0:
                    errors.append(f"Multiple choice question '{question.id}' must have options")
                elif len(question.options) < 2:
                    warnings.append(f"Multiple choice question '{question.id}' has only one option")

                # Check for duplicate option IDs
                if question.options:
                    option_ids = [opt.id for opt in question.options]
                    if len(option_ids) != len(set(option_ids)):
                        errors.append(f"Question '{question.id}' has duplicate option IDs")

            elif question.type == QuestionType.SINGLE_CHOICE:
                if not question.options or len(question.options) == 0:
                    errors.append(f"Single choice question '{question.id}' must have options")

                # Check for duplicate option IDs
                if question.options:
                    option_ids = [opt.id for opt in question.options]
                    if len(option_ids) != len(set(option_ids)):
                        errors.append(f"Question '{question.id}' has duplicate option IDs")
            
            elif question.type == QuestionType.SCALE:
                # Validate scale questions have proper validation rules
                if question.validation_rules:
                    has_range = any(rule.type == "range" for rule in question.validation_rules)
                    if not has_range:
                        warnings.append(f"Scale question '{question.id}' should have range validation")
            
            # Validate validation rules
            if question.validation_rules:
                for rule in question.validation_rules:
                    if not self._validate_validation_rule(rule, question.type):
                        errors.append(f"Invalid validation rule '{rule.type}' for question '{question.id}'")
        
        return QuizValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _validate_validation_rule(self, rule: ValidationRule, question_type: QuestionType) -> bool:
        """Validate a single validation rule."""
        valid_rules = {
            QuestionType.OPEN_TEXT: ["required", "min_length", "max_length", "pattern"],
            QuestionType.MULTIPLE_CHOICE: ["required"],
            QuestionType.SINGLE_CHOICE: ["required"],
            QuestionType.SCALE: ["required", "range", "min", "max"],
            QuestionType.YES_NO: ["required"],
            QuestionType.DATE: ["required", "min_date", "max_date"],
            QuestionType.NUMBER: ["required", "min", "max", "integer_only"]
        }
        
        return rule.type in valid_rules.get(question_type, [])


class QuizResponseService:
    """Service for managing quiz responses."""

    def __init__(self, db: Session):
        self.db = db
        self.response_repository = QuizResponseRepository(db)
        self.template_repository = QuizTemplateRepository(db)
        self.session_repository = QuizSessionRepository(db)
    
    async def create_response(self, response_data: QuizResponseCreate) -> QuizResponseResponse:
        """Create a quiz response with comprehensive validation."""
        # Validate template exists and is active
        template = self.template_repository.get(response_data.quiz_template_id)
        if not template:
            raise NotFoundError(f"Quiz template with ID {response_data.quiz_template_id} not found")

        if not template.is_active:
            raise ValidationError("Cannot create response for inactive template")

        # Find the specific question in template
        questions = template.questions
        target_question = None
        for q in questions:
            if q.get('id') == response_data.question_id:
                target_question = q
                break

        if not target_question:
            raise ValidationError(f"Question '{response_data.question_id}' not found in template")

        # Comprehensive response validation based on question type
        question_type = target_question.get('type', 'open_text')
        response_value = response_data.response_value

        # Normalize "Outra" aliases to "other"
        normalized_value = normalize_other_value(response_value)

        # Validate response based on question type
        validation_errors = self._validate_response_by_type(
            question_type,
            normalized_value,
            target_question.get('options', []),
            target_question.get('validation_rules', [])
        )

        if validation_errors:
            raise ValidationError(f"Response validation failed: {'; '.join(validation_errors)}")

        # Validate other_text requirement
        question_options = target_question.get('options', [])
        requires_other_text = extract_other_text_requirement(normalized_value, question_options)

        if requires_other_text and not response_data.other_text:
            raise ValidationError("Custom text required when 'Outra' option is selected")

        if response_data.other_text and not requires_other_text:
            # Check if question or any option allows 'other' text
            question_allows_other = target_question.get('allow_other', False)
            option_allows_other = any(opt.get('allow_other', False) for opt in question_options)

            if not (question_allows_other or option_allows_other):
                raise ValidationError("other_text provided but question/option does not allow custom text")

        # Get active quiz session for this patient if it exists
        active_session = self.session_repository.get_active_session(response_data.patient_id)
        session_id = active_session.id if active_session else None

        # Serialize response value for storage (preserves lists as JSON)
        stored_value = serialize_response_value(normalized_value)

        # Create response (link to active session if present)
        response = QuizResponse(
            patient_id=response_data.patient_id,
            quiz_template_id=response_data.quiz_template_id,
            quiz_session_id=session_id,
            question_id=response_data.question_id,
            question_text=response_data.question_text or target_question.get('text', ''),
            response_type=response_data.response_type.value,
            response_value=stored_value,  # Serialized value
            response_metadata=response_data.response_metadata or {},
            responded_at=response_data.responded_at or datetime.utcnow(),
            other_text=response_data.other_text
        )

        try:
            created_response = self.response_repository.create(response)
            self.db.commit()

            # Publish WebSocket event for quiz response with proper session_id
            if websocket_events:
                await websocket_events.publish_quiz_event(
                    event_type=WebSocketEventType.QUIZ_RESPONSE_SUBMITTED,
                    patient_id=response_data.patient_id,
                    quiz_id=session_id,  # Use session_id instead of None
                    template_id=response_data.quiz_template_id,
                    session_id=session_id,
                    response_id=created_response.id,
                    question_id=response_data.question_id,
                    answer=normalized_value  # Use normalized value for event
                )

            return QuizResponseResponse.from_orm(created_response)
        except IntegrityError as e:
            self.db.rollback()
            raise ConflictError(f"Failed to create response: {str(e)}")

    def _validate_response_by_type(self, question_type: str, response_value: Union[str, List[str]],
                                  options: List[Dict], validation_rules: List[Dict]) -> List[str]:
        """Validate response based on question type and rules."""
        errors = []

        if question_type == 'multiple_choice':
            # Multi-select: response_value should be a list
            if not isinstance(response_value, list):
                # Try to parse if it's a JSON string
                if isinstance(response_value, str):
                    try:
                        parsed = json.loads(response_value)
                        response_value = parsed if isinstance(parsed, list) else [parsed]
                    except (json.JSONDecodeError, TypeError):
                        response_value = [response_value]
                else:
                    response_value = [response_value]

            # Use utility function for validation
            multi_select_errors = validate_multi_select_response(response_value, options)
            errors.extend(multi_select_errors)

        elif question_type == 'single_choice':
            # Single select: response_value should be a string
            if isinstance(response_value, list):
                if len(response_value) > 1:
                    errors.append("Single choice question can only have one selection")
                elif len(response_value) == 1:
                    response_value = response_value[0]
                else:
                    errors.append("Response value cannot be empty")
                    return errors

            # Extract valid option IDs and values
            valid_ids = {str(opt.get("id")) for opt in options if opt.get("id")}
            valid_values = {str(opt.get("value")) for opt in options if opt.get("value")}

            # Check if any option allows "other"
            has_other_option = any(opt.get("allow_other", False) for opt in options)

            response_str = str(response_value)

            # Check if "other" is selected (normalized)
            if response_str.lower() == "other":
                if not has_other_option:
                    errors.append("Option 'other' is not allowed for this question")
            elif response_str not in valid_ids and response_str not in valid_values:
                errors.append(f"Invalid option selected: {response_value}")

        elif question_type == 'scale':
            # Validate scale response is numeric and within range
            try:
                numeric_value = float(response_value)
                # Check range validation rules
                for rule in validation_rules:
                    if rule.get('type') == 'range':
                        min_val = rule.get('min', 0)
                        max_val = rule.get('max', 10)
                        if not (min_val <= numeric_value <= max_val):
                            errors.append(f"Scale value {numeric_value} must be between {min_val} and {max_val}")
            except (ValueError, TypeError):
                errors.append("Scale response must be numeric")

        elif question_type == 'yes_no':
            # Validate yes/no response
            if response_value not in ['yes', 'no', 'sim', 'não', True, False, 1, 0]:
                errors.append("Yes/No question response must be yes, no, true, false, 1, or 0")

        elif question_type == 'number':
            # Validate numeric response
            try:
                numeric_value = float(response_value)
                # Check min/max validation rules
                for rule in validation_rules:
                    if rule.get('type') == 'min' and numeric_value < rule.get('value', 0):
                        errors.append(f"Number must be at least {rule.get('value')}")
                    elif rule.get('type') == 'max' and numeric_value > rule.get('value', 100):
                        errors.append(f"Number must be at most {rule.get('value')}")
                    elif rule.get('type') == 'integer_only' and rule.get('value') and numeric_value != int(numeric_value):
                        errors.append("Number must be an integer")
            except (ValueError, TypeError):
                errors.append("Number response must be numeric")

        elif question_type == 'date':
            # Validate date response
            try:
                if isinstance(response_value, str):
                    from datetime import datetime
                    datetime.fromisoformat(response_value.replace('Z', '+00:00'))
            except ValueError:
                errors.append("Date response must be in valid ISO format")

        elif question_type == 'open_text':
            # Validate text length based on rules
            text_value = str(response_value)
            for rule in validation_rules:
                if rule.get('type') == 'min_length' and len(text_value) < rule.get('value', 0):
                    errors.append(f"Text must be at least {rule.get('value')} characters long")
                elif rule.get('type') == 'max_length' and len(text_value) > rule.get('value', 1000):
                    errors.append(f"Text must be at most {rule.get('value')} characters long")

        # Check required validation
        for rule in validation_rules:
            if rule.get('type') == 'required' and rule.get('value') and not response_value:
                errors.append("This question requires a response")

        return errors
    
    def get_patient_responses(self, patient_id: UUID, skip: int = 0, limit: int = 100) -> tuple[List[QuizResponseResponse], int]:
        """Get quiz responses for a patient."""
        responses, total = self.response_repository.get_by_patient_with_count(patient_id, skip=skip, limit=limit)
        return [QuizResponseResponse.from_orm(response) for response in responses], total
    
    def get_template_responses(self, template_id: UUID, skip: int = 0, limit: int = 100) -> tuple[List[QuizResponseResponse], int]:
        """Get responses for a quiz template."""
        responses, total = self.response_repository.get_by_quiz_template_with_count(template_id, skip=skip, limit=limit)
        return [QuizResponseResponse.from_orm(response) for response in responses], total
    
    def get_patient_quiz_responses(self, patient_id: UUID, template_id: UUID) -> List[QuizResponseResponse]:
        """Get all responses from a patient for a specific quiz."""
        responses = self.response_repository.get_patient_quiz_responses(patient_id, template_id)
        return [QuizResponseResponse.from_orm(response) for response in responses]


class QuizSessionService:
    """Service for managing quiz sessions."""

    def __init__(self, db: Session):
        self.db = db
        self.session_repository = QuizSessionRepository(db)
        self.template_repository = QuizTemplateRepository(db)
        self.response_repository = QuizResponseRepository(db)

    def _enrich_session_response(self, session: QuizSession) -> QuizSessionResponse:
        """Enrich session response with patient and template data."""
        response = QuizSessionResponse.from_orm(session)

        # Use relationships if already loaded (from joinedload), otherwise None
        if hasattr(session, 'patient') and session.patient:
            response.patient_name = session.patient.name

        if hasattr(session, 'quiz_template') and session.quiz_template:
            response.template_name = session.quiz_template.name
            response.template_version = session.quiz_template.version

        return response
    
    async def start_quiz_session(self, session_data: QuizSessionCreate) -> QuizSessionResponse:
        """Start a new quiz session for a patient with proper race condition handling."""
        # Use database transaction with proper isolation and locking
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError
        from app.models.patient import Patient

        try:
            # Start transaction with serializable isolation level to prevent race conditions
            with self.db.begin():
                # Check if template exists and is active
                template = self.template_repository.get(session_data.quiz_template_id)
                if not template:
                    raise NotFoundError(f"Quiz template with ID {session_data.quiz_template_id} not found")

                if not template.is_active:
                    raise ValidationError("Cannot start session with inactive template")

                # Use database-level uniqueness constraint with FOR UPDATE NOWAIT to prevent race conditions
                # FIX: Use 'completed_at IS NULL' instead of non-existent 'is_completed' column
                active_session_query = text(
                    """
                    SELECT id FROM quiz_sessions
                    WHERE patient_id = :patient_id AND completed_at IS NULL
                    FOR UPDATE NOWAIT
                    """
                )

                try:
                    result = self.db.execute(active_session_query, {"patient_id": str(session_data.patient_id)})
                    active_session = result.fetchone()

                    if active_session:
                        raise ConflictError("Patient already has an active quiz session")
                except Exception as lock_error:
                    # If we can't acquire lock immediately, another session is being created
                    if "could not obtain lock" in str(lock_error).lower():
                        raise ConflictError("Another quiz session is currently being created for this patient")
                    raise

                # Create new session with database constraints ensuring uniqueness
                # FIX: Use correct field names matching database schema
                session = QuizSession(
                    patient_id=session_data.patient_id,
                    quiz_template_id=session_data.quiz_template_id,
                    current_question=0,  # FIX: Renamed from current_question_index
                    status='started',    # FIX: Use status instead of is_completed
                    started_at=datetime.utcnow()
                )

                # Use repository create which should handle unique constraints
                created_session = self.session_repository.create(session)
                self.db.flush()  # Ensure database constraints are checked

            # Publish WebSocket event for quiz started (outside transaction)
            if websocket_events:
                await websocket_events.publish_quiz_event(
                    event_type=WebSocketEventType.QUIZ_STARTED,
                    patient_id=session_data.patient_id,
                    quiz_id=created_session.id,
                    template_id=session_data.quiz_template_id,
                    session_id=created_session.id
                )

            # Manually load relationships for enrichment since they weren't eager loaded
            self.db.refresh(created_session)
            created_session.patient = self.db.query(Patient).filter(Patient.id == created_session.patient_id).first()
            created_session.quiz_template = self.template_repository.get(created_session.quiz_template_id)

            return self._enrich_session_response(created_session)

        except IntegrityError as e:
            # Handle database constraint violations
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                raise ConflictError("Patient already has an active quiz session")
            raise ConflictError(f"Failed to create quiz session: {str(e)}")
        except Exception as e:
            self.db.rollback()
            raise
    
    def get_active_session(self, patient_id: UUID) -> Optional[QuizSessionResponse]:
        """Get active quiz session for a patient with enriched data."""
        from app.models.patient import Patient

        # Use eager loading to avoid N+1 queries
        session = (
            self.db.query(QuizSession)
            .options(
                joinedload(QuizSession.patient),
                joinedload(QuizSession.quiz_template)
            )
            .filter(
                QuizSession.patient_id == patient_id,
                QuizSession.status != 'completed'
            )
            .order_by(QuizSession.started_at.desc())
            .first()
        )

        if session:
            return self._enrich_session_response(session)
        return None
    
    def get_session(self, session_id: UUID) -> QuizSessionResponse:
        """Get quiz session by ID with enriched data."""
        from app.models.patient import Patient

        # Use eager loading to avoid N+1 queries
        session = (
            self.db.query(QuizSession)
            .options(
                joinedload(QuizSession.patient),
                joinedload(QuizSession.quiz_template)
            )
            .filter(QuizSession.id == session_id)
            .first()
        )

        if not session:
            raise NotFoundError(f"Quiz session with ID {session_id} not found")
        return self._enrich_session_response(session)
    
    def advance_session(self, session_id: UUID) -> QuizSessionResponse:
        """Advance session to next question."""
        from app.models.patient import Patient

        # Use eager loading for enrichment
        session = (
            self.db.query(QuizSession)
            .options(
                joinedload(QuizSession.patient),
                joinedload(QuizSession.quiz_template)
            )
            .filter(QuizSession.id == session_id)
            .first()
        )

        if not session:
            raise NotFoundError(f"Quiz session with ID {session_id} not found")

        if session.status == 'completed':
            raise ValidationError("Cannot advance completed session")

        # Get template to check question count (already loaded via joinedload)
        template = session.quiz_template
        if not template:
            raise NotFoundError("Quiz template not found")

        questions = template.questions
        if session.current_question >= len(questions) - 1:
            # Complete the session
            session.status = 'completed'
            session.completed_at = datetime.utcnow()
        else:
            # Advance to next question
            session.current_question += 1

        try:
            updated_session = self.session_repository.update(session, {})
            self.db.commit()

            # Refresh relationships after update
            self.db.refresh(updated_session)
            updated_session.patient = session.patient
            updated_session.quiz_template = session.quiz_template

            return self._enrich_session_response(updated_session)
        except IntegrityError as e:
            self.db.rollback()
            raise ConflictError(f"Failed to advance session: {str(e)}")
    
    async def complete_session(self, session_id: UUID) -> QuizSessionResponse:
        """Complete a quiz session and evaluate responses for alerts."""
        from app.models.patient import Patient
        from app.services.quiz_response_evaluator import QuizResponseEvaluator

        # Use eager loading for enrichment
        session = (
            self.db.query(QuizSession)
            .options(
                joinedload(QuizSession.patient),
                joinedload(QuizSession.quiz_template)
            )
            .filter(QuizSession.id == session_id)
            .first()
        )

        if not session:
            raise NotFoundError(f"Quiz session with ID {session_id} not found")

        if session.status == 'completed':
            return self._enrich_session_response(session)

        # Mark as completed
        session.status = 'completed'
        session.completed_at = datetime.utcnow()

        try:
            updated_session = self.session_repository.update(session, {})
            self.db.commit()

            # Refresh relationships after update
            self.db.refresh(updated_session)
            updated_session.patient = session.patient
            updated_session.quiz_template = session.quiz_template

            # NEW: Evaluate quiz responses and generate alerts
            try:
                # Get all responses for this session
                responses_data = self._collect_session_responses(session_id)

                if responses_data:
                    # Initialize evaluator
                    evaluator = QuizResponseEvaluator(self.db)

                    # Evaluate responses and generate alerts
                    triggered_alerts, risk_score = await evaluator.evaluate_quiz_session(
                        quiz_session_id=session_id,
                        patient_id=session.patient_id,
                        responses=responses_data
                    )

                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(
                        f"Quiz session {session_id} evaluation: "
                        f"{len(triggered_alerts)} alerts, risk score: {risk_score:.2f}"
                    )
            except Exception as e:
                # Don't fail session completion on alert evaluation error
                import logging
                logging.getLogger(__name__).error(
                    f"Failed to evaluate quiz responses for alerts: {e}", exc_info=True
                )

            # Record completion metric
            try:
                metrics = await get_quiz_metrics_collector()
                await metrics.record_quiz_completion(
                    template_id=session.quiz_template_id,
                    session_id=session.id
                )
            except Exception as e:
                # Don't fail session completion on metrics error
                import logging
                logging.getLogger(__name__).error(
                    f"Failed to record quiz completion metric: {e}", exc_info=True
                )

            # Publish WebSocket event for quiz completion
            if websocket_events:
                await websocket_events.publish_quiz_event(
                    event_type=WebSocketEventType.QUIZ_COMPLETED,
                    patient_id=session.patient_id,
                    quiz_id=session.id,
                    template_id=session.quiz_template_id,
                    session_id=session.id,
                    completed=True
                )

            return self._enrich_session_response(updated_session)
        except IntegrityError as e:
            self.db.rollback()
            raise ConflictError(f"Failed to complete session: {str(e)}")

    def _collect_session_responses(self, session_id: UUID) -> Dict[str, Any]:
        """
        Collect all responses for a quiz session into a dictionary.

        Args:
            session_id: UUID of the quiz session

        Returns:
            Dictionary mapping question_id to response_value
        """
        responses = self.response_repository.get_by_session(session_id)

        response_dict = {}
        for response in responses:
            # Deserialize response value if needed
            value = deserialize_response_value(response.response_value)
            response_dict[response.question_id] = value

        return response_dict
    
    def get_patient_sessions(self, patient_id: UUID, skip: int = 0, limit: int = 100) -> tuple[List[QuizSessionResponse], int]:
        """Get quiz sessions for a patient with enriched data."""
        from app.models.patient import Patient

        # Use eager loading to avoid N+1 queries
        query = (
            self.db.query(QuizSession)
            .options(
                joinedload(QuizSession.patient),
                joinedload(QuizSession.quiz_template)
            )
            .filter(QuizSession.patient_id == patient_id)
            .order_by(QuizSession.started_at.desc())
        )

        total = query.count()
        sessions = query.offset(skip).limit(limit).all()

        return [self._enrich_session_response(session) for session in sessions], total

    def get_all_sessions(self, skip: int = 0, limit: int = 100, status: Optional[str] = None) -> tuple[List[QuizSessionResponse], int]:
        """Get all quiz sessions with optional status filtering and enriched data."""
        from app.models.patient import Patient

        # Use eager loading to avoid N+1 queries
        query = (
            self.db.query(QuizSession)
            .options(
                joinedload(QuizSession.patient),
                joinedload(QuizSession.quiz_template)
            )
        )

        # Apply status filter if provided
        if status:
            if status.lower() == 'completed':
                query = query.filter(QuizSession.status == 'completed')
            elif status.lower() in ('in_progress', 'active', 'started'):
                query = query.filter(QuizSession.status == 'started')

        query = query.order_by(QuizSession.started_at.desc())

        total = query.count()
        sessions = query.offset(skip).limit(limit).all()

        return [self._enrich_session_response(session) for session in sessions], total


class QuizAnalyticsService:
    """Service for quiz analytics and insights."""
    
    def __init__(self, db: Session):
        self.db = db
        self.template_repository = QuizTemplateRepository(db)
        self.response_repository = QuizResponseRepository(db)
        self.session_repository = QuizSessionRepository(db)
    
    def get_patient_analytics(self, patient_id: UUID, template_id: Optional[UUID] = None) -> PatientQuizAnalytics:
        """Get analytics for a patient's quiz responses."""
        from app.models.quiz import QuizSession

        # FIX N+1: Use SQL WHERE clause instead of Python filtering
        if template_id:
            responses = self.response_repository.get_patient_quiz_responses(patient_id, template_id)
            # Use database query instead of Python list comprehension
            sessions = self.db.query(QuizSession).filter(
                QuizSession.patient_id == patient_id,
                QuizSession.quiz_template_id == template_id
            ).all()
        else:
            responses = self.response_repository.get_by_patient(patient_id)
            sessions = self.session_repository.get_patient_sessions(patient_id)

        # Calculate basic metrics
        total_responses = len(responses)
        # FIX: Use status field instead of is_completed
        completed_sessions = len([s for s in sessions if s.status == 'completed'])
        total_sessions = len(sessions)
        completion_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
        
        # Calculate average score (simplified - could be enhanced based on scoring logic)
        average_score = None  # Would need scoring logic implementation
        
        # Get recent activity (last 10 responses)
        recent_activity = []
        for response in responses[:10]:
            recent_activity.append({
                "quiz_template_id": str(response.quiz_template_id),
                "question_id": response.question_id,
                "response_value": response.response_value,
                "responded_at": response.responded_at.isoformat()
            })
        
        return PatientQuizAnalytics(
            patient_id=patient_id,
            total_quizzes_completed=completed_sessions,
            completion_rate=completion_rate,
            average_score=average_score,
            recent_activity=recent_activity
        )
    
    def get_template_analytics(self, template_id: UUID) -> QuizAnalytics:
        """Get analytics for a quiz template."""
        template = self.template_repository.get(template_id)
        if not template:
            raise NotFoundError(f"Quiz template with ID {template_id} not found")
        
        # Get all responses for this template
        responses = self.response_repository.get_by_quiz_template(template_id)
        sessions = self.session_repository.get_template_sessions(template_id)
        
        # Calculate metrics
        total_responses = len(responses)
        completed_sessions = len([s for s in sessions if s.status == 'completed'])
        total_sessions = len(sessions)
        completion_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
        
        # Calculate average completion time
        completed_session_times = []
        for session in sessions:
            # FIX: Use status field instead of is_completed
            if session.status == 'completed' and session.completed_at:
                duration = (session.completed_at - session.started_at).total_seconds() / 60
                completed_session_times.append(duration)

        avg_completion_time = sum(completed_session_times) / len(completed_session_times) if completed_session_times else None

        # FIX N+1: Use SQL GROUP BY instead of Python nested loops
        # Analyze questions with a single aggregated query
        from sqlalchemy import func
        from app.models.quiz import QuizResponse

        # Get question stats in ONE query instead of N queries
        question_stats_query = self.db.query(
            QuizResponse.question_id,
            QuizResponse.response_value,
            func.count(QuizResponse.id).label('count')
        ).filter(
            QuizResponse.quiz_template_id == template_id
        ).group_by(
            QuizResponse.question_id,
            QuizResponse.response_value
        ).all()

        # Build question analytics from aggregated results
        question_analytics = []
        questions = template.questions

        # Create a lookup dict for O(1) access instead of O(n) loops
        stats_by_question = {}
        for q_id, value, count in question_stats_query:
            if q_id not in stats_by_question:
                stats_by_question[q_id] = {"responses": 0, "distribution": {}}
            stats_by_question[q_id]["responses"] += count
            stats_by_question[q_id]["distribution"][value] = count

        for question in questions:
            question_id = question.get('id')
            stats = stats_by_question.get(question_id, {"responses": 0, "distribution": {}})

            question_analytics.append({
                "question_id": question_id,
                "question_text": question.get('text'),
                "total_responses": stats["responses"],
                "response_distribution": stats["distribution"]
            })
        
        # Analyze trends (simplified - could be enhanced with time-based analysis)
        trends = {
            "completion_rate_trend": "stable",  # Would need historical data
            "response_volume_trend": "stable",
            "average_time_trend": "stable"
        }
        
        return QuizAnalytics(
            quiz_template_id=template_id,
            total_responses=total_responses,
            completion_rate=completion_rate,
            average_completion_time=avg_completion_time,
            question_analytics=question_analytics,
            trends=trends
        )


# Unified QuizService class that combines all quiz-related services
class QuizService:
    """Unified service for all quiz-related operations."""

    def __init__(self, db: Session):
        self.db = db
        self.template_service = QuizTemplateService(db)
        self.response_service = QuizResponseService(db)
        self.session_service = QuizSessionService(db)
        self.analytics_service = QuizAnalyticsService(db)

    # Template service methods
    def create_template(self, template_data: QuizTemplateCreate) -> QuizTemplateResponse:
        return self.template_service.create_template(template_data)

    def get_template(self, template_id: UUID) -> QuizTemplateResponse:
        return self.template_service.get_template(template_id)

    def get_templates(self, skip: int = 0, limit: int = 100, is_active: Optional[bool] = None) -> List[QuizTemplateResponse]:
        return self.template_service.get_templates(skip=skip, limit=limit, is_active=is_active)

    def update_template(self, template_id: UUID, template_data: QuizTemplateUpdate) -> QuizTemplateResponse:
        return self.template_service.update_template(template_id, template_data)

    def delete_template(self, template_id: UUID) -> None:
        return self.template_service.delete_template(template_id)

    # Session service methods
    def create_session(self, session_data: QuizSessionCreate) -> QuizSessionResponse:
        return self.session_service.create_session(session_data)

    def get_session(self, session_id: UUID) -> QuizSessionResponse:
        return self.session_service.get_session(session_id)

    def get_patient_sessions(self, patient_id: UUID, skip: int = 0, limit: int = 100) -> List[QuizSessionResponse]:
        return self.session_service.get_patient_sessions(patient_id, skip=skip, limit=limit)

    def complete_session(self, session_id: UUID) -> QuizSessionResponse:
        return self.session_service.complete_session(session_id)

    def cancel_session(self, session_id: UUID) -> QuizSessionResponse:
        return self.session_service.cancel_session(session_id)

    # Response service methods
    def create_response(self, response_data: QuizResponseCreate) -> QuizResponseResponse:
        return self.response_service.create_response(response_data)

    def get_response(self, response_id: UUID) -> QuizResponseResponse:
        return self.response_service.get_response(response_id)

    def get_session_responses(self, session_id: UUID, skip: int = 0, limit: int = 100) -> List[QuizResponseResponse]:
        return self.response_service.get_session_responses(session_id, skip=skip, limit=limit)

    def get_patient_responses(self, patient_id: UUID, skip: int = 0, limit: int = 100) -> List[QuizResponseResponse]:
        return self.response_service.get_patient_responses(patient_id, skip=skip, limit=limit)

    # Analytics service methods
    def get_template_analytics(self, template_id: UUID, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> QuizAnalytics:
        return self.analytics_service.get_template_analytics(template_id, start_date=start_date, end_date=end_date)

    def get_patient_analytics(self, patient_id: UUID, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> PatientQuizAnalytics:
        return self.analytics_service.get_patient_analytics(patient_id, start_date=start_date, end_date=end_date)

    # Additional unified methods
    def validate_template(self, questions: List[QuizQuestion]) -> QuizValidationResult:
        return self.template_service.validate_template(questions)