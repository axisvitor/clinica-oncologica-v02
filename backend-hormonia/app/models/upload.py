"""
Upload Model

Tracks uploaded files for quota management and file lifecycle.
Supports soft deletes for compliance and data retention.
"""

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.models.base import BaseModel


class Upload(BaseModel):
    """
    Upload model for file tracking and quota management.

    Attributes:
        user_id: UUID of user who uploaded the file
        file_name: Original filename
        file_size: Size in bytes
        file_type: MIME type
        storage_path: Path to file in storage (local or cloud)
        storage_provider: Storage provider (local, s3, gcs, azure)
        content_hash: SHA256 hash for deduplication
        file_metadata: Additional file metadata (JSONB)
        is_public: Whether file is publicly accessible
        virus_scanned: Whether file was scanned for viruses
        virus_clean: Whether file passed virus scan
        deleted_at: Soft delete timestamp
    """
    __tablename__ = "uploads"

    # User relationship
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # File information
    file_name = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # Bytes
    file_type = Column(String(100), nullable=True)  # MIME type

    # Storage information
    storage_path = Column(String(1000), nullable=False, unique=True)
    storage_provider = Column(
        String(50),
        nullable=False,
        default="local",
        server_default="local"
    )

    # Deduplication
    content_hash = Column(String(64), nullable=True)  # SHA256

    # File Metadata (renamed from 'metadata' to avoid SQLAlchemy conflict)
    file_metadata = Column(JSONB, nullable=True, default={}, server_default="{}")

    # Access control
    is_public = Column(Boolean, nullable=False, default=False, server_default="false")

    # Security
    virus_scanned = Column(Boolean, nullable=False, default=False, server_default="false")
    virus_clean = Column(Boolean, nullable=True)  # Null if not scanned

    # Relationships
    user = relationship("User", backref="uploads")

    # Indexes for quota queries
    __table_args__ = (
        Index(
            "ix_uploads_user_quota",
            user_id,
            file_size,
            postgresql_where=(Column("deleted_at").is_(None))
        ),
        Index(
            "ix_uploads_storage_path",
            storage_path
        ),
        Index(
            "ix_uploads_content_hash",
            content_hash,
            postgresql_where=(content_hash.isnot(None))
        ),
    )

    def __repr__(self):
        return f"<Upload(id={self.id}, file_name='{self.file_name}', size={self.file_size})>"

    @property
    def size_mb(self) -> float:
        """File size in megabytes"""
        return round(self.file_size / (1024 * 1024), 2)

    @property
    def size_kb(self) -> float:
        """File size in kilobytes"""
        return round(self.file_size / 1024, 2)
