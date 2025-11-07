from typing import Any, Dict, Generic, List, Optional, Tuple, Type, TypeVar, Union
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from app.models.base import BaseModel
from app.services.unified_cache import UnifiedCacheService


ModelType = TypeVar("ModelType", bound=BaseModel)
logger = logging.getLogger(__name__)


class BaseRepository(Generic[ModelType]):
    """Base repository with common CRUD operations"""
    
    def __init__(self, db: Session, model: Type[ModelType]):
        self.db = db
        self.model = model
    
    def get_by_id(self, id: UUID) -> Optional[ModelType]:
        """Get record by ID"""
        return self.db.query(self.model).filter(self.model.id == id).first()
    
    def get(self, id: UUID) -> Optional[ModelType]:
        """Get record by ID (alias for get_by_id)"""
        return self.get_by_id(id)
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """
        Get all records with pagination.
        
        Args:
            skip: Number of records to skip (must be >= 0)
            limit: Maximum number of records to return (must be > 0)
            
        Returns:
            List of model instances
            
        Raises:
            ValueError: If skip < 0 or limit <= 0
        """
        if skip < 0:
            raise ValueError("Skip parameter must be >= 0")
        if limit <= 0:
            raise ValueError("Limit parameter must be > 0")
            
        return self.db.query(self.model).offset(skip).limit(limit).all()
    
    def create(self, obj_in: Dict[str, Any]) -> ModelType:
        """
        Create new record with automatic cache invalidation.

        CACHE INVALIDATION: Invalidates related caches after creation.
        """
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)

        # Invalidate caches after mutation
        self._invalidate_caches_for_model(db_obj)

        return db_obj
    
    def update(self, db_obj: ModelType, obj_in: Dict[str, Any]) -> ModelType:
        """
        Update existing record with automatic cache invalidation.

        CACHE INVALIDATION: Invalidates related caches after update.
        """
        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)

        # Invalidate caches after mutation
        self._invalidate_caches_for_model(db_obj)

        return db_obj
    
    def delete(self, id: UUID) -> bool:
        """
        Delete record by ID with automatic cache invalidation.

        CACHE INVALIDATION: Invalidates related caches after deletion.
        """
        db_obj = self.get_by_id(id)
        if db_obj:
            # Invalidate caches BEFORE deletion (while we still have the object)
            self._invalidate_caches_for_model(db_obj)

            self.db.delete(db_obj)
            self.db.commit()
            return True
        return False
    
    def count(self, **filters) -> int:
        """
        Count total records with optional filters.
        
        Args:
            **filters: Additional filter criteria
            
        Returns:
            Total number of records matching filters
        """
        query = self.db.query(self.model)
        
        # Apply filters if provided
        for field, value in filters.items():
            if hasattr(self.model, field) and value is not None:
                query = query.filter(getattr(self.model, field) == value)
        
        return query.count()
    
    def get_paginated(self, skip: int = 0, limit: int = 100, **filters) -> Tuple[List[ModelType], int]:
        """
        Get paginated records with total count.
        
        Args:
            skip: Number of records to skip (must be >= 0)
            limit: Maximum number of records to return (must be > 0)
            **filters: Additional filter criteria
            
        Returns:
            Tuple of (items, total_count) where items is the paginated list
            and total_count is the total number of records matching filters
            
        Raises:
            ValueError: If skip < 0 or limit <= 0
        """
        # Validate pagination parameters
        if skip < 0:
            raise ValueError("Skip parameter must be >= 0")
        if limit <= 0:
            raise ValueError("Limit parameter must be > 0")
        
        query = self.db.query(self.model)
        
        # Apply filters if provided
        for field, value in filters.items():
            if hasattr(self.model, field) and value is not None:
                query = query.filter(getattr(self.model, field) == value)
        
        # Get total count before applying pagination
        total = query.count()
        
        # Apply pagination
        items = query.offset(skip).limit(limit).all()
        
        return items, total
    
    def exists(self, id: UUID) -> bool:
        """
        Check if record exists by ID.

        Args:
            id: Record ID to check

        Returns:
            True if record exists, False otherwise
        """
        return self.db.query(self.model).filter(self.model.id == id).first() is not None

    def _invalidate_caches_for_model(self, db_obj: ModelType):
        """
        Invalidate caches for a model instance after mutations.

        CACHE INVALIDATION STRATEGY:
        - Patient: Invalidate patient:ID tag
        - Quiz: Invalidate quiz:ID tag
        - Report: Invalidate report:ID tag

        Args:
            db_obj: Model instance that was mutated
        """
        try:
            cache_service = get_cache_service()
            model_name = self.model.__name__.lower()

            # Get model ID
            if hasattr(db_obj, 'id') and db_obj.id:
                tag = f"{model_name}:{db_obj.id}"
                cache_service.invalidate_by_tag(tag)
                logger.debug(f"Cache invalidated for {tag}")

            # Model-specific invalidations
            if model_name == 'patient':
                # Invalidate doctor's patient list if patient has doctor_id
                if hasattr(db_obj, 'doctor_id') and db_obj.doctor_id:
                    doctor_tag = f"doctor:{db_obj.doctor_id}"
                    cache_service.invalidate_by_tag(doctor_tag)

            elif model_name == 'quizsession':
                # Invalidate patient's quiz list
                if hasattr(db_obj, 'patient_id') and db_obj.patient_id:
                    patient_tag = f"patient:{db_obj.patient_id}"
                    cache_service.invalidate_by_tag(patient_tag)

            elif model_name == 'medicalreport':
                # Invalidate patient's report list
                if hasattr(db_obj, 'patient_id') and db_obj.patient_id:
                    patient_tag = f"patient:{db_obj.patient_id}"
                    cache_service.invalidate_by_tag(patient_tag)

        except Exception as e:
            # Log error but don't fail the mutation
            logger.error(f"Cache invalidation error for {model_name}: {e}")