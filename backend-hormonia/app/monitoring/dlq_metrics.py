"""
DLQ Prometheus Metrics
=====================

Métricas Prometheus para monitoramento da Dead Letter Queue.

Métricas disponíveis:
- dlq_messages_total: Total de mensagens na DLQ (por categoria)
- dlq_retries_total: Total de tentativas de retry
- dlq_retries_success_total: Total de retries bem-sucedidos
- dlq_retries_failed_total: Total de retries que falharam
- dlq_discard_total: Total de mensagens descartadas
- dlq_message_age_seconds: Idade das mensagens na DLQ (histograma)
- dlq_retry_duration_seconds: Duração das tentativas de retry
- dlq_queue_size: Tamanho atual da DLQ (por categoria)
"""

from prometheus_client import Counter, Gauge, Histogram, Info
from typing import Optional


# ============================================================================
# Counters - Contadores incrementais
# ============================================================================

dlq_messages_total = Counter(
    "dlq_messages_total",
    "Total number of messages added to DLQ",
    labelnames=["category", "source", "error_type"],
)

dlq_retries_total = Counter(
    "dlq_retries_total",
    "Total number of DLQ retry attempts",
    labelnames=["category", "status"],
)

dlq_retries_success_total = Counter(
    "dlq_retries_success_total",
    "Total number of successful DLQ retries",
    labelnames=["category", "source"],
)

dlq_retries_failed_total = Counter(
    "dlq_retries_failed_total",
    "Total number of failed DLQ retries",
    labelnames=["category", "error_type"],
)

dlq_discard_total = Counter(
    "dlq_discard_total",
    "Total number of messages discarded from DLQ",
    labelnames=["category", "reason"],
)


# ============================================================================
# Gauges - Valores instantâneos
# ============================================================================

dlq_queue_size = Gauge(
    "dlq_queue_size",
    "Current size of DLQ by category",
    labelnames=["category", "status"],
)

dlq_oldest_message_age_seconds = Gauge(
    "dlq_oldest_message_age_seconds",
    "Age of the oldest message in DLQ (in seconds)",
    labelnames=["category"],
)

dlq_processing_active = Gauge(
    "dlq_processing_active",
    "Number of DLQ messages currently being processed",
    labelnames=["category"],
)


# ============================================================================
# Histograms - Distribuições
# ============================================================================

dlq_message_age_seconds = Histogram(
    "dlq_message_age_seconds",
    "Age of messages when added to DLQ",
    labelnames=["category"],
    buckets=(60, 300, 900, 1800, 3600, 7200, 14400, 28800, 86400),  # 1min to 1day
)

dlq_retry_duration_seconds = Histogram(
    "dlq_retry_duration_seconds",
    "Duration of DLQ retry attempts",
    labelnames=["category", "status"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

dlq_retry_attempts_histogram = Histogram(
    "dlq_retry_attempts",
    "Number of retry attempts per message",
    labelnames=["category"],
    buckets=(1, 2, 3, 5, 10, 15, 20),
)


# ============================================================================
# Info - Metadados
# ============================================================================

dlq_info = Info(
    "dlq_info",
    "DLQ configuration and metadata",
)


# ============================================================================
# Helper Functions
# ============================================================================


def record_dlq_message(
    category: str,
    source: str,
    error_type: str,
    message_age_seconds: Optional[float] = None,
) -> None:
    """
    Registra uma nova mensagem adicionada à DLQ.

    Args:
        category: Categoria da mensagem (webhook, whatsapp, flow, etc)
        source: Origem da mensagem
        error_type: Tipo do erro que causou a entrada na DLQ
        message_age_seconds: Idade da mensagem em segundos (opcional)
    """
    dlq_messages_total.labels(
        category=category,
        source=source,
        error_type=error_type,
    ).inc()

    if message_age_seconds is not None:
        dlq_message_age_seconds.labels(category=category).observe(message_age_seconds)


def record_dlq_retry(
    category: str,
    status: str,
    duration_seconds: float,
    error_type: Optional[str] = None,
) -> None:
    """
    Registra uma tentativa de retry de mensagem DLQ.

    Args:
        category: Categoria da mensagem
        status: Status do retry (success, failed, skipped)
        duration_seconds: Duração da tentativa em segundos
        error_type: Tipo do erro em caso de falha (opcional)
    """
    dlq_retries_total.labels(category=category, status=status).inc()

    dlq_retry_duration_seconds.labels(
        category=category,
        status=status,
    ).observe(duration_seconds)

    if status == "success":
        dlq_retries_success_total.labels(
            category=category,
            source="manual",  # ou "automatic" dependendo do contexto
        ).inc()
    elif status == "failed" and error_type:
        dlq_retries_failed_total.labels(
            category=category,
            error_type=error_type,
        ).inc()


def record_dlq_discard(category: str, reason: str) -> None:
    """
    Registra o descarte de uma mensagem DLQ.

    Args:
        category: Categoria da mensagem
        reason: Razão do descarte (manual, max_retries, expired, etc)
    """
    dlq_discard_total.labels(category=category, reason=reason).inc()


def update_dlq_queue_size(category: str, status: str, size: int) -> None:
    """
    Atualiza o tamanho atual da fila DLQ.

    Args:
        category: Categoria da mensagem
        status: Status das mensagens (pending, processing, failed)
        size: Tamanho atual da fila
    """
    dlq_queue_size.labels(category=category, status=status).set(size)


def update_oldest_message_age(category: str, age_seconds: float) -> None:
    """
    Atualiza a idade da mensagem mais antiga na DLQ.

    Args:
        category: Categoria da mensagem
        age_seconds: Idade em segundos
    """
    dlq_oldest_message_age_seconds.labels(category=category).set(age_seconds)


def update_processing_count(category: str, count: int) -> None:
    """
    Atualiza o número de mensagens sendo processadas.

    Args:
        category: Categoria da mensagem
        count: Número de mensagens em processamento
    """
    dlq_processing_active.labels(category=category).set(count)


def record_retry_attempts(category: str, attempts: int) -> None:
    """
    Registra o número de tentativas de retry para uma mensagem.

    Args:
        category: Categoria da mensagem
        attempts: Número de tentativas
    """
    dlq_retry_attempts_histogram.labels(category=category).observe(attempts)


def set_dlq_info(
    max_retries: int,
    retry_delay_seconds: int,
    max_age_hours: int,
    retention_days: int,
) -> None:
    """
    Define informações de configuração da DLQ.

    Args:
        max_retries: Número máximo de retries
        retry_delay_seconds: Delay entre retries
        max_age_hours: Idade máxima de mensagens
        retention_days: Dias de retenção
    """
    dlq_info.info(
        {
            "max_retries": str(max_retries),
            "retry_delay_seconds": str(retry_delay_seconds),
            "max_age_hours": str(max_age_hours),
            "retention_days": str(retention_days),
        }
    )


# ============================================================================
# Initialization
# ============================================================================


def initialize_dlq_metrics(config: dict) -> None:
    """
    Inicializa as métricas DLQ com configuração padrão.

    Args:
        config: Dicionário com configurações da DLQ
    """
    set_dlq_info(
        max_retries=config.get("max_retries", 3),
        retry_delay_seconds=config.get("retry_delay_seconds", 60),
        max_age_hours=config.get("max_age_hours", 72),
        retention_days=config.get("retention_days", 30),
    )

    # Inicializar gauges com valor zero
    categories = ["webhook", "whatsapp", "flow", "quiz", "notification", "other"]
    statuses = ["pending", "processing", "failed"]

    for category in categories:
        for status in statuses:
            dlq_queue_size.labels(category=category, status=status).set(0)
        dlq_oldest_message_age_seconds.labels(category=category).set(0)
        dlq_processing_active.labels(category=category).set(0)


# ============================================================================
# Export
# ============================================================================

__all__ = [
    # Metrics
    "dlq_messages_total",
    "dlq_retries_total",
    "dlq_retries_success_total",
    "dlq_retries_failed_total",
    "dlq_discard_total",
    "dlq_queue_size",
    "dlq_oldest_message_age_seconds",
    "dlq_processing_active",
    "dlq_message_age_seconds",
    "dlq_retry_duration_seconds",
    "dlq_retry_attempts_histogram",
    "dlq_info",
    # Functions
    "record_dlq_message",
    "record_dlq_retry",
    "record_dlq_discard",
    "update_dlq_queue_size",
    "update_oldest_message_age",
    "update_processing_count",
    "record_retry_attempts",
    "set_dlq_info",
    "initialize_dlq_metrics",
]
