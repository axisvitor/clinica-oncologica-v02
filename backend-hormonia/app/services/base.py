"""
Base Service Classes
Provides common functionality for all services to reduce code duplication.
"""
import logging
from typing import Optional, Any, Dict, List, TypeVar, Generic
from datetime import datetime
from uuid import UUID
from abc import ABC, abstractmethod

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.message_factory import MessageFactory
from app.services.ai import get_cache_layer, AICache
from app.services.circuit_breaker import get_ai_circuit_breaker, AIServiceCircuitBreaker

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BaseService(ABC):
    """
    Base service class with common functionality.
    All services should inherit from this class.
    """
    
    def __init__(self, db: Session):
        """
        Initialize base service.
        
        Args:
            db: Database session
        """
        self.db = db
        self._message_factory: Optional[MessageFactory] = None
        self._ai_cache: Optional[AICache] = None
        self._circuit_breaker: Optional[AIServiceCircuitBreaker] = None
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @property
    def message_factory(self) -> MessageFactory:
        """
        Get or create message factory instance.
        
        Returns:
            MessageFactory instance
        """
        if self._message_factory is None:
            self._message_factory = MessageFactory(self.db)
        return self._message_factory
    
    @property
    async def ai_cache(self) -> AICache:
        """
        Get or create AI cache instance.
        
        Returns:
            AICache instance
        """
        if self._ai_cache is None:
            self._ai_cache = await get_cache_layer()
        return self._ai_cache
    
    @property
    def circuit_breaker(self) -> AIServiceCircuitBreaker:
        """
        Get or create circuit breaker instance.
        
        Returns:
            AIServiceCircuitBreaker instance
        """
        if self._circuit_breaker is None:
            self._circuit_breaker = get_ai_circuit_breaker()
        return self._circuit_breaker
    
    def save_entity(self, entity: T) -> T:
        """
        Save entity to database with error handling.
        
        Args:
            entity: Entity to save
            
        Returns:
            Saved entity
            
        Raises:
            SQLAlchemyError: Database error
        """
        try:
            self.db.add(entity)
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except SQLAlchemyError as e:
            self.logger.error(f"Database error saving entity: {e}")
            self.db.rollback()
            raise
    
    def save_entities(self, entities: List[T]) -> List[T]:
        """
        Save multiple entities in a batch.
        
        Args:
            entities: List of entities to save
            
        Returns:
            List of saved entities
        """
        try:
            for entity in entities:
                self.db.add(entity)
            self.db.commit()
            
            for entity in entities:
                self.db.refresh(entity)
            
            return entities
        except SQLAlchemyError as e:
            self.logger.error(f"Database error saving entities: {e}")
            self.db.rollback()
            raise
    
    def delete_entity(self, entity: T) -> bool:
        """
        Delete entity from database.
        
        Args:
            entity: Entity to delete
            
        Returns:
            True if successful
        """
        try:
            self.db.delete(entity)
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.logger.error(f"Database error deleting entity: {e}")
            self.db.rollback()
            return False
    
    def log_operation(
        self,
        operation: str,
        entity_type: str,
        entity_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log service operation for auditing.
        
        Args:
            operation: Operation name
            entity_type: Type of entity
            entity_id: Entity ID if applicable
            metadata: Additional metadata
        """
        log_data = {
            "operation": operation,
            "entity_type": entity_type,
            "entity_id": str(entity_id) if entity_id else None,
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.__class__.__name__
        }
        
        if metadata:
            log_data["metadata"] = metadata
        
        self.logger.info(f"Service operation: {log_data}")


class BaseRepository(ABC, Generic[T]):
    """
    Base repository class with common CRUD operations.
    """
    
    def __init__(self, db: Session, model_class: type):
        """
        Initialize base repository.
        
        Args:
            db: Database session
            model_class: Model class for this repository
        """
        self.db = db
        self.model_class = model_class
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get(self, entity_id: UUID) -> Optional[T]:
        """
        Get entity by ID.
        
        Args:
            entity_id: Entity UUID
            
        Returns:
            Entity or None
        """
        try:
            return self.db.query(self.model_class).filter(
                self.model_class.id == entity_id
            ).first()
        except SQLAlchemyError as e:
            self.logger.error(f"Error getting entity {entity_id}: {e}")
            return None
    
    def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """
        Get all entities with pagination.

        OPTIMIZATION: Added ORDER BY to use index and prevent full table scans.
        Default limit of 100 prevents accidentally loading entire tables.

        Args:
            limit: Maximum number of entities (default 100)
            offset: Number of entities to skip

        Returns:
            List of entities
        """
        try:
            query = self.db.query(self.model_class)

            # Add ORDER BY if model has created_at or id field to use index
            if hasattr(self.model_class, 'created_at'):
                query = query.order_by(self.model_class.created_at.desc())
            elif hasattr(self.model_class, 'id'):
                query = query.order_by(self.model_class.id.desc())

            return query.limit(limit).offset(offset).all()
        except SQLAlchemyError as e:
            self.logger.error(f"Error getting entities: {e}")
            return []
    
    def create(self, entity: T) -> T:
        """
        Create new entity.
        
        Args:
            entity: Entity to create
            
        Returns:
            Created entity
        """
        try:
            self.db.add(entity)
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except SQLAlchemyError as e:
            self.logger.error(f"Error creating entity: {e}")
            self.db.rollback()
            raise
    
    def update(self, entity: T) -> T:
        """
        Update existing entity.
        
        Args:
            entity: Entity to update
            
        Returns:
            Updated entity
        """
        try:
            self.db.merge(entity)
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except SQLAlchemyError as e:
            self.logger.error(f"Error updating entity: {e}")
            self.db.rollback()
            raise
    
    def delete(self, entity_id: UUID) -> bool:
        """
        Delete entity by ID.
        
        Args:
            entity_id: Entity UUID
            
        Returns:
            True if successful
        """
        try:
            entity = self.get(entity_id)
            if entity:
                self.db.delete(entity)
                self.db.commit()
                return True
            return False
        except SQLAlchemyError as e:
            self.logger.error(f"Error deleting entity {entity_id}: {e}")
            self.db.rollback()
            return False
    
    def count(self) -> int:
        """
        Count total entities.
        
        Returns:
            Total count
        """
        try:
            return self.db.query(self.model_class).count()
        except SQLAlchemyError as e:
            self.logger.error(f"Error counting entities: {e}")
            return 0


class BaseQuizService(BaseService):
    """
    Base class for quiz-related services.
    """
    
    def create_quiz_message(
        self,
        patient_id: UUID,
        question: Dict[str, Any],
        session_id: str,
        question_index: int,
        total_questions: int,
        patient_name: Optional[str] = None
    ):
        """
        Create quiz message using factory.
        
        Args:
            patient_id: Patient UUID
            question: Question data
            session_id: Quiz session ID
            question_index: Current question index
            total_questions: Total questions
            patient_name: Optional patient name
            
        Returns:
            Created message
        """
        return self.message_factory.create_quiz_message(
            patient_id=patient_id,
            question=question,
            session_id=session_id,
            question_index=question_index,
            total_questions=total_questions,
            patient_name=patient_name
        )
    
    def validate_quiz_response(
        self,
        response: str,
        expected_type: str,
        options: Optional[List[Dict[str, Any]]] = None
    ) -> tuple[bool, Any, str]:
        """
        Validate quiz response based on type.
        
        Args:
            response: User response
            expected_type: Expected response type
            options: Available options for validation
            
        Returns:
            Tuple of (is_valid, parsed_value, error_message)
        """
        response = response.strip()
        
        if expected_type == "OPEN_TEXT":
            if not response:
                return False, None, "Resposta não pode estar vazia"
            return True, response, ""
        
        elif expected_type == "YES_NO":
            response_lower = response.lower()
            yes_words = ['sim', 'yes', 's', 'claro']
            no_words = ['não', 'nao', 'no', 'n', 'nunca']
            
            if any(word in response_lower for word in yes_words):
                return True, "yes", ""
            elif any(word in response_lower for word in no_words):
                return True, "no", ""
            else:
                return False, None, "Por favor, responda com 'sim' ou 'não'"
        
        elif expected_type == "SCALE":
            import re
            numbers = re.findall(r'\d+', response)
            
            if not numbers:
                return False, None, "Por favor, forneça um número de 1 a 10"
            
            value = int(numbers[0])
            if 1 <= value <= 10:
                return True, value, ""
            else:
                return False, None, "Por favor, escolha um número entre 1 e 10"
        
        elif expected_type == "MULTIPLE_CHOICE" and options:
            # Try exact match
            for option in options:
                if response.lower() == option['value'].lower():
                    return True, option['value'], ""
            
            # Try partial match
            for option in options:
                if response.lower() in option['text'].lower():
                    return True, option['value'], ""
            
            return False, None, "Por favor, escolha uma das opções disponíveis"
        
        return False, None, "Tipo de resposta não reconhecido"


class BaseFlowService(BaseService):
    """
    Base class for flow-related services.
    """
    
    def get_patient_context(self, patient_id: UUID) -> Dict[str, Any]:
        """
        Get patient context for flow processing.
        
        Args:
            patient_id: Patient UUID
            
        Returns:
            Patient context dictionary
        """
        from app.repositories.patient import PatientRepository
        from app.repositories.flow import FlowStateRepository
        
        patient_repo = PatientRepository(self.db)
        flow_repo = FlowStateRepository(self.db)
        
        patient = patient_repo.get(patient_id)
        active_flow = flow_repo.get_active_flow(patient_id)
        
        if not patient:
            return {}
        
        context = {
            "patient_id": str(patient_id),
            "patient_name": patient.name,
            "patient_phone": patient.phone,
            "enrollment_date": patient.created_at.isoformat() if hasattr(patient, 'created_at') else None
        }
        
        if active_flow:
            context.update({
                "flow_type": active_flow.flow_type,
                "flow_step": active_flow.current_step,
                "flow_started": active_flow.started_at.isoformat(),
                "flow_data": active_flow.state_data or {}
            })
        
        return context
    
    def should_trigger_action(
        self,
        trigger_type: str,
        patient_context: Dict[str, Any]
    ) -> bool:
        """
        Determine if an action should be triggered.
        
        Args:
            trigger_type: Type of trigger
            patient_context: Patient context
            
        Returns:
            True if action should be triggered
        """
        # Implement trigger logic based on type
        trigger_rules = {
            "daily_message": lambda ctx: True,  # Always trigger daily
            "weekly_quiz": lambda ctx: datetime.utcnow().weekday() == 0,  # Monday
            "monthly_report": lambda ctx: datetime.utcnow().day == 1,  # First of month
        }
        
        rule = trigger_rules.get(trigger_type)
        if rule:
            return rule(patient_context)
        
        return False