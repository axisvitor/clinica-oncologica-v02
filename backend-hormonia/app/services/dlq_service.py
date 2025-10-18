"""
Dead Letter Queue (DLQ) Service - Sistema Hormonia

Este módulo gerencia a fila de mensagens com falha (DLQ) com retry inteligente,
categorização de erros e dashboard administrativo.

Sprint 1 - DLQ Estruturada com Dashboard
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID
import time

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from app.models.failed_message import FailedMessage, FailureReason, DLQStatus
from app.schemas.dlq import (
    DLQMessageResponse,
    DLQMessageList,
    DLQRetryRequest,
    DLQStats,
)
from app.monitoring.dlq_metrics import (
    record_dlq_message,
    record_dlq_retry,
    record_dlq_discard,
    update_dlq_queue_size,
    update_oldest_message_age,
    update_processing_count,
    record_retry_attempts,
    initialize_dlq_metrics,
)

logger = logging.getLogger(__name__)


class ErrorCategory(str, Enum):
    """Categorias de erro para retry inteligente."""

    TRANSIENT = "transient"  # Erro temporário - retry automático
    PERMANENT = "permanent"  # Erro permanente - requer intervenção manual
    UNKNOWN = "unknown"  # Erro desconhecido - análise necessária


class DLQService:
    """
    Serviço de gerenciamento da Dead Letter Queue.

    Features:
    - Categorização automática de erros
    - Retry inteligente baseado em categoria
    - Dashboard administrativo
    - Métricas e estatísticas
    - Paginação e filtros
    """

    # Erros transientes (retry automático)
    TRANSIENT_ERRORS = [
        "ConnectionError",
        "TimeoutError",
        "ConnectionResetError",
        "TemporaryFailure",
        "ServiceUnavailable",
        "TooManyRequests",
        "RateLimitExceeded",
        "NetworkError",
        "HTTPError: 429",
        "HTTPError: 503",
        "HTTPError: 504",
    ]

    # Erros permanentes (requer intervenção)
    PERMANENT_ERRORS = [
        "ValidationError",
        "AuthenticationError",
        "AuthorizationError",
        "NotFoundError",
        "InvalidCredentials",
        "HTTPError: 400",
        "HTTPError: 401",
        "HTTPError: 403",
        "HTTPError: 404",
        "HTTPError: 422",
    ]

    # Configuração de retry
    MAX_RETRY_ATTEMPTS = 5
    RETRY_DELAYS = [60, 300, 900, 3600, 7200]  # 1min, 5min, 15min, 1h, 2h

    def __init__(self, db: Session):
        """
        Inicializa o serviço de DLQ.

        Args:
            db: Sessão do banco de dados
        """
        self.db = db

        # Inicializar métricas DLQ
        config = {
            "max_retries": self.MAX_RETRY_ATTEMPTS,
            "retry_delay_seconds": self.RETRY_DELAYS[0],
            "max_age_hours": 72,
            "retention_days": 30,
        }
        initialize_dlq_metrics(config)

    def categorize_error(self, error_message: str, error_type: str) -> ErrorCategory:
        """
        Categoriza o erro para determinar estratégia de retry.

        Args:
            error_message: Mensagem de erro
            error_type: Tipo do erro

        Returns:
            Categoria do erro
        """
        # Verificar erros transientes
        for transient_error in self.TRANSIENT_ERRORS:
            if (
                transient_error.lower() in error_message.lower()
                or transient_error.lower() in error_type.lower()
            ):
                return ErrorCategory.TRANSIENT

        # Verificar erros permanentes
        for permanent_error in self.PERMANENT_ERRORS:
            if (
                permanent_error.lower() in error_message.lower()
                or permanent_error.lower() in error_type.lower()
            ):
                return ErrorCategory.PERMANENT

        # Erro desconhecido
        return ErrorCategory.UNKNOWN

    def add_to_dlq(
        self,
        message_id: UUID,
        patient_id: UUID,
        error_message: str,
        error_type: str,
        payload: Dict[str, Any],
        failure_reason: FailureReason,
    ) -> FailedMessage:
        """
        Adiciona mensagem à DLQ.

        Args:
            message_id: ID da mensagem
            patient_id: ID do paciente
            error_message: Mensagem de erro
            error_type: Tipo do erro
            payload: Payload da mensagem original
            failure_reason: Razão da falha

        Returns:
            Mensagem adicionada à DLQ
        """
        # Categorizar erro
        category = self.categorize_error(error_message, error_type)

        # Criar entrada na DLQ
        failed_message = FailedMessage(
            message_id=message_id,
            patient_id=patient_id,
            error_message=error_message,
            error_type=error_type,
            payload=payload,
            failure_reason=failure_reason,
            retry_count=0,
            status=DLQStatus.PENDING,
            metadata={
                "error_category": category.value,
                "added_at": datetime.utcnow().isoformat(),
            },
        )

        self.db.add(failed_message)
        self.db.commit()
        self.db.refresh(failed_message)

        # Registrar métrica Prometheus
        record_dlq_message(
            category=failure_reason.value,
            source="system",
            error_type=error_type,
            message_age_seconds=0,
        )

        logger.info(
            f"Mensagem adicionada à DLQ: {message_id} (categoria: {category.value})"
        )

        # Atualizar tamanho da fila
        self._update_queue_metrics()

        # Se for erro transiente, agendar retry automático
        if category == ErrorCategory.TRANSIENT:
            self._schedule_automatic_retry(failed_message)

        return failed_message

    def _update_queue_metrics(self):
        """Atualiza métricas Prometheus do tamanho da fila."""
        try:
            # Contar mensagens por categoria e status
            from sqlalchemy import func

            results = (
                self.db.query(
                    FailedMessage.failure_reason,
                    FailedMessage.status,
                    func.count(FailedMessage.id).label("count")
                )
                .group_by(FailedMessage.failure_reason, FailedMessage.status)
                .all()
            )

            for failure_reason, status, count in results:
                update_dlq_queue_size(
                    category=failure_reason.value,
                    status=status.value,
                    size=count,
                )

            # Atualizar idade da mensagem mais antiga
            oldest = (
                self.db.query(FailedMessage)
                .order_by(FailedMessage.created_at)
                .first()
            )

            if oldest:
                age_seconds = (datetime.utcnow() - oldest.created_at).total_seconds()
                update_oldest_message_age(
                    category=oldest.failure_reason.value,
                    age_seconds=age_seconds,
                )

        except Exception as e:
            logger.error(f"Erro ao atualizar métricas DLQ: {e}")
</text>


    def _schedule_automatic_retry(self, failed_message: FailedMessage):
        """
        Agenda retry automático para erro transiente.

        Args:
            failed_message: Mensagem com falha
        """
        if failed_message.retry_count >= self.MAX_RETRY_ATTEMPTS:
            logger.warning(
                f"Mensagem {failed_message.message_id} excedeu máximo de retries"
            )
            failed_message.status = DLQStatus.MAX_RETRIES_EXCEEDED
            self.db.commit()

            # Registrar métrica
            record_retry_attempts(
                category=failed_message.failure_reason.value,
                attempts=failed_message.retry_count,
            )
            return

        # Calcular delay baseado no número de retries
        delay_seconds = self.RETRY_DELAYS[
            min(failed_message.retry_count, len(self.RETRY_DELAYS) - 1)
        ]

        # Atualizar metadata com schedule
        failed_message.metadata["next_retry_at"] = (
            datetime.utcnow() + timedelta(seconds=delay_seconds)
        ).isoformat()

        failed_message.status = DLQStatus.RETRY_SCHEDULED
        self.db.commit()

        logger.info(
            f"Retry automático agendado para {failed_message.message_id} "
            f"em {delay_seconds}s (tentativa {failed_message.retry_count + 1}/{self.MAX_RETRY_ATTEMPTS})"
        )

    def retry_message(
        self, dlq_id: UUID, manual: bool = False
    ) -> tuple[bool, Optional[str]]:
        """
        Tenta reprocessar mensagem da DLQ.

        Args:
            dlq_id: ID da entrada na DLQ
            manual: Se é retry manual (admin)

        Returns:
            Tuple (sucesso, mensagem_erro)
        """
        start_time = time.time()

        failed_message = (
            self.db.query(FailedMessage).filter(FailedMessage.id == dlq_id).first()
        )

        if not failed_message:
            return False, "Mensagem não encontrada na DLQ"

        category = failed_message.failure_reason.value

        # Incrementar contador de retries
        failed_message.retry_count += 1
        failed_message.status = DLQStatus.RETRYING
        failed_message.last_retry_at = datetime.utcnow()

        if manual:
            failed_message.metadata["manual_retry"] = True
            failed_message.metadata["manual_retry_at"] = datetime.utcnow().isoformat()

        self.db.commit()

        # Atualizar métrica de processamento
        update_processing_count(category, 1)

        try:
            # Tentar reenviar mensagem
            success = self._reprocess_message(failed_message)

            duration = time.time() - start_time

            if success:
                failed_message.status = DLQStatus.RESOLVED
                failed_message.resolved_at = datetime.utcnow()
                self.db.commit()

                # Registrar métrica de sucesso
                record_dlq_retry(
                    category=category,
                    status="success",
                    duration_seconds=duration,
                )

                # Registrar tentativas
                record_retry_attempts(category, failed_message.retry_count)

                logger.info(
                    f"Mensagem {failed_message.message_id} reprocessada com sucesso"
                )

                # Atualizar métricas de fila
                self._update_queue_metrics()
                update_processing_count(category, 0)

                return True, None
            else:
                # Se falhou, determinar próximo passo
                error_category = failed_message.metadata.get("error_category", "unknown")

                # Registrar métrica de falha
                record_dlq_retry(
                    category=category,
                    status="failed",
                    duration_seconds=duration,
                    error_type=error_category,
                )

                if error_category == ErrorCategory.TRANSIENT.value:
                    # Reagendar retry automático
                    self._schedule_automatic_retry(failed_message)
                else:
                    # Erro permanente ou desconhecido - requer intervenção
                    failed_message.status = DLQStatus.PENDING
                    self.db.commit()

                update_processing_count(category, 0)
                self._update_queue_metrics()

                return False, "Falha ao reprocessar mensagem"

        except Exception as e:
            duration = time.time() - start_time

            logger.error(f"Erro ao tentar retry de {dlq_id}: {e}", exc_info=True)
            failed_message.status = DLQStatus.PENDING
            failed_message.error_message = str(e)
            self.db.commit()

            # Registrar métrica de erro
            record_dlq_retry(
                category=category,
                status="failed",
                duration_seconds=duration,
                error_type=type(e).__name__,
            )

            update_processing_count(category, 0)
            self._update_queue_metrics()

            return False, str(e)

    def _reprocess_message(self, failed_message: FailedMessage) -> bool:
        """
        Reprocessa mensagem (lógica de reenvio).

        Args:
            failed_message: Mensagem a ser reprocessada

        Returns:
            True se sucesso, False caso contrário
        """
        # TODO: Implementar lógica real de reenvio
        # Por enquanto, apenas simula o reprocessamento

        try:
            # Aqui deveria chamar o serviço de envio de mensagem
            # from app.services.message_sender import MessageSender
            # sender = MessageSender(self.db)
            # sender.send_message(
            #     patient_id=failed_message.patient_id,
            #     content=failed_message.payload.get("content"),
            #     ...
            # )

            # Simulação
            logger.info(f"Reprocessando mensagem {failed_message.message_id}")
            return True

        except Exception as e:
            logger.error(f"Erro ao reprocessar mensagem: {e}")
            return False

    def discard_message(self, dlq_id: UUID, reason: str = "manual") -> bool:
        """
        Descarta mensagem da DLQ (não será mais processada).

        Args:
            dlq_id: ID da entrada na DLQ
            reason: Razão do descarte

        Returns:
            True se sucesso, False caso contrário
        """
        failed_message = (
            self.db.query(FailedMessage).filter(FailedMessage.id == dlq_id).first()
        )

        if not failed_message:
            return False

        category = failed_message.failure_reason.value

        failed_message.status = DLQStatus.DISCARDED
        failed_message.resolved_at = datetime.utcnow()
        failed_message.metadata["discard_reason"] = reason
        failed_message.metadata["discarded_at"] = datetime.utcnow().isoformat()

        self.db.commit()

        # Registrar métrica de descarte
        record_dlq_discard(category=category, reason=reason)

        # Atualizar métricas de fila
        self._update_queue_metrics()

        logger.info(f"Mensagem {failed_message.message_id} descartada: {reason}")

        return True

    def list_messages(
        self,
        page: int = 1,
        size: int = 20,
        status: Optional[DLQStatus] = None,
        category: Optional[ErrorCategory] = None,
        patient_id: Optional[UUID] = None,
    ) -> DLQMessageList:
        """
        Lista mensagens da DLQ com paginação e filtros.

        Args:
            page: Página atual
            size: Tamanho da página
            status: Filtrar por status
            category: Filtrar por categoria de erro
            patient_id: Filtrar por paciente

        Returns:
            Lista paginada de mensagens
        """
        query = self.db.query(FailedMessage)

        # Aplicar filtros
        filters = []

        if status:
            filters.append(FailedMessage.status == status)

        if category:
            # Filtrar por categoria no metadata
            filters.append(
                FailedMessage.metadata["error_category"].astext == category.value
            )

        if patient_id:
            filters.append(FailedMessage.patient_id == patient_id)

        if filters:
            query = query.filter(and_(*filters))

        # Ordenar por data de criação (mais recente primeiro)
        query = query.order_by(desc(FailedMessage.created_at))

        # Contar total
        total = query.count()

        # Paginar
        messages = query.offset((page - 1) * size).limit(size).all()

        # Converter para schema
        items = [DLQMessageResponse.from_orm(msg) for msg in messages]

        return DLQMessageList(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size,
        )

    def get_stats(self) -> DLQStats:
        """
        Obtém estatísticas da DLQ.

        Returns:
            Estatísticas da DLQ
        """
        # Total de mensagens
        total = self.db.query(FailedMessage).count()

        # Por status
        pending = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.status == DLQStatus.PENDING)
            .count()
        )

        retry_scheduled = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.status == DLQStatus.RETRY_SCHEDULED)
            .count()
        )

        retrying = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.status == DLQStatus.RETRYING)
            .count()
        )

        resolved = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.status == DLQStatus.RESOLVED)
            .count()
        )

        discarded = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.status == DLQStatus.DISCARDED)
            .count()
        )

        max_retries = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.status == DLQStatus.MAX_RETRIES_EXCEEDED)
            .count()
        )

        # Por categoria (últimas 24h)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_messages = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.created_at >= yesterday)
            .all()
        )

        transient_count = sum(
            1
            for msg in recent_messages
            if msg.metadata.get("error_category") == ErrorCategory.TRANSIENT.value
        )

        permanent_count = sum(
            1
            for msg in recent_messages
            if msg.metadata.get("error_category") == ErrorCategory.PERMANENT.value
        )

        unknown_count = sum(
            1
            for msg in recent_messages
            if msg.metadata.get("error_category") == ErrorCategory.UNKNOWN.value
        )

        # Taxa de sucesso de retries
        total_retries = (
            self.db.query(FailedMessage).filter(FailedMessage.retry_count > 0).count()
        )

        successful_retries = resolved

        retry_success_rate = (
            (successful_retries / total_retries * 100) if total_retries > 0 else 0
        )

        return DLQStats(
            total=total,
            pending=pending,
            retry_scheduled=retry_scheduled,
            retrying=retrying,
            resolved=resolved,
            discarded=discarded,
            max_retries_exceeded=max_retries,
            transient_errors_24h=transient_count,
            permanent_errors_24h=permanent_count,
            unknown_errors_24h=unknown_count,
            retry_success_rate=round(retry_success_rate, 2),
        )

    def process_scheduled_retries(self) -> int:
        """
        Processa retries agendados (chamado por worker/cron).

        Returns:
            Número de mensagens processadas
        """
        # Buscar mensagens com retry agendado e hora já passou
        now = datetime.utcnow()

        messages = (
            self.db.query(FailedMessage)
            .filter(FailedMessage.status == DLQStatus.RETRY_SCHEDULED)
            .all()
        )

        processed = 0

        for message in messages:
            next_retry_str = message.metadata.get("next_retry_at")
            if not next_retry_str:
                continue

            try:
                next_retry = datetime.fromisoformat(next_retry_str)

                if now >= next_retry:
                    # Hora de fazer retry
                    success, error = self.retry_message(message.id, manual=False)

                    if success:
                        processed += 1
                        logger.info(
                            f"Retry automático bem-sucedido: {message.message_id}"
                        )
                    else:
                        logger.warning(
                            f"Retry automático falhou: {message.message_id} - {error}"
                        )

            except Exception as e:
                logger.error(
                    f"Erro ao processar retry agendado de {message.id}: {e}",
                    exc_info=True,
                )

        logger.info(f"Processados {processed} retries agendados")
        return processed


__all__ = [
    "DLQService",
    "ErrorCategory",
]
