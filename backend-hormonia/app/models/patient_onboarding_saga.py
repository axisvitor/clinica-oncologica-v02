"""
Model para Patient Onboarding Saga - Sistema Hormonia

Este módulo define o modelo de banco de dados para rastreamento de sagas
de onboarding de pacientes com retry logic e compensações.

Sprint 1 - Transação Distribuída no Cadastro
"""

from enum import Enum
from datetime import datetime
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM as PG_ENUM
from sqlalchemy.orm import relationship
import uuid

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.patient import Patient


class SagaStatus(str, Enum):
    """Status possíveis de uma saga de onboarding."""

    STARTED = "STARTED"
    IN_PROGRESS = "IN_PROGRESS"  # Alias for STARTED - saga orchestrator compatibility
    STEP_1_PATIENT_CREATED = "STEP_1_PATIENT_CREATED"
    STEP_2_FIREBASE_USER_CREATED = "STEP_2_FIREBASE_USER_CREATED"
    STEP_3_FLOW_INITIALIZED = "STEP_3_FLOW_INITIALIZED"
    STEP_4_MESSAGE_SENT = "STEP_4_MESSAGE_SENT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"


class PatientOnboardingSaga(BaseModel):
    """
    Model para rastreamento de sagas de onboarding de pacientes.

    Implementa o Saga Pattern para garantir consistência em transações distribuídas.

    Attributes:
        id: ID único da saga
        patient_id: ID do paciente criado (pode ser None se falhou antes)
        doctor_id: ID do médico responsável
        status: Status atual da saga
        current_step: Step atual (0-4)
        retry_count: Número de retries executados
        max_retries: Máximo de retries permitidos (padrão: 3)
        patient_data: Dados do paciente (JSONB)
        execution_log: Log de execução de cada step (JSONB array)
        error_message: Mensagem de erro se falhou
        error_type: Tipo do erro
        next_retry_at: Data/hora do próximo retry agendado
        started_at: Quando a saga iniciou
        completed_at: Quando a saga completou com sucesso
        failed_at: Quando a saga falhou definitivamente
    """

    __tablename__ = "patient_onboarding_saga"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Keys
    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    doctor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Status and Progress
    status = Column(
        PG_ENUM(SagaStatus, name="saga_status", create_type=False),
        nullable=False,
        default=SagaStatus.STARTED,
        index=True,
    )
    current_step = Column(Integer, nullable=False, default=0)

    # Retry Logic
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    # Data
    patient_data = Column(JSONB, nullable=False)
    execution_log = Column(JSONB, nullable=False, default=list)

    # Error Information
    error_message = Column(Text, nullable=True)
    error_type = Column(String(255), nullable=True)

    # Timestamps
    started_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    patient = relationship("Patient", back_populates="onboarding_sagas")
    doctor = relationship("User", foreign_keys=[doctor_id])

    # Indexes (defined in migration)
    __table_args__ = (
        Index("idx_patient_onboarding_saga_patient_id", "patient_id"),
        Index("idx_patient_onboarding_saga_status", "status"),
        Index("idx_patient_onboarding_saga_doctor_id", "doctor_id"),
        Index(
            "idx_patient_onboarding_saga_retry",
            "status",
            "next_retry_at",
            postgresql_where=Column("status") == SagaStatus.RETRY_SCHEDULED,
        ),
    )

    def __repr__(self):
        return (
            f"<PatientOnboardingSaga("
            f"id='{self.id}', "
            f"patient_id='{self.patient_id}', "
            f"status='{self.status}', "
            f"step={self.current_step}, "
            f"retries={self.retry_count}/{self.max_retries}"
            f")>"
        )

    def add_log_entry(self, step: int, action: str, status: str, message: str = None):
        """
        Adiciona entrada ao log de execução.

        Args:
            step: Número do step (1-4)
            action: Ação executada (ex: "create_patient", "send_message")
            status: Status (ex: "success", "failed", "compensated")
            message: Mensagem adicional (opcional)
        """
        log_entry = {
            "step": step,
            "action": action,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if message:
            log_entry["message"] = message

        if not self.execution_log:
            self.execution_log = []

        self.execution_log.append(log_entry)

    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Retorna resumo da execução da saga.

        Returns:
            Dicionário com resumo da execução
        """
        return {
            "saga_id": str(self.id),
            "patient_id": str(self.patient_id) if self.patient_id else None,
            "status": self.status.value,
            "current_step": self.current_step,
            "total_steps": 4,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "failed_at": self.failed_at.isoformat() if self.failed_at else None,
            "duration_seconds": self._calculate_duration(),
            "execution_log": self.execution_log or [],
            "error": {
                "type": self.error_type,
                "message": self.error_message,
            }
            if self.error_message
            else None,
        }

    def _calculate_duration(self) -> Optional[float]:
        """Calcula duração da saga em segundos."""
        if not self.started_at:
            return None

        end_time = self.completed_at or self.failed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()

    def is_completed(self) -> bool:
        """Verifica se a saga foi completada com sucesso."""
        return self.status == SagaStatus.COMPLETED

    def is_failed(self) -> bool:
        """Verifica se a saga falhou definitivamente."""
        return self.status == SagaStatus.FAILED

    def can_retry(self) -> bool:
        """Verifica se a saga pode ser retentada."""
        return (
            self.status in [SagaStatus.FAILED, SagaStatus.RETRY_SCHEDULED]
            and self.retry_count < self.max_retries
        )

    def should_compensate(self) -> bool:
        """Verifica se deve executar compensações."""
        return (
            self.status == SagaStatus.FAILED
            and self.current_step > 0
            and self.retry_count >= self.max_retries
        )

    def get_last_error(self) -> Optional[Dict[str, str]]:
        """Retorna informações do último erro."""
        if not self.error_message:
            return None

        return {
            "type": self.error_type or "Unknown",
            "message": self.error_message,
            "step": self.current_step,
            "retry_count": self.retry_count,
        }

    def get_steps_to_compensate(self) -> List[int]:
        """
        Retorna lista de steps que precisam ser compensados.

        Returns:
            Lista de números de steps em ordem reversa
        """
        return list(range(self.current_step, 0, -1))


__all__ = ["PatientOnboardingSaga", "SagaStatus"]
