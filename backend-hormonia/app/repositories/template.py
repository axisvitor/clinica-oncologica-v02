from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.template import MessageTemplate
from app.repositories.base import BaseRepository

class TemplateRepository(BaseRepository[MessageTemplate]):
    """Repository for MessageTemplate model."""

    def __init__(self, db: Session):
        super().__init__(db, MessageTemplate)

    def get_by_name(self, name: str) -> Optional[MessageTemplate]:
        """Get a template by its name."""
        return self.db.query(MessageTemplate).filter(
            MessageTemplate.name == name,
            MessageTemplate.is_active == True
        ).first()

    def list_active(self) -> List[MessageTemplate]:
        """List all active templates."""
        return self.db.query(MessageTemplate).filter(
            MessageTemplate.is_active == True
        ).all()
