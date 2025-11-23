"""
Message Template model.
"""
from sqlalchemy import Column, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import BaseModel

class MessageTemplate(BaseModel):
    """
    Message Template model for WhatsApp messages.
    
    Attributes:
        name (str): Unique name of the template.
        content (str): The message content with placeholders.
        variables (list): List of variable names used in content.
        message_type (str): Type of message (text, image, document, etc.).
        media_url (str): Optional URL for media messages.
        is_active (bool): Whether the template is active.
    """
    __tablename__ = "message_templates"

    name = Column(String, unique=True, nullable=False, index=True)
    content = Column(Text, nullable=False)
    variables = Column(JSONB, default=list)
    message_type = Column(String, default="text", nullable=False)
    media_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<MessageTemplate(name={self.name}, type={self.message_type})>"

    def format(self, **kwargs) -> str:
        """Format template with provided variables."""
        try:
            return self.content.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}")
