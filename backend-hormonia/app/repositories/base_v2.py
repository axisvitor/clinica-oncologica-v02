"""
Base Repository for API v2
Enhanced repository with cursor-based pagination support.
"""

from typing import Any, Dict, Generic, List, Optional, Tuple, Type, TypeVar
from uuid import UUID
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models.base import BaseModel
from app.schemas.v2.common import CursorEncoder

ModelType = TypeVar("ModelType", bound=BaseModel)
logger = logging.getLogger(__name__)


class BaseRepositoryV2(Generic[ModelType]):
    """Base repository with cursor-based pagination for API v2"""
    
    def __init__(self, db: Session, model: Type[ModelType]):
        self.db = db
        self.model = model
    
    def list_paginated(
        self,
        cursor: Optional[str] = None,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = "created_at"
    ) -> Tuple[List[ModelType], int, bool]:
        """
        List items with cursor-based pagination.
        
        Args:
            cursor: Pagination cursor from previous response
            limit: Items per page (1-100)
            filters: Additional filter criteria
            order_by: Field to order by (default: created_at)
            
        Returns:
            Tuple of (items, total_count, has_more)
        """
        query = self.db.query(self.model)
        
        # Apply filters
        if filters:
            query = self._apply_filters(query, filters)
        
        # Get total count
        total = query.count()
        
        # Apply cursor
        if cursor:
            try:
                cursor_data = CursorEncoder.decode(cursor)
                query = self._apply_cursor(query, cursor_data, order_by)
            except ValueError as e:
                logger.warning(f"Invalid cursor: {e}")
                # Continue without cursor
        
        # Order and limit
        order_field = getattr(self.model, order_by, self.model.created_at)
        query = query.order_by(
            order_field.desc(),
            self.model.id.desc()
        ).limit(limit + 1)  # Fetch one extra to check has_more
        
        items = query.all()
        has_more = len(items) > limit
        
        if has_more:
            items = items[:limit]
        
        return items, total, has_more
    
    def _apply_filters(self, query, filters: Dict[str, Any]):
        """Apply filter criteria to query."""
        for field, value in filters.items():
            if hasattr(self.model, field) and value is not None:
                query = query.filter(getattr(self.model, field) == value)
        return query
    
    def _apply_cursor(self, query, cursor_data: Dict[str, Any], order_by: str):
        """Apply cursor-based filtering to query."""
        if "id" not in cursor_data:
            return query
        
        order_field = getattr(self.model, order_by, self.model.created_at)
        
        # Handle both timestamp and ID for stable pagination
        if "created_at" in cursor_data:
            cursor_timestamp = datetime.fromisoformat(cursor_data["created_at"])
            query = query.filter(
                or_(
                    order_field < cursor_timestamp,
                    and_(
                        order_field == cursor_timestamp,
                        self.model.id < cursor_data["id"]
                    )
                )
            )
        else:
            # Fallback to ID-only cursor
            query = query.filter(self.model.id < cursor_data["id"])
        
        return query
    
    def get_by_id(self, id: UUID) -> Optional[ModelType]:
        """Get record by ID."""
        return self.db.query(self.model).filter(self.model.id == id).first()
    
    def create(self, obj_in: Dict[str, Any]) -> ModelType:
        """Create new record."""
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def update(self, db_obj: ModelType, obj_in: Dict[str, Any]) -> ModelType:
        """Update existing record."""
        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def delete(self, id: UUID) -> bool:
        """Delete record by ID."""
        db_obj = self.get_by_id(id)
        if db_obj:
            self.db.delete(db_obj)
            self.db.commit()
            return True
        return False
    
    def soft_delete(self, id: UUID) -> bool:
        """
        Soft delete record by setting is_active=False.
        
        Args:
            id: Record ID
            
        Returns:
            True if deleted, False if not found
        """
        db_obj = self.get_by_id(id)
        if db_obj and hasattr(db_obj, 'is_active'):
            db_obj.is_active = False
            self.db.add(db_obj)
            self.db.commit()
            return True
        return False
