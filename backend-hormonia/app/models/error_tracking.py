"""
Error tracking model for monitoring and debugging critical system errors.
"""
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from datetime import datetime

from app.models.base import BaseModel


class ErrorLog(BaseModel):
    """Model for tracking and deduplicating system errors."""
    __tablename__ = "error_logs"

    error_type = Column(String(100), nullable=False, index=True)
    """Type of error (e.g., 'DI_GENERATOR', 'ROLE_ENUM', 'SCHEMA_MISMATCH')"""
    
    error_message = Column(Text, nullable=False)
    """The error message or description"""
    
    stack_trace = Column(Text, nullable=True)
    """Full stack trace of the error (optional)"""
    
    context = Column(JSONB, default={}, nullable=False)
    """Additional context data as JSON (request info, user data, etc.)"""
    
    count = Column(Integer, default=1, nullable=False)
    """Number of times this error has occurred (for deduplication)"""
    
    first_seen = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    """When this error was first encountered"""
    
    last_seen = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    """When this error was last encountered"""
    
    resolved = Column(Boolean, default=False, nullable=False)
    """Whether this error has been resolved"""
    
    severity = Column(String(20), default="ERROR", nullable=False)
    """Error severity level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"""

    def __repr__(self):
        return f"<ErrorLog(type='{self.error_type}', count={self.count}, resolved={self.resolved})>"

    def increment_count(self):
        """Increment the error count and update last_seen timestamp."""
        self.count += 1
        self.last_seen = datetime.utcnow()

    def mark_resolved(self):
        """Mark this error as resolved."""
        self.resolved = True

    @classmethod
    def create_error_key(cls, error_type: str, error_message: str) -> str:
        """Create a unique key for error deduplication."""
        return f"{error_type}:{hash(error_message)}"