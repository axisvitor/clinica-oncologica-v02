"""
Schemas Pydantic para Dead Letter Queue (DLQ).

Sprint 1 - DLQ Estruturada com Dashboard
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.failed_message import DLQStatus, FailureReason


class DLQMessageBase(BaseModel):
    """Base schema para mensagem na DLQ."""

    message_id: UUID
    patient_id: UUID
    error_message: str
    error_type: str
    failure_reason: FailureReason


class DLQMessageResponse(DLQMessageBase):
    """Schema para resposta de mensagem da DLQ."""

    id: UUID
    payload: Dict[str, Any]
    retry_count: int
    status: DLQStatus
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    last_retry_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DLQMessageList(BaseModel):
    """Schema para lista paginada de mensagens da DLQ."""

    items: List[DLQMessageResponse]
    total: int
    page: int
    size: int
    pages: int


class DLQRetryRequest(BaseModel):
    """Schema para requisição de retry manual."""

    dlq_id: UUID
    reason: Optional[str] = Field(None, description="Razão do retry manual (opcional)")


class DLQDiscardRequest(BaseModel):
    """Schema para requisição de descarte."""

    dlq_id: UUID
    reason: str = Field(..., description="Razão do descarte (obrigatório)")


class DLQStats(BaseModel):
    """Schema para estatísticas da DLQ."""

    total: int = Field(..., description="Total de mensagens na DLQ")
    pending: int = Field(..., description="Mensagens pendentes")
    retry_scheduled: int = Field(..., description="Retries agendados")
    retrying: int = Field(..., description="Em processo de retry")
    resolved: int = Field(..., description="Mensagens resolvidas")
    discarded: int = Field(..., description="Mensagens descartadas")
    max_retries_exceeded: int = Field(
        ..., description="Mensagens que excederam máximo de retries"
    )
    transient_errors_24h: int = Field(
        ..., description="Erros transientes nas últimas 24h"
    )
    permanent_errors_24h: int = Field(
        ..., description="Erros permanentes nas últimas 24h"
    )
    unknown_errors_24h: int = Field(
        ..., description="Erros desconhecidos nas últimas 24h"
    )
    retry_success_rate: float = Field(..., description="Taxa de sucesso de retries (%)")


class DLQFilterParams(BaseModel):
    """Schema para parâmetros de filtro."""

    status: Optional[DLQStatus] = None
    category: Optional[str] = Field(
        None, description="Categoria do erro: transient, permanent, unknown"
    )
    patient_id: Optional[UUID] = None
    page: int = Field(1, ge=1, description="Página atual")
    size: int = Field(20, ge=1, le=100, description="Tamanho da página")


__all__ = [
    "DLQMessageBase",
    "DLQMessageResponse",
    "DLQMessageList",
    "DLQRetryRequest",
    "DLQDiscardRequest",
    "DLQStats",
    "DLQFilterParams",
]
